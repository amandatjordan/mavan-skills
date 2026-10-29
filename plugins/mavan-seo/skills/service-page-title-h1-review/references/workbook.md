# Service Page H1 & Title Tag Review workbook

`scripts/build.py` builds it. Arial throughout, header row dark blue with white bold text, frozen header, an Excel table (filters) on every tab, wrapped text, `#,##0` on clicks and impressions. Yellow marks the columns the writer fills in. Exactly three tabs, in this order, and nothing added to them.

## 1. Review

One row per crawled URL, sorted by GSC Clicks (highest first), then GSC Impressions.

| Column | Content |
| --- | --- |
| URL | As exported |
| Matched Taxonomy Entry | "Level: Entry (Parent)", e.g. "Sub-Service: Lip Filler (Dermal Filler)", or "Needs review" |
| Current Page Title | Title Tag as exported |
| Current H1 | H1 as exported |
| Suggested Page Title | Empty, yellow, for the writer |
| Suggested H1 | Empty, yellow, for the writer |
| Update to Include | Up to 5 lines, `keyword - volume`, highest volume first. The header carries a note that volume is competitor-ranked and for ranking only |
| GSC Clicks | Clicks in the date range (0 when GSC has no row) |
| GSC Impressions | Impressions in the date range |
| Notes | Joined with " \| ": what matched (path, H1 or title), the Needs review reason, entries whose keywords were also used, "No keywords found in taxonomy", "No GSC data", "Blank H1", "Blank Title Tag" |

## 2. Recommendations

One row per implied page missing from the crawl (rules.md § Implied entries), Service first, then Sub-Service, then Brand / Device.

| Column | Content |
| --- | --- |
| Recommended Page | Service name, or Sub-Service / Brand / Device with its parent, e.g. "Lip Filler (Dermal Filler)" |
| Level | Service, Sub-Service or Brand / Device |
| Implied By (URL) | Every crawled URL that implies it, one per line |
| Reason | "Implied by the [entry] page; no crawled page maps to [recommended page]." |

With no rows, the tab holds one row: "None" and "No implied page is missing from the crawl."

## 3. Data

One row per crawled URL, in export order: URL, Page Path, H1, Title Tag, GSC Clicks, GSC Impressions.

## QA

`build.py` prints PASS or FAIL for each and exits non-zero on a FAIL:
- Every crawled URL appears once in Data and once in Review.
- Update to Include has at most 5 lines, sorted by volume, with no duplicate keywords.
- Needs review rows have no keywords.
- Every Recommendations row names crawled URLs.
