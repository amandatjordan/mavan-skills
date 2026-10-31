"""service-gap-audit build.py on a small made-up site with non-standard URL paths.

Run from the repo root:  python3 -m unittest discover -s tests/service-gap-audit -v
"""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins/mavan-seo/skills/service-gap-audit/scripts/build.py"
TAXONOMY = ROOT / "plugins/mavan-seo/skills/service-gap-audit/references/service-taxonomy.xlsx"
SITE = "https://example-medspa.com"

# Sitebulb-style export with no H2 columns. Paths deliberately avoid /services/ and /blog/.
HEADER = ["URL", "HTTP Status Code", "Indexable Status", "Title", "Meta Description", "H1", "No. Content Words"]
PAGES = [
    # path, status, indexable, title, meta, h1, words, type, node, city
    ("/", 200, "Indexable", "Example Med Spa | Tampa", "", "Med spa in Tampa", 400, "Utility", "", ""),
    ("/treatments/botox-tampa", 200, "Canonicalized", "Botox in Tampa | Example", "", "Botox in Tampa", 1500, "Service", "Botox", "tampa"),
    ("/treatments/botox-tampa/", 301, "", "", "", "", 0, None, None, None),
    ("/treatments/microneedling-skinpen", 200, "Indexable", "SkinPen Microneedling | Example", "", "SkinPen", 900, "Service", "SkinPen", ""),
    ("/treatments/fillers", 200, "Indexable", "Dermal Fillers | Example", "", "Dermal Fillers", 12, "Service", "Dermal Filler", ""),
    ("/treatments/kysse", 200, "Indexable", "Restylane Kysse | Example", "", "Restylane Kysse", 700, "Service", "Restylane Kysse", ""),
    ("/results/lip-filler-1", 200, "Indexable", "Lip filler results", "", "Lip filler", 6, "Gallery", "", ""),
    ("/by-area/body", 200, "Indexable", "Body treatments | Example", "", "Cellulite and body", 300, "Concern", "", ""),
    ("/treatments/emsella-chair", 200, "Indexable", "Emsella Chair | Example", "", "Emsella Chair", 650, "Service", "NEW: Emsella Chair > Sexual Wellness", ""),
]


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


class ServiceGapAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.crawl = root / "crawl.csv"
        with open(cls.crawl, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(HEADER)
            for p in PAGES:
                w.writerow([SITE + p[0], *p[1:7]])
        work = root / "work"
        cls.inspect = run("inspect", "--crawl", str(cls.crawl), "--cities", "Tampa", "--practice", "medspa", "--out", str(work))
        pages = pd.read_csv(work / "pages.tsv", sep="\t", dtype=str, keep_default_na=False, quoting=3)
        fix = {p[0]: p for p in PAGES if p[7]}
        for i, r in pages.iterrows():  # the review step: set every type and node by hand
            p = fix[r["path"]]
            pages.loc[i, ["type", "node", "city"]] = [p[7], p[8], p[9]]
        cls.pages = work / "pages.tsv"
        pages.to_csv(cls.pages, sep="\t", index=False, quoting=3)
        cls.out = root / "audit.xlsx"
        cls.build = run("build", "--crawl", str(cls.crawl), "--pages", str(cls.pages), "--cities", "Tampa",
                        "--practice", "medspa", "--domain", "example-medspa.com", "--out", str(cls.out))
        cls.recs = pd.read_excel(cls.out, "Recommendations", header=1).fillna("")
        cls.why = dict(zip(cls.recs["Service Page Recommended"], cls.recs["Why Recommended"]))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_runs_and_passes_qa(self):
        self.assertEqual(self.inspect.returncode, 0, self.inspect.stderr)
        self.assertEqual(self.build.returncode, 0, self.build.stderr)
        self.assertNotIn("FAIL", self.build.stdout)
        self.assertIn("No H2 columns", self.inspect.stdout + str(pd.read_excel(self.out, "Read Me", header=None).values))

    def test_canonical_loop_without_canonical_column(self):
        self.assertEqual(self.why["Botox (Neurotoxin)"], "Existing page, not indexable")

    def test_thin_service_page(self):
        self.assertEqual(self.why["Dermal Filler"], "Existing page, thin content")

    def test_gallery_proves_lip_filler(self):
        self.assertEqual(self.why["Lip Filler (Dermal Filler)"], "Offered (before & after photos), no page")

    def test_concern_page_proves_cellulite(self):
        self.assertEqual(self.why["Cellulite Treatment"], "Offered (named on a concern page), no page")

    def test_brand_only_names_existing_page(self):
        row = self.recs[self.recs["Service Page Recommended"] == "Microneedling"].iloc[0]
        self.assertEqual(row["Why Recommended"], "Only has a brand/product page")
        self.assertIn("SkinPen: /treatments/microneedling-skinpen", row["Existing Brand / Sub-Service Page(s)"])

    def test_new_device_counts_for_its_service_and_is_listed(self):
        self.assertIn("Emsella Chair", self.build.stdout)
        self.assertNotEqual(self.why.get("Sexual Wellness"), "Confirm with client (no sign it is offered)")

    def test_no_other_market_keywords(self):
        kws = ", ".join(self.recs["Relevant Keywords"]).lower()
        self.assertNotIn("miami", kws)

    def test_taxonomy_is_not_accepted_as_gsc(self):
        r = run("build", "--crawl", str(self.crawl), "--pages", str(self.pages), "--practice", "medspa",
                "--gsc", str(TAXONOMY), "--out", str(Path(self.tmp.name) / "x.xlsx"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not Search Console data", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
