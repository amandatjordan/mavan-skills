---
name: service-page-title-h1-review
description: Run Mavan's Service Page H1 & Title Tag Review from a Sitebulb or Screaming Frog export of the service pages. Works out what each page is about, chooses its target keywords from the path, H1 and title, adds each page's top Search Console queries from the Google Sheet of GSC data the person provides, and builds a two-tab workbook (Review, Data) with a Review Needed flag (including a missing location in the Title Tag or H1). Use for service page title tag and H1 reviews or rewrites.
---

# Service Page H1 & Title Tag Review (Mavan SOP)

This skill carries the whole process and does not need the written SOP; a copy in a project management tool is documentation for people.

For every service page it shows the current Title Tag and H1, leaves Suggested Page Title and Suggested H1 empty for the writer, and fills "Suggested Keywords" with the target keywords for that page. **You decide what each page is about and which keywords it should target, using SEO common sense and what you know about the service.** Do not write titles or H1s.

Work only from the export and the Google Sheet of Search Console data the person provides. **Do not use Composio for any part of this skill. Never visit the live site or use any tool to get page content.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person first and explaining why it is needed. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Assume nothing about the site (industry, URL structure, locations, brands, column names). Every number, count and join is done by `scripts/build.py`; never type or estimate a number.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). Scripts need Python 3 with pandas and openpyxl. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## What you need

- **Crawl export** (CSV or xlsx) of the service pages only, with the URL, H1 and Title Tag. Screaming Frog: Address, H1-1, Title 1. Sitebulb: URL, H1, Title. Ask for it if missing, and do not add or remove pages.
- **The client's city, or service-area cities**, for the city check (a page whose Title Tag or H1 names none of them is flagged, each separately). If the person does not know them, take them from the Title Tags if they are plainly there and say so; otherwise skip the check and say so.
- **Search Console data** (optional): a Google Sheet the person provides, with Page, Query, Clicks and Impressions columns, attached to the chat. If it is not attached, ask for it in Step 1. If the person says there is no access or no sheet, skip it: the workbook builds without the Top GSC Queries column.
- **Brand term(s)** of the client, so branded queries are left out of the Top GSC Queries column (skip if the sheet is already filtered).

Ask for whatever the request does not give in **one** message (Step 1), with no menus of options.

## Step 1: Check the export, then confirm once

```
python $SKILL/scripts/build.py inspect --crawl EXPORT.csv --out work
```

It prints which columns it will use, the page count, blank H1 and Title Tag counts, any pages that look like they are not service pages (tag, category, blog paths), and writes `work/pages.tsv`. If a column is wrong or missing, re-run with `--url-col`, `--h1-col` or `--title-col`.

Send **one** message with only what the request did not already give: the Google Sheet of Search Console data (if it is not attached), the cities, the brand term(s), and whether to drop the pages inspect flagged as not service pages (they are kept and flagged otherwise). No menus of options. Wait for the answer.

Done when the columns are confirmed, the cities and brand terms are known (or skipped), and you know whether Search Console data is used.

## Step 2: Check the Search Console sheet (only with the sheet)

The sheet can have thousands of rows. **Do not open it, print it, or read its rows into the chat, and do not read it with a Google Sheets tool.** The script reads the attached file. The script uses the tab named "Claude Use This" (the name in Mavan's Search Console template) when the file has one. If the file has several tabs with Page and Query columns and none has that name, the script stops and lists them: ask the person which tab to use (one question), then pass `--gsc-tab NAME`. Never add tabs together. Skip this step when Search Console data is not used.

Done when you know which file (and tab) to pass to `--gsc`, or the step is skipped.

## Step 3: Decide each page's topic and target keywords

Read `work/pages.tsv` (pages with a note "likely not a service page" still need a topic) and write `work/keywords.tsv`, one line per page, tab separated: `id`, `topic`, then up to 8 keywords separated by `;`, most important first.

- The H1 and last path segment name the page; the title confirms. Earlier path segments are context (category, location) only. Ignore the city and "near me".
- The topic is what a searcher would call the service. A page for two things ("dermabrasion or facial sanding") has both.
- Keywords: the main term first, then the other names for it, then the closest variants a searcher would use ("otoplasty; ear pinning; ear surgery; ear pinning surgery"). Keep every keyword on this page's topic: a broad word shared with other pages ("facial") is a keyword only on the page for that broad topic. No city, no "near me", no brand the page does not name, no how-to or cost keywords unless the page is that.
- A category or hub page ("Face", "Men", "Procedures") targets the category term, not its procedures.
- Do not invent numbers or claim volume. If you are unsure what a page is about, say so in the topic ("unclear: Providing DefenAge Skincare") and give your best keywords; the person will see the topic.

Done when every page has a topic and keywords.

## Step 4: Build the workbook

```
python $SKILL/scripts/build.py build --crawl EXPORT.csv --keywords work/keywords.tsv --cities "CITY, CITY" --gsc GSC_SHEET_FILE --brand "BRAND TERM" --out DOMAIN_service_page_title_h1_review.xlsx
```

Leave out `--gsc` when Search Console is not used, `--cities` when the city check is skipped. Read what it prints: the Review Needed count by reason and how many pages have queries.

Done when the script prints PASS for every check, the GSC match rate (if used) is not flagged by a WARNING or you have explained it, and you have opened 5 Review rows (include a Review Needed = Yes row) and agree that each Page Topic is what the page is about and the keywords belong to it.

## Step 5: Report

Send the workbook and reply in a few sentences:
- Pages processed, how many are Review Needed and the main reasons (including how many lack a location in the Title Tag or H1).
- Whether Search Console data was used. Without it, say there is no Top GSC Queries column and that providing the sheet and re-running adds it. Suggested Keywords are your judgment, not validated against search data.
- With Search Console: pages whose queries are mostly other cities or other services (for example a page that ranks for a different suburb), since that tells the writer what the page is really matching. Do not rank or judge the queries otherwise.
- Pages flagged as likely not service pages.
- Pages whose topic you were unsure of, so the person can check them.
- The next human step: review the Yes rows, then the writer fills Suggested Page Title and Suggested H1 and adds the location.

Do not paste Search Console rows into the chat.
