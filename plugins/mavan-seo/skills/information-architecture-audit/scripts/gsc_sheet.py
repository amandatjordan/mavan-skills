#!/usr/bin/env python3
"""Build the Search Console tables for the IA audit from the Google Sheet of GSC data.

No Composio and no API calls: the sheet is the only source. The sheet is a page + query export
(columns Page, Query, Clicks, Impressions, and optionally CTR and Position), the same sheet the
Service Page Title/H1 Review uses. It is an .xlsx download of the Google Sheet or the text export
(each tab starts with a '## Sheet name: NAME' line followed by CSV).

Usage:
  python gsc_sheet.py build --sheet GSC.xlsx --domain example.com --brand "example,nickname" \
        --start 2026-04-01 --end 2026-09-30 [--tab NAME] [--out work/gsc] \
        [--ga4-property properties/123] [--site-label "Google Sheet"]
  python gsc_sheet.py pair-queries --pairs 3:17,4:9 [--out work/gsc]

`build` writes meta.csv, pages.csv, pairs.csv, noowner.csv, home.csv (same layout analyze.py has always
read) plus _q_pages.json for `pair-queries`. If work/gsc/ga4.csv exists (see references/ga4.md) its
sessions and key events are merged into pages.csv.

What a sheet cannot give: Search Console withholds rare ("anonymized") queries from page + query
exports, so a page's clicks and impressions here are the sum of its listed queries and can be lower
than the Performance report's page totals. The meta table says so and fill.py puts it in the Read Me.
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, key as ia_key  # noqa: E402

GSC_TAB = 'Claude Use This'  # the tab of Mavan's Search Console template that is used when it exists
GSC_COLS = {'page': ('page', 'landing page', 'url', 'address', 'top pages'),
            'query': ('query', 'top queries', 'search query'),
            'clicks': ('clicks',), 'impressions': ('impressions',)}
OPT_COLS = {'position': ('position', 'average position', 'avg. position')}
NOOWNER_MIN_IMPR = 100  # a search must reach this many impressions to be listed as having no owner page


def to_num(x):
    try:
        return float(str(x).replace(',', '').replace('%', '').strip() or 0)
    except ValueError:
        return None


def clean(s):
    return re.sub(r'[|\r\n\t]+', ' ', str(s)).strip()


def read_tabs(path):
    """-> {tab name: [(page, query, clicks, impressions, position or None)]} for every tab that has the
    Page, Query, Clicks and Impressions columns in its first 10 rows."""
    raw = {}
    if path.lower().endswith(('.xlsx', '.xlsm', '.xls')):
        for name, df in pd.read_excel(path, sheet_name=None, dtype=str, header=None).items():
            raw[name] = df.fillna('').values.tolist()
    else:
        name = '(file)'
        with open(path, encoding='utf-8-sig', newline='') as fh:
            for line in fh:
                if line.startswith('## Sheet name:'):
                    name = line.split(':', 1)[1].strip()
                    raw[name] = []
                elif line.strip():
                    raw.setdefault(name, []).append(next(csv.reader([line])))
    tabs = {}
    for name, rows in raw.items():
        for hi, row in enumerate(rows[:10]):
            cells = [str(c).strip().lower() for c in row]
            idx = {k: next((cells.index(n) for n in names if n in cells), None) for k, names in GSC_COLS.items()}
            if any(v is None for v in idx.values()):
                continue
            pos = next((cells.index(n) for n in OPT_COLS['position'] if n in cells), None)
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
            sys.exit(f"--tab '{tab}' is not a tab with those columns. Tabs: {{ {', '.join(tabs)} }}")
        return tab
    named = next((n for n in tabs if n.strip().lower() == GSC_TAB.lower()), None)
    if named:
        return named
    if len(tabs) == 1:
        return next(iter(tabs))
    listing = '; '.join(f"'{n}' ({len(r)} rows)" for n, r in tabs.items())
    sys.exit(f'{path} has several tabs with GSC columns: {listing}. Ask the person which tab to use, then re-run '
             f'with --tab NAME (or name the tab "{GSC_TAB}"). Never add the tabs together.')


def write_csv(path, head, rows):
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(head)
        w.writerows(rows)


def build(a):
    domain = bare_domain(a.domain)
    brand = [t.strip().lower() for t in a.brand.split(',') if t.strip()]
    is_brand = lambda q: any(t in q.lower() for t in brand)
    tabs = read_tabs(a.sheet)
    use = pick_tab(tabs, a.tab, a.sheet)
    rows = tabs[use]
    os.makedirs(a.out, exist_ok=True)

    # URLs from another domain or subdomain are kept under their full URL (ia_key does that), so the sheet
    # of one client never silently mixes in another site's pages. Report how many are not this domain.
    foreign = {p for p, *_ in rows if domain not in re.sub(r'^https?://(www\.)?', '', p.lower()).split('/')[0]}
    pages = defaultdict(lambda: {'c': 0.0, 'i': 0.0, 'pw': 0.0, 'pi': 0.0, 'tq': '', 'tqi': 0.0, 'nb': 0.0,
                                 's': 0.0, 'ke': 0.0})
    pq = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])  # (key, query) -> clicks, impr, pos*impr, impr with a position
    utm = defaultdict(lambda: [0.0, 0.0])
    raw_clicks = raw_impr = 0.0
    for page, q, c, i, pos in rows:
        k = ia_key(page, domain)
        p = pages[k]
        p['c'] += c; p['i'] += i
        if pos is not None:
            p['pw'] += pos * i; p['pi'] += i
        raw_clicks += c; raw_impr += i
        if '?' in page and k == '/':
            utm[page][0] += c; utm[page][1] += i
        a_ = pq[(k, q.lower())]
        a_[0] += c; a_[1] += i
        if pos is not None:
            a_[2] += pos * i; a_[3] += i

    q_pages = defaultdict(dict)  # non-brand query -> {key: impressions}
    page_nb = defaultdict(float)
    brand_impr = 0.0
    for (k, q), (c, i, pw, pi) in pq.items():
        if is_brand(q):
            brand_impr += i
            continue
        q_pages[q][k] = q_pages[q].get(k, 0) + i
        page_nb[k] += i
        if i > pages[k]['tqi']:
            pages[k]['tq'], pages[k]['tqi'] = q, i
    for k, v in page_nb.items():
        pages[k]['nb'] = v

    ga4_path = os.path.join(a.out, 'ga4.csv')
    ga4_rows = 0
    if os.path.exists(ga4_path):
        g = pd.read_csv(ga4_path, keep_default_na=False)
        for r in g.itertuples():
            k = ia_key(str(r.key), domain)
            pages[k]['s'] += float(r.sessions or 0)
            pages[k]['ke'] += float(r.key_events or 0)
            ga4_rows += 1

    keys = sorted(pages, key=lambda k: (-pages[k]['i'], -pages[k]['s'], k))
    pid = {k: n for n, k in enumerate(keys)}

    # pair overlap: per shared query take the smaller of the two pages' impressions;
    # score = that total / the smaller page's non-brand query impressions. The homepage has its own table.
    pair = defaultdict(lambda: [0.0, 0])
    for q, pm in q_pages.items():
        top = sorted(((k, v) for k, v in pm.items() if k != '/'), key=lambda x: (-x[1], x[0]))[:25]
        for x in range(len(top)):
            for y in range(x + 1, len(top)):
                (ka, va), (kb, vb) = top[x], top[y]
                kk = (ka, kb) if pid[ka] < pid[kb] else (kb, ka)
                acc = pair[kk]
                acc[0] += min(va, vb); acc[1] += 1
    pairs = []
    for (x, y), (shared, n) in pair.items():
        denom = min(page_nb.get(x, 0), page_nb.get(y, 0))
        if denom > 0 and n >= 2 and shared / denom >= 0.30:
            pairs.append([pid[x], pid[y], round(shared / denom, 3), n, int(shared)])
    pairs.sort(key=lambda r: (-r[4], r[0], r[1]))

    # searches with no owner: 3+ pages show for it, no page gets half its impressions, and it reaches
    # NOOWNER_MIN_IMPR impressions in the window
    noowner = []
    for q, pm in q_pages.items():
        tot = sum(pm.values())
        if len(pm) >= 3 and tot >= NOOWNER_MIN_IMPR and max(pm.values()) / tot < 0.5:
            top = sorted(pm.items(), key=lambda x: (-x[1], x[0]))[:6]
            noowner.append([clean(q), int(tot), len(pm), ';'.join(f'{pid[k]}:{int(v)}' for k, v in top)])
    noowner.sort(key=lambda r: (-r[1], r[0]))
    noowner = noowner[:150]

    # pages that share 60%+ of their non-brand query impressions with the homepage
    home_top = sorted(((q, pm['/']) for q, pm in q_pages.items() if '/' in pm), key=lambda x: (-x[1], x[0]))[:10]
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
    home.sort(key=lambda r: (-r[3], r[0]))

    page_tab = []
    for k in keys:
        p = pages[k]
        pos = round(p['pw'] / p['pi'], 1) if p['pi'] else ''
        page_tab.append([pid[k], k, int(p['c']), int(p['i']), pos, clean(p['tq'])[:80], int(p['tqi']),
                         int(p['nb']), int(p['s']), int(p['ke'])])

    note = ("Source: the Google Sheet of Search Console page + query rows (tab '%s'), not the API. Search Console "
            "withholds rare queries from page + query exports, so page clicks and impressions are the sum of the "
            "listed queries and can be lower than the Performance report." % use)
    meta = [
        ['site_url', f'Google Sheet, tab "{use}"'], ['domain', domain], ['source', 'sheet'],
        ['window_start', a.start or 'not given'], ['window_end', a.end or 'not given'],
        ['window_note', 'Dates as stated by the person who supplied the sheet.' if a.start else
         'The sheet does not say which dates it covers; ask the person and note it.'],
        ['clicks', int(raw_clicks)], ['impressions', int(raw_impr)],
        ['page_rows', len(pages)], ['page_query_rows', len(rows)],
        ['brand_terms', ', '.join(brand)], ['brand_query_impr', int(brand_impr)],
        ['ga4_property', a.ga4_property if ga4_rows else ''], ['ga4_rows', ga4_rows],
        ['sheet_note', note], ['other_domain_urls', len(foreign)],
        ['home_top_queries', '; '.join(f'{clean(q)} ({int(i)})' for q, i in home_top)],
    ] + [['utm_home', f'{clean(u)} ({int(v[0])} clicks, {int(v[1])} impr)']
         for u, v in sorted(utm.items(), key=lambda x: (-x[1][0], x[0]))[:5]]
    write_csv(os.path.join(a.out, 'meta.csv'), ['key', 'value'], meta)
    write_csv(os.path.join(a.out, 'pages.csv'),
              ['id', 'key', 'clicks', 'impressions', 'position', 'top_query', 'top_query_impr',
               'nonbrand_query_impr', 'ga4_sessions', 'ga4_key_events'], page_tab)
    write_csv(os.path.join(a.out, 'pairs.csv'), ['id_a', 'id_b', 'overlap', 'shared_queries', 'shared_impr'], pairs)
    write_csv(os.path.join(a.out, 'noowner.csv'), ['query', 'impressions', 'pages', 'top_pages'], noowner)
    write_csv(os.path.join(a.out, 'home.csv'),
              ['id', 'share_on_home_queries', 'shared_queries', 'nonbrand_query_impr'], home)
    with open(os.path.join(a.out, '_q_pages.json'), 'w') as fh:
        json.dump({'q': {q: {str(pid[k]): v for k, v in pm.items()} for q, pm in q_pages.items()}}, fh)
    print(f"Loaded tab '{use}': {len(rows)} page+query rows, {len(pages)} pages, {int(raw_clicks)} clicks, "
          f"{int(raw_impr)} impressions. Brand terms: {', '.join(brand) or 'none given'} "
          f"({int(brand_impr)} brand impressions left out of query analysis).")
    print(f'pairs: {len(pairs)}, searches with no owner page: {len(noowner)}, pages sharing the homepage\'s searches: {len(home)}')
    if foreign:
        print(f'WARNING: {len(foreign)} URL(s) in the sheet are not on {domain} (kept under their full URL), '
              f'for example {sorted(foreign)[0]}. Check the sheet is for this client.')
    if not a.start or not a.end:
        print('WARNING: no --start/--end given. Ask the person which dates the sheet covers.')
    if ga4_rows:
        print(f'GA4: merged {ga4_rows} landing pages from ga4.csv')


def pair_queries(a):
    path = os.path.join(a.out, '_q_pages.json')
    if not os.path.exists(path):
        sys.exit(f'{path} not found: run `gsc_sheet.py build` first.')
    d = json.load(open(path))
    out = []
    for spec in a.pairs.split(','):
        x, y = spec.strip().split(':')
        shared = [(min(pm[x], pm[y]), q) for q, pm in d['q'].items() if x in pm and y in pm]
        top = '; '.join(clean(q)[:60] for _, q in sorted(shared, key=lambda t: (-t[0], t[1]))[:a.n])
        out.append([x, y, top])
    f = os.path.join(a.out, 'pair_queries.csv')
    old = []
    if os.path.exists(f):
        old = [r for r in csv.reader(open(f, encoding='utf-8'))][1:]
    seen = {(r[0], r[1]) for r in out}
    write_csv(f, ['id_a', 'id_b', 'top_shared'], [r for r in old if (r[0], r[1]) not in seen] + out)
    print(f'pair_queries.csv: {len(out)} pair(s) added or refreshed')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--sheet', required=True)
    b.add_argument('--domain', required=True)
    b.add_argument('--brand', default='')
    b.add_argument('--start')
    b.add_argument('--end')
    b.add_argument('--tab')
    b.add_argument('--out', default='work/gsc')
    b.add_argument('--ga4-property', default='')
    p = sub.add_parser('pair-queries')
    p.add_argument('--pairs', required=True, help='id_a:id_b,id_a:id_b (page ids from pages.csv)')
    p.add_argument('--n', type=int, default=3)
    p.add_argument('--out', default='work/gsc')
    a = ap.parse_args()
    build(a) if a.cmd == 'build' else pair_queries(a)


if __name__ == '__main__':
    main()
