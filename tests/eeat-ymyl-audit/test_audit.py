"""eeat-ymyl-audit audit.py on a small made-up clinic (fixture.py).

Run from the repo root:  python3 -m unittest discover -s tests/eeat-ymyl-audit -v
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixture  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[2] / "plugins/mavan-seo/skills/eeat-ymyl-audit/scripts/audit.py"
SITE = fixture.SITE


def run(*args, check=True):
    p = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError(p.stdout + p.stderr)
    return p


class Audit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.d = Path(cls.tmp.name)
        cls.f = fixture.make(cls.d)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def common(self):
        f = self.f
        return ["--config", f["config.json"], "--crawl", f["crawl.csv"], "--outlinks", f["outlinks.csv"]]

    def test_preflight_part_one_writes_external_list(self):
        out = self.d / "work1"
        p = run("preflight", *self.common(), "--out", out)
        urls = (out / "external_urls.txt").read_text().split()
        self.assertEqual(len(urls), len(fixture.LINKS))
        self.assertFalse(any("social.example" in u for u in urls), "footer links must not be listed")
        self.assertIn("list crawl", p.stdout)
        self.assertIn("[Condition]", p.stdout)
        self.assertIn("START:", p.stdout)

    def test_preflight_full_lists_warnings(self):
        out = self.d / "work2"
        p = run("preflight", *self.common(), "--external", self.f["external.csv"], "--out", out)
        self.assertIn("4 crawled page(s) match no page type", p.stdout)
        self.assertIn("did not return 200", p.stdout)
        self.assertIn("blocked the crawler", p.stdout)
        self.assertIn("Author is empty on 4 of 8 pages", p.stdout)

    def test_preflight_shows_what_the_crawl_detected_on_chrome_pages(self):
        p = run("preflight", *self.common(), "--external", self.f["external.csv"], "--chrome", self.f["chrome.tsv"], "--out", self.d / "work5")
        self.assertIn("What the crawl detected on the pages checked in Claude in Chrome", p.stdout)
        self.assertIn("Author: Yes; reviewer: Yes; credentials: MD, board-certified", p.stdout)

    def test_queue_counts_per_type_and_text_files(self):
        out = self.d / "work3"
        p = run("queue", *self.common(), "--external", self.f["external.csv"], "--out", out)
        self.assertIn("Condition: 3 pages", p.stdout)
        self.assertIn("Service: 3 pages", p.stdout)
        self.assertIn("Blog: 2 pages", p.stdout)
        self.assertIn("Queue: 8 pages", p.stdout)
        self.assertEqual(len(list((out / "text").glob("*.txt"))), 8)
        self.assertIn("External citations on the page:", (out / "text/001.txt").read_text())

    def test_queue_types_and_max(self):
        out = self.d / "work4"
        p = run("queue", *self.common(), "--external", self.f["external.csv"], "--out", out, "--types", "Service,Blog", "--max", "4")
        self.assertIn("Queue: 4 pages", p.stdout)
        self.assertEqual(len(list((out / "text").glob("*.txt"))), 4)

    def test_build_workbook(self):
        out = self.d / "audit.xlsx"
        p = run("build", *self.common(), "--external", self.f["external.csv"], "--claims", self.f["claims.tsv"],
                "--chrome", self.f["chrome.tsv"], "--out", out)
        self.assertNotIn("FAIL", p.stdout)
        wb = load_workbook(out)
        self.assertEqual(wb.sheetnames, ["Recommendations", "Page Review", "External Links", "Accuracy Review Queue", "Chrome Page Check"])
        rows = {r[0]: r for r in wb["Page Review"].iter_rows(min_row=2, values_only=True)}
        self.assertEqual(len(rows), 8)  # providers, about, contact, tag page and the 404 are left out
        mig = rows[SITE + "/conditions/migraine/"]
        self.assertEqual(mig[2], "No")           # author
        self.assertEqual(mig[9], 2)              # citations
        self.assertEqual(mig[10], 0)             # no flagged links: forum is not flagged any more
        self.assertIn("No schema", mig[15])
        self.assertEqual(rows[SITE + "/services/botox/"][5], "12 years of experience")
        self.assertEqual(rows[SITE + "/services/botox/"][14], "Yes")
        links = list(wb["External Links"].iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(links), len(fixture.LINKS))
        flags = {r[2]: r[7] for r in links}
        self.assertIn("Dead link", flags["https://health-agency.example/high-blood-pressure"])
        self.assertIn("No shared words", flags["https://best-supplements.example/blood-sugar-support"])
        self.assertIn("Check manually", flags["https://blocked-journal.example/paper"])
        self.assertNotIn("Dead link", flags["https://blocked-journal.example/paper"])
        self.assertFalse(flags["https://health-agency.example/"])  # a homepage link or redirect is not flagged
        match = {r[2]: r[6] for r in links}
        self.assertEqual(match["https://health-agency.example/"], "Generic anchor")
        self.assertEqual(match["https://diabetes-assoc.example/standards-of-care"], "Partial")
        queue = list(wb["Accuracy Review Queue"].iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(queue), 8)
        self.assertEqual(sum(1 for r in queue if r[4] == "Not read"), 0)
        chrome = list(wb["Chrome Page Check"].iter_rows(min_row=2, values_only=True))
        self.assertEqual({r[0] for r in chrome}, {"Condition", "Service", "Blog"})
        self.assertIn("Author: Yes", chrome[0][2])

    def test_build_without_claims(self):
        out = self.d / "plain.xlsx"
        run("build", *self.common(), "--external", self.f["external.csv"], "--chrome", self.f["chrome.tsv"], "--out", out)
        wb = load_workbook(out)
        queue = list(wb["Accuracy Review Queue"].iter_rows(min_row=2, values_only=True))
        self.assertTrue(all(r[4] == "Not read" for r in queue))

    def test_build_stops_without_chrome_check_for_every_type(self):
        import csv
        with open(self.f["chrome.tsv"], encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh, delimiter="\t"))
        short = self.d / "short_chrome.tsv"
        with open(short, "w", encoding="utf-8", newline="") as fh:
            csv.writer(fh, delimiter="\t").writerows(rows[:3])  # header + Condition + Service
        p = run("build", *self.common(), "--external", self.f["external.csv"], "--chrome", short, "--out", self.d / "y.xlsx", check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("Claude in Chrome check has no page for", p.stdout + p.stderr)

    def test_build_stops_without_external_export(self):
        p = run("build", *self.common(), "--chrome", self.f["chrome.tsv"], "--out", self.d / "x.xlsx", check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("list crawl export", p.stdout + p.stderr)

    def test_stops_on_wrong_body_column(self):
        cfg = json.loads(self.f["config.json"].read_text())
        cfg["columns"]["body"] = "Nope"
        bad = self.d / "bad.json"
        bad.write_text(json.dumps(cfg))
        p = run("preflight", "--config", bad, "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"], "--out", self.d / "w", check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("no such column", p.stdout + p.stderr)

    def test_stops_when_every_body_is_empty(self):
        import csv
        with open(self.f["crawl.csv"], encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        head = rows[0]
        bi = head.index("Body 1")
        for r in rows[1:]:
            r[bi] = ""
        empty = self.d / "empty.csv"
        with open(empty, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(rows)
        p = run("preflight", "--config", self.f["config.json"], "--crawl", empty, "--outlinks", self.f["outlinks.csv"], "--out", self.d / "w2", check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("Body text is empty on every page", p.stdout + p.stderr)

    def test_stops_without_external_links(self):
        import csv
        with open(self.f["outlinks.csv"], encoding="utf-8") as fh:
            rows = [r for r in csv.reader(fh) if r[2].startswith(SITE) or r[0] == "Type"]
        none = self.d / "none.csv"
        with open(none, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(rows)
        p = run("preflight", "--config", self.f["config.json"], "--crawl", self.f["crawl.csv"], "--outlinks", none, "--out", self.d / "w3", check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("external link crawling was off", p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
