# Service Page H1 & Title Tag Review workbook

`scripts/build.py` builds it. Arial throughout, header row dark blue with white bold text, frozen header, an Excel table (filters) on every tab, wrapped text, `#,##0` on clicks and impressions. Yellow marks the columns the writer fills in. Exactly two tabs, in this order, and nothing added to them.

## 1. Review

One row per crawled URL. With Search Console data, sorted by GSC Clicks (highest first), then GSC Impressions. Without it, in export order.

| Column | Content |
| --- | --- |
| URL | As exported |
| Review Needed | "Yes" (shaded) or "No". Filter on Yes to see every page a person must look at |
| Why Review | Each reason on its own line, in plain words (rules.md § When a person must review a page). Blank when Review Needed is No |
| Page Topic | What the page is about, as decided in SKILL.md Step 3 |
| Current Page Title | Title Tag as exported |
| Current H1 | H1 as exported |
| Suggested Page Title | Empty, yellow, for the writer |
| Suggested H1 | Empty, yellow, for the writer |
| Update to Include | Up to 5 keywords, one per line. With Search Console: `keyword - impressions`, highest first. Without: the keyword only, in the AI's order. The header carries a note saying what the numbers are (or that there are none) |
| GSC Clicks | Clicks in the date range (0 when GSC has no row). Only with Search Console data |
| GSC Impressions | Impressions in the date range. Only with Search Console data |
| Notes | Information only, e.g. "No GSC data for this page" |

## 2. Data

One row per crawled URL, in export order: URL, Page Path, H1, Title Tag, and with Search Console data GSC Clicks and GSC Impressions.

## QA

`build.py` prints PASS or FAIL for each and exits non-zero on a FAIL:
- Every crawled URL appears once in Data and once in Review.
- Update to Include has at most 5 keywords with no duplicates.
- With Search Console data, keywords are ordered by impressions.
- Every page has a topic.
- Every page with no keywords is marked Review Needed = Yes.
