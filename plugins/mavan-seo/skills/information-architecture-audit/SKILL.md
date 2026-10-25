---
name: information-architecture-audit
description: Run Mavan's information architecture (IA) audit for a client site from Sitebulb or Screaming Frog exports plus Search Console and GA4 through Composio, and fill the IA Audit template sheet. Use for IA audits, site architecture or site structure audits, and pre-migration or pre-rebuild structure reviews.
---

# Information Architecture Audit (Mavan SOP)

Full SOP: the "Information Architecture Audit Process" page in Notion. This skill is its Step 4 prompt, turned into scripts plus the judgment calls the scripts can't make. The output is a diagnosis with suggested actions, not the new structure: a person decides the target architecture.

Template: https://docs.google.com/spreadsheets/d/1uLh1ceuPOhxVeTmIi7dlTbAFYDaIk_BhjaQGNpxHVu4/edit (file id `1uLh1ceuPOhxVeTmIi7dlTbAFYDaIk_BhjaQGNpxHVu4`).

Scripts do every count, match and join; never estimate a number by reading. `$SKILL` below is this skill's folder: the base directory shown when the skill loads (`${CLAUDE_SKILL_DIR}` in Claude Code). Set it once in the shell, e.g. `SKILL=<that folder>`. Scripts need Python 3 with pandas and openpyxl (`pip install --break-system-packages pandas openpyxl` if missing). Work in a folder named after the client (e.g. `client-ia/`) with a `work/` subfolder, and keep a task list with one item per step below.

## What you need

- **Crawl exports**, every URL not just 200s: (1) URL export, (2) all internal links export, (3) redirects export. Sitebulb or Screaming Frog; the SOP's Step 3 lists the columns. Ask for them if missing. The Sitebulb connector cannot replace them (it returns 50 sample URLs per query).
- **Client facts**: business name, domain, main city and state, other cities targeted, brand terms (name and nicknames). Ask in one question for whatever the request doesn't give; work out what you can from the site first.
- **Optional**: the client's existing redirect list (e.g. a redirect plugin export) and past prune & merge decisions. Skip anything about them when they aren't attached.
- **Composio** connector with Google Search Console and Google Analytics connected (once per account, see the SOP's Step 1).

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

## Step 3: Search Console and GA4 through Composio

Follow [references/composio.md](references/composio.md). Composio keeps large API responses in its own sandbox and returns at most ~40KB per call, so the script `gsc_workbench.py` does the heavy work there and prints compact, checksummed tables that you save here. Done when `python $SKILL/scripts/gsc_import.py --dir work/gsc` prints "Loaded" with no PROBLEMS. If Search Console has no property for the domain, say so and continue without it; the scripts leave those columns blank and the Read Me says why.

## Step 4: Analyze and review

Write `work/config.json`:

```json
{"client": "Example Med Spa", "domain": "examplemedspa.com", "city": "Springfield, IL",
 "other_cities": ["Chatham", "Rochester"], "brand_terms": ["example med spa", "example"],
 "crawler": "Sitebulb", "crawl_date": "2026-10-20"}
```

Then run `python $SKILL/scripts/analyze.py --work work [--past PAST.csv]` and work through `work/review/next_steps.md` using [references/review.md](references/review.md): page types, topics, duplicate pairs, and the follow-up Composio calls it prints. Corrections go in `work/decisions.json`; re-run analyze.py after each round. Done when next_steps.md asks for nothing more: no "check" pairs, no Composio calls left to run, Unclassified pages either labeled or left on purpose for the chat summary, and you have opened 5 rows per page type in `work/review/page_types.csv` and agree with them.

## Step 5: Recommendations and Read Me notes

Add the Recommendations rows, Read Me notes and any tab notes to `work/decisions.json`, following [references/recommendations.md](references/recommendations.md). Take every number from `work/analysis/summary.json` or the analysis CSVs.

## Step 6: Fill and check

```
python $SKILL/scripts/fill.py --work work --template work/template.xlsx --out "CLIENT Information Architecture Audit.xlsx"
```

fill.py writes every tab from the analysis, keeps the template's tabs, headers, hover notes, dropdowns, colours and formulas, and runs the automated QA: redirect targets live and not themselves redirected, wildcards not matching their own targets, every required topic covered by a Recommendations row, Areas that the Pages formula counts correctly, no placeholder text left, no recommendation to add links to blog posts. Done when it prints "All checks passed". Fix each listed problem at its source (decisions.json, or a re-run of analyze.py) rather than editing the workbook. Then compare the printed Area counts with the numbers in your Recommendations text.

## Step 7: Deliver

Send the .xlsx. In the reply:
- 5-7 headline findings in plain language.
- The Unclassified pages, if any.
- Anything you could not do (no GA4, no Search Console, missing export columns) and anything else from Read Me "Missing / uncertain".
- How to get it into Sheets, from the SOP's Step 5: new blank Google Sheet named "[Client] Information Architecture Audit", File > Import > Upload > **Replace spreadsheet**, then spot-check that the Area column and the Recommendations Pages column show numbers.
