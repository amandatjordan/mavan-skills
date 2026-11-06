"""site-diagnosis triage.py on a small made-up dental site with non-standard URL paths.

Run from the repo root:  python3 -m unittest discover -s tests/site-diagnosis -v
Expected numbers are worked out by hand in the comments, not by the script.
"""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins/mavan-seo/skills/site-diagnosis/scripts/triage.py"
SITE = "https://www.example-dental.com"
HEAD = ["Page", "Query", "Clicks", "Impressions", "CTR", "Position"]

A_ROWS = [
    ("/smiles/whitening/", "teeth whitening cleveland", 10, 200, 5),
    ("/journal/whitening-tips/", "teeth whitening cleveland", 2, 120, 9),
    ("/journal/old-post/", "how to whiten", 5, 300, 7),
    ("/", "bright smile dental", 50, 400, 1),
    ("/smiles/implants/", "dental implants cleveland", 8, 150, 6),
]
B_ROWS = [
    ("/smiles/whitening/", "teeth whitening cleveland", 4, 90, 8),
    ("/journal/whitening-tips/", "teeth whitening cleveland", 3, 110, 8),
    ("/", "bright smile dental", 55, 420, 1),
    ("/smiles/implants/", "dental implants cleveland", 12, 220, 5),
    ("/smiles/new-page/", "invisalign cleveland", 1, 30, 12),
]
CRAWL = [("/", 200), ("/smiles/whitening/", 200), ("/journal/whitening-tips/", 200),
         ("/journal/old-post/", 404), ("/smiles/implants/", 200)]


def write(path, head, rows, prefix=""):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(head)
        for r in rows:
            w.writerow([prefix + r[0], *r[1:]] if prefix is not None else r)


def run(*args):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True)


class Triage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.a, cls.b, cls.crawl = d / "a.csv", d / "b.csv", d / "crawl.csv"
        for p, rows in ((cls.a, A_ROWS), (cls.b, B_ROWS)):
            with open(p, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(HEAD)
                for page, q, c, i, pos in rows:
                    w.writerow([SITE + page, q, c, i, c / i, pos])
        with open(cls.crawl, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Address", "Status Code", "Title 1"])
            for page, s in CRAWL:
                w.writerow([SITE + page, s, "t"])
        cls.out = d / "Client Site Triage.xlsx"
        cls.args = ["build", "--domain", "example-dental.com", "--client", "Example Dental",
                    "--brand", "bright smile", "--a", str(cls.a), "--a-start", "2026-01-01", "--a-end", "2026-03-31",
                    "--b", str(cls.b), "--b-start", "2026-04-01", "--b-end", "2026-06-30",
                    "--min-page-impr", "100", "--top-n", "5", "--prune-if", "1", "--dead-share-pct", "25",
                    "--out", str(cls.out)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def build(self, *extra):
        r = run(*self.args, *extra)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return r.stdout

    def sheet(self, name):
        return pd.read_excel(self.out, sheet_name=name, header=None).fillna("")

    def test_summary_totals(self):
        self.build("--crawl", str(self.crawl))
        s = self.sheet("Summary")
        row = lambda label: s[s[0] == label].iloc[0].tolist()
        # A: clicks 10+2+5+50+8=75, impr 200+120+300+400+150=1170, non-brand clicks 25, non-brand impr 770
        self.assertEqual(row("Clicks (all searches)")[1:4], [75, 75, 0])
        self.assertEqual(row("Impressions (all searches)")[1:4], [1170, 870, -300])
        self.assertEqual(row("Clicks (non-brand)")[1:4], [25, 20, -5])
        self.assertEqual(row("Impressions (non-brand)")[1:4], [770, 450, -320])
        self.assertEqual(row("Impressions (brand)")[1:4], [400, 420, 20])

    def test_pages_and_dead_url_flag(self):
        self.build("--crawl", str(self.crawl))
        p = self.sheet("Pages")
        losses = p[p[0] == "Loss"]
        self.assertEqual(losses[1].tolist()[:3], ["/journal/old-post/", "/smiles/whitening/", "/journal/whitening-tips/"])
        self.assertEqual(losses.iloc[0][2], "404 not found")
        self.assertEqual(losses.iloc[0][5], -300)
        gains = p[p[0] == "Gain"]
        self.assertEqual(gains[1].tolist(), ["/smiles/implants/", "/smiles/new-page/"])
        self.assertEqual(gains.iloc[1][2], "Not in crawl")

    def test_searches_and_pages_behind(self):
        self.build()
        s = self.sheet("Searches")
        losses = s[s[0] == "Loss"]
        self.assertEqual(losses[1].tolist(), ["how to whiten", "teeth whitening cleveland"])
        self.assertEqual(losses[4].tolist(), [-300, -120])
        self.assertNotIn("bright smile dental", s[1].tolist())  # brand left out
        b = self.sheet("Pages behind searches")
        sub = b[b[0] == "teeth whitening cleveland"]
        self.assertEqual(sub[1].tolist(), ["/smiles/whitening/", "/journal/whitening-tips/"])
        self.assertEqual(sub[2].tolist(), [200, 120])  # impressions A
        self.assertEqual(sub[3].tolist(), [90, 110])  # impressions B

    def test_competing_threshold(self):
        self.build()
        c = self.sheet("Competing pages")
        body = c.iloc[3:]
        # at 100 impressions only period A has two qualifying pages
        self.assertEqual(body[0].tolist(), ["teeth whitening cleveland"] * 2)
        self.assertEqual(set(body[1]), {"period A only"})
        out = self.build("--crawl", str(self.crawl))
        self.assertIn("Competing searches: 1 (1 in A, 0 in B)", out)

    def test_competing_lower_threshold_and_next_steps(self):
        args = list(self.args)
        args[args.index("--min-page-impr") + 1] = "50"
        r = run(*args, "--crawl", str(self.crawl))
        self.assertEqual(r.returncode, 0, r.stderr)
        c = self.sheet("Competing pages")
        self.assertEqual(set(c.iloc[3:][1]), {"both periods"})
        n = self.sheet("What to run next")
        nxt = dict(zip(n[0], n[3]))
        self.assertEqual(nxt["Content Prune & Merge"], "Yes")
        # old-post is 300 of 770 non-brand impressions in A = 39% >= 25
        self.assertEqual(nxt["Information architecture audit"], "Yes")
        self.assertEqual(nxt["Service gap audit"], "Ask the person")

    def test_url_list_and_no_crawl(self):
        self.build()
        n = self.sheet("What to run next")
        self.assertEqual(dict(zip(n[0], n[3]))["Information architecture audit"], "Ask the person")
        urls = Path(str(self.out)[:-5] + " URLs to crawl.txt").read_text().split()
        self.assertEqual(len(urls), 6)  # 6 distinct pages across both periods
        self.assertIn(SITE + "/journal/old-post/", urls)

    def test_same_tab_and_bad_dates_stop(self):
        args = list(self.args)
        args[args.index("--b") + 1] = str(self.a)
        r = run(*args)
        self.assertNotEqual(r.returncode, 0)
        args = list(self.args)
        args[args.index("--a-start") + 1] = "2026-05-01"
        self.assertNotEqual(run(*args).returncode, 0)

    def test_profile(self):
        r = run("profile", "--domain", "example-dental.com", "--brand", "bright smile", "--a", str(self.a),
                "--b", str(self.b), "--crawl", str(self.crawl))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1,170 impressions", r.stdout)
        self.assertIn("'404 not found': 1", r.stdout)


if __name__ == "__main__":
    unittest.main()
