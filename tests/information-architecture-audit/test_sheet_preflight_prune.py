"""IA audit: Search Console from a sheet, GA4 block import, preflight, and the prune type check.

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

    def test_gsc_data_sheet_is_not_the_template(self):
        import openpyxl
        wb = openpyxl.Workbook()
        wb.active.title = "Claude Use This"
        wb.save(self.t / "t.xlsx")
        r = self.pre("--template", self.t / "t.xlsx")
        self.assertIn("looks like the Search Console data sheet", r.stdout)

    def test_missing_redirects_can_be_skipped_explicitly(self):
        r = self.pre("--skip", "redirects")
        self.assertIn("SKIPPED  Redirects export", r.stdout)

    def test_ga4_undecided_is_a_warning_not_a_composio_requirement(self):
        r = self.pre()
        self.assertIn("GA4: not decided", r.stdout)


class TypeCheck(unittest.TestCase):
    def test_conflicts_grouped_and_noise_split(self):
        t = Path(tempfile.mkdtemp())
        (t / "analysis").mkdir()
        ia = pd.DataFrame([
            ("https://x.com/radiesse-brandon-fl/", "/radiesse-brandon-fl/", "Service-like (no folder)", "Rule 7", "Radiesse"),
            ("https://x.com/botox/", "/botox/", "Service", "mapping", "Botox"),
            ("https://x.com/body/", "/body/", "Service-like (no folder)", "Rule 7", "Body"),
            ("https://x.com/about/", "/about/", "Company / Info", "Rule 7", "About"),
        ], columns=["url", "path", "type", "why", "h1"])
        ia.to_csv(t / "analysis/all_pages.csv", index=False)
        pr = pd.DataFrame([
            ("/radiesse-brandon-fl/", "Blog Post", "Root-level, slug reads like a post"),
            ("/botox/", "Service", "Folder map: /services/"),
            ("/body/", "Hub / Category Page", "Folder map: listing page"),
            ("/about/", "Other", "Slug: about"),
        ], columns=["key", "prune_type", "prune_reason"])
        pr["plan_action"], pr["plan_target"], pr["plan_source"], pr["url"] = "Keep", "", "Suggested Next Step", ""
        pr.to_csv(t / "prune.csv", index=False)
        r = run("type_check.py", "--work", t)
        c = pd.read_csv(t / "review/type_conflicts.csv", keep_default_na=False).set_index("path")
        self.assertEqual(set(c.index), {"/radiesse-brandon-fl/", "/body/"})   # agreeing pages are not listed
        self.assertEqual(c.loc["/radiesse-brandon-fl/", "severity"], "Different type")
        self.assertEqual(c.loc["/body/", "severity"], "Hub or page?")
        self.assertIn("a guess from the URL wording", c.loc["/radiesse-brandon-fl/", "prune_basis"].replace("was ", "a ").replace("a a", "a"))
        self.assertIn("CONFLICTS: 2 of 4", r.stdout)


if __name__ == "__main__":
    unittest.main()
