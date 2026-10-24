"""IA audit: Search Console + GA4 pull. Runs INSIDE Composio's remote workbench, not locally.

Composio keeps large API responses in its own sandbox and returns at most ~40KB of printed
output per call, so all heavy processing happens here and only compact, checksummed tables
are printed back (see ia_emit).

How to run (one COMPOSIO_REMOTE_WORKBENCH call per line; state persists between calls):
  1. The whole file, with CONFIG filled in.            -> defines everything, prints nothing big
  2. ia_ga4_properties()                               -> only if CONFIG['ga4_property'] is unknown
  3. ia_months()                                       -> 16-month migration check table
  4. ia_window('YYYY-MM-DD', 'YYYY-MM-DD')             -> pulls the analysis window (+ GA4)
  5. ia_build()                                        -> builds tables, prints the part list
  6. ia_emit('<table>', <part>)                        -> once per part listed by ia_build()
  7. ia_pair_queries([(id_a, id_b), ...])              -> later, for the duplicate pairs kept
Every step saves to /mnt/files/ia/, so if the sandbox restarts, re-run step 1 and carry on.
"""
import json, os, re, zlib, datetime as _dt
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

CONFIG = {
    'site_url': 'sc-domain:example.com',   # exactly as GOOGLE_SEARCH_CONSOLE_LIST_SITES returns it
    'domain': 'example.com',               # bare domain, no www
    'brand_terms': ['example'],            # lowercase; any query containing one is brand
    'ga4_property': None,                  # 'properties/123456789', or None to skip GA4
}

IA_DIR = '/mnt/files/ia'
os.makedirs(IA_DIR, exist_ok=True)
CHUNK_CHARS = 24000


# ---------- URL normalizing (keep identical to normalize() in scripts/common.py) ----------
def ia_norm(u):
    """lowercase, drop ?query and #fragment, https, no www, trailing slash (not on files)."""
    if not isinstance(u, str) or not u.strip():
        return ''
    u = u.strip().lower()
    u = re.sub(r'[?#].*$', '', u)
    if u.startswith('//'):
        u = 'https:' + u
    u = re.sub(r'^http://', 'https://', u)
    if not u.startswith('https://'):
        u = 'https://' + CONFIG['domain'] + ('' if u.startswith('/') else '/') + u
    u = re.sub(r'^https://www\.', 'https://', u)
    if not u.endswith('/') and not re.search(r'/[^/]*\.[a-z0-9]{2,5}$', u):
        u += '/'
    return u


def ia_key(u):
    """Compact key: the path for the main domain, the full URL for anything else."""
    n = ia_norm(u)
    pre = 'https://' + CONFIG['domain']
    return n[len(pre):] if n.startswith(pre + '/') else n


def _is_brand(q):
    q = (q or '').lower()
    return any(t and t in q for t in CONFIG['brand_terms'])


def _save(name, obj):
    json.dump(obj, open(f'{IA_DIR}/{name}.json', 'w'))


def _load(name):
    return json.load(open(f'{IA_DIR}/{name}.json'))


def _data(res):
    d = res
    for _ in range(3):
        if isinstance(d, dict) and 'rows' not in d and isinstance(d.get('data'), dict):
            d = d['data']
    return d if isinstance(d, dict) else {}


# ---------- Search Console ----------
def _gsc(dims, start, end):
    rows, start_row, limit = [], 0, 25000
    while True:
        res, err = run_composio_tool('GOOGLE_SEARCH_CONSOLE_SEARCH_ANALYTICS_QUERY', {
            'site_url': CONFIG['site_url'], 'start_date': start, 'end_date': end,
            'dimensions': dims, 'row_limit': limit, 'start_row': start_row, 'data_state': 'final'})
        if err:
            raise RuntimeError(f'GSC {dims} {start}..{end}: {err}')
        got = _data(res).get('rows') or []
        rows.extend(got)
        if len(got) < limit:
            return rows
        start_row += limit


def _month_ranges(n=16):
    last = _dt.date.today() - _dt.timedelta(days=3)
    first_of_this = last.replace(day=1)
    out, end = [], first_of_this - _dt.timedelta(days=1)
    for _ in range(n):
        start = end.replace(day=1)
        out.append((start.isoformat(), end.isoformat()))
        end = start - _dt.timedelta(days=1)
    return out[::-1]


def ia_months():
    """16 full months by page. Prints the migration-check table and a suggested window."""
    months = _month_ranges()
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda m: _gsc(['page'], m[0], m[1]), months))
    per = []
    for (s, e), rows in zip(months, res):
        agg = defaultdict(lambda: [0, 0])
        for r in rows:
            k = ia_key(r['keys'][0])
            agg[k][0] += r.get('clicks', 0)
            agg[k][1] += r.get('impressions', 0)
        per.append({'month': s[:7], 'pages': agg})
    _save('months_pages', [{'month': m['month'], 'pages': m['pages']} for m in per])
    last_keys = set(per[-1]['pages'])
    table = []
    for m in per:
        clicks = sum(v[0] for v in m['pages'].values())
        impr = sum(v[1] for v in m['pages'].values())
        gone = sum(v[1] for k, v in m['pages'].items() if k not in last_keys)
        table.append({'month': m['month'], 'clicks': int(clicks), 'impressions': int(impr),
                      'gone_impr': int(gone), 'gone_pct': round(gone / impr, 3) if impr else 0})
    _save('monthly', table)
    # suggestion: a migration is the month after the last month where 25%+ of impressions
    # went to URLs that are dead now, provided later months sit under 10%
    sug, hi = None, [i for i, t in enumerate(table) if t['gone_pct'] >= 0.25]
    if hi and all(t['gone_pct'] < 0.10 for t in table[hi[-1] + 1:-1]) and hi[-1] + 1 < len(table):
        sug = table[hi[-1] + 1]['month']
    print('month | clicks | impressions | impr on URLs with none last month | share')
    for t in table:
        print(f"{t['month']} | {t['clicks']} | {t['impressions']} | {t['gone_impr']} | {t['gone_pct']:.0%}")
    print('Suggested migration month:', sug or 'none detected (use the last 3 full months)')
    print('Last 3 full months:', months[-3][0], 'to', months[-1][1])


def ia_window(start, end):
    """Pulls page totals, page+query and GA4 landing pages for the analysis window."""
    _save('window', {'start': start, 'end': end})
    s, e = _dt.date.fromisoformat(start), _dt.date.fromisoformat(end)
    spans, cur = [], s
    while cur <= e:  # month-sized slices so page+query pulls run in parallel within 180s
        nxt = min((cur.replace(day=28) + _dt.timedelta(days=4)).replace(day=1) - _dt.timedelta(days=1), e)
        spans.append((cur.isoformat(), nxt.isoformat()))
        cur = nxt + _dt.timedelta(days=1)
    with ThreadPoolExecutor(8) as ex:
        f_pages = ex.submit(_gsc, ['page'], start, end)
        pq_parts = list(ex.map(lambda sp: _gsc(['page', 'query'], sp[0], sp[1]), spans))
        page_rows = f_pages.result()
    _save('page_rows', page_rows)
    pq = defaultdict(lambda: [0.0, 0.0, 0.0])  # (key, query) -> clicks, impr, pos*impr
    raw_n = 0
    for part in pq_parts:
        for r in part:
            raw_n += 1
            k = (ia_key(r['keys'][0]), r['keys'][1])
            a = pq[k]
            a[0] += r.get('clicks', 0); a[1] += r.get('impressions', 0)
            a[2] += r.get('position', 0) * r.get('impressions', 0)
    _save('pq', [[k[0], k[1], v[0], v[1], v[2]] for k, v in pq.items()])
    print(f'GSC window {start}..{end}: {len(page_rows)} page rows, {raw_n} page+query rows '
          f'({len(pq)} after merging months and URL variants)')
    ga = []
    if CONFIG.get('ga4_property'):
        off = 0
        while True:
            res, err = run_composio_tool('GOOGLE_ANALYTICS_RUN_REPORT', {
                'property': CONFIG['ga4_property'],
                'dateRanges': [{'startDate': start, 'endDate': end}],
                'dimensions': [{'name': 'landingPage'}],
                'metrics': [{'name': 'sessions'}, {'name': 'engagedSessions'}, {'name': 'keyEvents'}],
                'limit': 100000, 'offset': off})
            if err:
                print('GA4 failed:', err)
                ga = None
                break
            d = _data(res)
            rows = d.get('rows') or []
            for r in rows:
                dv = [x.get('value') for x in r.get('dimensionValues', [])]
                mv = [float(x.get('value') or 0) for x in r.get('metricValues', [])]
                ga.append([dv[0]] + mv)
            off += len(rows)
            if not rows or off >= int(d.get('rowCount') or 0):
                break
        if ga is not None:
            print(f'GA4: {len(ga)} landing page rows')
    else:
        print('GA4: skipped (no property in CONFIG)')
    _save('ga4', ga)


def ia_ga4_properties():
    """Lists GA4 properties so the right one can go in CONFIG['ga4_property']."""
    token, out = None, []
    while True:
        args = {'pageSize': 200}
        if token:
            args['pageToken'] = token
        res, err = run_composio_tool('GOOGLE_ANALYTICS_LIST_ACCOUNT_SUMMARIES', args)
        if err:
            print('GA4 list failed:', err); return
        d = _data(res)
        for acc in d.get('accountSummaries') or []:
            for p in acc.get('propertySummaries') or []:
                out.append((p.get('property'), p.get('displayName'), acc.get('displayName')))
        token = d.get('nextPageToken')
        if not token:
            break
    flat = lambda x: re.sub(r'[^a-z0-9]', '', str(x).lower())
    hint = flat(CONFIG['domain'].split('.')[0])
    likely = [p for p in out if hint[:8] in flat(p[1]) + flat(p[2]) or flat(p[1])[:8] in hint]
    print(f'{len(out)} GA4 properties. ' + ('Likely matches:' if likely else 'No name match; all:'))
    for p in likely or out:
        print(f'{p[0]} | {p[1]} | account: {p[2]}')


# ---------- build compact tables ----------
# Every other table refers to pages by their row number in the pages table ("id"), which keeps
# the tables small enough to bring back in one or two parts.
def _clean(s):
    return re.sub(r'[|\r\n\t]+', ' ', str(s)).strip()


def ia_build():
    page_rows, pq, ga = _load('page_rows'), _load('pq'), _load('ga4')
    pages = defaultdict(lambda: {'c': 0, 'i': 0, 'pw': 0.0, 'tq': '', 'tqi': 0, 'nb': 0,
                                 's': 0, 'es': 0, 'ke': 0})
    utm, raw_clicks, raw_impr = defaultdict(lambda: [0, 0]), 0, 0
    for r in page_rows:
        raw = r['keys'][0]
        p = pages[ia_key(raw)]
        c, i = r.get('clicks', 0), r.get('impressions', 0)
        raw_clicks += c; raw_impr += i
        p['c'] += c; p['i'] += i; p['pw'] += r.get('position', 0) * i
        if '?' in raw and ia_key(raw) == '/':
            utm[raw][0] += c; utm[raw][1] += i
    q_pages = defaultdict(dict)  # non-brand query -> {key: impressions}
    page_nb = defaultdict(float)
    brand_impr = 0
    for k, q, c, i, pw in pq:
        if _is_brand(q):
            brand_impr += i
            continue
        q_pages[q][k] = q_pages[q].get(k, 0) + i
        page_nb[k] += i
        p = pages[k]
        if i > p['tqi']:
            p['tq'], p['tqi'] = q, i
    for k, v in page_nb.items():
        pages[k]['nb'] = v
    if ga:
        for row in ga:
            lp = row[0]
            if not lp or lp.startswith('(not set)'):
                continue
            p = pages[ia_key(lp)]
            p['s'] += row[1]; p['es'] += row[2]; p['ke'] += row[3]

    keys = sorted(pages, key=lambda k: (-pages[k]['i'], -pages[k]['s'], k))
    pid = {k: n for n, k in enumerate(keys)}

    # pair overlap: per shared query take the smaller of the two pages' impressions;
    # score = that total / the smaller page's non-brand query impressions.
    # The homepage is left out here; it has its own table (home).
    pair = defaultdict(lambda: [0.0, 0])
    for q, pm in q_pages.items():
        top = sorted(((k, v) for k, v in pm.items() if k != '/'), key=lambda x: -x[1])[:25]
        for a in range(len(top)):
            for b in range(a + 1, len(top)):
                (ka, va), (kb, vb) = top[a], top[b]
                key = (ka, kb) if pid[ka] < pid[kb] else (kb, ka)
                acc = pair[key]
                acc[0] += min(va, vb); acc[1] += 1
    pairs = []
    for (a, b), (shared, n) in pair.items():
        denom = min(page_nb.get(a, 0), page_nb.get(b, 0))
        if denom > 0 and n >= 2 and shared / denom >= 0.30:
            pairs.append([pid[a], pid[b], round(shared / denom, 3), n, int(shared)])
    pairs.sort(key=lambda x: -x[4])

    # searches with no owner: 3+ pages show for it and no page gets half its impressions
    noowner = []
    for q, pm in q_pages.items():
        tot = sum(pm.values())
        if len(pm) >= 3 and tot > 0 and max(pm.values()) / tot < 0.5:
            top = sorted(pm.items(), key=lambda x: -x[1])[:6]
            noowner.append([_clean(q), int(tot), len(pm), ';'.join(f'{pid[k]}:{int(v)}' for k, v in top)])
    noowner.sort(key=lambda x: -x[1])
    noowner = noowner[:150]

    # pages that share 60%+ of their non-brand query impressions with the homepage
    home_top = sorted(((q, pm['/']) for q, pm in q_pages.items() if '/' in pm), key=lambda x: -x[1])[:10]
    page_home = defaultdict(lambda: [0.0, 0])
    for q, pm in q_pages.items():
        if '/' in pm:
            for k, i in pm.items():
                if k != '/':
                    page_home[k][0] += i; page_home[k][1] += 1
    home = []
    for k, (si, n) in page_home.items():
        nb = page_nb.get(k, 0)
        if nb > 0 and si / nb >= 0.60:
            home.append([pid[k], round(si / nb, 3), n, int(nb)])
    home.sort(key=lambda x: -x[3])

    page_tab = []
    for k in keys:
        p = pages[k]
        pos = round(p['pw'] / p['i'], 1) if p['i'] else ''
        page_tab.append([pid[k], k, int(p['c']), int(p['i']), pos, _clean(p['tq'])[:80], int(p['tqi']),
                         int(p['nb']), int(p['s']), int(p['es']), int(p['ke'])])

    win = _load('window')
    meta = [
        ['site_url', CONFIG['site_url']], ['domain', CONFIG['domain']],
        ['window_start', win['start']], ['window_end', win['end']],
        ['clicks', int(raw_clicks)], ['impressions', int(raw_impr)],
        ['page_rows', len(page_rows)], ['page_query_rows', len(pq)],
        ['brand_terms', ', '.join(CONFIG['brand_terms'])], ['brand_query_impr', int(brand_impr)],
        ['ga4_property', CONFIG.get('ga4_property') or ''],
        ['ga4_rows', len(ga) if ga else ('failed' if ga is None else 0)],
        ['home_top_queries', '; '.join(f'{_clean(q)} ({int(i)})' for q, i in home_top)],
    ] + [['utm_home', f'{_clean(u)} ({int(v[0])} clicks, {int(v[1])} impr)']
         for u, v in sorted(utm.items(), key=lambda x: -x[1][0])[:5]]
    monthly = [[t['month'], t['clicks'], t['impressions'], t['gone_impr'], t['gone_pct']]
               for t in (_load('monthly') if os.path.exists(f'{IA_DIR}/monthly.json') else [])]
    tables = {
        'meta': (['key', 'value'], meta),
        'monthly': (['month', 'clicks', 'impressions', 'gone_impr', 'gone_pct'], monthly),
        'pages': (['id', 'key', 'clicks', 'impressions', 'position', 'top_query', 'top_query_impr',
                   'nonbrand_query_impr', 'ga4_sessions', 'ga4_engaged', 'ga4_key_events'], page_tab),
        'pairs': (['id_a', 'id_b', 'overlap', 'shared_queries', 'shared_impr'], pairs),
        'noowner': (['query', 'impressions', 'pages', 'top_pages'], noowner),
        'home': (['id', 'share_on_home_queries', 'shared_queries', 'nonbrand_query_impr'], home),
    }
    parts = {}
    for name, (head, rows) in tables.items():
        lines = ['|'.join(_clean(x) for x in r) for r in rows]
        chunks, cur, size = [], [], 0
        for ln in lines:
            if cur and size + len(ln) + 1 > CHUNK_CHARS:
                chunks.append(cur); cur, size = [], 0
            cur.append(ln); size += len(ln) + 1
        chunks.append(cur)
        parts[name] = {'head': head, 'chunks': chunks}
    _save('parts', parts)
    _save('q_pages', {'keys': keys, 'q': {q: {str(pid[k]): v for k, v in pm.items()} for q, pm in q_pages.items()}})
    plan, cur, size = [], [], 0
    for name, v in parts.items():
        for n, c in enumerate(v['chunks'], 1):
            sz = sum(len(l) + 1 for l in c) + 120
            if cur and size + sz > CHUNK_CHARS:
                plan.append(cur); cur, size = [], 0
            cur.append(f'{name}:{n}'); size += sz
    plan.append(cur)
    for name, v in parts.items():
        print(f"{name}: {sum(len(c) for c in v['chunks'])} rows")
    print('Bring the tables back with these calls, one per workbench call:')
    for g in plan:
        print('  ia_emit(' + ', '.join(repr(x) for x in g) + ')')


def _block(name, part, body, head, total):
    text = '\n'.join(body)
    crc = zlib.crc32(text.encode('utf-8')) & 0xffffffff
    return (f"##IA table={name} part={part}/{total} rows={len(body)} crc={crc:08x}\n"
            + '|'.join(head) + '\n' + text + ('\n' if text else '') + '##END')


def ia_emit(*specs):
    """Prints checksummed blocks, e.g. ia_emit('pages:1') or ia_emit('meta:1', 'monthly:1').
    Save the whole printed output, exactly as printed, to work/gsc/<anything>.txt."""
    parts = _load('parts')
    for spec in specs:
        name, _, part = spec.partition(':')
        v = parts[name]
        part = int(part or 1)
        print(_block(name, part, v['chunks'][part - 1], v['head'], len(v['chunks'])))


def ia_pair_queries(pairs, n=3):
    """Top shared non-brand queries for the duplicate pairs kept, e.g. ia_pair_queries([(3, 17)]).
    Save the printed block to work/gsc/pair_queries.txt."""
    d = _load('q_pages')
    out = []
    for a, b in pairs:
        a, b = str(a), str(b)
        shared = [(min(pm[a], pm[b]), q) for q, pm in d['q'].items() if a in pm and b in pm]
        top = '; '.join(_clean(q)[:60] for _, q in sorted(shared, reverse=True)[:n])
        out.append(f'{a}|{b}|{top}')
    print(_block('pair_queries', 1, out, ['id_a', 'id_b', 'top_shared'], 1))


def ia_crawl_split(not_live_ids):
    """Exact SOP migration check: monthly impressions on URLs live in the crawl vs not.
    not_live_ids = ids from the pages table whose URL is not a live 200 page in the crawl
    (analyze.py prints the full call). URLs with no impressions in the window count as not
    live. Save the printed block to work/gsc/monthly_split.txt."""
    keys = _load('q_pages')['keys']
    bad = {int(i) for i in not_live_ids}
    live = {k for n, k in enumerate(keys) if n not in bad}
    out = []
    for m in _load('months_pages'):
        impr = sum(v[1] for v in m['pages'].values())
        off = sum(v[1] for k, v in m['pages'].items() if k not in live)
        out.append(f"{m['month']}|{int(impr)}|{int(off)}|{round(off / impr, 3) if impr else 0}")
    print(_block('monthly_split', 1, out, ['month', 'impressions', 'not_in_crawl_impr', 'not_in_crawl_pct'], 1))
