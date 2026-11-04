# Filling the template

Template: https://docs.google.com/spreadsheets/d/1T4vKYdOy6yl3x-bdNMNeLolYs9qDmXXdvmZkq1cqUOY/edit (file id `1T4vKYdOy6yl3x-bdNMNeLolYs9qDmXXdvmZkq1cqUOY`).

Tabs, whose names the formulas depend on: `TEMPLATE - Recommendations`, `TEMPLATE - Audit`, `TEMPLATE - Redirects`, `TEMPLATE - Existing Redirects`. Keep every tab name as it is.

| Tab | Write from | Columns | Fills itself |
| --- | --- | --- | --- |
| Audit | B2 | URL ... Notes (25 columns, rules.md order) | A (Area), from Suggested Next Step / Next Steps, Notes and Page Type Reason |
| Recommendations | B5 | Priority, Area, Problem, Do this | # (A), Pages (F), Where to find (G); FINAL decision (H) is a dropdown for the person |
| Existing Redirects | A2 | Source URL, Target URL, Notes | nothing |
| Redirects | never write | | the whole tab: Audit redirects plus Existing Redirects |

## The workbook (always)

Build one workbook with `$SKILL/scripts/make_xlsx.py` from the TSV blocks the build scripts already write (`audit.tsv`, `recommendations.tsv`, `existing_redirects.tsv`, and `not_in_crawl.tsv`):

```
python $SKILL/scripts/make_xlsx.py --out "{Client} Content Pruning and Merging.xlsx" --audit work/audit.tsv --recs work/recommendations.tsv --existing work/existing_redirects.tsv --not-in-crawl work/not_in_crawl.tsv
```

Tabs: Recommendations, Audit, Existing Redirects, Not in crawl, with the template's column headers. The Audit Area column and the Recommendations Pages and Where to find columns are written as plain values that reproduce the template's formulas, so the file reads on its own. Text that looks like a number or starts with `=`, `+`, `-` or `@` is stored as text. The template reads exact Notes flag wording and Page Type Reason wording ("Root-level", "No rule matched"), so keep that text unchanged. Deliver the file once with SendUserFile and do not also hand over separate TSV files.

To move it into the template: open the template link, File > Make a copy, then paste Audit columns B:Z at **B2** of TEMPLATE - Audit (never over column A) and the Recommendations columns B:E at **B5** of TEMPLATE - Recommendations, and Existing Redirects at **A2**. The template's own formulas then fill column A and the Pages columns.

## Delivery

The workbook is the whole deliverable, for everyone: no connector is used to copy the template or write rows. Give the paste steps from "To move it into the template" and ask the person to check that column A of the Audit tab and the Pages column of the Recommendations tab show values.
