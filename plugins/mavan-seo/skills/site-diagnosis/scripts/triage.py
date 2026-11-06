#!/usr/bin/env python3
"""Search Console triage for the site-diagnosis skill: compare two periods of page + query data.

No Composio and no API calls: the Google Sheet (or .xlsx / .csv download) of Search Console data is the only
source. Every count, join and sum in the workbook comes from this script.

Usage:
  python triage.py profile --domain example.com --a SHEET_A.xlsx [--a-tab NAME] --b SHEET_B.xlsx [--b-tab NAME]
        [--brand "term,term"] [--crawl CRAWL.csv]
  python triage.py build   --domain example.com --client "Name" --brand "term,term"
        --a SHEET_A.xlsx [--a-tab NAME] --a-start YYYY-MM-DD --a-end YYYY-MM-DD
        --b SHEET_B.xlsx [--b-tab NAME] --b-start YYYY-MM-DD --b-end YYYY-MM-DD
        --min-page-impr N --top-n N --prune-if N --dead-share-pct N [--rank-by impressions|clicks]
        [--include-brand-competing] [--crawl CRAWL.csv] --out "CLIENT Site Triage.xlsx"

Period A is the earlier (baseline) period, period B the later one. Change = B minus A.
`profile` prints facts used to build the questions for the person (it writes nothing). The thresholds of
`build` have no defaults on purpose: the person confirms each one.

A page's or search's clicks and impressions here are the sum of its listed page + query rows, because Search
Console withholds rare queries from page + query exports. They can be lower than the Performance report's totals.
"""
import argparse
import csv
import re
import sys
from collections import defaultdict

import pandas as pd

GSC_TAB = 'Claude Use This'  # Mavan's Search Console template tab, used when it exists
GSC_COLS = {'page': ('page', 'landing page', 'url', 'address', 'top pages'),
            'query': ('query', 'top queries', 'search query'),
            'clicks': ('clicks',), 'impressions': ('impressions',)}
POS_COLS = ('position', 'average position', 'avg. position')
CRAWL_COLS = {'url': ('url', 'address'), 'status': ('http status code', 'status code')}
PROFILE_THRESHOLDS = (5, 10, 25, 50, 100)


# ---------------------------------------------------------------- loading
def to_num(x):
    try:
        return float(str(x).replace(',', '').replace('%', '').strip() or 0)
    except ValueError:
        return None


def bare_domain(d):
    d = re.sub(r'^https?://', '', d.strip().lower())
    return re.sub(r'^www\.', '', d).split('/')[0]


def normalize(u, domain):
    """Same rules as the IA audit's normalize(): lowercase, no ?query or #fragment, https, no www, trailing
    slash (not on files). The main domain becomes a path, anything else keeps its full URL."""
    u = re.sub(r'[?#].*$', '', str(u).strip().lower())
    if not u:
        return ''
    if u.startswith('//'):
        u = 'https:' + u
    u = re.sub(r'^http://', 'https://', u)
    if not u.startswith('https://'):
        u = 'https://' + domain + ('' if u.startswith('/') else '/') + u
    u = re.sub(r'^https://www\.', 'https://', u)
    if not u.endswith('/') and not re.search(r'/[^/]*\.[a-z0-9]{2,5}$', u):
        u += '/'
    pre = 'https://' + domain
    return u[len(pre):] if u.startswith(pre + '/') else u


def read_raw(path):
    """-> {tab name: [row, ...]} from .xlsx, a text export with '## Sheet name:' lines, or a plain CSV."""
    if path.lower().endswith(('.xlsx', '.xlsm', '.xls')):
        return {n: df.fillna('').values.tolist()
                for n, df in pd.read_excel(path, sheet_name=None, dtype=str, header=None).items()}
    raw, name = {}, '(file)'
    with open(path, encoding='utf-8-sig', newline='') as fh:
        for line in fh:
            if line.startswith('## Sheet name:'):
                name = line.split(':', 1)[1].strip()
                raw[name] = []
            elif line.strip():
                raw.setdefault(name, []).append(next(csv.reader([line])))
    return raw


def read_tabs(path):
    """-> {tab: [(page, query, clicks, impressions, position or None)]} for every tab with the four columns
    in its first 10 rows."""
    tabs = {}
    for name, rows in read_raw(path).items():
        for hi, row in enumerate(rows[:10]):
            cells = [str(c).strip().lower() for c in row]
            idx = {k: next((cells.index(n) for n in names if n in cells), None) for k, names in GSC_COLS.items()}
            if any(v is None for v in idx.values()):
                continue
            pos = next((cells.index(n) for n in POS_COLS if n in cells), None)
            out = []
            for r in rows[hi + 1:]:
                if len(r) <= max(idx.values()):
                    continue
                c, i = to_num(r[idx['clicks']]), to_num(r[idx['impressions']])
                if c is None or i is None or not str(r[idx['query']]).strip() or not str(r[idx['page']]).strip():
                    continue
                p = to_num(r[pos]) if pos is not None and len(r) > pos else None
                out.append((str(r[idx['page']]).strip(), str(r[idx['query']]).strip(), c, i, p))
            tabs[name] = out
            break
    return tabs


def pick_tab(tabs, tab, path):
    if not tabs:
        sys.exit(f'{path}: no tab has Page, Query, Clicks and Impressions columns. Stop and tell the person '
                 'what the sheet needs ("What you need" in SKILL.md).')
    if tab:
        if tab not in tabs:
            sys.exit(f"--tab '{tab}' is not a tab with those columns in {path}. Tabs: {{ {', '.join(tabs)} }}")
        return tab
    named = next((n for n in tabs if n.strip().lower() == GSC_TAB.lower()), None)
    if named:
        return named
    if len(tabs) == 1:
        return next(iter(tabs))
    listing = '; '.join(f"'{n}' ({len(r)} rows)" for n, r in tabs.items())
    sys.exit(f'{path} has several tabs with GSC columns: {listing}. Ask the person which tab is this period, then '
             'pass --a-tab / --b-tab. Never add tabs together.')


def load_period(path, tab, domain, brand):
    """-> DataFrame [page, query, clicks, impr, pos, brand] with page keys normalized and one row per
    (page, query); also the pages on other domains and the tab used."""
    tabs = read_tabs(path)
    use = pick_tab(tabs, tab, path)
    df = pd.DataFrame(tabs[use], columns=['raw', 'query', 'clicks', 'impr', 'pos'])
    df['page'] = df['raw'].map(lambda u: normalize(u, domain))
    df['query'] = df['query'].str.strip().str.lower()
    df['pw'] = df['pos'].fillna(0) * df['impr'].where(df['pos'].notna(), 0)
    df['pi'] = df['impr'].where(df['pos'].notna(), 0)
    g = df.groupby(['page', 'query'], as_index=False).agg(
        clicks=('clicks', 'sum'), impr=('impr', 'sum'), pw=('pw', 'sum'), pi=('pi', 'sum'))
    g['pos'] = (g['pw'] / g['pi']).where(g['pi'] > 0)
    g['brand'] = g['query'].map(lambda q: any(t in q for t in brand))
    g = g.drop(columns=['pw', 'pi'])
    foreign = sorted({p for p in g['page'] if p.startswith('https://')})
    return g, foreign, use


def load_crawl(path, domain):
    """-> {page key: status code string}. Needs the URL and status columns of a Sitebulb or Screaming Frog export."""
    raw = read_raw(path)
    name = next(iter(raw))
    rows = raw[name]
    for hi, row in enumerate(rows[:10]):
        cells = [str(c).strip().lower() for c in row]
        idx = {k: next((cells.index(n) for n in names if n in cells), None) for k, names in CRAWL_COLS.items()}
        if any(v is None for v in idx.values()):
            continue
        out = {}
        for r in rows[hi + 1:]:
            if len(r) > max(idx.values()) and str(r[idx['url']]).strip():
                out[normalize(r[idx['url']], domain)] = str(r[idx['status']]).strip().split('.')[0]
        return out
    sys.exit(f'{path}: no URL and status code columns found (Sitebulb: URL, HTTP Status Code; Screaming Frog: '
             'Address, Status Code). Ask the person for the crawl URL export with every status code.')


def status_class(code):
    if code is None:
        return 'Not in crawl'
    if code == '200':
        return '200 OK'
    if code.startswith('3'):
        return '3xx redirect'
    if code.startswith('4'):
        return '4xx error' if code != '404' else '404 not found'
    if code.startswith('5'):
        return '5xx error'
    return f'Other ({code})'


# ---------------------------------------------------------------- computations
def pct(a, b):
    if a == 0:
        return 'new' if b else ''
    return (b - a) / a


def totals(df):
    nb = df[~df['brand']]
    br = df[df['brand']]
    return {'Clicks (all searches)': df['clicks'].sum(), 'Impressions (all searches)': df['impr'].sum(),
            'Clicks (non-brand)': nb['clicks'].sum(), 'Impressions (non-brand)': nb['impr'].sum(),
            'Clicks (brand)': br['clicks'].sum(), 'Impressions (brand)': br['impr'].sum(),
            'Pages with impressions': df.loc[df['impr'] > 0, 'page'].nunique(),
            'Non-brand searches': nb['query'].nunique()}


def by_page(a, b):
    def agg(df, tag):
        t = df.groupby('page').agg(**{f'c_{tag}': ('clicks', 'sum'), f'i_{tag}': ('impr', 'sum')})
        n = df[~df['brand']].groupby('page').agg(**{f'nc_{tag}': ('clicks', 'sum'), f'ni_{tag}': ('impr', 'sum')})
        return t.join(n, how='outer')
    m = agg(a, 'a').join(agg(b, 'b'), how='outer').fillna(0).reset_index()
    for k in ('c', 'i', 'nc', 'ni'):
        m[f'{k}_d'] = m[f'{k}_b'] - m[f'{k}_a']
    return m


def by_search(a, b):
    a, b = a[~a['brand']], b[~b['brand']]
    def agg(df, tag):
        g = df.assign(pw=df['pos'].fillna(0) * df['impr'].where(df['pos'].notna(), 0),
                      pi=df['impr'].where(df['pos'].notna(), 0))
        t = g.groupby('query').agg(**{f'c_{tag}': ('clicks', 'sum'), f'i_{tag}': ('impr', 'sum'),
                                      f'pages_{tag}': ('page', 'nunique'), f'pw_{tag}': ('pw', 'sum'),
                                      f'pi_{tag}': ('pi', 'sum')})
        t[f'pos_{tag}'] = (t[f'pw_{tag}'] / t[f'pi_{tag}']).where(t[f'pi_{tag}'] > 0)
        return t.drop(columns=[f'pw_{tag}', f'pi_{tag}'])
    m = agg(a, 'a').join(agg(b, 'b'), how='outer')
    for k in ('c_a', 'i_a', 'c_b', 'i_b', 'pages_a', 'pages_b'):
        m[k] = m[k].fillna(0)
    m = m.reset_index()
    m['c_d'] = m['c_b'] - m['c_a']
    m['i_d'] = m['i_b'] - m['i_a']
    return m


def movers(m, rank_by, n, nonbrand_cols):
    """top-n losses (change < 0, biggest first) and gains (change > 0, biggest first)."""
    key, other = ('i', 'c') if rank_by == 'impressions' else ('c', 'i')
    dcol, ocol = (f'n{key}_d' if nonbrand_cols else f'{key}_d'), (f'n{other}_d' if nonbrand_cols else f'{other}_d')
    loss = m[m[dcol] < 0].sort_values([dcol, ocol]).head(n)
    gain = m[m[dcol] > 0].sort_values([dcol, ocol], ascending=[False, False]).head(n)
    return loss, gain


def competing(a, b, min_impr, include_brand):
    """One row per (query, page) for every query that has 2+ pages with >= min_impr impressions in A or in B."""
    if not include_brand:
        a, b = a[~a['brand']], b[~b['brand']]
    cols = ['clicks', 'impr', 'pos']
    m = a.merge(b, on=['page', 'query'], how='outer', suffixes=('_a', '_b'))
    for c in ('clicks_a', 'impr_a', 'clicks_b', 'impr_b'):
        m[c] = m[c].fillna(0)
    m['ok_a'] = m['impr_a'] >= min_impr
    m['ok_b'] = m['impr_b'] >= min_impr
    n = m.groupby('query').agg(n_a=('ok_a', 'sum'), n_b=('ok_b', 'sum'))
    n = n[(n['n_a'] >= 2) | (n['n_b'] >= 2)]
    m = m.merge(n, left_on='query', right_index=True)
    m = m[m['ok_a'] | m['ok_b']].copy()
    # a query counts only if 2+ pages remain after the per-row filter in at least one period
    m['n_a'] = m.groupby('query')['ok_a'].transform('sum')
    m['n_b'] = m.groupby('query')['ok_b'].transform('sum')
    m['qimpr'] = m.groupby('query')[['impr_a', 'impr_b']].transform('sum').max(axis=1)
    m['where'] = m.apply(lambda r: 'both periods' if r['n_a'] >= 2 and r['n_b'] >= 2
                         else ('period A only' if r['n_a'] >= 2 else 'period B only'), axis=1)
    return m.sort_values(['qimpr', 'query', 'impr_b', 'impr_a'], ascending=[False, True, False, False])


# ---------------------------------------------------------------- commands
def parse_brand(s):
    """'none' (the person said not to filter) and an empty value both mean no brand terms."""
    if (s or '').strip().lower() == 'none':
        return []
    return [t.strip().lower() for t in (s or '').split(',') if t.strip()]


def periods(a):
    domain = bare_domain(a.domain)
    brand = parse_brand(a.brand)
    pa = load_period(a.a, a.a_tab, domain, brand)
    pb = load_period(a.b, a.b_tab, domain, brand)
    if a.a == a.b and pa[2] == pb[2]:
        sys.exit('Period A and period B point at the same tab. Each period needs its own sheet or tab.')
    return domain, brand, pa, pb


def cmd_profile(a):
    domain, brand, (A, fa, ta), (B, fb, tb) = periods(a)
    print(f'Domain: {domain}   brand terms used: {brand or "none"}')
    for tag, df, tab, fo in (('A', A, ta, fa), ('B', B, tb, fb)):
        nb = df[~df['brand']]
        print(f'\nPeriod {tag} (tab "{tab}"): {len(df)} page+query rows, {df["page"].nunique()} pages, '
              f'{df["clicks"].sum():,.0f} clicks, {df["impr"].sum():,.0f} impressions; '
              f'non-brand {nb["clicks"].sum():,.0f} clicks, {nb["impr"].sum():,.0f} impressions')
        if fo:
            print(f'  WARNING: {len(fo)} pages are not on {domain} (kept under their full URL), e.g. {fo[:3]}')
    print('\nTop non-brand searches by impressions across both periods (check for brand terms you missed):')
    q = pd.concat([A, B])
    q = q[~q['brand']].groupby('query')['impr'].sum().sort_values(ascending=False).head(15)
    for k, v in q.items():
        print(f'  {v:>9,.0f}  {k}')
    print('\nSearches with 2+ pages at or above each impression level (non-brand, in A or B):')
    for t in PROFILE_THRESHOLDS:
        c = competing(A, B, t, False)
        print(f'  >= {t:<4} impressions per page: {c["query"].nunique()} searches')
    if a.crawl:
        crawl = load_crawl(a.crawl, domain)
        pages = set(A['page']) | set(B['page'])
        cnt = defaultdict(int)
        for p in pages:
            cnt[status_class(crawl.get(p))] += 1
        print(f'\nCrawl: {len(crawl)} URLs. Search Console pages by status: {dict(cnt)}')
        print('  (An export with only 200 URLs shows every dead URL as "Not in crawl"; confirm it has every status code.)')


def r0(x):
    return round(float(x), 1) if x == x and x is not None else ''


def write_workbook(a, domain, brand, A, B, crawl):
    ta, tb = totals(A), totals(B)
    pg = by_page(A, B)
    sr = by_search(A, B)
    pg['status'] = pg['page'].map(lambda p: status_class(crawl.get(p)) if crawl is not None else '')
    pgl, pgg = movers(pg, a.rank_by, a.top_n, True)
    srl, srg = movers(sr, a.rank_by, a.top_n, False)
    comp = competing(A, B, a.min_page_impr, a.include_brand_competing)
    n_comp = comp['query'].nunique()
    n_comp_a = comp.loc[comp['n_a'] >= 2, 'query'].nunique()
    n_comp_b = comp.loc[comp['n_b'] >= 2, 'query'].nunique()

    sheets = {}
    # ---- Summary
    rows = [['Metric', f'Period A ({a.a_start} to {a.a_end})', f'Period B ({a.b_start} to {a.b_end})', 'Change', '% change']]
    for k in ta:
        rows.append([k, ta[k], tb[k], tb[k] - ta[k], pct(ta[k], tb[k])])
    status_rows = []
    if crawl is not None:
        pg['cls'] = pg['status']
        s = pg.groupby('cls').agg(pages=('page', 'count'), ni_a=('ni_a', 'sum'), nc_a=('nc_a', 'sum'),
                                  ni_b=('ni_b', 'sum'), nc_b=('nc_b', 'sum')).reset_index()
        s = s.sort_values('ni_a', ascending=False)
        tot_ni_a, tot_nc_a = pg['ni_a'].sum(), pg['nc_a'].sum()
        status_rows.append(['Search Console pages by crawl status', 'Pages', 'Non-brand impressions A',
                            'Share of A', 'Non-brand clicks A', 'Non-brand impressions B', 'Non-brand clicks B'])
        for _, r in s.iterrows():
            status_rows.append([r['cls'], r['pages'], r['ni_a'], (r['ni_a'] / tot_ni_a) if tot_ni_a else '',
                                r['nc_a'], r['ni_b'], r['nc_b']])
    notes = [
        ['How to read this'],
        [f'Period A is the earlier period, period B the later one. Change = B minus A. Brand terms used: {", ".join(brand) or "none"}.'],
        ['Clicks and impressions are the sum of the listed page + query rows. Search Console withholds rare searches from '
         'page + query exports, so totals can be lower than the Performance report.'],
        ['Pages and Searches are ranked by non-brand ' + a.rank_by + f' change; the top {a.top_n} losses and gains are listed. '
         'Searches lists non-brand searches only.'],
        ['This workbook reports what changed and what it affected. It does not explain why (no migration, site change, '
         'algorithm or seasonality detection).'],
    ]
    if crawl is None:
        notes.append(['No crawl was supplied, so the status of each URL is not known. The Pages tab lists the losing '
                      'URLs; check each one returns 200.'])
    else:
        notes.append(['"Not in crawl" means the crawler did not reach the URL: it is not linked from the site and not in the '
                      'sitemap. That is not proof it is dead; check it returns 200.'])
    sheets['Summary'] = (rows, status_rows, notes)

    # ---- Pages
    head = ['Direction', 'Page', 'Status' if crawl is not None else None,
            'Non-brand impr A', 'Non-brand impr B', 'Change', 'Non-brand clicks A', 'Non-brand clicks B', 'Change',
            'All impr A', 'All impr B', 'All clicks A', 'All clicks B']
    keep = [i for i, h in enumerate(head) if h]
    def prow(d, r):
        row = [d, r['page'], r['status'], r['ni_a'], r['ni_b'], r['ni_d'], r['nc_a'], r['nc_b'], r['nc_d'],
               r['i_a'], r['i_b'], r['c_a'], r['c_b']]
        return [row[i] for i in keep]
    prows = [[head[i] for i in keep]]
    prows += [prow('Loss', r) for _, r in pgl.iterrows()] + [prow('Gain', r) for _, r in pgg.iterrows()]
    sheets['Pages'] = prows

    # ---- Searches
    shead = ['Direction', 'Search', 'Impr A', 'Impr B', 'Change', 'Clicks A', 'Clicks B', 'Change',
             'Pages A', 'Pages B', 'Avg position A', 'Avg position B']
    def srow(d, r):
        return [d, r['query'], r['i_a'], r['i_b'], r['i_d'], r['c_a'], r['c_b'], r['c_d'],
                r['pages_a'], r['pages_b'], r0(r['pos_a']), r0(r['pos_b'])]
    sheets['Searches'] = [shead] + [srow('Loss', r) for _, r in srl.iterrows()] + \
                         [srow('Gain', r) for _, r in srg.iterrows()]

    # ---- Pages behind the losing searches
    pq = A.merge(B, on=['page', 'query'], how='outer', suffixes=('_a', '_b'))
    for c in ('clicks_a', 'impr_a', 'clicks_b', 'impr_b'):
        pq[c] = pq[c].fillna(0)
    bhead = ['Losing search', 'Page'] + (['Status'] if crawl is not None else []) + \
            ['Impr A', 'Impr B', 'Change', 'Clicks A', 'Clicks B', 'Avg position A', 'Avg position B']
    brows = [bhead]
    for q in srl['query']:
        sub = pq[pq['query'] == q].sort_values(['impr_a', 'impr_b'], ascending=False)
        for _, r in sub.iterrows():
            brows.append([q, r['page']] + ([status_class(crawl.get(r['page']))] if crawl is not None else []) +
                         [r['impr_a'], r['impr_b'], r['impr_b'] - r['impr_a'], r['clicks_a'], r['clicks_b'],
                          r0(r['pos_a']), r0(r['pos_b'])])
    sheets['Pages behind searches'] = brows

    # ---- Competing pages
    chead = ['Search', 'Competing in', 'Page'] + (['Status'] if crawl is not None else []) + \
            ['Impr A', 'Clicks A', 'Avg position A', 'Impr B', 'Clicks B', 'Avg position B']
    crows = [chead]
    top_q = list(dict.fromkeys(comp['query']))[:a.top_n]
    for q in top_q:
        for _, r in comp[comp['query'] == q].iterrows():
            crows.append([q, r['where'], r['page']] + ([status_class(crawl.get(r['page']))] if crawl is not None else []) +
                         [r['impr_a'], r['clicks_a'], r0(r['pos_a']), r['impr_b'], r['clicks_b'], r0(r['pos_b'])])
    sheets['Competing pages'] = crows
    comp_note = (f'Searches with 2+ pages that each have at least {a.min_page_impr:g} impressions: {n_comp} '
                 f'({n_comp_a} in period A, {n_comp_b} in period B). The {min(n_comp, a.top_n)} with the most impressions are listed.'
                 + ('' if a.include_brand_competing else ' Brand searches are left out.'))

    # ---- What to run next
    nxt = [['Audit', 'Evidence', 'Rule', 'Suggested']]
    nxt.append(['Content Prune & Merge', comp_note,
                f'Suggested when {a.prune_if} or more searches have competing pages',
                'Yes' if n_comp >= a.prune_if else 'No'])
    if crawl is not None:
        live = pg['status'] == '200 OK'
        tot = pg['ni_a'].sum()
        off = pg.loc[~live, 'ni_a'].sum()
        off_c = pg.loc[~live, 'nc_a'].sum()
        share = (off / tot * 100) if tot else 0
        nxt.append(['Information architecture audit',
                    f'{off:,.0f} of {tot:,.0f} period A non-brand impressions ({share:.0f}%) and {off_c:,.0f} of '
                    f'{pg["nc_a"].sum():,.0f} non-brand clicks are on URLs that did not return 200 in the crawl or were not in it.',
                    f'Suggested when {a.dead_share_pct}% or more of period A non-brand impressions are on URLs not returning 200',
                    'Yes' if share >= a.dead_share_pct else 'No'])
        l200 = pg.loc[live]
        nxt.append(['Backlink audit',
                    f'Non-brand impressions on URLs that return 200: {l200["ni_a"].sum():,.0f} in A, {l200["ni_b"].sum():,.0f} in B '
                    f'(change {l200["ni_d"].sum():,.0f}); non-brand clicks {l200["nc_a"].sum():,.0f} to {l200["nc_b"].sum():,.0f}.',
                    'No rule: a drop on pages that are still live is not explained by dead URLs. Ask the person.',
                    'Ask the person'])
    else:
        nxt.append(['Information architecture audit',
                    'No crawl was supplied, so dead URLs cannot be counted. The URLs on the Pages tab need checking.',
                    'Needs a crawl that includes the Search Console URLs', 'Ask the person'])
        nxt.append(['Backlink audit', f'Non-brand impressions changed from {ta["Impressions (non-brand)"]:,.0f} to '
                    f'{tb["Impressions (non-brand)"]:,.0f}. Whether the loss is on live pages is unknown without a crawl.',
                    'No rule. Ask the person.', 'Ask the person'])
    nxt.append(['Service gap audit', 'Triage cannot tell what the client sells.',
                'Only built for med spa and plastic surgery sites. Ask the person what the client offers.',
                'Ask the person'])
    sheets['What to run next'] = nxt

    # ---- write
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    wb.remove(wb.active)
    bold = Font(bold=True, color='FFFFFF')
    fill = PatternFill('solid', fgColor='305496')

    def put(ws, rows, start=1):
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                ws.cell(row=start + i, column=j + 1, value=v)
        return start + len(rows)

    def style_head(ws, row):
        for c in ws[row]:
            if c.value is not None:
                c.font, c.fill = bold, fill
                c.alignment = Alignment(wrap_text=True, vertical='top')

    s_rows, s_status, s_notes = sheets['Summary']
    ws = wb.create_sheet('Summary')
    nxt_row = put(ws, [[f'{a.client}: Search Console triage, period A vs period B']], 1)
    ws['A1'].font = Font(bold=True, size=14)
    top = put(ws, s_rows, 3)
    style_head(ws, 3)
    for r in range(4, top):
        ws.cell(row=r, column=5).number_format = '0.0%'
    cur = top + 1
    if s_status:
        put(ws, s_status, cur)
        style_head(ws, cur)
        for r in range(cur + 1, cur + len(s_status)):
            ws.cell(row=r, column=4).number_format = '0.0%'
        cur += len(s_status) + 1
    put(ws, s_notes, cur)
    ws.cell(row=cur, column=1).font = Font(bold=True)
    for r in range(cur + 1, cur + len(s_notes)):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[r].height = 45
    ws.column_dimensions['A'].width = 38
    for col in 'BCDEFG':
        ws.column_dimensions[col].width = 22

    for name in ('Pages', 'Searches', 'Pages behind searches', 'Competing pages', 'What to run next'):
        ws = wb.create_sheet(name)
        rows = sheets[name]
        if name == 'Competing pages':
            put(ws, [[comp_note]], 1)
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=8)
            ws['A1'].alignment = Alignment(wrap_text=True, vertical='top')
            ws.row_dimensions[1].height = 45
            put(ws, rows, 3)
            style_head(ws, 3)
            ws.freeze_panes = 'A4'
        else:
            put(ws, rows, 1)
            style_head(ws, 1)
            ws.freeze_panes = 'A2'
        for j in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(j)].width = 60 if (j <= 3 and name != 'What to run next') else 16
        if name == 'What to run next':
            for col, w in zip('ABCD', (30, 80, 55, 16)):
                ws.column_dimensions[col].width = w
            for row in ws.iter_rows(min_row=2):
                for c in row:
                    c.alignment = Alignment(wrap_text=True, vertical='top')
    wb.save(a.out)
    return {'summary_a': ta, 'summary_b': tb, 'pages_loss': len(pgl), 'pages_gain': len(pgg),
            'searches_loss': len(srl), 'searches_gain': len(srg), 'competing_queries': n_comp,
            'competing_a': n_comp_a, 'competing_b': n_comp_b,
            'next': {r[0]: r[3] for r in nxt[1:]}}


def cmd_build(a):
    for k in ('a_start', 'a_end', 'b_start', 'b_end'):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', getattr(a, k)):
            sys.exit(f'--{k.replace("_", "-")} must be YYYY-MM-DD')
    if a.a_start > a.a_end or a.b_start > a.b_end:
        sys.exit('A period starts after it ends.')
    if a.a_start >= a.b_start:
        sys.exit('Period A must start before period B (A is the earlier period). Swap the sheets or dates.')
    domain, brand, (A, fa, ta_), (B, fb, tb_) = periods(a)
    crawl = load_crawl(a.crawl, domain) if a.crawl else None
    res = write_workbook(a, domain, brand, A, B, crawl)
    for tag, f in (('A', fa), ('B', fb)):
        if f:
            print(f'WARNING: period {tag} has {len(f)} pages not on {domain}, kept under their full URL.')
    if not brand:
        print('WARNING: no brand terms, so total and non-brand figures are the same.')
    print(f'Period A tab "{ta_}", period B tab "{tb_}".')
    for k in ('Clicks (all searches)', 'Impressions (all searches)', 'Clicks (non-brand)', 'Impressions (non-brand)'):
        print(f'  {k}: {res["summary_a"][k]:,.0f} -> {res["summary_b"][k]:,.0f}')
    print(f'Pages: {res["pages_loss"]} losses, {res["pages_gain"]} gains listed. Searches: {res["searches_loss"]} losses, '
          f'{res["searches_gain"]} gains listed.')
    print(f'Competing searches: {res["competing_queries"]} ({res["competing_a"]} in A, {res["competing_b"]} in B).')
    print(f'Next-step suggestions: {res["next"]}')
    print(f'Wrote {a.out}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('profile', 'build'):
        p = sub.add_parser(name)
        p.add_argument('--domain', required=True)
        p.add_argument('--brand', default='')
        p.add_argument('--a', required=True)
        p.add_argument('--a-tab')
        p.add_argument('--b', required=True)
        p.add_argument('--b-tab')
        p.add_argument('--crawl')
    b = sub.choices['build']
    b.add_argument('--client', required=True)
    for k in ('a-start', 'a-end', 'b-start', 'b-end'):
        b.add_argument(f'--{k}', required=True)
    b.add_argument('--min-page-impr', type=float, required=True)
    b.add_argument('--top-n', type=int, required=True)
    b.add_argument('--prune-if', type=int, required=True)
    b.add_argument('--dead-share-pct', type=float, required=True)
    b.add_argument('--rank-by', choices=('impressions', 'clicks'), default='impressions')
    b.add_argument('--include-brand-competing', action='store_true')
    b.add_argument('--out', required=True)
    a = ap.parse_args()
    {'profile': cmd_profile, 'build': cmd_build}[a.cmd](a)


if __name__ == '__main__':
    main()
