"""Schema markup templates: type mapping, roadmap output, template lint, fill, status gating, document.

Run from the repo root:  python3 -m unittest discover -s tests/schema-markup-templates -v
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

SKILL = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/schema-markup-templates'
SCRIPT = SKILL / 'scripts/schema.py'
_spec = importlib.util.spec_from_file_location('schema', SCRIPT)
schema = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(schema)

HEAD = ["#", "Page", "Page type", "Content to write", "Why", "Parent page / links to", "Primary keyword", "Vol",
        "Must appear on page", "Gap", "Sections", "SEO priority"]
PAGES = [("Home", "Home"), ("About Us", "About Us"), ("Bridal packages", "Extra: Package"), ("Dr Smith", "Extra: Provider"),
         ("Parking guide", "Extra: Directions"), ("Dermal Filler", "Service"), ("Dermal Filler > Lip Filler", "Sub-Service"),
         ("Neurotoxin > Botox", "Brand / Device"), ("Acne", "Concern"), ("Blog 1: Prep for Dermal Filler", "Blog")]


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def make_roadmap(path, pages=PAGES):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Roadmap'
    ws.append(HEAD)
    for i, (name, typ) in enumerate(pages, 1):
        ws.append([i, name, typ, "Page", "", "", "", "", "", "", "", ""])
    wb.create_sheet('Internal links').append(["From page", "To page"])
    wb.create_sheet('Cut for the 50-page cap').append(["x"])
    rm = wb.create_sheet('Read Me')
    rm.append(['Item', 'Detail'])
    rm.append(['New site content roadmap', 'Test Med Spa'])
    wb.save(path)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.road = self.tmp / 'roadmap.xlsx'
        make_roadmap(self.road)
        self.work = self.tmp / 'work'
        self.out = self.tmp / 'out.xlsx'

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def build(self, btype='medspa'):
        return run('build', '--roadmap', self.road, '--business-type', btype, '--out', self.out, '--work', self.work)

    def install_example(self, slug='treatment'):
        (self.work / 'templates').mkdir(parents=True, exist_ok=True)
        shutil.copy(SKILL / 'references/example-treatment.json', self.work / 'templates' / f'{slug}.json')
        shutil.copy(SKILL / 'references/example-treatment.map.json', self.work / 'templates' / f'{slug}.map.json')


class TestClassify(unittest.TestCase):
    def test_types(self):
        c = schema.classify
        self.assertEqual(c('Home', 'MedicalClinic')[:3], ('home', 'Home', 'MedicalClinic'))
        self.assertEqual(c('About Us', 'X')[2], 'AboutPage')
        for t in ('Service', 'Sub-Service', 'Brand / Device'):
            self.assertEqual(c(t, 'X')[:1] + c(t, 'X')[2:3], ('treatment', 'MedicalProcedure'))
        self.assertEqual(c('Concern', 'X')[2], 'MedicalCondition')
        self.assertEqual(c('Blog', 'X')[2], 'BlogPosting')

    def test_extras(self):
        c = schema.classify
        self.assertEqual(c('Extra: Package', 'X')[0:3:2], ('extra-package', 'Service'))
        self.assertEqual(c('Extra: Provider', 'X')[2], 'Person')
        self.assertEqual(c('Extra: Location', 'MedicalClinic')[2], 'MedicalClinic')
        self.assertEqual(c('Extra: Event', 'X')[2], 'Event')
        slug, label, stype, why, confirm = c('Extra: Directions', 'X')
        self.assertEqual((slug, stype, confirm), ('extra-directions', 'WebPage', True))

    def test_business_type(self):
        self.assertEqual(schema.business_schema_type('medspa')[0], 'MedicalClinic')
        self.assertEqual(schema.business_schema_type('Dental')[0], 'Dentist')
        self.assertEqual(schema.business_schema_type('DaySpa')[0], 'DaySpa')
        self.assertIsNone(schema.business_schema_type('day spa')[0])


class TestBuild(Base):
    def test_preflight(self):
        r = run('preflight', '--roadmap', self.road, '--business-type', 'medspa', '--out', self.work)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('READY', r.stdout)
        r = run('preflight', '--roadmap', self.road, '--business-type', 'not a type', '--out', self.work)
        self.assertEqual(r.returncode, 1)
        self.assertIn('NOT READY', r.stdout)

    def test_preflight_missing_tab(self):
        wb = openpyxl.Workbook()
        wb.active.title = 'Other'
        wb.save(self.road)
        r = run('preflight', '--roadmap', self.road, '--business-type', 'medspa', '--out', self.work)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no 'Roadmap' tab", r.stdout)

    def test_workbook(self):
        r = self.build()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        wb = openpyxl.load_workbook(self.out)
        self.assertEqual(sorted(wb.sheetnames), ['Read Me', 'Roadmap'])   # other tabs dropped
        ws = wb['Roadmap']
        head = [c.value for c in ws[1]]
        self.assertEqual(head[-2:], ['Primary schema type', 'Why this schema type'])
        got = {ws.cell(row=r, column=2).value: ws.cell(row=r, column=len(head) - 1).value for r in range(2, ws.max_row + 1)}
        self.assertEqual(got['Home'], 'MedicalClinic')
        self.assertEqual(got['Dermal Filler'], 'MedicalProcedure')
        self.assertEqual(got['Dermal Filler > Lip Filler'], 'MedicalProcedure')
        self.assertEqual(got['Neurotoxin > Botox'], 'MedicalProcedure')
        self.assertEqual(got['Acne'], 'MedicalCondition')
        self.assertEqual(got['Blog 1: Prep for Dermal Filler'], 'BlogPosting')
        self.assertEqual(got['Dr Smith'], 'Person')
        self.assertEqual(got['Parking guide'], 'WebPage')
        # every roadmap page is typed, and original columns are kept
        self.assertEqual(len(got), len(PAGES))
        self.assertEqual(head[1], 'Page')

    def test_yellow_only_for_confirm(self):
        self.build()
        ws = openpyxl.load_workbook(self.out)['Roadmap']
        col = [c.value for c in ws[1]].index('Primary schema type') + 1
        fills = {ws.cell(row=r, column=2).value: ws.cell(row=r, column=col).fill.fgColor.rgb for r in range(2, ws.max_row + 1)}
        self.assertEqual(fills['Parking guide'], '00FFF2CC')
        self.assertNotEqual(fills['Home'], '00FFF2CC')

    def test_plan_groups(self):
        self.build()
        plan = json.load(open(self.work / 'plan.json'))
        slugs = [g['slug'] for g in plan['groups']]
        self.assertEqual(slugs, ['home', 'about-us', 'extra-package', 'extra-provider', 'extra-directions', 'treatment', 'concern', 'blog'])
        treat = next(g for g in plan['groups'] if g['slug'] == 'treatment')
        self.assertEqual(len(treat['pages']), 3)
        status = json.load(open(self.work / 'status.json'))
        self.assertTrue(all(v['status'] == 'not started' for v in status.values()))

    def test_rebuild_keeps_status(self):
        self.build()
        sp = self.work / 'status.json'
        s = json.load(open(sp))
        s['home'] = {'status': 'passed'}
        json.dump(s, open(sp, 'w'))
        self.build()
        self.assertEqual(json.load(open(sp))['home']['status'], 'passed')

    def test_original_untouched(self):
        before = self.road.read_bytes()
        self.build()
        self.assertEqual(before, self.road.read_bytes())


class TestCheck(Base):
    def setUp(self):
        super().setUp()
        self.build()
        self.install_example()

    def check(self, slug='treatment'):
        return run('check', '--work', self.work, '--slug', slug, '--page-url', 'https://x.test/a')

    def edit(self, fn):
        p = self.work / 'templates/treatment.json'
        d = json.load(open(p))
        fn(d)
        json.dump(d, open(p, 'w'))

    def test_example_passes(self):
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(json.load(open(self.work / 'status.json'))['treatment']['status'], 'draft')

    def test_unknown_slug(self):
        r = self.check('nope')
        self.assertNotEqual(r.returncode, 0)

    def test_invalid_json(self):
        (self.work / 'templates/treatment.json').write_text('{bad')
        r = self.check()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('not valid JSON', r.stdout + r.stderr)

    def test_empty_value(self):
        self.edit(lambda d: d['@graph'][1].update(bodyLocation=''))
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn('is empty', r.stdout)

    def test_empty_object(self):
        self.edit(lambda d: d['@graph'][1].update(geo={}))
        self.assertEqual(self.check().returncode, 1)

    def test_undescribed_placeholder(self):
        self.edit(lambda d: d['@graph'][1].update(status='{{surprise}}'))
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn('surprise', r.stdout)

    def test_unused_description(self):
        mp = self.work / 'templates/treatment.map.json'
        m = json.load(open(mp))
        m['placeholders']['unused_one'] = 'never used'
        json.dump(m, open(mp, 'w'))
        self.assertEqual(self.check().returncode, 1)

    def test_type_placeholder_rejected(self):
        self.edit(lambda d: d['@graph'][1].update({'@type': '{{type}}'}))
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn('placeholder', r.stdout)

    def test_missing_context(self):
        self.edit(lambda d: d.pop('@context'))
        self.assertEqual(self.check().returncode, 1)

    def test_primary_type_missing(self):
        def drop(d):
            d['@graph'] = [n for n in d['@graph'] if n['@type'] != 'MedicalProcedure']
        self.edit(drop)
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn('primary type MedicalProcedure', r.stdout)

    def test_bad_placeholder_name(self):
        self.edit(lambda d: d['@graph'][1].update(name='{{Bad Name}}'))
        # not matched by the placeholder pattern, so it is just text; a capital letter name is caught
        self.edit(lambda d: d['@graph'][1].update(name='{{BadName}}'))
        self.assertEqual(self.check().returncode, 1)


class TestFill(Base):
    def setUp(self):
        super().setUp()
        self.build()
        self.install_example()
        meta = json.load(open(self.work / 'templates/treatment.map.json'))
        self.values = {k: f'value of {k}' for k in meta['placeholders']}
        self.vpath = self.work / 'values.json'

    def fill(self):
        json.dump(self.values, open(self.vpath, 'w'))
        return run('fill', '--work', self.work, '--slug', 'treatment', '--values', self.vpath)

    def test_fill_all(self):
        r = self.fill()
        self.assertEqual(r.returncode, 0, r.stdout)
        out = json.load(open(self.work / 'test/treatment.filled.json'))
        self.assertEqual(out['@graph'][0]['name'], 'value of page_title')
        self.assertNotIn('{{', json.dumps(out))

    def test_value_with_quotes_stays_valid_json(self):
        self.values['faq_1_answer'] = 'He said "yes" and\nleft'
        self.assertEqual(self.fill().returncode, 0)
        out = json.load(open(self.work / 'test/treatment.filled.json'))
        faq = next(n for n in out['@graph'] if n['@type'] == 'FAQPage')
        self.assertEqual(faq['mainEntity'][0]['acceptedAnswer']['text'], 'He said "yes" and\nleft')

    def test_missing_value(self):
        del self.values['page_title']
        r = self.fill()
        self.assertEqual(r.returncode, 1)
        self.assertIn('page_title', r.stdout)
        self.assertFalse((self.work / 'test/treatment.filled.json').exists())

    def test_extra_value(self):
        self.values['not_in_template'] = 'x'
        r = self.fill()
        self.assertEqual(r.returncode, 1)
        self.assertIn('not_in_template', r.stdout)

    def test_blank_value(self):
        self.values['faq_2_answer'] = '  '
        r = self.fill()
        self.assertEqual(r.returncode, 1)


class TestStatusAndDoc(Base):
    def setUp(self):
        super().setUp()
        make_roadmap(self.road, [("Home", "Home"), ("Dermal Filler", "Service")])
        self.build()

    def write_home(self):
        tpl = {"@context": "https://schema.org", "@graph": [
            {"@type": "MedicalClinic", "@id": "{{business_id}}", "name": "{{business_name}}"}]}
        d = self.work / 'templates'
        json.dump(tpl, open(d / 'home.json', 'w'))
        json.dump({"placeholders": {"business_id": "The business @id", "business_name": "Legal name"}}, open(d / 'home.map.json', 'w'))

    def test_mark_requires_template(self):
        r = run('mark', '--work', self.work, '--slug', 'home', '--status', 'passed')
        self.assertNotEqual(r.returncode, 0)

    def test_doc_refuses_until_all_passed(self):
        self.write_home()
        run('check', '--work', self.work, '--slug', 'home', '--page-url', 'https://x.test/')
        run('mark', '--work', self.work, '--slug', 'home', '--status', 'passed')
        r = run('doc', '--work', self.work, '--out', self.tmp / 'doc.md')
        self.assertEqual(r.returncode, 1)
        self.assertIn('treatment', r.stdout)
        self.assertFalse((self.tmp / 'doc.md').exists())

    def test_failed_blocks_doc(self):
        self.write_home()
        run('check', '--work', self.work, '--slug', 'home')
        run('mark', '--work', self.work, '--slug', 'home', '--status', 'failed', '--note', 'error')
        self.assertEqual(run('doc', '--work', self.work, '--out', self.tmp / 'doc.md').returncode, 1)

    def test_doc_with_all_passed(self):
        self.write_home()
        self.install_example()
        for slug, url in (('home', 'https://x.test/'), ('treatment', 'https://x.test/dermal-filler')):
            self.assertEqual(run('check', '--work', self.work, '--slug', slug, '--page-url', url).returncode, 0)
            run('mark', '--work', self.work, '--slug', slug, '--status', 'passed')
        r = run('doc', '--work', self.work, '--client', 'Test Med Spa', '--out', self.tmp / 'doc.md')
        self.assertEqual(r.returncode, 0, r.stdout)
        text = (self.tmp / 'doc.md').read_text()
        self.assertIn('# Schema markup templates - Test Med Spa', text)
        self.assertIn('## Home', text)
        self.assertIn('## Service, Sub-Service and Brand / Device', text)
        self.assertIn('https://x.test/dermal-filler', text)
        self.assertIn('| `{{business_name}}` | Legal name |', text)
        self.assertIn('"@type": "MedicalProcedure"', text)

    def install_example(self):
        d = self.work / 'templates'
        shutil.copy(SKILL / 'references/example-treatment.json', d / 'treatment.json')
        shutil.copy(SKILL / 'references/example-treatment.map.json', d / 'treatment.map.json')


class TestSkillFiles(unittest.TestCase):
    def test_frontmatter_name_matches_folder(self):
        text = (SKILL / 'SKILL.md').read_text()
        self.assertIn(f'name: {SKILL.name}', text.split('---')[1])

    def test_example_files_are_json(self):
        for f in ('example-treatment.json', 'example-treatment.map.json'):
            json.load(open(SKILL / 'references' / f))


if __name__ == '__main__':
    unittest.main()
