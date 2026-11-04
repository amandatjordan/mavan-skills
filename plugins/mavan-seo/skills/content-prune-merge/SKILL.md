---
name: content-prune-merge
description: Run Mavan's Content Prune & Merge audit for a client site from Sitebulb or Screaming Frog exports plus Search Console and GA4, and deliver a workbook with a Recommendations tab, one tab per issue and a dev redirect CSV tab. Use for prune, merge, or cannibalization audits.
---

# Content Prune & Merge

Decide, for every live page on a client site, whether to keep, update, repurpose, merge or remove it, and hand the SEO one workbook: a Recommendations tab, one tab per issue holding only the pages and data needed to check it, and a redirect tab the developer downloads as a CSV. This skill carries every rule it needs; it does not need access to the SOP. The SEO QAs the workbook and fills the cells marked SEO fill in before anything goes to an implementer.

Sites are built differently. Never assume folder names, page types, cities or a CMS: map this site's own structure first (Step 2) and let the person confirm it. Scripts apply the rules in references/ and do every count, match and join; they make no site-specific decision. Anything that depends on how this site is built (which folder is which page type, which words are cities, which pages are about the same topic, which folders are junk) is proposed by you from the data, shown to the person, confirmed, and saved as a file the scripts read. Never write your own audit code: run `scripts/build.py`, and if a rule seems not to fit this site, tell the person instead of working around it. Never fill a gap with fuzzy matching: when no exact match or confirmed rule decides a call, leave it for the reviewer and say so. The only assumption is that the client is an aesthetics business, which is why the vocabulary says treatments, concerns and locations.

`$SKILL` below is this skill's folder: the base directory shown when the skill loads. Set it once in the shell (`SKILL=<that folder>`). Scripts need Python 3 with pandas and openpyxl (`pip install --break-system-packages pandas openpyxl` if missing). Work in a folder named after the client with a `work/` subfolder and keep a task list with one item per step.

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
| 5 | How long the Search Console data covers | Required | The person has said how long the data covers (for example "last 90 days"). Ask for the length only, not exact dates. Never assume it. The recommended length is the last 90 days. |
| 6 | GA4 landing pages | Optional | A GA4 landing page file (Sessions, New users, Views, Key events) for the same dates, or nothing: see Step 3 for when GA4 is pulled and when it is skipped. |
| 7 | Domain | Required | Stated, or readable from the crawl URLs. |
| 8 | Cities | Required | The main city, and every other city or area the client wants its own pages for. Step 2 checks this list against the URL paths. |
| 9 | IA audit All Pages tab | Optional | When attached, its page types are used. |
| 10 | Newer copy of the SOP | Optional | When pasted, it wins over references/rules.md and the differences are listed in the report. |

Brand terms are handled in the Search Console export, so never ask for them. A Google Sheet link given with the command is the Search Console data (item 4) when it has Page and Query columns.

**If the person asks what is needed**, answer with this table in plain words, then ask for what they have not given.

**If anything required is missing**, send **one** message that lists only the missing items, one line each, saying what to provide (for crawl files, which export; for Search Console, the columns and how long the data covers), and points to the Content Prune & Merge SOP for the full export steps. Then stop and wait. Do not run a script, guess a missing value, or start with part of the inputs. A file that is not what it should be counts as missing (for example a links export with no CSS or link path column, or a Search Console sheet with no Query column): say what is wrong with it.

Load every file in code only; never print or paste one into the chat (the links file is often 20MB+). Make no requests to the live site: no sitemap fetches, no status checks, no redirect resolving. The crawl's status codes and the redirects export are the truth. The Sitebulb connector cannot replace the crawl files.

Done when items 1 to 5, 7 and 8 are provided, and you know whether GA4 comes from a file, from Composio, or is skipped.

## Step 2: Prepare the crawl, map the structure, confirm the cities

```
python $SKILL/scripts/prep.py --domain DOMAIN --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv --out work
```

It detects the crawler (and prints the columns it used; if it guesses wrong, pass `--crawler "Screaming Frog"` or `--crawler Sitebulb`), normalizes URLs, follows every redirect chain to where it ends, and classes every link Nav / Footer / Breadcrumb / Body from the CSS path (Sitebulb) or link path (Screaming Frog), because the crawlers' own location labels are unreliable. Read the printed class counts and path patterns. Done when menus land in Nav, footers in Footer, article copy in Body and there is no WARNING; otherwise re-run with `--nav-regex` / `--footer-regex` built from the paths shown. Theme menus often sit in short-ID containers the default pattern misses (SmartMenus `ul#sm-...`, sliders `swiper-wrapper`): when the crawler labels a Body-classed path Header or Footer in its own location column, extend the regex (keep the default by appending to it: `--nav-regex "$(python3 -c 'import sys;sys.path.insert(0,"'$SKILL/scripts'");import prep;print(prep.NAV_RE)')|#sm-"`).

Read `work/crawl_pages.csv` by its `primary` rows only: `/page` (301) and `/page/` (200) share one key, and the primary row is the live one. `work/redirects.csv` already has each redirect's `final` page, `hops`, full `chain` and `final_status`; rows with `normalization_only` True only add a slash or change case and need nothing. From the raw URL export, also note case-duplicate URLs (e.g. `/Page-Name/` returning 200 beside `/page-name/`) and `?utm_` variants (drop them). `prep.py` writes `work/canonical_issues.csv`: pages whose canonical points at a non-200 URL, including a canonical that redirects back to the page (`/a/` canonicalizes to `/a-2/`, which redirects to `/a/`). Each one gets the canonical flag in Notes (references/rules.md). Pagination URLs such as `?e-page-1a2b=2` canonicalize to the listing and get no audit rows.

**Map the structure.** Do not assume folder names. List every top-level URL folder of the live pages with its page count, 3 example URLs with titles, and the Page Type you think it is and why, plus one row for root-level pages (no folder). Map this site's own kinds of pages onto the Page Type values in references/rules.md: a page that makes the client money (a service, a product, a practice area) = Service; a page about a problem or topic the client treats = Concern / Condition; a city, branch or area page = Service Area / Location; a folder's own listing page, or a listing of a group of services or products = Hub / Category Page. Show the table as normal chat text first (folder | pages | example titles | proposed Page Type | why). Then ask only about the folders you are unsure of, one question per folder ("What type of page is everything under /xyz/?"), with the proposed type as the first option, marked "(Recommended)". If you are sure of every folder, ask nothing and say the map is below. Also name, from the root-level pages, any page that is a listing (the blog listing, a gallery page, a hub of services), the blog listing page itself, and any hub page that lists the client's concerns; show them in the same table. Save the map as `work/folder_map.json`: `{"folders": {"/folder/": "Page Type", "/one-root-page/": "Page Type"}, "blog_listing": "/blog/", "concern_hubs": ["/conditions/"]}` (exact page paths win over folders; leave `blog_listing` as `""` and `concern_hubs` as `[]` when the site has none).

**Confirm the cities.** `prep.py` writes `work/slug_words.csv`: every word used in live URL paths, with the number of pages and examples. Read it and pick out the place names (cities, neighborhoods, areas), together with the cities from pre-flight item 8. Show them as chat text (city | pages with it in the URL | 3 example URLs). Then, for each city, ask: "Should [city] be treated as a separate market with its own pages?" with two options: "Separate market" (pages named for it are location pages, and a service page that repeats another page for it is a city copy) and "Ignore in URLs" (the word says nothing about the page; use this for the main city when most URLs carry it). Recommend "Ignore in URLs" for the main city and "Separate market" for the others the person named. Ask about at most 4 cities per question round; cities with 1 or 2 pages can share one multi-select question ("Which of these are separate markets?").

Then list the service pages whose URL names a separate-market city but that have no twin with the same slug once the city is removed (for example `/services/brandname-microneedling-riverton/` beside `/services/microneedling-springfield/`), with the closest-looking page next to each, and ask the person which of them are copies of another page ("Which of these [city] pages repeat a page you already have?", multi-select). Never pair them yourself. Save everything as `work/cities.json`: `{"main": "...", "separate": [...], "ignore": [...], "copy_pairs": [[copy, original], ...]}`.

Done when every folder has a type the person has seen and every city found has a confirmed treatment.

## Step 3: Search Console and GA4

Follow references/data.md for reading the Search Console file. `scripts/build.py` (Step 4) builds the topic groups and the overlap list from it.

**GA4 is gated by Search Console clicks**, because GA4 often holds too little to use and pulling it costs time:
1. A GA4 file was attached: pass it to build.py with `--ga4` (no Composio).
2. No file and Search Console has under 300 clicks in the window: skip GA4, and say in one report line that GA4 was not pulled because the site had [N] Search Console clicks.
3. No file and 300+ clicks, with Composio connected: run the one monthly sessions report first (references/data.md). Under 200 sessions in the window: skip GA4 and say so with the total (and, if sessions collapse partway, tell the person to check the GA4 tag). 200 or more: pull the landing page report into `work/ga4.tsv` and pass it with `--ga4`.
4. No file and no Composio: leave GA4 blank and say so.

Done when you know whether GA4 is used, and the one line that says so (it goes to build.py as `--ga4-status` and into the workbook README).

## Step 4: Run the audit

```
python $SKILL/scripts/build.py --domain DOMAIN --work work --gsc GSC_FILE [--gsc-tab TAB] --window "last 90 days" [--ga4 work/ga4.tsv] --ga4-status "..."
```

It applies references/rules.md, data.md and redirects-qa.md in code, using only the files confirmed in Step 2, and writes the audit rows, the redirect rows, the pages Search Console has that the crawl does not, and a QA file. It never asks you to write code. Run it, then work through what it prints, in this order, re-running it after each change to a `work/` file:

1. **Junk folders.** `work/junk_candidates.csv` lists archive-style folders and folders of thin, unlinked pages. Show them as chat text (folder | rule matched | page count | total impressions | 5 example URLs | suggested wildcard target). Ask exactly: "Which of these URL folders are JUNK (leave out of the audit and cover with one wildcard redirect)? Anything you don't pick stays in the audit as normal pages." as a multi-select, one option per folder, labelled with its size ("/tag/ - 81 pages, 1,240 impressions"); more than 4 candidates go over several questions of the same wording. Every option description says both outcomes: "Pick = junk: no audit rows, one wildcard redirect. Don't pick = audited as normal pages." Never use the wording "not junk". Save the picked folders with their wildcard target as `work/junk.json` (`{"/tag/": "/blog/"}`). A target must be a live page the pattern does not match.
2. **Title topic groups.** `work/title_group_candidates.csv` lists the pages with under 20 impressions (too little data to share searches) with their titles. Propose groups of pages whose titles name the same treatment or concern, as chat text (group | pages | the title words they share), and ask the person to confirm or correct them in one question. Save the confirmed groups as `work/title_groups.json` (`[["/page-a/", "/page-b/"], ...]`). Never group by fuzzy slug matching.
3. **Rules 5 and 6** (references/rules.md). `work/rule5_candidates.csv` lists blog posts whose searches include a location, "near me" or a price word, with no service page on the topic; `work/rule6_candidates.csv` lists service pages with a URL word few searchers use. Read each candidate's searches and decide: rule 5 applies when the searches are someone looking to buy or book; rule 6 when the page is named for a brand or product and searchers use the treatment or problem instead. Save each confirmed page in `work/overrides.json` as `{"/page/": {"step": "Repurpose", "rule": 5, "query": "<top matching search>"}}` (or `"Update"` and `6`).
4. **Judgment calls** (thin stubs, Needs Discussion, anything the rules do not cover): add them to `work/overrides.json` with `step`, `target` when it merges or redirects, and a `why` sentence. They are marked "judgment".
5. **QA.** Read `work/qa.txt`. Done when it has no BREAKING line and every GAP is fixed or listed for the report.

Leave Referring Domains blank. Done when the QA is clean and the counts printed per page type and per suggestion look right to you.

## Step 5: Deliver the workbook

Follow references/deliverable.md:

```
python $SKILL/scripts/make_xlsx.py --work work --rules $SKILL/references/rules.md --out "{Client} Content Prune & Merge.xlsx"
```

Deliver the file once with SendUserFile. Use no Google Drive or Sheets connector. Done when the workbook is delivered.

## Step 6: Report

In chat, plain language. The person may not know the workbook's labels: whenever you use one (Check page type, keeper, location copy), say what it means in the same sentence.
- The tabs in the workbook with their row counts.
- The folder map and city decisions you used, how long the Search Console data covers, and what happened with GA4 (file, pulled, or skipped and why).
- The junk folders with their wildcards, so the person can change a target.
- The findings that change the plan: demand with no page (`work/not_in_crawl.tsv`), case duplicates, menu links to redirected URLs (a menu link on every page is one template fix), Needs Discussion items, and the old URLs left with no target (Redirects needing a target tab). Do not mention canonical problems; they live only in the affected page's Why text.
- Internal links to update (`work/internal_links_to_update.csv`, references/redirects-qa.md): Nav and Footer links first, since one template edit fixes them sitewide. Give it as a separate file when it is long. Case duplicates are in `work/case_duplicates.csv`.
- The judgment calls, anything you could not get (no overlap data, missing export columns), and any differences from a pasted SOP.
- The next human step: QA the tabs in the Recommendations order and fill every SEO fill in cell, then hand off each tab to the owner named on the Recommendations tab.

## If the SEO changes Check page type or Kept pages

This only works in the same chat where the audit ran (a new chat has neither the rules nor the `work/` files). Ask the person to attach the edited workbook. Read only the Check page type and Kept pages tabs from it, in code. Put each changed page type in `work/overrides.json` as `page_type` (with `why`: "Changed by the SEO"), and each Kept pages change as `step` and `target`. Re-run build.py and make_xlsx.py, deliver the new workbook, and list what moved between tabs.
