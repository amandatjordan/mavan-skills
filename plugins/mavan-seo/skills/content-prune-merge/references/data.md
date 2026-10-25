# Search Console and GA4 data

Window: the last 12 full months, ending 3 days ago (GSC lags). Brand terms are removed from every query count and overlap (case-insensitive regex of the client name, doctor's name and misspellings).

## With Composio

1. `COMPOSIO_SEARCH_TOOLS` with use cases for listing Search Console sites, querying search analytics by page/query/date, listing GA4 account summaries and running a GA4 report. If Search Console or Google Analytics shows no active connection, switch to **Without Composio** for that source and say so.
2. Use the Search Console property exactly as listed for the domain (prefer `sc-domain:`; it may be `https://domain/`). Find the GA4 property with `GOOGLE_ANALYTICS_LIST_ACCOUNT_SUMMARIES` by display name.
3. Pull inside `COMPOSIO_REMOTE_WORKBENCH` (its state persists between calls; save raw results to `/mnt/files/<client>/`), `row_limit: 25000`, paginating with `start_row` until a page comes back short:
   - `page`, 12 months: clicks and impressions per page.
   - `date,page`, 16 months: the migration check.
   - `page,query`, 12 months: non-brand query count, top non-brand query, overlap.
   - GA4 `GOOGLE_ANALYTICS_BATCH_RUN_REPORTS`: dimension `landingPage`, metrics `sessions, newUsers, screenPageViews, keyEvents`; and `eventName` with `keyEvents` so the report can say what counts as a conversion.
4. **Aggregate in the workbench** and print compact tab-separated rows, one per normalized page: `path, clicks, impressions, nonbrand_queries, top_query, top_query_impressions, sessions, new_users, views, key_events`. Print the overlap list the same way (see Overlap). Composio returns about 40KB per call, so split long tables across calls.
5. **Bring the rows back by printing, not downloading:** the workbench's file links are blocked by the egress proxy. Write the printed rows to `work/gsc/*.tsv` here, then verify with row counts, column sums and an md5 of one text column computed in both places. A mismatch means a copy error: print that chunk again.

The workbench can also fetch the live site (`requests`), which the local shell often cannot: use it for the sitemap and status checks in SKILL.md Step 4.

## Without Composio

Ask the person for whichever exports are missing, in one message:

- **Search Console, page + query** (needed for overlap and keyword counts): the Search Analytics for Sheets add-on or a Looker Studio table with dimensions Page and Query for the window, exported as CSV. The Search Console UI export alone gives pages and queries separately and caps at 1,000 rows, so it cannot show overlap.
- **Search Console, pages**: Performance > Pages for the window, exported (fine if the page+query export already covers it).
- **Search Console, by month** (migration check, optional): Performance with 16 months, compare mode or a Date + Page table.
- **GA4**: Reports > Engagement > Landing page (or an Exploration) for the window with Sessions, New users, Views and Key events, exported as CSV.

If only the UI page export is available: fill clicks and impressions, leave No. Keywords blank, skip suggestion rule 2 and the Competes flags, and say in the report that overlap could not be measured. Never estimate a missing number.

## Checks on the data

- **Migration:** monthly impressions on URLs live in the crawl vs URLs that are not. A small, fading non-live share means no migration: say so and use the 12-month window. A step change means a migration: use the period after it, and credit old URLs to the page they now redirect to.
- **Non-site paths in GA4:** booking-widget UUID folders, `/to/` short links, `(not set)`. Confirm they are not pages on the site, then exclude them.
- **Case duplicates:** GSC may report `/Facelift/` and `/facelift/` separately; join on the lowercase path and flag the duplicate URL from the crawl.

## Overlap

For each pair of pages: shared non-brand impressions as a share of the smaller page's non-brand total. Global pairwise overlap is noise on local sites (generic "[treatment] [city]" queries hit dozens of pages), so compare only:

- pages in the same treatment group (a slug regex per treatment: botox|jeuveau|neurotoxin, filler|juvederm, lipo, tummy-tuck|abdominoplasty, breast-lift, ...), and
- concern pages against service pages,

with a floor of 20 non-brand impressions on both pages. Keep each page's strongest competitor (highest share, then the competitor with more impressions) and the top shared query for the Competes flag.
