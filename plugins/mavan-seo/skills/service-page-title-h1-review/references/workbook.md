# Service Page H1 & Title Tag Review workbook

`scripts/build.py` builds it. Arial throughout, header row dark blue with white bold text, frozen header, an Excel table (filters) on every tab, wrapped text. Yellow marks the columns the writer fills in. Exactly two tabs, in this order, and nothing added to them.

## 1. Review

One row per crawled URL. In export order.

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
| Suggested Keywords | Up to 5 keywords separated by commas (`keyword, keyword`), most important first. The header carries a note that they are not search volume |
| Top GSC Queries (impressions/clicks) | Only with Search Console. Up to 10 non-branded queries, at least 5 impressions each, `query (impressions/clicks); ...`. Width about 80 |
| Notes | Information only |

## 2. Data

One row per crawled URL, in export order: URL, Page Path, H1, Title Tag.

## QA

`build.py` prints PASS or FAIL for each and exits non-zero on a FAIL:
- Every crawled URL appears once in Data and once in Review.
- Suggested Keywords has at most 5 keywords with no duplicates.
- Top GSC Queries has at most 10 queries per page, none under 5 impressions and none branded.
- Every page has a topic.
- Every page with no keywords is marked Review Needed = Yes.
