# Composio: live status checks and Search Console

This container usually can't reach client sites (the network allowlist blocks them), so live checks run in Composio's remote workbench (`COMPOSIO_REMOTE_WORKBENCH`), which can.

## Live status of URLs

prep.py and build.py write the URLs that need checking to `work/status_needed.txt`. Send this to the workbench as `code_to_execute`, pasting the file's lines into `URLS`:

```python
import requests
URLS = """
PASTE status_needed.txt HERE
""".split()
H = {'User-Agent': 'Mozilla/5.0 (compatible; MavanAudit/1.0)'}
print('##STATUS', len(URLS))
for u in URLS:
    try:
        r = requests.get(u, headers=H, timeout=20, allow_redirects=False)
        final_url, final = '', ''
        if 300 <= r.status_code < 400:
            f = requests.get(u, headers=H, timeout=20, allow_redirects=True)
            final_url, final = f.url, f.status_code
        print(f'{u}\t{r.status_code}\t{final_url}\t{final}')
    except Exception as e:
        print(f'{u}\tERR\t\t')
print('##END')
```

Copy every line between `##STATUS` and `##END` (not the markers) and append it to `work/status.tsv`. Check the line count matches the number after `##STATUS`. Over ~300 URLs, split into batches of 300.

- A 403 or 429 on many URLs at once is usually bot protection, not a real error. Retry those after a few seconds; if they still fail, list them in the notes for the person to open in a browser, and don't treat them as broken.
- Columns: url, first-hop status, final URL after redirects, final status. build.py treats a URL as live only when it answers 200 itself, and a broken URL as already fixed when it now answers 200 or redirects to a page that does.

## Search Console

Call `COMPOSIO_SEARCH_TOOLS` (use case: list Search Console sites; query search analytics by page). Its connection status lists the properties. Pick the one for the domain, preferring `sc-domain:`, and copy it exactly as listed. If there's no active Search Console connection, say Composio needs Google Search Console connected with the Mavan Google login and carry on without it.

Pull clicks and impressions by page for the last 12 months with `GOOGLE_SEARCH_CONSOLE_SEARCH_ANALYTICS_QUERY` (dimensions `["page"]`, `row_limit` 25000, `start_row` to paginate until a page returns fewer rows). Do it inside the workbench and print only the top pages per topic you need, so the result stays small. Use it to choose between two equally good redirect targets for a broken backlink.

**The Search Console API has no manual actions or Links report.** The manual actions result comes from the person (SOP Step 2) and goes in config.json; the Links report comes as an attached CSV. Never say you checked manual actions.
