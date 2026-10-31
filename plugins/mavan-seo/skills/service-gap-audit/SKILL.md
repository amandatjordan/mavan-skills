---
name: service-gap-audit
description: Run Mavan's Service Gap Audit for a medspa or plastic surgery site from a Sitebulb or Screaming Frog export and the bundled Service Taxonomy, and build the gap audit workbook. Use for service gap audits, missing service pages, or thin and non-indexable service pages.
---

# Service Gap Audit (Mavan SOP)

This skill carries the whole process and does not need the written SOP; a copy in a project management tool is documentation for people.

The audit answers four questions for every service in the taxonomy: does the practice offer it, does it have a page Google can index, does that page have real content, and how much national search demand is behind it. The deliverable is the Recommendations tab: one row per page to build or fix.

Work only from the crawl export, the bundled taxonomy, and the optional Search Console sheet. **Never visit the live site or use Composio or any other connector.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person first and explaining why it is needed. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Assume nothing about the site: URL structure, folder names, locations and brands differ on every site, so page types are decided per page in Step 3, never from a folder name. Every number, count and join is done by `scripts/build.py`; never type or estimate a number.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). The script needs Python 3 with pandas and openpyxl. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## What you need

- **Crawl export** (CSV or xlsx, internal HTML URLs, every status code). Sitebulb: URL, HTTP Status Code, Indexable Status, Title, Meta Description, H1, H2, H2 (second), No. Content Words, and the canonical URL column if exported. Screaming Frog: Address, Status Code, Indexability Status, Title 1, Meta Description 1, H1-1, H2-1, H2-2, Word Count, Canonical Link Element 1. URL, status, title, H1 and word count are required; the rest are used when present.
- **Client facts**: domain, practice type (medspa, surgical, or both), and every city and suburb the practice targets.
- **Search Console data** (optional): a Google Sheet with Page, Query, Clicks and Impressions columns, attached to the chat. The script uses the tab named "Claude Use This" when the file has one.
- **Taxonomy**: bundled at `$SKILL/references/service-taxonomy.xlsx` (Taxonomy, Filters, All Keywords tabs). Do not ask for it, and do not read a sheet link to it: the bundled copy is the one to use. Use a different file only when the person explicitly says to, and pass it with `--taxonomy`.

## Vocabulary

Use these names in every column, label and message: **Category > Service > Sub-Service > Brand / Device**. A **Concern** is a problem people search for; it points to Services and is never a page gap on its own. A **Modifier** (Cost, Before & After, Recovery / Risks, Comparison, Candidacy, Best / Top) is a flag on a keyword, never a level. Name every page for what it is: a Botox page is Botox (Brand / Device under Neurotoxin), never "Neurotoxin".

## Step 1: Ask once

Send **one** message with only what the request did not already give: practice type, every city and suburb they target (nearby towns not named are treated as other markets), and the Search Console Google Sheet. No menus of options. If a sheet link or file is provided, the script checks it has Page, Query, Clicks and Impressions columns; a sheet without them (for example the taxonomy) is not Search Console data, so say so and continue without it. If the person has no sheet, continue without it: the workbook builds without the Client GSC Impressions column and the Read Me says so.

Done when practice type and cities are known and you know whether Search Console data is used.

## Step 2: Inspect the crawl

```
python $SKILL/scripts/build.py inspect --crawl EXPORT.csv --cities "City, City" --practice medspa --out work
```

It prints which columns it will use, the ones missing (H2s, canonical), status code counts, and writes `work/pages.tsv`: one line per live page with its words, indexability, title, H1, a suggested type and suggested taxonomy node, and editable `type`, `node` and `city` columns. If a column is mapped wrong, re-run with `--url-col`, `--h1-col` and so on.

Done when the columns are confirmed and `work/pages.tsv` exists.

## Step 3: Review every page's type and node

Read `work/pages.tsv` and correct the `type` and `node` columns in place (leave `suggested_*` as they are). Suggestions come from taxonomy matches and generic hints, so they are a start, not an answer. Apply [references/rules.md](references/rules.md) § Page types and § Nodes. In short:
- **type** is one of Service, Concern, Gallery, Blog, Location, Utility, judged from the page's H1, title and path together.
- **node** is the exact taxonomy name of what the page is about (Service pages must have one; other types may). A brand or device missing from the taxonomy is written `NEW: Name > Service`.

Done when every Service page has a node, every row's type is one of the six, and you have checked every Service and Concern row plus 5 rows of each other type.

## Step 4: Build

```
python $SKILL/scripts/build.py build --crawl EXPORT.csv --pages work/pages.tsv --cities "City, City" --practice medspa \
  --domain DOMAIN --out DOMAIN_service_gap_audit.xlsx [--gsc GSC_SHEET_FILE [--gsc-tab TAB]]
```

If it stops on pages.tsv problems, fix each listed row and re-run. If the GSC file has several tabs with GSC columns and none is "Claude Use This", ask the person which tab (one question) and pass `--gsc-tab`; never add tabs together. Do not open, print or paste Search Console rows into the chat.

Done when every check prints PASS.

## Step 5: Check

- Open 5 Recommendations rows (include a "not indexable" or "thin" row and a "no page" row) against Page Inventory: the label, URL and word count agree.
- Read the top 10 rows the script prints. Relevant Keywords contain no other city and no keyword from a different service. A wrong-service keyword means a match term is too broad: note it for the taxonomy pull request.
- Read the Read Me: inputs, missing columns and "Not in taxonomy" are right.

Done when all three hold.

## Step 6: Report

Send the workbook and reply in a few sentences: the biggest issue, the top missing pages, what needs client confirmation, whether Search Console data was used, and every brand, device or service marked NEW (plus any match term that needs tightening) for the `service-taxonomy.xlsx` pull request. Practice-specific package or program names never go in the taxonomy.
