# Search Console and GA4 data

Window: the last 90 days, ending 3 days ago (GSC lags). Use the same window for every source. Brand terms are handled in the Search Console export itself: do not ask for brand terms and do not filter queries yourself. Say in the report that you used the export's queries as given.

## Ask for files first

Ask for these in one message at the start of the run, naming the window (last 90 days, ending 3 days ago), and carry on with whatever arrives:

- **Search Console, page + query** (needed for overlap and keyword counts): the Search Analytics for Sheets add-on or a Looker Studio table with dimensions Page and Query, exported as CSV or XLSX. The Search Console UI export gives pages and queries separately and caps at 1,000 rows, so it cannot show overlap.
- **Search Console, pages**: Performance > Pages (fine if the page + query export already covers it).
- **GA4 landing pages**: Reports > Engagement > Landing page (or an Exploration) with Sessions, New users, Views and Key events.

Files are the main route for Search Console. Composio is the fallback when a Search Console file is missing, and the default route for GA4 when no file was attached (see GA4 and the end of this file).

## Reading the page + query export

Exports from the add-on or Looker Studio are messy. Handle these in code before anything else:

- **Several sheets in one file**, separated by lines like `## Sheet name:`. Read each sheet separately. Use the sheet that holds every page + query row; ignore sheets that are a filtered subset of it (for example a top-queries or single-folder sheet). Say which sheet you used.
- **Thousands separators** in numbers (`"1,853"`): strip the commas before converting to numbers.
- **UTM and other query-string variants** of the same page: strip the query string and fragment, then add up the rows that now share a URL. Normalize with the same rule as the crawl (lowercase, https, non-www, trailing slash).
- **Case duplicates:** `/Page-Name/` and `/page-name/` join on the lowercase path; flag the duplicate URL from the crawl.
- **Non-site paths in GA4:** booking-widget UUID folders, `/to/` short links, `(not set)`. Confirm they are not pages on the site, then exclude them.

## GA4

1. **Get it.** Use the GA4 landing page file when one was given. Otherwise, whenever Composio is connected, pull it yourself without waiting to be asked: `GOOGLE_ANALYTICS_LIST_ACCOUNT_SUMMARIES` to find the property by client name, then `GOOGLE_ANALYTICS_RUN_REPORT` with dimension `landingPage` and metrics `sessions, newUsers, screenPageViews, keyEvents` for the 90-day window (end 3 days ago). If no file and no connection, leave GA4 blank and say so.
2. **200-session rule.** If total GA4 sessions in the window are under 200, skip GA4: leave Conversions, New Users, Sessions and Views blank, do not estimate them, spend no more time on it, and say in one report line that GA4 was skipped and why, with the total.
3. **Optional diagnosis, one call.** When GA4 is skipped or looks low, run a monthly sessions report (dimension `month` or `yearMonth`, metric `sessions`) to show when tracking broke (for example about 1,500 sessions a month, then 35, 31 and 23). Tell the person to check the GA4 tag. Do not change the window.
4. **Context only.** Compare total GA4 sessions with Search Console clicks and mention a large gap in the report as context. It does not change what gets filled in; the 200-session rule decides.

## Pages the crawl does not have

Build `work/not_in_crawl.tsv` from the data: every URL that appears in Search Console or GA4 but not in the crawl, with `url | clicks | impressions | sessions | redirect target if it is a source in the redirects export`. Make no status checks and no live requests. The crawl's status codes are the truth, and the redirects export gives where a URL went. This file feeds the 404-with-demand rows in references/redirects-qa.md.

## Overlap

For each pair of pages: shared non-brand impressions as a share of the smaller page's non-brand total. Never compare every pair: generic "[treatment] [city]" queries hit dozens of pages on local sites, so global pairwise overlap is noise. Compare only:

- pages in the same topic group. Build the groups first: pages that share the same top query, or the same main term in the title, H1 or slug (a treatment family such as the brands of one product type, or one body area), and
- concern pages against service pages,

with a floor of 20 impressions on both pages. Keep each page's strongest competitor (highest share, then the competitor with more impressions) and the top shared query for the Competes flag. Save the groups to `work/overlap_groups.tsv` (group ID | URLs | shared top query) so the report can show how pages were grouped.

Without a page + query export: fill clicks and impressions from the pages export, leave No. Keywords blank, skip suggestion rule 2 and the Competes flags, and say in the report that overlap could not be measured. Never estimate a missing number.

## Composio: pull only what this audit needs

Every Composio call in this skill (Search Console and GA4) follows these limits. Data pulled through Composio is filtered at the source, never pulled wide and trimmed afterwards:

- **Window:** the 90-day window only (end 3 days ago), the same for every call. No longer ranges, no comparison periods.
- **Search Console:** the client's property only. Dimensions `page` (clicks, impressions) and `page,query`, nothing else: no device, country, search appearance or date splits.
- **GA4:** the client's property only. Dimension `landingPage` and metrics `sessions, newUsers, screenPageViews, keyEvents`, nothing else. The one extra call allowed is the monthly sessions report in the GA4 section, and only when GA4 is skipped or looks low.
- **Row limits:** request no more rows than the site has live pages (plus a margin), and stop paging as soon as a page comes back short.
- **Aggregate in the workbench:** join and total there, bring back one compact row per page, and never print raw rows into the chat.
- **Search Composio tools only for the use cases listed in the fallback below.** Do not run other Composio tools or pull other reports "while you are there".

## Fallback: Composio

Use only for a source whose file was not provided.

1. `COMPOSIO_SEARCH_TOOLS` with use cases for listing Search Console sites, querying search analytics by page and query, listing GA4 account summaries and running a GA4 report. If Search Console or Google Analytics shows no active connection, say so and ask for that file.
2. Use the Search Console property exactly as listed for the domain (prefer `sc-domain:`). Find the GA4 property with `GOOGLE_ANALYTICS_LIST_ACCOUNT_SUMMARIES` by display name.
3. Pull inside `COMPOSIO_REMOTE_WORKBENCH` with `row_limit: 25000`, paginating with `start_row` until a page comes back short: `page` (clicks, impressions), `page,query`, and GA4 `GOOGLE_ANALYTICS_BATCH_RUN_REPORTS` with dimension `landingPage` and metrics `sessions, newUsers, screenPageViews, keyEvents` (plus `eventName` with `keyEvents` so the report can say what counts as a conversion). If the site has more than about 300 live pages, do not page through `page,query` in Composio: ask for the file.
4. Aggregate in the workbench and print compact tab-separated rows, one per normalized page: `path, clicks, impressions, nonbrand_queries, top_query, top_query_impressions, sessions, new_users, views, key_events`. The workbench's file links are blocked and the rows cannot be downloaded, so bring them back by printing in chunks of about 40KB. Write them to `work/gsc/*.tsv`, then verify with row counts, column sums and an md5 of one text column computed in both places; a mismatch means a copy error, so print that chunk again. Retyping rows by hand is never the plan: if more than a few hundred rows are needed, stop and ask for the file.
