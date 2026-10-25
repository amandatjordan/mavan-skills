# Exports and how prep.py reads them

Use one tool for the whole audit. Ahrefs' DR and Semrush's AS are different scales, so the workbook labels the authority column with whichever the exports use, and never mixes them.

## What the person attaches

| prep.py flag | Data | Ahrefs | Semrush |
| --- | --- | --- | --- |
| `--backlinks` | Client backlinks, live, not grouped | Site Explorer > Backlinks > Live > All links > Export | Backlink Analytics > Backlinks > Active > Export |
| `--refdomains` | Client referring domains | Site Explorer > Referring domains > Export | Backlink Analytics > Referring Domains > Export |
| `--anchors` | Client anchors (optional) | Site Explorer > Anchors > Export | Backlink Analytics > Anchors > Export |
| `--broken` | Broken backlinks | Site Explorer > Broken backlinks > Export | Backlink Analytics > Indexed Pages > Broken pages > Export |
| `--compare` | Client + competitor metrics | Batch Analysis > Export | Backlink Analytics compare view or Bulk Analysis > Export |
| `--gap` (repeatable) | Domains linking to competitors, not the client | Competitive Analysis > Link Intersect (Referring domains mode) > Export | Backlink Gap (Missing or Best view) > Export |
| `--gap-pages` (optional, repeatable) | Link gap in referring-pages mode, for Evidence URLs | Link Intersect, Referring pages mode | Backlink Gap > expand a domain > Export |
| `--audit` (Semrush only, optional) | Backlink Audit | none | Backlink Audit > Audit tab > Export |
| `--gsc-links` | GSC Links report | Search Console > Links > Export external links > Latest links, or Top linking sites | same |
| `--redirect-map` (optional) | Planned redirects | The client's prune & merge Redirects tab, or IA audit Redirects tab, as CSV | same |

Semrush Backlink Gap takes 5 domains, so with more than 4 competitors there are two gap files: pass `--gap` twice. prep.py merges them by domain.

## Identify files by their columns

People rarely name exports clearly. Open the header row of each file (read the first 2 lines only; never read a whole export into the chat) and match it to the table. Signals:

- Backlinks: one row per link, with a referring page URL and a target URL.
- Referring domains: one row per domain, no target URL.
- Broken: Ahrefs has referring page + target URL + target HTTP code; Semrush Indexed Pages has one row per client URL with a response code and a domains count.
- Comparison: one row per domain (client and competitors) with DR/AS, referring domains, backlinks. Semrush's compare view can come out with metrics as rows and domains as columns; prep.py transposes that.
- Link gap: one row per referring domain, plus one column per competitor (the header contains the competitor's domain).

## Encoding and column names

Ahrefs offers UTF-8 or UTF-16 CSV; Semrush uses comma CSV; GSC uses UTF-8 CSV. `read_table()` handles all of them.

prep.py prints, for each file, which column it used for each field and which fields it could not find. If a field maps to the wrong column, or a needed field is missing because the tool renamed it, re-run with `--map label.field="Exact column name"` (labels: backlinks, refdomains, broken, compare, gap, gap_pages, anchors, audit, gsc_links, redirect_map; fields are listed in `SPEC` at the top of prep.py). Required fields stop the run with the list of columns found.

## Export limits

Plans cap export rows. If a backlinks export has a round number of rows (1,000, 10,000, 50,000, 100,000) treat it as capped and say so in the notes: the Disavow Review tab only covers what was exported.
