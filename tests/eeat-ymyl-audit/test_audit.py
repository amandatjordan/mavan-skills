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
        self.assertIn("match no page type", p.stdout)
        self.assertIn("did not return 200", p.stdout)
        self.assertIn("blocked the crawler", p.stdout)
        self.assertIn("Author is empty", p.stdout)

    def test_reps_one_per_page_type(self):
        p = run("reps", *self.common(), "--external", self.f["external.csv"])
        types = [l.split("\t")[0] for l in p.stdout.strip().splitlines()]
        self.assertEqual(types, ["Condition", "Service", "Blog", "Provider", "Company"])

    def test_queue_scopes_and_text_files(self):
        out = self.d / "work3"
        p = run("queue", *self.common(), "--external", self.f["external.csv"], "--out", out)
        self.assertIn("scope failed: 7 pages", p.stdout)
        self.assertIn("scope all-high: 8 pages", p.stdout)
        self.assertEqual(len(list((out / "text").glob("*.txt"))), 7)
        first = (out / "text/001.txt").read_text()
        self.assertIn("External citations on the page:", first)

    def test_build_workbook(self):
        out = self.d / "audit.xlsx"
        p = run("build", *self.common(), "--external", self.f["external.csv"], "--claims", self.f["claims.tsv"],
                "--chrome", self.f["chrome.tsv"], "--out", out)
        self.assertNotIn("FAIL", p.stdout)
        wb = load_workbook(out)
        self.assertEqual(wb.sheetnames, ["Recommendations", "Page Review", "External Links", "Accuracy Review Queue", "Chrome Page Check"])
        rows = {r[0]: r for r in wb["Page Review"].iter_rows(min_row=2, values_only=True)}
        self.assertEqual(len(rows), 11)  # 404 and tag page left out
        mig = rows[SITE + "/conditions/migraine/"]
        self.assertEqual(mig[3], "No")           # author
        self.assertEqual(mig[10], 2)             # citations
        self.assertEqual(mig[13], 1)             # only the forum link is flagged (weak source)
        self.assertEqual(rows[SITE + "/about/"][19], "Not scored")
        self.assertEqual(rows[SITE + "/providers/dr-alex-sample/"][12], "No citations")
        self.assertEqual(rows[SITE + "/services/botox/"][6], "12 years of experience")
        links = list(wb["External Links"].iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(links), len(fixture.LINKS))
        flags = {r[2]: r[8] for r in links}
        self.assertIn("Dead link", flags["https://health-agency.example/high-blood-pressure"])
        self.assertIn("No shared words", flags["https://best-supplements.example/blood-sugar-support"])
        self.assertIn("Goes to homepage", flags["https://health-agency.example/"])
        self.assertIn("Redirect", flags["https://journal-medicine.example/menopause-position"])
        self.assertIn("Check manually", flags["https://blocked-journal.example/paper"])
        self.assertNotIn("Dead link", flags["https://blocked-journal.example/paper"])
        self.assertIn("Weak source", flags["https://forum.example/thread/12345"])
        generic = {r[2]: r[7] for r in links}
        self.assertEqual(generic["https://health-agency.example/"], "Generic anchor")
        queue = list(wb["Accuracy Review Queue"].iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(queue), 7)  # botox passes every check
        self.assertTrue(all(r[4] in ("Yes", "No", "Not read") for r in queue))
        self.assertEqual(sum(1 for r in queue if r[4] == "Not read"), 0)

    def test_build_without_optional_inputs(self):
        out = self.d / "plain.xlsx"
        run("build", *self.common(), "--external", self.f["external.csv"], "--out", out)
        wb = load_workbook(out)
        self.assertEqual(wb.sheetnames, ["Recommendations", "Page Review", "External Links", "Accuracy Review Queue"])

    def test_build_stops_without_external_export(self):
        p = run("build", *self.common(), "--out", self.d / "x.xlsx", check=False)
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
