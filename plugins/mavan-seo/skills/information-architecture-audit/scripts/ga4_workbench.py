"""IA audit: GA4 landing-page pull. Runs INSIDE Composio's remote workbench (COMPOSIO_REMOTE_WORKBENCH), not locally.

Search Console no longer comes through Composio: it comes from the Google Sheet (scripts/gsc_sheet.py).
Composio is used only here, for GA4 sessions and key events per landing page, and only when the person wants GA4.

Composio returns at most ~40KB of printed output per call, so the pull is saved in the workbench and brought
back as one checksummed block that scripts/gsc_import.py checks and writes to work/gsc/ga4.csv.

One COMPOSIO_REMOTE_WORKBENCH call per line (state persists between calls):
  1. This whole file, with CONFIG filled in.     -> defines everything, prints nothing big
  2. ia_ga4_properties()                          -> only if CONFIG['ga4_property'] is unknown
  3. ia_ga4('2026-04-01', '2026-09-30')           -> pulls sessions + key events by landing page for those dates
  4. ia_ga4_emit()                                -> prints the block to save as work/gsc/ga4.txt
"""
import json, os, re, zlib

CONFIG = {
    'domain': 'example.com',       # bare domain, no www
    'ga4_property': None,          # 'properties/123456789'
}

IA_DIR = '/mnt/files/ia'
os.makedirs(IA_DIR, exist_ok=True)
CHUNK_CHARS = 36000


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


def _data(res):
    d = res
    for _ in range(3):
        if isinstance(d, dict) and 'rows' not in d and isinstance(d.get('data'), dict):
            d = d['data']
    return d if isinstance(d, dict) else {}


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


def ia_ga4(start, end):
    """Pulls sessions and key events by landing page for start..end (YYYY-MM-DD). Use the same dates as the
    Search Console sheet."""
    if not CONFIG.get('ga4_property'):
        print('No ga4_property in CONFIG'); return
    ga, off = {}, 0
    while True:
        res, err = run_composio_tool('GOOGLE_ANALYTICS_RUN_REPORT', {
            'property': CONFIG['ga4_property'],
            'dateRanges': [{'startDate': start, 'endDate': end}],
            'dimensions': [{'name': 'landingPage'}],
            'metrics': [{'name': 'sessions'}, {'name': 'keyEvents'}],
            'limit': 100000, 'offset': off})
        if err:
            print('GA4 failed:', err); return
        d = _data(res)
        rows = d.get('rows') or []
        for r in rows:
            dv = [x.get('value') for x in r.get('dimensionValues', [])]
            mv = [float(x.get('value') or 0) for x in r.get('metricValues', [])]
            if not dv[0] or dv[0].startswith('(not set)'):
                continue
            k = ia_key(dv[0])
            a = ga.setdefault(k, [0.0, 0.0])
            a[0] += mv[0]; a[1] += mv[1]
        off += len(rows)
        if not rows or off >= int(d.get('rowCount') or 0):
            break
    json.dump({'start': start, 'end': end, 'rows': ga}, open(f'{IA_DIR}/ga4.json', 'w'))
    print(f'GA4 {start}..{end}: {len(ga)} landing pages, {int(sum(v[0] for v in ga.values()))} sessions')


def ia_ga4_emit():
    """Prints the checksummed block. Save the whole output, exactly as printed, to work/gsc/ga4.txt."""
    d = json.load(open(f'{IA_DIR}/ga4.json'))
    lines = [f"{k}|{int(v[0])}|{int(v[1])}" for k, v in sorted(d['rows'].items(), key=lambda x: -x[1][0])]
    if sum(len(l) + 1 for l in lines) > CHUNK_CHARS:
        print(f'Too many landing pages for one block ({len(lines)}); keeping the top ones by sessions.')
        keep, size = [], 0
        for l in lines:
            size += len(l) + 1
            if size > CHUNK_CHARS:
                break
            keep.append(l)
        lines = keep
    text = '\n'.join(lines)
    crc = zlib.crc32(text.encode('utf-8')) & 0xffffffff
    print(f"##IA table=ga4 part=1/1 rows={len(lines)} crc={crc:08x}\nkey|sessions|key_events\n{text}\n##END")
