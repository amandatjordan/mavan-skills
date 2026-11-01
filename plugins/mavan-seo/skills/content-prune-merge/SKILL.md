---
name: content-prune-merge
description: Run Mavan's Content Prune & Merge audit for a client site from Sitebulb or Screaming Frog exports plus Search Console and GA4, and deliver one workbook that fills the Prune & Merge template sheet. Use for prune, merge, or cannibalization audits.
---

# Content Prune & Merge

Decide, for every live page on a client site, whether to keep, update, repurpose, merge or remove it, and hand the reviewer one workbook with suggestions, a Recommendations TL;DR and a clean redirect list. This skill carries every rule it needs; it does not need access to the SOP. A person makes the final calls: fill the Suggested columns and leave Next Steps, Target URL and Reasoning blank.

Sites are built differently. Never assume folder names, page types, cities or a CMS: map this site's own structure first (Step 2) and let the person confirm it. Scripts only do what is true on every site (normalizing URLs, following redirect chains, counting). Anything that depends on how this site is built (which folder is which page type, which words are cities, which pages are about the same topic) is proposed by you from the data, shown to the person, and confirmed. Never fill a gap with fuzzy matching: when no exact match or confirmed rule decides a call, leave it for the reviewer and say so. The only assumption is that the client is an aesthetics business, which is why the vocabulary says treatments, concerns and locations.

`$SKILL` below is this skill's folder: the base directory shown when the skill loads. Set it once in the shell (`SKILL=<that folder>`). Scripts need Python 3 with pandas and openpyxl (`pip install --break-system-packages pandas openpyxl` if missing). Work in a folder named after the client with a `work/` subfolder, do every count, match and join in code, and keep a task list with one item per step.

**How to ask.** Every question the person has to answer follows these rules:
- Put the single decision in the question text, as a direct question ending in a question mark ("Which of these URL folders are JUNK?"). Never leave the decision only in the option descriptions.
- One decision per question. Do not combine a table of folders and several decisions in one prompt.
- Option labels name the thing and its size ("/tag/ - 81 pages"). Option descriptions say what picking it does.
- Put tables and long lists in the chat text first, and keep the question itself short.
- The question tool takes at most 4 options per question. When there are more choices (for example 7 junk-folder candidates), split them over several questions of the same wording, largest first, and say in each question that unpicked items keep their default.

## Step 1: Pre-flight check

Run this before anything else, and again whenever the person says what they have. It applies when the person asks what is needed, and when the request leaves anything required out. Check the chat for each item:

| # | Item | Required? | Ready when |
| --- | --- | --- | --- |
| 1 | Crawl: URL export | Required | Sitebulb or Screaming Frog, every URL and every status code (not just 200s). Sitebulb: the URLs export. Screaming Frog: Internal > All. |
| 2 | Crawl: internal links export | Required | Every internal link with its CSS path (Sitebulb) or link path (Screaming Frog). Sitebulb: Links > Internal Links. Screaming Frog: Bulk Export > Links > All Inlinks. |
| 3 | Crawl: redirects export | Required | The target of every 3XX. Sitebulb: the redirected URLs export. Screaming Frog: Response Codes > Redirection (3xx) > Export, or Reports > Redirects > All Redirects. |
| 4 | Search Console page + query data | Required | The Google Sheet link pasted into the chat (the app attaches the sheet as a file, which is what gets read), or a CSV or XLSX of it, with Page, Query, Clicks and Impressions columns. Made with the Search Analytics for Sheets add-on or a Looker Studio table. The Search Console UI export is not enough: it splits pages and queries and caps at 1,000 rows. |
| 5 | Search Console date range | Required | The person has said the start and end dates the Search Console data covers. Always ask; never assume a window. The recommended window is the last 90 days, ending 3 days ago. |
| 6 | GA4 landing pages | Optional | A GA4 landing page file (Sessions, New users, Views, Key events) for the same dates, or nothing: see Step 3 for when GA4 is pulled and when it is skipped. |
| 7 | Domain | Required | Stated, or readable from the crawl URLs. |
| 8 | Cities | Required | The main city, and every other city or area the client wants its own pages for. Step 2 checks this list against the URL paths. |
| 9 | IA audit All Pages tab | Optional | When attached, its page types are used. |
| 10 | Newer copy of the SOP | Optional | When pasted, it wins over references/rules.md and the differences are listed in the report. |

Brand terms are handled in the Search Console export, so never ask for them. The Prune & Merge template link is fixed (references/sheet.md); a Google Sheet link given with the command is the Search Console data (item 4), not the template, when it has Page and Query columns.

**If the person asks what is needed**, answer with this table in plain words, then ask for what they have not given.

**If anything required is missing**, send **one** message that lists only the missing items, one line each, saying what to provide (for crawl files, which export; for Search Console, the columns and the date range question), and points to the Content Prune & Merge SOP for the full export steps. Then stop and wait. Do not run a script, guess a missing value, or start with part of the inputs. A file that is not what it should be counts as missing (for example a links export with no CSS or link path column, or a Search Console sheet with no Query column): say what is wrong with it.

Load every file in code only; never print or paste one into the chat (the links file is often 20MB+). Make no requests to the live site: no sitemap fetches, no status checks, no redirect resolving. The crawl's status codes and the redirects export are the truth. The Sitebulb connector cannot replace the crawl files.

Also check which tools the session has: with Google Drive and Sheets connectors, the template is copied and the Recommendations tab written by connector (references/sheet.md); without them, the workbook alone with paste steps. Say which in one line.

Done when items 1 to 5, 7 and 8 are provided, and you know whether GA4 comes from a file, from Composio, or is skipped.

## Step 2: Prepare the crawl, map the structure, confirm the cities

```
python $SKILL/scripts/prep.py --domain DOMAIN --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv --out work
```

It detects the crawler (and prints the columns it used; if it guesses wrong, pass `--crawler "Screaming Frog"` or `--crawler Sitebulb`), normalizes URLs, follows every redirect chain to where it ends, and classes every link Nav / Footer / Breadcrumb / Body from the CSS path (Sitebulb) or link path (Screaming Frog), because the crawlers' own location labels are unreliable. Read the printed class counts and path patterns. Done when menus land in Nav, footers in Footer, article copy in Body and there is no WARNING; otherwise re-run with `--nav-regex` / `--footer-regex` built from the paths shown. Theme menus often sit in short-ID containers the default pattern misses (SmartMenus `ul#sm-...`, sliders `swiper-wrapper`): when the crawler labels a Body-classed path Header or Footer in its own location column, extend the regex (keep the default by appending to it: `--nav-regex "$(python3 -c 'import sys;sys.path.insert(0,"'$SKILL/scripts'");import prep;print(prep.NAV_RE)')|#sm-"`).

Read `work/crawl_pages.csv` by its `primary` rows only: `/page` (301) and `/page/` (200) share one key, and the primary row is the live one. `work/redirects.csv` already has each redirect's `final` page, `hops`, full `chain` and `final_status`; rows with `normalization_only` True only add a slash or change case and need nothing. From the raw URL export, also note case-duplicate URLs (e.g. `/Page-Name/` returning 200 beside `/page-name/`) and `?utm_` variants (drop them). `prep.py` writes `work/canonical_issues.csv`: pages whose canonical points at a non-200 URL, including a canonical that redirects back to the page (`/a/` canonicalizes to `/a-2/`, which redirects to `/a/`). Each one gets the canonical flag in Notes (references/rules.md). Pagination URLs such as `?e-page-1a2b=2` canonicalize to the listing and get no audit rows.

**Map the structure.** Do not assume folder names. List every top-level URL folder of the live pages with its page count, 3 example URLs with titles, and the Page Type you think it is and why, plus one row for root-level pages (no folder). Map this site's own kinds of pages onto the Page Type values in references/rules.md: a page that makes the client money (a service, a product, a practice area) = Service; a page about a problem or topic the client treats = Concern / Condition; a city, branch or area page = Service Area / Location; a folder's own listing page, or a listing of a group of services or products = Hub / Category Page. Show the table as normal chat text first (folder | pages | example titles | proposed Page Type | why). Then ask only about the folders you are unsure of, one question per folder ("What type of page is everything under /xyz/?"), with the proposed type as the first option, marked "(Recommended)". If you are sure of every folder, ask nothing and say the map is below. Save the map as `work/folder_map.json`.

**Confirm the cities.** `prep.py` writes `work/slug_words.csv`: every word used in live URL paths, with the number of pages and examples. Read it and pick out the place names (cities, neighborhoods, areas), together with the cities from pre-flight item 8. Show them as chat text (city | pages with it in the URL | 3 example URLs). Then, for each city, ask: "Should [city] be treated as a separate market with its own pages?" with two options: "Separate market" (pages named for it are location pages, and a service page that repeats another page for it is a city copy) and "Ignore in URLs" (the word says nothing about the page; use this for the main city when most URLs carry it). Recommend "Ignore in URLs" for the main city and "Separate market" for the others the person named. Ask about at most 4 cities per question round; cities with 1 or 2 pages can share one multi-select question ("Which of these are separate markets?").

Then list the service pages whose URL names a separate-market city but that have no twin with the same slug once the city is removed (for example `/services/skinpen-microneedling-tampa-fl/` beside `/services/microneedling-brandon-fl/`), with the closest-looking page next to each, and ask the person which of them are copies of another page ("Which of these Tampa pages repeat a page you already have?", multi-select). Never pair them yourself. Save everything as `work/cities.json`: `{"main": "...", "separate": [...], "ignore": [...], "copy_pairs": [[copy, original], ...]}`.

Done when every folder has a type the person has seen and every city found has a confirmed treatment.

## Step 3: Search Console and GA4

Follow references/data.md: read the Search Console data, confirm its date range matches what the person said (or say it could not be checked), build the topic groups and the overlap list.

**GA4 is gated by Search Console clicks**, because GA4 often holds too little to use and pulling it costs time:
1. A GA4 file was attached: read it (no Composio).
2. No file and Search Console has under 300 clicks in the window: skip GA4. Leave Conversions, New Users, Sessions and Views blank, and say in one report line that GA4 was not pulled because the site had [N] Search Console clicks.
3. No file and 300+ clicks, with Composio connected: run the one monthly sessions report first (references/data.md). Under 200 sessions in the window: skip GA4 and say so with the total (and, if sessions collapse partway, tell the person to check the GA4 tag). 200 or more: pull the landing page report.
4. No file and no Composio: leave GA4 blank and say so.

**Topic groups.** Build groups from shared Search Console queries (references/data.md). Pages with too little Search Console data to share queries (under 20 impressions) are grouped by their title instead: propose those title groups as chat text (group | pages | the title words they share) and ask the person to confirm or correct them in one question before they are used. Never group by fuzzy slug matching.

Done when every live page has its metrics (or the stated reason GA4 was skipped), the topic groups are confirmed, and the overlap list is built.

## Step 4: List the demand the crawl missed

No live requests. Build `work/not_in_crawl.tsv` (references/data.md): every URL in Search Console or GA4 that is not a live page in the crawl, with clicks, impressions, sessions and its redirect target when the redirects export has one. Use the sitemap only if it is already in the crawl data. Category, tag, author and date archives found this way belong to junk folders. Done when the file exists and its row count is in the report.

## Step 5: Build the Audit rows

Write `work/build.py` so reruns are one command. Apply references/rules.md in order: Page Type (from `work/folder_map.json` and `work/cities.json`), Suggested Next Step and Target, Notes, junk folders. Leave Referring Domains blank. Keep judgment overrides in one dict with a reason string each, and mark them "judgment" in Notes. Done when every live page has a row (or sits in a junk folder), every Merge/Remove row has a full target URL whose own suggestion is Keep, Update, Repurpose or Needs Discussion, and the counts per Page Type and per suggestion are printed.

Then show the junk-folder candidates as chat text (folder | rule matched | page count | total impressions | 5 example URLs | suggested wildcard target). Candidates are archive-style folders (tag, category, author, date, gallery or single-image folders, and the like). Ask exactly: "Which of these URL folders are JUNK (leave out of the audit and cover with one wildcard redirect)? Anything you don't pick stays in the audit as normal pages." as a multi-select, one option per folder, labelled with its size ("/tag/ - 81 pages, 1,240 impressions"); more than 4 candidates go over several questions of the same wording. Every option description says both outcomes: "Pick = junk: no audit rows, one wildcard redirect. Don't pick = audited as normal pages." Checked = junk, unchecked = normal pages. Never use the wording "not junk", and never mix the two meanings in one prompt. Re-run `work/build.py` with only the picked folders as junk before Step 6. List each junk folder's wildcard target in the report so the person can change it.

## Step 6: Recommendations and existing redirects

Write the Recommendations rows (references/rules.md) and the Existing Redirects rows (references/redirects-qa.md, in `work/redirects.py`). Run the QA in references/redirects-qa.md once, in code, on the final set. Done when the breaking checks return nothing, and every gap or consistency finding is either fixed or listed for the report.

## Step 7: Deliver the workbook

Follow references/sheet.md. Build one workbook with `scripts/make_xlsx.py` (tabs: Recommendations, Audit, Existing Redirects, Not in crawl) and deliver it once with SendUserFile. With Drive and Sheets connectors, also copy the template and write only the Recommendations rows by connector; never write the Audit through a connector, because that was the slow part of earlier runs. Done when the workbook is delivered (and, on the connector path, the Recommendations read-back matches).

## Step 8: Report

In chat, plain language. The person may not know the sheet's labels: whenever you use one (Check page type, Competes with, keeper, skim list, review queue, city copy), say what it means in the same sentence.
- The folder map and city decisions you used, the Search Console date range, and what happened with GA4 (file, pulled, or skipped and why).
- Counts per suggestion and the junk folders with their wildcards.
- The skim list and review queue counts (references/rules.md, Review triage).
- The findings that change the plan: demand with no page (the not-in-crawl list), case duplicates, menu links to redirected URLs (a menu link on every page is one template fix), Needs Discussion items, and redirects left with no target for the reviewer. Do not mention canonical problems here or in Recommendations; they live only in the affected page's Notes.
- The judgment calls, anything you could not get (no overlap data, missing export columns), how many pages had their type guessed from the URL wording (shown as Check page type in the sheet), and any differences from a pasted SOP.
- The next human step: work the review queue by page type. Skim-list rows only need the suggestion copied into Next Steps. Once Next Steps are filled in, the SOP's conflict check (Step 5) and its redirect-map check (Step 6) still need to run, because this skill's QA only covers its own suggestions.
