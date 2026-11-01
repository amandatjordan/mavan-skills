"""content-prune-merge prep.py on a small made-up Sitebulb-style site.

Run from the repo root:  python3 -m unittest discover -s tests/content-prune-merge -v
"""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins/mavan-seo/skills/content-prune-merge/scripts/prep.py"
SITE = "https://example-medspa.com"

URLS = [
    # URL, status, indexable, title, h1, words, canonical
    ("/", 200, "Indexable", "Home", "Med spa", 500, "/"),
    ("/services/botox-denver/", 200, "Indexable", "Botox", "Botox", 900, "/services/botox-denver/"),
    ("/services/botox-denver", 301, "", "", "", 0, ""),            # slash-only redirect, same key as the 200
    ("/services/botox-boulder/", 200, "Indexable", "Botox Boulder", "Botox Boulder", 120, "/services/botox-boulder/"),
    ("/old-botox/", 301, "", "", "", 0, ""),                      # two hops: /old-botox/ -> /botox/ -> /services/botox-denver/
    ("/botox/", 301, "", "", "", 0, ""),
    ("/old-peel/", 301, "", "", "", 0, ""),                       # ends on a 404
    ("/peel/", 404, "", "", "", 0, ""),
    ("/blog-post/", 200, "Indexable", "Post", "Post", 1500, "/blog-post-2/"),
    ("/blog-post-2/", 301, "", "", "", 0, ""),                   # canonical that redirects back
]
REDIRECTS = [
    ("/services/botox-denver", "/services/botox-denver/"),
    ("/old-botox/", "/botox/"),
    ("/botox/", "/services/botox-denver/"),
    ("/old-peel/", "/peel/"),
    ("/blog-post-2/", "/blog-post/"),
]
LINKS = [
    ("/services/botox-denver/", "/", "Header", "header>nav>ul>li>a"),
    ("/services/botox-boulder/", "/", "Header", "header>nav>ul>li>a"),
    ("/blog-post/", "/services/botox-denver/", "Content", "main>article>p>a"),
    ("/services/botox-denver/", "/blog-post/", "Footer", "footer>div>ul>li>a"),
]


def write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


class Prep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        write(d / "urls.csv", ["URL", "HTTP Status Code", "Indexable Status", "Title", "H1", "No. Content Words", "Canonical URL"],
              [(SITE + u, s, i, t, h, w, SITE + c if c else "") for u, s, i, t, h, w, c in URLS])
        write(d / "redirects.csv", ["URL", "HTTP Status Code", "Redirect URL"],
              [(SITE + s, 301, SITE + t) for s, t in REDIRECTS])
        write(d / "links.csv", ["Target URL", "Linking URL", "Location", "CSS Path"],
              [(SITE + t, SITE + s, loc, p) for t, s, loc, p in LINKS])
        out = d / "work"
        cls.proc = subprocess.run([sys.executable, str(SCRIPT), "--domain", "example-medspa.com", "--urls", str(d / "urls.csv"),
                                  "--links", str(d / "links.csv"), "--redirects", str(d / "redirects.csv"), "--out", str(out)],
                                 capture_output=True, text=True)
        cls.out = out

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_runs(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_one_primary_row_per_key_prefers_the_200(self):
        p = pd.read_csv(self.out / "crawl_pages.csv")
        prim = p[p.primary]
        self.assertFalse(prim.key.duplicated().any())
        self.assertEqual(int(prim[prim.key == "/services/botox-denver/"].status.iloc[0]), 200)

    def test_redirect_chains_are_resolved(self):
        r = pd.read_csv(self.out / "redirects.csv").set_index("source")
        self.assertTrue(r.loc["/services/botox-denver/", "normalization_only"])
        self.assertEqual(r.loc["/old-botox/", "final"], "/services/botox-denver/")
        self.assertEqual(int(r.loc["/old-botox/", "hops"]), 2)
        self.assertEqual(r.loc["/old-botox/", "chain"], "/old-botox/ -> /botox/ -> /services/botox-denver/")
        self.assertEqual(int(r.loc["/old-botox/", "final_status"]), 200)
        self.assertEqual(int(r.loc["/old-peel/", "final_status"]), 404)

    def test_report_counts(self):
        rep = json.loads((self.out / "prep_report.json").read_text())
        self.assertEqual(rep["redirects_normalization_only"], 1)
        self.assertEqual(rep["redirects_multi_hop"], 1)
        self.assertEqual(rep["redirects_final_not_live"], 1)
        self.assertEqual(rep["canonical_redirect_loops"], 1)

    def test_slug_words_counts_live_pages_only(self):
        sw = pd.read_csv(self.out / "slug_words.csv").set_index("word")
        self.assertEqual(int(sw.loc["botox", "pages"]), 2)   # the two live service pages; redirects not counted
        self.assertEqual(int(sw.loc["denver", "pages"]), 1)
        self.assertNotIn("peel", sw.index)


if __name__ == "__main__":
    unittest.main()
