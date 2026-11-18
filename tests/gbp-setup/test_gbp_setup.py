"""GBP setup: top 3 categories per export, specialty grouping, service matching, character limits, outputs.

Run from the repo root:  python3 -m unittest discover -s tests/gbp-setup -v
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

SCRIPT = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/gbp-setup/scripts/gbp_setup.py'


def run(*args):
    return subprocess.run([sys.executable, '-I', str(SCRIPT), *args], capture_output=True, text=True)


def export(path, rows):
    out = []
    for i, (name, cats) in enumerate(rows, 1):
        r = {'Position': i, 'Business Name': name, 'Rating': '4.5', 'Reviews': '10', 'Primary Category': cats[0]}
        for j in range(4):
            r[f'Category {j + 2}'] = cats[j + 1] if j + 1 < len(cats) else ''
        out.append(r)
    Path(path).write_text(json.dumps({'data': out}))


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        d = Path(self.t.name)
        self.d = d
        rm = pd.DataFrame([['Home', 'Home', ''], ['Dermal Filler', 'Service', ''], ['Lip Filler', 'Sub-Service', 'Dermal Filler'],
                           ['Dental Implants', 'Service', ''], ['Botox', 'Brand / Device', 'Neurotoxin'], ['Acne', 'Concern', ''],
                           ['Blog 1', 'Blog', '']], columns=['Page', 'Page type', 'Parent page / links to'])
        cut = pd.DataFrame([['Kybella', 'Brand / Device', ''], ['Teeth Whitening', 'Service', '']], columns=rm.columns)
        with pd.ExcelWriter(d / 'roadmap.xlsx') as xw:
            rm.to_excel(xw, sheet_name='Roadmap', index=False)
            cut.to_excel(xw, sheet_name='Cut for the 50-page cap', index=False, startrow=1)
        ms = ['Medical spa', 'Skin care clinic', 'Day spa', 'Plastic surgeon']
        export(d / 'a.json', [(f'A{i}', ['Medical spa', 'Skin care clinic'] if i < 4 else ['Day spa', 'Medical spa']) for i in range(5)]
               + [('Glow', ['Medical spa'])])
        export(d / 'b.json', [(f'B{i}', ['Medical spa', 'Plastic surgeon'] if i < 3 else ['Skin care clinic']) for i in range(5)])
        export(d / 'c.json', [(f'C{i}', ['Dental implants provider', 'Dentist']) for i in range(4)])
        self.args = ['--roadmap', str(d / 'roadmap.xlsx'), '--gbp', f'Med spa|search a={d / "a.json"}', '--gbp', f'Med spa|search b={d / "b.json"}',
                     '--gbp', f'Dental|search c={d / "c.json"}', '--business', 'Glow']

    def tearDown(self):
        self.t.cleanup()

    def categories(self):
        r = run('categories', *self.args, '--out', str(self.d / 'work'))
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return json.loads((self.d / 'work/categories.json').read_text())

    def fill(self, cats, desc=None):
        w = self.d / 'work'
        m = pd.read_csv(w / 'service_match.tsv', sep='\t', dtype=str, keep_default_na=False)
        m['category'] = m['page'].map(cats).fillna('')
        m.to_csv(w / 'service_match.tsv', sep='\t', index=False)
        ds = pd.read_csv(w / 'descriptions.tsv', sep='\t', dtype=str, keep_default_na=False)
        ds['description'] = ds['name'] + ' by our licensed team.'
        for k, v in (desc or {}).items():
            ds.loc[ds['name'] == k, 'description'] = v
        ds.to_csv(w / 'descriptions.tsv', sep='\t', index=False)

    def build(self):
        return run('build', *self.args, '--client', 'Test', '--match', str(self.d / 'work/service_match.tsv'),
                   '--descriptions', str(self.d / 'work/descriptions.tsv'), '--out', str(self.d / 't.docx'), '--sheet', str(self.d / 't.xlsx'))


class TestGbpSetup(Base):
    def test_preflight_ready_and_missing(self):
        r = run('preflight', *self.args, '--client', 'Test', '--out', str(self.d / 'w'))
        self.assertEqual(r.returncode, 0, r.stdout)
        r = run('preflight', '--roadmap', str(self.d / 'roadmap.xlsx'), '--client', 'Test', '--out', str(self.d / 'w'))
        self.assertEqual(r.returncode, 1)
        self.assertIn('no Pleper Search Export', r.stdout)

    def test_top3_per_export_excludes_client_and_groups_by_specialty(self):
        c = self.categories()
        self.assertEqual(len(c), 3)
        a = next(x for x in c if x['search'] == 'search a')
        self.assertEqual(a['n_competitors'], 5)                      # Glow is the client, not a competitor
        self.assertEqual([t['category'] for t in a['top']], ['Medical spa', 'Skin care clinic', 'Day spa'])
        self.assertTrue(all(len(x['top']) <= 3 for x in c))

    def test_build_makes_doc_and_sheet(self):
        self.categories()
        self.fill({'Dermal Filler': 'Medical spa', 'Lip Filler': 'Medical spa', 'Dental Implants': 'Dental implants provider'})
        r = self.build()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertNotIn('FAIL', r.stdout)
        wb = load_workbook(self.d / 't.xlsx')
        self.assertEqual({'Services', 'Products'}, set(wb.sheetnames))
        self.assertEqual(wb['Services'].max_row - 1, 4)             # includes the service from the cut tab
        self.assertEqual(wb['Products'].max_row - 1, 2)             # Botox and the cut-tab Kybella
        self.assertTrue((self.d / 't.docx').exists())

    def test_unknown_category_stops(self):
        self.categories()
        self.fill({'Dermal Filler': 'Not a category'})
        r = self.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('not in any top 3', r.stderr + r.stdout)

    def test_character_limits_stop_the_build(self):
        self.categories()
        self.fill({'Dermal Filler': 'Medical spa'}, {'Dermal Filler': 'x' * 276, 'Botox': 'y' * 751})
        r = self.build()
        self.assertNotEqual(r.returncode, 0)
        out = r.stderr + r.stdout
        self.assertIn('276 characters', out)
        self.assertIn('751 characters', out)
        ds = pd.read_csv(self.d / 'work/descriptions.tsv', sep='\t', dtype=str, keep_default_na=False)
        ds.loc[ds['name'] == 'Kybella', 'title'] = 'K' * 46
        ds.loc[ds['name'] == 'Dermal Filler', 'description'] = 'x' * 275
        ds.loc[ds['name'] == 'Botox', 'description'] = 'y' * 750
        ds.to_csv(self.d / 'work/descriptions.tsv', sep='\t', index=False)
        r = self.build()
        self.assertIn('46 characters', r.stderr + r.stdout)

    def test_blank_description_stops(self):
        self.categories()
        self.fill({})
        ds = pd.read_csv(self.d / 'work/descriptions.tsv', sep='\t', dtype=str, keep_default_na=False)
        ds.loc[0, 'description'] = ''
        ds.to_csv(self.d / 'work/descriptions.tsv', sep='\t', index=False)
        self.assertNotEqual(self.build().returncode, 0)


if __name__ == '__main__':
    unittest.main()
