---
name: information-architecture-audit
description: Run Mavan's information architecture (IA) audit for a client site from Sitebulb or Screaming Frog exports plus a Google Sheet of Search Console data (GA4 optional, through Composio), and build the IA audit workbook: a Recommendations tab plus one tab per issue (page types to check, moves and their redirects, links to fix, menu cleanup, internal linking opportunities). Adopts the page types of a content prune & merge workbook when the client has one. Use for IA audits, site architecture or site structure audits, and pre-migration or pre-rebuild structure reviews.
---

# Information Architecture Audit (Mavan SOP)

This skill turns Sitebulb or Screaming Frog exports plus Search Console data into an implementation workbook. Scripts do every count, match, join and all of the workbook wording; Claude confirms the folder-to-type mapping with the person and reviews the page types the rules got wrong. The output is a diagnosis with recommended actions, not the new structure: a person decides the target architecture.

`$SKILL` below is this skill's folder: the base directory shown when the skill loads. Set it once in the shell, e.g. `SKILL=<that folder>`. Scripts need Python 3 with pandas and openpyxl (`pip install --break-system-packages pandas openpyxl` if missing). Work in a folder named after the client (e.g. `client-ia/`) with a `work/` subfolder, and keep a task list with one item per step below.

Assume nothing about the site's URL structure. Folder names, depth and naming differ on every site, so the skill learns the structure from the crawl and a person confirms it (Step 3) before any page is classified. Which tabs a workbook has depends on what the site's data shows: a tab with no rows is left out.

**This audit does not cover junk archives, posts to remove, duplicate or merge pages, or their redirects.** The Content Prune & Merge audit owns those. If the client has no prune workbook, say so in the reply: those items need the prune audit first.

## How to ask the person questions

Ask with the AskUserQuestion tool (multiple choice) whenever the answer is a choice, and fall back to one plain-text message only when that tool is not available (for example an unattended run). The rules:

- **Build every option from this site's own data** (the crawl, the folder profile, the Search Console sheet, the file names), never from a list written into this skill. Nothing here may assume a folder name, a page type, a city or a site structure; sites differ on every engagement.
- **Put the best-supported option first and mark it "(Recommended)"**, then the other plausible options, one line each saying what choosing it leads to. The person can always type their own answer ("Other").
- **Never fill in a default silently.** If a value is a guess (for example brand terms inferred from the business name or domain), it goes in a question as an option to confirm, and the answer is what gets used.
- **Make each question stand on its own**: the dialog may be all the person sees, so name the folder, page or pair in the question text. Keep the full table or list in the chat message above the dialog for context.
- **Limits**: 1-4 questions per call and 2-4 options each. When there are more decisions than that, ask the ones that change the most pages first (largest folders, highest-impression pairs), batch the rest in further rounds, and offer a rule option ("apply the same type to all remaining folders that look like X") when the evidence is the same.
- **Ask only what the data cannot settle.** Do not ask about a folder or pair where the evidence is clear.

**The audit is always of the whole site.** A request to "focus on" the service pages, or a crawl export filtered to some pages, does not change what the audit needs: page types, links and duplicates are judged against every other page. Run the full site and put the service-page findings first in the summary.

**The audit is always of the whole site.** A request to "focus on" some pages, or a crawl export filtered to some pages, does not change what the audit needs: page types and links are judged against every other page. Run the full site.

## What you need

- **Crawl exports**, every URL not just 200s: (1) URL export, (2) all internal links export, (3) redirects export. Sitebulb or Screaming Frog. Ask for them if missing, naming the exports: Sitebulb URL Explorer > Internal > HTML (URL, HTTP Status Code, Indexable Status, Crawl Depth, Path Depth, Crawl Source, Title, H1, first H2, No. Content Words, No. Internal Links to URL; no GSC or GA columns), Links > Internal Links (Target URL, Anchor Text, Linking URL, Location, CSS Path, Image) and the Redirects report; Screaming Frog Internal > HTML (Address, Status Code, Indexability, Indexability Status, Title 1, H1-1, H2-1, Word Count, Crawl Depth, Folder Depth, Unique Inlinks), Bulk Export > Links > All Inlinks (Source, Destination, Anchor, Status Code, Link Position, Link Path, Type) and Reports > Redirects > All Redirects. The Sitebulb connector cannot replace them (it returns 50 sample URLs per query). A filtered export (for example "on page filtered", only some pages) is not the URL export.
- **Client facts**: business name, domain, main city and state, other cities targeted, brand terms (name and nicknames). Work out what you can from the site and the files first, then ask for whatever is left in one multiple-choice call (see "How to ask the person questions"): brand terms (offer the candidates you derived from the business name and domain for the person to confirm, plus "none, do not filter" and Other), other cities (offer "use every city found in the URLs and queries" with the cities you found listed in the question, "only the ones I list", and "none").
- **Search Console data**: a Google Sheet (attached, or as an .xlsx download) of page + query rows with the columns Page, Query, Clicks, Impressions (CTR and Position are used when present), for about the last 6 months, in a tab named "Claude Use This" (Mavan's Search Console template; otherwise the one tab with those columns). The sheet does not say which dates it covers, so ask the person (multiple choice: a few common windows ending on the date the export was made, taken from the sheet or its file name when it shows one, plus Other) and write down which window was used. If the person has no sheet, the audit still runs: the Internal linking opportunities tab is empty and the README says why.
- **Optional, the content prune & merge workbook** (from the content-prune-merge skill), as an attached .xlsx. Use the **SEO's working copy**, the one that still has the Kept pages and Check page type tabs, because those carry the page types. If the person has it in Google Sheets, they download it as .xlsx and attach it. Do not read it through a connector. When it is attached, its page types are used and its planned removals and merges are assumed to happen (Moves skips them). Skip everything about it when it isn't attached.
- **Optional**: the client's existing redirect list (e.g. a redirect plugin export). Skip anything about it when it isn't attached.
- **GA4 (optional, and no tab in this workbook depends on it)**: only when the person asks for it. It comes through **Composio** (Step 4). Never use Composio unless they asked; Search Console never uses Composio.

## Step 0: Preflight (always first)

```
python $SKILL/scripts/preflight.py --domain DOMAIN --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv \
  --gsc-sheet GSC.xlsx --gsc-start YYYY-MM-DD --gsc-end YYYY-MM-DD \
  [--prune PRUNE.xlsx] [--client-redirects LIST.csv] --ga4 yes|no \
  --client "Name" --city "City, ST" --brand "term,term" --out work
```

Leave out an argument you do not have yet and the preflight reports it missing. It reads headers and a sample only, so it takes seconds. It checks that each export is the right kind, that the exports come from the same crawl, that the Search Console sheet is a page + query export for this domain with a date range, that the optional prune workbook is the Prune & Merge workbook (and whether it has the page-type tabs), and what the client facts still lack.

Read `work/preflight.md`. If it says NOT READY, send the person **one** message that lists each FAIL and says exactly which export or answer is needed and where to get it, then stop. Do not build around a missing input. Offer to continue without an input only for the ones the preflight can skip (redirects, Search Console sheet): ask as a multiple-choice question ("continue without it" with what the audit loses, or "wait for the file"), and use `--skip` only after the person picks that. Mention each WARN in the final reply. Done when the preflight says READY.

## Step 1: Crawl exports

```
python $SKILL/scripts/prep.py --domain DOMAIN --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv \
  [--client-redirects LIST.csv] --out work
```

Links are classed Nav / Footer / Breadcrumb / Body from the CSS path or link path, because Sitebulb labels almost every link "Navigation". Read the printed class counts and the most common paths per class. Done when menus land in Nav, footers in Footer, article copy in Body, and there's no WARNING. If a menu or footer container is landing in Body (or 95%+ of links are Nav), re-run with `--nav-regex` / `--footer-regex` built from the paths shown.

## Step 2: Prune workbook (only if one was attached)

```
python $SKILL/scripts/prune_import.py --workbook PRUNE.xlsx --domain DOMAIN --out work
```

It reads the prune tabs by name and writes `work/prune.csv` (page types to adopt), `work/past.csv` (the plan: removals, merges, keeps), `work/prune_wildcards.csv` and, if the SEO typed a change in the Disagree column of Kept pages, `work/prune_disagree.csv`. A page whose type on Check page type was only a guess and was not corrected gets no type here: this audit types it. Do not guess about the disagree pages: list them in the reply. Done when it prints the tabs it read.

## Step 3: Folder profile and mapping (stop and confirm)

```
python $SKILL/scripts/folder_profile.py --work work [--deep folder1,folder2]
```

It profiles every first-level folder and the root level (live pages, share, sample pages with titles and H1s, median words, how many pages read like articles) and proposes a page type per folder. A common folder name is one piece of evidence, not the answer. Folders over 30 pages also get their second-level folders profiled; pass `--deep` to force it for others.

**Send `work/review/folder_mapping.md` to the person in the chat, then ask the questions below with AskUserQuestion and STOP until they answer.** Do not classify any page until they confirm or correct the mapping. The table gives the context; the questions collect the decisions:
- One question per Low-confidence folder (largest first): the proposed type first, then the next most plausible types for that folder given its sample pages, then Other.
- One question for the blog: options built from the profile (each folder that reads like articles, "posts sit at the root and are typed page by page", "the site has no blog"). Do the same for the service folder (each folder whose pages read like services, "services are spread across several folders, type them page by page").
- One question for each folder where the proposed type is Medium confidence and the evidence line shows a conflict.
- Where two or more folders share the same evidence, ask once and offer to apply the answer to all of them.
In the table message, flag every Low-confidence row. A folder that holds only a blog listing page and no posts is a hub, not a blog folder; say which it is.

**With a prune workbook:** add the prune's page type for each folder to the table (from the `prune_import.py` output). The prune's types are used for the pages it typed; the folder mapping covers everything else. Do not ask about folders where both agree.

When they reply, write their mapping to `work/decisions.json` (create it if needed) and set the flag that lets analyze.py run:

```json
{"mapping_confirmed": true,
 "folder_types": {"procedures": "Service", "journal": "Blog", "before-after": "Gallery item", "resources": "Mixed"},
 "blog_folder": "/journal/", "service_folder": "/procedures/"}
```

Types a folder can take: Service, Concern, Blog, Location / Area, Company / Info, Gallery item, Archive, Utility / Policy, Mixed (each page is typed from its slug and H1), or any other name, which becomes "Name (folder)". The root level is always typed page by page. To type a second-level folder on its own, map its parent as Mixed and add `"parent/child"` as a key. Done when the person has confirmed and `mapping_confirmed` is true.

## Step 4: Search Console from the sheet (and GA4 only if asked)

Write `work/config.json` first (the brand terms are needed here):

```json
{"client": "Example Med Spa", "domain": "examplemedspa.com", "city": "Springfield, IL",
 "other_cities": ["Chatham", "Rochester"], "brand_terms": ["example med spa", "example"],
 "crawler": "Sitebulb", "crawl_date": "2026-10-20"}
```

```
python $SKILL/scripts/gsc_sheet.py build --sheet GSC.xlsx --domain DOMAIN --brand "term,term" \
  --start YYYY-MM-DD --end YYYY-MM-DD --out work/gsc
```

It reads the "Claude Use This" tab (or says which tab to ask about), drops nothing silently, and writes the tables to `work/gsc/`. Read what it prints: pages and queries loaded, brand impressions left out, and any WARNING (URLs from another domain, no dates). A page's clicks and impressions here are the sum of its listed queries, because Search Console withholds rare queries from page + query exports; the README says so. Done when it prints "Loaded" with no WARNING you cannot explain. If the person has no sheet, skip this step.

**GA4, only if the person asked for it:** follow [references/ga4.md](references/ga4.md). It needs Composio with Google Analytics connected and the same dates as the sheet. Pull only the fields that file lists (sessions and key events by landing page); never pull other reports. If Composio has no GA4 connection or the person did not ask, do not use Composio.

## Step 5: Analyze and review

```
python $SKILL/scripts/analyze.py --work work [--past work/past.csv --prune work/prune.csv]
```

(`--past` and `--prune` only with a prune workbook.) It stops if the folder mapping isn't confirmed (`--allow-unconfirmed` is for tests only; never use it for a client). Work through `work/review/next_steps.md` using [references/review.md](references/review.md): the page types it flags, folders missing from the mapping, and topics. Ask the judgment calls as multiple-choice questions (see "How to ask the person questions"): each root-level page whose type the evidence does not settle, grouped by the rule that typed it (offer a single rule such as "treat long slugs that do not read as services as blog posts" as an option, with 3-5 example URLs in the question). Pages the evidence does settle are not asked about, and pages typed by the prune workbook are not re-asked. Corrections go in `work/decisions.json`; re-run analyze.py after each round.

Two rules that hold on every site:
- **Blog posts belong in a blog folder.** Posts outside it appear on the Moves tab with the folder they go to (the confirmed blog folder, else an existing blog listing page). When the site has no blog folder and no listing page, the new URL is left for the SEO. Never recommend leaving posts at the root.
- **Never recommend adding links to blog posts.** Linking from blogs to service pages is fine; that is not a goal of this audit.

Done when next_steps.md asks for nothing more: no folders missing from the mapping, Unclassified pages either labeled or left on purpose for the reply, and you have opened 5 rows per page type in `work/review/page_types.csv` and agree with them.

## Step 6: Build the workbook

```
python $SKILL/scripts/make_xlsx.py --work work --out "CLIENT Information Architecture Audit.xlsx"
```

The script writes every tab, banner, header, fix, owner and order from fixed wording; see [references/deliverable.md](references/deliverable.md). Claude does not write or reword workbook text. Read the printed row counts and compare them with `work/analysis/summary.json`. If the analysis found an issue the script has no wording for, add it as `extra_recommendations` in decisions.json (rules in deliverable.md), re-run, and tell the person you did. Done when the script prints "Wrote" and every tab you expected is listed.

## Step 7: Deliver

Send the .xlsx. In the reply:
- The headline findings in plain language, taken from the Recommendations rows and counts.
- The pages that were typed by guess (Check page type) and how many were adopted from the prune workbook.
- Kept pages the SEO typed a change for (`work/prune_disagree.csv`), listed and not acted on.
- With no prune workbook: that junk archives, posts to remove, duplicates and merges were not covered and need the prune audit.
- Blog posts outside a blog folder: the number, the folder they should move to, and that the move belongs in the same release as the other URL changes.
- Anything you could not do (no Search Console, a window the sheet did not state, missing export columns) plus each preflight WARN and the README notes.
- That it is a standalone .xlsx: the SEO opens it, works through the README, and asks Claude in the same chat to update it after any change.
