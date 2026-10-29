# Service Page H1 & Title Tag Review workbook

`scripts/build.py` builds it. Arial throughout, header row dark blue with white bold text, frozen header, an Excel table (filters) on every tab, wrapped text, `#,##0` on clicks and impressions. Yellow marks the columns the writer fills in. Exactly three tabs, in this order, and nothing added to them.

## 1. Review

One row per crawled URL. With Search Console data, sorted by GSC Clicks (highest first), then GSC Impressions. Without it, in export order.

| Column | Content |
| --- | --- |
| URL | As exported |
| Review Needed | "Yes" (shaded) or "No". Filter on Yes to see every page a person must look at |
| Why Review | Each reason on its own line, in plain words (rules.md § When a person must review a page). Blank when Review Needed is No |
| Page Topic | What the page is about, as decided in SKILL.md Step 3, e.g. "dermabrasion; facial sanding" |
| Current Page Title | Title Tag as exported |
| Current H1 | H1 as exported |
| Suggested Page Title | Empty, yellow, for the writer |
| Suggested H1 | Empty, yellow, for the writer |
| Update to Include | Up to 5 lines, `keyword - volume`, highest volume first. The header carries a note that volume is competitor-ranked and for ranking only |
| GSC Clicks | Clicks in the date range (0 when GSC has no row). Only with Search Console data |
| GSC Impressions | Impressions in the date range. Only with Search Console data |
| Matching Notes | Information only, joined with " \| ": the taxonomy's entry for the page and the field it matched (or that the topic says the guess was wrong), entries whose keywords were also offered because they have no page in the crawl, and "No GSC data" |

## 2. Recommendations

One row per implied page missing from the crawl (rules.md § Implied entries and missing pages), Service first, then Sub-Service, then Brand / Device.

| Column | Content |
| --- | --- |
| Recommended Page | Service name, or Sub-Service / Brand / Device with its parent, e.g. "Lip Filler (Dermal Filler)" |
| Level | Service, Sub-Service or Brand / Device |
| Implied By (URL) | Every crawled URL that implies it, one per line |
| Reason | "Implied by the [entry] page; no crawled page maps to [recommended page]." |

With no rows, the tab holds one row: "None" and "No implied page is missing from the crawl."

## 3. Data

One row per crawled URL, in export order: URL, Page Path, H1, Title Tag, and with Search Console data GSC Clicks and GSC Impressions.

## QA

`build.py` prints PASS or FAIL for each and exits non-zero on a FAIL:
- Every crawled URL appears once in Data and once in Review.
- Update to Include has at most 5 lines, sorted by volume, with no duplicate keywords.
- Every page has a topic.
- Every page with no keywords is marked Review Needed = Yes.
- Every Recommendations row names crawled URLs.

## Missing-keywords file

When a topic term has few or no keywords in the list, `build.py` also writes `<workbook name>_missing_keywords.csv` next to the workbook: Topic, Keywords found in the list, Pages (URL). It is for Amanda, to add keywords to the taxonomy. It is not a tab.
