# The workbook

`scripts/make_xlsx.py` builds it from `work/audit.tsv`, `work/existing_redirects.tsv` and `work/run.json` (all written by `scripts/build.py`) and the Workbook README table in references/rules.md. Every banner, header, Fix, owner and order is fixed in the script; Claude writes none of it. The only per-page text is the "Why" column, taken from each row's Notes with `Suggested because: ` removed.

It is a standalone .xlsx: no template, no Google Drive or Sheets connector. The SEO imports it to Google Sheets if they want it there.

## Tabs

In this order. A tab with no rows is left out, with its Recommendations row and README row. Tab names never change, because banners and other tabs refer to them.

| Tab | Color | Rows | Columns |
| --- | --- | --- | --- |
| Recommendations | orange | one per issue with rows | Issue, Priority, Fix, Number of Pages Affected, Tab(s) for SEO to Review, Tab(s) to hand off, Handoff to, Order |
| Check page type | grey, SEO only | Page Type Reason contains `Root-level` or `No rule matched`. Left out when an IA audit workbook was given (the IA settled page types) | Page, Page type we guessed, Correct page type (SEO fill in), Why we guessed |
| Kept pages | grey, SEO only | Keep, and not on an action tab below | Page, Page type, Clicks, Impressions, Why, Disagree? (SEO fill in) |
| Needs discussion | grey, SEO only | Needs Discussion | Page, Question for the client (SEO fill in), Why |
| Junk folders | green | junk wildcards | Folder to redirect, Redirect to, Why |
| Remove pages | green | Remove then Redirect | Page to remove, Redirect to, Why |
| All redirects - Handoff to Dev | blue | redirect-now rows | Source URL, Target URL, Regex (0 = no, 1 = yes), HTTP Code |
| Redirects needing a target | grey, SEO only | old URLs with demand and no same-slug live page | Old URL, Redirect to (SEO fill in), Why |
| Merge pages | green | Merge then Redirect, not a location copy | Page that will be removed after merge, Page we are keeping, Unique content to copy over (SEO fill in), Why |
| Per location service pages | green | every location copy (rules.md rule 2), merged or kept | Location page, Main page, Clicks, What to do, Unique content to copy over (SEO fill in on Merge rows), Why |
| Redirect after merge | green | every Merge then Redirect row | Old URL, Redirect to, Why, Done when |
| Menu cleanup | green | Merge or Remove rows in the main menu, and menu links to URLs that redirect. With an IA audit workbook: only menu items its Menu cleanup tab does not already list, and no redirected-link rows (its Fix links tab has them) | Menu item to replace, Replace with, Why |
| Update pages | green | Update | Page to update, New title, New H1, New first sentence (all SEO fill in), Why with the current title and H1 |
| Repurpose pages | green | Repurpose | Blog post, What to do (SEO fill in), Why |
| Blog beats service | green | Blog posts flagged `Blog outranks service page` | Blog post, Service page, What to do (SEO fill in), Why |
| README | grey, SEO only | | How to use, what Claude checked per tab (from rules.md), settings this run, data used |

Every tab but Recommendations and the dev tab has a yellow banner in row 1 that says what to QA. Header colors: green = columns the implementer uses, grey = SEO only (the Why column is deleted before handoff), orange = SEO fill in (the cells are orange too). Rows 1-2 are frozen, text wraps and column widths are set, so nobody reformats.

## The dev handoff tab

Downloaded as a CSV, so it has one header row, no banner and no other columns. It holds only redirects to add now, all 301:
- junk folder wildcards, as `https://domain/folder/(.*)` with Regex 1;
- Remove then Redirect pages;
- existing-redirect fixes with a target (chains removed, repointed redirects, old URLs with a same-slug live page).

Merge redirects are never on it: they are on Redirect after merge, sent only once the merges are live. Old URLs with no target are on Redirects needing a target until the SEO fills them in. Each source URL appears on exactly one redirect tab; make_xlsx.py stops if one appears twice.

## README

Built per run (with an IA audit workbook, it also lists the IA's folder map and that the IA was used): the six how-to steps, one row per tab present from the Workbook README table in rules.md, the settings (overlap share, remove thresholds, how long the data covers, GA4 used or skipped and why, the folder map, the locations) and the data used. GA4 is listed only when it was used, and a Composio line ("Only the listed fields were pulled.") only when GA4 came through Composio.
