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
    ['Brand / Device', 'Injectables', 'Filler', '', 'Famy (family)', '', 'Both', 'Filler', '', 'famy'],
    ['Brand / Device', 'Injectables', 'Filler', 'Lip Filler; Chin Filler', 'Brandz', '', 'Both', 'Filler', '', 'brandz'],
    ['Brand / Device', 'Injectables', 'Filler', '', 'Oldy', '', 'Both', 'Filler', 'Discontinued. Do not flag as a gap.', 'oldy'],
    ['Service', 'Dental - Implants', 'Implants', '', '', '', 'Dental', '', '', 'implant'],
    ['Sub-Service', 'Dental - Implants', 'Implants', 'Full-Arch', '', '', 'Dental', 'Implants', '', 'full.?arch'],
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
    ('famy', 1200, 'Brand / Device', 'Filler', '', 'Famy (family)', '', '', ''),
    ('facial', 3000, 'Service', 'Facials', '', '', '', '', ''),
    ('wrinkles', 800, 'Concern', '', '', '', 'Lines', '', ''),
]
OFFERS = 'Client offers it? (Yes / No)'
LINKS = 'Internal links out (priority)'
ANCHOR = 'Anchor text for links to this page (SEO fills in)'
KW_TAB = 'SEO Please Check Keywords'
BLANK_KD = {'wrinkles'}  # concern keywords added from a Google Ads check have no difficulty or CPC


def read_kw(path):
    """The keywords tab: instructions in row 1, table header in row 2."""
    return pd.read_excel(path, sheet_name=KW_TAB, header=1)


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
        blank = kw in BLANK_KD
        k.append([kw, 'Medspa', vol, None if blank else 20, None if blank else 1.5, 'Concern' if lvl == 'Concern' else 'Service', lvl, '', svc, sub, brand, con, near, geo])
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
        kw = read_kw(out)
        self.assertNotIn('filler in miami', set(kw['Keyword']))
        self.assertIn('Highest keyword in the whole service', ' '.join(pages.columns))
        self.assertIn('lip filler (2,000)', row['Highest keyword in the whole service (national)'])

    def test_not_recommended_is_left_out(self):
        p, out = self.match_and_build(services='filler', products='oldy; brandy')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        skipped = pd.read_excel(out, sheet_name='Not in the plan')
        self.assertIn('Do not flag', ' '.join(skipped['Why it is not in the plan']))
        pages = pd.read_excel(out, sheet_name='Pages')
        self.assertNotIn('Filler > Oldy', set(pages['Service / sub-service']))

    def test_dental_is_included_with_a_no_keyword_note(self):
        p, out = self.match_and_build(services='implant')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        pages = pd.read_excel(out, sheet_name='Pages').set_index('Service / sub-service')
        self.assertEqual(pages.loc['Implants', 'Recommendation'], 'Own page')
        self.assertEqual(pages.loc['Implants', 'Keywords in taxonomy'], 0)
        self.assertIn('research its volume separately', pages.loc['Implants', 'Notes'])

    def test_dental_has_no_minimum_volume(self):
        p, out = self.match_and_build(services='full arch')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        pages = pd.read_excel(out, sheet_name='Pages').set_index('Service / sub-service')
        self.assertEqual(pages.loc['Implants > Full-Arch', 'Recommendation'], 'Own page')   # no keywords, still a page
        self.assertIn('no minimum volume', pages.loc['Implants > Full-Arch', 'Why'])
        p, out = self.match_and_build(services='implant')
        pages = pd.read_excel(out, sheet_name='Pages').set_index('Service / sub-service')
        self.assertTrue(pd.isna(pages.loc['Implants > Full-Arch', OFFERS]))   # unlisted dental item is suggested with no cutoff, client not yet asked

    def test_blank_difficulty_and_cpc_are_allowed(self):
        p, out = self.match_and_build(services='filler', concerns='wrinkles')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        pages = pd.read_excel(out, sheet_name='Pages')
        row = pages[pages['Service / sub-service'] == 'Lines'].iloc[0]
        self.assertEqual(row['Primary keyword'], 'wrinkles')
        self.assertTrue(pd.isna(row['Primary keyword difficulty']))

    def test_internal_links_are_a_column_on_pages(self):
        p, out = self.match_and_build(services='lip filler; chin filler; facial', products='brandy', concerns='wrinkles; marks')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        pages = pd.read_excel(out, sheet_name='Pages').set_index('Service / sub-service')
        out_links = lambda name: str(pages.loc[name, LINKS])
        self.assertIn('Filler > Lip Filler (High)', out_links('Filler'))
        self.assertIn('Filler (High)', out_links('Filler > Lip Filler'))
        self.assertIn('Filler (High)', out_links('Filler > Brandy'))
        self.assertIn('Filler (Medium)', out_links('Lines'))                 # concern -> service that treats it
        self.assertIn('Lines (Medium)', out_links('Facials'))                # and back
        self.assertIn('Facials (Medium)', out_links('Marks'))
        self.assertNotIn('Chin Filler', out_links('Filler'))                 # chin filler is only a section: no page, no link
        self.assertEqual(len(pages[pages['Level'] == 'Concern']), 2)

    def test_no_internal_links_tab_and_no_suggested_anchor(self):
        p, out = self.match_and_build(services='lip filler')
        self.assertEqual(pd.ExcelFile(out).sheet_names, ['Pages', KW_TAB, 'Not in the plan', 'Read Me'])   # Read Me last, no Confirm / Internal links tabs
        pages = pd.read_excel(out, sheet_name='Pages')
        self.assertTrue(pages[ANCHOR].isna().all())          # left blank for the SEO

    def test_unlisted_items_are_pages_rows_with_a_blank_offers_column(self):
        p, out = self.match_and_build(services='filler')
        pages = pd.read_excel(out, sheet_name='Pages').set_index('Service / sub-service')
        self.assertEqual(pages.loc['Filler', OFFERS], 'Yes')                 # listed
        for name in ('Filler > Lip Filler', 'Filler > Brandy'):              # 2,000 and 1,500, unlisted
            self.assertTrue(pd.isna(pages.loc[name, OFFERS]))
            self.assertEqual(pages.loc[name, 'Where it came from'], 'Suggested from the taxonomy, not listed')
            self.assertEqual(pages.loc[name, 'Recommendation'], 'Own page')
        self.assertNotIn('Filler > Chin Filler', pages.index)                # 400 is under the cutoff
        self.assertNotIn('Filler > Oldy', pages.index)                       # not recommended
        self.assertIn('only if the client offers it', pages.loc['Filler', LINKS])
        self.assertIn('Filler > Brandy', set(read_kw(out)['Target page']))

    def test_a_suggested_page_is_never_the_parent_of_a_section(self):
        p, out = self.match_and_build(services='filler', products='brandz')   # Lip Filler is unlisted, so brandz sits on Filler
        pages = pd.read_excel(out, sheet_name='Pages').set_index('Service / sub-service')
        self.assertEqual(pages.loc['Filler > Brandz', 'Recommendation'], 'Section on Filler page')

    def test_family_tag_is_never_shown(self):
        p, out = self.match_and_build(services='filler', products='famy')
        pages = pd.read_excel(out, sheet_name='Pages')
        names = set(pages['Service / sub-service'])
        self.assertIn('Filler > Famy', names)
        self.assertFalse(any('family' in n for n in names))
        self.assertNotIn('family', ' '.join(map(str, pages[LINKS].dropna())))

    def test_reviewer_can_type_the_name_without_the_family_tag(self):
        def edit(rows):
            for r in rows:
                if r['input'] == 'famy':
                    r['brand_device'] = 'Famy'
        p, out = self.match_and_build(services='filler', products='famy', edit=edit)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_bad_selection_row_stops_the_build(self):
        def edit(rows):
            rows[0]['service'] = 'No Such Service'
        p, _ = self.match_and_build(services='filler', edit=edit)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('no taxonomy row', p.stdout + p.stderr)

    def test_unmatched_concern_can_be_kept_as_a_custom_target(self):
        def edit(rows):
            for r in rows:
                if r['input'] == 'uneven tone':
                    r.update(level='Custom concern', concern='Uneven Tone', treated_by='Facials')
        p, out = self.match_and_build(services='facial', concerns='uneven tone', edit=edit)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('not in the taxonomy', p.stdout)
        pages = pd.read_excel(out, sheet_name='Pages').set_index('Service / sub-service')
        row = pages.loc['Uneven Tone']
        self.assertEqual(row['Level'], 'Concern')
        self.assertEqual(row['Recommendation'], 'Own page')
        self.assertEqual(row[OFFERS], 'Yes')
        self.assertEqual(row['Keywords in taxonomy'], 0)
        self.assertTrue(pd.isna(row['Primary keyword volume (national)']))
        self.assertIn('Not in the taxonomy', row['Notes'])
        self.assertIn('Facials (Medium)', row[LINKS])
        self.assertIn('Uneven Tone (Medium)', pages.loc['Facials', LINKS])
        self.assertEqual(len(pd.read_excel(out, sheet_name='Not in the plan')), 0)

    def test_match_offers_custom_concern_for_unmatched_concern(self):
        p = run('match', '--services', 'facial', '--concerns', 'uneven tone', '--out', self.tmp / 'work', '--taxonomy', self.tax)
        self.assertIn('Custom concern', p.stdout)

    def test_custom_concern_rejects_bad_links_and_taxonomy_names(self):
        def bad_link(rows):
            for r in rows:
                if r['input'] == 'uneven tone':
                    r.update(level='Custom concern', concern='Uneven Tone', treated_by='No Such Service')
        p, _ = self.match_and_build(services='facial', concerns='uneven tone', edit=bad_link)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('treated_by', p.stdout + p.stderr)

        def taxonomy_name(rows):
            for r in rows:
                if r['input'] == 'uneven tone':
                    r.update(level='Custom concern', concern='Lines')
        p, _ = self.match_and_build(services='facial', concerns='uneven tone', edit=taxonomy_name)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('is a taxonomy concern', p.stdout + p.stderr)

    def test_keywords_tab_has_instructions_and_the_reply_reminder(self):
        from openpyxl import load_workbook
        p, out = self.match_and_build(services='filler')
        wb = load_workbook(out)
        self.assertNotIn('Keywords', wb.sheetnames)                          # renamed
        ws = wb[KW_TAB]
        for word in ('CHANGE', 'REMOVE', 'ADD', 'Primary keyword on the Pages tab'):
            self.assertIn(word, ws['A1'].value)
        self.assertEqual([c.value for c in ws[2]][:5], ['Target page', 'Topic', 'Level', 'Keyword', 'Volume (national)'])
        self.assertEqual(len(read_kw(out)), 6)                               # filler 2, lip filler 2, brandy 1, famy 1; city term and sub-cutoff items left out
        self.assertIn(KW_TAB, ' '.join(pd.read_excel(out, 'Read Me')['Item']))
        self.assertIn(f"NEXT: tell the person to open the '{KW_TAB}' tab", p.stdout)   # the build prints the reminder Claude relays

    def test_more_than_five_concerns_warns(self):
        p, out = self.match_and_build(services='facial', concerns='wrinkles; marks; extra1; extra2; extra3; extra4')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('6 concerns listed', p.stdout)
        p, _ = self.match_and_build(services='facial', concerns='wrinkles; marks')
        self.assertNotIn('concerns listed', p.stdout)


class RealTaxonomySmoke(unittest.TestCase):
    def test_both_skills_bundle_the_same_taxonomy(self):
        other = SKILL.parent / 'service-gap-audit/references/service-taxonomy.xlsx'
        self.assertEqual(other.read_bytes(), REAL_TAXONOMY.read_bytes(),
                         'service-taxonomy.xlsx differs between service-gap-audit and new-site-keyword-research: copy the updated file to both')

    def test_every_concern_has_keywords(self):
        tax = pd.read_excel(REAL_TAXONOMY, sheet_name='Taxonomy')
        kw = pd.read_excel(REAL_TAXONOMY, sheet_name='All Keywords')
        have = set(kw[kw.Class == 'Concern'].Concern.dropna())
        missing = [c for c in tax[tax.Level == 'Concern'].Concern if c not in have]
        self.assertEqual(missing, [], 'concerns with no keywords in the taxonomy')

    def test_every_concern_points_to_real_services(self):
        tax = pd.read_excel(REAL_TAXONOMY, sheet_name='Taxonomy')
        names = set(tax[tax.Level.isin(['Service', 'Sub-Service'])][['Service', 'Sub-Service']].stack())
        for _, r in tax[tax.Level == 'Concern'].iterrows():
            for nm in [x.strip() for x in str(r['Implies Offered']).split(';') if x.strip()]:
                self.assertIn(nm, names, f"{r['Concern']} points to {nm!r}, which is not a Service or Sub-Service")


    def test_real_taxonomy_builds(self):
        tmp = Path(tempfile.mkdtemp())
        run('match', '--services', 'Botox; lip filler; tummy tuck', '--products', 'Juvederm Voluma', '--concerns', 'double chin', '--out', tmp / 'work')
        run('build', '--selection', tmp / 'work/selection.tsv', '--client', 'Smoke', '--out', tmp / 'o.xlsx')
        pages = pd.read_excel(tmp / 'o.xlsx', sheet_name='Pages')
        self.assertTrue((pages['Recommendation'] == 'Own page').any())
        self.assertIn('Neurotoxin > Botox', set(pages['Service / sub-service']))


if __name__ == '__main__':
    unittest.main()
