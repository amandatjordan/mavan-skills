# Search Console and GA4 through Composio

`scripts/gsc_workbench.py` runs inside Composio's remote workbench (`COMPOSIO_REMOTE_WORKBENCH`), not here. Its state persists between workbench calls and it saves everything to `/mnt/files/ia/`, so if the sandbox restarts, send the file again and carry on from the step you were on.

## 1. Find the property

Call `COMPOSIO_SEARCH_TOOLS` (use case: list Search Console sites; query search analytics by page and query; run a GA4 report). Its connection status lists the Search Console properties. Pick the one for the domain, preferring `sc-domain:`, and copy it exactly as listed. If neither Search Console nor GA4 shows an active connection, tell the person Composio needs Google Search Console and Google Analytics connected with a Google account that has access to the client's properties, and continue without them.

## 2. Load the script

Send the whole of `gsc_workbench.py` as `code_to_execute`, with one line appended that sets the client:

```python
CONFIG.update({'site_url': 'sc-domain:example.com', 'domain': 'example.com',
               'brand_terms': ['example', 'nickname'], 'ga4_property': None})
```

Brand terms are lowercase. If the GA4 property is unknown, append `ia_ga4_properties()` too, pick the match it prints, and set `CONFIG['ga4_property'] = 'properties/123456789'` at the start of the next call.

## 3. Pull the data (one workbench call each)

1. `ia_window()`: the last 6 full calendar months (it prints the dates; there is no migration check). Pulls page totals, page + query (paginated until short of 25,000 rows, one slice per month so the slices run in parallel), and GA4 landing pages with sessions and key events. If GA4 fails, it says so and carries on.
2. `ia_build()`: builds the tables and prints the `ia_emit(...)` calls needed to bring them back, grouped so each call stays under the output limit. Searches with no owner page are kept only when they reach 100 impressions in the window.

Composio prints a response-schema preview the first time a tool runs in a call; ignore it.

## 4. Bring the tables back

Run each printed `ia_emit(...)` call. Save its output, exactly as printed, from the first `##IA` line to the last `##END` line, to a new file in `work/gsc/` (e.g. `work/gsc/emit_1.txt`). Then:

```
python $SKILL/scripts/gsc_import.py --dir work/gsc
```

Every block carries a row count and checksum. A block that fails was copied wrong: run that `ia_emit` again and save it again over the bad file. Done when it prints "Loaded" for meta, pages, pairs, noowner and home, with no PROBLEMS.

## 5. Follow-up from analyze.py

analyze.py's `next_steps.md` prints one more workbench call. Run it and save its block to `work/gsc/` the same way, then re-run gsc_import.py and analyze.py:

- `ia_pair_queries([...])`: top shared searches for the duplicate and city-variant pairs. Rounds add up, so after a later review round you only run it for the new pairs.
