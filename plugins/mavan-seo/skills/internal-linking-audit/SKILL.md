---
name: "internal-linking-audit"
description: "Run Mavan's internal linking audit for a client site from Sitebulb or Screaming Frog exports and deliver the implementation sheet. Use for internal linking audits or link opportunities to service pages."
---

# Internal Linking Audit (Mavan SOP)

Version 2.0 (Oct 2026). This skill carries the whole process and does not need the written SOP; the "Internal Linking Audit Process" page in Notion is documentation for people.

Find which pages should link to the client's priority pages (any commercial page; usually service pages) and deliver a sheet that says **which page to edit and which page to link to**. The team finds the spot in the copy and writes the anchor themselves, so don't read pages, quote sentences or suggest anchors. Everything comes from the crawl export and Search Console. Keep the run light.

## Inputs

- Crawler exports from Sitebulb or Screaming Frog: a URLs export and an all-internal-links export (with link position/location and CSS path or link path). Ask for them if they're missing.
- Priority page URLs (optionally with the phrases people use for each service, separated by `|`), or "all service pages".
- The client domain.

## Setup

`$SKILL` below is this skill's folder: the base directory shown when the skill loads (`${CLAUDE_SKILL_DIR}` in Claude Code). Set it once in the shell, e.g. `SKILL=<that folder>`. The script needs Python 3 with pandas and openpyxl (`pip install --break-system-packages pandas openpyxl` if missing). Work in a folder named after the client (e.g. `client-ila/`); the script writes to its `work/` subfolder. Keep a task list with one item per step.

## Step 1: Search Console through Composio

1. Use Composio to list the Search Console sites and check the client is there. If it isn't, tell the person right away that the Google account authorized in Composio doesn't have access, and continue without search data. Don't use any other ranking source.
2. If it is, pull the last 3 full months:
   - By page: save `gsc_pages.csv` with columns `page,clicks,impressions`.
   - By page + query, **filtered** to the priority topics: one request with a `query` filter using operator `includingRegex` and a regex of the priority terms (e.g. `rhinoplasty|nose job|breast augmentation|liposuction`). Paginate with start_row until fewer rows come back than requested. Save `gsc_queries.csv` with columns `page,query,clicks,impressions`.
3. Composio returns at most ~40KB per call. If a pull is bigger, run it in Composio's remote workbench (`COMPOSIO_REMOTE_WORKBENCH`) and print the CSV back in parts.

## Step 2: Prepare the crawl data

```
python $SKILL/scripts/audit.py prep --urls <urls.csv> --links <links.csv> --base https://DOMAIN
```

Read the pattern table and choose a `--body-regex` that matches only links inside the main content (on the test site: `#(post-part|section)`). Related-post cards, the sitemap page, popups and CTA buttons are not body copy even when labelled "Content". Re-run with `--body-regex` and check the counts by section look right.

## Step 3: Priority pages and terms

Write `priority.csv` with columns `url,terms`. Leave `terms` blank to derive it from the page H1, or add synonyms (`tummy tuck|abdominoplasty`). Work out the service URL pattern from the URLs export (e.g. `^/procedures/[^/]+/[^/]+$`); category hubs aren't services. Don't stop to confirm terms; list them in the final summary.

## Step 4: Find candidates

```
python $SKILL/scripts/audit.py candidates --base https://DOMAIN --priority priority.csv --service-regex '<pattern>' [--gsc-pages gsc_pages.csv] [--gsc-queries gsc_queries.csv]
```

It writes to `work/`: `candidates.csv` (pages whose title, H1, URL or Search Console queries match a priority topic and that don't link to it in body copy), `service_links.csv` (every priority page / service pair and whether each links to the other), `gallery.csv` (gallery and review pages per priority page and how many link up outside the menu), `wrong_target.csv` (body links whose anchor names a service but point to a blog, gallery, review or contact page), `baseline.csv`.

## Step 5: Decide the rows

Write `work/rows.csv` with columns `priority,type,priority_page,action,source,target,why`. Judge from titles and URLs only.

- **Related content** (`candidates.csv`, type Related content): keep pages genuinely about the service. Drop pages that fit a different service better. Action `Add link`.
- **Related service**: from `service_links.csv`, pick the services that genuinely relate to each priority page (e.g. tummy tuck and mommy makeover) and add a row for each missing direction. Candidates typed Related service count too. Action `Add link`.
- **Gallery & reviews**: for each priority page where `linking_up_outside_menu` is 0 and there are gallery/review pages, add one row with the gallery URL as source and action `Add link (template)`. In `why`, say how many pages it covers, and add "May need platform support to change the template" if the site runs on a hosted platform (e.g. DoctorLogic).
- **Wrong target**: from `wrong_target.csv`, rows where the anchor really describes the service and `source_already_links_to_suggested` is False. Action `Change link target`; put the current anchor and current target in `why`.
- **Priority**: High = the source page gets meaningful clicks, is a closely related service page, or is a template fix. Low = everything else.
- **Why**: one short line (e.g. "Blog about rhinoplasty swelling; ranks for 'rhinoplasty recovery'").
- `priority_page` is a short label (e.g. "Rhinoplasty"), or "Other service pages" when the target isn't a priority page.

Also write `work/findings.txt`: 3–5 plain-language findings, one per line.

## Step 6: Build

```
python $SKILL/scripts/audit.py build --base https://DOMAIN --rows work/rows.csv --client DOMAIN --findings work/findings.txt --note "<data sources used>" --out "<client> Internal Linking Audit.xlsx"
```

It rejects rows where the page already links to the target in its body copy, URLs that aren't live, duplicates and anything other than High/Low. Fix every error and re-run. If the xlsx skill's recalc script is available, run it on the file.

## Step 7: Deliver

Send the .xlsx (import it into Google Sheets with File > Import > Replace spreadsheet). In the reply: 3–5 findings, row counts by priority, the terms used, and anything missing (e.g. no Search Console access). Mention that Sitebulb can hide a body link that uses the same anchor as a menu link, so a few rows may already be done; the team marks those Rejected.
