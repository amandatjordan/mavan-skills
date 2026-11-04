"""IA audit: Search Console from a sheet, GA4 block import, preflight, and reading the prune workbook.

Run from the repo root:  python3 -m unittest discover -s tests/information-architecture-audit -v
"""
import csv
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SK = ROOT / "plugins/mavan-seo/skills/information-architecture-audit/scripts"
D = "example-medspa.com"


def run(script, *args, check=True):
    r = subprocess.run([sys.executable, "-I", str(SK / script), *map(str, args)], capture_output=True, text=True)
    if check and r.returncode:
        raise AssertionError(f"{script} failed:\n{r.stdout}\n{r.stderr}")
    return r


GSC_TEXT = """## Sheet name: Other tab
Page,Query,Clicks,Impressions
https://example-medspa.com/x/,ignored query,9,999
## Sheet name: Claude Use This
Page,Query,Clicks,Impressions,CTR,Position
https://example-medspa.com/,example med spa,5,100,5%,2.0
https://example-medspa.com/?utm_source=gbp,botox near me,3,"1,000",0.3%,3.0
https://example-medspa.com/botox-denver/,botox denver,1,"1,200",0.1%,8.0
https://example-medspa.com/botox-denver/,botox price,0,300,0%,9.0
https://example-medspa.com/botox-boulder/,botox denver,0,900,0%,20.0
https://example-medspa.com/botox-boulder/,botox price,0,250,0%,22.0
https://example-medspa.com/filler/,lip filler,0,50,0%,12.0
"""


class Sheet(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        (self.t / "gsc.txt").write_text(GSC_TEXT)

    def build(self, *extra):
        return run("gsc_sheet.py", "build", "--sheet", self.t / "gsc.txt", "--domain", D, "--brand", "example med spa",
                   "--start", "2026-04-01", "--end", "2026-09-30", "--out", self.t / "gsc", *extra)

    def test_named_tab_pages_pairs_and_brand(self):
        r = self.build()
        self.assertIn("Loaded tab 'Claude Use This'", r.stdout)
        pages = pd.read_csv(self.t / "gsc/pages.csv", keep_default_na=False)
        self.assertNotIn("/x/", pages.key.tolist())                       # the other tab is never added in
        home = pages[pages.key == "/"].iloc[0]
        self.assertEqual((home.clicks, home.impressions), (8, 1100))      # utm variant joins the homepage
        pairs = pd.read_csv(self.t / "gsc/pairs.csv")
        self.assertEqual(len(pairs), 1)                                   # denver/boulder share two searches
        meta = dict(zip(*pd.read_csv(self.t / "gsc/meta.csv", keep_default_na=False)[["key", "value"]].values.T))
        self.assertEqual(meta["brand_query_impr"], "100")                 # the brand query is left out of query analysis
        self.assertEqual(meta["window_start"], "2026-04-01")

    def test_pair_queries_local(self):
        self.build()
        pages = pd.read_csv(self.t / "gsc/pages.csv")
        a, b = [int(pages[pages.key == k].id.iloc[0]) for k in ("/botox-denver/", "/botox-boulder/")]
        run("gsc_sheet.py", "pair-queries", "--pairs", f"{a}:{b}", "--out", self.t / "gsc")
        pq = pd.read_csv(self.t / "gsc/pair_queries.csv")
        self.assertIn("botox denver", pq.top_shared.iloc[0])

    def test_ga4_block_round_trip(self):
        body = "/botox-denver/|40|3\n/|10|1"
        crc = zlib.crc32(body.encode()) & 0xffffffff
        g = self.t / "gsc"
        g.mkdir()
        (g / "ga4.txt").write_text(f"##IA table=ga4 part=1/1 rows=2 crc={crc:08x}\nkey|sessions|key_events\n{body}\n##END\n")
        run("gsc_import.py", "--dir", g)
        r = self.build("--ga4-property", "properties/1")
        self.assertIn("GA4: merged 2", r.stdout)
        pages = pd.read_csv(g / "pages.csv")
        self.assertEqual(int(pages[pages.key == "/botox-denver/"].ga4_sessions.iloc[0]), 40)

    def test_wrong_domain_warns_and_no_dates_warns(self):
        (self.t / "other.txt").write_text("Page,Query,Clicks,Impressions\nhttps://someone-else.com/a/,q,1,10\n")
        r = run("gsc_sheet.py", "build", "--sheet", self.t / "other.txt", "--domain", D, "--out", self.t / "g2")
        self.assertIn("not on " + D, r.stdout)
        self.assertIn("no --start/--end", r.stdout)


class Preflight(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())

    def pre(self, *args):
        return run("preflight.py", "--domain", D, "--out", self.t / "o", *args, check=False)

    def test_filtered_url_export_and_missing_inputs_fail(self):
        f = self.t / "onpage.csv"
        f.write_text('"URL","Title","H1"\n"https://example-medspa.com/a/","T","H"\n')
        r = self.pre("--urls", f)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no status column", r.stdout)
        self.assertIn("Links export: not provided", r.stdout)
        self.assertIn("NOT READY", r.stdout)

    def test_prune_workbook_needs_known_tabs(self):
        import openpyxl
        wb = openpyxl.Workbook()
        wb.active.title = "Claude Use This"
        wb.save(self.t / "p.xlsx")
        r = self.pre("--prune", self.t / "p.xlsx")
        self.assertIn("none of the Content Prune & Merge tabs", r.stdout)

    def test_prune_copy_without_page_types_warns(self):
        import openpyxl
        wb = openpyxl.Workbook()
        wb.active.title = "Remove pages"
        wb.save(self.t / "p.xlsx")
        r = self.pre("--prune", self.t / "p.xlsx")
        self.assertIn("no page types", r.stdout)

    def test_missing_redirects_can_be_skipped_explicitly(self):
        r = self.pre("--skip", "redirects")
        self.assertIn("SKIPPED  Redirects export", r.stdout)

    def test_ga4_undecided_is_a_warning_not_a_composio_requirement(self):
        r = self.pre()
        self.assertIn("GA4: not decided", r.stdout)


def prune_workbook(path):
    import openpyxl
    wb = openpyxl.Workbook()
    k = wb.active
    k.title = "Kept pages"
    k.append(["banner"])
    k.append(["Page (SEO: QA this URL)", "Page type", "Clicks", "Impressions", "Why", "Disagree? Type the change you want (SEO fill in)"])
    k.append(["https://x.com/lip-flip/", "Service", 1, 50, "why", ""])
    k.append(["https://x.com/botox/", "Service", 1, 50, "why", "should be a hub"])
    c = wb.create_sheet("Check page type")
    c.append(["banner"])
    c.append(["Page", "Page type we guessed", "Correct page type (SEO fill in)", "Why we guessed"])
    c.append(["https://x.com/aftercare/", "Service", "Blog Post", "Root-level"])
    c.append(["https://x.com/body/", "Service", "SEO fill in", "Root-level"])
    c.append(["https://x.com/tips/", "Blog Post", "", "Root-level"])
    rm = wb.create_sheet("Remove pages")
    rm.append(["banner"])
    rm.append(["Page to remove", "Redirect to", "Why"])
    rm.append(["https://x.com/old/", "https://x.com/services/", ""])
    lc = wb.create_sheet("Per location service pages")
    lc.append(["banner"])
    lc.append(["Location page", "Main page", "Clicks", "What to do", "Unique content", "Why"])
    lc.append(["https://x.com/botox-denver/", "https://x.com/botox/", 3, "Merge into the main page", "", ""])
    lc.append(["https://x.com/botox-boulder/", "https://x.com/botox/", 9, "Keep", "", ""])
    dv = wb.create_sheet("All redirects - Handoff to Dev")
    dv.append(["Source URL", "Target URL", "Regex (0 = no, 1 = yes)", "HTTP Code"])
    dv.append(["https://x.com/tag/(.*)", "https://x.com/blog/", 1, 301])
    dv.append(["https://x.com/old/", "https://x.com/services/", 0, 301])
    wb.save(path)


class PruneImport(unittest.TestCase):
    def test_reads_new_workbook(self):
        t = Path(tempfile.mkdtemp())
        prune_workbook(t / "p.xlsx")
        r = run("prune_import.py", "--workbook", t / "p.xlsx", "--domain", "x.com", "--out", t / "w")
        pr = pd.read_csv(t / "w/prune.csv", keep_default_na=False).set_index("key")
        self.assertEqual(pr.loc["/lip-flip/", "prune_type"], "Service")                       # Kept pages
        self.assertEqual(pr.loc["/aftercare/", "prune_type"], "Blog Post")                    # SEO corrected the guess
        self.assertEqual(pr.loc["/body/", "prune_type"], "")                                  # guess nobody corrected
        self.assertEqual(pr.loc["/body/", "prune_reason"], "Guessed from the URL")
        self.assertEqual(pr.loc["/tips/", "prune_type"], "")                                  # blank = guess stands, IA types it
        self.assertEqual(pr.loc["/old/", "plan_action"], "Remove then Redirect")
        self.assertEqual(pr.loc["/old/", "plan_target"], "/services/")
        self.assertEqual(pr.loc["/botox-denver/", "plan_action"], "Merge then Redirect")
        self.assertEqual(pr.loc["/botox-boulder/", "plan_action"], "Keep")
        wild = pd.read_csv(t / "w/prune_wildcards.csv")
        self.assertEqual(wild.source.tolist(), ["https://x.com/tag/*"])                       # (.*) written back as *
        self.assertTrue((t / "w/prune_disagree.csv").exists())                                # not guessed at
        past = pd.read_csv(t / "w/past.csv", keep_default_na=False)
        self.assertIn("Remove then Redirect", past.decision.tolist())
        self.assertIn("Disagree", r.stdout)

    def test_not_a_prune_workbook_stops(self):
        import openpyxl
        t = Path(tempfile.mkdtemp())
        wb = openpyxl.Workbook()
        wb.active.title = "Other"
        wb.save(t / "o.xlsx")
        r = run("prune_import.py", "--workbook", t / "o.xlsx", "--domain", "x.com", "--out", t / "w", check=False)
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
