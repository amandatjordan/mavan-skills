---
name: information-architecture-audit
description: Run Mavan's information architecture (IA) audit for a client site from Sitebulb or Screaming Frog exports plus a Google Sheet of Search Console data (GA4 optional, through Composio), and fill the IA Audit template sheet. If the client has a content prune & merge workbook, checks the page types against it. Use for IA audits, site architecture or site structure audits, and pre-migration or pre-rebuild structure reviews.
---

# Information Architecture Audit (Mavan SOP)

This skill carries the whole process: it is the Information Architecture Audit SOP's prompt turned into scripts, plus the judgment calls the scripts can't make. It does not need the written SOP; a copy in a project management tool is documentation for people. The output is a diagnosis with suggested actions, not the new structure: a person decides the target architecture.

Template (v2): https://docs.google.com/spreadsheets/d/16Gw6vVDIR4nKr8bpupmI4hsTKDuExURly3Z5rmmn1a8/edit (file id `16Gw6vVDIR4nKr8bpupmI4hsTKDuExURly3Z5rmmn1a8`).

Scripts do every count, match and join; never estimate a number by reading. `$SKILL` below is this skill's folder: the base directory shown when the skill loads. Set it once in the shell, e.g. `SKILL=<that folder>`. Scripts need Python 3 with pandas and openpyxl (`pip install --break-system-packages pandas openpyxl` if missing). Work in a folder named after the client (e.g. `client-ia/`) with a `work/` subfolder, and keep a task list with one item per step below.

Assume nothing about the site's URL structure. Folder names, depth and naming differ on every site, so the skill learns the structure from the crawl and a person confirms it (Step 3) before any page is classified.

**The audit is always of the whole site.** A request to "focus on" the service pages, or a crawl export filtered to some pages, does not change what the audit needs: page types, links and duplicates are judged against every other page. Run the full site and put the service-page findings first in the summary.

## What you need

- **Crawl exports**, every URL not just 200s: (1) URL export, (2) all internal links export, (3) redirects export. Sitebulb or Screaming Frog. Ask for them if missing, naming the exports: Sitebulb URL Explorer > Internal > HTML (URL, HTTP Status Code, Indexable Status, Crawl Depth, Path Depth, Crawl Source, Title, H1, first H2, No. Content Words, No. Internal Links to URL; no GSC or GA columns), Links > Internal Links (Target URL, Anchor Text, Linking URL, Location, CSS Path, Image) and the Redirects report; Screaming Frog Internal > HTML (Address, Status Code, Indexability, Indexability Status, Title 1, H1-1, H2-1, Word Count, Crawl Depth, Folder Depth, Unique Inlinks), Bulk Export > Links > All Inlinks (Source, Destination, Anchor, Status Code, Link Position, Link Path, Type) and Reports > Redirects > All Redirects. The Sitebulb connector cannot replace them (it returns 50 sample URLs per query). A filtered export (for example "on page filtered", only some pages) is not the URL export.
- **Client facts**: business name, domain, main city and state, other cities targeted, brand terms (name and nicknames). Ask in one question for whatever the request doesn't give; work out what you can from the site first.
- **Search Console data**: a Google Sheet (attached, or as an .xlsx download) of page + query rows with the columns Page, Query, Clicks, Impressions (CTR and Position are used when present), for about the last 6 months, in a tab named "Claude Use This" (Mavan's Search Console template; otherwise the one tab with those columns). The sheet does not say which dates it covers, so ask the person for the start and end dates. If the person has no sheet, the audit still runs: the search columns stay blank and the Read Me says why.
- **GA4** (optional): only when the person wants it. It comes through the **Composio** connector with Google Analytics connected (Step 4). Many clients have too little traffic for GA4 to matter; if the person says to skip it, skip it, and do not touch Composio at all. Search Console never uses Composio.
- **Optional, a content prune & merge workbook** (the Prune & Merge template, from the content-prune-merge skill): not every client has one. When it is attached, its page types are checked against this audit's and its Suggested Next Step is read as the plan (Steps 3 and 5). Skip everything about it when it isn't attached.
- **Optional**: the client's existing redirect list (e.g. a redirect plugin export) and past prune decisions as a CSV (url, decision, target). Skip anything about them when they aren't attached.

## Step 0: Preflight (always first)

Collect every file the request attached or linked and run:

```
python $SKILL/scripts/preflight.py --domain DOMAIN --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv \
  --template work/template.xlsx --gsc-sheet GSC.xlsx --gsc-start YYYY-MM-DD --gsc-end YYYY-MM-DD \
  [--prune PRUNE.xlsx] [--client-redirects LIST.csv] --ga4 yes|no \
  --client "Name" --city "City, ST" --brand "term,term" --out work
```

Leave out an argument you do not have yet and the preflight reports it missing. (The template is fetched in Step 1; run the preflight once without it if you like, then again.) It reads headers and a sample only, so it takes seconds. It checks that each export is the right kind (for example a filtered on-page export is not the URL export; the links file has source, target and path columns), that the URL export has non-200 rows and the homepage, that the exports come from the same crawl (dates in the file names), that the template has all 11 tabs (a link to the Search Console data sheet is a common mix-up), that the Search Console sheet is a page + query export for this domain with a date range, that the optional prune workbook is the Prune & Merge workbook, and what the client facts still lack.

Read `work/preflight.md`. If it says NOT READY, send the person **one** message that lists each FAIL and says exactly which export or answer is needed and where to get it (the export names above), then stop. Do not build around a missing input, for example by reading URLs out of the links file in place of the URL export. Offer to continue without an input only for the ones the preflight can skip (redirects, Search Console sheet), say what the audit loses, and use `--skip` only after the person agrees. Mention each WARN in the final reply. Done when the preflight says READY.

## Step 1: Template

Download the template with the Google Drive connector: `download_file_content` on the file id above with `exportMimeType` `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. The result is saved to a tool-results file; turn it into the workbook:

```
python $SKILL/scripts/save_drive_xlsx.py <saved result file> work/template.xlsx
```

If the Drive connector isn't available, ask the person to attach the template downloaded as .xlsx. Done when `work/template.xlsx` exists and the script printed "Saved". A Google Sheets link in the request is not necessarily this template: it can be the Search Console data sheet. Use the template id above unless the person says they have a newer IA template, and let the preflight check the tabs.

## Step 2: Crawl exports

```
python $SKILL/scripts/prep.py --domain DOMAIN --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv \
  [--client-redirects LIST.csv] --out work
```

Links are classed Nav / Footer / Breadcrumb / Body from the CSS path or link path, because Sitebulb labels almost every link "Navigation". Read the printed class counts and the most common paths per class. Done when menus land in Nav, footers in Footer, article copy in Body, and there's no WARNING. If a menu or footer container is landing in Body (or 95%+ of links are Nav), re-run with `--nav-regex` / `--footer-regex` built from the paths shown.

## Step 3: Folder profile and mapping (stop and confirm)

If a prune workbook was provided, read it first (it is also used in Step 5):

```
python $SKILL/scripts/prune_import.py --workbook PRUNE.xlsx --domain DOMAIN --out work
```

It prints the prune workbook's page types per folder and writes `work/prune.csv` and `work/past.csv`.

```
python $SKILL/scripts/folder_profile.py --work work [--deep folder1,folder2]
```

It profiles every first-level folder and the root level (live pages, share, sample pages with titles and H1s, median words, how many pages read like articles) and proposes a page type per folder. A common folder name is one piece of evidence, not the answer. Folders over 30 pages also get their second-level folders profiled; pass `--deep` to force it for others.

**Send `work/review/folder_mapping.md` to the person in the chat and STOP.** Do not classify any page until they confirm or correct it. In the message, say which folder(s) hold the blog and which hold services (or that none exist), and flag every Low-confidence row. If the blog folder is not one of /blog/, /blogs/, /articles/, /news/ or /resources/, say so: the template's Area formula only recognises those five, so every post would be tagged "Blog URLs" on All Pages. Blog posts that sit at the root (no blog folder) are typed page by page.

**With a prune workbook:** add the prune's page type for each folder to the table (from the `prune_import.py` output), and where it disagrees with your proposal, say so and ask which is right. The prune's folder decisions were already confirmed by a person, so they are the better starting point than the folder-name guess; still show them. Do not ask about folders where both agree.

When they reply, write their mapping to `work/decisions.json` (create it if needed) and set the flag that lets analyze.py run:

```json
{"mapping_confirmed": true,
 "folder_types": {"procedures": "Service", "journal": "Blog", "before-after": "Gallery item", "resources": "Mixed"},
 "blog_folder": "/journal/", "service_folder": "/procedures/"}
```

Types a folder can take: Service, Concern, Blog, Location / Area, Company / Info, Gallery item, Archive, Utility / Policy, Mixed (each page is typed from its slug and H1), or any other name, which becomes "Name (folder)". The root level is always typed page by page. To type a second-level folder on its own, map its parent as Mixed and add `"parent/child"` as a key. Done when the person has confirmed and `mapping_confirmed` is true.

## Step 4: Search Console from the sheet, and GA4 if wanted

Search Console comes only from the sheet. Write `work/config.json` first (Step 5 shows its fields; the brand terms are needed here), then:

```
python $SKILL/scripts/gsc_sheet.py build --sheet GSC.xlsx --domain DOMAIN --brand "term,term" \
  --start YYYY-MM-DD --end YYYY-MM-DD --out work/gsc
```

It reads the "Claude Use This" tab (or says which tab to ask about), drops nothing silently, and writes the same tables as before (meta, pages, pairs, noowner, home) to `work/gsc/`. Read what it prints: pages and queries loaded, brand impressions left out, and any WARNING (URLs from another domain, no dates). A page's clicks and impressions here are the sum of its listed queries, because Search Console withholds rare queries from page + query exports; the Read Me says so. Done when it prints "Loaded" with no WARNING you cannot explain. If the person has no sheet, skip this step; the scripts leave those columns blank and the Read Me says why.

**GA4, only if the person asked for it:** follow [references/ga4.md](references/ga4.md). It needs Composio with Google Analytics connected and the same dates as the sheet; run it before `gsc_sheet.py build` so the sessions are merged, or re-run `build` afterwards. If Composio has no GA4 connection or the person said to skip GA4, do not use Composio, leave the GA4 columns blank and let the Read Me say GA4 was not used.

## Step 5: Analyze and review

Write `work/config.json`:

```json
{"client": "Example Med Spa", "domain": "examplemedspa.com", "city": "Springfield, IL",
 "other_cities": ["Chatham", "Rochester"], "brand_terms": ["example med spa", "example"],
 "crawler": "Sitebulb", "crawl_date": "2026-10-20"}
```

Then run `python $SKILL/scripts/analyze.py --work work [--past work/past.csv]` (`--past` only with a prune workbook, or a CSV of past decisions). It stops if the folder mapping isn't confirmed (`--allow-unconfirmed` exists for tests only; never use it for a client). Work through `work/review/next_steps.md` using [references/review.md](references/review.md): page types, topics, duplicate pairs, and the follow-up command it prints for top shared queries (`gsc_sheet.py pair-queries`, local, no Composio). Corrections go in `work/decisions.json`; re-run analyze.py after each round.

**Check the page types against the prune (only with a prune workbook):**

```
python $SKILL/scripts/type_check.py --work work
```

It lists every page both audits cover where the types cannot be reconciled, grouped by "prune says / this audit says", marks each group "Different type" or "Hub or page?" (one side calls it a listing page), and notes whether the prune typed the page from its folder map or only guessed from the URL wording. Neither audit is assumed right.

- If there are no conflicts, say so in one line and carry on.
- If there are, show the person the grouped table in the chat. Ask for the correct type of each "Different type" group (examples from `work/review/type_conflicts.md` in the question), one decision per group, and ask the "Hub or page?" groups in one question. Do not guess: where the person does not know, leave the type as this audit has it and list the pages in the final reply.
- Put the answers in `decisions.json` `page_types` and re-run analyze.py.
- Tell the person plainly that the **prune workbook should be updated to match**, because its Suggested Next Step depends on its Page Type, and give them the corrected pages (`work/review/type_conflicts.csv`, with the type the person confirmed). If a page the person re-types changes what the prune would suggest (a "Blog Post" that is really a Service page should not be removed or merged), name those pages.

Done when next_steps.md asks for nothing more: no "check" pairs, no top-shared-queries command left to run, no folders missing from the mapping, Unclassified pages either labeled or left on purpose for the chat summary, every type conflict answered or listed, and you have opened 5 rows per page type in `work/review/page_types.csv` and agree with them.

## Step 6: Recommendations and Read Me notes

Add the Recommendations rows, Read Me notes and any tab notes to `work/decisions.json`, following [references/recommendations.md](references/recommendations.md). Take every number from `work/analysis/summary.json` or the analysis CSVs.

## Step 7: Fill and check

```
python $SKILL/scripts/fill.py --work work --template work/template.xlsx --out "CLIENT Information Architecture Audit.xlsx"
```

fill.py writes values only, into the data cells under the template's headers, and keeps the template's tabs, headers, hover notes, dropdowns, colours and formulas. The only formulas in the template are All Pages column C (Area, copied down) and Recommendations column F (Pages); it never writes any other. It counts the template's dropdowns, conditional formats and hover notes before and after and stops if any changed. It then runs the automated QA: redirect targets live and not themselves redirected, wildcards not matching their own targets, every required topic covered by a Recommendations row, Areas that the Pages formula counts correctly, no placeholder text left, no recommendation to add links to blog posts. Done when it prints "All checks passed". Fix each listed problem at its source (decisions.json, or a re-run of analyze.py) rather than editing the workbook. Then compare the printed Area counts with the numbers in your Recommendations text.

## Step 8: Deliver

Send the .xlsx. In the reply:
- 5-7 headline findings in plain language; with a service-page focus, the service-page findings first.
- The Unclassified pages, if any.
- With a prune workbook: how many pages had conflicting types, what the person decided, the pages still unresolved, and the line that the prune workbook should be updated to match (with the file of corrected pages). Say that the prune's Suggested Next Step was read as the plan.
- Anything you could not do (no GA4, no Search Console, missing export columns, a window the sheet did not state) and anything else from Read Me "Missing / uncertain", plus each preflight WARN.
- How to get it into Sheets: new blank Google Sheet named "[Client] Information Architecture Audit", File > Import > Upload > **Replace spreadsheet**, then spot-check that the Area column and the Recommendations Pages column show numbers.
