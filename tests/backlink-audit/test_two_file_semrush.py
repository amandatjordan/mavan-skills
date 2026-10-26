"""End-to-end check: a Semrush audit runs on just two exports (client backlinks + Backlink Gap matrix).

Builds synthetic exports with Semrush's column headers, runs prep.py and build.py with no --map and no
hand-made CSVs, and checks the workbook. The only extra inputs are the ones a person or Composio supplies:
config.json, the live status check (status.tsv, faked here) and the review decisions (decisions.json).

Run from the repo root:  python3 -m unittest discover -s tests/backlink-audit -v
"""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

SKILL = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/backlink-audit'
CLIENT = 'example-medspa.com'
COMPS = ['comp-one.com', 'comp-two.com', 'comp-three.com']
HOME = f'https://{CLIENT}/'

BACKLINK_HEADER = ['Page ascore', 'Source title', 'Source url', 'Target url', 'Anchor', 'External links',
                   'Internal links', 'Nofollow', 'Sponsored', 'Ugc', 'Text', 'Frame', 'Form', 'Image', 'Sitewide',
                   'First seen', 'Last seen', 'New link', 'Lost link']
GAP_HEADER = ['Domain', 'Domain ascore', CLIENT] + COMPS + ['Matches']

TARGETS = [HOME, f'{HOME}services/botox/', f'{HOME}services/', f'{HOME}old-botox-page/', f'{HOME}sevices/',
           f'{HOME}blocked-page/', f'{HOME}redirected/']
N_REAL, N_SPAM = 25, 60


def link(src, target, anchor, title='', nofollow='false', lost='false'):
    return ['31', title, src, target, anchor, '3', '12', nofollow, 'false', 'false', 'true', 'false', 'false',
            'false', 'false', '2025-06-01', '2026-10-01', 'false', lost]


def backlinks_rows():
    rows = []
    for i in range(N_REAL):
        rows.append(link(f'https://localsite{i}.com/blog/post-{i}/', TARGETS[i % len(TARGETS)], 'Example Med Spa',
                         title=f'Local post {i}', nofollow='true' if i % 5 == 0 else 'false'))
    for i in range(N_SPAM):
        rows.append(link(f'https://spamnet{i}.xyz/dir/link-outreach-services-{10000 + i}/', HOME,
                         f'Premium Link Building Experts for Better Rankings {CLIENT}',
                         title='Premium Link Building Experts'))
    rows.append(link('https://lostsite.com/old/', HOME, 'Example Med Spa', lost='true'))
    return rows


def gap_rows():
    def r(dom, au, n):  # n competitors linking, Missing view: client column is always 0
        cells = [1 if i < n else 0 for i in range(3)]
        return [dom, au, 0] + cells + [n]
    rows = [r('tampabaylocalnews.com', 55, 3), r('floridachamber.org', 48, 2), r('bestmedspas-listing.com', 33, 2),
            r('frankfurtmedspa.com', 28, 2),             # contains "rank": must not be treated as junk
            r('smallbloglocal.com', 15, 1),              # 1 competitor, low authority: dropped unless decided
            r('onecomp-highauth.com', 62, 1)]
    for dom in ['cheap-backlinks.shop', 'seochecker.site', 'dapa-tools.online', 'rankbooster.xyz', 'bigdeals.store']:
        rows.append(r(dom, 12, 3))
    return rows


def write_csv(path, header, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def fake_status(needed):
    """What the Composio status check would return for the fixture's client URLs."""
    out = []
    for u in needed:
        if u.endswith('/old-botox-page/') or u.endswith('/sevices/'):
            out.append(f'{u}\t404\t\t')
        elif u.endswith('/blocked-page/'):
            out.append(f'{u}\t403\t\t')
        elif u.endswith('/redirected/'):
            out.append(f'{u}\t301\t{HOME}services/\t200')
        else:
            out.append(f'{u}\t200\t\t')
    return '\n'.join(out) + '\n'


class TwoFileSemrushAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.work = cls.root / 'work'
        cls.work.mkdir()
        write_csv(cls.root / 'backlinks.csv', BACKLINK_HEADER, backlinks_rows())
        write_csv(cls.root / 'gap.csv', GAP_HEADER, gap_rows())
        (cls.work / 'config.json').write_text(json.dumps({
            'client': 'Example Med Spa', 'domain': CLIENT, 'tool': 'semrush', 'competitors': COMPS,
            'brand_terms': ['example med spa'], 'manual_action': 'none', 'manual_action_checked': '2026-10-26',
            'safe_domains': []}))
        cls.prep = cls.run_py('prep.py', '--config', str(cls.work / 'config.json'), '--out', str(cls.work),
                              '--backlinks', str(cls.root / 'backlinks.csv'), '--gap', str(cls.root / 'gap.csv'))
        needed = (cls.work / 'status_needed.txt').read_text().split()
        (cls.work / 'status.tsv').write_text(fake_status(needed))
        (cls.work / 'decisions.json').write_text(json.dumps({
            'takeaways': ['Client has 25 real referring domains.', 'Three competitors share 6 gap domains.',
                          '3 broken URLs have links pointing at them.'],
            'broken': {
                f'{HOME}old-botox-page/': {'target': f'{HOME}services/botox/', 'action': '301'},
                f'{HOME}sevices/': {'target': f'{HOME}services/', 'action': 'typo'},
                f'{HOME}blocked-page/': {'target': f'{HOME}services/', 'action': '301'}},
            'opportunities': {
                # review step: every kept row of type Other needs a specific action
                'frankfurtmedspa.com': {'type': 'Industry publication / blog'},
                'onecomp-highauth.com': {'type': 'Industry publication / blog'},
                # added by hand: one competitor and low authority, so prep.py dropped it
                'smallbloglocal.com': {'type': 'Local news / media', 'do_this': 'Pitch a local story.',
                                       'priority': 'Medium'}}}))
        cls.out = cls.root / 'audit.xlsx'
        cls.build = cls.run_py('build.py', '--work', str(cls.work), '--out', str(cls.out))
        cls.wb = load_workbook(cls.out) if cls.out.exists() else None

    @classmethod
    def run_py(cls, script, *args):
        return subprocess.run([sys.executable, '-I', str(SKILL / 'scripts' / script), *args],
                              capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def tab(self, name):
        ws = self.wb[name]
        rows = list(ws.iter_rows(values_only=True))
        return rows[0], [dict(zip(rows[0], r)) for r in rows[1:] if any(v is not None for v in r)]

    def test_prep_and_build_pass_with_two_exports(self):
        self.assertEqual(self.prep.returncode, 0, self.prep.stdout + self.prep.stderr)
        self.assertEqual(self.build.returncode, 0, self.build.stdout + self.build.stderr)
        self.assertIn('All checks passed', self.build.stdout)

    def test_no_missing_export_warning_for_derived_data(self):
        self.assertNotIn('MISSING EXPORTS', self.prep.stdout)

    def test_gap_authority_read_from_domain_ascore(self):
        _, rows = self.tab('Recommendations')
        opp = {r['Domain / Source']: r for r in rows if r['Type'] == 'Link opportunity'}
        self.assertEqual(opp['tampabaylocalnews.com']['AS'], 55)

    def test_every_client_target_is_checked_live(self):
        needed = set((self.work / 'status_needed.txt').read_text().split())
        for t in TARGETS:
            self.assertIn(t, needed)

    def test_broken_backlinks_derived_from_live_status(self):
        _, rows = self.tab('Recommendations')
        broken = {r['Client URL Affected'] for r in rows if r['Type'] == 'Broken backlink'}
        self.assertEqual(broken, {f'{HOME}old-botox-page/', f'{HOME}sevices/', f'{HOME}blocked-page/'})

    def test_rollup_built_from_links_and_gap(self):
        _, rows = self.tab('Competitor Rollup')
        by = {r['Domain']: r for r in rows if r['Domain'] in [CLIENT] + COMPS}
        self.assertEqual(set(by), {CLIENT, *COMPS})
        live_domains = N_REAL + N_SPAM  # the lost link is not counted
        self.assertEqual(by[CLIENT]['Referring Domains'], live_domains)
        self.assertEqual(by[CLIENT]['Backlinks'], live_domains)
        self.assertTrue(by['comp-one.com']['Domains Linking to Them but Not the Client'] > 0)

    def test_shared_domains_blank_when_gap_is_missing_view(self):
        _, rows = self.tab('Competitor Rollup')
        for r in rows:
            if r['Domain'] in COMPS:
                self.assertIsNone(r['Shared Referring Domains with Client'])

    def test_spam_network_collapsed_into_noise_row(self):
        _, rows = self.tab('Disavow Review')
        self.assertFalse([r for r in rows if 'spamnet' in str(r['Referring Domain'])])
        noise = [r for r in rows if r['Pattern Group'] == 'Noise - auto-generated, ignore']
        self.assertEqual(len(noise), 1)
        self.assertGreaterEqual(noise[0]['Links from Domain'], N_SPAM)

    def test_junk_gap_domains_removed_but_real_ones_kept(self):
        _, rows = self.tab('Recommendations')
        opp = {r['Domain / Source'] for r in rows if r['Type'] == 'Link opportunity'}
        for junk in ['cheap-backlinks.shop', 'seochecker.site', 'dapa-tools.online', 'rankbooster.xyz',
                     'bigdeals.store']:
            self.assertNotIn(junk, opp)
        for good in ['tampabaylocalnews.com', 'floridachamber.org', 'frankfurtmedspa.com']:
            self.assertIn(good, opp)

    def test_decisions_can_add_a_one_competitor_domain(self):
        _, rows = self.tab('Recommendations')
        opp = {r['Domain / Source']: r for r in rows if r['Type'] == 'Link opportunity'}
        self.assertIn('smallbloglocal.com', opp)
        self.assertEqual(opp['smallbloglocal.com']['Priority'], 'Medium')

    def test_evidence_url_blank_on_semrush(self):
        _, rows = self.tab('Recommendations')
        for r in rows:
            if r['Type'] == 'Link opportunity':
                self.assertIsNone(r['Evidence URL'])


if __name__ == '__main__':
    unittest.main()
