"""Prospect audit: crawl checks, tool detection (Semrush and Ahrefs), keyword gap groups, thin content, workbook.

The export headers are written from the tools' documented column names, not from real files.
Run from the repo root:  python3 -m unittest discover -s tests/prospect-audit -v
"""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

SKILL = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/prospect-audit/scripts'
PROSPECT, C1, C2 = 'example-spa.com', 'rival-one.com', 'rival-two.com'


def write_csv(path, header, rows):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def run(script, *args, check=True):
    p = subprocess.run([sys.executable, str(SKILL / script), *map(str, args)], capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError(p.stdout + p.stderr)
    return p


def crawl_rows(empty=False):
    rows = []
    for i in range(12):
        rows.append([f'https://{PROSPECT}/blog/post-{i}/', 200, 'Indexable', '' if empty else f'Post {i}', '' if empty else f'Post {i}', 0 if empty else 900])
    rows += [
        [f'https://{PROSPECT}/', 200, 'Indexable', 'Home', 'Welcome', 700],
        [f'https://{PROSPECT}/botox/', 200, 'Indexable', 'Botox in Springfield', 'Botox', 150],
        [f'https://{PROSPECT}/contact/', 200, 'Indexable', 'Contact', 'Contact', 40],
        [f'https://{PROSPECT}/old-fillers/', 404, 'Not Indexable', '', '', 0],
    ]
    return rows


CRAWL_HEAD = ['URL', 'HTTP Status Code', 'Indexable Status', 'Title', 'H1', 'No. Content Words']
SEMRUSH_RANK = ['Keyword', 'Position', 'Previous position', 'Search Volume', 'Keyword Difficulty', 'CPC', 'URL', 'Traffic', 'Traffic (%)', 'Traffic Cost']
AHREFS_RANK = ['Keyword', 'Volume', 'KD', 'CPC', 'Organic traffic', 'Current position', 'Current URL']
SEMRUSH_GAP = ['Keyword', PROSPECT, C1, C2, 'Search Volume', 'Keyword Difficulty', 'CPC', 'Competitive Density']
AHREFS_GAP = ['Keyword', 'Volume', 'KD', f'{PROSPECT}: Position', f'{C1}: Position', f'{C2}: Position', f'{C1}: URL']

GAP = [  # keyword, prospect, c1, c2, volume
    ['botox cost near me', '', 3, 8, 5400], ['dysport vs botox', '', 12, '', 900],
    ['lip filler', '', 5, 9, 3000], ['rival one spa', '', 1, '', 200],
    ['laser hair removal', 4, 2, 1, 2000], ['hydrafacial treatment', '', '', '', 1000]]


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        (self.work / 'config.json').write_text(json.dumps({'client': 'Example Spa', 'domain': PROSPECT, 'competitors': [C1, C2]}))

    def tearDown(self):
        self.tmp.cleanup()

    def crawl(self, empty=False):
        write_csv(self.root / 'crawl.csv', CRAWL_HEAD, crawl_rows(empty))
        return run('prep.py', 'crawl', '--crawl', self.root / 'crawl.csv', '--out', self.work, check=not empty)

    def test_empty_crawl_fails(self):
        p = self.crawl(empty=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn('FAIL', p.stdout)

    def test_crawl_thin_candidates(self):
        p = self.crawl()
        self.assertIn('PASS crawl', p.stdout)
        urls = (self.work / 'thin_candidates.csv').read_text()
        self.assertIn('/botox/', urls)
        self.assertIn('/contact/', urls)
        self.assertNotIn('/old-fillers/', urls)  # 404 is not a thin page

    def keywords(self, tool):
        if tool == 'semrush':
            write_csv(self.root / 'rank.csv', SEMRUSH_RANK, [
                ['botox', 4, 5, 8100, 40, 2, f'https://{PROSPECT}/botox/', 300, '1.2', 500],
                ['lip filler', 30, 30, 3000, 40, 2, f'https://{PROSPECT}/old-fillers/', 20, '0.1', 50]])
            write_csv(self.root / 'gap.csv', SEMRUSH_GAP, [[k, a, b, c, v, 40, 2, 0.5] for k, a, b, c, v in GAP])
        else:
            write_csv(self.root / 'rank.csv', AHREFS_RANK, [
                ['botox', 8100, 40, 2, 300, 4, f'https://{PROSPECT}/botox/'],
                ['lip filler', 3000, 40, 2, 20, 30, f'https://{PROSPECT}/old-fillers/']])
            write_csv(self.root / 'gap.csv', AHREFS_GAP, [[k, v, 40, a, b, c, ''] for k, a, b, c, v in GAP])
        return run('prep.py', 'keywords', '--config', self.work / 'config.json', '--ranking', self.root / 'rank.csv',
                   '--gap', self.root / 'gap.csv', '--out', self.work)

    def full_run(self, tool):
        self.crawl()
        p = self.keywords(tool)
        self.assertIn(f'detected {tool.capitalize()}', p.stdout)
        gap = (self.work / 'gap.csv').read_text()
        self.assertNotIn('laser hair removal', gap)   # prospect ranks
        self.assertNotIn('hydrafacial', gap)          # nobody ranks
        self.assertIn('botox cost near me', gap)
        (self.work / 'gap_groups.json').write_text(json.dumps([
            {'group': 'Competitor brand', 'kind': 'exclude', 'terms': ['rival one']},
            {'group': 'Botox and neurotoxin', 'practice_type': 'medspa', 'kind': 'service', 'terms': ['botox', 'dysport']},
            {'group': 'Lip filler', 'practice_type': 'medspa', 'kind': 'service', 'terms': ['lip filler']}]))
        (self.work / 'thin_decisions.json').write_text(json.dumps({'exclude_folders': ['contact'], 'exclude_urls': [f'https://{PROSPECT}/contact/']}))
        out = self.root / 'audit.xlsx'
        b = run('build.py', '--work', self.work, '--out', out)
        self.assertIn('All checks passed', b.stdout)
        return load_workbook(out)

    def test_semrush_workbook(self):
        wb = self.full_run('semrush')
        self.assertEqual(wb.sheetnames, ['Read Me', 'Summary', 'Competitor Keyword Gap', 'Gap Keywords', 'Thin Content', 'Ranking URLs Not Live', 'Ranking Pages'])
        gaprows = {r[0].value: r for r in wb['Competitor Keyword Gap'].iter_rows(min_row=2)}
        self.assertEqual(set(gaprows), {'Botox and neurotoxin', 'Lip filler'})
        botox = gaprows['Botox and neurotoxin']
        self.assertEqual(botox[3].value, 2)                      # two keywords
        self.assertEqual(botox[4].value, 'botox cost near me')   # largest search
        self.assertEqual(botox[6].value, 3)                      # best position of rival-one
        lip = gaprows['Lip filler']
        self.assertEqual(lip[-4].value, 0)                       # no page matches "lip filler"
        self.assertEqual(lip[-3].value, 'Possible missing service page')
        self.assertEqual(botox[-3].value, 'Only thin pages match')  # the botox page has 150 words
        nl = [r[0].value for r in wb['Ranking URLs Not Live'].iter_rows(min_row=2)]
        self.assertEqual(nl, [f'https://{PROSPECT}/old-fillers/'])
        thin = [r[0].value for r in wb['Thin Content'].iter_rows(min_row=2)]
        self.assertEqual(thin, [f'https://{PROSPECT}/botox/'])
        heads = ' '.join(str(c.value) for ws in wb.worksheets for c in ws[1]).lower()
        self.assertNotIn('impressions', heads)
        self.assertNotIn('clicks', heads)

    def test_ahrefs_workbook(self):
        wb = self.full_run('ahrefs')
        self.assertIn('Competitor Keyword Gap', wb.sheetnames)

    def preflight(self, **files):
        args = ['preflight', '--config', self.work / 'config.json', '--out', self.work]
        for k, v in files.items():
            args += [f'--{k.replace("_", "-")}', v]
        return run('prep.py', *args, check=False)

    def test_preflight_ready_and_not_ready(self):
        cfg = json.loads((self.work / 'config.json').read_text())
        cfg.update({'brand_terms': ['example spa'], 'practice_type': 'medspa'})
        (self.work / 'config.json').write_text(json.dumps(cfg))
        write_csv(self.root / 'crawl.csv', CRAWL_HEAD, crawl_rows())
        write_csv(self.root / 'rank.csv', SEMRUSH_RANK, [['botox', 4, 5, 8100, 40, 2, f'https://{PROSPECT}/botox/', 300, '1.2', 500]])
        write_csv(self.root / 'gap.csv', SEMRUSH_GAP, [[k, a, b, c, v, 40, 2, 0.5] for k, a, b, c, v in GAP])
        ok = self.preflight(crawl=self.root / 'crawl.csv', ranking=self.root / 'rank.csv', gap=self.root / 'gap.csv')
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertIn('READY', ok.stdout)
        self.assertIn('SKIP', ok.stdout)  # backlink exports are optional
        # the ranking file passed as the gap file, and no crawl
        bad = self.preflight(ranking=self.root / 'rank.csv', gap=self.root / 'rank.csv')
        self.assertEqual(bad.returncode, 2)
        self.assertIn('NOT READY', bad.stdout)
        self.assertIn('Crawl URL export', bad.stdout)
        self.assertIn('Keyword gap export', bad.stdout)

    def test_unknown_tool_stops(self):
        self.crawl()
        write_csv(self.root / 'rank.csv', ['Keyword', 'Position', 'URL', 'Search Volume', 'Volume'], [['a', 1, 'https://x.com/', 10, 10]])
        p = run('prep.py', 'keywords', '--config', self.work / 'config.json', '--ranking', self.root / 'rank.csv', '--out', self.work, check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('--tool', p.stdout + p.stderr)


if __name__ == '__main__':
    unittest.main()
