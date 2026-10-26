"""The optional exports still work when attached, and bot protection is not mistaken for broken pages.

Run from the repo root:  python3 -m unittest discover -s tests/backlink-audit -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

import test_two_file_semrush as base
from test_two_file_semrush import CLIENT, COMPS, HOME, SKILL, write_csv

sys.path.insert(0, str(SKILL / 'scripts'))
import build  # noqa: E402


class OptionalExportsAttached(unittest.TestCase):
    """Same audit, plus referring domains, a comparison export and a broken-backlinks export."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        work = root / 'work'
        work.mkdir()
        write_csv(root / 'backlinks.csv', base.BACKLINK_HEADER, base.backlinks_rows())
        write_csv(root / 'gap.csv', base.GAP_HEADER, base.gap_rows())
        doms = sorted({r[2].split('/')[2] for r in base.backlinks_rows()})
        write_csv(root / 'refdomains.csv', ['Domain', 'Domain ascore', 'Backlinks'], [[d, 40, 1] for d in doms])
        write_csv(root / 'compare.csv', ['Target', 'Authority Score', 'Referring Domains', 'Backlinks'],
                  [[CLIENT, 30, 500, 900], ['comp-one.com', 45, 1200, 4000], ['comp-two.com', 38, 800, 2500],
                   ['comp-three.com', 41, 950, 3100]])
        write_csv(root / 'broken.csv', ['Source url', 'Target url', 'Response code'],
                  [['https://localsite3.com/blog/post-3/', f'{HOME}old-botox-page/', '404']])
        (work / 'config.json').write_text(json.dumps({
            'client': 'Example Med Spa', 'domain': CLIENT, 'tool': 'semrush', 'competitors': COMPS,
            'brand_terms': ['example med spa'], 'manual_action': 'none', 'safe_domains': []}))
        cls.prep = base.TwoFileSemrushAudit.run_py(
            'prep.py', '--config', str(work / 'config.json'), '--out', str(work),
            '--backlinks', str(root / 'backlinks.csv'), '--gap', str(root / 'gap.csv'),
            '--refdomains', str(root / 'refdomains.csv'), '--compare', str(root / 'compare.csv'),
            '--broken', str(root / 'broken.csv'))
        (work / 'status.tsv').write_text(base.fake_status((work / 'status_needed.txt').read_text().split()))
        (work / 'decisions.json').write_text(json.dumps({
            'takeaways': ['a 1.', 'b 2.', 'c 3.'],
            'broken': {f'{HOME}old-botox-page/': {'target': f'{HOME}services/botox/'},
                       f'{HOME}sevices/': {'target': f'{HOME}services/', 'action': 'typo'},
                       f'{HOME}blocked-page/': {'action': 'drop'}},
            'opportunities': {'frankfurtmedspa.com': {'type': 'Industry publication / blog'},
                              'onecomp-highauth.com': {'type': 'Industry publication / blog'}}}))
        cls.out = root / 'audit.xlsx'
        cls.build = base.TwoFileSemrushAudit.run_py('build.py', '--work', str(work), '--out', str(cls.out))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_passes_and_lists_no_broken_url_twice(self):
        self.assertEqual(self.prep.returncode, 0, self.prep.stdout + self.prep.stderr)
        self.assertEqual(self.build.returncode, 0, self.build.stdout + self.build.stderr)
        self.assertIn('All checks passed', self.build.stdout)

    def test_comparison_export_fills_competitor_rows(self):
        ws = load_workbook(self.out)['Competitor Rollup']
        rows = [dict(zip([c.value for c in ws[1]], [c.value for c in r])) for r in ws.iter_rows(min_row=2)]
        by = {r['Domain']: r for r in rows if r['Domain'] in [CLIENT] + COMPS}
        self.assertEqual(by[CLIENT]['Referring Domains'], 500)
        self.assertEqual(by['comp-one.com']['Referring Domains'], 1200)
        self.assertEqual(by['comp-one.com']['Gap vs Client'], 700)

    def test_referring_domains_export_supplies_domain_authority(self):
        self.assertNotIn('is blank on the Disavow Review tab', self.prep.stdout)


class LiveStatusDerivation(unittest.TestCase):
    def links(self):
        return pd.DataFrame({'target_url': [f'{HOME}a/', f'{HOME}b/', f'{HOME}c/'], 'domain': ['x.com'] * 3,
                             'source_url': ['https://x.com/1/'] * 3, 'authority': [10.0, 20.0, 30.0]})

    def status(self, home, other):
        s = {HOME: {'status': home, 'final_url': '', 'final_status': ''}}
        for t in ['a', 'b', 'c']:
            s[f'{HOME}{t}/'] = {'status': other, 'final_url': '', 'final_status': ''}
        return s

    def test_403_everywhere_is_bot_protection_not_broken(self):
        df, warns = build.derive_broken(self.links(), self.status('403', '403'), CLIENT, {}, set())
        self.assertTrue(df.empty)
        self.assertIn('could not be checked', warns[0])

    def test_429_is_never_broken(self):
        df, _ = build.derive_broken(self.links(), self.status('200', '429'), CLIENT, {}, set())
        self.assertTrue(df.empty)

    def test_redirect_to_404_is_broken_and_redirect_to_200_is_not(self):
        s = self.status('200', '200')
        s[f'{HOME}a/'] = {'status': '301', 'final_url': f'{HOME}gone/', 'final_status': '404'}
        s[f'{HOME}b/'] = {'status': '301', 'final_url': f'{HOME}live/', 'final_status': '200'}
        df, _ = build.derive_broken(self.links(), s, CLIENT, {}, set())
        self.assertEqual(list(df['url']), [f'{HOME}a/'])

    def test_unchecked_urls_are_requested(self):
        needed = set()
        build.derive_broken(self.links(), {}, CLIENT, {}, needed)
        self.assertEqual(needed, {HOME, f'{HOME}a/', f'{HOME}b/', f'{HOME}c/'})


if __name__ == '__main__':
    unittest.main()
