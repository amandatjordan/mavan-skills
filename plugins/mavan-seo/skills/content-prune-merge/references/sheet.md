# Filling the template

Template: https://docs.google.com/spreadsheets/d/1T4vKYdOy6yl3x-bdNMNeLolYs9qDmXXdvmZkq1cqUOY/edit (file id `1T4vKYdOy6yl3x-bdNMNeLolYs9qDmXXdvmZkq1cqUOY`).

Tabs, whose names the formulas depend on: `TEMPLATE - Recommendations`, `TEMPLATE - Audit`, `TEMPLATE - Redirects`, `TEMPLATE - Existing Redirects`. Keep every tab name as it is.

| Tab | Write from | Columns | Fills itself |
| --- | --- | --- | --- |
| Audit | B2 | URL ... Notes (25 columns, rules.md order) | A (Area), from Suggested Next Step / Next Steps, Notes and Page Type Reason |
| Recommendations | B5 | Priority, Area, Problem, Do this | # (A), Pages (F), Where to find (G); FINAL decision (H) is a dropdown for the person |
| Existing Redirects | A2 | Source URL, Target URL, Notes | nothing |
| Redirects | never write | | the whole tab: Audit redirects plus Existing Redirects |

Before writing, open the template (`get_spreadsheet` with grid data for row 1-2 of each tab, or the downloaded .xlsx) and confirm the headers and formulas still match this table. If they differ, the template changed: follow the template and say so in the report.

## The workbook (always)

Build one workbook with `$SKILL/scripts/make_xlsx.py` from the TSV blocks the build scripts already write (`audit.tsv`, `recommendations.tsv`, `existing_redirects.tsv`, and `not_in_crawl.tsv`):

```
python $SKILL/scripts/make_xlsx.py --out "{Client} Content Pruning and Merging.xlsx" --audit work/audit.tsv --recs work/recommendations.tsv --existing work/existing_redirects.tsv --not-in-crawl work/not_in_crawl.tsv
```

Tabs: Recommendations, Audit, Existing Redirects, Not in crawl, with the template's column headers. The Audit Area column and the Recommendations Pages and Where to find columns are written as plain values that reproduce the template's formulas, so the file reads on its own. Text that looks like a number or starts with `=`, `+`, `-` or `@` is stored as text. The template reads exact Notes flag wording and Page Type Reason wording ("Root-level", "No rule matched"), so keep that text unchanged. Deliver the file once with SendUserFile and do not also hand over separate TSV files. If openpyxl cannot be installed, fall back to the TSV route at the end of this file.

To move it into the template: open the template link, File > Make a copy, then paste Audit columns B:Z at **B2** of TEMPLATE - Audit (never over column A) and the Recommendations columns B:E at **B5** of TEMPLATE - Recommendations, and Existing Redirects at **A2**. The template's own formulas then fill column A and the Pages columns.

## With Google Drive and Sheets connectors

1. Copy the whole template file with the Drive connector (`copy_file`), titled `{Client} Content Pruning and Merging`.
2. Write only the Recommendations rows (about 11) with Sheets `update_values` at B5. Do not write the Audit or Existing Redirects through the connector: hundreds of rows cell by cell was the slowest step of earlier runs. Tell the person to import or paste those two tabs from the workbook.
3. Read the Recommendations back with `get_values` and compare. Done when it matches and the Pages column shows values.

## Without connectors

The workbook above is the whole deliverable. Give the paste steps from "To move it into the template" and ask the person to check that column A of the Audit tab and the Pages column of the Recommendations tab show values.

## Fallback: TSV files (only if openpyxl is unavailable)

Hand back three tab-separated files with no header row, plus the paste steps: `audit.tsv` at **B2** of the Audit tab, `recommendations.tsv` at **B5** of the Recommendations tab, `existing_redirects.tsv` at **A2** of the Existing Redirects tab. Keep tabs and newlines out of every cell (replace with spaces), or the paste shifts columns.
