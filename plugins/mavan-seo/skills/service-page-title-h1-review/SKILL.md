---
name: service-page-title-h1-review
description: Run Mavan's Service Page H1 & Title Tag Review from a Sitebulb or Screaming Frog export of the service pages. Pulls Search Console clicks and impressions through Composio, matches each page to the bundled Service Taxonomy, and builds a three-tab workbook (Review, Recommendations, Data) with the top 5 keywords by search volume for each page. Use for service page title tag and H1 reviews or rewrites.
---

# Service Page H1 & Title Tag Review (Mavan SOP)

This skill carries the whole process and does not need the written SOP; a copy in a project management tool is documentation for people.

For every service page it shows the current Title Tag and H1, leaves Suggested Page Title and Suggested H1 empty for the writer, and fills "Update to Include" with the top 5 keywords (with volume) that page should be targeting, based on what the page is about according to the Service Taxonomy. Do not write titles or H1s.

Work only from the export, the bundled taxonomy and Search Console through Composio. **Never visit the live site or use any tool to get page content.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person first and explaining why it is needed. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Assume nothing about the site (URL structure, locations, brands, column names). Every count, match and join is done by `scripts/build.py`; never estimate a number by reading.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). Scripts need Python 3 with pandas and openpyxl. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## What you need

- **Crawl export** (CSV or xlsx) of the service pages only, with the URL, H1 and Title Tag. Screaming Frog: Address, H1-1, Title 1. Sitebulb: URL, H1, Title. Ask for it if missing, and do not add or remove pages.
- **Search Console property** for the site (domain or URL-prefix) and a **date range**. Default: the 90 days ending 3 days before today. Ask for what is missing in one question.
- **Taxonomy**: `$SKILL/references/service-taxonomy.xlsx` (Taxonomy and All Keywords tabs are used). If the person attaches a newer taxonomy, use theirs with `--taxonomy` and say so.
- **Composio** with Google Search Console connected. No GA4.

## Vocabulary

Use these names in every column, label and message: **Category > Service > Sub-Service > Brand / Device**. A **Concern** is a problem people search for and points to Services. Name every page for what it is: a Botox page is Botox (Brand / Device under Neurotoxin), never "Neurotoxin".

## Step 1: Check the inputs and access

```
python $SKILL/scripts/build.py inspect --crawl EXPORT.csv --out work
```

It prints which columns it will use, the page count, blank H1 and Title Tag counts, and writes `work/urls.txt`. If a column is wrong or missing, re-run with `--url-col`, `--h1-col` or `--title-col`. Then check the Composio Search Console connection (references/composio-gsc.md § 1) and tell the person the property and date range you will use.

Done when the columns are confirmed, the property and range have the person's yes, and Composio shows an active Search Console connection (or you have told the person to connect it and stopped).

## Step 2: Pull clicks and impressions

Follow references/composio-gsc.md, including every filtering rule: only the page dimension with clicks and impressions, filtered to the crawled URLs in small batches, nothing pulled beyond that. Save each batch to `work/gsc/`.

Done when every batch is saved and every URL in `work/urls.txt` was in some batch.

## Step 3: Build the workbook

```
python $SKILL/scripts/build.py build --crawl EXPORT.csv --gsc work/gsc --out DOMAIN_service_page_title_h1_review.xlsx
```

It applies references/rules.md (match each page to one taxonomy entry, build the keyword pool, add the keywords of implied entries that have no page, pick the top 5) and builds the workbook in references/workbook.md. Read what it prints: pages by matched level, the Needs review reasons, the recommendation count, how many GSC rows matched, and every Implies Offered name not found in the taxonomy.

Done when the script prints PASS for every check, the GSC match rate is not flagged by a WARNING (or you have explained it), and you have opened 5 Review rows (include a Needs review row and a row that used implied entries) and agree that the matched entry is named by the page's path, H1 or title and that the keywords belong to it.

## Step 4: Report

Send the workbook and reply in a few sentences:
- Pages processed, how many are Needs review and why, and how many Recommendations.
- Anything the person must decide: Needs review pages, and pages whose label looks wrong.
- Any services or brands the pages name that are not in the taxonomy (so they can be added by pull request), and any Implies Offered names the script could not find.
- That volume is from competitor rankings and ranks keywords against each other, and that the workbook imports into Google Sheets.
- The next human step: the writer fills Suggested Page Title and Suggested H1 and adds the location.

Do not paste raw GSC responses or the keyword list into the chat.
