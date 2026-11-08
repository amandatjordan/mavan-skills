"""Client diagnosis: the 6-month Search Console split, the capped-export check, keyword drops, GSC signals, the
manual action rule and the end-to-end build with the report reading it.

Run from the repo root:  python3 -m unittest discover -s tests/client-diagnosis -v
"""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / 'plugins/mavan-seo/skills'
sys.path.insert(0, str(SKILLS / 'client-diagnosis/scripts'))
import diagnose  # noqa: E402
import gsc  # noqa: E402

DIAG = SKILLS / 'client-diagnosis/scripts/diagnose.py'
REPORT = SKILLS / 'prospect-sales-report/scripts/report.py'
P, C1, C2 = 'example-spa.com', 'rival-one.com', 'rival-two.com'


def days(start, n):
    return pd.date_range(start, periods=n, freq='D')


def make_gsc(rows):
    """rows: (date, query, page, clicks, impressions, position)"""
    return pd.DataFrame(rows, columns=['Date', 'Query', 'Page', 'Clicks', 'Impressions', 'Position'])


def year_rows(zero_clicks_in_b=True, a_clicks=10, b_clicks=4):
    """One year 2025-11-07 .. 2026-11-06, two real searches, plus zero-click filler rows."""
    rows = []
    for d in days('2025-11-07', 365):
        in_b = d >= pd.Timestamp('2026-05-07')
        click = 1 if d.day == 1 else 0
        if not in_b or zero_clicks_in_b:
            rows.append((d.date(), 'botox near me', f'https://{P}/botox/', click, 10, 12.0))
            rows.append((d.date(), 'filler cost', f'https://{P}/filler/', 0, 5, 9.0))
        elif click:     # a capped export keeps only the rows that had a click
            rows.append((d.date(), 'botox near me', f'https://{P}/botox/', click, 10, 12.0))
    rows.append((pd.Timestamp('2026-11-06').date(), 'botox near me', f'https://{P}/botox/', 1, 10, 12.0))  # newest date
    rows.append((pd.Timestamp('2026-01-05').date(), 'lip filler', f'https://{P}/filler/', a_clicks, 100, 8.0))
    rows.append((pd.Timestamp('2026-08-05').date(), 'lip filler', f'https://{P}/filler/', b_clicks, 100, 8.0))
    rows.append((pd.Timestamp('2026-01-06').date(), 'balance spa', f'https://{P}/', 7, 20, 1.0))
    return rows


def prep(rows, brand=('balance',), path=None):
    tmp = Path(tempfile.mkdtemp()) / 'gsc.csv'
    make_gsc(rows).to_csv(tmp, index=False)
    return gsc.load(str(tmp), None, P, list(brand))


class Periods(unittest.TestCase):
    def test_two_six_month_periods_end_on_newest_date_and_do_not_overlap(self):
        df, _ = prep(year_rows())
        p = gsc.periods(df)
        self.assertEqual(p['b_end'], pd.Timestamp('2026-11-06'))
        self.assertEqual(p['b_start'], pd.Timestamp('2026-05-07'))
        self.assertEqual(p['a_start'], pd.Timestamp('2025-11-07'))
        self.assertEqual(p['a_end'], pd.Timestamp('2026-05-06'))
        a, b = gsc.split(df, p)
        self.assertEqual(len(a) + len(b), len(df))

    def test_short_export_does_not_cover_the_year(self):
        df, _ = prep([(d.date(), 'q', f'https://{P}/', 1, 5, 3.0) for d in days('2026-10-09', 29)])
        self.assertFalse(gsc.profile(df)['covered'])

    def test_full_year_is_covered(self):
        df, _ = prep(year_rows())
        self.assertTrue(gsc.profile(df)['covered'])


class CappedExport(unittest.TestCase):
    def test_capped_export_marks_impressions_not_comparable(self):
        df, _ = prep(year_rows(zero_clicks_in_b=False))
        prof = gsc.profile(df)
        self.assertFalse(prof['comparable'])
        self.assertIn('not comparable', prof['reason'])

    def test_complete_export_is_comparable(self):
        df, _ = prep(year_rows(zero_clicks_in_b=True))
        self.assertTrue(gsc.profile(df)['comparable'])


class Brand(unittest.TestCase):
    def test_brand_is_whole_word_only(self):
        rx = gsc.brand_re(['balance', 'balance aesthetic'])
        self.assertTrue(rx.search('balance spa brandon'))
        self.assertTrue(rx.search('balance  aesthetic'))
        self.assertFalse(rx.search('counterbalance'))
        self.assertFalse(rx.search('balanced diet'))

    def test_brand_rows_leave_non_brand_figures(self):
        df, _ = prep(year_rows())
        a, b = gsc.split(df, gsc.periods(df))
        q = gsc.query_table(a, b)
        self.assertNotIn('balance spa', set(q['query']))


class Drops(unittest.TestCase):
    def setUp(self):
        df, _ = prep(year_rows(a_clicks=10, b_clicks=4))
        a, b = gsc.split(df, gsc.periods(df))
        self.q = gsc.query_table(a, b)

    def test_only_clicks_that_fell_are_listed(self):
        d = gsc.drops(self.q, True, 3, 50)
        self.assertIn('lip filler', set(d['query']))
        self.assertTrue((d[d['basis'].str.startswith('Clicks')]['change'] < 0).all())
        row = d[d['query'] == 'lip filler'].iloc[0]
        self.assertEqual((row['clicks_a'], row['clicks_b'], row['change']), (10, 4, -6))

    def test_low_numbers_are_labelled(self):
        d = gsc.drops(self.q, False, 50, 50)     # floor above both periods' clicks
        self.assertEqual(d[d['query'] == 'lip filler'].iloc[0]['basis'], 'Clicks (low numbers)')

    def test_impressions_judge_a_keyword_only_when_comparable(self):
        q = pd.DataFrame([{'query': 'x', 'clicks_a': 1, 'clicks_b': 1, 'impr_a': 200, 'impr_b': 20, 'pos_a': 5, 'pos_b': 9,
                           'change': 0, 'top_page_a': ''}])
        self.assertEqual(len(gsc.drops(q, True, 3, 50)), 1)
        self.assertEqual(gsc.drops(q, True, 3, 50).iloc[0]['basis'], 'Impressions (clicks too low)')
        self.assertEqual(len(gsc.drops(q, False, 3, 50)), 0)


class Signals(unittest.TestCase):
    def run_gsc(self, rows, other_pages=None):
        df, _ = prep(rows)
        prof = gsc.profile(df)
        a, b = gsc.split(df, prof)
        G = {'prof': prof, 'a': a, 'b': b, 'q': gsc.query_table(a, b), 'has_position': True,
             'archive_re': diagnose.re.compile('|'.join(diagnose.ARCHIVE_PATTERNS), diagnose.re.I)}
        S = diagnose.Signals()
        out = gsc.score_gsc(S, G, other_pages or {f'https://{P}/botox/', f'https://{P}/never/'}, [], 3, 50)
        return {r['id']: r for r in S.rows}, out

    def test_impression_signals_not_scored_when_capped(self):
        s, out = self.run_gsc(year_rows(zero_clicks_in_b=False))
        for sid in ('A7', 'A8', 'A9', 'C6'):
            self.assertIsNone(s[sid]['points'], sid)
        self.assertFalse(out['a7_scored'])
        self.assertIsNotNone(s['C5']['points'])        # clicks are complete

    def test_impression_signals_scored_when_complete(self):
        s, out = self.run_gsc(year_rows(zero_clicks_in_b=True))
        for sid in ('A7', 'A8', 'C5'):
            self.assertIsNotNone(s[sid]['points'], sid)
        self.assertTrue(out['a7_scored'])
        self.assertEqual(s['A7']['data']['no_impressions'], 1)    # /never/ had no impressions

    def test_traffic_drop_scores_one_point(self):
        s, _ = self.run_gsc(year_rows(zero_clicks_in_b=True, a_clicks=30, b_clicks=5))
        self.assertEqual(s['C5']['points'], 1)
        self.assertEqual(s['C5']['data']['basis'], 'clicks')

    def test_competing_pages_found(self):
        rows = year_rows(zero_clicks_in_b=True)
        d = pd.Timestamp('2026-09-01').date()
        rows += [(d, 'tummy tuck', f'https://{P}/a/', 0, 30, 6.0), (d, 'tummy tuck', f'https://{P}/b/', 0, 25, 7.0)]
        s, out = self.run_gsc(rows)
        self.assertEqual([r[0] for r in out['competing_rows']], ['tummy tuck'])
        self.assertEqual(s['A9']['data']['competing'], 1)


class ManualAction(unittest.TestCase):
    def S(self, value):
        S = diagnose.Signals()
        S.add('Authority', 'U1', 'x', '', '', 0, 2)
        S.add('Authority', 'U2', 'x', '', '', 0, 1)
        m = gsc.manual_action_signal(S, value)
        return S, m

    def test_yes_makes_authority_high(self):
        S, m = self.S('yes')
        lenses, _ = diagnose.verdict(S, m)
        a = next(v for v in lenses if v['lens'] == 'Authority')
        self.assertEqual(a['severity'], 'High')
        self.assertEqual(a['share'], 1.0)

    def test_no_and_unknown_do_not(self):
        for value in ('no', '', 'unknown'):
            S, m = self.S(value)
            lenses, _ = diagnose.verdict(S, m)
            self.assertEqual(next(v for v in lenses if v['lens'] == 'Authority')['severity'], 'Low')
        S, _ = self.S('unknown')
        self.assertIsNone(next(r for r in S.rows if r['id'] == 'U5')['points'])


def write_csv(path, header, rows):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.root = Path(self.tmp.name)
        u = f'https://www.{P}'
        crawl = [[f'{u}/', 0, 200, 'HTML', 'Indexable', 'Home', 'Welcome', 900]]
        crawl += [[f'{u}/services/s{i}/', 1, 200, 'HTML', 'Indexable', f'S{i}', f'S{i}', 800] for i in range(20)]
        crawl += [[f'{u}/botox/', 1, 200, 'HTML', 'Indexable', 'Botox', 'Botox', 800],
                  [f'{u}/filler/', 1, 200, 'HTML', 'Indexable', 'Filler', 'Filler', 800]]
        write_csv(r / 'crawl.csv', ['URL', 'Crawl Depth', 'HTTP Status Code', 'Content Type', 'Indexable Status', 'Title', 'H1',
                                    'No. Content Words'], crawl)
        write_csv(r / 'rank.csv', ['Keyword', 'Position', 'Search Volume', 'Keyword Difficulty', 'URL', 'Traffic'],
                  [['botox', 3, 9000, 50, f'{u}/botox/', 300], ['filler', 5, 500, 20, f'{u}/filler/', 10]])
        gap = [[f'botox cost near me {i}', 'Commercial', 1000, 40, 1, 0.5, 0, 5, 30, '', '', '', 100] for i in range(30)]
        write_csv(r / 'gap.csv', ['Keyword', 'Intents', 'Volume', 'Keyword Difficulty', 'CPC', 'Competition Density', P, C1, C2,
                                  f'{P} (pages)', f'{C1} (pages)', f'{C2} (pages)', 'Results'], gap)
        make_gsc(year_rows(zero_clicks_in_b=False)).to_csv(r / 'gsc.csv', index=False)
        self.cfg = {'client': 'Example Spa', 'domain': P, 'brand_terms': ['balance'], 'manual_action': 'no',
                    'service_terms': ['botox', 'filler'],
                    'overview': {P: {'authority_score': 10, 'referring_domains': 100, 'referring_domains_12m_ago': 90},
                                 C1: {'authority_score': 12, 'referring_domains': 120, 'referring_domains_12m_ago': 100},
                                 C2: {'authority_score': 11, 'referring_domains': 110, 'referring_domains_12m_ago': 95}}}
        (r / 'config.json').write_text(json.dumps(self.cfg))

    def tearDown(self):
        self.tmp.cleanup()

    def args(self):
        r = self.root
        return ['--config', r / 'config.json', '--crawl', r / 'crawl.csv', '--ranking', r / 'rank.csv', '--gap', r / 'gap.csv',
                '--gsc', r / 'gsc.csv']

    def run_script(self, script, *a, check=True):
        p = subprocess.run([sys.executable, str(script), *map(str, a)], capture_output=True, text=True)
        if check and p.returncode:
            raise AssertionError(p.stdout + p.stderr)
        return p

    def test_preflight_warns_about_capped_impressions(self):
        p = self.run_script(DIAG, 'preflight', *self.args(), '--out', self.root / 'work')
        self.assertIn('not comparable', p.stdout)
        self.assertIn('READY', p.stdout)

    def test_preflight_fails_on_short_export_and_missing_brand_terms(self):
        make_gsc([(d.date(), 'q', f'https://{P}/', 1, 5, 3.0) for d in days('2026-10-09', 29)]).to_csv(
            self.root / 'gsc.csv', index=False)
        (self.root / 'config.json').write_text(json.dumps({k: v for k, v in self.cfg.items() if k != 'brand_terms'}))
        p = self.run_script(DIAG, 'preflight', *self.args(), '--out', self.root / 'work', check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn('Brand terms', p.stdout)
        self.assertIn('less than the 12 months', p.stdout)

    def test_build_then_client_report(self):
        out = self.root / 'diag.xlsx'
        p = self.run_script(DIAG, 'build', *self.args(), '--out', out)
        self.assertIn('All checks passed', p.stdout)
        wb = load_workbook(out)
        self.assertTrue({'Search Console', 'Keyword Drops'} <= set(wb.sheetnames))
        sig = {r[1]: r for r in list(wb['Signals'].values)[1:]}
        self.assertEqual(sig['A7'][5], 'Not scored')
        self.assertNotEqual(sig['C5'][5], 'Not scored')
        self.assertIn('A3', sig)                       # the keyword-tool proxy stays when A7 cannot be scored
        data = json.loads((self.root / 'diagnosis.json').read_text())
        self.assertEqual(data['report_type'], 'client')
        self.assertFalse(data['gsc']['impressions_comparable'])
        page = self.root / 'report.html'
        r = self.run_script(REPORT, 'build', '--workbook', out, '--tier', 'signature', '--out', page)
        self.assertIn('All checks passed', r.stdout)
        html = page.read_text()
        self.assertNotIn('Onboarding', html)
        self.assertIn('Month 1', html)
        self.assertIn('Search Console figures are actual clicks', html)


if __name__ == '__main__':
    unittest.main()
