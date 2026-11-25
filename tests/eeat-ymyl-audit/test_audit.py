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
        return ["--config", f["config.json"], "--crawl", f["crawl.csv"], "--outlinks", f["outlinks.csv"], "--checks", f["checks.tsv"]]

    def test_preflight_part_one_writes_external_list(self):
        out = self.d / "work1"
        p = run("preflight", *self.common(), "--out", out)
        urls = (out / "external_urls.txt").read_text().split()
        self.assertEqual(len(urls), len(fixture.LINKS) - 4)  # the booking, Google, address and phone links are not listed
        self.assertFalse(any("social.example" in u for u in urls), "footer links must not be listed")
        self.assertFalse(any("podium.com" in u or "goo.gl" in u for u in urls))
        self.assertIn("4 external content links left out because they are not citations", p.stdout)
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
        self.assertIn("Reviewer who is a medical professional: Yes; External link to a credible medical source: Yes", p.stdout)

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
        self.assertEqual(wb.sheetnames, ["Recommendations", "All Pages", "External Links Needed", "External Link Issues",
                                         "Claims Needing Verification", "Sample Page Check"])
        head = [c.value for c in wb["All Pages"][1]]
        rows = {r[0]: dict(zip(head, r)) for r in wb["All Pages"].iter_rows(min_row=2, values_only=True)}
        self.assertEqual(len(rows), 8)  # providers, about, contact, tag page and the 404 are left out
        blog = rows[SITE + "/blog/is-intermittent-fasting-safe/"]
        self.assertEqual(blog["External link to a credible medical source"], "Missing")
        self.assertEqual(rows[SITE + "/conditions/migraine/"]["Author shown"], "Not required")  # authors are for blogs only
        self.assertEqual(rows[SITE + "/conditions/migraine/"]["Published date shown"], "Not required")
        self.assertEqual(rows[SITE + "/services/botox/"]["Years of experience"], "12 years of experience")
        self.assertEqual(rows[SITE + "/services/botox/"]["Before/after photos"], "Yes")
        needed = [r[0] for r in wb["External Links Needed"].iter_rows(min_row=2, values_only=True)]
        self.assertEqual(needed, [SITE + "/blog/is-intermittent-fasting-safe/"])
        self.assertEqual([c.value for c in wb["External Links Needed"][1]],
                         ["URL", "Page type", "External links on the page now (not credible)", "Source to link to",
                          "Anchor text on the page", "Notes", "Completion handoff"])  # no claims column
        self.assertEqual(wb["External Links Needed"].cell(2, 7).value, "Dev")
        self.assertNotIn("booking.podium.com", wb["External Links Needed"].cell(2, 3).value)
        issues = {r[2]: r for r in wb["External Link Issues"].iter_rows(min_row=2, values_only=True)}
        self.assertIn("Dead link", issues["https://health-agency.example/high-blood-pressure"][4])
        self.assertIn("No shared words", issues["https://best-supplements.example/blood-sugar-support"][4])
        self.assertIn("Check manually", issues["https://blocked-journal.example/paper"][4])
        self.assertNotIn("https://health-agency.example/", issues)  # a homepage link with a generic anchor is not an issue
        for dest in ("https://booking.podium.com/clinic/123", "https://maps.app.goo.gl/abc123",
                     "https://directions.example/clinic", "https://callnow.example/clinic"):
            self.assertNotIn(dest, issues)  # booking, Google, address and phone links are never citations
        claims = list(wb["Claims Needing Verification"].iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(claims), sum(len(c[2].split("|")) for c in fixture.CLAIMS))  # one row per claim
        self.assertEqual(claims[0][7], "Content")
        rec = [r for r in wb["Recommendations"].iter_rows(values_only=True) if r and r[0] in ("High", "Medium", "Low")]
        self.assertTrue(any("1 of 2 blog posts have no external link" in (r[1] or "") for r in rec))
        self.assertTrue(all(r[5] in ("Dev", "Content") for r in rec))
        chrome = list(wb["Sample Page Check"].iter_rows(min_row=2, values_only=True))
        self.assertEqual({r[0] for r in chrome}, {"Condition", "Service", "Blog"})

    def test_build_without_claims(self):
        out = self.d / "plain.xlsx"
        run("build", *self.common(), "--external", self.f["external.csv"], "--chrome", self.f["chrome.tsv"], "--out", out)
        claims = list(load_workbook(out)["Claims Needing Verification"].iter_rows(min_row=2, values_only=True))
        self.assertTrue(claims and all(r[2] == "Not read" for r in claims))

    def test_build_stops_without_chrome_check_for_every_type(self):
        import csv
        with open(self.f["chrome.tsv"], encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh, delimiter="\t"))
        short = self.d / "short_chrome.tsv"
        with open(short, "w", encoding="utf-8", newline="") as fh:
            csv.writer(fh, delimiter="\t").writerows(rows[:3])  # header + Condition + Service
        p = run("build", *self.common(), "--external", self.f["external.csv"], "--chrome", short, "--out", self.d / "y.xlsx", check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("sample page check has no page for", p.stdout + p.stderr)

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
        a = run("queue", "--config", self.f["config.json"], "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"], "--checks", self.f["checks.tsv"],
                "--external", self.f["external.csv"], "--out", self.d / "q1").stdout
        b = run("queue", "--config", path, "--crawl", crawl, "--outlinks", self.f["outlinks.csv"], "--checks", self.f["checks.tsv"],
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
        p = run("build", "--config", self.f["config.json"], "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"], "--checks", self.f["checks.tsv"],
                "--external", ext, "--claims", self.f["claims.tsv"], "--chrome", self.f["chrome.tsv"], "--out", out)
        self.assertNotIn("FAIL", p.stdout)
        links = list(load_workbook(out)["External Link Issues"].iter_rows(min_row=2, values_only=True))
        self.assertTrue(links and all(r[5] == "URL" for r in links))
        by = {r[2]: r for r in links}
        self.assertIn("No shared words", by["https://best-supplements.example/blood-sugar-support"][4])
        self.assertIn("Dead link", by["https://health-agency.example/high-blood-pressure"][4])

    def test_url_helpers(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import audit
        self.assertEqual(audit.url_words("https://pubmed.ncbi.nlm.nih.gov/18462427/", path_only=True), "")
        self.assertIn("compounding", audit.url_words("https://www.fda.gov/drugs/human-drug-compounding/q-and-a"))
        self.assertEqual(audit.schema_types("{'@type':'Organization'} {'@type':'FAQPage','mainEntity':[{'@type':'Question'}]}"),
                         "Organization, FAQPage")
        self.assertIn(405, audit.BLOCKED)

    def test_build_stops_when_an_empty_extraction_is_not_checked_in_chrome(self):
        p = run("build", "--config", self.f["config.json"], "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"],
                "--external", self.f["external.csv"], "--chrome", self.f["chrome.tsv"], "--out", self.d / "x.xlsx", check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("CHECK: Testimonials 1 is empty on all 3 Condition pages", p.stdout)
        q = run("preflight", "--config", self.f["config.json"], "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"],
                "--external", self.f["external.csv"], "--checks", self.f["checks.tsv"], "--out", self.d / "wc")
        self.assertIn("confirmed absent in Claude in Chrome", q.stdout)
        self.assertNotIn("CHECK:", q.stdout)

    def test_body_markers_and_checks_only_for_required(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import audit
        found = audit.body_found("Botox FAQs Is it safe? ★★★★★", {"body_markers": {"faq": r"\bFAQs?\b", "rating": "★"}})
        self.assertEqual(found("faq", None), "Found in body text")
        self.assertEqual(found("rating", ""), "Found in body text")
        self.assertIsNone(found("before_after", None))
        self.assertFalse(audit.required_for("before_after", "blog"))
        self.assertTrue(audit.required_for("before_after", "service"))
        self.assertTrue(audit.required_for("reviewer", "condition"))
        self.assertFalse(audit.required_for("published", "service"))

    def test_claims_sample_and_follow_up_review(self):
        common = ["--config", self.f["config.json"], "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"],
                  "--checks", self.f["checks.tsv"], "--external", self.f["external.csv"]]
        q1 = run("queue", *common, "--out", self.d / "s1", "--sample-per-type", "1").stdout
        q2 = run("queue", *common, "--out", self.d / "s2", "--sample-per-type", "1").stdout
        self.assertIn("Queue: 3 pages", q1)
        rows = (self.d / "s1/queue.tsv").read_text().splitlines()[1:]
        self.assertEqual(rows, (self.d / "s2/queue.tsv").read_text().splitlines()[1:])  # the same pages every run
        sampled = [r.split("\t")[1] for r in rows]
        claims = self.d / "claims_two.tsv"
        with open(claims, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["url", "specific_claims", "claims_to_verify"])
            for u in sampled:
                w.writerow([u, "Yes", "claim one | claim two"])
        cfg = json.loads(Path(self.f["config.json"]).read_text())
        cfg["credible_domains"] = []  # no source counts as credible, so every sampled page is unsourced
        nocred = self.d / "cfg_nocred.json"
        nocred.write_text(json.dumps(cfg))
        args = ["--config", nocred] + common[2:]
        out = self.d / "sample.xlsx"
        run("build", *args, "--chrome", self.f["chrome.tsv"], "--claims", claims, "--sample-per-type", "1", "--out", out)
        rec = [r for r in load_workbook(out)["Recommendations"].iter_rows(values_only=True) if r and r[0] in ("High", "Medium", "Low")]
        follow = {r[1].split(" make ")[0]: r for r in rec if "need a closer review for claims" in (r[1] or "")}
        self.assertEqual(set(follow), {"The sampled concern / condition pages", "The sampled blog posts"})  # never services
        self.assertIn("the other 2 concern / condition pages need a closer review", follow["The sampled concern / condition pages"][1])
        self.assertEqual(follow["The sampled blog posts"][5], "Content")
        # with credible sources on the sampled pages, there is no follow-up
        out2 = self.d / "sample2.xlsx"
        run("build", *common, "--chrome", self.f["chrome.tsv"], "--claims", claims, "--sample-per-type", "1", "--out", out2)
        rec2 = [r for r in load_workbook(out2)["Recommendations"].iter_rows(values_only=True) if r and r[0] == "Low"]
        self.assertFalse(any("closer review" in (r[1] or "") for r in rec2))

    def test_page_type_without_paths_needs_a_source(self):
        cfg = json.loads(json.dumps(fixture.CONFIG))
        cfg["page_types"].append({"name": "Area"})
        path = self.d / "cfg_bad.json"
        path.write_text(json.dumps(cfg))
        p = run("preflight", "--config", path, "--crawl", self.f["crawl.csv"], "--outlinks", self.f["outlinks.csv"], "--out", self.d / "w4", check=False)
        self.assertIn("needs a name, and paths unless page_type_source labels the pages", p.stdout)

if __name__ == "__main__":
    unittest.main()
