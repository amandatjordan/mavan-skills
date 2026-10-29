# Search Console through Composio

This is the only use of Composio in this skill. It pulls clicks and impressions by page and query for the crawled URLs and nothing else. No GA4. The queries are how the keywords are ranked.

**Tools allowed:** `COMPOSIO_SEARCH_TOOLS`, `COMPOSIO_GET_TOOL_SCHEMAS` (only to read the parameters of the one tool you found) and `COMPOSIO_MULTI_EXECUTE_TOOL`. Do not use the remote workbench, remote bash or any other Composio tool without asking the person first and explaining why it is needed.

## 1. Find the tool and the property

Call `COMPOSIO_SEARCH_TOOLS` (use case: query Search Console search analytics by page). Its connection status lists the Search Console properties. If there is no active Search Console connection, tell the person Composio needs Google Search Console connected with an account that has access to the client's property, and build the workbook without numbers (SKILL.md Step 1). Do not substitute another source.

Do not assume the tool name or the property. Use the tool Composio returns, and show the person the property you will use (and whether it is a domain or URL-prefix property) next to the date range, and wait for a yes.

## 2. Date range

Default: the 90 days ending 3 days before today (the newest days are often incomplete), unless the person gave dates. One fixed range for every request.

## 3. Filtering rules (follow all of them)

- Ask for only the **page** and **query** dimensions and the **clicks** and **impressions** metrics. No device, country, search appearance or date dimensions.
- Filter every request to the crawled URLs with a page filter, in small batches (start with about 10 URLs from `work/urls.txt`, because every page returns many query rows). Never pull the whole site and filter afterward.
- Set the row limit to about 100 rows per URL in the batch (for example 1,000 for 10 URLs), never to the site maximum. Search Console returns the highest-click queries first, which is what the ranking needs.
- If a batch fails (for example, the filter is too long), make the batch smaller and retry it. Do not fall back to pulling the whole site.
- Keep only the URL, query, clicks and impressions from each response. Do not paste raw responses into the chat or into the workbook.
- Use the tool's own parameter names; the names above are Search Console's.

## 4. Save every batch as it comes back

Save each response's rows exactly as returned, as JSON, to `work/gsc/batch_N.json` (any wrapper the tool added is fine; `build.py` finds the rows inside it). Do not retype numbers into another format. `build.py` prints the row count of each file; it must match the number of rows the response returned. If it reads 0 rows from a file, stop and show the person the response shape instead of guessing a format.

URLs the crawl lists but GSC does not return get 0 clicks and 0 impressions, keep the AI's keyword order and the note "No GSC data for this page". That is normal for new or unindexed pages.
