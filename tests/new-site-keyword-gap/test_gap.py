"""New-site keyword gap: preflight, brand removal, groups, flags, Ahrefs headers.

Run from the repo root:  python3 -m unittest discover -s tests/new-site-keyword-gap -v
"""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

SCRIPT = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/new-site-keyword-gap/scripts/gap.py'
C1, C2, C3 = 'rival-one.com', 'rival-two.com', 'rival-three.com'
GAP_HEAD = ['Keyword', 'Intents', 'Volume', 'Keyword Difficulty', 'CPC', 'Competition Density', C1, C2, C3,
            f'{C1} (pages)', f'{C2} (pages)', f'{C3} (pages)', 'Results']
RANK_HEAD = ['Keyword', 'Position', 'Previous position', 'Search Volume', 'Keyword Difficulty', 'CPC', 'URL', 'Traffic']
# keyword, volume, positions for C1, C2, C3 (blank = not ranking)
ROWS = [
    ('botox cost', 900, 2, 8, ''),            # service, A (two top 10) and B
    ('botox near me', 500, 5, '', ''),         # local (near me)
    ('botox in miami', 300, 4, 6, 40),         # local (city)
    ('laser hair removal', 700, 15, 20, 7),    # service, one top 10, not A, not B
    ('tummy tuck recovery', 200, '', 3, ''),   # service, B only
    ('rival one botox', 400, 1, '', ''),       # branded (name)
    ('rivaltwo specials', 100, '', 1, ''),     # branded (domain stem joined)
    ('skin care routine', 800, 9, 9, 9),       # unassigned, A
    ('nothing ranks here', 50, '', '', ''),    # no competitor ranks
]


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


class GapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        t = self.tmp
        write_csv(t / 'gap.csv', GAP_HEAD, [[k, 'Commercial', v, 30, 1, 0.5, a, b, c, '', '', '', 100] for k, v, a, b, c in ROWS])
        self.rank = {}
        for i, d in enumerate((C1, C2, C3)):
            rows = [[k, r[2 + i], '', r[1], 30, 1, f'https://{d}/' + k.replace(' ', '-') + '/', 10]
                    for k in [x[0] for x in ROWS] for r in [next(y for y in ROWS if y[0] == k)] if r[2 + i] != '']
            rows.append(['home', 50, '', 10, 1, 1, f'https://{d}/', 1])
            write_csv(t / f'{d}.csv', RANK_HEAD, rows)
            self.rank[d] = t / f'{d}.csv'
        self.cfg = {'business': 'New Spa', 'competitors': {C1: ['rival one'], C2: ['rival two spa'], C3: ['third rival']},
                    'service_terms': ['botox', {'service': 'Tummy tuck', 'terms': ['abdominoplasty']}, 'laser hair removal'],
                    'cities': ['miami']}
        self.cfg_path = t / 'config.json'
        self.write_cfg()

    def write_cfg(self):
        self.cfg_path.write_text(json.dumps(self.cfg))

    def args(self, cmd, out):
        a = [cmd, '--config', self.cfg_path, '--gap', self.tmp / 'gap.csv', '--out', out]
        for d, p in self.rank.items():
            a += ['--ranking', f'{d}={p}']
        return a

    def test_preflight_ready_and_candidates(self):
        p = run(*self.args('preflight', self.tmp / 'work'))
        self.assertIn('READY', p.stdout)
        self.assertIn('semrush', p.stdout)
        self.assertTrue((self.tmp / 'work' / 'candidates.md').exists())

    def test_preflight_fails_without_competitor_name(self):
        del self.cfg['competitors'][C3]
        self.write_cfg()
        p = run(*self.args('preflight', self.tmp / 'work'), check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(f'No competitor name for {C3}', p.stdout)

    def test_preflight_fails_without_ranking_export(self):
        del self.rank[C2]
        p = run(*self.args('preflight', self.tmp / 'work'), check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(f'No Organic Positions export for {C2}', p.stdout)

    def test_preflight_fails_without_service_terms(self):
        self.cfg['service_terms'] = []
        self.write_cfg()
        p = run(*self.args('preflight', self.tmp / 'work'), check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('service_terms', p.stdout)

    def test_build(self):
        out = self.tmp / 'out.xlsx'
        p = run(*self.args('build', out))
        self.assertIn('All checks passed', p.stdout)
        wb = load_workbook(out)
        self.assertEqual(wb.sheetnames, ['Read Me', 'Summary', 'Service opportunities', 'Keywords', 'Local', 'Competitor pages',
                                         'Unassigned', 'Branded removed'])
        summ = {r[0]: r[1] for r in wb['Summary'].iter_rows(min_row=2, values_only=True) if r[0]}
        self.assertEqual(summ['Removed as branded (a competitor name)'], 2)
        self.assertEqual(summ['No competitor ranks (empty position columns)'], 1)
        self.assertEqual(summ['Non-branded keywords analysed'], 6)
        self.assertEqual(summ['In the Local group (city or near me)'], 2)
        self.assertEqual(summ['Unassigned (no service or city term matched)'], 1)
        self.assertEqual(summ['Flagged A (2 or more competitors in the top 10)'], 3)   # botox cost, botox in miami, skin care
        self.assertEqual(summ['Flagged B (a competitor in the top 3)'], 2)             # botox cost, tummy tuck recovery
        # service rows
        svc = {r[0]: r for r in wb['Service opportunities'].iter_rows(min_row=2, values_only=True)}
        self.assertEqual(svc['botox'][1], 1)            # only 'botox cost' is a service keyword; the other two are Local
        self.assertEqual(svc['Tummy tuck'][1], 1)       # 'tummy tuck recovery' contains the service name
        self.assertEqual(svc['Tummy tuck'][3], 1)       # and one competitor is top 3 for it
        self.assertEqual(svc['laser hair removal'][4], 0)
        # branded keywords are not in any group tab
        kws = [r[0] for ws in ('Keywords', 'Local', 'Unassigned') for r in wb[ws].iter_rows(min_row=2, values_only=True)]
        self.assertNotIn('rival one botox', kws)
        self.assertNotIn('rivaltwo specials', kws)
        # the page of the best competitor comes from that competitor's ranking export
        top = next(r for r in wb['Keywords'].iter_rows(min_row=2, values_only=True) if r[0] == 'botox cost')
        self.assertEqual(top[8], C1)
        self.assertEqual(top[9], 2)
        self.assertEqual(top[10], f'https://{C1}/botox-cost/')

    def test_ahrefs_headers(self):
        head = ['Keyword', 'Volume', 'KD', 'CPC'] + [f'{d}: Position' for d in (C1, C2, C3)]
        write_csv(self.tmp / 'gap.csv', head, [[k, v, 20, 1, a, b, c] for k, v, a, b, c in ROWS])
        rh = ['Keyword', 'Volume', 'KD', 'Current position', 'Current URL']
        for d in (C1, C2, C3):
            write_csv(self.tmp / f'{d}.csv', rh, [['botox cost', 900, 20, 2, f'https://{d}/botox-cost/']])
        p = run(*self.args('preflight', self.tmp / 'work'))
        self.assertIn('ahrefs', p.stdout)


if __name__ == '__main__':
    unittest.main()
