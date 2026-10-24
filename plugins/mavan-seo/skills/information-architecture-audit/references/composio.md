# Search Console and GA4 through Composio

`scripts/gsc_workbench.py` runs inside Composio's remote workbench (`COMPOSIO_REMOTE_WORKBENCH`), not here. Its state persists between workbench calls and it saves everything to `/mnt/files/ia/`, so if the sandbox restarts, send the file again and carry on from the step you were on.

## 1. Find the property

Call `COMPOSIO_SEARCH_TOOLS` (use case: list Search Console sites; query search analytics by page and query; run a GA4 report). Its connection status lists the Search Console properties. Pick the one for the domain, preferring `sc-domain:`, and copy it exactly as listed. If neither Search Console nor GA4 shows an active connection, tell the person Composio needs Google Search Console and Google Analytics connected with the Mavan Google login (SOP Step 1) and continue without them.

## 2. Load the script

Send the whole of `gsc_workbench.py` as `code_to_execute`, with one line appended that sets the client:

```python
CONFIG.update({'site_url': 'sc-domain:example.com', 'domain': 'example.com',
               'brand_terms': ['example', 'nickname'], 'ga4_property': None})
```

Brand terms are lowercase. If the GA4 property is unknown, append `ia_ga4_properties()` too, pick the match it prints, and set `CONFIG['ga4_property'] = 'properties/123456789'` at the start of the next call.

## 3. Pull the data (one workbench call each)

1. `ia_months()`: 16 months by page. Prints a monthly table and a suggested window. A migration shows up as months where a large share of impressions sits on URLs that no longer get any. Use the period after the migration as the window; with no migration, the last 3 full months it prints.
2. `ia_window('YYYY-MM-DD', 'YYYY-MM-DD')`: page totals, page + query (paginated until short of 25,000 rows), GA4 landing pages. If GA4 fails, it says so and carries on.
3. `ia_build()`: builds the tables and prints the `ia_emit(...)` calls needed to bring them back, grouped so each call stays under the output limit.

Composio prints a response-schema preview the first time a tool runs in a call; ignore it.

## 4. Bring the tables back

Run each printed `ia_emit(...)` call. Save its output, exactly as printed, from the first `##IA` line to the last `##END` line, to a new file in `work/gsc/` (e.g. `work/gsc/emit_1.txt`). Then:

```
python $SKILL/scripts/gsc_import.py --dir work/gsc
```

Every block carries a row count and checksum. A block that fails was copied wrong: run that `ia_emit` again and save it again over the bad file. Done when it prints "Loaded" for meta, monthly, pages, pairs, noowner and home, with no PROBLEMS.

## 5. Follow-ups from analyze.py

analyze.py's `next_steps.md` prints two more workbench calls. Run each and save its block to `work/gsc/` the same way, then re-run gsc_import.py and analyze.py:

- `ia_crawl_split([...])`: the SOP's migration check split into URLs live in the crawl vs not, for the Read Me table. It needs the crawl, which Composio can't see, so analyze.py passes it the ids of pages that aren't live.
- `ia_pair_queries([...])`: top shared searches for the duplicate and city-variant pairs. Rounds add up, so after a later review round you only run it for the new pairs.
