# GA4 through Composio (optional)

Only when the person asked for GA4. Search Console does not use Composio: it comes from the Google Sheet (`scripts/gsc_sheet.py`). Many clients have too little traffic for GA4 to matter; if the person says to skip it, do none of this and leave the GA4 columns blank.

`scripts/ga4_workbench.py` runs inside Composio's remote workbench (`COMPOSIO_REMOTE_WORKBENCH`), not here. Its state persists between workbench calls and it saves to `/mnt/files/ia/`, so if the sandbox restarts, send the file again and carry on from the step you were on.

## 1. Check the connection

Call `COMPOSIO_SEARCH_TOOLS` (use case: run a GA4 report; list GA4 properties). Its connection status shows whether Google Analytics is connected. If it is not, tell the person Composio needs Google Analytics connected with a Google account that has access to the client's property, and continue without GA4.

## 2. Load the script

Send the whole of `ga4_workbench.py` as `code_to_execute`, with one line appended that sets the client:

```python
CONFIG.update({'domain': 'example.com', 'ga4_property': None})
```

If the GA4 property is unknown, append `ia_ga4_properties()` too, pick the match it prints, and set `CONFIG['ga4_property'] = 'properties/123456789'` at the start of the next call. If no property matches the domain, say so and continue without GA4.

## 3. Pull and bring it back

Use the same dates as the Search Console sheet (the window you passed to `gsc_sheet.py`).

1. `ia_ga4('YYYY-MM-DD', 'YYYY-MM-DD')`: sessions and key events by landing page. Prints the number of landing pages.
2. `ia_ga4_emit()`: prints one checksummed block. Save it, exactly as printed from the `##IA` line to the `##END` line, to `work/gsc/ga4.txt`.

Composio prints a response-schema preview the first time a tool runs in a call; ignore it.

Then, locally:

```
python $SKILL/scripts/gsc_import.py --dir work/gsc        # checks the checksum, writes work/gsc/ga4.csv
python $SKILL/scripts/gsc_sheet.py build ... --ga4-property properties/123456789   # same command as Step 4, now merges ga4.csv
```

A block that fails its checksum was copied wrong: run `ia_ga4_emit()` again and save it over the bad file. Done when `gsc_import.py` prints "Loaded: ga4" with no PROBLEMS and the `build` output says "GA4: merged N landing pages".
