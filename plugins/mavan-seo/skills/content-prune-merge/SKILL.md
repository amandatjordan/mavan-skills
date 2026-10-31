---
name: content-prune-merge
description: Run Mavan's Content Prune & Merge audit for a client site from Sitebulb or Screaming Frog exports plus Search Console and GA4, and deliver one workbook that fills the Prune & Merge template sheet. Use for prune, merge, or cannibalization audits.
---

# Content Prune & Merge

Decide, for every live page on a client site, whether to keep, update, repurpose, merge or remove it, and hand the reviewer one workbook with suggestions, a Recommendations TL;DR and a clean redirect list. This skill carries every rule it needs; it does not need access to the SOP. A person makes the final calls: fill the Suggested columns and leave Next Steps, Target URL and Reasoning blank.

Sites are built differently. Never assume folder names, page types or a CMS: map this site's own structure first (Step 2). The only assumption is that the client is an aesthetics business, which is why the vocabulary says treatments, concerns and locations.

`$SKILL` below is this skill's folder: the base directory shown when the skill loads. Set it once in the shell (`SKILL=<that folder>`). Scripts need Python 3 with pandas and openpyxl (`pip install --break-system-packages pandas openpyxl` if missing). Work in a folder named after the client with a `work/` subfolder, do every count, match and join in code, and keep a task list with one item per step.

## What you need

- **Crawl exports** from Sitebulb or Screaming Frog, all three required: (1) URL export (every URL, not just 200s), (2) all internal links export, (3) **redirects export**, which gives the target of every 3XX. Sitebulb: the URLs export, Links > Internal Links, and the redirected URLs export. Screaming Frog: Internal > All, Bulk Export > Links > All Inlinks, and Response Codes > Redirection (3xx) > Export (or Reports > Redirects > All Redirects). Without the redirects export the redirect map cannot be built, and redirects are never resolved with live requests. The Sitebulb connector cannot replace these files. Load these files in code only, never print or paste one into the chat; the links file is often 20MB+.
- **Search Console and GA4 files** for the last 90 days, ending 3 days ago: Search Console page + query, Search Console pages, GA4 landing pages (references/data.md has the exact exports). Ask for them at the start, with the window stated.
- **Client facts**: domain and main city. Brand terms are handled in the Search Console export, so do not ask for them.
- **Optional**: an IA audit All Pages tab (when one is attached, use its page types), a newer pasted copy of the SOP (it wins over references/rules.md; list the differences in the report).

**Start fast.** Do not ask permission to start. Ask for everything that is missing (files, domain, main city) in one first message, then begin as soon as the crawl exports are attached. Run `prep.py` and the build in code, and call a connector only for the small Recommendations tab.

**How to ask.** Every question the person has to answer follows these rules:
- Put the single decision in the question text, as a direct question ending in a question mark ("Which of these URL folders are JUNK?"). Never leave the decision only in the option descriptions.
- One decision per question. Do not combine a table of folders and several decisions in one prompt.
- Option labels name the thing and its size ("/tag/ - 81 pages"). Option descriptions say what picking it does.
- Put tables and long lists in the chat text first, and keep the question itself short.

## Step 1: Check access

Before any work, check which tools this session has and tell the person in one short message what you will do for each gap:

| Need | With it | Without it |
| --- | --- | --- |
| Search Console files | read them (references/data.md) | Composio, if connected; otherwise say what is missing |
| GA4 landing page file | read it | pull it through Composio yourself (filtered as in references/data.md) when it is connected and no file was attached; otherwise leave GA4 blank and say so |
| Google Drive + Sheets connectors | copy the template and write only the Recommendations tab by connector (references/sheet.md) | the workbook alone, with paste steps |

This skill makes no requests to the live site: no sitemap fetches, no status checks, no redirect resolving. The crawl's status codes and the redirects export are the truth. Done when every row above has a chosen path and the person has been told about any gaps.

## Step 2: Prepare the crawl and map the structure

```
python $SKILL/scripts/prep.py --domain DOMAIN --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv --out work
```

It detects the crawler (and prints the columns it used; if it guesses wrong, pass `--crawler "Screaming Frog"` or `--crawler Sitebulb`), normalizes URLs, and classes every link Nav / Footer / Breadcrumb / Body from the CSS path (Sitebulb) or link path (Screaming Frog), because the crawlers' own location labels are unreliable. Read the printed class counts and path patterns. Done when menus land in Nav, footers in Footer, article copy in Body and there is no WARNING; otherwise re-run with `--nav-regex` / `--footer-regex` built from the paths shown. Theme menus often sit in short-ID containers the default pattern misses (SmartMenus `ul#sm-...`, sliders `swiper-wrapper`): when the crawler labels a Body-classed path Header or Footer in its own location column, extend the regex (keep the default by appending to it: `--nav-regex "$(python3 -c 'import sys;sys.path.insert(0,"'$SKILL/scripts'");import prep;print(prep.NAV_RE)')|#sm-"`).

From the raw URL export, also note case-duplicate URLs (e.g. `/Page-Name/` returning 200 beside `/page-name/`) and `?utm_` variants (drop them). `prep.py` writes `work/canonical_issues.csv`: pages whose canonical points at a non-200 URL, including a canonical that redirects back to the page (`/a/` canonicalizes to `/a-2/`, which redirects to `/a/`). Each one gets the canonical flag in Notes (references/rules.md). Pagination URLs such as `?e-page-1a2b=2` canonicalize to the listing and get no audit rows.

**Map the structure.** Do not assume folder names. List every top-level URL folder of the live pages with its page count, 3 example URLs with titles, and the Page Type you think it is and why, plus one row for root-level pages (no folder). Map this site's own kinds of pages onto the Page Type values in references/rules.md: a page that makes the client money (a service, a product, a practice area) = Service; a page about a problem or topic the client treats = Concern / Condition; a city, branch or area page = Service Area / Location; a folder's own listing page, or a listing of a group of services or products = Hub / Category Page. Show the table as normal chat text first (folder | pages | example titles | proposed Page Type | why). Then ask only about the folders you are unsure of, one question per folder ("What type of page is everything under /xyz/?"), with the proposed type as the first option, marked "(Recommended)". If you are sure of every folder, ask nothing and say the map is below. Save the map as `work/folder_map.json`. Done when every folder has a type the person has seen.

## Step 3: Search Console and GA4

Follow references/data.md: read the files for the 90-day window, get GA4 (through Composio when no file was attached), apply the 200-session rule, build the overlap list. If total GA4 sessions in the window are under 200, skip GA4: leave Conversions, New Users, Sessions and Views blank, spend no more time on it, and say in one report line that GA4 was skipped and why, with the total. Done when every live page has its metrics (or the stated reason GA4 was skipped) and the overlap list is built, or the report says why it could not be.

## Step 4: List the demand the crawl missed

No live requests. Build `work/not_in_crawl.tsv` (references/data.md): every URL in Search Console or GA4 that is not in the crawl, with clicks, impressions, sessions and its redirect target when the redirects export has one. Use the sitemap only if it is already in the crawl data. Category, tag, author and date archives found this way belong to junk folders. Done when the file exists and its row count is in the report.

## Step 5: Build the Audit rows

Write `work/build.py` so reruns are one command. Apply references/rules.md in order: Page Type (from `work/folder_map.json`), Suggested Next Step and Target, Notes, junk folders. Leave Referring Domains blank. Keep judgment overrides in one dict with a reason string each, and mark them "judgment" in Notes. Done when every live page has a row (or sits in a junk folder), every Merge/Remove row has a full target URL whose own suggestion is Keep, Update, Repurpose or Needs Discussion, and the counts per Page Type and per suggestion are printed.

Then show the junk-folder candidates as chat text (folder | rule matched | page count | total impressions | 5 example URLs | suggested wildcard target). Candidates are archive-style folders (tag, category, author, date, gallery or single-image folders, and the like). Ask exactly: "Which of these URL folders are JUNK (leave out of the audit and cover with one wildcard redirect)? Anything you don't pick stays in the audit as normal pages." as a multi-select, one option per folder, labelled with its size ("/tag/ - 81 pages, 1,240 impressions"). Every option description says both outcomes: "Pick = junk: no audit rows, one wildcard redirect. Don't pick = audited as normal pages." Checked = junk, unchecked = normal pages. Never use the wording "not junk", and never mix the two meanings in one prompt. Re-run `work/build.py` with only the picked folders as junk before Step 6. List each junk folder's wildcard target in the report so the person can change it.

## Step 6: Recommendations and existing redirects

Write the Recommendations rows (references/rules.md) and the Existing Redirects rows (references/redirects-qa.md, in `work/redirects.py`). Run the QA in references/redirects-qa.md once, in code, on the final set. Done when the breaking checks return nothing, and every gap or consistency finding is either fixed or listed for the report.

## Step 7: Deliver the workbook

Follow references/sheet.md. Build one workbook with `scripts/make_xlsx.py` (tabs: Recommendations, Audit, Existing Redirects, Not in crawl) and deliver it once with SendUserFile. With Drive and Sheets connectors, also copy the template and write only the Recommendations rows by connector; never write the Audit through a connector, because that was the slow part of earlier runs. Done when the workbook is delivered (and, on the connector path, the Recommendations read-back matches).

## Step 8: Report

In chat, plain language:
- The folder map you used, the 90-day window, and the result of the GA4 sanity check.
- Counts per suggestion and the junk folders with their wildcards.
- The skim list and review queue counts (references/rules.md, Review triage).
- The findings that change the plan: demand with no page (the not-in-crawl list), case duplicates, menu links to pages being redirected, Needs Discussion items. Do not mention canonical problems here or in Recommendations; they live only in the affected page's Notes.
- The judgment calls, anything you could not get (no overlap data, GA4 skipped and the total, no page + query export, missing export columns), how many pages are typed only by slug rules (Check page type), and any differences from a pasted SOP.
- If GA4 sessions collapse partway through a monthly report, one line telling the person to check the GA4 tag.
- The next human step: work the review queue by page type. Skim-list rows only need the suggestion copied into Next Steps. Once Next Steps are filled in, the SOP's Step 6 check and its final redirect-map check (Step 7) still need to run, because this skill's QA only covers its own suggestions.
