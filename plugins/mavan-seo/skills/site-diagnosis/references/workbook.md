# Triage workbook (what each tab holds)

Written by `triage.py build`. Claude does not write or reword workbook text. Change = period B minus period A.

| Tab | Contents |
| --- | --- |
| Summary | Clicks and impressions for both periods: all searches, non-brand, brand; pages with impressions; non-brand searches; change and % change. With a crawl: Search Console pages grouped by crawl status (200 OK, 3xx redirect, 404 not found, other 4xx, 5xx, Not in crawl) with their non-brand impressions and clicks. Notes on how to read it. |
| Pages | Top N losses and top N gains, ranked by non-brand impressions (or clicks) change. Both periods, the change, and all-search totals. A Status column when a crawl was given. |
| Searches | Same for non-brand searches: both periods, the change, how many pages the search appeared on, average position. |
| Pages behind searches | For each listed losing search, every page it appeared on in either period, with impressions, clicks and average position for each period (and crawl status). |
| Competing pages | Non-brand searches where two or more pages each have at least the confirmed minimum impressions, in period A, period B or both. Each page's impressions, clicks and average position for each period. The most impressions first, capped at Top N searches; the note above the table gives the full count. |
| What to run next | Content Prune & Merge, Information architecture audit, Backlink audit, Service gap audit: the evidence, the rule that was confirmed with the person, and Yes / No / Ask the person. |

Average position is impression-weighted across the rows listed. A page's or search's numbers are the sum of its listed page + query rows, so they can be lower than the Performance report.
