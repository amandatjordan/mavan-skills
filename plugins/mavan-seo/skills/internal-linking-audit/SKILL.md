---
name: "internal-linking-audit"
description: "Run Mavan's internal linking audit for a client site from Sitebulb or Screaming Frog exports and deliver the implementation sheet. Use for internal linking audits or link opportunities to service pages."
---

# Internal Linking Audit (Mavan SOP)

Version 1.1 (Oct 2026). Full SOP: the "Internal Linking Audit Process" page in Notion. Sheet template: https://docs.google.com/spreadsheets/d/1hyxsOaSlpdvPdV9y289M-8Gb6t4f0qCMYZvj4xJkzW0/edit

This skill finds internal linking opportunities for a client's priority pages (any commercial page the strategist picks; usually service pages) and delivers an implementation sheet the team can work straight down. Code does everything with a clear right answer; Claude's judgment is used only for relevance, link placement and anchors. Follow the steps in order and don't skip the verification step.

## What you need before starting

- **Crawl exports** from Sitebulb or Screaming Frog: a URLs export (status code, indexability, title, H1, crawl depth) and an all-internal-links export (source, target, anchor, link position/location, CSS path or link path). Ask for them if they're not attached.
- **Priority pages**: a list of URLs (any commercial page: service, location, concern, package), optionally with topic/synonyms per page, or "all service pages".
- **The client domain.**
- **The built-in browser** (Claude desktop app). The live-page read in Step 3 needs it. If no browser tool is available, tell the person the audit can't verify existing links or quote sentences without it, and stop.

## Setup (every run)

Create a working folder and write the four scripts from the Appendix into `ila/scripts/` exactly as shown (prep.py, reader.py, checks.py, finalize.py). Copy the crawl exports into `ila/`. Run all commands from `ila/`. Use a task list so a returning person can see progress.

## Step 1: Search data

1. Use Composio. Search its tools for Google Search Console and Google Analytics, list the GSC sites and GA4 properties, and check the client is there.
2. If it is: pull the last 3 full months of GSC data by page + query (paginate with start_row until rows < row_limit) and GA4 sessions by landing page. Save `ranked.csv` with columns `keyword,url,volume,position` (use impressions as volume and add a `clicks` column).
3. If it isn't (or Composio isn't connected): tell the person right away that the Google account authorized in Composio doesn't have access to this property, then continue without `--keywords`. Don't use any other ranking source. Say "No search data" in the Baseline note and the final summary.
4. The homepage ranking for service keywords is not a problem; it's a high-intent page. Only flag a blog or gallery page outranking the service page.

## Step 2: Prepare the crawl data

```
python scripts/prep.py --urls <urls.csv> --links <links.csv> --base https://DOMAIN --out work
```

Read the pattern table it prints. Pick a `--body-regex` that matches only links inside the main article/body container (on the test site: `#(post-part|section)`). Related-post cards, sitemap lists, popups/forms, CTA buttons and "View all" links are not body copy even when the crawler labels them "Content". Re-run with the regex and sanity-check the counts by section.

Sitebulb caveat: when a body link has the same anchor as a menu link to the same page, Sitebulb records only the menu link, so crawl body counts run low. Step 3 fixes this by reading the live pages, and live data wins wherever they disagree.

## Step 3: Read the live pages

**Over ~1,000 pages to read** (reader.py make prints the count and warns): do Step 4 first, then run `python scripts/checks.py --work work --base https://DOMAIN --priority priority.csv --service-regex '<pattern>' --terms-only` and add `--filter-terms work/terms.csv --keep-full '<service pattern>'` to the make command below. The browser then sends back every body link and a word count for each page, but only the paragraphs that mention a priority term (full text for the homepage and service pages). On the test site this gave identical candidates from a fifth of the data. Retarget rows on filtered pages that don't mention a priority term can't be auto-verified; finalize.py warns, so check those by hand.

1. `python scripts/reader.py make --work work --base https://DOMAIN` (adjust `--exclude` if gallery/review/listing URLs use other patterns; galleries, reviews, tag/category pages and the sitemap are excluded by default).
2. Open any page of the client site in the built-in browser (preview_start). Run the contents of `work/js/start.js` with the browser's JavaScript tool. It returns immediately and keeps fetching in the background (about 10 pages at a time).
3. Run `work/js/status.js` every ~20 seconds until `done == total`. Check the sample text looks like article copy, not menus. If many content pages come back empty, the site uses different markup: inspect one page and pass better selectors with `--body-sel` / `--remove-sel`, then redo this step.
4. Run `work/js/chunk.js` with `CHUNK = 0`. The result is gzipped and padded so the tool saves it to a file; note the file path and the `of` value (number of chunks). Then run CHUNK = 1 … of-1 (they can run in parallel). If any result says it was truncated, lower SIZE in chunk.js and redo that chunk.
5. `python scripts/reader.py merge --work work --base https://DOMAIN <saved files…>`. It must report 0 missing pages.

## Step 4: Terms and service map

1. Work out the service-page URL pattern (e.g. `^/procedures/[^/]+/[^/]+$`) from the URLs export. Category hubs aren't services.
2. Write `priority.csv` with columns `url,terms`. `terms` is a `|`-separated list of the phrases people use for that service, including synonyms (`tummy tuck|abdominoplasty`, `rhinoplasty|nose job|nose surgery`). Drop generic words like "surgery" or "treatment" that would match everything. For "all service pages", list every service URL (or use `--all-services` and then fix terms in priority.csv).
3. Propose service groups (e.g. face / breast / body / injectables) and which services relate to each other.
4. **When to pause:** if there are 10 or more priority pages, or the request is "all service pages", show the person the terms and groups and wait for a yes before Step 5. With fewer than 10, don't pause: list the terms and groups in the final summary so they can be checked.

## Step 5: Run the checks

```
python scripts/checks.py --work work --base https://DOMAIN --priority priority.csv --service-regex '<pattern>' [--keywords ranked.csv]
```

Outputs in `work/`: `baseline.csv`, `A_candidates.csv` (check A, or D when the source is a service page), `B_anchors.csv`, `C_redirects.csv`, `D_reverse.csv`, `D_no_body_links.csv`, `E_misdirected.csv`, `E_linkup.csv`. These are candidates, not recommendations.

## Step 6: Review candidates and write rows.json

Read every candidate sentence yourself. For each recommendation, add an object to `work/rows.json` with: `priority, check, page, action, source, target, current_anchor, suggested_anchor, sentence, position, reason`. `page` is the priority page label (e.g. "Rhinoplasty"), or "Other service pages" when the target isn't a priority page.

**A. Unlinked relevant content.** Keep a page only if it's genuinely about the service (a passing list mention is Low at most). Send pages that fit a different service better to that service. Copy the sentence exactly as it appears in `pages.json`, including curly quotes and dashes. Pick an anchor made of words already in the sentence. Vary anchors across pages. Always consider the homepage and doctor/staff bio pages. If no sentence fits, use action `Add sentence + link` with `CURRENT: <exact sentence>` and `SUGGESTED: <rewritten sentence>` on two lines.

**B. Weak anchors.** Review `B_anchors.csv` flags plus anchors that describe a different topic. Exact-match anchors are fine on their own. Action `Change anchor`.

**C. Redirects.** Every link (menu and footer included) to a redirecting or non-canonical version of a priority page becomes an `Update URL` row with the final URL. One template fix covers many links, so it's High. Other internal redirects go to Other findings.

**D. Related services.** Use the confirmed groups. Easiest wins: sentences on related service pages that already name the priority service (A_candidates rows marked D). Then reciprocal links from the priority page (`D_reverse.csv`). Service pages with zero body links are worth a line in Other findings.

**E. Links going to the wrong page.**
- `E_misdirected.csv`: a service-describing anchor pointing to a blog, gallery, review or contact page. Decide whether the anchor is really about the service ("details of liposuction") or legitimately about the post's topic ("liposuction recovery" → a recovery post is fine). Recommend `Change link target` only when `source_already_links_to_suggested` is False. Log the skipped ones in Other findings.
- `E_linkup.csv`: gallery/case/review pages for each priority service that never link to the service page outside the menu. Spot-check 2–3 of them live in the browser (fetch the page, strip header/footer, look for a link to the service page). If confirmed, add one `Add link (template)` row per service, with the gallery URL as source, saying how many pages it covers. End the Reason with "May need platform support (e.g. DoctorLogic) to change the template." when the site runs on a hosted platform.

**Rules for every row:**
- Duplicate-link rule: never add a link to, or retarget a link at, a page the source already links to in its body copy. Menu, footer and widget links don't count.
- New links per source page: 1 per 300 words of live body text, never more than 8 (`new_link_cap` in A_candidates.csv). Retargets don't count. The homepage and category hubs are exempt.
- `Add sentence + link` rows change page copy, so they start with Status **Needs approval** (finalize.py sets this). Say in the Reason what the new sentence adds.
- Never put a new link on words that are already a link.
- Don't recommend removing links.

**Priority:**
- High: template fixes (redirects, gallery/review link-ups); links between closely related service pages; posts squarely about a priority page that has few body links in.
- Medium: homepage copy links; posts partly about the service; less closely related service pages; copy additions; single retargets.
- Low: passing mentions, list items, minor anchor fixes.
- With GSC data, use the source page's clicks as the tiebreaker within a level. Without it, use relevance alone.

Also write `work/findings.json` (3–5 plain-language key findings) and `work/other.json` (list of `{area, priority, finding, recommendation}`: skipped duplicates, broken links, unrelated redirects, anything notable).

## Step 7: Verify, then build

```
python scripts/finalize.py --work work --base https://DOMAIN --rows work/rows.json --verify-only
```

It checks every sentence word for word against the live pages, that each anchor is in its sentence and not already a link, the duplicate-link rule, and the per-page link cap. Fix every ERROR (don't use --force), then build:

```
python scripts/finalize.py --work work --base https://DOMAIN --rows work/rows.json --findings work/findings.json --other work/other.json --client DOMAIN --subtitle "Priority pages: …, <date>" --baseline-note "<data sources used>" --out <client>-internal-linking-audit.xlsx
```

The workbook uses formulas. If the xlsx skill's recalc script is available, run it on the file. Otherwise the formulas calculate when the file is opened in Excel or imported into Google Sheets.

## Step 8: Deliver

Send the .xlsx. The tabs and columns match the team's Google Sheets template, so it can be imported into a copy of the template. In the reply, give 3–5 key findings, what the sheet contains (counts by priority), and anything you couldn't do (e.g. no GSC access). If you didn't pause in Step 4, list the terms and service groups used. Don't recap the steps.

## Appendix: scripts

Write each file exactly as shown.

### scripts/prep.py

```python
#!/usr/bin/env python3
"""Normalize crawler exports (Sitebulb or Screaming Frog) into work/urls.pkl and work/links.pkl.

Usage:
  python prep.py --urls URLS.csv --links LINKS.csv --base https://example.com --out work
  python prep.py ... --body-regex '#(post-part|section)'   # mark body-copy links by CSS path / XPath

Run once without --body-regex to see the link-path patterns, pick the regex that matches only
the main article/body container, then run again with it.
"""
import argparse, re, sys
import pandas as pd

def norm(u, base):
    if not isinstance(u, str) or not u.strip():
        return ''
    u = u.strip()
    if u.startswith('/'):
        u = base + u
    u = re.sub(r'^http://', 'https://', u)
    u = re.sub(r'[#?].*$', '', u)
    m = re.match(r'(https://[^/]+)(.*)', u)
    if m:
        u = m.group(1).lower() + m.group(2)
    return u.rstrip('/') if u.count('/') > 2 else u.rstrip('/')

def pick(df, *names):
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([None] * len(df))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--urls', required=True)
    ap.add_argument('--links', required=True)
    ap.add_argument('--base', required=True, help='https://domain.com (no trailing slash)')
    ap.add_argument('--out', default='work')
    ap.add_argument('--body-regex', default=None)
    a = ap.parse_args()
    import os; os.makedirs(a.out, exist_ok=True)
    base = a.base.rstrip('/')

    u = pd.read_csv(a.urls, encoding='utf-8-sig', low_memory=False)
    if 'Address' in u.columns:
        crawler = 'screaming_frog'
    elif 'URL' in u.columns:
        crawler = 'sitebulb'
    else:
        sys.exit(f'Unrecognised URLs export columns: {list(u.columns)[:15]}')
    U = pd.DataFrame({
        'url': pick(u, 'Address', 'URL').map(lambda x: norm(x, base)),
        'status': pd.to_numeric(pick(u, 'Status Code', 'HTTP Status Code'), errors='coerce'),
        'indexability': pick(u, 'Indexability', 'Indexable Status').astype(str),
        'title': pick(u, 'Title 1', 'Title').astype(str),
        'h1': pick(u, 'H1-1', 'H1').astype(str),
        'depth': pd.to_numeric(pick(u, 'Crawl Depth'), errors='coerce'),
        'redirect_to': pick(u, 'Redirect URL', 'Redirect URL 1').map(lambda x: norm(x, base) if isinstance(x, str) else ''),
    })
    U['indexable'] = U.indexability.str.lower().eq('indexable')

    l = pd.read_csv(a.links, encoding='utf-8-sig', low_memory=False)
    if 'Linking URL' in l.columns:
        L = pd.DataFrame({'src': l['Linking URL'], 'dst': l['Target URL'], 'anchor': l['Anchor Text'],
                          'position': pick(l, 'Location'), 'path': pick(l, 'CSS Path')})
    elif 'Source' in l.columns and 'Destination' in l.columns:
        if 'Type' in l.columns:
            l = l[l['Type'].astype(str).str.lower().eq('hyperlink')]
        L = pd.DataFrame({'src': l['Source'], 'dst': l['Destination'], 'anchor': pick(l, 'Anchor', 'Alt Text'),
                          'position': pick(l, 'Link Position'), 'path': pick(l, 'Link Path')})
    else:
        sys.exit(f'Unrecognised links export columns: {list(l.columns)[:15]}')
    L['src'] = L.src.map(lambda x: norm(x, base)); L['dst'] = L.dst.map(lambda x: norm(x, base))
    L['raw_dst'] = (l['Target URL'] if 'Target URL' in l.columns else l['Destination']).astype(str).values
    L = L[L.dst.str.startswith(base)]
    L['anchor'] = L.anchor.fillna('').astype(str).str.strip()
    L['position'] = L.position.fillna('').astype(str)
    L['path'] = L.path.fillna('').astype(str)
    L['pattern'] = L.path.str.replace(r':nth-child\(\d+\)', '', regex=True).str.replace(r'\[\d+\]', '', regex=True).str.replace(r'\d+', 'N', regex=True)
    content = L.position.str.lower().isin(['content'])
    if a.body_regex:
        L['body'] = L.path.str.contains(a.body_regex, regex=True)
    else:
        L['body'] = content
    U.to_pickle(f'{a.out}/urls.pkl'); L.to_pickle(f'{a.out}/links.pkl')

    print(f'crawler={crawler} urls={len(U)} (indexable {U.indexable.sum()}) internal links={len(L)}')
    print('status codes:', U.status.value_counts().to_dict())
    print('link positions:', L.position.value_counts().to_dict())
    print('\nContent-position link patterns (pick a --body-regex that keeps only the article/body container):')
    c = L[content]
    g = c.groupby('pattern').agg(n=('dst', 'size'), pages=('src', 'nunique'),
                                 median_anchor_len=('anchor', lambda s: int(s.str.len().median())),
                                 example=('anchor', lambda s: s.iloc[0][:60]))
    print(g.sort_values('n', ascending=False).head(30).to_string())
    if a.body_regex:
        print(f'\nbody links with regex {a.body_regex!r}: {L.body.sum()} from {L[L.body].src.nunique()} pages')
        print('by source section:', L[L.body].src.str.replace(base, '').str.split('/').str[1].value_counts().head(10).to_dict())

if __name__ == '__main__':
    main()
```

### scripts/reader.py

```python
#!/usr/bin/env python3
"""Read live page body copy through the built-in browser.

Above ~1,000 pages, pass --filter-terms work/terms.csv --keep-full '<service path regex>' so the browser
sends back only paragraphs that mention a service term (plus every body link and a word count per page).

1) python reader.py make --work work --base https://example.com [--exclude REGEX] [--include REGEX]
   Writes work/js/start.js, work/js/status.js and work/js/chunk.js and prints how to use them.
   Run start.js in the browser (javascript tool) on any page of the site, poll status.js until done,
   then run chunk.js once per chunk (edit the CHUNK number). Each chunk is gzipped, base64-encoded and
   padded so the tool always saves it to a file instead of printing it.
2) python reader.py merge --work work FILE [FILE ...]
   FILE = the saved tool-result files from the chunk calls. Writes work/pages.json and
   work/body_links.csv (every link found in body copy, from the live pages).
"""
import argparse, base64, gzip, json, os, re, sys
import pandas as pd

BODY_SEL = ('article p, article li, main p, main li, [id^=post-part] p, [id^=post-part] li, '
            '.section__text-block p, .section__text-block li, .faq summary, .faq p, '
            '.entry-content p, .entry-content li, .post-content p, .post-content li, .content p, .content li')
REMOVE_SEL = ('header, footer, nav, aside, form, dialog, script, style, noscript, .cards, .card, '
              '[class*=related], [class*=testimonial], [id*=testimonial], [class*=breadcrumb], '
              '[class*=sidebar], [class*=widget], [class*=cta], [class*=popup], [class*=modal]')

START = r'''(() => {
window.__P = {}; window.__ERR = {}; window.__DONE = 0;
const L = __URLS__.map(p => location.origin + p);
const SEL = __SEL__, RM = __RM__;
const FILTER = __FILTER__ ? new RegExp(__FILTER__, 'i') : null, KEEP = new RegExp(__KEEP__);
const one = async u => { try {
  const r = await fetch(u, {credentials: 'omit'}); const h = await r.text();
  const d = new DOMParser().parseFromString(h, 'text/html');
  d.querySelectorAll(RM).forEach(x => x.remove());
  const seen = new Set(), out = [];
  d.querySelectorAll(SEL).forEach(e => {
    if (e.tagName === 'LI' && e.querySelector('p')) return;
    const t = e.textContent.replace(/\s+/g, ' ').trim();
    if (!t || seen.has(t)) return; seen.add(t);
    out.push({tag: e.tagName.toLowerCase(), t, links: [...e.querySelectorAll('a')].map(a => [a.textContent.replace(/\s+/g,' ').trim(), a.getAttribute('href') || ''])});
  });
  const words = out.reduce((n, x) => n + (x.tag === 'p' || x.tag === 'li' ? x.t.split(' ').length : 0), 0);
  const full = !FILTER || KEEP.test(new URL(u).pathname.replace(/\/$/, '') || '/');
  window.__P[u] = {status: r.status, final: r.url, h1: (d.querySelector('h1')||{}).textContent?.trim()||'', words,
    all_links: FILTER ? out.flatMap(x => x.links) : undefined, items: full ? out : out.filter(x => FILTER.test(x.t))};
} catch (e) { window.__ERR[u] = String(e); } finally { window.__DONE++; } };
(async () => { for (let i = 0; i < L.length; i += 10) await Promise.all(L.slice(i, i + 10).map(one)); })();
return 'started ' + L.length + ' pages';
})()
'''
STATUS = r'''
(() => { const P = window.__P || {}; const keys = Object.keys(P);
  const empty = keys.filter(k => !P[k].items.length);
  return {done: window.__DONE, total: __N__, errors: Object.keys(window.__ERR || {}).length, empty_pages: empty.length,
          empty_examples: empty.slice(0, 8), sample: keys.slice(0, 2).map(k => [k, P[k].items.slice(0, 3).map(x => x.t.slice(0, 80))])}; })()
'''
CHUNK = r'''
(async () => { const CHUNK = 0, SIZE = 550000;
  const P = window.__P, keys = Object.keys(P).sort(); const ch = []; let cur = [], s = 0;
  for (const k of keys) { const n = JSON.stringify(P[k]).length + k.length; if (s + n > SIZE && cur.length) { ch.push(cur); cur = []; s = 0; } cur.push(k); s += n; }
  if (cur.length) ch.push(cur);
  if (CHUNK >= ch.length) return 'no chunk ' + CHUNK + ' (total ' + ch.length + ')';
  const raw = JSON.stringify(Object.fromEntries(ch[CHUNK].map(k => [k, P[k]])));
  const gz = new Uint8Array(await new Response(new Blob([raw]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());
  let bin = ''; for (let i = 0; i < gz.length; i += 0x8000) bin += String.fromCharCode.apply(null, gz.subarray(i, i + 0x8000));
  const b64 = btoa(bin);
  return JSON.stringify({chunk: CHUNK, of: ch.length, pages_in_chunk: ch[CHUNK].length, gz: b64, _pad: 'x'.repeat(Math.max(0, 130000 - b64.length))}); })()
'''

def make(a):
    U = pd.read_pickle(f'{a.work}/urls.pkl')
    pages = U[(U.status == 200) & U.indexable]
    if a.include:
        pages = pages[pages.url.str.contains(a.include, regex=True)]
    if a.exclude:
        pages = pages[~pages.url.str.contains(a.exclude, regex=True)]
    urls = sorted(pages.url.unique())
    os.makedirs(f'{a.work}/js', exist_ok=True)
    paths = [u.replace(a.base.rstrip('/'), '') or '/' for u in urls]
    filt = ''
    if a.filter_terms:
        tf = pd.read_csv(a.filter_terms).fillna('')
        if 'priority' in tf.columns: tf = tf[tf.priority.astype(str).str.lower() == 'true']   # priority pages' terms only
        tl = sorted({t.strip() for v in tf.terms for t in str(v).split('|') if t.strip()}, key=len, reverse=True)
        filt = r'\b(?:' + '|'.join(re.escape(t).replace(r'\ ', r'[\s-]+') for t in tl) + r')'
    keep = '^/$' + ('|' + a.keep_full if a.keep_full else '')
    if len(urls) > 1000 and not a.filter_terms:
        print('WARNING: over 1,000 pages. Run checks.py --terms-only and re-run make with --filter-terms work/terms.csv --keep-full <service regex>.')
    open(f'{a.work}/js/start.js', 'w').write(START.replace('__URLS__', json.dumps(paths, separators=(',', ':'))).replace('__SEL__', json.dumps(a.body_sel)).replace('__RM__', json.dumps(a.remove_sel)).replace('__FILTER__', json.dumps(filt)).replace('__KEEP__', json.dumps(keep)))
    open(f'{a.work}/js/status.js', 'w').write(STATUS.replace('__N__', str(len(urls))))
    open(f'{a.work}/js/chunk.js', 'w').write(CHUNK)
    json.dump(urls, open(f'{a.work}/read_list.json', 'w'))
    print(f'{len(urls)} pages to read. Sections:', pd.Series([u.replace(a.base, '').split('/')[1] if u.count('/') > 2 else 'home' for u in urls]).value_counts().head(12).to_dict())
    print('mode:', f'filtered by {a.filter_terms} (full text kept for {keep})' if filt else 'full text for every page')
    print(f'Files: {a.work}/js/start.js (run once), status.js (poll), chunk.js (set CHUNK = 0, 1, 2 ... until it says no chunk)')

def parse_tool_file(path):
    raw = open(path, encoding='utf-8').read()
    try:
        d = json.loads(raw)
        text = d[0]['text'] if isinstance(d, list) else raw
    except Exception:
        text = raw
    if '[truncated' in text:
        sys.exit(f'{path}: output was truncated by the bridge. Lower SIZE in chunk.js and re-run.')
    i = text.find('"{'); j = text.rfind('}"')
    if i >= 0 and j > i:
        s = json.loads(text[i:j + 2])
    else:
        i = text.find('{'); j = text.rfind('}'); s = text[i:j + 1]
    return json.loads(s)

def merge(a):
    P = {}
    for f in a.files:
        obj = parse_tool_file(f)
        pages = obj['pages'] if 'pages' in obj else json.loads(gzip.decompress(base64.b64decode(obj['gz'])).decode('utf-8'))
        P.update({k.rstrip('/'): v for k, v in pages.items() if not re.search(a.drop, k)})
        print(f'{f}: chunk {obj["chunk"]} of {obj["of"]}, {len(pages)} pages')
    json.dump(P, open(f'{a.work}/pages.json', 'w'))
    base = a.base.rstrip('/')
    rows = []
    for u, p in P.items():
        groups = [{'tag': 'body', 'links': p['all_links']}] if p.get('all_links') is not None else p['items']
        for it in groups:
            for anc, href in it['links']:
                h = href.strip()
                if not h or h.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    continue
                if h.startswith('/'):
                    h = base + h
                h = re.sub(r'^http://', 'https://', h); h = re.sub(r'[#?].*$', '', h).rstrip('/')
                rows.append({'source': u, 'anchor': anc, 'href': h, 'raw_href': href, 'tag': it['tag']})
    pd.DataFrame(rows).to_csv(f'{a.work}/body_links.csv', index=False)
    expected = [u for u in json.load(open(f'{a.work}/read_list.json')) if not re.search(a.drop, u)]
    missing = sorted(set(expected) - set(P))
    print(f'merged {len(P)} pages, {len(rows)} body links. Missing pages: {len(missing)} {missing[:5]}')
    empty = [u for u, p in P.items() if not p['items'] and not p.get('words')]
    print(f'pages with no body text captured: {len(empty)} {empty[:8]}')
    nf = sum(1 for p in P.values() if p.get('all_links') is not None)
    if nf: print(f'filtered mode: {nf} pages read; outside --keep-full only paragraphs mentioning a priority term were kept')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('make'); m.add_argument('--work', default='work'); m.add_argument('--base', required=True)
    m.add_argument('--include'); m.add_argument('--exclude', default=r'before-after|/reviews|gallery|/tag/|/category/|/page/\d|/sitemap|\?')
    m.add_argument('--filter-terms', help='terms.csv: keep only paragraphs mentioning these terms (use above ~1,000 pages)')
    m.add_argument('--keep-full', default='', help='regex of URL paths whose full text is always kept (service pages)')
    m.add_argument('--body-sel', default=BODY_SEL); m.add_argument('--remove-sel', default=REMOVE_SEL)
    g = sub.add_parser('merge'); g.add_argument('--work', default='work'); g.add_argument('--base', required=True)
    g.add_argument('--drop', default=r'/sitemap|/directory$', help='pages to leave out of pages.json (link lists, not content)'); g.add_argument('files', nargs='+')
    a = ap.parse_args()
    make(a) if a.cmd == 'make' else merge(a)
```

### scripts/checks.py

```python
#!/usr/bin/env python3
"""Baseline + candidate lists for Checks A-E. Output is for Claude to review; nothing here is final.

Usage:
  python checks.py --work work --base https://example.com --priority priority.csv \
      --service-regex '/procedures/[^/]+/[^/]+$' [--keywords ranked.csv] [--all-services]

priority.csv columns: url (required), terms (optional, '|'-separated synonyms), group (optional).
--all-services: treat every page matching --service-regex as a priority page.
ranked.csv (optional): keyword, url, volume, position  (GSC page + query data pulled through Composio).

Writes to work/: terms.csv, baseline.csv, A_candidates.csv, B_anchors.csv, C_redirects.csv,
D_reverse.csv, D_no_body_links.csv, E_misdirected.csv, E_linkup.csv
"""
import argparse, json, re
import pandas as pd

GENERIC = r'^(click here|here|read more|learn more|this|this page|more|link|go|see more|find out more|details|view|page|website|click)$'
SPLIT = re.compile(r'(?<!\bDr)(?<!\bMr)(?<!\bMs)(?<!\bMrs)(?<!\bSt)(?<=[.!?])["”]?\s+(?=[A-Z0-9"“])')
LOW_VALUE = r'/blog|before-after|gallery|/reviews|testimonial|contact|/schedule|/about|/staff|/doctors|/dr-|/team'

def nrm(u, base):
    u = str(u).strip()
    if u.startswith('/'): u = base + u
    u = re.sub(r'^http://', 'https://', u); u = re.sub(r'[#?].*$', '', u)
    return u.rstrip('/')

def sentences(text):
    return [s.strip() for s in SPLIT.split(text) if s.strip()]

def derive_terms(h1, url):
    t = re.split(r'\s+in\s+|\s*[|,–-]\s*', str(h1), maxsplit=1)[0].strip().lower() if h1 and h1 != 'nan' else ''
    t = re.sub(r'\s+(surgery|treatments?|procedures?|services?|options?)$', '', t)
    if not t or len(t) < 3:
        slug = url.rstrip('/').split('/')[-1]
        t = re.sub(r'-(in-)?[a-z]+-[a-z]{2}$', '', slug).replace('-', ' ')
    return [t]

def rx_for(terms):
    return re.compile(r'\b(?:' + '|'.join(re.escape(t).replace(r'\ ', r'[\s-]+') for t in terms if t) + r')s?\b', re.I)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work'); ap.add_argument('--base', required=True)
    ap.add_argument('--priority'); ap.add_argument('--service-regex', required=True)
    ap.add_argument('--keywords'); ap.add_argument('--all-services', action='store_true')
    ap.add_argument('--terms-only', action='store_true', help='write work/terms.csv from the crawl only (before reading pages on large sites)')
    a = ap.parse_args(); W = a.work; base = a.base.rstrip('/')
    U = pd.read_pickle(f'{W}/urls.pkl'); L = pd.read_pickle(f'{W}/links.pkl')
    if a.terms_only:
        P, BL = {}, pd.DataFrame(columns=['source', 'anchor', 'href'])
    else:
        P = json.load(open(f'{W}/pages.json'))
        BL = pd.read_csv(f'{W}/body_links.csv').fillna('')
        BL['href'] = BL.href.map(lambda h: nrm(h, base) if h.startswith(('/', 'http')) else h)
    svc_re = re.compile(a.service_regex)
    services = sorted(u for u in U[(U.status == 200)].url if svc_re.search(u.replace(base, '')))
    h1 = dict(zip(U.url, U.h1)); title = dict(zip(U.url, U.title))
    for u, p in P.items():
        if p.get('h1'): h1[u] = p['h1']

    # priority list + terms
    if a.all_services or not a.priority:
        pr = pd.DataFrame({'url': services, 'terms': '', 'group': ''})
    else:
        pr = pd.read_csv(a.priority).fillna('')
        for c in ('terms', 'group'):
            if c not in pr.columns: pr[c] = ''
        pr['url'] = pr.url.map(lambda x: nrm(x, base))
    # terms for every service page (needed for D reverse + E), priority overrides
    terms = {s: derive_terms(h1.get(s, ''), s) for s in services}
    for _, r in pr.iterrows():
        if r.terms: terms[r.url] = [t.strip().lower() for t in str(r.terms).split('|') if t.strip()]
        elif r.url not in terms: terms[r.url] = derive_terms(h1.get(r.url, ''), r.url)
    pd.DataFrame([{'url': k, 'terms': '|'.join(v), 'priority': k in set(pr.url)} for k, v in terms.items()]).to_csv(f'{W}/terms.csv', index=False)
    targets = list(pr.url)
    if a.terms_only:
        print(f'wrote {W}/terms.csv for {len(terms)} service/priority pages. Review it, then run reader.py make --filter-terms {W}/terms.csv')
        for t in targets: print(' ', t.replace(base, ''), '->', terms[t])
        return

    links_to = BL.groupby('source').href.apply(set).to_dict()   # live body links per page
    def page_links(u): return links_to.get(u, set())
    def words(u):
        p = P.get(u, {})
        return p.get('words') or sum(len(it['t'].split()) for it in p.get('items', []) if it['tag'] in ('p', 'li'))
    def cap(u): return min(8, max(1, words(u) // 300))

    kw = None
    if a.keywords:
        kw = pd.read_csv(a.keywords); kw.columns = [c.lower() for c in kw.columns]
        kw['url'] = kw.url.map(lambda x: nrm(x, base))

    # ---------- baseline ----------
    base_rows = []
    for t in targets:
        live_in = BL[BL.href == t]
        crawl_in = L[(L.dst == t) & L.body]
        rx = rx_for(terms[t])
        related = U[(U.url.str.contains('/' + '-'.join(terms[t][0].split()) + r'(?:/|$)', regex=True)) & ~U.url.isin(services) & ~U.url.isin(P.keys())]
        tmpl = L[(L.src.isin(related.url)) & (L.dst == t) & ~L.position.str.lower().isin(['header', 'navigation', 'footer', 'nav'])]
        base_rows.append({'page': t, 'terms': '|'.join(terms[t]), 'crawl_depth': U.set_index('url').depth.get(t),
            'body_links_in_live': len(live_in), 'pages_linking_body_live': live_in.source.nunique(),
            'body_links_in_crawl': len(crawl_in), 'body_links_out_live': len(page_links(t)),
            'keywords_ranked': int((kw.url == t).sum()) if kw is not None else '',
            'related_gallery_review_pages': len(related), 'of_which_link_up_outside_menu_crawl': tmpl.src.nunique()})
    pd.DataFrame(base_rows).to_csv(f'{W}/baseline.csv', index=False)

    # ---------- A (and D where source is a service page) ----------
    A = []
    for t in targets:
        rx = rx_for(terms[t])
        for u, p in P.items():
            if u == t or t in page_links(u): continue
            hits = []
            for it in p['items']:
                if it['tag'] not in ('p', 'li'): continue
                for s in sentences(it['t']):
                    if rx.search(s): hits.append(s)
            if not hits: continue
            kwn = int(((kw.url == u) & kw.keyword.str.contains(rx)).sum()) if kw is not None else ''
            A.append({'check': 'D' if u in services else 'A', 'target': t, 'source': u, 'source_title': title.get(u, ''),
                      'mentions': len(hits), 'source_kw_for_topic': kwn, 'source_words': words(u), 'new_link_cap': cap(u),
                      'sentence_1': hits[0], 'sentence_2': hits[1] if len(hits) > 1 else '', 'sentence_3': hits[2] if len(hits) > 2 else ''})
    A = pd.DataFrame(A)
    if len(A): A = A.sort_values(['target', 'check', 'mentions'], ascending=[True, True, False])
    A.to_csv(f'{W}/A_candidates.csv', index=False)

    # ---------- B ----------
    B = BL[BL.href.isin(targets)].copy()
    a_ = B.anchor.str.strip()
    B['flag'] = ''
    B.loc[a_.str.match(GENERIC, case=False), 'flag'] = 'generic'
    B.loc[a_.str.startswith(('http', 'www')), 'flag'] = 'naked url'
    B.loc[~a_.str.contains(r'[A-Za-z]'), 'flag'] = 'empty/punctuation'
    B.loc[a_.str.split().str.len() > 10, 'flag'] = 'too long'
    B['topic_match'] = [bool(rx_for(terms[h]).search(an)) for h, an in zip(B.href, B.anchor)]
    B.to_csv(f'{W}/B_anchors.csv', index=False)

    # ---------- C ----------
    red = U[U.status.between(300, 399)]
    redir = dict(zip(red.url, red.redirect_to))
    C = L[L.dst.isin(red.url)].copy()
    C['final'] = C.dst.map(redir)
    C['to_priority'] = C.final.isin(targets)
    variants = L[(L.dst.isin(targets)) & (L.raw_dst.str.contains(r'^http://|[A-Z]|\?', regex=True) if 'raw_dst' in L else False)]
    C = pd.concat([C.assign(kind='redirect'), variants.assign(kind='non-canonical', final=variants.dst, to_priority=True)])
    C[['kind', 'src', 'dst', 'final', 'to_priority', 'anchor', 'position']].drop_duplicates().to_csv(f'{W}/C_redirects.csv', index=False)

    # ---------- D reverse + service pages with no body links ----------
    R = []
    for t in targets:
        if t not in P: continue
        for other in services:
            if other == t or other in page_links(t): continue
            rx = rx_for(terms[other])
            for it in P[t]['items']:
                if it['tag'] not in ('p', 'li'): continue
                for s in sentences(it['t']):
                    m = rx.search(s)
                    if m and not rx_for(terms[t]).fullmatch(m.group(0)):
                        R.append({'source': t, 'target': other, 'matched': m.group(0), 'sentence': s})
    pd.DataFrame(R).drop_duplicates(['source', 'target']).to_csv(f'{W}/D_reverse.csv', index=False)
    pd.DataFrame([{'service_page': s, 'body_links_out_live': len(page_links(s)), 'read_live': s in P} for s in services]).to_csv(f'{W}/D_no_body_links.csv', index=False)

    # ---------- E ----------
    E = []
    for _, r in BL.iterrows():
        h = r.href
        if not h.startswith(base) or h in services or not re.search(LOW_VALUE, h.replace(base, '')): continue
        for s in services:
            if rx_for(terms[s]).search(r.anchor):
                E.append({'source': r.source, 'anchor': r.anchor, 'current_target': h, 'suggested_target': s,
                          'source_already_links_to_suggested': s in page_links(r.source), 'is_priority': s in targets})
                break
    pd.DataFrame(E).to_csv(f'{W}/E_misdirected.csv', index=False)
    pd.DataFrame(base_rows)[['page', 'related_gallery_review_pages', 'of_which_link_up_outside_menu_crawl']].to_csv(f'{W}/E_linkup.csv', index=False)

    # ---------- summary ----------
    print(f'services={len(services)} priority={len(targets)} pages_read={len(P)} live_body_links={len(BL)}')
    print(pd.DataFrame(base_rows).drop(columns=['terms']).to_string(index=False))
    if len(A): print('\nA/D candidates (pages not linking, mentioning topic):', A.groupby(['target', 'check']).size().to_dict())
    print('B flagged:', int((B.flag != '').sum()), '| C rows:', len(C), '(to priority:', int(C.to_priority.sum()), ')')
    print('D reverse candidates:', len(R), '| service pages with 0 body links out:', sum(len(page_links(s)) == 0 for s in services if s in P), 'of', sum(s in P for s in services))
    print('E misdirected:', len(E), '| of which source already links to suggested (skip):', sum(e['source_already_links_to_suggested'] for e in E))
    print('\nterms used (edit work/terms.csv via --priority terms column if wrong):')
    for t in targets: print(' ', t.replace(base, ''), '->', terms[t])

if __name__ == '__main__':
    main()
```

### scripts/finalize.py

```python
#!/usr/bin/env python3
"""Verify the recommendations against the live pages, then build the Excel workbook.

Usage:
  python finalize.py --work work --base https://example.com --rows rows.json --out audit.xlsx \
      --client "example.com" [--findings findings.json] [--other other.json] [--hubs REGEX] [--verify-only]

rows.json: list of objects with keys
  priority (High|Medium|Low), check (A-E), page (priority page label), action, source, target,
  current_anchor, suggested_anchor, sentence, position, reason
  action is one of: Add link | Add sentence + link | Add link (template) | Change link target | Change anchor | Update URL
  For "Add sentence + link" on an existing sentence use: "CURRENT: <exact text>\nSUGGESTED: <new text>".
  Those rows start with Status "Needs approval"; every other row starts as "To do".
New-link cap per source page: 1 per 300 words of live body text, max 8 (pages matching --hubs are exempt).
findings.json: list of 3-5 plain-language key findings (strings).
other.json: list of {area, priority, finding, recommendation}.
Exits with code 1 and a list of problems if any row fails verification (unless --force).
"""
import argparse, json, re, sys
from collections import Counter
import pandas as pd

def norm_q(s):
    return re.sub(r'\s+', ' ', s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')).strip()

def nrm(u, base):
    u = str(u).strip()
    if u.startswith('/'): u = base + u
    return re.sub(r'[#?].*$', '', re.sub(r'^http://', 'https://', u)).rstrip('/')

def verify(rows, P, BL, base, hubs):
    errs, warns = [], []
    links_to = BL.groupby('source').href.apply(set).to_dict()
    per_source = Counter()
    seen = set()
    for i, r in enumerate(rows, 1):
        tag = f'row {i} ({r["source"].replace(base, "") or "/"} -> {r["target"].replace(base, "")})'
        src, tgt, act = nrm(r['source'], base), nrm(r['target'], base), r['action']
        if (src, tgt, act) in seen: errs.append(f'{tag}: duplicate row');
        seen.add((src, tgt, act))
        if act in ('Add link', 'Add sentence + link', 'Change link target') and tgt in links_to.get(src, set()):
            errs.append(f'{tag}: source already links to target in body copy (duplicate-link rule)')
        if act in ('Add link', 'Add sentence + link'):   # retargets don't add a link
            per_source[src] += 1
        if act in ('Add link (template)', 'Update URL', 'Change anchor') or r['sentence'].startswith(('Same ', 'Add under', 'No body sentence')):
            continue
        page = P.get(src)
        if page is None:
            warns.append(f'{tag}: source page not in pages.json, sentence not verified'); continue
        text = r['sentence'].split('\nSUGGESTED:')[0].replace('CURRENT:', '').strip()
        items = [it for it in page['items'] if text in it['t']]
        if not items:
            loose = [it for it in page['items'] if norm_q(text) in norm_q(it['t'])]
            if loose: errs.append(f'{tag}: sentence matches only after normalising quotes/spaces; copy it exactly from pages.json')
            elif page.get('all_links') is not None and not re.search(r'^https?://[^/]+/?$', src):
                warns.append(f'{tag}: page was read in filtered mode and this sentence has no priority term, so it could not be checked; confirm it by hand')
            else: errs.append(f'{tag}: sentence not found on the live page')
            continue
        if act in ('Add link', 'Change link target'):
            anc = r['suggested_anchor']
            if anc not in text:
                errs.append(f'{tag}: suggested anchor "{anc}" not in sentence')
            linked = [l[0] for it in items for l in it["links"] if len(l[0]) >= 3 and (anc in l[0] or l[0] in anc) and l[0] in text]
            if act == 'Add link' and linked:
                errs.append(f'{tag}: anchor text overlaps an existing link in that sentence ("{linked[0]}"); pick other words or use Change link target')
            if act == 'Change link target' and not linked:
                errs.append(f'{tag}: no existing link with that anchor in the sentence to retarget')
    for s, n in per_source.items():
        p = P.get(s, {})
        words = p.get('words') or sum(len(it['t'].split()) for it in p.get('items', []) if it['tag'] in ('p', 'li'))
        cap = min(8, max(1, words // 300))
        if n > cap and not re.search(hubs, s.replace(base, '') or '/'):
            errs.append(f'{s}: {n} new links on one page; cap is {cap} ({words} words of body text, 1 per 300, max 8)')
    return errs, warns

def build(rows, a, base):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.formatting.rule import CellIsRule
    order = {'High': 0, 'Medium': 1, 'Low': 2}
    rows = sorted(rows, key=lambda r: (order[r['priority']], r['check'], r['page'], r['source']))
    F = 'Arial'; H = Font(name=F, bold=True, color='FFFFFF'); HF = PatternFill('solid', fgColor='1F3A5F')
    N = Font(name=F, size=10); Wr = Alignment(wrap_text=True, vertical='top'); thin = Side(style='thin', color='D0D0D0')
    wb = Workbook(); s = wb.active; s.title = 'Summary'
    s['A1'] = f'Internal Linking Audit — {a.client}'; s['A1'].font = Font(name=F, bold=True, size=14)
    s['A2'] = a.subtitle or ''; s['A2'].font = Font(name=F, italic=True, size=10)
    s['A4'] = 'Actions by priority page'; s['A4'].font = Font(name=F, bold=True)
    for i, h in enumerate(['Priority page', 'High', 'Medium', 'Low', 'Total', 'Done']):
        c = s.cell(5, i + 1, h); c.font = H; c.fill = HF
    labels = list(dict.fromkeys(r['page'] for r in sorted(rows, key=lambda r: r['page'] == 'Other service pages')))
    for j, lab in enumerate(labels):
        r = 6 + j; s.cell(r, 1, lab).font = N
        for k, p in enumerate(['High', 'Medium', 'Low']):
            s.cell(r, 2 + k, f'=COUNTIFS(Implementation!$C:$C,$A{r},Implementation!$A:$A,"{p}")').font = N
        s.cell(r, 5, f'=SUM(B{r}:D{r})').font = N
        s.cell(r, 6, f'=COUNTIFS(Implementation!$C:$C,$A{r},Implementation!$N:$N,"Done")').font = N
    tr = 6 + len(labels); s.cell(tr, 1, 'Total').font = Font(name=F, bold=True)
    for k, col in enumerate('BCDEF', start=2):
        s.cell(tr, k, f'=SUM({col}6:{col}{tr - 1})').font = Font(name=F, bold=True)
    fr = tr + 2; s.cell(fr, 1, 'Key findings').font = Font(name=F, bold=True)
    findings = json.load(open(a.findings)) if a.findings else []
    for i, t in enumerate(findings):
        r = fr + 1 + i; c = s.cell(r, 1, f'{i + 1}. {t}'); c.font = N; c.alignment = Wr
        s.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6); s.row_dimensions[r].height = 30
    hr = fr + 2 + len(findings)
    s.cell(hr, 1, 'How to use: work the Implementation tab top to bottom (High first). Set the Status column as you go; the counts above update automatically. Rows marked Needs approval change page copy: get client approval first.').font = Font(name=F, size=10, italic=True)
    s.merge_cells(start_row=hr, start_column=1, end_row=hr, end_column=6); s.cell(hr, 1).alignment = Wr; s.row_dimensions[hr].height = 30
    s.column_dimensions['A'].width = 34
    for col in 'BCDEF': s.column_dimensions[col].width = 11
    im = wb.create_sheet('Implementation')
    cols = ['Priority', 'Check', 'Priority page', 'Action', 'Source URL (page to edit)', 'Target URL (link to)', 'Current anchor', 'Suggested anchor', 'Sentence to edit (quoted from live page)', 'Link position', 'Reason', 'Owner', 'Date done', 'Status']
    widths = [9, 7, 18, 16, 48, 48, 12, 22, 70, 18, 55, 12, 11, 11]
    for i, (h, w) in enumerate(zip(cols, widths)):
        c = im.cell(1, i + 1, h); c.font = H; c.fill = HF; c.alignment = Alignment(wrap_text=True, vertical='center')
        im.column_dimensions[c.column_letter].width = w
    for i, r in enumerate(rows):
        vals = [r['priority'], r['check'], r['page'], r['action'], r['source'], r['target'], r.get('current_anchor', ''), r.get('suggested_anchor', ''), r['sentence'], r.get('position', ''), r.get('reason', ''), '', '', 'Needs approval' if r['action'] == 'Add sentence + link' else 'To do']
        for j, v in enumerate(vals):
            c = im.cell(i + 2, j + 1, v); c.font = N; c.alignment = Wr; c.border = Border(bottom=thin)
    n = len(rows) + 1
    dv = DataValidation(type='list', formula1='"To do,Needs approval,In progress,Done,Rejected"', allow_blank=True); im.add_data_validation(dv); dv.add(f'N2:N{n}')
    for p, col in {'High': 'F8D7DA', 'Medium': 'FFF3CD', 'Low': 'E2E3E5'}.items():
        im.conditional_formatting.add(f'A2:A{n}', CellIsRule(operator='equal', formula=[f'"{p}"'], fill=PatternFill('solid', fgColor=col)))
    im.conditional_formatting.add(f'N2:N{n}', CellIsRule(operator='equal', formula=['"Done"'], fill=PatternFill('solid', fgColor='D4EDDA')))
    im.conditional_formatting.add(f'N2:N{n}', CellIsRule(operator='equal', formula=['"Needs approval"'], fill=PatternFill('solid', fgColor='CFE2FF')))
    im.freeze_panes = 'E2'; im.auto_filter.ref = f'A1:N{n}'
    b = wb.create_sheet('Baseline')
    bl = pd.read_csv(f'{a.work}/baseline.csv')
    bcols = ['page', 'crawl_depth', 'body_links_in_live', 'pages_linking_body_live', 'body_links_in_crawl', 'body_links_out_live', 'keywords_ranked', 'related_gallery_review_pages', 'of_which_link_up_outside_menu_crawl']
    bh = ['Priority page URL', 'Crawl depth', 'Body-copy links in (live)', 'Pages linking from body copy (live)', 'Body links in per crawl export', 'Body links out (live)', 'Keywords ranked', 'Related gallery/review pages', 'Of which link up outside menu', 'Recrawl: body links in', 'Change']
    for i, h in enumerate(bh):
        c = b.cell(1, i + 1, h); c.font = H; c.fill = HF; c.alignment = Alignment(wrap_text=True, vertical='center')
    for i, (_, r) in enumerate(bl.iterrows()):
        for j, col in enumerate(bcols): b.cell(i + 2, j + 1, None if pd.isna(r[col]) else r[col]).font = N
        b.cell(i + 2, 10).fill = PatternFill('solid', fgColor='FFFF00')
        b.cell(i + 2, 11, f'=IF(J{i + 2}="","",J{i + 2}-D{i + 2})').font = N
    b.row_dimensions[1].height = 45; b.column_dimensions['A'].width = 62
    for col in 'BCDEFGHIJK': b.column_dimensions[col].width = 14
    notes = ['Notes', '"Live" counts come from reading the body copy of the site\'s indexable content pages in the browser; they override the crawl where the two disagree.',
             'Yellow column: fill in from the recrawl after implementation.'] + ([a.baseline_note] if a.baseline_note else [])
    for i, t in enumerate(notes):
        b.cell(len(bl) + 4 + i, 1, t).font = Font(name=F, bold=(i == 0), size=10)
    o = wb.create_sheet('Other findings')
    for i, h in enumerate(['Area', 'Priority', 'Finding', 'Recommendation']):
        c = o.cell(1, i + 1, h); c.font = H; c.fill = HF
    other = json.load(open(a.other)) if a.other else []
    for i, r in enumerate(other):
        for j, k in enumerate(['area', 'priority', 'finding', 'recommendation']):
            c = o.cell(i + 2, j + 1, r.get(k, '')); c.font = N; c.alignment = Wr
    for col, w in zip('ABCD', [12, 9, 70, 70]): o.column_dimensions[col].width = w
    wb.save(a.out)
    print(f'saved {a.out}: {len(rows)} actions, {len(other)} other findings')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work'); ap.add_argument('--base', required=True); ap.add_argument('--rows', required=True)
    ap.add_argument('--out', default='internal-linking-audit.xlsx'); ap.add_argument('--client', default='')
    ap.add_argument('--subtitle', default=''); ap.add_argument('--findings'); ap.add_argument('--other')
    ap.add_argument('--baseline-note', default=''); ap.add_argument('--hubs', default=r'^/$')
    ap.add_argument('--verify-only', action='store_true'); ap.add_argument('--force', action='store_true')
    a = ap.parse_args(); base = a.base.rstrip('/')
    rows = json.load(open(a.rows))
    P = {k.rstrip('/'): v for k, v in json.load(open(f'{a.work}/pages.json')).items()}
    BL = pd.read_csv(f'{a.work}/body_links.csv').fillna('')
    errs, warns = verify(rows, P, BL, base, a.hubs)
    for w in warns: print('WARN', w)
    for e in errs: print('ERROR', e)
    print(f'{len(rows)} rows checked: {len(errs)} errors, {len(warns)} warnings')
    if errs and not a.force: sys.exit(1)
    if not a.verify_only: build(rows, a, base)
```
