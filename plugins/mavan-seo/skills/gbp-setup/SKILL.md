---
name: gbp-setup
description: Recommend Google Business Profile categories from what competitors use (Pleper local search exports), list the services and products to add from the new-site content roadmap, and give the full checklist to finish the profile, as a Word document. Use for GBP setup, "what categories should the client's Google Business Profile have", GBP services and products, or a GBP checklist after the new site content roadmap. Also use when the client offers more than one specialty (for example plastic surgery and cosmetic dentistry).
---

# GBP setup (Mavan)

Two outputs. A **Word document** tells the SEO which GBP categories to use, which services and products to add, and everything else to complete the profile. A separate **Excel sheet** holds the title and description for every service and product, ready to paste into the profile. Every recommendation is a draft the SEO must confirm. The document says so at the top.

Work only from uploaded files: the content roadmap workbook and Pleper Search Export files. **Never visit Google or the live site, and use no Composio tool, DataForSEO or other connector.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person and explaining why. If a step is unreliable, expensive or needs workarounds, stop and say so. The script does every count and ranking; never estimate a number by reading. What each rule means is in [references/rules.md](references/rules.md).

`$SKILL` is this skill's folder (the base directory shown when the skill loads). The script needs Python 3 with pandas, openpyxl and python-docx. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## Step 1: Ask for the inputs (preflight request)

Ask for all of this in **one** message.

| Input | Required? | Notes |
| --- | --- | --- |
| Content roadmap workbook | Required | The .xlsx from `new-site-content-roadmap`. The Roadmap tab and, when present, the "Cut for the 50-page cap" tab are read |
| Pleper **Search Export** files (JSON, or CSV with the same headers) | Required | One per priority local search, each labelled with the **specialty** it belongs to (for example "Plastic surgery" or "Cosmetic dentistry"). Three per specialty is the target. A client with two specialties needs exports for each. Offer priority searches built from the roadmap's services plus the location, for the SEO to confirm |
| Client name | Required | Names the document |
| Client's exact GBP business name | Optional | As written in the exports. If it is in them, each recommended category shows as "Has it" or "Missing". Leave out when the client has no profile |

## Step 2: Preflight

```
python $SKILL/scripts/gbp_setup.py preflight --roadmap ROADMAP.xlsx --client "CLIENT" [--business "Exact Name"] \
  --gbp "Specialty|search words=EXPORT.json" [--gbp ...] --out work
```

Read `work/preflight.md`. On NOT READY, send **one** message listing each FAIL and exactly what is needed, then stop. Mention each WARN in the final reply. Done when it says READY.

## Step 3: Count categories and match services

```
python $SKILL/scripts/gbp_setup.py categories (same --roadmap, --gbp and --business options) --out work
```

It prints the top 3 categories for each export and writes `work/service_match.tsv`, one row per Service and Sub-Service on the roadmap, with a blank `category` column. Fill `category` for each service with the **exact name** of one of the printed candidate categories that fits the service, or leave it blank when none fits. Never invent a category and never match a service to a category that does not describe it. A service with no fit is shown in the document as unmatched; that is a finding, not a mistake. Done when every row is either an exact candidate or deliberately blank.

It also writes `work/descriptions.tsv`: one row per service and product, with `title` prefilled from the roadmap and `description` blank. Write both for every row:
- **Services:** description 275 characters at most.
- **Products:** name (the `title`) 45 characters at most, description 750 characters at most. Shorten the name only when the roadmap's name is over 45.
- Use only what the roadmap gives you (the name, its parent page and type) and plain statements about the service. Never invent details about the business (years, awards, prices, locations, equipment), and never promise or imply results, in line with the roadmap skill's blog rule. Write each description so it reads well on its own, since the SEO will edit it.
- Do not count characters by eye. The build stops and lists every row over its limit; rewrite those rows shorter, never cut a sentence off.

## Step 4: Build

```
python $SKILL/scripts/gbp_setup.py build (same options) --client "CLIENT" --match work/service_match.tsv --descriptions work/descriptions.tsv \
  --out "CLIENT GBP Setup Month YYYY.docx" --sheet "CLIENT GBP Services and Products Month YYYY.xlsx"
```

Done when every check prints PASS. If it stops on a character limit, fix those rows in `descriptions.tsv` and run it again.

## Step 5: Check

Render the document and look at it. Confirm:
- The draft notice is at the top and every specialty has a suggested primary (or says why not).
- Pick 3 category rows and compare the counts with the printed per-export lists.
- Every service and product on the roadmap appears once; products are the Brand / Device rows.
- Every competitor category that has no matching service is listed as not recommended, and unmatched services are listed.
- The checklist has all 11 items.
- In the sheet, every service and product has a title and description, the character counts are filled in and none is highlighted red (limits above), and the rows match sections 2 and 3 of the document.

Say you did these checks.

## Step 6: Reply

Send both files, then say in plain language: the suggested primary and recommended categories per specialty, the services with no matching category, the competitor categories left out because no service matches, and any preflight WARN. Remind the person that every category must be confirmed, and that booking and menu / services links depend on the categories chosen.
