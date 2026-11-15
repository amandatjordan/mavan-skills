---
name: migration-sheet
description: Merge the Content Prune & Merge, IA audit and (when it applies) Service Gap workbooks, plus the old-site crawl exports, a backlink export and the Search Console sheet, into one migration workbook for a site migration - pages to keep, merge and redirect, media with backlinks, new pages, the final navigation the SEO fills in, and the developer redirect list. Use for migration sheets, redirect maps for a rebuild or re-platform, or step 1C of the Site Migration SOP.
---

# Migration sheet (Mavan SOP: Site Migration, step 1C)

This skill merges the audits' decisions into **one workbook**: the single source of truth for the developer, the client approval and every staging and launch check. Scripts do every count, join, redirect fix and all of the workbook wording; Claude runs the scripts, shows the person what they found and asks the questions. Claude writes none of the workbook text.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads). Scripts need Python 3 with pandas and openpyxl only. Work in a folder named after the client with a `work/` subfolder. Keep a task list with one item per step below.

**Hard rules**
- **Never live crawl.** No step fetches, crawls or sends a request to the old, staging or live site. Every number comes from files the person uploads.
- **No Composio and no other connector.** Everything is an uploaded file. Do not add a tool or a step that is not written here.
- **Assume nothing about the site.** URL structure, page types, folders and cities differ on every site; the skill reads them from the files.
- **A change to a keep, merge, remove or move decision is made in the audit workbook, never in chat and never in the migration sheet.** The SEO's working copy of each audit workbook is the approval: a row still on a tab is part of the plan.

## What is outside the skill and what is inside

**Outside the skill, before it starts (the person provides these files):**
1. Old-site crawl exports, with the XML sitemap added as a crawl source: URL export, internal links export, redirects export (optional). Sitebulb or Screaming Frog. See `references/inputs.md`.
2. The **Content Prune & Merge** workbook, the SEO's working copy (it still has Kept pages and Check page type). Run first.
3. The **IA audit** workbook, the SEO's working copy (it still has README and Check page type). Run second, using the prune workbook.
4. The **Service Gap** workbook, only for med spa and plastic surgery sites.
5. A backlink export (Ahrefs or Semrush backlinks). It is also where media files with backlinks come from.
6. The Search Console sheet (tab "Claude Use This", Page and Impressions columns).

The crawl's images and documents lists are **not required**. If the person includes them, nothing is penalized.

**Inside the skill, pass 1:** preflight, prep, import the audits, build, write the workbook.
**Outside the skill, between the passes:** the SEO fills in the orange cells.
**Inside the skill, pass 2:** preflight on the SEO's working copy, build again with every check, write the final workbook and the developer redirect CSV.
**Outside the skill, after:** client approval, then SOP step 1D (build and check staging; the `migration-check` skill is planned for that).

## How to ask the person questions

Use AskUserQuestion (multiple choice) whenever the answer is a choice; plain text only when that tool is not available. Build every option from this run's data (the file names, the counts in `work/preflight.md`), never from a list written in this skill. Put the best-supported option first and mark it "(Recommended)". Ask only what the data cannot settle. The only question this skill always asks is the preflight confirmation.

## Pass 1

### Step 0: Preflight (always first, blocks on problems)

```
python $SKILL/scripts/preflight.py --domain DOMAIN --urls URLS.csv --links LINKS.csv --backlinks BACKLINKS.csv --gsc GSC.xlsx \
  --prune PRUNE.xlsx --ia IA.xlsx [--gap GAP.xlsx] [--redirects REDIRECTS.csv] --out work
```

It checks that each file is the right kind (crawl not empty, the prune and IA files are the SEO's working copies and not the implementer copies, the backlink export has a Target URL column), then **blocks on every unresolved cell in the audit workbooks and lists each one**: a filled "Disagree?" cell on Kept pages, a Needs discussion row with no answer in column B, a blank, "SEO fill in" or NEEDS TARGET redirect or merge target, a "Correct page type" still "SEO fill in", an IA move or menu item still open, an empty Next Steps on a Service Gap row.

If it says STOPPED, send the person **one** message listing every item and which workbook to fix it in, then stop. The SEO fixes the audit workbook and uploads it again. Do not work around a blocker.

When it passes, send the person the **"What I read"** section of `work/preflight.md` (each file and tab with row counts, and the decisions taken from each). Ask one question: is this the right set of files? Continue only after yes.

### Step 1: Crawl, links, backlinks, Search Console

```
python $SKILL/scripts/prep.py --domain DOMAIN --urls URLS.csv --links LINKS.csv [--redirects REDIRECTS.csv] \
  --backlinks BACKLINKS.csv --gsc GSC.xlsx --out work
```

Links are classed Nav / Footer / Breadcrumb / Body from the CSS path, because Sitebulb labels almost every link "Navigation". Read the class counts and the common paths. If a menu or footer lands in Body (or 95%+ of links are Nav), re-run with `--nav-regex` / `--footer-regex` built from the paths shown. Done when there is no WARNING.

### Step 2: Import the audits

```
python $SKILL/scripts/import_audits.py --domain DOMAIN --prune PRUNE.xlsx --ia IA.xlsx [--gap GAP.xlsx] --out work
```

Writes `work/audits.json`. It must print no unresolved cells (preflight already blocked them).

### Step 3: Build

```
python $SKILL/scripts/build.py --domain DOMAIN --work work
```

Gives every old URL one decision: Content Prune's action first, then the IA move for a page that stays, then keep at the same URL. Resolves every redirect target to its final URL in one hop (existing site redirects included), lists every discrepancy, and runs the checks (see `references/rules.md`). Exit code 1 means a structural problem (a chain or loop, a target that is not a page that stays, a page inside a wildcard rule): show the person the lines, say which audit workbook to change, and stop. Cells the SEO still has to fill in are expected in pass 1 and show as OPEN.

### Step 4: Write the workbook

```
python $SKILL/scripts/make_xlsx.py --work work --out CLIENT-migration-sheet.xlsx --client "Client name"
```

Send the workbook with SendUserFile. Then tell the person, in a few lines: the counts, how many discrepancies are on the Summary tab (read them before approving), and which orange cells are theirs to fill: the **Final menu and nav** tab (the SEO MUST set the navigation, always with parent and child levels), **Media with backlinks** (decide each file), **New pages** (URL and internal links), and any redirect target or Gone reason marked SEO fill in on **Pages to redirect**. Do not propose a menu, a media decision, a new URL or a redirect target.

## Between the passes (outside the skill)

The SEO fills in the orange cells in the workbook and uploads their working copy. Nothing else changes: to change a keep, merge, remove or move decision, they edit the audit workbook and the skill is re-run from pass 1.

## Pass 2

Run preflight again with `--working-copy WORKING_COPY.xlsx` (and the same files), then:

```
python $SKILL/scripts/build.py --domain DOMAIN --work work --working-copy WORKING_COPY.xlsx
python $SKILL/scripts/make_xlsx.py --work work --out CLIENT-migration-sheet-final.xlsx --client "Client name"
```

Pass 2 re-runs every check, now including the Final menu and nav and Media with backlinks checks, and **fails while any cell the SEO was supposed to fill is blank**. Only when every check passes does it write the final workbook (with the **Redirects - Handoff to Dev** tab) and a CSV of that tab next to it. Send both with SendUserFile. Remind the person the README tab and the banner rows are for the SEO and are deleted before the client and developer see the sheet.

## What the person gets

One workbook: Summary, Pages to keep, Final menu and nav, Pages to merge, Pages to redirect, Media with backlinks, New pages, Redirects - Handoff to Dev (pass 2), README. Tab contents are in `references/rules.md`.
