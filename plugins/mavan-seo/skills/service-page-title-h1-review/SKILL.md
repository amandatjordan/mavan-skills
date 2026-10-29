---
name: service-page-title-h1-review
description: Run Mavan's Service Page H1 & Title Tag Review from a Sitebulb or Screaming Frog export of the service pages. Works out what each page is about, chooses its target keywords from the path, H1 and title, ranks them by Search Console impressions when Composio is connected (otherwise lists them without numbers), and builds a three-tab workbook (Review, Recommendations, Data) with a Review Needed flag. Use for service page title tag and H1 reviews or rewrites.
---

# Service Page H1 & Title Tag Review (Mavan SOP)

This skill carries the whole process and does not need the written SOP; a copy in a project management tool is documentation for people.

For every service page it shows the current Title Tag and H1, leaves Suggested Page Title and Suggested H1 empty for the writer, and fills "Update to Include" with the target keywords for that page. **You decide what each page is about and which keywords it should target, using SEO common sense and what you know about the service.** Do not write titles or H1s.

Work only from the export and, when it is connected, Search Console through Composio. **Never visit the live site or use any tool to get page content.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person first and explaining why it is needed. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Assume nothing about the site (industry, URL structure, locations, brands, column names). Every number, count and join is done by `scripts/build.py`; never type or estimate a number.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). Scripts need Python 3 with pandas and openpyxl. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## What you need

- **Crawl export** (CSV or xlsx) of the service pages only, with the URL, H1 and Title Tag. Screaming Frog: Address, H1-1, Title 1. Sitebulb: URL, H1, Title. Ask for it if missing, and do not add or remove pages.
- **The client's city, or service-area cities**, for the city check (a page whose Title Tag and H1 name none of them is flagged). If the person does not know them, take them from the Title Tags if they are plainly there and say so; otherwise skip the check and say so.
- **Search Console** (optional): the property (domain or URL-prefix) and a date range. Default: the 90 days ending 3 days before today. Needs Composio with Google Search Console connected, and the person's yes. **Without it the workbook still builds: the keywords are listed in your order of importance with no numbers.**

Ask for whatever the request does not give in one question.

## Step 1: Check the inputs and access

```
python $SKILL/scripts/build.py inspect --crawl EXPORT.csv --out work
```

It prints which columns it will use, the page count, blank H1 and Title Tag counts, and writes `work/urls.txt` and `work/pages.tsv`. If a column is wrong or missing, re-run with `--url-col`, `--h1-col` or `--title-col`. Then check the Composio Search Console connection (references/composio-gsc.md § 1). If it is connected, tell the person the property and date range and wait for a yes. If it is not, or the person cannot give a property, say in one line that the keywords will have no numbers, and carry on without it.

Done when the columns are confirmed, the cities are known (or the check is skipped), and you know whether Search Console is used.

## Step 2: Pull page and query data (only with Search Console)

Follow references/composio-gsc.md, including every filtering rule: only the page and query dimensions with clicks and impressions, filtered to the crawled URLs in small batches. Save each batch to `work/gsc/`. Skip this step when Search Console is not used.

Done when every batch is saved and every URL in `work/urls.txt` was in some batch, or the step is skipped.

## Step 3: Decide each page's topic and target keywords

Read `work/pages.tsv` and write `work/keywords.tsv`, one line per page, tab separated: `id`, `topic`, then up to 8 keywords separated by `;`, most important first.

- The H1 and last path segment name the page; the title confirms. Earlier path segments are context (category, location) only. Ignore the city and "near me".
- The topic is what a searcher would call the service. A page for two things ("dermabrasion or facial sanding") has both.
- Keywords: the main term first, then the other names for it, then the closest variants a searcher would use ("otoplasty; ear pinning; ear surgery; ear pinning surgery"). Keep every keyword on this page's topic: a broad word shared with other pages ("facial") is a keyword only on the page for that broad topic. No city, no "near me", no brand the page does not name, no how-to or cost keywords unless the page is that.
- A category or hub page ("Face", "Men", "Procedures") targets the category term, not its procedures.
- Do not invent numbers or claim volume. If you are unsure what a page is about, say so in the topic ("unclear: Providing DefenAge Skincare") and give your best keywords; the person will see the topic.

If a page clearly implies a page that is missing from the crawl (for example a brand page whose parent service page is not in the export), write it to `work/recommendations.tsv`: recommended page, implied-by URL(s) separated by `;`, reason, tab separated. Only obvious cases; never hunt for gaps.

Done when every page has a topic and keywords.

## Step 4: Build the workbook

```
python $SKILL/scripts/build.py build --crawl EXPORT.csv --keywords work/keywords.tsv --recs work/recommendations.tsv --cities "CITY, CITY" --gsc work/gsc --out DOMAIN_service_page_title_h1_review.xlsx
```

Leave out `--gsc` when Search Console is not used, `--cities` when the city check is skipped, and `--recs` when there are none. Read what it prints: the Review Needed count by reason and how many GSC pages matched.

Done when the script prints PASS for every check, the GSC match rate (if used) is not flagged by a WARNING or you have explained it, and you have opened 5 Review rows (include a Review Needed = Yes row) and agree that each Page Topic is what the page is about and the keywords belong to it.

## Step 5: Report

Send the workbook and reply in a few sentences:
- Pages processed, how many are Review Needed and the main reasons, and how many Recommendations.
- Whether Search Console was used. Without it, say the keywords have no numbers and are not validated against search data, and that connecting Search Console and re-running ranks them.
- Pages whose topic you were unsure of, so the person can check them.
- The next human step: review the Yes rows, then the writer fills Suggested Page Title and Suggested H1 and adds the location.

Do not paste raw GSC responses into the chat.
