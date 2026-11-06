"""site-diagnosis preflight.py on a small made-up site.

Run from the repo root:  python3 -m unittest discover -s tests/site-diagnosis -v
"""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins/mavan-seo/skills/site-diagnosis/scripts/preflight.py"
SITE = "https://www.example-dental.com"
GSC = ["Page", "Query", "Clicks", "Impressions", "Position"]
SITEBULB = ["URL", "HTTP Status Code", "Indexable Status", "Crawl Depth", "Path Depth", "Crawl Source", "Title",
            "Meta Description", "H1", "H2", "H2 (second)", "No. Content Words", "No. Internal Links to URL",
            "Canonical URL"]


def write_csv(path, head, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(head)
        w.writerows(rows)


class Preflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.d = Path(cls.tmp.name)
        a = [[SITE + "/smiles/whitening/", "teeth whitening", 10, 200, 5], [SITE + "/", "example dental", 50, 400, 1]]
        b = [[SITE + "/smiles/whitening/", "teeth whitening", 4, 90, 8], [SITE + "/", "example dental", 55, 420, 1]]
        with pd.ExcelWriter(d / "gsc.xlsx") as w:
            pd.DataFrame([GSC] + a).to_excel(w, sheet_name="Jan-Mar", header=False, index=False)
            pd.DataFrame([GSC] + b).to_excel(w, sheet_name="Apr-Jun", header=False, index=False)
        page = lambda p, s: [SITE + p, s, "Indexable", 1, 1, "Crawl", "t", "m", "h", "a", "b", 500, 5, SITE + p]
        crawl = [page("/", 200), page("/smiles/whitening/", 200), page("/old/", 404)]
        write_csv(d / "crawl.csv", SITEBULB, crawl)
        write_csv(d / "crawl_thin.csv", ["Address", "Status Code", "Title 1", "Clicks"],
                  [[SITE + "/", 200, "t", 3], [SITE + "/old/", 404, "", 0]])
        write_csv(d / "links.csv", ["Target URL", "Linking URL", "CSS Path"], [[SITE + "/", SITE + "/old/", "nav a"]])
        write_csv(d / "redirects.csv", ["URL", "Redirect URL"], [[SITE + "/a/", SITE + "/b/"]])
        cls.base = ["--domain", "example-dental.com", "--client", "Example Dental", "--brand", "example dental",
                    "--a", str(d / "gsc.xlsx"), "--a-tab", "Jan-Mar", "--a-start", "2026-01-01", "--a-end", "2026-03-31",
                    "--b", str(d / "gsc.xlsx"), "--b-tab", "Apr-Jun", "--b-start", "2026-04-01", "--b-end", "2026-06-30"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_pf(self, *args):
        out = self.d / "work"
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), *args, "--out", str(out)], capture_output=True, text=True)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        self.assertTrue((out / "preflight.md").exists())
        return r

    def args(self, **change):
        a = list(self.base)
        for k, v in change.items():
            flag = "--" + k.replace("_", "-")
            i = a.index(flag)
            if v is None:
                del a[i:i + 2]
            else:
                a[i + 1] = v
        return a

    def test_ready_with_full_combined_export(self):
        r = self.run_pf(*self.base, "--crawl", str(self.d / "crawl.csv"), "--links", str(self.d / "links.csv"),
                        "--redirects", str(self.d / "redirects.csv"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("has every column triage, the IA audit and the service gap audit use", r.stdout)
        self.assertNotIn("FAIL ", r.stdout)

    def test_missing_crawl_is_a_warning_not_a_stop(self):
        r = self.run_pf(*self.base)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("WARN  Crawl URL export: not provided", r.stdout)
        self.assertIn("INFO  Links export: not provided", r.stdout)

    def test_missing_columns_name_the_audit(self):
        r = self.run_pf(*self.base, "--crawl", str(self.d / "crawl_thin.csv"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("no word count column; needed by the IA audit, service gap audit (required there)", r.stdout)
        self.assertIn("no meta description column; needed by the service gap audit", r.stdout)
        self.assertIn("search or analytics columns (Clicks)", r.stdout)

    def test_missing_dates_and_brand_fail(self):
        r = self.run_pf(*self.args(a_start=None, brand=None))
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing: --a-start", r.stdout)
        self.assertIn("brand terms not confirmed", r.stdout)
        self.assertIn("NOT READY", r.stdout)

    def test_same_tab_and_ambiguous_tab_fail(self):
        r = self.run_pf(*self.args(b_tab="Jan-Mar"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("are the same tab", r.stdout)
        r = self.run_pf(*self.args(a_tab=None))
        self.assertEqual(r.returncode, 1)
        self.assertIn("several tabs have Search Console columns", r.stdout)

    def test_date_order_overlap_and_length(self):
        r = self.run_pf(*self.args(a_start="2026-05-01", a_end="2026-06-30"))
        self.assertIn("period A must be the earlier period", r.stdout)
        r = self.run_pf(*self.args(a_end="2026-04-15"))
        self.assertIn("the periods overlap", r.stdout)
        r = self.run_pf(*self.args(a_start="2026-02-15"))
        self.assertIn("not like for like", r.stdout)

    def test_brand_none_is_accepted(self):
        r = self.run_pf(*self.args(brand="none"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("brand terms: none", r.stdout)


if __name__ == "__main__":
    unittest.main()
