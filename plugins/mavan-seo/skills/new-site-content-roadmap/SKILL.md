---
name: new-site-content-roadmap
description: For a brand-new site, turn the new-site keyword research workbook, the new-site keyword gap workbook and the bundled blog taxonomy into the list of pages and blog posts to write content for (50 at most, always including Home and About Us). Asks for the two workbooks and any extra pages that need content (packages, providers, locations, events, financing and so on). Use for a new site content roadmap, "which pages should we write for the new site", or after new site keyword research and the new-site keyword gap.
---

# New site content roadmap (Mavan)

One question for a business building a **new site**: of everything the keyword research and the competitor gap found, which pages and blog posts should we write content for first? The answer is a list of **50 pages at most**. Home, About Us, every extra page the SEO names and every blog post count toward the 50.

Work only from the two workbooks, the bundled blog taxonomy and what the person types in. **Never visit a live site, and use no Composio tool, DataForSEO, Semrush, Ahrefs export or other connector.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person and explaining why. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Every count, rank and cut is done by `scripts/roadmap.py`; never type or estimate a number. What each rule means is in [references/rules.md](references/rules.md).

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). The script needs Python 3 with pandas and openpyxl. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## Pages that are not on this roadmap

Pages the site needs but that need **no content from us** (Contact, Privacy Policy, Terms, Sitemap and similar) are not part of this skill. If the person lists them, say they belong in the information architecture work for the new site and leave them out.

## Volumes are national and taxonomy-level

Volumes in the roadmap come from the research workbook, which takes them from the taxonomy's keyword list, so they are **national** and many keywords carry a city name. They rank pages against each other. They are not demand for the client's market and not a traffic forecast. Say this in the final reply.

## Step 1: Ask for the inputs (preflight request)

Ask for all of this in **one** message, before doing anything else.

| Input | Required? | Notes |
| --- | --- | --- |
| **New site keyword research** workbook | Required | The .xlsx from `new-site-keyword-research`. Its Pages tab needs **Client offers it? (Yes / No)** filled in (only Yes rows are used; blank and No are left out) and, ideally, the yellow **Anchor text for links to this page** column filled in: it becomes "Must appear on page" |
| **New-site keyword gap** workbook | Required | The .xlsx from `new-site-keyword-gap`. Its **Offered by our client** column on Service opportunities should be filled in: only Yes services count |
| **Other pages that need content** | Ask, can be none | Pages we would write that are not in either sheet: packages, provider pages, location pages, events, financing, treatments by area or age, and anything else the person names. Give each a name and, if they can, a type (Package, Provider, Location, Event, Financing, Treatment by area, Treatment by age) |
| Client name | Optional | Names the workbook |

Home and About Us are always added. Do not ask about them. The blog taxonomy is bundled; never ask for it.

Done when both workbooks are attached and the person has given the extra pages or said there are none.

## Step 2: Preflight

```
python $SKILL/scripts/roadmap.py preflight --research RESEARCH.xlsx --gap GAP.xlsx --extras "Bridal packages|Package; Dr Smith|Provider" --out work
```

Pass `--extras` only when there are extras (`Name|Type` separated by semicolons). It checks that each workbook is the right kind, counts blank Offered answers and checks that Home, About Us and the extras fit under 50. Read `work/preflight.md`. On NOT READY, send **one** message listing each FAIL and exactly what is needed, then stop. Mention each WARN in the final reply: gap services whose Offered column is blank are left out of the roadmap. If the person wants those in, they fill in the gap workbook and send it again. Done when it says READY.

## Step 3: Match gap services to research pages

```
python $SKILL/scripts/roadmap.py match --research RESEARCH.xlsx --gap GAP.xlsx --out work
```

It writes `work/gap_match.tsv`, one row per gap service, and prints every row that is not `ok`. The gap workbook's service names are free text the SEO chose (Fillers, botox, NAD+), so each one has to be matched to a page on the research Pages tab. Read **every** row, ok ones included, and correct `page` in place so it is the **exact label** from the research Pages tab, or blank when the service is not on that tab:
- A gap service that is one treatment or product matches the page for that treatment or product (botox -> the Botox brand page). A broad name (Fillers) matches the Service page.
- Two gap services may point to the same page; their numbers are added.
- A service with no page and `offered` = Yes becomes a page of its own: set `level` to Service, Sub-Service, Brand / Device or Concern and fix the name's capitalization. Never invent a research label.
- `offered` can be edited in this file when the person tells you the answer for a blank row. Say you did.
- A service with no page and Offered No or blank is left off the roadmap and is not listed anywhere.

Done when every row is either an exact research page or deliberately blank.

## Step 4: Build

```
python $SKILL/scripts/roadmap.py build --research RESEARCH.xlsx --gap GAP.xlsx --match work/gap_match.tsv --extras "..." --client "CLIENT" --out "CLIENT_new_site_content_roadmap.xlsx"
```

If it stops on a gap service or a page name, fix that row and run again. Done when every check prints PASS. Printed warnings (for example a gap service the client does not offer that is matched to a research page) go in the reply.

## Step 5: Check

- Roadmap tab: Home, About Us and every extra page are at the top, the row count is 50 or fewer, and the rows follow Service, Sub-Service, Brand / Device, Blog, Concern.
- Pick 3 page rows and compare the primary keyword and volume to the research Pages tab.
- Pick 3 gap numbers and compare them to the Service opportunities tab (non-local plus local, of the matched service).
- Pick 2 blog rows and compare the angle to the blog taxonomy's Lookup tab.
- Cut tab (only present when something is over 50): starts with the instruction row, has the same columns as the Roadmap with the reason last, and each cut page is there. Sections are not pages: each one is in "Sections to cover" on its parent page.

Done when all five hold.

## Step 6: Report

Send the workbook. Reply in a few sentences: how many rows by type, what was cut for the 50 cap (the number by group, and which Service pages if any), the extra pages, any warning, that the SEO must check the yellow primary keyword column (a primary keyword is only the highest-volume search for the page and may be a search from someone looking at pictures or reading about a topic, for example "face with wrinkles") and replace it or add keywords, that content must use the "Must appear on page" words (the anchor text other pages link with), that the SEO fills in the yellow priority column and makes the final call, and the volume caveat (national, taxonomy-level, relative not absolute). Do not recap the steps.

## Workbook

Tabs: Read Me; Roadmap (number, page, page type, content to write, why, parent page or link target, primary keyword and national volume, competitor gap keywords, sections to cover, and must appear on page (the research sheet's anchor text), and three yellow columns for the SEO: the primary keyword to check, keywords the SEO adds or swaps in, and a High / Medium / Low priority dropdown); Cut for the 50-page cap (only when something is over 50: an instruction row, then the same columns as the Roadmap plus the reason, so the SEO can move rows between the two tabs to make the final list). The Read Me's last row lists blogs that could not be added because a page is not in the blog taxonomy.
