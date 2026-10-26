---
name: information-architecture-audit
description: Run Mavan's information architecture (IA) audit for a client site from Sitebulb or Screaming Frog exports plus Search Console and GA4 through Composio, and fill the IA Audit template sheet. Use for IA audits, site architecture or site structure audits, and pre-migration or pre-rebuild structure reviews.
---

# Information Architecture Audit (Mavan SOP)

This skill carries the whole process: it is the Information Architecture Audit SOP's prompt turned into scripts, plus the judgment calls the scripts can't make. It does not need the written SOP; a copy in a project management tool is documentation for people. The output is a diagnosis with suggested actions, not the new structure: a person decides the target architecture.

Template (v2): https://docs.google.com/spreadsheets/d/16Gw6vVDIR4nKr8bpupmI4hsTKDuExURly3Z5rmmn1a8/edit (file id `16Gw6vVDIR4nKr8bpupmI4hsTKDuExURly3Z5rmmn1a8`).

Scripts do every count, match and join; never estimate a number by reading. `$SKILL` below is this skill's folder: the base directory shown when the skill loads (`${CLAUDE_SKILL_DIR}` in Claude Code). Set it once in the shell, e.g. `SKILL=<that folder>`. Scripts need Python 3 with pandas and openpyxl (`pip install --break-system-packages pandas openpyxl` if missing). Work in a folder named after the client (e.g. `client-ia/`) with a `work/` subfolder, and keep a task list with one item per step below.

Assume nothing about the site's URL structure. Folder names, depth and naming differ on every site, so the skill learns the structure from the crawl and a person confirms it (Step 3) before any page is classified.

## What you need

- **Crawl exports**, every URL not just 200s: (1) URL export, (2) all internal links export, (3) redirects export. Sitebulb or Screaming Frog. Ask for them if missing, naming the exports: Sitebulb URL Explorer > Internal > HTML (URL, HTTP Status Code, Indexable Status, Crawl Depth, Path Depth, Crawl Source, Title, H1, first H2, No. Content Words, No. Internal Links to URL; no GSC or GA columns), Links > Internal Links (Target URL, Anchor Text, Linking URL, Location, CSS Path, Image) and the Redirects report; Screaming Frog Internal > HTML (Address, Status Code, Indexability, Indexability Status, Title 1, H1-1, H2-1, Word Count, Crawl Depth, Folder Depth, Unique Inlinks), Bulk Export > Links > All Inlinks (Source, Destination, Anchor, Status Code, Link Position, Link Path, Type) and Reports > Redirects > All Redirects. The Sitebulb connector cannot replace them (it returns 50 sample URLs per query).
- **Client facts**: business name, domain, main city and state, other cities targeted, brand terms (name and nicknames). Ask in one question for whatever the request doesn't give; work out what you can from the site first.
- **Optional**: the client's existing redirect list (e.g. a redirect plugin export) and past prune & merge decisions. Skip anything about them when they aren't attached.
- **Composio** connector with Google Search Console and Google Analytics connected, using a Google account that has access to the client's properties (set up once per account in Composio). Without it the audit still runs: the search columns stay blank and the Read Me says why.

## Step 1: Template

Download the template with the Google Drive connector: `download_file_content` on the file id above with `exportMimeType` `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. The result is saved to a tool-results file; turn it into the workbook:

```
python $SKILL/scripts/save_drive_xlsx.py <saved result file> work/template.xlsx
```

If the Drive connector isn't available, ask the person to attach the template downloaded as .xlsx. Done when `work/template.xlsx` exists and the script printed "Saved".

## Step 2: Crawl exports

```
python $SKILL/scripts/prep.py --domain DOMAIN --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv \
  [--client-redirects LIST.csv] --out work
```

Links are classed Nav / Footer / Breadcrumb / Body from the CSS path or link path, because Sitebulb labels almost every link "Navigation". Read the printed class counts and the most common paths per class. Done when menus land in Nav, footers in Footer, article copy in Body, and there's no WARNING. If a menu or footer container is landing in Body (or 95%+ of links are Nav), re-run with `--nav-regex` / `--footer-regex` built from the paths shown.

## Step 3: Folder profile and mapping (stop and confirm)

```
python $SKILL/scripts/folder_profile.py --work work [--deep folder1,folder2]
```

It profiles every first-level folder and the root level (live pages, share, sample pages with titles and H1s, median words, how many pages read like articles) and proposes a page type per folder. A common folder name is one piece of evidence, not the answer. Folders over 30 pages also get their second-level folders profiled; pass `--deep` to force it for others.

**Send `work/review/folder_mapping.md` to the person in the chat and STOP.** Do not classify any page until they confirm or correct it. In the message, say which folder(s) hold the blog and which hold services (or that none exist), and flag every Low-confidence row. If the blog folder is not one of /blog/, /blogs/, /articles/, /news/ or /resources/, say so: the template's Area formula only recognises those five, so every post would be tagged "Blog URLs" on All Pages.

When they reply, write their mapping to `work/decisions.json` (create it if needed) and set the flag that lets analyze.py run:

```json
{"mapping_confirmed": true,
 "folder_types": {"procedures": "Service", "journal": "Blog", "before-after": "Gallery item", "resources": "Mixed"},
 "blog_folder": "/journal/", "service_folder": "/procedures/"}
```

Types a folder can take: Service, Concern, Blog, Location / Area, Company / Info, Gallery item, Archive, Utility / Policy, Mixed (each page is typed from its slug and H1), or any other name, which becomes "Name (folder)". The root level is always typed page by page. To type a second-level folder on its own, map its parent as Mixed and add `"parent/child"` as a key. Done when the person has confirmed and `mapping_confirmed` is true.

## Step 4: Search Console and GA4 through Composio

Follow [references/composio.md](references/composio.md). The window is the last 6 full calendar months. Composio keeps large API responses in its own sandbox and returns at most ~40KB per call, so the script `gsc_workbench.py` does the heavy work there and prints compact, checksummed tables that you save here. Done when `python $SKILL/scripts/gsc_import.py --dir work/gsc` prints "Loaded" with no PROBLEMS. If Search Console has no property for the domain, say so and continue without it; the scripts leave those columns blank and the Read Me says why.

## Step 5: Analyze and review

Write `work/config.json`:

```json
{"client": "Example Med Spa", "domain": "examplemedspa.com", "city": "Springfield, IL",
 "other_cities": ["Chatham", "Rochester"], "brand_terms": ["example med spa", "example"],
 "crawler": "Sitebulb", "crawl_date": "2026-10-20"}
```

Then run `python $SKILL/scripts/analyze.py --work work [--past PAST.csv]`. It stops if the folder mapping isn't confirmed (`--allow-unconfirmed` exists for tests only; never use it for a client). Work through `work/review/next_steps.md` using [references/review.md](references/review.md): page types, topics, duplicate pairs, and the follow-up Composio call it prints. Corrections go in `work/decisions.json`; re-run analyze.py after each round. Done when next_steps.md asks for nothing more: no "check" pairs, no Composio calls left to run, no folders missing from the mapping, Unclassified pages either labeled or left on purpose for the chat summary, and you have opened 5 rows per page type in `work/review/page_types.csv` and agree with them.

## Step 6: Recommendations and Read Me notes

Add the Recommendations rows, Read Me notes and any tab notes to `work/decisions.json`, following [references/recommendations.md](references/recommendations.md). Take every number from `work/analysis/summary.json` or the analysis CSVs.

## Step 7: Fill and check

```
python $SKILL/scripts/fill.py --work work --template work/template.xlsx --out "CLIENT Information Architecture Audit.xlsx"
```

fill.py writes values only, into the data cells under the template's headers, and keeps the template's tabs, headers, hover notes, dropdowns, colours and formulas. The only formulas in the template are All Pages column C (Area, copied down) and Recommendations column F (Pages); it never writes any other. It counts the template's dropdowns, conditional formats and hover notes before and after and stops if any changed. It then runs the automated QA: redirect targets live and not themselves redirected, wildcards not matching their own targets, every required topic covered by a Recommendations row, Areas that the Pages formula counts correctly, no placeholder text left, no recommendation to add links to blog posts. Done when it prints "All checks passed". Fix each listed problem at its source (decisions.json, or a re-run of analyze.py) rather than editing the workbook. Then compare the printed Area counts with the numbers in your Recommendations text.

## Step 8: Deliver

Send the .xlsx. In the reply:
- 5-7 headline findings in plain language.
- The Unclassified pages, if any.
- Anything you could not do (no GA4, no Search Console, missing export columns) and anything else from Read Me "Missing / uncertain".
- How to get it into Sheets: new blank Google Sheet named "[Client] Information Architecture Audit", File > Import > Upload > **Replace spreadsheet**, then spot-check that the Area column and the Recommendations Pages column show numbers.
