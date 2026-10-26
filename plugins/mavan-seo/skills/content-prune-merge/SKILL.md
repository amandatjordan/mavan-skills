---
name: content-prune-merge
description: Run Mavan's Content Prune & Merge audit for a client site from Sitebulb or Screaming Frog exports plus Search Console and GA4, and fill a client copy of the Prune & Merge template sheet. Use for prune, merge, or cannibalization audits.
---

# Content Prune & Merge

Decide, for every live page on a client site, whether to keep, update, repurpose, merge or remove it, and hand the reviewer a filled template with suggestions, a Recommendations TL;DR and a clean redirect list. This skill carries every rule it needs; it does not need access to the SOP. A person makes the final calls: fill the Suggested columns and leave Next Steps, Target URL and Reasoning blank.

Sites are built differently. Never assume folder names, page types or a CMS: map this site's own structure first (Step 2). The only assumption is that the client is an aesthetics business, which is why the vocabulary says treatments, concerns and locations.

`$SKILL` below is this skill's folder: the base directory shown when the skill loads. Set it once in the shell (`SKILL=<that folder>`). Scripts need Python 3 with pandas (`pip install --break-system-packages pandas` if missing). Work in a folder named after the client with a `work/` subfolder, do every count, match and join in code, and keep a task list with one item per step.

## What you need

- **Crawl exports** from Sitebulb or Screaming Frog: (1) URL export (every URL, not just 200s), (2) all internal links export, (3) redirects/errors export. Sitebulb: the URLs export, Links > Internal Links, and the redirected URLs export. Screaming Frog: Internal > All, Bulk Export > Links > All Inlinks, and Response Codes > Redirection (3xx) / Client Error (4xx). The Sitebulb connector cannot replace these files. Load these files in code only, never print or paste one into the chat; the links file is often 20MB+.
- **Client facts**: domain, main city, brand terms (client name, doctor's name, misspellings). Ask in one question for whatever is missing.
- **Optional**: a bulk backlink export (referring domains per page, from Ahrefs or Semrush), an IA audit All Pages tab (use it only when the person asks), a newer pasted copy of the SOP (it wins over references/rules.md; list the differences in the report).

## Step 1: Check access

Before any work, check which tools this session has and tell the person in one short message what you will do for each gap:

| Need | With it | Without it |
| --- | --- | --- |
| Composio with Search Console + GA4 | pull the data yourself (references/data.md) | ask for the exports listed in references/data.md |
| Google Drive + Sheets connectors | copy the template and fill it (references/sheet.md) | hand back .tsv files with paste steps |
| Web access to the live site (Composio workbench or WebFetch) | sitemap and status checks (Step 4) | ask whether the crawl included the XML sitemap; mark 404s "per crawl" |

Done when every row above has a chosen path and the person has been told about any gaps.

## Step 2: Prepare the crawl and map the structure

```
python $SKILL/scripts/prep.py --domain DOMAIN --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv --out work
```

It detects the crawler, normalizes URLs, and classes every link Nav / Footer / Breadcrumb / Body from the CSS path (Sitebulb) or link path (Screaming Frog), because the crawlers' own location labels are unreliable. Read the printed class counts and path patterns. Done when menus land in Nav, footers in Footer, article copy in Body and there is no WARNING; otherwise re-run with `--nav-regex` / `--footer-regex` built from the paths shown. Theme menus often sit in short-ID containers the default pattern misses (SmartMenus `ul#sm-...`, sliders `swiper-wrapper`): when the crawler labels a Body-classed path Header or Footer in its own location column, extend the regex (keep the default by appending to it: `--nav-regex "$(python3 -c 'import sys;sys.path.insert(0,"'$SKILL/scripts'");import prep;print(prep.NAV_RE)')|#sm-"`).

From the raw URL export, also note case-duplicate URLs (e.g. `/Page-Name/` returning 200 beside `/page-name/`), `?utm_` variants (drop them), and canonicals pointing at non-200 URLs.

**Map the structure.** Do not assume folder names. List every top-level URL folder of the live pages with its page count, 3 example URLs with titles, and the Page Type you think it is and why, plus one row for root-level pages (no folder). Map this site's own kinds of pages onto the Page Type values in references/rules.md: a page that makes the client money (a service, a product, a practice area) = Service; a page about a problem or topic the client treats = Concern / Condition; a city, branch or area page = Service Area / Location; a folder's own listing page, or a listing of a group of services or products = Hub / Category Page. Show the table to the person, ask once about any folder you are unsure of, and save the confirmed map as `work/folder_map.json`. Done when every folder has a type the person has seen.

## Step 3: Search Console and GA4

Follow references/data.md: the size check, page metrics, non-brand query counts, topic groups and the overlap list, and the migration check only when the crawl or the person points to a migration. Done when every live page has its metrics (or a stated reason it has none) and the overlap list is built, or the report says why it could not be.

## Step 4: Find what the crawl missed

Fetch `robots.txt` and the XML sitemap index (Yoast: `/sitemap_index.xml`; WordPress core: `/wp-sitemap.xml`; other platforms: usually `/sitemap.xml`), list sitemap URLs that are not in the crawl, and request each one. Also request every non-live URL that has GSC impressions or GA4 sessions. Done when every sitemap-only URL and every non-live URL with demand has a status code. Category, tag, author and date archives found here belong to junk folders.

## Step 5: Build the Audit rows

Write `work/build.py` so reruns are one command. Apply references/rules.md in order: Page Type (from `work/folder_map.json`), Suggested Next Step and Target, Notes, junk folders. Fill Referring Domains from the bulk backlink export when one was given, matched on the normalized URL, and leave it blank otherwise. Keep judgment overrides in one dict with a reason string each, and mark them "judgment" in Notes. Done when every live page has a row (or sits in a junk folder), every Merge/Remove row has a full target URL whose own suggestion is Keep, Update, Repurpose or Needs Discussion, and the counts per Page Type and per suggestion are printed.

Then show the junk-folder candidates (rule matched, page count, clicks, impressions, 5 example URLs, wildcard target) and ask once which folders, if any, are not junk. Re-run `work/build.py` with those folders treated as normal pages before Step 6.

## Step 6: Recommendations and existing redirects

Write the Recommendations rows (references/rules.md) and the Existing Redirects rows (references/redirects-qa.md, in `work/redirects.py`). Run the QA in references/redirects-qa.md once, in code, on the final set. Done when the breaking checks return nothing, and every gap or consistency finding is either fixed or listed for the report.

## Step 7: Fill the template

Follow references/sheet.md. Done when the read-back matches the source rows cell for cell (connector path), or the three .tsv files are delivered with paste steps (no-connector path).

## Step 8: Report

In chat, plain language:
- The folder map you used, the analysis window and why, and whether a migration was found or the check was skipped.
- Counts per suggestion and the junk folders with their wildcards.
- The skim list and review queue counts (references/rules.md, Review triage).
- The findings that change the plan: archives the crawl missed, demand with no page (404s or gaps), technical bugs (broken canonicals, case duplicates), menu links to pages being redirected, Needs Discussion items.
- The judgment calls, anything you could not get (no overlap data, no GA4, no page + query export, missing export columns), and any differences from a pasted SOP.
- The next human step: pull Referring Domains for every Merge and Remove row that has none, then work the review queue by page type. Skim-list rows only need the suggestion copied into Next Steps.
