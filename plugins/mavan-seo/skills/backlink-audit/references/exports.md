# Exports and how prep.py reads them

Use one tool for the whole audit. Ahrefs' DR and Semrush's AS are different scales, so the workbook labels the authority column with whichever the exports use, and never mixes them.

An audit needs **two exports and one answer from the person**. Everything else is derived from those; nothing is checked live. Only ask for an export that is listed here for the person's tool: if a tool has no such export, say so and don't ask. Don't tell the person an export exists unless they have confirmed it.

## Required

| prep.py flag | Data | Ahrefs | Semrush |
| --- | --- | --- | --- |
| `--backlinks` | Client backlinks, not grouped, live AND lost (don't filter to live or active only) | Site Explorer > Backlinks > All links, including lost links > Export. Lost links are marked in the `Lost` column (not yet tested in an audit) | Backlink Analytics > Backlinks > Export, not filtered to Active. Lost links are marked in the `Lost link` column |
| `--gap` (repeatable) | Domains linking to competitors, not the client | Competitive Analysis > Link Intersect (Referring domains mode) > Export | Backlink Gap (Missing or Best view) > Export |
| (not an export) | GSC Manual Actions result | The person reports it: Search Console > Security & Manual Actions > Manual actions | same |

Semrush Backlink Gap takes 5 domains, so with more than 4 competitors there are two gap files: pass `--gap` twice. prep.py merges them by domain. The Semrush gap export is a domain-level matrix only: `Domain, Domain ascore, <client>, <competitor columns>, Matches`. It has no referring-page URLs, so the Evidence URL column stays blank on Semrush audits.

## Derived from those two, no export needed

| What | How |
| --- | --- |
| Client referring domains, backlink counts, dofollow referring domains | Counted from the backlinks export (reported in the reply as the baseline for the next audit) |
| Anchor mix | Computed from the backlinks `Anchor` column |
| Lost backlinks | The backlinks rows marked lost (`lost.csv`). Semrush's export has a true/false flag and the last-seen date, not the reason a link was lost: the reason is only in the tool's UI |
| Link-gap domains per competitor | Counted from the gap export |

## Optional

Each one only adds detail. Use it if the person already has it; don't make them pull it.

| prep.py flag | What it adds | Ahrefs | Semrush |
| --- | --- | --- | --- |
| `--refdomains` | The linking domain's authority on Disavow Review and Recommendations. Semrush backlinks rows carry a page score, not the domain's AS, so this column is blank on Semrush without it (Ahrefs backlinks rows have DR) | Site Explorer > Referring domains > Export | Backlink Analytics > Referring Domains > Export |
| `--audit` | Tool Risk Score and Markers on Disavow Review | none | Backlink Audit > Audit tab > Export |
| `--gsc-links` | Fills "In GSC Links Report?" on Disavow Review | Search Console > Links > Export external links > Latest links, or Top linking sites | same |
| `--gap-pages` | Evidence URLs for opportunities | Link Intersect, Referring pages mode (not yet tested in an audit; confirm with the person that it exports before asking) | none: Backlink Gap has no page-level export |

## Identify files by their columns

People rarely name exports clearly. Open the header row of each file (read the first 2 lines only; never read a whole export into the chat) and match it to the table. Signals:

- Backlinks: one row per link, with a referring page URL and a target URL.
- Link gap: one row per referring domain, plus one column per domain (the header contains the domain). Semrush adds `Domain ascore` and `Matches`.
- Referring domains: one row per domain, no target URL.

## Encoding and column names

Ahrefs offers UTF-8 or UTF-16 CSV; Semrush uses comma CSV; GSC uses UTF-8 CSV. `read_table()` handles all of them.

prep.py prints, for each file, which column it used for each field and which fields it could not find. If a field maps to the wrong column, or a needed field is missing because the tool renamed it, re-run with `--map label.field="Exact column name"` (labels: backlinks, refdomains, gap, gap_pages, audit, gsc_links; fields are listed in `SPEC` at the top of prep.py). Required fields stop the run with the list of columns found.

## Export limits

Plans cap export rows. If a backlinks export has a round number of rows (1,000, 10,000, 50,000, 100,000) treat it as capped and say so in the notes: the Disavow Review tab only covers what was exported, and the client counts in the reply come from it too.
