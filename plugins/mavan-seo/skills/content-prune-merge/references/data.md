# Search Console and GA4 data

Search Console data comes only from the person (a Google Sheet, or a download of it). Never pull Search Console through Composio or any other connector query. GA4 comes from a file, or through Composio only when Step 3 of SKILL.md allows it.

**Date range.** Ask the person which dates the Search Console data covers (pre-flight item 5); the add-on export has no date column, so it cannot be read from the file. Recommend the last 90 days, ending 3 days ago (Search Console lags). Use the same dates for GA4. Write the range into the report. If the person does not know, say in the report that the range is unconfirmed.

Brand terms are handled in the Search Console export itself: do not ask for brand terms and do not filter queries yourself. Say in the report that you used the export's queries as given.

## Getting the Search Console data

The person pastes the Google Sheet link into the chat. The Claude app then attaches the sheet itself as a file (every tab, separated by `## Sheet name:` lines), so read that attached file in code, like any other export: it never passes through the conversation and its size does not matter. Use the link only to confirm which sheet it is (for example its tab names with the Sheets connector's `get_spreadsheet`); do not read the rows through the connector.

If a link is pasted but no attached file arrives, ask the person to paste the link again, or to attach a CSV or XLSX of the sheet. A CSV or XLSX attached directly is accepted too.

The data needs Page, Query, Clicks and Impressions columns (CTR and Position are optional). It is made with the Search Analytics for Sheets add-on or a Looker Studio table. The Search Console UI export gives pages and queries separately and caps at 1,000 rows, so it cannot show overlap: if that is all the person has, say so and ask for the add-on export.

## Reading the page + query data

Exports from the add-on or Looker Studio are messy. Handle these in code before anything else:

- **Several sheets in one file or link**, in a download separated by lines like `## Sheet name:`. Read each sheet separately. Use the sheet that holds every page + query row; ignore sheets that are a filtered subset of it (fewer rows, a minimum-impressions filter, a top-queries or single-folder sheet). Say which sheet you used and why.
- **Thousands separators** in numbers (`"1,853"`): strip the commas before converting to numbers.
- **UTM and other query-string variants** of the same page: strip the query string and fragment, then add up the rows that now share a URL. Normalize with the same rule as the crawl (lowercase, https, non-www, trailing slash).
- **Case duplicates:** `/Page-Name/` and `/page-name/` join on the lowercase path; flag the duplicate URL from the crawl.
- **Join on the crawl's primary rows** (`primary` column of `work/crawl_pages.csv`), never on every crawl row: `/page` (301) and `/page/` (200) share a key.
- **Non-site paths in GA4:** booking-widget UUID folders, `/to/` short links, `(not set)`. Confirm they are not pages on the site, then exclude them.

## GA4

SKILL.md Step 3 decides whether GA4 is read, pulled or skipped. Under 300 Search Console clicks in the window, GA4 is never pulled through Composio.

1. **File.** Use the GA4 landing page file when one was given: Reports > Engagement > Landing page (or an Exploration) with Sessions, New users, Views and Key events, for the same dates.
2. **Composio, check first.** With no file, 300+ Search Console clicks and Composio connected: find the property with `GOOGLE_ANALYTICS_LIST_ACCOUNT_SUMMARIES` by client name, then run ONE `GOOGLE_ANALYTICS_RUN_REPORT` with dimension `yearMonth` and metric `sessions` for the window. It gives the total and shows whether tracking broke partway (for example about 1,500 sessions a month, then 35, 31 and 23).
3. **200-session rule.** Under 200 sessions in total: skip GA4. Leave Conversions, New Users, Sessions and Views blank, do not estimate them, spend no more time on it, and say in one report line that GA4 was skipped, why, and the total. If sessions collapsed partway, tell the person to check the GA4 tag.
4. **Composio, landing pages.** 200 or more: one `GOOGLE_ANALYTICS_RUN_REPORT` with dimension `landingPage` and metrics `sessions, newUsers, screenPageViews, keyEvents`, for the window, `limit` no more than the live page count plus a margin. Aggregate in `COMPOSIO_REMOTE_WORKBENCH` and print compact tab-separated rows, one per normalized page (`path, sessions, new_users, views, key_events`), in chunks of about 40KB; write them to `work/ga4.tsv` and check the row count and the sessions total against the workbench. Never retype rows by hand.
5. **Context only.** Compare total GA4 sessions with Search Console clicks and mention a large gap in the report. It does not change what gets filled in.

Composio limits: the client's GA4 property only, the window only, the two reports above and nothing else, no other Composio tools.

## Pages the crawl does not have

Build `work/not_in_crawl.tsv` from the data: every URL that appears in Search Console or GA4 but is not a live page in the crawl, with `url | clicks | impressions | sessions | redirect target` (the `final` page from `work/redirects.csv` when the URL is a redirect source). Make no status checks and no live requests. The crawl's status codes are the truth, and the redirects export gives where a URL went. This file feeds the demand rows in references/redirects-qa.md.

## Topic groups

Overlap is measured only inside topic groups and between concern and service pages, because generic "[treatment] [city]" queries hit dozens of pages on local sites, so overlap across every pair is noise.

1. **From Search Console.** Pages with 20+ impressions are grouped by the queries they share: two pages are in the same group when they share their top query, or when one page's top query is among the other page's queries. Groups that chain together through shared pages merge into one.
2. **From titles, confirmed by the person.** Pages with under 20 impressions have too little data to share queries. Propose groups for them from their titles (pages whose titles name the same treatment or concern), show them as chat text (group | pages | the title words they share), and ask in one question whether the groups are right. Use only the groups the person confirms. Never group by fuzzy slug matching.

Save the groups to `work/overlap_groups.tsv` (group ID | source: GSC or title | URLs | shared top query or title words) so the report can show how pages were grouped.

## Overlap

For each pair of pages compared (same topic group, or a concern page and a service page that share any query):

- **Shared impressions** = for each query both pages appear for, the smaller of the two pages' impressions for that query, added up.
- **Share** = shared impressions ÷ the smaller page's total impressions.
- **Counts** only when both pages have 20+ impressions and the shared impressions are 10 or more. Without the 10 floor, a 21-impression page reads as "100% overlapped" by any bigger page.
- **30%+** is the bar for rule 3 (overlap) in references/rules.md.

Keep each page's strongest competitor (highest share, then the competitor with more impressions) and the shared query with the most shared impressions, for the Competes flag.

Without page + query data: fill clicks and impressions from a pages export if there is one, leave No. Keywords blank, skip rule 3 and the Competes flags (city copies, rule 2, do not need it), and say in the report that overlap could not be measured. Never estimate a missing number.
