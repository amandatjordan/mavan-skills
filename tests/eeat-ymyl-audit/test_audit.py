"""eeat-ymyl-audit audit.py on a small made-up clinic (fixture.py).

Run from the repo root:  python3 -m unittest discover -s tests/eeat-ymyl-audit -v
"""
import csv
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
        self.assertIn("status codes are not in yet", p.stdout)
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
        flags = {r[2]: r[8] for r in links}
        self.assertIn("Dead link", flags["https://health-agency.example/high-blood-pressure"])
        self.assertIn("No shared words", flags["https://best-supplements.example/blood-sugar-support"])
        self.assertIn("Check manually", flags["https://blocked-journal.example/paper"])
        self.assertNotIn("Dead link", flags["https://blocked-journal.example/paper"])
        self.assertFalse(flags["https://health-agency.example/"])  # a homepage link or redirect is not flagged
        match = {r[2]: r[7] for r in links}
        self.assertEqual({r[2]: r[6] for r in links}["https://diabetes-assoc.example/standards-of-care"], "Title and H1")
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
        self.assertIn("status codes is missing", p.stdout + p.stderr)

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



class PageTypeLabels(unittest.TestCase):
    """Page types from a label column in the crawl export or from an IA / prune workbook, and Sitebulb's "Not Found"."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.d = Path(cls.tmp.name)
        cls.f = fixture.make(cls.d)
        with open(cls.f["crawl.csv"], newline="", encoding="utf-8") as fh:
            cls.rows = list(csv.DictReader(fh))
        cls.labels = {"/conditions/": "Concern", "/services/": "Service Page", "/blog/": "Blog Post"}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def label(self, url):
        return next((v for k, v in self.labels.items() if k in url), "Other")

    def config(self, name, source, labels=True):
        cfg = json.loads(json.dumps(fixture.CONFIG))
        cfg["page_type_source"] = source
        cfg["page_types"] = [{"name": "Condition", "labels": ["Concern"]}, {"name": "Service", "labels": ["Service Page"]},
                             {"name": "Blog", "labels": ["Blog Post"]}]
        path = self.d / name
        path.write_text(json.dumps(cfg))
        return path

    def write_crawl(self, name, extra=None, change=None):
        rows = [dict(r) for r in self.rows]
        for r in rows:
            if extra:
                r["Page Type"] = self.label(r["Address"])
            if change:
                change(r)
        path = self.d / name
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        return path

    def test_label_column_in_crawl_export(self):
        crawl = self.write_crawl("crawl_labels.csv", extra=True)
        cfg = self.config("cfg_col.json", {"column": "Page Type"})
        p = run("preflight", "--config", cfg, "--crawl", crawl, "--outlinks", self.f["outlinks.csv"], "--out", self.d / "w1")
        self.assertIn("Pages per page type: Condition 3, Service 3, Blog 2", p.stdout)
        self.assertIn("Page type labels not in the audit (left out): Other", p.stdout)

    def test_labels_from_workbook_file_without_scheme(self):
        types = self.d / "ia.csv"
        with open(types, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["URL", "Page Type"])
            for r in self.rows:
                w.writerow([r["Address"].split("://", 1)[1].replace("www.", "").rstrip("/"), self.label(r["Address"])])
        cfg = self.config("cfg_file.json", {"file": str(types), "url_column": "URL", "type_column": "Page Type"})
        p = run("preflight", "--config", cfg, "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"], "--out", self.d / "w2")
        self.assertIn("Pages per page type: Condition 3, Service 3, Blog 2", p.stdout)

    def test_sitebulb_not_found_counts_as_empty(self):
        def nf(r):
            for c in ("Author 1", "Reviewer 1"):
                if not r[c].strip():
                    r[c] = "Not Found"
        crawl = self.write_crawl("crawl_nf.csv", change=nf)
        p = run("preflight", "--config", self.f["config.json"], "--crawl", crawl, "--outlinks", self.f["outlinks.csv"],
                "--external", self.f["external.csv"], "--out", self.d / "w3")
        self.assertIn("Author is empty on 4 of 8 pages", p.stdout)

    def test_sitebulb_numbered_match_columns_are_joined(self):
        def split(r):
            words = r["Body 1"].split()
            half = len(words) // 2
            r["Body 1"], r["Body 2"], r["Body 3"] = " ".join(words[:half]), " ".join(words[half:]), "Not Set"
        crawl = self.write_crawl("crawl_split.csv", change=split)
        cfg = json.loads(self.f["config.json"].read_text() if hasattr(self.f["config.json"], "read_text") else open(self.f["config.json"]).read())
        cfg["columns"]["body"] = "Body *"
        path = self.d / "cfg_split.json"
        path.write_text(json.dumps(cfg))
        a = run("queue", "--config", self.f["config.json"], "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"],
                "--external", self.f["external.csv"], "--out", self.d / "q1").stdout
        b = run("queue", "--config", path, "--crawl", crawl, "--outlinks", self.f["outlinks.csv"],
                "--external", self.f["external.csv"], "--out", self.d / "q2").stdout
        self.assertEqual(a, b.replace(str(self.d / "q2"), str(self.d / "q1")))
        self.assertNotIn("Not Set", (self.d / "q2/text/001.txt").read_text())

    def test_anchor_compared_with_url_when_no_title_or_h1(self):
        ext = self.d / "ext_status_only.csv"
        with open(self.f["external.csv"], newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        ucol = next(c for c in rows[0] if c.lower() in ("address", "url"))
        scol = next(c for c in rows[0] if "status" in c.lower() and "code" in c.lower())
        with open(ext, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["URL", "HTTP Status Code"])
            for r in rows:
                w.writerow([r[ucol], r[scol]])
        out = self.d / "audit_url.xlsx"
        p = run("build", "--config", self.f["config.json"], "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"],
                "--external", ext, "--claims", self.f["claims.tsv"], "--chrome", self.f["chrome.tsv"], "--out", out)
        self.assertNotIn("FAIL", p.stdout)
        links = list(load_workbook(out)["External Links"].iter_rows(min_row=2, values_only=True))
        self.assertTrue(all(r[6] == "URL" for r in links))
        by = {r[2]: r for r in links}
        self.assertIn("No shared words", by["https://best-supplements.example/blood-sugar-support"][8] or "")
        self.assertIn("Dead link", by["https://health-agency.example/high-blood-pressure"][8])

    def test_url_helpers(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import audit
        self.assertEqual(audit.url_words("https://pubmed.ncbi.nlm.nih.gov/18462427/", path_only=True), "")
        self.assertIn("compounding", audit.url_words("https://www.fda.gov/drugs/human-drug-compounding/q-and-a"))
        self.assertEqual(audit.schema_types("{'@type':'Organization'} {'@type':'FAQPage','mainEntity':[{'@type':'Question'}]}"),
                         "Organization, FAQPage")
        self.assertIn(405, audit.BLOCKED)

    def test_page_type_without_paths_needs_a_source(self):
        cfg = json.loads(json.dumps(fixture.CONFIG))
        cfg["page_types"].append({"name": "Area"})
        path = self.d / "cfg_bad.json"
        path.write_text(json.dumps(cfg))
        p = run("preflight", "--config", path, "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"], "--out", self.d / "w4", check=False)
        self.assertIn("needs a name, and paths unless page_type_source labels the pages", p.stdout)

if __name__ == "__main__":
    unittest.main()
