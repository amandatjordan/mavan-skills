"""IA audit: end to end on a tiny made-up site (no client data): crawl -> analysis -> workbook.

Run from the repo root:  python3 -m unittest discover -s tests/information-architecture-audit -v
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
SK = ROOT / "plugins/mavan-seo/skills/information-architecture-audit/scripts"


def run(script, *args):
    r = subprocess.run([sys.executable, "-I", str(SK / script), *map(str, args)], capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"{script} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def make_site():
    import csv, json, os, openpyxl
    D='https://example-medspa.com'
    pages=[('/',200),('/services/',200),('/services/botox/',200),('/services/filler/',200),('/services/microneedling/',200),
    ('/what-is-botox-and-how-does-it-work/',200),('/botox-aftercare-tips/',200),('/about-us/',200),('/contact/',200),
    ('/old-botox/',301),('/gone-page/',404),('/privacy-policy/',200),('/lip-flip-denver/',200),('/blog/',200),('/blog/first-post/',200),('/services/old/',200)]
    with open('urls.csv','w',newline='') as f:
        w=csv.writer(f);w.writerow(['URL','HTTP Status Code','Indexable Status','Crawl Depth','Title','H1','No. Content Words'])
        for p,s in pages: w.writerow([D+p,s,'Indexable' if s==200 else 'Redirected' if s==301 else 'Client Error',1,p.strip('/') or 'Home',p.strip('/').replace('-',' ') or 'Home',500])
    links=[]
    menu=['/','/services/','/services/botox/','/services/filler/','/services/microneedling/','/about-us/','/contact/','/old-botox/','/lip-flip-denver/','/blog/']
    for p,s in pages:
        if s!=200: continue
        for m in menu: links.append((D+m,m,D+p,'Navigation','div.main-nav > ul > li > a'))
    links += [(D+'/old-botox/','botox',D+'/services/filler/','Content','div.entry > p > a'),
              (D+'/gone-page/','x',D+'/services/botox/','Content','div.entry > p > a'),
              (D+'/botox-aftercare-tips/','botox aftercare',D+'/services/microneedling/','Content','div.entry > p > a'),
              (D+'/what-is-botox-and-how-does-it-work/','b',D+'/services/botox/','Content','div.entry > p > a')]
    with open('links.csv','w',newline='') as f:
        w=csv.writer(f);w.writerow(['Target URL','Anchor Text','Linking URL','Location','CSS Path','Image'])
        for t,a,s,l,c in links: w.writerow([t,a,s,l,c,'False'])
    with open('redirects.csv','w',newline='') as f:
        w=csv.writer(f);w.writerow(['Address','Status Code','Redirect URL']);w.writerow([D+'/old-botox/',301,D+'/services/botox/'])
    gsc=[('/services/botox/','face treatment near me',1,400),('/services/filler/','face treatment near me',1,300),('/services/microneedling/','face treatment near me',1,300),
    ('/services/botox/','botox',20,900),('/what-is-botox-and-how-does-it-work/','botox',1,200),('/botox-aftercare-tips/','botox',0,100),('/services/filler/','filler',5,500)]
    wb=openpyxl.Workbook();ws=wb.active;ws.title='Claude Use This'
    ws.append(['Page','Query','Clicks','Impressions'])
    for p,q,c,i in gsc: ws.append([D+p,q,c,i])
    wb.save('gsc.xlsx')
    # prune workbook (new format)
    pw=openpyxl.Workbook();k=pw.active;k.title='Kept pages'
    k.append(['SEO QA REVIEW banner']);k.append(['Page (SEO: QA this URL)','Page type','Clicks','Impressions','Why','Disagree? Type the change you want (SEO fill in)'])
    k.append([D+'/lip-flip-denver/','Service',1,50,'why',''])
    c=pw.create_sheet('Check page type');c.append(['banner']);c.append(['Page','Page type we guessed','Correct page type (SEO fill in)','Why we guessed'])
    c.append([D+'/botox-aftercare-tips/','Service','Blog Post','Root-level'])
    r=pw.create_sheet('Remove pages');r.append(['banner']);r.append(['Page to remove','Redirect to','Why']);r.append([D+'/services/old/',D+'/services/',''])
    d=pw.create_sheet('All redirects - Handoff to Dev');d.append(['Source URL','Target URL','Regex (0 = no, 1 = yes)','HTTP Code']);d.append([D+'/tag/(.*)',D+'/blog/',1,301]);d.append([D+'/services/old/',D+'/services/',0,301])
    pw.save('prune.xlsx')
    json.dump({"mapping_confirmed":True,"folder_types":{"services":"Service","blog":"Blog"},"blog_folder":"/blog/","service_folder":"/services/"},open('decisions.json','w'))
    json.dump({"client":"Example","domain":"example-medspa.com","city":"Denver, CO","other_cities":[],"brand_terms":["example"],"crawler":"Sitebulb","crawl_date":"2026-10-20"},open('config.json','w'))


def rows(wb, name):
    return [[c for c in r] for r in wb[name].iter_rows(values_only=True)]


class Deliverable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = Path(tempfile.mkdtemp())
        cwd = os.getcwd()
        os.chdir(cls.t)
        try:
            make_site()
            run("prep.py", "--domain", "example-medspa.com", "--urls", "urls.csv", "--links", "links.csv", "--redirects", "redirects.csv", "--out", "work")
            run("prune_import.py", "--workbook", "prune.xlsx", "--domain", "example-medspa.com", "--out", "work")
            Path("work/config.json").write_text(Path("config.json").read_text())
            Path("work/decisions.json").write_text(Path("decisions.json").read_text())
            run("gsc_sheet.py", "build", "--sheet", "gsc.xlsx", "--domain", "example-medspa.com", "--brand", "example",
                "--start", "2026-05-01", "--end", "2026-10-31", "--out", "work/gsc")
            run("analyze.py", "--work", "work", "--past", "work/past.csv", "--prune", "work/prune.csv")
            run("make_xlsx.py", "--work", "work", "--out", "out.xlsx")
        finally:
            os.chdir(cwd)
        cls.wb = openpyxl.load_workbook(cls.t / "out.xlsx")

    def test_tabs_in_order_and_empty_ones_left_out(self):
        self.assertEqual(self.wb.sheetnames, ["Recommendations", "Check page type", "Moves", "All redirects - Handoff to Dev", "Fix links",
                                              "Menu cleanup", "Internal linking opportunities", "README"])

    def test_prune_types_adopted_and_guesses_listed(self):
        guessed = [r[0] for r in rows(self.wb, "Check page type")[2:]]
        self.assertIn("/what-is-botox-and-how-does-it-work/", guessed)       # IA's own guess
        self.assertNotIn("/botox-aftercare-tips/", guessed)                  # the prune's corrected type was adopted
        self.assertNotIn("/lip-flip-denver/", guessed)

    def test_moves_and_dev_tab(self):
        mv = {r[0]: r[1] for r in rows(self.wb, "Moves")[2:]}
        self.assertEqual(mv["https://example-medspa.com/botox-aftercare-tips/"], "https://example-medspa.com/blog/botox-aftercare-tips/")
        self.assertEqual(mv["https://example-medspa.com/lip-flip-denver/"], "https://example-medspa.com/services/lip-flip-denver/")
        dev = rows(self.wb, "All redirects - Handoff to Dev")
        self.assertEqual(dev[0], ["Source URL", "Target URL", "Regex (0 = no, 1 = yes)", "HTTP Code"])   # header row 1, no banner
        self.assertEqual(len(dev) - 1, 3)
        self.assertTrue(all(r[2] == 0 and r[3] == 301 for r in dev[1:]))

    def test_fix_links_follow_to_the_final_url(self):
        fx = {(r[0], r[1]): r[2] for r in rows(self.wb, "Fix links")[2:]}
        self.assertEqual(fx[("/services/filler/", "/old-botox/")], "/services/botox/")
        self.assertEqual(fx[("/services/botox/", "/gone-page/")], "SEO fill in")                    # 404: SEO decides
        self.assertEqual(fx[("/services/microneedling/", "/botox-aftercare-tips/")], "/blog/botox-aftercare-tips/")   # moved page
        self.assertIn(("Main menu", "/old-botox/"), fx)                                              # sitewide link is one row

    def test_menu_is_a_recommended_removal_list(self):
        m = rows(self.wb, "Menu cleanup")
        self.assertIn("recommends removing", m[0][0])
        items = [r[0] for r in m[2:]]
        self.assertNotIn("/services/", items)       # hub stays
        self.assertNotIn("/contact/", items)        # core company page stays
        self.assertIn("/services/botox/", items)
        self.assertTrue(all(r[2] == "SEO fill in" for r in m[2:]))

    def test_internal_linking_one_link_from_per_row_with_hub_to_fill(self):
        li = rows(self.wb, "Internal linking opportunities")[2:]
        self.assertEqual(len({r[0] for r in li}), len(li))
        self.assertTrue(all(r[1] == "SEO fill in" and r[3] == "SEO fill in" for r in li))            # no page owns the topic

    def test_recommendations_counts_match_tabs(self):
        rec = {r[0]: r[3] for r in rows(self.wb, "Recommendations")[1:]}
        self.assertEqual(rec["Blog posts and service pages that sit outside their folder"], 3)


if __name__ == "__main__":
    unittest.main()
