---
name: new-site-keyword-research
description: For a brand-new site, turn the client's most important services, products or devices and (optionally) top concerns into the pages to build and the keywords each should target, using the bundled Service Taxonomy. Says which items get their own page and which are a section on a parent page, and which pages should link to each other. Use for new site keyword research, planning pages for a site with no site yet, or "what pages and keywords does a new site need".
---

# New site keyword research (Mavan)

One question for a business building a **new site**: given the services, products and devices it cares about most, which pages should the site have and which keywords should each page target? The answer comes from the bundled Service Taxonomy (v5.1), which already holds about 10,000 keywords mapped to Category > Service > Sub-Service > Brand / Device, plus Concerns. A separate skill will later turn this plan and the blog taxonomy into a content roadmap; this skill stops at pages, keywords and internal links.

Work only from what the person types in and the bundled taxonomy. **Never visit a live site, and use no Composio tool, DataForSEO, Semrush, Ahrefs export or other connector.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person and explaining why. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Every count, join and cutoff is done by `scripts/research.py`; never type or estimate a number. What each rule means is in [references/rules.md](references/rules.md).

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). The script needs Python 3 with pandas and openpyxl. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## Volumes are national and taxonomy-level

Tell the person this in Step 1, and keep it in the Read Me and the final reply. Every volume in this skill is **national** search volume taken from the taxonomy's keyword list, which was built from what competitors rank for, so many keywords carry a city name. Use volumes to rank pages and sections against each other. They are not demand for the client's market and not a traffic forecast. Volumes are never added together: the script uses the highest keyword on each row, because many keywords are the same search worded differently.

## Step 1: Ask for the inputs

Ask for all of this in **one** message, before doing anything else. Say the volume caveat above in the same message. Do not offer menus of options.

| Input | Required? | Notes |
| --- | --- | --- |
| Most important **services** | Required | Treatments, in the client's words ("Botox", "lip filler", "tummy tuck", "laser hair removal") |
| **Products / devices / brands** | Required (the person can say there are none) | Named products or machines the client uses or plans to buy ("Juvéderm Voluma", "Emsculpt Neo", "CoolSculpting") |
| **Top concerns** to address | Optional, up to 5 | Problems patients search for ("double chin", "acne scars"). A new site gets very few concern pages, so suggest up to 5 and accept none |
| Client name | Optional | Names the workbook |

Dental is handled with **no minimum volume**: every dental service, sub-service, brand and concern the client lists gets its own page. The taxonomy has keyword data for dental concerns only, so other dental rows come out with no keywords and a note to research volume separately; tell the person this when they list dental services.

Done when the person has given services and products (or said there are none) and said whether they want concerns.

## Step 2: Match to the taxonomy

```
python $SKILL/scripts/research.py match --services "A; B; C" --products "D; E" [--concerns "F; G"] --out work
```

Separate items with semicolons. It matches each typed item to the taxonomy by name, then by the taxonomy's match terms (using the most specific level that matches), and writes `work/selection.tsv` with one row per item and a `status` (ok, review, none). It prints every row that is not ok.

Done when `work/selection.tsv` exists.

## Step 3: Review every match

Read `work/selection.tsv`. Correct `level`, `service`, `sub_service`, `brand_device` and `concern` in place so they are the **exact taxonomy names** (the `candidates` column lists what matched). Check every row, ok ones included, since match terms can be loose. In short:
- A product or device is a **Brand / Device** row; a treatment is a **Service** or **Sub-Service** row; a problem is a **Concern** row. Name each for what it is (Botox is a Brand / Device under Neurotoxin, never "Neurotoxin").
- One typed item that names two things ("Juvéderm lip filler") becomes two rows.
- A row with no match stays with `level` blank. Ask the person what it is in **one** message for all such rows, or leave it out. Never invent a taxonomy name.

Done when every row is either a valid taxonomy item or deliberately blank.

## Step 4: Build

```
python $SKILL/scripts/research.py build --selection work/selection.tsv --client "CLIENT" --out CLIENT_new_site_keyword_research.xlsx
```

If it stops on selection rows, fix each listed row and run again.

Done when every check prints PASS. Printed warnings (more than 5 concerns, a concern whose services are not on the plan) go in the reply.

## Step 5: Check

- Open the Pages tab: each "Own page" row has a primary keyword with a volume, and each "Section on..." row names a parent page that exists.
- Pick 3 rows and compare their primary keyword and volume to the taxonomy's All Keywords tab (filter on the Service, Sub-Service or Brand / Device).
- Pick 3 rows with an Internal links out entry and confirm the links follow the Internal links rules in the Read Me (a link to a suggested, unconfirmed page carries the "only if the client offers it" tag).
- Read the Not in the plan tab: every typed item the person gave is either on the Pages tab or listed there with a reason.

Done when all four hold.

## Step 6: Report

Send the workbook and reply in a few sentences: how many own pages and how many sections, the services with the highest keyword volume, anything on Not in the plan and why, how many rows have a blank Client offers it? for the client to answer (the SEO asks the client; a No drops the row), any warning, and the volume caveat (national, taxonomy-level, relative not absolute). Name any typed item the taxonomy does not have, for the `service-taxonomy.xlsx` pull request. Practice-specific package or program names never go in the taxonomy.

## Workbook

Tabs, in this order: **Pages**, Keywords, Not in the plan, Read Me. Everything a person works from is on Pages, so nothing that needs human input hides on a later tab.
- **Pages**: one row per service, sub-service, brand / device and concern. Columns: Own page or Section on a named parent page, why, **Client offers it? (Yes / No)**, where the row came from (listed by the client, parent of a listed item, or suggested from the taxonomy), primary keyword with volume, difficulty and CPC, related keywords, sections searchers look for, what to mention as a section, **Internal links out (priority)**, and **Anchor text (SEO fills in)**. Client offers it? is filled with Yes for listed items and parents of listed items, and left blank (yellow) for the sub-services and brands the client did not list but that have real volume; the SEO asks the client and fills in Yes or No. Anchor text is left blank on purpose; this skill never suggests it.
- **Keywords**: every keyword with its target page and modifier.
- **Not in the plan**: not-approved or discontinued items, and items with no match.
- **Read Me**: how to read the workbook, the rules, and the volume caveat.
