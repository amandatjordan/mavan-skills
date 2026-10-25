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

## With Google Drive and Sheets connectors

1. Copy the whole template file with the Drive connector (`copy_file`), titled `{Client} Content Pruning and Merging`.
2. Write with Sheets `update_values` in chunks of about 60 rows (bigger calls hit size limits). Numbers as numbers, blanks as `""`.
3. Read back with `get_values` (large results save to a file; compare that file to your source rows in Python). Done when every written cell matches and the Area column and Recommendations Pages column show values.

## Without connectors

Hand back three tab-separated files with no header row, plus the steps to paste them:

- `audit.tsv`: paste at **B2** of the Audit tab.
- `recommendations.tsv`: paste at **B5** of the Recommendations tab.
- `existing_redirects.tsv`: paste at **A2** of the Existing Redirects tab.

Steps for the person: open the template link, File > Make a copy, name it `{Client} Content Pruning and Merging`, click the cell named above on each tab and paste. Then check that column A of the Audit tab and the Pages column of the Recommendations tab show values.

Keep tabs and newlines out of every cell before writing a .tsv (replace with spaces), or the paste shifts columns.
