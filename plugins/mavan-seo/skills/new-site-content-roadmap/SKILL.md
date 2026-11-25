---
name: new-site-content-roadmap
description: For a brand-new site, turn the new-site keyword research workbook, the new-site keyword gap workbook (one per set of competitors) and the bundled blog taxonomy into the list of pages and blog posts to write content for (50 at most, always including Home and About Us). Asks for the research workbook, the gap workbook or workbooks and any extra pages that need content (packages, providers, locations, events, financing and so on). Use for a new site content roadmap, "which pages should we write for the new site", or after new site keyword research and the new-site keyword gap.
---

# New site content roadmap (Mavan)

One question for a business building a **new site**: of everything the keyword research and the competitor gap found, which pages and blog posts should we write content for first? The answer is a list of **50 pages at most**. Home, About Us, every extra page the SEO names and every blog post count toward the 50.

Work only from the two workbooks, the bundled blog taxonomy and service taxonomy, and what the person types in. **Never visit a live site, and use no Composio tool, DataForSEO, Semrush, Ahrefs export or other connector.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person and explaining why. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Every count, rank and cut is done by `scripts/roadmap.py`; never type or estimate a number. What each rule means is in [references/rules.md](references/rules.md).

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
| **New-site keyword gap** workbook(s) | Required, one or more | The .xlsx from `new-site-keyword-gap`. A client with services that do not overlap has one per set of competitors: ask for all of them and use them together. Each one's **Offered by our client** column on Service opportunities should be filled in: only Yes services count |
| **Other pages that need content** | Ask, can be none | Pages we would write that are not in either sheet: packages, provider pages, location pages, events, financing, treatments by area or age, and anything else the person names. Give each a name and, if they can, a type (Package, Provider, Location, Event, Financing, Treatment by area, Treatment by age) |
| Client name | Optional | Names the workbook |

Home and About Us are always added. Do not ask about them. The blog taxonomy is bundled; never ask for it.

Done when the research workbook and every gap workbook are attached and the person has given the extra pages or said there are none.

## Step 2: Preflight

```
python $SKILL/scripts/roadmap.py preflight --research RESEARCH.xlsx --gap GAP.xlsx [GAP2.xlsx ...] --extras "Bridal packages|Package; Dr Smith|Provider" --out work
```

Pass `--extras` only when there are extras (`Name|Type` separated by semicolons). It checks that each workbook is the right kind, counts blank Offered answers and checks that Home, About Us and the extras fit under 50. Read `work/preflight.md`. On NOT READY, send **one** message listing each FAIL and exactly what is needed, then stop. Mention each WARN in the final reply: gap services whose Offered column is blank are left out of the roadmap. If the person wants those in, they fill in the gap workbook and send it again. Done when it says READY.

## Step 3: Match gap services to research pages

```
python $SKILL/scripts/roadmap.py match --research RESEARCH.xlsx --gap GAP.xlsx [GAP2.xlsx ...] --out work
```

It writes `work/gap_match.tsv`, one row per gap service, and prints every row that is not `ok`. A gap service with no research page is also looked up in the bundled service taxonomy (`references/service-taxonomy.xlsx`), by its exact name and then by each node's Match Terms, because the blog taxonomy is keyed by the taxonomy's names (a gap sheet's "Nose Job" is Rhinoplasty there). A hit fills `taxonomy_name` (the name the roadmap page will use) and `level`; the printed row says `TAXONOMY` for an exact name and `TAXONOMY?` for a search-term match, which you must check. Several hits are listed as `REVIEW` with no name filled in. The gap workbook's service names are free text the SEO chose (Fillers, botox, NAD+), so each one has to be matched to a page on the research Pages tab. Read **every** row, ok ones included, and correct `page` in place so it is the **exact label** from the research Pages tab, or blank when the service is not on that tab:
- A gap service that is one treatment or product matches the page for that treatment or product (botox -> the Botox brand page). A broad name (Fillers) matches the Service page.
- Two gap services may point to the same page; their numbers are added.
- With more than one gap workbook, all their services are in this one file. A service name that appears in more than one workbook is already one row, with the higher number (non-local plus local) and Offered = Yes if any of them says Yes.
- A service with no page and `offered` = Yes becomes a page of its own. Its name is `taxonomy_name` when that is filled in (check the `TAXONOMY?` ones against what the service really is, and clear `taxonomy_name` and set `level` yourself if the guess is wrong); with several candidates, pick one and type its full label into `taxonomy_name`. When there is no `taxonomy_name`, set `level` to Service, Sub-Service, Brand / Device or Concern and fix the name's capitalization. Never invent a research label or a taxonomy name.
- Two gap services with the same `taxonomy_name` are one page and their numbers are added (Remove Wrinkles and Deep Wrinkles both point to the Wrinkles / Fine Lines concern).
- `offered` can be edited in this file when the person tells you the answer for a blank row. Say you did.
- A service with no page and Offered No or blank is left off the roadmap and is not listed anywhere.

Done when every row is an exact research page, a taxonomy name you have checked, or deliberately blank.

## Step 4: Build

```
python $SKILL/scripts/roadmap.py build --research RESEARCH.xlsx --gap GAP.xlsx [GAP2.xlsx ...] --match work/gap_match.tsv --extras "..." --client "CLIENT" --out "CLIENT_new_site_content_roadmap.xlsx"
```

If it stops on a gap service or a page name, fix that row and run again. Done when every check prints PASS. Printed warnings (for example a gap service the client does not offer that is matched to a research page) go in the reply.

## Step 5: Check

- Roadmap tab: Home, About Us and every extra page are at the top, the row count is 50 or fewer, and the rows follow Service, Sub-Service, Brand / Device, Blog, Concern.
- Pick 3 page rows and compare the primary keyword and volume to the research Pages tab.
- Pick 3 gap numbers and compare them to the Service opportunities tab (of the gap workbook the number came from) (non-local plus local, of the matched service).
- Pick 2 blog rows and compare the angle to the blog taxonomy's Lookup tab.
- Internal links tab: pick 3 rows and compare them to the research Pages tab's "Internal links out" column. Every Service, Sub-Service and Brand / Device page on the Roadmap is in the To page column (the script checks this). Every phrase in "Must appear on page" is the anchor of at least one row (the script checks this). Say how many links were added and why.
- Cut tab (only present when something is over 50): starts with the instruction row, has the same columns as the Roadmap with the reason last (including the empty page title, H1 and meta description columns), is styled like the Roadmap (yellow columns, orange H1 cells, priority dropdown), and each cut page is there. Sections are not pages: each one is in "Sections to cover" on its parent page.
- Open the workbook and look at it: the Read Me's second row says the SEO must update ALL THE TABS, the page title, H1 and meta description columns are empty on every row of the Roadmap and the Cut tab (never fill them in or suggest text), the H1 cells of Home and Service pages are orange, the Internal links tab's Anchor text column is yellow, and the Must appear on page header sends the content team to the Internal links tab.

Done when all six hold.

## Step 6: Report

Send the workbook. Reply in a few sentences: how many rows by type, what was cut for the 50 cap (the number by group, and which Service pages if any), the extra pages, how many internal links were added so every page receives one, any warning (include each gap service that has no service in the taxonomy and so got no blogs, and each gap service that took a taxonomy name, naming the page it became), that the SEO must check the yellow primary keyword column (a primary keyword is only the highest-volume search for the page and may be a search from someone looking at pictures or reading about a topic, for example "face with wrinkles") and replace it or add keywords, that content must use the "Must appear on page" words (the anchor text other pages link with), that that the SEO must update ALL THE TABS (the Roadmap, the Cut tab if there is one, and the Internal links tab): fill in the page title, H1 and meta description on the Roadmap and Cut tabs (the H1 of Home and of every Service page must include the location / city name) and add the anchor text they want used on the Internal links tab, that the content team must check the Internal links tab for the anchor text needed on each page, that the SEO fills in the yellow priority column and makes the final call, and the volume caveat (national, taxonomy-level, relative not absolute). Do not recap the steps.

## Workbook

Tabs: Read Me; Roadmap (number, page, page type, content to write, why, parent page or link target, primary keyword and national volume, competitor gap keywords, sections to cover, and must appear on page (the research sheet's anchor text), and yellow columns for the SEO: the primary keyword to check (replace it or add keywords in the same cell), and the empty page title, H1 and meta description to complete (the H1 cells of Home and Service pages are orange: they must include the location / city name), and a High / Medium / Low priority dropdown; we give the empty fields and never suggest text for them); Internal links (from page, to page, a yellow anchor text column the SEO fills in, and where each link came from; every Service, Sub-Service and Brand / Device page on the Roadmap receives at least one link); Cut for the 50-page cap (only when something is over 50: an instruction row, then the same columns, styling and dropdown as the Roadmap plus the reason, treated exactly like the Roadmap, so the SEO can move rows between the two tabs to make the final list). The Read Me's second row tells the SEO to update ALL THE TABS. The Read Me's last row lists blogs that could not be added because a page is not in the blog taxonomy.
