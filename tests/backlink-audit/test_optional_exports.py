"""The optional exports still work when attached.

Run from the repo root:  python3 -m unittest discover -s tests/backlink-audit -v
"""
import json
import tempfile
import unittest
from pathlib import Path

import test_two_file_semrush as base
from test_two_file_semrush import CLIENT, COMPS, write_csv



class OptionalExportsAttached(unittest.TestCase):
    """Same audit, plus the referring domains export."""

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
        (work / 'config.json').write_text(json.dumps({
            'client': 'Example Med Spa', 'domain': CLIENT, 'tool': 'semrush', 'competitors': COMPS,
            'brand_terms': ['example med spa'], 'manual_action': 'none', 'safe_domains': []}))
        cls.prep = base.TwoFileSemrushAudit.run_py(
            'prep.py', '--config', str(work / 'config.json'), '--out', str(work),
            '--backlinks', str(root / 'backlinks.csv'), '--gap', str(root / 'gap.csv'),
            '--refdomains', str(root / 'refdomains.csv'))
        (work / 'decisions.json').write_text(json.dumps({
            'takeaways': ['a legacy key: ignored now that there is no Rollup tab'],
            'broken': {'https://example.com/x/': {'action': 'drop'}},  # legacy key: ignored
            'opportunities': {'frankfurtmedspa.com': {'type': 'Industry publication / blog'},
                              'onecomp-highauth.com': {'type': 'Industry publication / blog'}}}))
        cls.out = root / 'audit.xlsx'
        cls.build = base.TwoFileSemrushAudit.run_py('build.py', '--work', str(work), '--out', str(cls.out))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_passes(self):
        self.assertEqual(self.prep.returncode, 0, self.prep.stdout + self.prep.stderr)
        self.assertEqual(self.build.returncode, 0, self.build.stdout + self.build.stderr)
        self.assertIn('All checks passed', self.build.stdout)

    def test_referring_domains_export_supplies_domain_authority(self):
        self.assertNotIn('is blank on the Disavow Review tab', self.prep.stdout)


if __name__ == '__main__':
    unittest.main()
