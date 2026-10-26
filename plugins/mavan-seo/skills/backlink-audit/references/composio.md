# Composio: live status checks

This container usually can't reach client sites (the network allowlist blocks them), so live checks run in Composio's remote workbench (`COMPOSIO_REMOTE_WORKBENCH`), which can.

## Live status of URLs

prep.py and build.py write the URLs that need checking to `work/status_needed.txt`: every client URL the backlinks point at, the homepage, and any redirect targets. Broken backlinks are found from these results, so check them all. Send this to the workbench as `code_to_execute`, pasting the file's lines into `URLS`:

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

- A 403 or 429 on many URLs at once is usually bot protection, not a real error. Retry those after a few seconds; if they still fail, list them in the notes for the person to open in a browser. build.py doesn't count a 429, an error, or a 403 on a blocked homepage as broken; it does count a 403 as broken when the homepage answers 200, with a warning to confirm in a browser.
- Columns: url, first-hop status, final URL after redirects, final status. build.py treats a URL as live only when it answers 200 itself, and a broken URL as already fixed when it now answers 200 or redirects to a page that does.

## Manual actions and the Links report

**The Search Console API has no manual actions or Links report, and the audit doesn't pull Search Console data.** The manual actions result comes from the person and goes in config.json (references/process.md § Disavow rule); the Links report is an optional attached CSV. Never say you checked manual actions.
