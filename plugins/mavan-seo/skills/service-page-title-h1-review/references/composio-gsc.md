# Search Console through Composio

This is the only use of Composio in this skill. It pulls queries (with impressions and clicks) for the crawled URLs and nothing else. No GA4. The queries go in the Top GSC Queries column for a person to read; you do not rank or judge them.

**Tools allowed:** `COMPOSIO_SEARCH_TOOLS`, `COMPOSIO_GET_TOOL_SCHEMAS` (only to read the parameters of the one tool you found), `COMPOSIO_MULTI_EXECUTE_TOOL`, and `COMPOSIO_REMOTE_BASH_TOOL` for **one job only** (§ 4), which the person has approved. Do not use the remote workbench or any other Composio tool without asking the person first and explaining why.

## 1. Find the tool and the property

Call `COMPOSIO_SEARCH_TOOLS` (use case: query Search Console search analytics by page and query). Its connection status lists the Search Console properties. If there is no active Search Console connection, tell the person Composio needs Google Search Console connected with an account that has access to the client's property, and build the workbook without the Top GSC Queries column (SKILL.md Step 1). Do not substitute another source.

Do not assume the tool name or the property. Use the tool Composio returns. The property, date range, brand terms and the rest are confirmed in one message (SKILL.md Step 1), not here.

## 2. Date range

Default: the 90 days ending 3 days before today (the newest days are often incomplete), unless the person gave dates. One fixed range for every request.

## 3. Request rules (follow all of them)

- Ask for only the **page** and **query** dimensions and the **clicks** and **impressions** metrics. No device, country, search appearance or date dimensions.
- Filter every request to the crawled URLs with a page filter, about 10 URLs per batch (from `work/urls.txt`). Never pull the whole site and filter afterward.
- In the same filter group as the page filter, exclude branded queries with the tool's exclude-regex operator on the query dimension (the person's brand terms, joined with `|`), so branded rows never come back. If the person has no brand term, skip this.
- Row limit about 100 per URL in the batch (1,000 for 10 URLs), never the site maximum. Search Console returns the highest-click queries first.
- Send all batches in **one** `COMPOSIO_MULTI_EXECUTE_TOOL` call.
- If a batch fails (for example, the filter is too long), make the batch smaller and retry it. Do not fall back to pulling the whole site.
- Use the tool's own parameter names; the names above are Search Console's.
- Do not paste raw responses into the chat.

## 4. Getting the rows into `work/gsc/`

Rows are at `results[i].response.data.rows`, each with `keys` [page, query], `clicks` and `impressions`.

- **Response comes back in full:** save the rows exactly as returned to `work/gsc/batch_N.json`. `build.py` reads them, drops queries under 5 impressions and branded queries, and keeps the top 10 per page. It prints the row count of each file; it must match the number of rows returned. If it reads 0 rows, stop and show the person the response shape.
- **Composio saved the response to its sandbox and returned only a preview** (it names a file such as `/mnt/files/mex/….json`): the full rows can only be read there. Use `COMPOSIO_REMOTE_BASH_TOOL` for this one job, a single call that reads that file, keeps rows with at least 5 impressions and no brand term in the query, groups by page path, sorts each page by impressions then clicks (both highest first), keeps 10 per page, and prints one line per page: `path<TAB>query (impressions/clicks); query (impressions/clicks); ...` (path only, no host; counts are whole numbers with no commas), then the md5 of the printed text. Example of the job:

```python
import json, re, hashlib
from urllib.parse import urlsplit
BRAND = ["brandterm"]          # the person's brand terms, lowercase; [] if none
def walk(o, out):
    if isinstance(o, dict):
        if "clicks" in o and "impressions" in o and isinstance(o.get("keys"), list):
            out.append(o)
        else:
            for v in o.values(): walk(v, out)
    elif isinstance(o, list):
        for v in o: walk(v, out)
rows = []; walk(json.load(open("/mnt/files/mex/SAVED.json")), rows)
pages = {}
for r in rows:
    page, q = r["keys"][0], r["keys"][1].lower()
    i, c = int(r["impressions"]), int(r["clicks"])
    if i < 5 or any(b in q for b in BRAND): continue
    pages.setdefault(urlsplit(page).path, []).append((q, i, c))
lines = []
for p, qs in pages.items():
    qs.sort(key=lambda x: (-x[1], -x[2], x[0]))
    lines.append(p + "\t" + "; ".join(f"{q} ({i}/{c})" for q, i, c in qs[:10]))
out = "\n".join(lines) + "\n"
print(out); print("MD5", hashlib.md5(out.encode()).hexdigest())
```

  Save the printed lines exactly as printed to `work/gsc/top_queries.tsv`, then run `md5sum` on it locally and compare with the printed MD5. If they differ, stop and tell the person. Do not use the sandbox for anything else.

URLs the crawl lists but Search Console does not return (or that have no query with 5 impressions) show "No GSC data for this page (or fewer than 5 impressions per query)". That is normal for new or unindexed pages.
