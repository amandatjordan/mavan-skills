"""migration-sheet on a small made-up site (see fixture.py). No client data, no network.

Run from the repo root:  python3 -m unittest discover -s tests/migration-sheet -v
"""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).parent))
import fixture  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
S = ROOT / 'plugins/mavan-seo/skills/migration-sheet/scripts'
sys.path.insert(0, str(S))
import redirects  # noqa: E402

DOM = 'example-medspa.com'


def run(script, *args, ok=True):
    p = subprocess.run([sys.executable, '-I', str(S / script), *map(str, args)], capture_output=True, text=True)
    if ok:
        assert p.returncode == 0, p.stdout + p.stderr
    return p


def pipeline(d, **kw):
    """inputs -> prep -> import_audits; returns paths and the work folder."""
    p = fixture.make_inputs(d, **kw)
    w = Path(d) / 'work'
    run('prep.py', '--domain', DOM, '--urls', p['urls'], '--links', p['links'], '--redirects', p['redirects'],
        '--backlinks', p['backlinks'], '--gsc', p['gsc'], '--out', w)
    run('import_audits.py', '--domain', DOM, '--prune', p['prune'], '--ia', p['ia'], '--gap', p['gap'], '--out', w)
    return p, w


def preflight(p, w, **extra):
    args = ['--domain', DOM, '--urls', p['urls'], '--links', p['links'], '--backlinks', p['backlinks'], '--gsc', p['gsc'],
            '--prune', p['prune'], '--ia', p['ia'], '--gap', p['gap'], '--out', w]
    for k, v in extra.items():
        args += [f'--{k}', v]
    return run('preflight.py', *args, ok=False)


def fill(path, tab, edits):
    """edits: {row label in column A: {column index (1-based): value}} on a tab with headers in row 2."""
    wb = openpyxl.load_workbook(path)
    ws = wb[tab]
    for r in range(3, ws.max_row + 1):
        label = ws.cell(r, 1).value
        for c, v in edits.get(label, {}).items():
            ws.cell(r, c, v)
    wb.save(path)


class Pass1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p, cls.w = pipeline(cls.tmp.name)
        run('build.py', '--domain', DOM, '--work', cls.w)
        cls.sheet = json.load(open(cls.w / 'sheet.json'))
        cls.tabs = cls.sheet['tabs']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_chain_is_fixed_and_listed(self):
        r = {x[0]: x for x in self.tabs['Pages to redirect']}
        self.assertEqual(r['/botox-tips/'][1], '/services/botox/')  # prune merged into /botox/, the IA moved /botox/
        d = [x for x in self.sheet['discrepancies'] if x['old'] == '/botox-tips/']
        self.assertEqual(d[0]['kind'], 'Redirect chain fixed')

    def test_ia_move_on_a_removed_page_is_dropped_and_listed(self):
        r = {x[0]: x for x in self.tabs['Pages to redirect']}
        self.assertEqual(r['/thin-page/'][1], '/services/')
        self.assertIn('IA move dropped', [x['kind'] for x in self.sheet['discrepancies']])
        self.assertNotIn('/services/thin/', [x[0] for x in self.tabs['All pages']])

    def test_existing_redirect_is_repointed_and_listed(self):
        r = {x[0]: x for x in self.tabs['Pages to redirect']}
        self.assertEqual(r['/old-botox/'][1], '/services/botox/')
        self.assertIn('Existing redirect repointed', [x['kind'] for x in self.sheet['discrepancies']])

    def test_wildcard_counted_once(self):
        olds = [x[0] for x in self.tabs['Pages to redirect']]
        self.assertEqual(sum('junk' in o for o in olds), 1)
        self.assertEqual(self.sheet['counts']['covered'], 2)
        self.assertNotIn('/junk/a/', [x[0] for x in self.tabs['All pages']])

    def test_merge_row_is_content_only(self):
        m = self.tabs['Pages to merge'][0]
        self.assertEqual(m, ['/botox-tips/', '/services/botox/', 'Two tips about aftercare'])  # its redirect is on the redirect tab and the dev list

    def test_all_pages_lists_stays_moved_and_new(self):
        k = {x[0]: x for x in self.tabs['All pages']}
        self.assertEqual(k['/fillers/'][3:6], ['Service', 'Dermal Fillers Denver', 'Dermal Fillers'])  # Update pages' title and H1
        self.assertEqual(k['/services/botox/'][1:3], ['/botox/', 'Moved'])
        self.assertEqual(k['/about/'][1:3], ['', 'Stays'])
        self.assertEqual(k['SEO fill in'][2], 'New page')
        self.assertNotIn('/botox-tips/', k)  # merged pages are not on the new site
        self.assertNotIn('/junk/a/', k)
        self.assertTrue(all(len(x) == 7 for x in self.tabs['All pages']))  # no internal link or backlink columns

    def test_pages_to_redirect_has_no_backlinks_column(self):
        self.assertTrue(all(len(x) == 5 for x in self.tabs['Pages to redirect']))  # old URL, target, code, Gone reason, decided by

    def test_undecided_urls_are_left_for_the_seo(self):
        r = {x[0]: x for x in self.tabs['Pages to redirect']}
        self.assertEqual(r['/gone-page/'][1], 'SEO fill in')
        self.assertEqual(r['/gsc-only/'][1], 'SEO fill in')

    def test_media_only_with_backlinks(self):
        urls = [x[0] for x in self.tabs['Media with backlinks']]
        self.assertEqual(sorted(urls), ['/wp-content/uploads/brochure.pdf', '/wp-content/uploads/menu.pdf'])
        everything = json.dumps(self.tabs)
        self.assertNotIn('logo.png', everything)

    def test_new_page_suggests_up_to_three_links_at_final_urls(self):
        n = self.tabs['New pages']
        self.assertEqual([x[0] for x in n], ['Lip Filler'])
        self.assertEqual([n[0][3], n[0][5], n[0][7]], ['/fillers/', '/services/botox/', '/blog/new-post/'])  # pages that link TO it; /botox-tips/ merged; capped at 3
        self.assertEqual([n[0][4], n[0][6], n[0][8]], ['SEO fill in'] * 3)

    def test_pass1_has_no_dev_tab_and_open_items_are_listed(self):
        wb = openpyxl.Workbook()
        run('make_xlsx.py', '--work', self.w, '--out', self.w / 's.xlsx')
        names = openpyxl.load_workbook(self.w / 's.xlsx').sheetnames
        self.assertNotIn('Redirects - Handoff to Dev', names)
        self.assertEqual(names[0], 'Summary')
        self.assertGreater(self.sheet['open'], 0)

    def test_pass2_fails_while_cells_are_open(self):
        run('make_xlsx.py', '--work', self.w, '--out', self.w / 'wc.xlsx')
        p = run('build.py', '--domain', DOM, '--work', self.w, '--working-copy', self.w / 'wc.xlsx', ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn('navigation', p.stdout)
        run('build.py', '--domain', DOM, '--work', self.w)  # restore the template sheet.json for other tests


class Pass2(unittest.TestCase):
    def test_filled_working_copy_gives_final_workbook_and_csv(self):
        with tempfile.TemporaryDirectory() as d:
            p, w = pipeline(d)
            run('build.py', '--domain', DOM, '--work', w)
            run('make_xlsx.py', '--work', w, '--out', Path(d) / 'wc.xlsx')
            wc = str(Path(d) / 'wc.xlsx')
            fill(wc, 'Pages to redirect', {'/gone-page/': {2: '/services/'}, '/gsc-only/': {2: 'Gone', 3: 410, 4: 'Never existed on the new site'}})
            fill(wc, 'Media with backlinks', {'/wp-content/uploads/brochure.pdf': {3: 'Redirect', 4: '/downloads/brochure.pdf'},
                                              '/wp-content/uploads/menu.pdf': {3: 'Keep at the same URL'}})
            fill(wc, 'New pages', {'Lip Filler': {2: '/services/lip-filler/', 5: 'lip filler', 7: 'botox', 9: 'our blog'}})
            wb = openpyxl.load_workbook(wc)
            ws = wb['Final menu and nav']
            for i, row in enumerate([('Services', '/services/', 'Botox', '/services/botox/', 1), ('Services', '/services/', 'Lip Filler', '/services/lip-filler/', 2),
                                     ('About', '/about/', '', '', 3)], 3):
                for c, v in enumerate(row, 1):
                    ws.cell(i, c, v)
            wb.save(wc)
            wb = openpyxl.load_workbook(wc)
            ws = wb['All pages']
            for r in range(3, ws.max_row + 1):  # the SEO reviews and updates the title and H1 on All pages
                if ws.cell(r, 1).value == '/fillers/':
                    ws.cell(r, 5, 'Dermal Fillers in Denver | Example')
                if str(ws.cell(r, 7).value).startswith('Service Gap: Lip Filler'):
                    ws.cell(r, 5, 'Lip Filler Denver')
                    ws.cell(r, 6, 'Lip Filler')
            wb.save(wc)
            run('build.py', '--domain', DOM, '--work', w, '--working-copy', wc)
            run('make_xlsx.py', '--work', w, '--out', Path(d) / 'final.xlsx')
            final = openpyxl.load_workbook(Path(d) / 'final.xlsx')
            rows = {x[0]: x for x in final['All pages'].iter_rows(min_row=3, values_only=True)}
            self.assertEqual(rows['/fillers/'][4], 'Dermal Fillers in Denver | Example')  # the SEO's edit is kept by the QA check
            self.assertEqual(rows['/services/lip-filler/'][4:6], ('Lip Filler Denver', 'Lip Filler'))
            names = final.sheetnames
            self.assertNotIn('Redirects - Handoff to Dev', names)  # the developer list is the separate CSV only
            rows = list(csv.reader(open(Path(d) / 'final-redirects.csv')))
            self.assertEqual(rows[0], ['Source URL', 'Target URL', 'Regex (0 = no, 1 = yes)', 'HTTP Code'])
            body = {r[0].replace(f'https://{DOM}', ''): r[1:] for r in rows[1:]}
            self.assertEqual(body['/gone-page/'][0], f'https://{DOM}/services/')
            self.assertEqual(body['/gsc-only/'], ['', '0', '410'])
            self.assertEqual(body['/wp-content/uploads/brochure.pdf'][0], f'https://{DOM}/downloads/brochure.pdf')
            self.assertNotIn('/wp-content/uploads/menu.pdf', body)
            self.assertEqual(body['/junk/(.*)'][1], '1')  # wildcard row, regex
            self.assertEqual(len(rows) - 1, len(set(r[0] for r in rows[1:])))  # no source twice

    def _pass2(self, d, menu, **fills):
        p, w = pipeline(d)
        run('build.py', '--domain', DOM, '--work', w)
        run('make_xlsx.py', '--work', w, '--out', Path(d) / 'wc.xlsx')
        wc = str(Path(d) / 'wc.xlsx')
        fill(wc, 'Pages to redirect', fills.get('redirect', {'/gone-page/': {2: '/services/'}, '/gsc-only/': {2: 'Gone', 4: 'reason'}}))
        fill(wc, 'Media with backlinks', fills.get('media', {'/wp-content/uploads/brochure.pdf': {3: 'Keep at the same URL'},
                                                             '/wp-content/uploads/menu.pdf': {3: 'Keep at the same URL'}}))
        fill(wc, 'New pages', fills.get('new', {'Lip Filler': {2: '/services/lip-filler/', 5: 'a', 7: 'b', 9: 'c'}}))
        wb = openpyxl.load_workbook(wc)
        for i, row in enumerate(menu, 3):
            for c, v in enumerate(row, 1):
                wb['Final menu and nav'].cell(i, c, v)
        wb.save(wc)
        return run('build.py', '--domain', DOM, '--work', w, '--working-copy', wc, ok=False)

    def test_menu_with_a_merged_page_and_an_orphan_child_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._pass2(d, [('Services', '/services/', 'Tips', '/botox-tips/', 1), ('', '', 'Orphan', '/about/', 2)])
            self.assertEqual(p.returncode, 1)
            self.assertIn('/botox-tips/ is in the menu', p.stdout)
            self.assertIn('has no parent', p.stdout)

    def test_new_page_linking_to_a_merged_page_or_without_anchor_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._pass2(d, [('Services', '/services/', '', '', 1)], new={'Lip Filler': {2: '/services/lip-filler/', 4: '/botox-tips/', 5: 'tips'}})
            self.assertEqual(p.returncode, 1)
            self.assertIn('/botox-tips/ is set to link to it but is not a page on the new site', p.stdout)
        with tempfile.TemporaryDirectory() as d:
            p = self._pass2(d, [('Services', '/services/', '', '', 1)], new={'Lip Filler': {2: '/services/lip-filler/', 5: 'ok'}})
            self.assertEqual(p.returncode, 1)
            self.assertIn('has no anchor text', p.stdout)

    def test_gone_without_reason_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._pass2(d, [('Services', '/services/', '', '', 1)], redirect={'/gone-page/': {2: '/services/'}, '/gsc-only/': {2: 'Gone'}})
            self.assertEqual(p.returncode, 1)
            self.assertIn('Gone with no reason', p.stdout)

    def test_media_redirect_without_new_url_and_missing_decision_fail(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._pass2(d, [('Services', '/services/', '', '', 1)],
                            media={'/wp-content/uploads/brochure.pdf': {3: 'Redirect'}})
            self.assertEqual(p.returncode, 1)
            self.assertIn('set to redirect with no new URL', p.stdout)
            self.assertIn('menu.pdf has no decision', p.stdout)


class Preflight(unittest.TestCase):
    def test_clean_inputs_pass_and_show_what_was_read(self):
        with tempfile.TemporaryDirectory() as d:
            p, w = pipeline(d)
            r = preflight(p, w)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn('What I read', r.stdout)
            self.assertIn('prune.xlsx / Merge pages: 1 rows', r.stdout)

    def test_unresolved_audit_cells_block_and_are_listed(self):
        with tempfile.TemporaryDirectory() as d:
            p, w = pipeline(d, disagree='Merge into /services/', gap_next='',
                            extra_prune={'Needs discussion': [(fixture.SITE + '/contact/', 'SEO fill in', 'why')]})
            r = preflight(p, w)
            self.assertEqual(r.returncode, 1)
            self.assertIn('Disagree cell has a change typed in it', r.stdout)
            self.assertIn('Needs discussion row has no answer', r.stdout)
            self.assertIn('Next Steps is empty', r.stdout)

    def test_blank_and_needs_target_cells_block(self):
        with tempfile.TemporaryDirectory() as d:
            p, w = pipeline(d)
            wb = openpyxl.load_workbook(p['prune'])
            wb['Remove pages'].cell(3, 2, 'NEEDS TARGET - no live page with the same slug')
            wb['Merge pages'].cell(3, 2, 'SEO fill in')
            wb.save(p['prune'])
            wb = openpyxl.load_workbook(p['ia'])
            wb['Moves'].cell(3, 2, 'SEO fill in')
            wb.save(p['ia'])
            r = preflight(p, w)
            self.assertEqual(r.returncode, 1)
            for text in ('Redirect target is blank', 'Merge target is blank', 'New URL is blank'):
                self.assertIn(text, r.stdout)

    def test_empty_crawl_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p, w = pipeline(d)
            rows = [['URL', 'HTTP Status Code', 'Indexable Status', 'Title', 'H1']] + [[f'{fixture.SITE}/p{i}/', '200', 'Indexable', '', ''] for i in range(200)]
            fixture.write_csv(p['urls'], rows[0], rows[1:])
            r = preflight(p, w)
            self.assertEqual(r.returncode, 1)
            self.assertIn('almost none has a title', r.stdout)

    def test_wrong_kind_of_workbook_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p, w = pipeline(d)
            r = preflight(p, w, **{'prune': str(p['ia'])})
            self.assertEqual(r.returncode, 1)
            self.assertIn('Is this the prune workbook', r.stdout)

    def test_crawl_media_lists_are_not_needed(self):
        with tempfile.TemporaryDirectory() as d:
            p, w = pipeline(d)  # the fixture has no images or documents list at all
            self.assertEqual(preflight(p, w).returncode, 0)


class Resolve(unittest.TestCase):
    """redirects.resolve_all on tiny inputs."""

    def audits(self, merge=(), remove=(), moves=(), keep=()):
        return {'prune': {'keep': {k: '' for k in keep}, 'merge': [{'source': s, 'target': t} for s, t in merge],
                          'remove': [{'source': s, 'target': t} for s, t in remove], 'update': {}, 'wildcards': [], 'carry': {}},
                'ia': {'moves': [{'old': o, 'new': n} for o, n in moves], 'types': {}}, 'gap': {'new_pages': []}}

    def go(self, live, audits, crawl_red=None, master_extra=()):
        master = {k: {'backlinks': 0, 'impressions': 0, 'media': False} for k in set(live) | set(master_extra)}
        return redirects.resolve_all(master, set(live), audits, crawl_red or {})

    def test_loop_is_caught(self):
        r = self.go(['/a/', '/b/', '/c/'], self.audits(merge=[('/a/', '/b/'), ('/b/', '/a/')]))
        self.assertTrue(any('loop' in p or 'cannot be resolved' in p for p in r['problems']))

    def test_chain_through_two_merges_ends_in_one_hop(self):
        r = self.go(['/a/', '/b/', '/c/'], self.audits(merge=[('/a/', '/b/'), ('/b/', '/c/')]))
        rows = {x['old']: x for x in r['rows']}
        self.assertEqual(rows['/a/']['final'], '/c/')
        self.assertEqual(r['problems'], [])

    def test_target_that_is_not_a_page_that_stays_fails(self):
        r = self.go(['/a/', '/c/'], self.audits(remove=[('/a/', '/nowhere/')]))
        self.assertTrue(any('not a page that stays' in p for p in r['problems']))

    def test_source_listed_twice_with_different_targets_fails(self):
        r = self.go(['/a/', '/b/', '/c/'], self.audits(merge=[('/a/', '/b/')], remove=[('/a/', '/c/')]))
        self.assertTrue(any('two different targets' in p for p in r['problems']))

    def test_two_pages_ending_at_one_url_fails(self):
        r = self.go(['/a/', '/b/'], self.audits(moves=[('/a/', '/x/'), ('/b/', '/x/')]))
        self.assertTrue(any('end at /x/' in p for p in r['problems']))

    def test_redirect_to_a_gone_page_fails(self):
        r = self.go(['/a/', '/b/'], self.audits(remove=[('/a/', 'GONE'), ('/b/', '/a/')]))
        self.assertTrue(any('being removed' in p for p in r['problems']))

    def test_kept_page_inside_a_wildcard_fails(self):
        a = self.audits(keep=['/junk/a/'])
        a['prune']['wildcards'] = [{'source': '/junk/*', 'target': '/', 'regex': 0}]
        r = self.go(['/', '/junk/a/'], a)
        self.assertTrue(any('inside the wildcard' in p for p in r['problems']))


if __name__ == '__main__':
    unittest.main()
