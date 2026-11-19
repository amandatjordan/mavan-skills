"""A small made-up clinic site (https://www.example-clinic.test) for the eeat-ymyl-audit tests and the example workbook.
All names, pages, claims, links and figures are fake. No client data.

Every rule in the skill is hit at least once:
  /conditions/type-2-diabetes   complete page, one link whose anchor shares no words with its destination
  /conditions/hypertension      no reviewer, no updated date, one dead authoritative link
  /conditions/migraine          nothing shown (no author, reviewer, dates, schema), weak source (forum), no credentials
  /services/botox               passes almost everything
  /services/hormone-therapy     no author, mismatched anchor, redirect, link to a homepage
  /services/weight-loss-program a destination that blocks the crawler (403)
  /blog/10-foods-...            affiliate link, no author
  /blog/is-intermittent-...     only citation is dead, no author, no dates
  /providers/ /about/ /contact/ /tag/   match none of the three page types (left out, listed in the preflight warnings)
  /old-page/                    404 (left out)
Footer links to social sites are in the outlinks export and must be ignored (link position Footer).
"""
import csv
import json
from pathlib import Path

SITE = "https://www.example-clinic.test"

CRAWL_HEAD = ["Address", "Status Code", "Indexability", "Word Count", "Body 1", "Author 1", "Reviewer 1", "Published 1", "Updated 1",
              "Schema 1", "Testimonials 1", "Before After 1", "Rating 1"]

PAGES = [  # path, status, indexability, body, author, reviewer, published, updated, schema, testimonials, before_after, rating
    ("/conditions/type-2-diabetes/", 200, "Indexable",
     "Type 2 diabetes affects how the body uses sugar. Reviewed by Sam Reviewer, MD, board-certified in endocrinology. "
     "Standards of care recommend regular glucose checks. Metformin is a common first treatment. Some people say you can reverse diabetes naturally in 30 days.",
     "Dr. Alex Sample", "Sam Reviewer, MD", "2024-02-10", "2025-06-01", "MedicalWebPage; FAQPage", "0", "0", ""),
    ("/conditions/hypertension/", 200, "Indexable",
     "High blood pressure often has no symptoms. Written by Dr. Alex Sample, MD. Government guidance sets 120/80 as normal. Lowering sodium helps most people.",
     "Dr. Alex Sample", "", "2023-09-14", "", "MedicalWebPage", "0", "0", ""),
    ("/conditions/migraine/", 200, "Indexable",
     "Migraines are severe headaches. Coffee always triggers migraines and magnesium cures them. Clinical trials show new drugs prevent attacks.",
     "", "", "", "", "", "0", "0", ""),
    ("/services/botox/", 200, "Indexable",
     "Botox smooths lines between the brows. Dr. Alex Sample, MD, FAAD has 12 years of experience with injectables. The treatment is labeled by the regulator for this use. "
     "See real patient results on our results page.",
     "Dr. Alex Sample", "Sam Reviewer, MD", "2024-05-02", "2025-08-20", "Service; Physician", "1", "1", "4.9 (212)"),
    ("/services/hormone-therapy/", 200, "Indexable",
     "Hormone therapy relieves hot flashes. Studies show hormone therapy is risk free and safe for every woman over 40. Read the menopause guidelines before you decide.",
     "", "", "2022-11-01", "", "Service", "1", "0", "4.8 (97)"),
    ("/services/weight-loss-program/", 200, "Indexable",
     "Our program helps you lose 20 pounds in 30 days. It is clinically proven. Led by Pat Example, NP, with 6 years of experience in weight management.",
     "Pat Example, NP", "", "2024-01-19", "2024-01-19", "Service", "1", "1", "4.7 (140)"),
    ("/blog/10-foods-that-lower-cholesterol/", 200, "Indexable",
     "These ten foods lower LDL cholesterol by 40 percent. Research on cholesterol and diet supports eating more fiber. Try our favorite superfood guide.",
     "", "", "2023-03-08", "", "Article", "0", "0", ""),
    ("/blog/is-intermittent-fasting-safe/", 200, "Indexable",
     "Fasting is safe for everyone. This article explains the schedule most people use and what to expect in the first week.",
     "", "", "", "", "", "0", "0", ""),
    ("/providers/dr-alex-sample/", 200, "Indexable",
     "Dr. Alex Sample, MD, PhD holds three board certifications and has 20 years of experience in family medicine.",
     "Dr. Alex Sample", "Practice Medical Director", "2021-01-10", "2025-09-01", "Physician; Person", "1", "0", "4.9 (310)"),
    ("/about/", 200, "Indexable", "We are a family-run clinic serving the community since 2005.", "", "", "", "", "", "0", "0", ""),
    ("/contact/", 200, "Indexable", "Call us or book online. Open Monday to Friday.", "", "", "", "", "", "0", "0", ""),
    ("/tag/wellness/", 200, "Indexable", "Posts tagged wellness.", "", "", "", "", "", "0", "0", ""),
    ("/old-page/", 404, "Non-Indexable", "", "", "", "", "", "", "", "", ""),
]

LINKS = [  # source path, destination, anchor, status, position
    ("/conditions/type-2-diabetes/", "https://diabetes-assoc.example/standards-of-care", "ADA treatment standards", 200, "Content"),
    ("/conditions/type-2-diabetes/", "https://health-agency.example/metformin", "metformin overview", 200, "Content"),
    ("/conditions/type-2-diabetes/", "https://best-supplements.example/blood-sugar-support", "reverse diabetes naturally", 200, "Content"),
    ("/conditions/hypertension/", "https://health-agency.example/high-blood-pressure", "CDC blood pressure guidance", 404, "Content"),
    ("/conditions/hypertension/", "https://nutrition-univ.example/sodium-and-health", "sodium intake", 200, "Content"),
    ("/conditions/migraine/", "https://forum.example/thread/12345", "migraine triggers", 200, "Content"),
    ("/conditions/migraine/", "https://journal-medicine.example/articles/migraine-cgrp", "CGRP migraine prevention study", 200, "Content"),
    ("/services/botox/", "https://health-agency.example/botulinum-toxin-labeling", "FDA labeling", 200, "Content"),
    ("/services/botox/", "https://competitor-clinic.example/botox", "Botox results", 200, "Content"),
    ("/services/hormone-therapy/", "https://wellness-blog.example/hrt-benefits", "risk free hormone therapy", 200, "Content"),
    ("/services/hormone-therapy/", "https://journal-medicine.example/menopause-position", "menopause guidelines", 301, "Content"),
    ("/services/hormone-therapy/", "https://health-agency.example/", "read more", 200, "Content"),
    ("/services/weight-loss-program/", "https://blocked-journal.example/paper", "program results study", 403, "Content"),
    ("/blog/10-foods-that-lower-cholesterol/", "https://nutrition-univ.example/cholesterol-and-diet", "research on cholesterol", 200, "Content"),
    ("/blog/10-foods-that-lower-cholesterol/", "https://affiliate-store.example/superfoods", "superfood guide", 200, "Content"),
    ("/blog/is-intermittent-fasting-safe/", "https://dead-site.example/fasting-study", "this article", 404, "Content"),
]

EXTERNAL = [  # address, status, title, h1
    ("https://diabetes-assoc.example/standards-of-care", 200, "Standards of Care in Diabetes", "Standards of Care in Diabetes"),
    ("https://health-agency.example/metformin", 200, "Metformin: Drug Overview", "Metformin Overview"),
    ("https://best-supplements.example/blood-sugar-support", 200, "Top 10 Blood Sugar Supplements", "Blood Sugar Support Supplements"),
    ("https://health-agency.example/high-blood-pressure", 404, "", ""),
    ("https://nutrition-univ.example/sodium-and-health", 200, "Sodium and Health", "Sodium and Health"),
    ("https://forum.example/thread/12345", 200, "Anyone else get migraines after coffee?", "Anyone else get migraines after coffee?"),
    ("https://journal-medicine.example/articles/migraine-cgrp", 200, "CGRP Antagonists in Migraine Prevention", "CGRP Antagonists in Migraine Prevention"),
    ("https://health-agency.example/botulinum-toxin-labeling", 200, "Botulinum Toxin Labeling", "Botulinum Toxin Labeling"),
    ("https://competitor-clinic.example/botox", 200, "Botox Near You | Competitor Clinic", "Botox Injections"),
    ("https://wellness-blog.example/hrt-benefits", 200, "5 Surprising Benefits of HRT", "5 Surprising Benefits of HRT"),
    ("https://journal-medicine.example/menopause-position", 301, "Menopause Position Statement", "Menopause Position Statement"),
    ("https://health-agency.example/", 200, "Health Agency Home", "Welcome"),
    ("https://blocked-journal.example/paper", 403, "", ""),
    ("https://nutrition-univ.example/cholesterol-and-diet", 200, "Cholesterol and Diet", "Cholesterol and Diet"),
    ("https://affiliate-store.example/superfoods", 200, "Buy Superfoods Online", "Superfoods Shop"),
    ("https://dead-site.example/fasting-study", 404, "", ""),
]

CONFIG = {
    "crawler": "screaming-frog",
    "columns": {"url": "Address", "status": "Status Code", "indexability": "Indexability", "body": "Body 1", "author": "Author 1",
                "reviewer": "Reviewer 1", "published": "Published 1", "updated": "Updated 1", "schema": "Schema 1",
                "testimonials": "Testimonials 1", "before_after": "Before After 1", "rating": "Rating 1"},
    "page_types": [
        {"name": "Condition", "paths": ["/conditions/"]},
        {"name": "Service", "paths": ["/services/"]},
        {"name": "Blog", "paths": ["/blog/"]},
    ],
    "content_link_positions": ["Content"],
}

CLAIMS = [  # url path, specific claims?, claims to verify (all fake)
    ("/conditions/type-2-diabetes/", "Yes", '"You can reverse diabetes naturally in 30 days" | "Metformin is a common first treatment"'),
    ("/conditions/hypertension/", "Yes", '"Normal blood pressure is 120/80" | "Lowering sodium helps most people"'),
    ("/conditions/migraine/", "Yes", '"Coffee always triggers migraines" | "Magnesium cures migraines" | "New drugs prevent attacks"'),
    ("/services/botox/", "Yes", '"The treatment is labeled by the regulator for this use"'),
    ("/services/hormone-therapy/", "Yes", '"Hormone therapy is risk free" | "Safe for every woman over 40"'),
    ("/services/weight-loss-program/", "Yes", '"Lose 20 pounds in 30 days" | "Clinically proven"'),
    ("/blog/10-foods-that-lower-cholesterol/", "Yes", '"These foods lower LDL by 40 percent"'),
    ("/blog/is-intermittent-fasting-safe/", "Yes", '"Fasting is safe for everyone"'),
]

CHROME = [  # url path, what a visitor sees, agrees, other opportunities (all fake)
    ("/conditions/type-2-diabetes/", "Author and reviewer names are in a small grey line under the title. No disclaimer that the page is not medical advice. Related-conditions links sit at the bottom.",
     "Yes", "Move the reviewer line above the first paragraph. Add a short not-medical-advice note and a booking button near the top."),
    ("/services/botox/", "Four before and after photos are real patient results with a consent note. The star rating is a widget that loads after the page. The booking button is below three screens of text.",
     "Partly", "The crawl found the rating from the page code, but visitors only see it after a delay. Add a booking button higher up and caption each photo with the treatment and time since."),
    ("/blog/10-foods-that-lower-cholesterol/", "No author, date or reviewer is visible. The superfood link opens a shop with a discount code. Wording is generic and repeats the same sentence structure in each section.",
     "Yes", "Add an author box, a reviewed-by line and a date. Replace the shop link with a primary source. Rewrite the generic sections in the practice's voice."),
]


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def make(d):
    """Write every input file into folder d and return the paths."""
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for path, status, idx, body, *rest in PAGES:
        rows.append([SITE + path, status, idx, len(body.split()), body] + rest)
    write_csv(d / "crawl.csv", CRAWL_HEAD, rows)
    out = []
    for src, dst, anchor, status, pos in LINKS:
        out.append(["Hyperlink", SITE + src, dst, anchor, status, pos])
    for path, *_ in PAGES:  # menu, footer and image links that must not count as citations
        out.append(["Hyperlink", SITE + path, SITE + "/contact/", "Contact", 200, "Navigation"])
        out.append(["Hyperlink", SITE + path, "https://www.social.example/example-clinic", "Follow us", 200, "Footer"])
        out.append(["Image", SITE + path, SITE + "/logo.png", "", 200, "Navigation"])
    write_csv(d / "outlinks.csv", ["Type", "Source", "Destination", "Anchor", "Status Code", "Link Position"], out)
    write_csv(d / "external.csv", ["Address", "Status Code", "Title 1", "H1-1"], EXTERNAL)
    (d / "config.json").write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")
    with open(d / "claims.tsv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["url", "specific_claims", "claims_to_verify"])
        w.writerows([(SITE + p, a, b) for p, a, b in CLAIMS])
    with open(d / "chrome.tsv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["url", "visitor_sees", "agrees", "opportunities"])
        w.writerows([(SITE + p, a, b, c) for p, a, b, c in CHROME])
    return {k: d / k for k in ("crawl.csv", "outlinks.csv", "external.csv", "config.json", "claims.tsv", "chrome.tsv")}
