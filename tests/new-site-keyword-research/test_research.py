"""New site keyword research: matching, page/section rule, links, exclusions.

Run from the repo root:  python3 -m unittest discover -s tests/new-site-keyword-research -v
"""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

SKILL = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/new-site-keyword-research'
SCRIPT = SKILL / 'scripts/research.py'
REAL_TAXONOMY = SKILL / 'references/service-taxonomy.xlsx'

TAX_HEAD = ['Level', 'Category', 'Service', 'Sub-Service', 'Brand / Device', 'Concern', 'Practice Type', 'Implies Offered', 'Status / Notes', 'Match Terms (regex)']
TAX = [
    ['Service', 'Injectables', 'Filler', '', '', '', 'Both', '', '', 'filler'],
    ['Sub-Service', 'Injectables', 'Filler', 'Lip Filler', '', '', 'Both', 'Filler', '', 'lip filler'],
    ['Sub-Service', 'Injectables', 'Filler', 'Chin Filler', '', '', 'Both', 'Filler', '', 'chin filler'],
    ['Brand / Device', 'Injectables', 'Filler', '', 'Brandy', '', 'Both', 'Filler', '', 'brandy'],
    ['Brand / Device', 'Injectables', 'Filler', 'Lip Filler; Chin Filler', 'Brandz', '', 'Both', 'Filler', '', 'brandz'],
    ['Brand / Device', 'Injectables', 'Filler', '', 'Oldy', '', 'Both', 'Filler', 'Discontinued. Do not flag as a gap.', 'oldy'],
    ['Service', 'Dental - Implants', 'Implants', '', '', '', 'Dental', '', '', 'implant'],
    ['Concern', 'Concerns', '', '', '', 'Lines', 'Both', 'Filler; Facials', 'Not a page gap on its own.', 'wrinkle|lines'],
    ['Concern', 'Concerns', '', '', '', 'Marks', 'Both', 'Facials', 'Not a page gap on its own.', 'marks'],
    ['Service', 'Skin', 'Facials', '', '', '', 'Both', '', '', 'facial'],
] + [['Concern', 'Concerns', '', '', '', f'Extra{i}', 'Both', 'Facials', '', f'extra{i}'] for i in range(1, 5)]
KW_HEAD = ['Keyword', 'Type', 'Volume', 'Keyword Difficulty', 'CPC', 'Class', 'Matched Level', 'Category', 'Service', 'Sub-Service',
           'Brand / Device', 'Concern', 'Near Me', 'Geo Modified']
KW = [  # keyword, volume, level, service, sub, brand, concern, near me, geo
    ('filler', 500, 'Service', 'Filler', '', '', '', '', ''),
    ('filler cost', 300, 'Service', 'Filler', '', '', '', '', ''),
    ('filler in miami', 9000, 'Service', 'Filler', '', '', '', '', 'Y'),
    ('lip filler', 2000, 'Sub-Service', 'Filler', 'Lip Filler', '', '', '', ''),
    ('lip filler recovery', 900, 'Sub-Service', 'Filler', 'Lip Filler', '', '', '', ''),
    ('chin filler', 400, 'Sub-Service', 'Filler', 'Chin Filler', '', '', '', ''),
    ('brandy near me', 1500, 'Brand / Device', 'Filler', '', 'Brandy', '', 'Y', ''),
    ('brandz', 600, 'Brand / Device', 'Filler', '', 'Brandz', '', '', ''),
    ('oldy', 5000, 'Brand / Device', 'Filler', '', 'Oldy', '', '', ''),
    ('facial', 3000, 'Service', 'Facials', '', '', '', '', ''),
    ('wrinkles', 800, 'Concern', '', '', '', 'Lines', '', ''),
]


def make_taxonomy(path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Read Me'
    ws['A1'] = 'Test taxonomy'
    t = wb.create_sheet('Taxonomy')
    t.append(TAX_HEAD)
    for r in TAX:
        t.append(r)
    k = wb.create_sheet('All Keywords')
    k.append(KW_HEAD)
    for kw, vol, lvl, svc, sub, brand, con, near, geo in KW:
        k.append([kw, 'Medspa', vol, 20, 1.5, 'Concern' if lvl == 'Concern' else 'Service', lvl, '', svc, sub, brand, con, near, geo])
    wb.save(path)


def run(*args, check=True):
    p = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError(p.stdout + p.stderr)
    return p


class ResearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tax = self.tmp / 'tax.xlsx'
        make_taxonomy(self.tax)

    def match_and_build(self, services='', products='', concerns='', edit=None):
        run('match', '--services', services, '--products', products, '--concerns', concerns, '--out', self.tmp / 'work', '--taxonomy', self.tax)
        sel = self.tmp / 'work/selection.tsv'
        if edit:
            rows = list(csv.DictReader(open(sel), delimiter='\t'))
            edit(rows)
            with open(sel, 'w', newline='') as f:
                w = csv.DictWriter(f, rows[0].keys(), delimiter='\t')
                w.writeheader()
                w.writerows(rows)
        out = self.tmp / 'out.xlsx'
        p = run('build', '--selection', sel, '--client', 'Test', '--out', out, '--taxonomy', self.tax, check=False)
        return p, out

    def test_match_picks_most_specific_level(self):
        run('match', '--services', 'lip filler; brandy', '--out', self.tmp / 'work', '--taxonomy', self.tax)
        rows = {r['input']: r for r in csv.DictReader(open(self.tmp / 'work/selection.tsv'), delimiter='\t')}
        self.assertEqual(rows['lip filler']['level'], 'Sub-Service')
        self.assertEqual(rows['brandy']['level'], 'Brand / Device')

    def test_page_vs_section_and_mentions(self):
        p, out = self.match_and_build(services='lip filler; chin filler', products='brandy; brandz')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        pages = pd.read_excel(out, sheet_name='Pages').set_index('Service / sub-service')
        self.assertEqual(pages.loc['Filler', 'Recommendation'], 'Own page')
        self.assertEqual(pages.loc['Filler > Lip Filler', 'Recommendation'], 'Own page')          # 2,000 >= 1,000
        self.assertEqual(pages.loc['Filler > Chin Filler', 'Recommendation'], 'Section on Filler page')  # 400 < 1,000
        self.assertEqual(pages.loc['Filler > Brandy', 'Recommendation'], 'Own page')              # 1,500
        # brandz (600) is a section on the parent that has its own page: Lip Filler, not the section-only Chin Filler
        self.assertEqual(pages.loc['Filler > Brandz', 'Recommendation'], 'Section on Filler > Lip Filler page')
        self.assertIn('Brandz (600)', pages.loc['Filler > Lip Filler', 'Mention on this page as a section'])
        self.assertIn('Chin Filler (400)', pages.loc['Filler', 'Mention on this page as a section'])

    def test_volume_is_highest_keyword_and_city_terms_excluded(self):
        p, out = self.match_and_build(services='filler')
        pages = pd.read_excel(out, sheet_name='Pages')
        row = pages[pages['Service / sub-service'] == 'Filler'].iloc[0]
        self.assertEqual(row['Primary keyword'], 'filler')
        self.assertEqual(row['Primary keyword volume (national)'], 500)      # not 9,000 (city) and not 800 (sum)
        self.assertEqual(row['Keywords in taxonomy'], 2)
        self.assertEqual(row['City-modified searches (not listed)'], 1)
        kw = pd.read_excel(out, sheet_name='Keywords')
        self.assertNotIn('filler in miami', set(kw['Keyword']))
        self.assertIn('Highest keyword in the whole service', ' '.join(pages.columns))
        self.assertIn('lip filler (2,000)', row['Highest keyword in the whole service (national)'])

    def test_not_recommended_and_dental_are_left_out(self):
        p, out = self.match_and_build(services='implant', products='oldy; brandy')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        skipped = pd.read_excel(out, sheet_name='Not in the plan')
        text = ' '.join(skipped['Why it is not in the plan'])
        self.assertIn('Dental', text)
        self.assertIn('Do not flag', text)
        pages = pd.read_excel(out, sheet_name='Pages')
        self.assertNotIn('Filler > Oldy', set(pages['Service / sub-service']))
        self.assertNotIn('Implants', set(pages['Service / sub-service']))

    def test_internal_links_follow_hierarchy_and_concerns(self):
        p, out = self.match_and_build(services='lip filler; chin filler; facial', products='brandy', concerns='wrinkles; marks')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        links = pd.read_excel(out, sheet_name='Internal links')
        pairs = set(zip(links['From page'], links['To page']))
        self.assertIn(('Filler', 'Filler > Lip Filler'), pairs)
        self.assertIn(('Filler > Lip Filler', 'Filler'), pairs)
        self.assertIn(('Filler > Brandy', 'Filler'), pairs)
        self.assertIn(('Lines', 'Filler'), pairs)            # concern -> service that treats it
        self.assertIn(('Facials', 'Lines'), pairs)           # and back
        self.assertNotIn(('Filler > Chin Filler', 'Filler'), pairs)   # chin filler is only a section: no page, no link
        pages = pd.read_excel(out, sheet_name='Pages')
        self.assertEqual(len(pages[pages['Level'] == 'Concern']), 2)
        # Marks only points to Facials, which is on the plan
        self.assertIn(('Marks', 'Facials'), pairs)

    def test_confirm_tab_lists_unlisted_items_with_volume(self):
        p, out = self.match_and_build(services='filler')
        conf = pd.read_excel(out, sheet_name='Confirm with client')
        names = set(conf['Sub-Service / Brand / Device'])
        self.assertIn('Lip Filler', names)       # 2,000 and unlisted
        self.assertIn('Brandy', names)           # 1,500
        self.assertNotIn('Chin Filler', names)   # 400 is under the cutoff
        self.assertNotIn('Oldy', names)          # not recommended

    def test_bad_selection_row_stops_the_build(self):
        def edit(rows):
            rows[0]['service'] = 'No Such Service'
        p, _ = self.match_and_build(services='filler', edit=edit)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('no taxonomy row', p.stdout + p.stderr)

    def test_more_than_five_concerns_warns(self):
        p, out = self.match_and_build(services='facial', concerns='wrinkles; marks; extra1; extra2; extra3; extra4')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('6 concerns listed', p.stdout)
        p, _ = self.match_and_build(services='facial', concerns='wrinkles; marks')
        self.assertNotIn('concerns listed', p.stdout)


class RealTaxonomySmoke(unittest.TestCase):
    def test_real_taxonomy_builds(self):
        tmp = Path(tempfile.mkdtemp())
        run('match', '--services', 'Botox; lip filler; tummy tuck', '--products', 'Juvederm Voluma', '--concerns', 'double chin', '--out', tmp / 'work')
        run('build', '--selection', tmp / 'work/selection.tsv', '--client', 'Smoke', '--out', tmp / 'o.xlsx')
        pages = pd.read_excel(tmp / 'o.xlsx', sheet_name='Pages')
        self.assertTrue((pages['Recommendation'] == 'Own page').any())
        self.assertIn('Neurotoxin > Botox', set(pages['Service / sub-service']))


if __name__ == '__main__':
    unittest.main()
