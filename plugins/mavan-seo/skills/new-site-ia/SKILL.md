---
name: new-site-ia
description: For a brand-new site, turns the new site content roadmap and a CSV of the other pages the site needs (Contact, Privacy Policy, booking, membership and so on) into the information architecture - every page with its parent, recommended URL path and main nav Yes / No - plus the planned internal links with URLs added. Asks for the roadmap and the CSV, and optionally the URLs the client wants. Use for new site information architecture, site map or URL structure for a site that does not exist yet, "what URLs should the new site use", or after the new site content roadmap.
---

# New site information architecture (Mavan)

One question for a business building a **new site**: what is **every page** on it, where does each one sit, what is its URL and is it in the main navigation? The answer is one workbook: a Pages tab and an Internal links tab.

Work only from the content roadmap workbook, the CSV the person gives and what they type in. **Never visit a live site, and use no Composio tool, DataForSEO, Semrush, Ahrefs export or other connector.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person and explaining why. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Every count, URL and check is done by `scripts/ia.py`; never type a URL or a number into the workbook yourself. What each rule means is in [references/rules.md](references/rules.md).

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). The script needs Python 3 with openpyxl. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## The roadmap owns the links

The roadmap's Internal links tab is the link plan: which page links to which page with which anchor text. This skill copies it, adds the URLs and checks it. It **never adds, removes or changes a link or an anchor**. A problem with a link is fixed in the roadmap skill, not here.

## Step 1: Ask for the inputs

Ask for all of this in **one** message, before doing anything else.

| Input | Required? | Notes |
| --- | --- | --- |
| **New site content roadmap** workbook | Required | The .xlsx from `new-site-content-roadmap`, with its Roadmap and Internal links tabs. If the SEO moved pages between the Roadmap and Cut tabs, the Internal links tab must be updated to match first |
| **CSV of every other page the site needs** | Required | Pages that need no content from us: Contact, Privacy Policy, booking, membership and so on. Columns: `Page` and `URL`. The URL is optional: give the path the client wants, or leave it blank and we recommend one. If the person only sends the roadmap, ask for this CSV; do not guess the pages |
| Client name | Optional | Names the workbook |

Done when the roadmap and the CSV are attached.

## Step 2: Preflight

```
python $SKILL/scripts/ia.py preflight --roadmap ROADMAP.xlsx --csv PAGES.csv --out work
```

Read `work/preflight.md`. On NOT READY, send **one** message listing each FAIL and exactly what is needed, then stop. Mention each WARN in the final reply. Done when it says READY.

## Step 3: Build

```
python $SKILL/scripts/ia.py build --roadmap ROADMAP.xlsx --csv PAGES.csv --client "CLIENT" --out "CLIENT_new_site_ia.xlsx"
```

Done when every check prints PASS. Printed warnings go in the reply.

## Step 4: Check

- Pages tab: every page is listed by its own name (Botox, not Neurotoxin > Botox), and so is every parent. Every roadmap page and every CSV page is there, plus a `/blog` index when there are blogs. Service, Sub-Service and Brand / Device URLs are under `/services/`; no URL has more than three segments.
- Read every row marked Recommended and every row with a Notes entry (text in brackets dropped from a URL, a Brand under a Sub-Service, blog placeholders). Do not edit them: list the ones that look wrong in the reply for the SEO.
- Main nav: Home and the blog index are Yes, individual blog posts are No, and the legal / utility pages from the CSV are No.
- Pick 3 rows on the Internal links tab and compare them to the roadmap's Internal links tab (same pages and anchor text; only the URLs are new).
- Warnings: each "Roadmap gap" or "No planned link" warning is a problem in the roadmap's Internal links tab. Say which pages and that the roadmap has to be fixed.

Done when all five hold. These checks do not replace the SEO's QA: the SEO still checks both tabs line by line (Step 5).

## Step 5: Report

Send the workbook. Start the reply by saying the SEO must QA **both** tabs before the workbook goes to the client or the developer: on the Pages tab every page name, parent, URL, main nav cell and note; on the Internal links tab every From and To page, both URLs and the anchor text. Then, in a few sentences: how many pages (and how many are blog posts), the pages added from the CSV and the `/blog` index, that URLs the client gave were used as given and the yellow URLs are our recommendations for the SEO to check, that the SEO can change any yellow cell in the "In main nav" column (Home, the blog index and blog posts are fixed), how many pages are in the main nav, that blog URLs are placeholders until the titles are chosen, each warning, and what needs fixing in the roadmap. Do not recap the steps.

## Workbook

Tabs: Pages (page name: the page's own name, not the roadmap's "Parent > Page" path, page type, recommended parent page, recommended URL path, URL source Provided / Recommended, In main nav Yes / No with a Yes / No dropdown, content from us Yes / No, notes; yellow cells are for the SEO to check); Internal links (from page, from URL, to page, to URL, anchor text, where the link came from, and priority when the roadmap has it); Read Me (SEO QA of both tabs, rules, counts, warnings). On the Internal links tab, From and To pages also use each page's own name.
