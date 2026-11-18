"""New site IA: URLs, nav rules, CSV pages, links copied unchanged, warnings, preflight.

Run from the repo root:  python3 -m unittest discover -s tests/new-site-ia -v
"""
import csv
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

SKILL = Path(__file__).resolve().parents[2] / 'plugins/mavan-seo/skills/new-site-ia'
SCRIPT = SKILL / 'scripts/ia.py'
_spec = importlib.util.spec_from_file_location('ia', SCRIPT)
ia = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ia)

ROAD_HEAD = ["#", "Page", "Page type", "Content to write", "Why", "Parent page / links to", "Primary keyword",
             "Vol", "Must appear on page (anchor text other pages use to link here)", "Gap", "Sections", "SEO priority"]


def make_roadmap(path, pages, links, with_links_tab=True, cut=0):
    wb = openpyxl.Workbook()
    rm = wb.active
    rm.title = "Roadmap"
    rm.append(ROAD_HEAD)
    for i, (name, typ, parent, anchors) in enumerate(pages, 1):
        content = "Blog post" if typ == "Blog" else "Page"
        rm.append([i, name, typ, content, "", parent, "", "", anchors, "", "", ""])
    if with_links_tab:
        il = wb.create_sheet("Internal links")
        il.append(["From page", "To page", "Anchor text", "Where this link came from"])
        for l in links:
            il.append(list(l))
    ct = wb.create_sheet("Cut for the 50-page cap")
    ct.append(["note"] + [None] * 12)
    ct.append(["#", "Page"] + [None] * 11)
    for i in range(cut):
        ct.append([None, f"cut {i}"] + [None] * 11)
    wb.save(path)


def make_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Page", "URL"])
        w.writerows(rows)


PAGES = [
    ("Home", "Home", "", ""),
    ("About Us", "About Us", "", ""),
    ("Neurotoxin", "Service", "", "neurotoxins"),
    ("Neurotoxin > Botox", "Brand / Device", "Neurotoxin", "botox"),
    ("Dermal Filler", "Service", "", "facial fillers; cheek filler"),
    ("Dermal Filler > Lip Filler", "Sub-Service", "Dermal Filler", "lip fillers"),
    ("Dermal Filler > Juvéderm Volbella XC", "Brand / Device", "Dermal Filler > Lip Filler", "volbella"),
    ("Dermal Filler > Evolysse (Form, Smooth)", "Brand / Device", "Dermal Filler", "evolysse"),
    ("Blog 1: How to prepare for Neurotoxin and what to do between visits", "Blog", "Neurotoxin page", ""),
]
LINKS = [
    ("Home", "Neurotoxin", "neurotoxins", "x"),
    ("Neurotoxin", "Neurotoxin > Botox", "botox", "x"),
    ("Neurotoxin > Botox", "Neurotoxin", "neurotoxins", "x"),
    ("Home", "Dermal Filler", "facial fillers", "x"),
    ("Home", "Dermal Filler", "cheek filler", "x"),
    ("Dermal Filler", "Dermal Filler > Lip Filler", "lip fillers", "x"),
    ("Dermal Filler > Lip Filler", "Dermal Filler > Juvéderm Volbella XC", "volbella", "x"),
    ("Dermal Filler", "Dermal Filler > Evolysse (Form, Smooth)", "evolysse", "x"),
    ("Blog 1: How to prepare for Neurotoxin and what to do between visits", "Neurotoxin", "neurotoxins", "x"),
]


class T(unittest.TestCase):
    def run_build(self, pages=PAGES, links=LINKS, csv_rows=(("Contact", "/contact"), ("Privacy Policy", ""),), **kw):
        d = tempfile.mkdtemp()
        r, c, o = (os.path.join(d, n) for n in ("r.xlsx", "c.csv", "o.xlsx"))
        make_roadmap(r, pages, links, **kw)
        make_csv(c, csv_rows)
        self.paths = (r, c, o)
        res = ia.plan(r, c)
        ia.write_workbook(res, o)
        wb = openpyxl.load_workbook(o)
        pg = {row[0]: row for row in wb["Pages"].iter_rows(min_row=2, values_only=True)}
        return pg, list(wb["Internal links"].iter_rows(min_row=2, values_only=True)), res["warnings"], wb

    def test_slugify(self):
        self.assertEqual(ia.slugify("Juvéderm Volbella XC"), "juvederm-volbella-xc")
        self.assertEqual(ia.slugify("Evolysse (Form, Smooth)"), "evolysse")
        self.assertEqual(ia.slugify("Revanesse Versa / Lips+"), "revanesse-versa-lips-plus")

    def test_services_prefix_and_depth(self):
        pg, *_ = self.run_build()
        self.assertEqual(pg["Neurotoxin"][3], "/services/neurotoxin")
        self.assertEqual(pg["Neurotoxin > Botox"][3], "/services/neurotoxin/botox")
        # brand whose parent is a sub-service stays at most one level under the Service
        self.assertEqual(pg["Dermal Filler > Juvéderm Volbella XC"][3], "/services/dermal-filler/juvederm-volbella-xc")
        self.assertEqual(pg["Dermal Filler > Juvéderm Volbella XC"][2], "Dermal Filler > Lip Filler")
        for row in pg.values():
            self.assertLessEqual(row[3].count("/"), 3)

    def test_home_about_and_non_service_paths(self):
        pg, *_ = self.run_build()
        self.assertEqual(pg["Home"][3], "/")
        self.assertEqual(pg["About Us"][3], "/about-us")

    def test_nav_rules(self):
        pg, *_ = self.run_build()
        self.assertEqual(pg["Home"][5], "Yes")
        self.assertEqual(pg["Blog"][5], "Yes")
        self.assertEqual(pg["Contact"][5], "Yes")
        self.assertEqual(pg["Privacy Policy"][5], "No")
        self.assertEqual(pg["Neurotoxin"][5], "Yes")
        self.assertEqual(pg["Neurotoxin > Botox"][5], "No")
        for name, row in pg.items():
            if row[1] == "Blog":
                self.assertEqual(row[5], "No")

    def test_nav_yellow_only_on_changeable_rows(self):
        *_, wb = self.run_build()
        ws = wb["Pages"]
        self.assertIn("SEO", ws.cell(1, 6).value)
        for row in ws.iter_rows(min_row=2):
            fixed = row[1].value in ("Home", "Blog") or row[1].value.startswith("Blog index")
            yellow = row[5].fill.fgColor.rgb in ("00FFF2CC", "FFFFF2CC")
            self.assertEqual(yellow, not fixed, row[0].value)

    def test_csv_url_kept_and_recommended(self):
        pg, *_ = self.run_build()
        self.assertEqual(pg["Contact"][3:5], ("/contact", "Provided"))
        self.assertEqual(pg["Privacy Policy"][3:5], ("/privacy-policy", "Recommended"))

    def test_csv_duplicate_of_roadmap_page_skipped(self):
        pg, _, w, _ = self.run_build(csv_rows=(("about us", ""),))
        self.assertEqual(list(pg).count("About Us"), 1)
        self.assertTrue(any("already on the roadmap" in x for x in w))

    def test_blog_index_added_and_blog_placeholder(self):
        pg, *_ = self.run_build()
        self.assertEqual(pg["Blog"][3], "/blog")
        b = [r for r in pg.values() if r[1] == "Blog"][0]
        self.assertEqual(b[3], "/blog/prepare-for-neurotoxin")

    def test_no_blog_index_without_blogs(self):
        pg, *_ = self.run_build(pages=PAGES[:-1], links=LINKS[:-1])
        self.assertNotIn("Blog", pg)

    def test_links_copied_unchanged_with_urls(self):
        _, links, _, _ = self.run_build()
        self.assertEqual(len(links), len(LINKS))
        self.assertEqual([(l[0], l[2], l[4]) for l in links], [(a, b, c) for a, b, c, _ in LINKS])
        self.assertEqual(links[1][1], "/services/neurotoxin")
        self.assertEqual(links[1][3], "/services/neurotoxin/botox")

    def test_unused_must_appear_term_warns_and_links_are_not_changed(self):
        broken = [l for l in LINKS if l[2] != "cheek filler"]
        _, links, w, _ = self.run_build(links=broken)
        self.assertTrue(any("cheek filler" in x and "Roadmap gap" in x for x in w))
        self.assertEqual(len(links), len(broken))

    def test_page_with_no_inbound_link_warns(self):
        broken = [l for l in LINKS if l[1] != "Neurotoxin > Botox"]
        _, _, w, _ = self.run_build(links=broken)
        self.assertTrue(any("No planned link points at 'Neurotoxin > Botox'" in x for x in w))

    def test_missing_links_tab_stops(self):
        with self.assertRaises(SystemExit):
            self.run_build(with_links_tab=False)

    def test_duplicate_url_warns(self):
        pg, _, w, _ = self.run_build(csv_rows=(("Services Neurotoxin", "/services/neurotoxin"),))
        self.assertTrue(any("used by more than one page" in x for x in w))

    def test_cut_pages_counted_not_listed(self):
        pg, _, _, wb = self.run_build(cut=3)
        detail = [r[1] for r in wb["Read Me"].iter_rows(values_only=True) if r[0] == "What this is"][0]
        self.assertIn("3 pages and blogs", detail)
        self.assertNotIn("cut 0", pg)

    def test_cli_build_prints_pass_and_preflight(self):
        d = tempfile.mkdtemp()
        r, c, o = (os.path.join(d, n) for n in ("r.xlsx", "c.csv", "o.xlsx"))
        make_roadmap(r, PAGES, LINKS)
        make_csv(c, (("Contact", "/contact"),))
        p = subprocess.run([sys.executable, str(SCRIPT), "preflight", "--roadmap", r, "--csv", c, "--out", d], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("READY", p.stdout)
        p = subprocess.run([sys.executable, str(SCRIPT), "build", "--roadmap", r, "--csv", c, "--out", o], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("FAIL", p.stdout)
        self.assertEqual(p.stdout.count("PASS"), 6)

    def test_preflight_needs_the_csv(self):
        d = tempfile.mkdtemp()
        r = os.path.join(d, "r.xlsx")
        make_roadmap(r, PAGES, LINKS)
        p = subprocess.run([sys.executable, str(SCRIPT), "preflight", "--roadmap", r, "--out", d], capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("CSV", p.stdout)
        self.assertIn("NOT READY", p.stdout)

    def test_preflight_fails_without_links_tab(self):
        d = tempfile.mkdtemp()
        r, c = os.path.join(d, "r.xlsx"), os.path.join(d, "c.csv")
        make_roadmap(r, PAGES, LINKS, with_links_tab=False)
        make_csv(c, ())
        p = subprocess.run([sys.executable, str(SCRIPT), "preflight", "--roadmap", r, "--csv", c, "--out", d], capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("Internal links", p.stdout)


if __name__ == "__main__":
    unittest.main()
