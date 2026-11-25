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
REAL_TAX = SKILL / 'references/service-taxonomy.xlsx'

PAGES_HEAD = ['Level', 'Service / sub-service', 'Category', 'Recommendation', 'Why', 'Parent page', 'Primary keyword',
              'Primary keyword volume (national)', 'Mention on this page as a section', 'Client offers it? (Yes / No)', 'Where it came from',
              'Anchor text for links to this page (SEO fills in)', 'Internal links out (priority)']
GAP_HEAD = ['Service', 'Offered by our client (SEO fills in: Yes or No)', 'Keywords with 2+ in top 10 or 1+ in top 3',
            'Local keywords with 2+ in top 10 or 1+ in top 3']
BLOG_HEAD = ['Key', 'Level', 'Category', 'Service', 'Sub-Service', 'Brand / Device', 'Practice Type', 'Action', 'Blog 1 angle', 'Blog 2 angle',
             'Intent', 'Links to', 'Status / Notes']


def page(level, label, rec='Own page', vol=1000, parent='', listed='Yes', sections='', anchor='', offers=None, links=''):
    came = {'Yes': 'Listed by the client', 'Implied': 'Parent of a listed item', 'Suggested': 'Suggested from the taxonomy, not listed'}[listed]
    return [level, label, 'Cat', rec, 'Why text', parent, label.split(' > ')[-1].lower(), vol, sections,
            offers if offers is not None else ('' if listed == 'Suggested' else 'Yes'), came, anchor, links]


def make_research(path, pages):
    wb = Workbook()
    wb.active.title = 'Read Me'
    ws = wb.create_sheet('Pages')
    ws.append(PAGES_HEAD)
    for r in pages:
        ws.append(r)
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


TAX_HEAD = ['Level', 'Category', 'Service', 'Sub-Service', 'Brand / Device', 'Concern', 'Match Terms (regex)']


def make_tax(path, nodes=()):
    """A small service taxonomy: (level, service, sub, brand, concern, regex) rows. The default has one node no test names, so a
    gap service only gets a taxonomy name when a test adds the node."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Taxonomy'
    ws.append(TAX_HEAD)
    for level, svc, sub, brand, concern, pat in (nodes or [('Service', 'Unrelated Zzz', '', '', '', 'zzzqqq')]):
        ws.append([level, 'Cat', svc, sub or None, brand or None, concern or None, pat or None])
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
        self.t = self.tmp / 'tax.xlsx'
        make_tax(self.t)

    def build(self, extras='', client='T', check=True):
        run('match', '--research', self.r, '--gap', self.g, '--service-taxonomy', self.t, '--out', self.work)
        return self.build_only(extras, client, check)

    def build_only(self, extras='', client='T', check=True):
        out = self.tmp / 'out.xlsx'
        p = run('build', '--research', self.r, '--gap', self.g, '--match', self.work / 'gap_match.tsv', '--blog-taxonomy', self.b,
                '--extras', extras, '--client', client, '--out', out, check=check)
        if p.returncode == 0:
            self.road = pd.read_excel(out, 'Roadmap').fillna('')
            names = pd.ExcelFile(out).sheet_names
            self.sheets = names
            self.notin = pd.read_excel(out, 'Cut for the 50-page cap', header=1).fillna('') if 'Cut for the 50-page cap' in names else pd.DataFrame(
                columns=['Page', 'Page type', 'Why it is over the 50-page cap'])
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
        ])
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

    def test_gap_not_offered_and_blank_are_left_out(self):
        self.build()
        # not offered (No or blank): not on the roadmap and not listed anywhere else either
        self.assertNotIn('NAD+', set(self.road['Page']))
        self.assertNotIn('Peels', set(self.road['Page']))
        self.assertEqual(self.sheets, ['Read Me', 'Roadmap', 'Internal links'])
        everything = ' '.join(str(v) for v in pd.read_excel(self.out, 'Read Me').fillna('').values.ravel())
        self.assertNotIn('NAD+', everything)

    def test_research_rows_the_client_has_not_confirmed_are_left_out(self):
        make_research(self.r, [
            page('Service', 'Filler', vol=1300), page('Service', 'Facials', vol=74000),
            page('Sub-Service', 'Filler > Lip Filler', vol=22000, parent='Filler'),
            page('Sub-Service', 'Filler > Chin Filler', vol=5000, parent='Filler', listed='Suggested'),   # blank: not asked yet
        ])
        self.build()
        names = set(self.road['Page'])
        self.assertIn('Filler > Lip Filler', names)
        self.assertNotIn('Filler > Chin Filler', names)

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
        self.assertIn('No blogs for Skin tightening', pd.read_excel(self.out, 'Read Me').fillna('').iloc[-1, 1])

    def test_section_listed_not_a_page(self):
        self.build()
        self.assertNotIn('Filler > Cheek Filler', set(self.road['Page']))
        self.assertNotIn('Filler > Cheek Filler', set(self.notin['Page']))

    def test_keyword_columns_are_highlighted_for_the_seo(self):
        self.build()
        ws = load_workbook(self.out)['Roadmap']
        heads = {c.value: c.column for c in ws[1]}
        for name in ('Primary keyword (SEO: check it fits the page, then replace it or add keywords)',):
            self.assertEqual(ws.cell(2, heads[name]).fill.fgColor.rgb[-6:], 'FFF2CC')
            self.assertEqual(ws.cell(ws.max_row, heads[name]).fill.fgColor.rgb[-6:], 'FFF2CC')
        self.assertIn('Keywords: SEO to check', ' '.join(pd.read_excel(self.out, 'Read Me')['Item']))

    def test_must_appear_on_page_comes_from_the_research_anchor_text(self):
        make_research(self.r, [
            page('Service', 'Filler', vol=1300, anchor='facial fillers'),
            page('Sub-Service', 'Filler > Lip Filler', vol=22000, parent='Filler', anchor='lip fillers near me'),
            page('Sub-Service', 'Filler > Cheek Filler', rec='Section on Filler page', vol=170, parent='Filler', anchor='cheek filler'),
            page('Service', 'Facials', vol=900),
        ])
        make_gap(self.g, [['Skin tightening', 'Yes', 1, 0]])
        self.build(extras='Bridal packages|Package')
        col = 'Must appear on page (anchor text other pages use to link here)'
        by = dict(zip(self.road['Page'], self.road[col]))
        self.assertEqual(by['Filler'], 'facial fillers; cheek filler')          # the section's anchor lands on its parent page
        self.assertEqual(by['Filler > Lip Filler'], 'lip fillers near me')
        self.assertEqual(by['Facials'], '')
        for blank in ('Home', 'About Us', 'Bridal packages', 'Skin tightening'):
            self.assertEqual(by[blank], '')
        self.assertTrue(all(v == '' for v in self.road[self.road['Page type'] == 'Blog'][col]))
        self.assertIn('Must appear on page', ' '.join(pd.read_excel(self.out, 'Read Me')['Item']))

    def test_preflight_warns_when_anchor_text_is_missing(self):
        make_research(self.r, [page('Service', 'Filler', anchor=''), page('Service', 'Facials', anchor='facial')])
        p = run('preflight', '--research', self.r, '--gap', self.g, '--out', self.work)
        self.assertIn('1 pages have no anchor text', p.stdout)

    def test_suggested_rows_the_seo_confirmed_rank_after_listed_and_implied(self):
        make_research(self.r, [
            page('Service', 'Svc Suggested', vol=90000, listed='Suggested', offers='Yes'),
            page('Service', 'Svc Implied', vol=100, listed='Implied'),
            page('Service', 'Svc Listed', vol=100),
        ])
        make_gap(self.g, [['Skin tightening', 'Yes', 50, 0]])
        self.build()
        self.assertEqual(list(self.road[self.road['Page type'] == 'Service']['Page']), ['Svc Listed', 'Svc Implied', 'Svc Suggested', 'Skin tightening'])
        why = self.road[self.road['Page'] == 'Svc Suggested'].iloc[0]['Why it is on the roadmap']
        self.assertIn('SEO confirmed', why)

    def links(self):
        return pd.read_excel(self.out, 'Internal links').fillna('')

    def test_internal_links_use_the_research_links_between_roadmap_pages(self):
        make_research(self.r, [
            page('Service', 'Filler', anchor='facial fillers', links='Filler > Lip Filler (High)\nFiller > Cheek Filler (High)\nFiller > Chin Filler (High) [only if the client offers it]\nLines (Medium)'),
            page('Sub-Service', 'Filler > Lip Filler', parent='Filler', anchor='lip fillers', links='Filler (High)'),
            page('Sub-Service', 'Filler > Cheek Filler', rec='Section on Filler page', parent='Filler', anchor='cheek filler'),
            page('Sub-Service', 'Filler > Chin Filler', parent='Filler', anchor='chin filler', offers='No', listed='Suggested', links='Filler (High)'),
            page('Concern', 'Lines', anchor='lines', links='Filler (Medium)'),
        ])
        make_gap(self.g, [])
        self.build()
        l = self.links()
        pairs = set(zip(l['From page'], l['To page']))
        page_pairs = {(f, to) for f, to, src in zip(l['From page'], l['To page'], l['Where this link came from']) if not src.startswith('The blog')}
        self.assertIn(('Filler', 'Filler > Lip Filler'), pairs)
        self.assertIn(('Filler > Lip Filler', 'Filler'), pairs)
        self.assertIn(('Filler', 'Lines'), pairs)
        # a link to a section, or to a page the client does not offer, is dropped
        self.assertFalse(any('Cheek Filler' in x or 'Chin Filler' in x for pr in page_pairs for x in pr))
        # the anchor is the linked page's own anchor text, not the section anchor text added to it for "Must appear on page"
        self.assertEqual(l[(l['From page'] == 'Filler > Lip Filler') & (l['To page'] == 'Filler')].iloc[0]['Anchor text'], 'facial fillers')
        self.assertEqual(self.road[self.road['Page'] == 'Filler'].iloc[0]['Must appear on page (anchor text other pages use to link here)'], 'facial fillers; cheek filler')
        # the section's phrase has a link of its own (its own row), and the existing links keep the first phrase
        own = l[(l['To page'] == 'Filler') & (l['Anchor text'] == 'cheek filler')]
        self.assertEqual(list(zip(own['From page'], own['Where this link came from'])), [('Home', 'Added so every phrase has a link')])
        self.assertEqual(set(l[(l['To page'] == 'Filler') & (l['Anchor text'] != 'cheek filler')]['Anchor text']), {'facial fillers'})

    def test_every_service_sub_service_and_brand_gets_a_link(self):
        make_research(self.r, [
            page('Service', 'Filler', anchor='fillers'),                                   # nothing in the research links to it
            page('Service', 'Lonely', anchor='lonely'),
            page('Sub-Service', 'Filler > Lip', parent='Filler'),                           # research gives no link at all
            page('Brand / Device', 'Filler > Lip > Brandy', parent='Filler > Lip'),
            page('Brand / Device', 'Facials > Glow', parent='Facials'),                    # parent and service are not on the roadmap
        ])
        make_gap(self.g, [['Skin tightening', 'Yes', 1, 0]])
        self.build()
        l = self.links()
        added = {(f, to) for f, to, src in zip(l['From page'], l['To page'], l['Where this link came from']) if src.startswith('Added')}
        self.assertEqual(added, {('Home', 'Filler'), ('Home', 'Lonely'), ('Filler', 'Filler > Lip'), ('Filler > Lip', 'Filler > Lip > Brandy'),
                                 ('Home', 'Facials > Glow'), ('Home', 'Skin tightening')})
        inbound = set(l[l['Where this link came from'] != 'The blog links to its page']['To page'])
        for pg in self.road[self.road['Page type'].isin(['Service', 'Sub-Service', 'Brand / Device'])]['Page']:
            self.assertIn(pg, inbound)
        self.assertIn('links were added', pd.read_excel(self.out, 'Read Me').fillna('').iloc[-1, 1])

    def test_every_must_appear_phrase_gets_its_own_link_row(self):
        make_research(self.r, [
            page('Service', 'Filler', anchor='fillers', links='Lonely (Low)'),
            page('Service', 'Lonely', anchor='lonely; second phrase; third phrase'),
            page('Concern', 'Lines', anchor='lines'),                        # nothing links to it
        ])
        make_gap(self.g, [])
        self.build()
        l = self.links()
        rows = {(f, to, a) for f, to, a in zip(l['From page'], l['To page'], l['Anchor text'])}
        self.assertIn(('Filler', 'Lonely', 'lonely'), rows)                    # from the research sheet, first phrase
        self.assertIn(('Home', 'Lonely', 'second phrase'), rows)               # Home does not link to Lonely yet
        third = l[(l['To page'] == 'Lonely') & (l['Anchor text'] == 'third phrase')].iloc[0]
        self.assertNotIn(third['From page'], ('Filler', 'Home', 'Lonely'))     # a page that does not already link to it
        self.assertIn(('Home', 'Lines', 'lines'), rows)                        # a Concern nothing links to still gets its phrase linked
        self.assertEqual(len(l[(l['To page'] == 'Lonely')]), len({(f, a) for f, a in zip(l[l['To page'] == 'Lonely']['From page'], l[l['To page'] == 'Lonely']['Anchor text'])}))

    def test_a_brand_whose_parent_is_only_a_section_is_linked_from_its_service(self):
        make_research(self.r, [
            page('Service', 'Filler', anchor='fillers'),
            page('Sub-Service', 'Filler > Cheek', rec='Section on Filler page', parent='Filler'),   # not a page
            page('Brand / Device', 'Filler > Brandy', parent='Filler > Cheek', anchor='brandy'),
        ])
        make_gap(self.g, [])
        self.build()
        l = self.links()
        row = l[l['To page'] == 'Filler > Brandy'].iloc[0]
        self.assertEqual((row['From page'], row['Where this link came from']), ('Filler', 'Added so every page gets a link'))

    def test_blogs_link_to_their_page_and_blog_rows_do_not_count_as_page_links(self):
        self.build()
        l = self.links()
        blog = l[l['Where this link came from'] == 'The blog links to its page']
        self.assertEqual(len(blog), int((self.road['Page type'] == 'Blog').sum()))
        self.assertTrue(blog['From page'].str.startswith('Blog ').all())

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
        self.assertIn('No blogs for Facials: excluded in the blog taxonomy', pd.read_excel(self.out, 'Read Me').fillna('').iloc[-1, 1])

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


class GapNamesMatchTheServiceTaxonomy(Base):
    """A gap sheet's service names are typed by hand (Nose Job). The service taxonomy knows them as Rhinoplasty, and the blog taxonomy is keyed by
    those names, so a gap-only page must take the taxonomy name or it gets no blogs."""
    NODES = [('Service', 'Rhinoplasty', '', '', '', 'nose job|rhinoplasty'),
             ('Service', 'Hair Restoration', '', '', '', 'hair restoration'),
             ('Sub-Service', 'Hair Restoration', 'Hair Transplant', '', '', 'hair transplant'),
             ('Brand / Device', 'Neurotoxin', '', 'Xeomin', '', 'xeomin'),
             ('Concern', '', '', '', 'Wrinkles / Fine Lines', 'wrinkle'),
             ('Concern', '', '', '', 'Diastasis Recti', 'diastasis'),
             ('Service', 'Tummy Tuck', '', '', '', 'tummy tuck|diastasis'),
             ('Service', 'Laser Hair Removal', '', '', '', 'laser'), ('Service', 'Laser Resurfacing', '', '', '', 'laser')]

    def setUp(self):
        super().setUp()
        make_tax(self.t, self.NODES)
        make_research(self.r, [page('Service', 'Filler', vol=1300)])
        make_blog(self.b, [('Service', 'Filler', ''), ('Service', 'Rhinoplasty', ''), ('Sub-Service', 'Hair Restoration', 'Hair Transplant')])

    def gap(self, *names):
        make_gap(self.g, [[n, 'Yes', 3, 1] for n in names])

    def row(self, name):
        return next(r for r in self.match_rows() if r['gap_service'] == name)

    def test_exact_name_and_pattern_hits_are_suggested_with_the_taxonomy_name_and_level(self):
        self.gap('Rhinoplasty', 'Nose Job', 'Hair Transplant', 'Xeomin')
        p = run('match', '--research', self.r, '--gap', self.g, '--service-taxonomy', self.t, '--out', self.work)
        r = self.row('Rhinoplasty')
        self.assertEqual((r['status'], r['taxonomy_name'], r['level']), ('taxonomy', 'Rhinoplasty', 'Service'))
        r = self.row('Nose Job')   # found by the node's Match Terms, so the person is told to check it
        self.assertEqual((r['status'], r['taxonomy_name'], r['level']), ('taxonomy?', 'Rhinoplasty', 'Service'))
        self.assertEqual((self.row('Hair Transplant')['taxonomy_name'], self.row('Hair Transplant')['level']), ('Hair Restoration > Hair Transplant', 'Sub-Service'))
        self.assertEqual((self.row('Xeomin')['taxonomy_name'], self.row('Xeomin')['level']), ('Neurotoxin > Xeomin', 'Brand / Device'))
        self.assertIn('Nose Job', p.stdout)
        self.assertIn('check it', p.stdout)

    def test_an_exact_concern_name_beats_a_pattern_hit_on_a_service(self):
        self.gap('Diastasis Recti')
        run('match', '--research', self.r, '--gap', self.g, '--service-taxonomy', self.t, '--out', self.work)
        r = self.row('Diastasis Recti')
        self.assertEqual((r['taxonomy_name'], r['level']), ('Diastasis Recti', 'Concern'))

    def test_several_pattern_hits_are_left_for_the_person_to_choose(self):
        self.gap('Laser')
        run('match', '--research', self.r, '--gap', self.g, '--service-taxonomy', self.t, '--out', self.work)
        r = self.row('Laser')
        self.assertEqual((r['status'], r['taxonomy_name']), ('review', ''))
        self.assertIn('Laser Hair Removal', r['candidates'])
        self.assertIn('Laser Resurfacing', r['candidates'])

    def test_a_research_page_wins_over_the_taxonomy(self):
        self.gap('Filler')
        make_tax(self.t, self.NODES + [('Service', 'Filler', '', '', '', 'filler')])
        run('match', '--research', self.r, '--gap', self.g, '--service-taxonomy', self.t, '--out', self.work)
        r = self.row('Filler')
        self.assertEqual((r['page'], r['taxonomy_name']), ('Filler', ''))

    def test_gap_only_page_takes_the_taxonomy_name_and_gets_its_blogs(self):
        self.gap('Nose Job', 'Hair Transplant')
        self.build()
        pages = list(self.road['Page'])
        self.assertIn('Rhinoplasty', pages)
        self.assertIn('Hair Restoration > Hair Transplant', pages)
        self.assertNotIn('Nose Job', pages)
        blogs = [x for x in pages if x.startswith('Blog')]
        self.assertTrue(any('Rhinoplasty' in b for b in blogs) and any('Hair Transplant' in b for b in blogs))

    def test_two_gap_services_with_one_taxonomy_name_are_one_page_and_their_numbers_add(self):
        self.gap('Nose Job', 'Rhinoplasty')
        self.build()
        rows = self.road[self.road['Page'] == 'Rhinoplasty']
        self.assertEqual(len(rows), 1)
        self.assertEqual(str(rows.iloc[0]['Competitor gap keywords (2+ in top 10 or 1+ in top 3)']).split(' ')[0], '8')

    def test_a_gap_service_with_no_taxonomy_match_keeps_its_name_and_the_warning_says_why(self):
        self.gap('Endermologie')
        p = self.build()
        self.assertIn('Endermologie', list(self.road['Page']))
        self.assertIn('No blogs for Endermologie: no service in the service taxonomy matches it', p.stdout)

    def test_a_match_file_without_the_taxonomy_column_still_builds(self):
        self.gap('Endermologie')
        self.build()
        rows = self.match_rows()
        for r in rows:
            r.pop('taxonomy_name')
        self.save_match(rows)
        self.assertEqual(self.build_only(check=False).returncode, 0)


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
        self.assertIn('Late', set(self.notin['Page']))
        self.assertIn('Cut for the 50-page cap', self.sheets)
        # the cut tab has an instruction row, then the Roadmap's columns plus the reason, so rows can be moved as they are
        ws = load_workbook(self.out)['Cut for the 50-page cap']
        self.assertIn('makes the final list', ws['A1'].value)
        self.assertIn('move a row to the Roadmap tab', ws['A1'].value)
        road_cols = list(pd.read_excel(self.out, 'Roadmap').columns)
        cut_cols = list(pd.read_excel(self.out, 'Cut for the 50-page cap', header=1).columns)
        self.assertEqual(cut_cols, road_cols + ['Why it is over the 50-page cap'])
        self.assertIn('Late', set(self.notin['Page']))

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
        make_research(self.r, [page('Service', 'Filler')])
        make_gap(self.g, [['Fillers', '', 1, 0]])
        p = run('preflight', '--research', self.r, '--gap', self.g, '--out', self.work)
        self.assertIn('READY', p.stdout)
        self.assertIn('blank "Offered by our client"', p.stdout)


class MultipleGaps(Base):
    """A client with services that do not overlap has one gap workbook per set of competitors. They are read as one list."""
    GAPCOL = 'Competitor gap keywords (2+ in top 10 or 1+ in top 3)'

    def setUp(self):
        super().setUp()
        self.g2 = self.tmp / 'g2.xlsx'
        make_research(self.r, [page('Service', 'Filler', vol=1300), page('Service', 'Facials', vol=74000)])
        make_blog(self.b, [('Service', 'Filler', ''), ('Service', 'Facials', '')])

    def go(self, check=True):
        run('match', '--research', self.r, '--gap', self.g, self.g2, '--service-taxonomy', self.t, '--out', self.work)
        self.out = self.tmp / 'out.xlsx'
        p = run('build', '--research', self.r, '--gap', self.g, self.g2, '--match', self.work / 'gap_match.tsv', '--blog-taxonomy', self.b,
                '--client', 'T', '--out', self.out, check=check)
        if p.returncode == 0:
            self.road = pd.read_excel(self.out, 'Roadmap').fillna('')
        return p

    def gap_of(self, page_name):
        return str(self.road[self.road['Page'] == page_name].iloc[0][self.GAPCOL])

    def test_services_from_every_workbook_are_used(self):
        make_gap(self.g, [['Fillers', 'Yes', 13, 0]])
        make_gap(self.g2, [['Facials', 'Yes', 2, 0], ['Skin tightening', 'Yes', 1, 0]])
        self.go()
        self.assertEqual({r['gap_service'] for r in self.match_rows()}, {'Fillers', 'Facials', 'Skin tightening'})
        self.assertEqual(list(self.road[self.road['Page type'] == 'Service']['Page']), ['Filler', 'Facials', 'Skin tightening'])
        self.assertTrue(self.gap_of('Facials').startswith('2 '))

    def test_same_service_in_two_workbooks_is_counted_once_with_the_higher_number(self):
        make_gap(self.g, [['Fillers', 'Yes', 13, 0]])
        make_gap(self.g2, [['fillers', 'Yes', 5, 4]])
        self.go()
        self.assertEqual(len(self.match_rows()), 1)
        self.assertTrue(self.gap_of('Filler').startswith('13 '))  # not 13 + 9

    def test_the_higher_number_can_come_from_the_second_workbook(self):
        make_gap(self.g, [['Fillers', 'Yes', 3, 0]])
        make_gap(self.g2, [['Fillers', 'Yes', 5, 4]])
        self.go()
        row = self.match_rows()[0]
        self.assertEqual((row['gap_keywords'], row['local_gap_keywords']), ('5', '4'))
        self.assertTrue(self.gap_of('Filler').startswith('9 '))

    def test_a_service_is_offered_if_any_workbook_says_yes(self):
        make_gap(self.g, [['Fillers', 'No', 13, 0]])
        make_gap(self.g2, [['Fillers', 'Yes', 2, 0]])
        self.go()
        row = self.match_rows()[0]
        self.assertEqual(row['offered'], 'Yes')
        self.assertTrue(self.gap_of('Filler').startswith('13 '))

    def test_different_services_with_the_same_number_are_all_kept(self):
        make_gap(self.g, [['Fillers', 'Yes', 4, 0], ['Facials', 'Yes', 4, 0]])
        make_gap(self.g2, [['Fillers', 'Yes', 4, 0]])
        self.go()
        self.assertEqual(len(self.match_rows()), 2)

    def test_preflight_names_the_workbook_that_is_wrong(self):
        make_gap(self.g, [['Fillers', 'Yes', 1, 0]])
        Workbook().save(self.g2)
        p = run('preflight', '--research', self.r, '--gap', self.g, self.g2, '--out', self.work, check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('g2.xlsx:', p.stdout)

    def test_preflight_counts_the_workbooks(self):
        make_gap(self.g, [['Fillers', 'Yes', 1, 0]])
        make_gap(self.g2, [['Facials', '', 1, 0]])
        p = run('preflight', '--research', self.r, '--gap', self.g, self.g2, '--out', self.work)
        self.assertIn('Gap: 2 services from 2 workbooks.', p.stdout)
        self.assertIn('blank "Offered by our client"', p.stdout)

    def test_read_me_says_how_many_gap_workbooks(self):
        make_gap(self.g, [['Fillers', 'Yes', 1, 0]])
        make_gap(self.g2, [['Facials', 'Yes', 1, 0]])
        self.go()
        text = ' '.join(str(v) for v in pd.read_excel(self.out, 'Read Me').fillna('').values.ravel())
        self.assertIn('2 new-site keyword gap workbooks', text)
        self.assertIn('counted once, with the higher number', text)


class RealBlogTaxonomy(unittest.TestCase):
    def test_this_skill_bundles_the_same_service_taxonomy_as_the_other_skills(self):
        for other in ('new-site-keyword-research', 'service-gap-audit'):
            self.assertEqual((SKILL.parent / other / 'references/service-taxonomy.xlsx').read_bytes(), REAL_TAX.read_bytes(),
                             f'service-taxonomy.xlsx differs between new-site-content-roadmap and {other}: copy the updated file to all three skills')

    def test_blog_taxonomy_has_a_row_for_every_service_and_sub_service_in_the_service_taxonomy(self):
        tax = pd.read_excel(REAL_TAX, 'Taxonomy').fillna('')
        want = {f"{r.Level}|{r.Service}|{r['Sub-Service']}|" for _, r in tax.iterrows() if r.Level in ('Service', 'Sub-Service')}
        have = set(pd.read_excel(REAL_BLOG, 'Lookup')['Key'])
        self.assertEqual(sorted(want - have), [], 'in the service taxonomy but not in the blog taxonomy Lookup: add the same rows to Lookup')
        self.assertEqual(sorted(have - want), [], 'in the blog taxonomy Lookup but not in the service taxonomy')

    def test_real_taxonomy_names_a_gap_services_the_way_the_blog_taxonomy_does(self):
        tmp = Path(tempfile.mkdtemp())
        make_research(tmp / 'r.xlsx', [page('Service', 'Microneedling')])
        make_gap(tmp / 'g.xlsx', [[n, 'Yes', 1, 0] for n in ('Nose Job', 'Blepharoplasty', 'Hair Transplant', 'Diep Flap')])
        run('match', '--research', tmp / 'r.xlsx', '--gap', tmp / 'g.xlsx', '--out', tmp / 'w')
        with open(tmp / 'w/gap_match.tsv', newline='') as f:
            got = {r['gap_service']: r['taxonomy_name'] for r in csv.DictReader(f, delimiter='\t')}
        look = set(pd.read_excel(REAL_BLOG, 'Lookup')['Key'])
        self.assertEqual(got, {'Nose Job': 'Rhinoplasty', 'Blepharoplasty': 'Blepharoplasty (Eyelid Surgery)', 'Hair Transplant': 'Hair Restoration > Hair Transplant',
                               'Diep Flap': 'Breast Reconstruction > DIEP Flap Reconstruction'})
        for name in got.values():
            parts = name.split(' > ')
            self.assertIn(f'Service|{parts[0]}||' if len(parts) == 1 else f'Sub-Service|{parts[0]}|{parts[1]}|', look)

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
