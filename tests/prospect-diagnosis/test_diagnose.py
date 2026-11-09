"""Prospect diagnosis: preflight, tool detection, page groups, ranking URLs not live, scoring and verdict.

Headers follow the real Semrush exports seen on a prospect (keyword gap uses "Volume" and "Intents").
Run from the repo root:  python3 -m unittest discover -s tests/prospect-diagnosis -v
"""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

SCRIPT = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/prospect-diagnosis/scripts/diagnose.py'
P, C1, C2 = 'example-spa.com', 'rival-one.com', 'rival-two.com'
CRAWL_HEAD = ['URL', 'Crawl Depth', 'HTTP Status Code', 'Content Type', 'Indexable Status', 'Title', 'H1', 'No. Content Words']
RANK_HEAD = ['Keyword', 'Position', 'Previous position', 'Search Volume', 'Keyword Difficulty', 'CPC', 'URL', 'Traffic',
             'Traffic (%)', 'Traffic Cost']
GAP_HEAD = ['Keyword', 'Intents', 'Volume', 'Keyword Difficulty', 'CPC', 'Competition Density', P, C1, C2,
            f'{P} (pages)', f'{C1} (pages)', f'{C2} (pages)', 'Results']
AHREFS_GAP_HEAD = ['Keyword', 'Volume', 'KD', 'CPC', f'{P}: Position', f'{C1}: Position', f'{C2}: Position']


def write_csv(path, header, rows):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def run(*args, check=True):
    p = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError(p.stdout + p.stderr)
    return p


def crawl(archives=40, empty=False):
    u = f'https://www.{P}'
    rows = [[f'{u}/', 0, 200, 'HTML', 'Indexable', 'Home', 'Welcome', 900]]
    for i in range(20):
        rows.append([f'{u}/services/svc-{i}/', 1, 200, 'HTML', 'Indexable', '' if empty else f'Service {i}',
                     '' if empty else f'Service {i}', 0 if empty else 800])
    for i in range(archives):
        rows.append([f'{u}/blog/tags/tag-{i}/', 2, 200, 'HTML', 'Indexable', f'Tag {i}', 'Tags', 1500])
    rows += [
        [f'{u}/services/svc-0', 2, 301, 'HTML', 'Redirects', '', '', 0],      # slash variant of a live page
        [f'{u}/old-page/', 2, 404, 'HTML', 'Not Indexable', '', '', 0],
        [f'{u}/contact/', 1, 200, 'HTML', 'Indexable', 'Contact', 'Contact', 120],
    ]
    return rows


RANK = [
    ['botox', 3, 3, 9000, 50, 1.0, f'https://www.{P}/services/svc-0/', 300, 10, 100],
    ['old thing', 8, 8, 500, 20, 1.0, f'https://www.{P}/old-page/', 10, 1, 1],
    ['serum', 5, 5, 700, 20, 1.0, f'https://store.{P}/serum/', 20, 1, 1],
]


def gap_rows():
    rows = []
    for i in range(30):   # competitors rank, prospect absent; buying searches where a competitor is top 20
        rows.append([f'botox cost near me {i}', 'Commercial', 1000, 40, 1, 0.5, 0, 5, 30, '', '', '', 100])
    for i in range(10):   # prospect ranks too
        rows.append([f'lip filler {i}', 'Commercial', 900, 30, 1, 0.5, 15, 3, 4, '', '', '', 100])
    rows.append(['rival one spa', 'Navigational', 300, 10, 1, 0.5, 0, 1, 0, '', '', '', 100])
    rows.append(['abdominoplasty recovery', 'Informational', 800, 30, 1, 0.5, 2, 8, 0, '', '', '', 100])
    rows.append(['tummy tuck', 'Commercial', 5000, 30, 1, 0.5, 0, 4, 9, '', '', '', 100])
    rows.append(['mini tummy tuck', 'Commercial', 900, 30, 1, 0.5, 0, 6, 0, '', '', '', 100])
    return rows


class Diagnosis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.cfg = {'client': 'Example Spa', 'domain': P, 'competitors': [C1, C2], 'brand_terms': ['rival one'],
                    'overview': {P: {'authority_score': 10, 'referring_domains': 100, 'referring_domains_12m_ago': 90},
                                 C1: {'authority_score': 30, 'referring_domains': 900, 'referring_domains_12m_ago': 800},
                                 C2: {'authority_score': 28, 'referring_domains': 700, 'referring_domains_12m_ago': 650}}}
        write_csv(self.root / 'rank.csv', RANK_HEAD, RANK)
        write_csv(self.root / 'gap.csv', GAP_HEAD, gap_rows())

    def tearDown(self):
        self.tmp.cleanup()

    def files(self, cfg=None, archives=40, empty=False):
        (self.work / 'config.json').write_text(json.dumps(cfg or self.cfg))
        write_csv(self.root / 'crawl.csv', CRAWL_HEAD, crawl(archives, empty))
        return ['--config', self.work / 'config.json', '--crawl', self.root / 'crawl.csv',
                '--ranking', self.root / 'rank.csv', '--gap', self.root / 'gap.csv']

    def build(self, args, check=True):
        out = self.root / 'diag.xlsx'
        return run('build', *args, '--out', out, check=check), out

    def signals(self, out):
        rows = list(load_workbook(out)['Signals'].values)[1:]
        return {r[1]: r for r in rows}

    def test_preflight_detects_semrush_gap_with_volume_column(self):
        p = run('preflight', *self.files(), '--out', self.work)
        self.assertIn('Semrush', p.stdout)
        self.assertIn('READY', p.stdout)
        self.assertNotIn('NOT READY', p.stdout)

    def test_competitors_come_from_gap_export(self):
        cfg = {k: v for k, v in self.cfg.items() if k != 'competitors'}
        p = run('preflight', *self.files(cfg), '--out', self.work)
        self.assertIn(f'{C1}, {C2} (from the keyword gap export)', p.stdout)
        b, out = self.build(self.files(cfg))
        self.assertIn('Competitors from the keyword gap export', b.stdout)
        self.assertIn('40 of 62', self.signals(out)['A1'][3])

    def test_preflight_fails_on_missing_competitor_column(self):
        cfg = dict(self.cfg, competitors=[C1, 'nobody.com'])
        p = run('preflight', *self.files(cfg), '--out', self.work, check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn('nobody.com', p.stdout)

    def test_ahrefs_gap_detected(self):
        write_csv(self.root / 'gap.csv', AHREFS_GAP_HEAD, [['botox cost', 1000, 40, 1, '', 5, 30]])
        p = run('preflight', *self.files(), '--out', self.work)
        self.assertIn('Ahrefs', p.stdout)

    def test_empty_crawl_stops(self):
        p, _ = self.build(self.files(archives=0, empty=True), check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn('re-crawl', p.stdout)

    def test_archive_pages_score_architecture(self):
        p, out = self.build(self.files(archives=40))
        s = self.signals(out)
        self.assertIn('40 of 62', s['A1'][3])       # 40 tag pages of 62 indexable
        self.assertEqual(s['A1'][5], 2)
        self.assertIn('All checks passed', p.stdout)

    def test_live_row_wins_and_other_host_is_separate(self):
        _, out = self.build(self.files())
        rows = list(load_workbook(out)['Ranking URLs Not Live'].values)[1:]
        status = {r[0]: r[1] for r in rows}
        self.assertNotIn(f'https://www.{P}/services/svc-0/', status)     # the 301 slash variant did not hide it
        self.assertEqual(status[f'https://www.{P}/old-page/'], 404)
        self.assertEqual(status[f'https://store.{P}/serum/'], 'Other host (not crawled)')
        self.assertIn('1 of 2', self.signals(out)['A6'][3])             # store URL not counted

    def test_content_and_brand_exclusion(self):
        _, out = self.build(self.files())
        s = self.signals(out)
        self.assertIn('43 vs 11', s['C1'][3])     # rival-one ranks 43 (brand search left out), prospect 11
        self.assertEqual(s['C1'][5], 2)
        self.assertIn('32 of 32', s['C3'][3])   # 30 botox + 2 tummy tuck buying searches
        kws = [r[0] for r in list(load_workbook(out)['Content'].values)]
        self.assertNotIn('rival one spa', kws)

    def test_authority_from_overview(self):
        _, out = self.build(self.files())
        s = self.signals(out)
        self.assertEqual(s['U1'][5], 2)          # 29 - 10 = 19
        self.assertEqual(s['U2'][5], 1)          # 100 vs 800
        self.assertEqual(s['U3'][5], 'Not scored')

    def test_no_overview_means_authority_not_enough_data(self):
        cfg = {k: v for k, v in self.cfg.items() if k != 'overview'}
        p, out = self.build(self.files(cfg))
        verdict = {r[0]: r for r in list(load_workbook(out)['Verdict'].values)[1:]}
        self.assertEqual(verdict['Authority'][1], 'Not enough data')
        self.assertNotEqual(verdict['Authority'][4], 'Yes')

    def service_table(self, out):
        rows = list(load_workbook(out)['Content'].values)
        i = next(n for n, r in enumerate(rows) if r[0] and str(r[0]).startswith('Non-branded service rankings'))
        out_rows = {}
        for r in rows[i + 1:]:
            if not r[0]:
                break
            out_rows[r[0]] = r
        return out_rows

    def test_service_rankings_with_synonyms(self):
        cfg = dict(self.cfg, service_terms=[{'service': 'Tummy tuck', 'terms': ['abdominoplasty']}, 'botox', 'hydrafacial'])
        _, out = self.build(self.files(cfg))
        t = self.service_table(out)
        self.assertEqual(t['Tummy tuck'][1], 3)       # tummy tuck, mini tummy tuck, abdominoplasty recovery
        self.assertEqual(t['Tummy tuck'][2], 1)       # prospect top 10 once (abdominoplasty, position 2)
        self.assertEqual(t['Tummy tuck'][4], C1)
        self.assertEqual(t['Tummy tuck'][7], 2)       # competitor top 10, prospect not top 20
        self.assertEqual(t['botox'][1], 30)
        self.assertEqual(t['hydrafacial'][8], 'No tracked keywords')
        c2 = self.signals(out)['C2']
        self.assertIn('Top-10 rankings on non-branded service keywords', c2[2])
        self.assertIn('1 vs', c2[3])

    def test_diagnosis_json(self):
        cfg = dict(self.cfg, service_terms=['botox'])
        self.build(self.files(cfg))
        d = json.loads((self.root / 'diagnosis.json').read_text())
        self.assertEqual({v['lens'] for v in d['lenses']}, {'Architecture', 'Content', 'Authority'})
        a1 = next(x for x in d['signals'] if x['id'] == 'A1')
        self.assertEqual(a1['data']['archive'], 40)
        self.assertEqual(d['services'][0]['service'], 'botox')

    def test_c2_falls_back_to_buying_searches(self):
        _, out = self.build(self.files())
        self.assertIn('no service_terms', self.signals(out)['C2'][7])

    def test_estimates_never_summed_and_tabs(self):
        _, out = self.build(self.files())
        wb = load_workbook(out)
        self.assertEqual(wb.sheetnames, ['Read Me', 'Verdict', 'Signals', 'Architecture', 'Content', 'Authority',
                                         'Ranking URLs Not Live'])
        for ws in wb:
            for row in ws.iter_rows(values_only=True):
                for v in row:
                    self.assertNotIn('total volume', str(v).lower())

    def gbp_sheet(self, prospect_cats=('Medical spa',), n_comps=3, rating=4.0):
        from openpyxl import load_workbook as lw
        tpl = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/prospect-diagnosis/references/gbp-template.xlsx'
        wb = lw(tpl)
        k = wb['Keywords']
        for i, kw in enumerate(['med spa near me', 'botox', 'lip filler'], 2):
            k.cell(i, 1, kw)
        g = wb['GBP']
        rows = [['Example Spa', 'Prospect', rating, 40, '; '.join(prospect_cats), 6, 2, None]]
        for n, (r, rev, cats, pos) in enumerate([(4.8, 210, 'Medical spa; Skin care clinic', (1, 1, 2)),
                                                  (4.7, 150, 'Medical spa; Skin care clinic', (2, 3, 1)),
                                                  (4.9, 300, 'Medical spa; Laser hair removal service', (3, 4, 3))][:n_comps]):
            rows.append([f'Rival {n}', 'Competitor', r, rev, cats, *pos])
        for i, row in enumerate(rows, 2):
            for j, v in enumerate(row, 1):
                g.cell(i, j, v)
        path = self.root / 'gbp.xlsx'
        wb.save(path)
        return path

    def test_gbp_findings_and_lens_unchanged(self):
        _, base = self.build(self.files())
        before = [r[:5] for r in list(load_workbook(base)['Verdict'].values)]
        _, out = self.build(self.files() + ['--gbp', self.gbp_sheet()])
        wb = load_workbook(out)
        self.assertIn('Google Business Profile', wb.sheetnames)
        rows = {r[0]: r for r in list(wb['Google Business Profile'].values)[1:5]}
        self.assertEqual([rows[i][3] for i in ('G1', 'G2', 'G3', 'G4')], ['Yes'] * 4)
        self.assertIn('Skin care clinic', rows['G4'][4])
        self.assertEqual(before, [r[:5] for r in list(wb['Verdict'].values)])   # GBP never changes the lens verdict
        d = json.loads((self.root / 'diagnosis.json').read_text())
        self.assertTrue(d['gbp']['assessed'])

    def test_gbp_ok_when_close_to_competitors(self):
        _, out = self.build(self.files() + ['--gbp', self.gbp_sheet(('Medical spa', 'Skin care clinic', 'Laser hair removal service'), rating=4.7)])
        rows = {r[0]: r for r in list(load_workbook(out)['Google Business Profile'].values)[1:5]}
        self.assertEqual(rows['G1'][3], 'No')
        self.assertEqual(rows['G4'][3], 'No')

    def test_gbp_missing_or_incomplete_still_runs(self):
        r, out = self.build(self.files())
        self.assertIn('Google Business Profile: not assessed', r.stdout)
        self.assertNotIn('Google Business Profile', load_workbook(out).sheetnames)
        r, out = self.build(self.files() + ['--gbp', self.gbp_sheet(n_comps=2)])
        self.assertIn('need at least 3 competitors', r.stdout)
        p = run('preflight', *self.files(), '--gbp', self.gbp_sheet(n_comps=2), '--out', self.work)
        self.assertIn('WARN | Google Business Profile (sheet)', p.stdout)


if __name__ == '__main__':
    unittest.main()
