"""New site content roadmap: cap, order, blogs, extras, gap match.

Run from the repo root:  python3 -m unittest discover -s tests/new-site-content-roadmap -v
"""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook

SKILL = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/new-site-content-roadmap'
SCRIPT = SKILL / 'scripts/roadmap.py'
REAL_BLOG = SKILL / 'references/blog-taxonomy.xlsx'

PAGES_HEAD = ['Level', 'Service / sub-service', 'Category', 'Recommendation', 'Why', 'Parent page', 'Primary keyword',
              'Primary keyword volume (national)', 'Mention on this page as a section', 'Client listed it']
CONFIRM_HEAD = ['Service', 'Level', 'Sub-Service / Brand / Device', 'Primary keyword', 'Primary keyword volume (national)', 'Would be',
                'Client offers it? (Yes / No)']
GAP_HEAD = ['Service', 'Offered by our client (SEO fills in: Yes or No)', 'Keywords with 2+ in top 10 or 1+ in top 3',
            'Local keywords with 2+ in top 10 or 1+ in top 3']
BLOG_HEAD = ['Key', 'Level', 'Category', 'Service', 'Sub-Service', 'Brand / Device', 'Practice Type', 'Action', 'Blog 1 angle', 'Blog 2 angle',
             'Intent', 'Links to', 'Status / Notes']


def page(level, label, rec='Own page', vol=1000, parent='', listed='Yes', sections=''):
    return [level, label, 'Cat', rec, 'Why text', parent, label.split(' > ')[-1].lower(), vol, sections, listed]


def make_research(path, pages, confirm=()):
    wb = Workbook()
    wb.active.title = 'Read Me'
    ws = wb.create_sheet('Pages')
    ws.append(PAGES_HEAD)
    for r in pages:
        ws.append(r)
    c = wb.create_sheet('Confirm with client')
    c.append(CONFIRM_HEAD)
    for r in confirm:
        c.append(r)
    wb.save(path)


def make_gap(path, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Service opportunities'
    ws.append(GAP_HEAD)
    for r in rows:
        ws.append(r)
    wb.save(path)


def make_blog(path, nodes, excluded=(), adds=()):
    """nodes: (level, service, sub). Blog angles are written as the real Lookup does."""
    wb = Workbook()
    wb.active.title = 'Read Me'
    wb['Read Me']['A1'] = 'Test blog taxonomy'
    lk = wb.create_sheet('Lookup')
    lk.append(BLOG_HEAD)
    for level, svc, sub in nodes:
        name = sub or svc
        key = f'{level}|{svc}|{sub}|'
        action = 'Exclude' if key in excluded else 'Rule'
        lk.append([key, level, 'Cat', svc, sub, '', 'Both', action,
                   '' if action == 'Exclude' else f'How to prepare for {name}',
                   '' if action == 'Exclude' else f'Choosing a provider for {name}', 'x', '', ''])
    rl = wb.create_sheet('Blog Rules')
    rl.append(['Key', 'Level', 'Blog #', 'Blog angle (template)'])
    ov = wb.create_sheet('Overrides')
    ov.append(['Key', 'Level', 'Category', 'Service', 'Sub-Service', 'Brand / Device', 'Action', 'Blog 1 angle', 'Blog 2 angle'])
    for svc, brand in adds:
        ov.append([f'Brand / Device|{svc}||{brand}', 'Brand / Device', 'Cat', svc, '', brand, 'Add', f'Brand one {brand}', f'Brand two {brand}'])
    wb.save(path)


def run(*args, check=True):
    p = subprocess.run([sys.executable, '-I', str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    if check and p.returncode != 0:
        raise AssertionError(p.stdout + p.stderr)
    return p


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.r, self.g, self.b = self.tmp / 'r.xlsx', self.tmp / 'g.xlsx', self.tmp / 'b.xlsx'
        self.work = self.tmp / 'work'

    def build(self, extras='', client='T', check=True):
        run('match', '--research', self.r, '--gap', self.g, '--out', self.work)
        return self.build_only(extras, client, check)

    def build_only(self, extras='', client='T', check=True):
        out = self.tmp / 'out.xlsx'
        p = run('build', '--research', self.r, '--gap', self.g, '--match', self.work / 'gap_match.tsv', '--blog-taxonomy', self.b,
                '--extras', extras, '--client', client, '--out', out, check=check)
        if p.returncode == 0:
            self.road = pd.read_excel(out, 'Roadmap').fillna('')
            self.notin = pd.read_excel(out, 'Not on the roadmap').fillna('')
        self.out = out
        return p

    def match_rows(self):
        with open(self.work / 'gap_match.tsv', newline='') as f:
            return list(csv.DictReader(f, delimiter='\t'))

    def save_match(self, rows):
        with open(self.work / 'gap_match.tsv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter='\t')
            w.writeheader()
            w.writerows(rows)


class Small(Base):
    def setUp(self):
        super().setUp()
        make_research(self.r, [
            page('Service', 'Filler', vol=1300), page('Service', 'Facials', vol=74000),
            page('Sub-Service', 'Filler > Lip Filler', vol=22000, parent='Filler'),
            page('Sub-Service', 'Filler > Cheek Filler', rec='Section on Filler page', vol=170, parent='Filler', sections=''),
            page('Brand / Device', 'Filler > Brandy', vol=8000, parent='Filler'),
            page('Concern', 'Lines', vol=480),
        ], confirm=[['Facials', 'Sub-Service', 'Dermaplaning', 'dermaplaning', 60500, 'Own page', 'Yes'],
                    ['Facials', 'Brand / Device', 'Glow', 'glow', 2000, 'Own page', 'No'],
                    ['Facials', 'Sub-Service', 'Acne Facial', 'acne facial', 1300, 'Own page', '']])
        make_gap(self.g, [['Fillers', 'Yes', 13, 0], ['Facials', 'Yes', 2, 0], ['NAD+', 'No', 4, 0], ['Skin tightening', 'Yes', 1, 0],
                          ['Peels', '', 5, 0]])
        make_blog(self.b, [('Service', 'Filler', ''), ('Service', 'Facials', ''), ('Sub-Service', 'Filler', 'Lip Filler'),
                           ('Sub-Service', 'Filler', 'Cheek Filler')])

    def test_home_about_first_and_order(self):
        self.build()
        self.assertEqual(list(self.road['Page'][:2]), ['Home', 'About Us'])
        types = list(self.road['Page type'])
        order = {'Home': 0, 'About Us': 1, 'Service': 3, 'Sub-Service': 4, 'Brand / Device': 5, 'Blog': 6, 'Concern': 7}
        seq = [order[t] for t in types]
        self.assertEqual(seq, sorted(seq))

    def test_gap_signal_beats_volume_inside_a_tier(self):
        self.build()
        svc = list(self.road[self.road['Page type'] == 'Service']['Page'])
        # Filler has the gap signal (13) so it is ahead of Facials (volume 74,000, signal 2); gap-only Skin tightening is last
        self.assertEqual(svc, ['Filler', 'Facials', 'Skin tightening'])

    def test_match_proposes_plural_names(self):
        self.build()
        m = {r['gap_service']: r for r in self.match_rows()}
        self.assertEqual(m['Fillers']['page'], 'Filler')
        self.assertEqual(m['NAD+']['page'], '')

    def test_inherited_gap_signal(self):
        self.build()
        row = self.road[self.road['Page'] == 'Filler > Lip Filler'].iloc[0]
        self.assertIn('inherited from the Filler service', row['Competitor gap keywords (2+ in top 10 or 1+ in top 3)'])

    def test_confirm_with_client(self):
        self.build()
        pages = set(self.road['Page'])
        self.assertIn('Facials > Dermaplaning', pages)
        self.assertNotIn('Facials > Glow', pages)
        self.assertNotIn('Facials > Acne Facial', pages)
        reasons = dict(zip(self.notin['Page or topic'], self.notin['Why it is not on the roadmap']))
        self.assertIn('said no', reasons['Facials > Glow'])
        self.assertIn('not answered', reasons['Facials > Acne Facial'])

    def test_gap_not_offered_and_blank_are_left_out(self):
        self.build()
        reasons = dict(zip(self.notin['Page or topic'], self.notin['Why it is not on the roadmap']))
        self.assertIn('does not offer', reasons['NAD+'])
        self.assertIn('blank', reasons['Peels'])
        self.assertNotIn('NAD+', set(self.road['Page']))

    def test_blogs_follow_their_page_and_sections(self):
        self.build()
        blogs = self.road[self.road['Page type'] == 'Blog']
        by_page = blogs.groupby('Parent page / links to').size().to_dict()
        self.assertEqual(by_page['Filler page'], 2)
        self.assertEqual(by_page['Filler > Lip Filler page'], 2)
        self.assertEqual(by_page['Facials page'], 2)
        sec = [p for p in by_page if 'Cheek Filler' in p]
        self.assertEqual(len(sec), 1)   # the section's two blogs link to the Filler page
        self.assertTrue(sec[0].startswith('Filler page'))
        self.assertNotIn('Skin tightening', ' '.join(blogs['Page']))
        self.assertIn('not in the blog taxonomy', ' '.join(self.notin['Why it is not on the roadmap']))

    def test_section_listed_not_a_page(self):
        self.build()
        self.assertNotIn('Filler > Cheek Filler', set(self.road['Page']))
        self.assertIn('Filler > Cheek Filler', set(self.notin['Page or topic']))

    def test_priority_dropdown_and_blank(self):
        self.build(extras='Bridal packages|Package')
        wb = load_workbook(self.out)
        ws = wb['Roadmap']
        self.assertEqual(ws.cell(1, ws.max_column).value, 'SEO priority (High / Medium / Low)')
        self.assertEqual(len(ws.data_validations.dataValidation), 1)
        self.assertEqual(ws.data_validations.dataValidation[0].formula1, '"High,Medium,Low"')
        self.assertTrue((self.road['SEO priority (High / Medium / Low)'] == '').all())

    def test_extras_are_listed_after_about_and_never_cut(self):
        self.build(extras='Bridal packages|Package; Dr Smith|Provider; bridal packages')
        self.assertEqual(list(self.road['Page'][:4]), ['Home', 'About Us', 'Bridal packages', 'Dr Smith'])
        self.assertEqual(list(self.road['Page type'][2:4]), ['Extra: Package', 'Extra: Provider'])

    def test_overrides_add_brand_blog(self):
        make_blog(self.b, [('Service', 'Filler', ''), ('Sub-Service', 'Filler', 'Lip Filler')], adds=[('Filler', 'Brandy')])
        self.build()
        self.assertIn('Blog 1: Brand one Brandy', set(self.road['Page']))

    def test_exclude_in_blog_taxonomy(self):
        make_blog(self.b, [('Service', 'Filler', ''), ('Service', 'Facials', ''), ('Sub-Service', 'Filler', 'Lip Filler')],
                  excluded=['Service|Facials||'])
        self.build()
        self.assertNotIn('Facials page', set(self.road['Parent page / links to']))
        self.assertIn('excluded in the blog taxonomy', ' '.join(self.notin['Why it is not on the roadmap']))

    def test_gap_only_offered_gets_a_level(self):
        self.build()
        self.assertEqual(self.road[self.road['Page'] == 'Skin tightening'].iloc[0]['Page type'], 'Service')
        rows = self.match_rows()
        for r in rows:
            if r['gap_service'] == 'Skin tightening':
                r['level'] = ''
        self.save_match(rows)
        p = self.build_only(check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('need a level', p.stdout + p.stderr)

    def test_match_pointing_at_missing_page_fails(self):
        self.build()
        rows = self.match_rows()
        rows[0]['page'] = 'Not a page'
        self.save_match(rows)
        p = self.build_only(check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('not on the research Pages tab', p.stdout + p.stderr)

    def test_offered_no_but_matched_warns(self):
        make_gap(self.g, [['Fillers', 'No', 13, 0]])
        self.build()
        p = self.build_only()
        self.assertIn('does not offer', p.stdout)


class Cap(Base):
    def setUp(self):
        super().setUp()
        pages = [page('Service', f'Svc{i:02d}', vol=1000 + i) for i in range(30)]
        pages += [page('Sub-Service', f'Svc{i:02d} > Sub{i:02d}', vol=5000 + i, parent=f'Svc{i:02d}') for i in range(20)]
        pages += [page('Concern', f'Concern{i}', vol=500) for i in range(3)]
        make_research(self.r, pages)
        make_gap(self.g, [['Svc29', 'Yes', 9, 0]])
        make_blog(self.b, [('Service', f'Svc{i:02d}', '') for i in range(30)] + [('Sub-Service', f'Svc{i:02d}', f'Sub{i:02d}') for i in range(20)])

    def test_cap_is_fifty_and_blogs_and_concerns_wait(self):
        self.build(extras='A|Package; B|Event; C|Provider')
        self.assertEqual(len(self.road), 50)
        self.assertEqual(list(self.road['Page'][:5]), ['Home', 'About Us', 'A', 'B', 'C'])
        types = self.road['Page type'].value_counts().to_dict()
        # 45 slots: 30 services + 15 sub-services; no room for blogs or concerns
        self.assertEqual(types.get('Service'), 30)
        self.assertEqual(types.get('Sub-Service'), 15)
        self.assertNotIn('Blog', types)
        self.assertNotIn('Concern', types)
        reasons = ' '.join(self.notin['Why it is not on the roadmap'])
        self.assertIn('Over the 50-page cap', reasons)
        self.assertEqual(int((self.notin['Page type'] == 'Sub-Service').sum()), 5)
        self.assertEqual(int((self.notin['Page type'] == 'Concern').sum()), 3)

    def test_gap_signal_puts_svc29_first(self):
        self.build()
        self.assertEqual(self.road[self.road['Page type'] == 'Service'].iloc[0]['Page'], 'Svc29')

    def test_blogs_fill_leftover_slots_in_order(self):
        make_research(self.r, [page('Service', f'Svc{i:02d}', vol=1000 + i) for i in range(10)] +
                      [page('Concern', f'Concern{i}', vol=500) for i in range(3)])
        make_gap(self.g, [['Svc09', 'Yes', 1, 0]])
        self.build(extras='A|Package')
        # 47 slots: 10 services, then 20 blogs, then 3 concerns, all fit
        self.assertEqual(len(self.road), 2 + 1 + 10 + 20 + 3)
        blog_pages = list(self.road[self.road['Page type'] == 'Blog']['Parent page / links to'])
        self.assertEqual(blog_pages[:2], ['Svc09 page', 'Svc09 page'])
        make_research(self.r, [page('Service', f'Svc{i:02d}', vol=1000 + i) for i in range(30)] + [page('Concern', 'Late', vol=1)])
        make_gap(self.g, [['Svc29', 'Yes', 1, 0]])
        self.build()
        self.assertEqual(len(self.road), 50)
        self.assertEqual(int((self.road['Page type'] == 'Blog').sum()), 18)   # 48 slots - 30 services
        self.assertNotIn('Concern', set(self.road['Page type']))
        self.assertIn('Late', set(self.notin['Page or topic']))

    def test_too_many_extras_fail(self):
        p = run('preflight', '--research', self.r, '--gap', self.g, '--extras', '; '.join(f'X{i}' for i in range(49)), '--out', self.work, check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('more than 50', p.stdout)


class Preflight(Base):
    def test_missing_tabs_fail(self):
        wb = Workbook()
        wb.save(self.r)
        wb.save(self.g)
        p = run('preflight', '--research', self.r, '--gap', self.g, '--out', self.work, check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('NOT READY', p.stdout)

    def test_ready_and_warns_on_blanks(self):
        make_research(self.r, [page('Service', 'Filler')], confirm=[['Filler', 'Sub-Service', 'Lip', 'lip', 2000, 'Own page', '']])
        make_gap(self.g, [['Fillers', '', 1, 0]])
        p = run('preflight', '--research', self.r, '--gap', self.g, '--out', self.work)
        self.assertIn('READY', p.stdout)
        self.assertIn('no Yes / No', p.stdout)
        self.assertIn('blank "Offered by our client"', p.stdout)


class RealBlogTaxonomy(unittest.TestCase):
    def test_bundled_taxonomy_shape(self):
        look = pd.read_excel(REAL_BLOG, 'Lookup').fillna('')
        self.assertTrue({'Key', 'Level', 'Service', 'Sub-Service', 'Action', 'Blog 1 angle', 'Blog 2 angle'} <= set(look.columns))
        self.assertEqual(set(look['Level']), {'Service', 'Sub-Service'})
        self.assertEqual(look['Key'].nunique(), len(look))
        done = look[look['Action'] == 'Rule']
        self.assertTrue((done['Blog 1 angle'] != '').all() and (done['Blog 2 angle'] != '').all())
        self.assertIn('Service|Neurotoxin||', set(look['Key']))
        self.assertIn('Sub-Service|Dermal Filler|Lip Filler|', set(look['Key']))


if __name__ == '__main__':
    unittest.main()
