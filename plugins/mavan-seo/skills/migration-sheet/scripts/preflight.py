#!/usr/bin/env python3
"""Preflight for the migration sheet: are the inputs the right kind, is anything in the audit workbooks still unresolved, and
what exactly will be read? Run it first, in both passes. It prints PASS / FAIL / INFO lines, ends with the "what I read"
summary the person confirms, and writes work/preflight.md. Exit code 1 when anything FAILs: the build does not start.

Usage:
  python preflight.py --domain example.com --urls URLS.csv --links LINKS.csv --backlinks BACKLINKS.csv --gsc GSC.xlsx \
      --prune PRUNE.xlsx --ia IA.xlsx [--gap GAP.xlsx] [--redirects REDIRECTS.csv] [--working-copy SHEET.xlsx] [--out work]

Blocks on unresolved cells in the audit workbooks (a filled Disagree cell, a Needs discussion row with no answer, a blank or
"SEO fill in" target, an empty Service Gap Next Steps). The SEO fixes them in the audit workbook and uploads it again.
Never makes a live request.
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, is_media, key, read_table, workbook_tabs  # noqa: E402
import import_audits as ia  # noqa: E402

lines = []


def add(level, msg):
    lines.append((level, msg))


def col(df, *names):
    low = {str(c).strip().lower(): c for c in df.columns}
    return next((low[n] for n in names if n in low), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domain', required=True)
    for n in ('urls', 'links', 'backlinks', 'gsc', 'prune', 'ia', 'gap', 'redirects', 'working-copy'):
        ap.add_argument('--' + n)
    ap.add_argument('--out', default='work')
    a = ap.parse_args()
    dom = bare_domain(a.domain)
    seen = []

    def need(name, path):
        if not path:
            add('FAIL', f'{name}: not provided.')
            return False
        if not os.path.exists(path):
            add('FAIL', f'{name}: {path} does not exist.')
            return False
        return True

    # ---- crawl URL export
    if need('Crawl URL export', a.urls):
        try:
            u = pd.read_csv(a.urls, encoding='utf-8-sig', dtype=str, keep_default_na=False, low_memory=False)
            uc, sc, tc = col(u, 'url', 'address'), col(u, 'http status code', 'status code'), col(u, 'title 1', 'title')
            if not uc or not sc:
                add('FAIL', f'Crawl URL export: needs a URL (or Address) and a status code column. Columns: {list(u.columns)[:12]}')
            else:
                ok = u[u[sc].str.strip() == '200']
                ok = ok[~ok[uc].map(lambda x: is_media(key(x, dom)))]
                with_title = int((ok[tc].str.strip() != '').sum()) if tc else 0
                if len(ok) == 0:
                    add('FAIL', 'Crawl URL export: no page with status 200. Is this the right export, and is --domain right?')
                elif len(ok) >= 5 and (not tc or with_title / len(ok) < 0.2):
                    add('FAIL', f'Crawl URL export: {len(ok)} pages return 200 but almost none has a title. The crawl looks empty or blocked.')
                else:
                    inside = sum(1 for x in u[uc] if key(x, dom).startswith('/'))
                    if inside < 0.5 * len(u):
                        add('FAIL', f'Crawl URL export: most URLs are not on {dom}. Check --domain.')
                    else:
                        add('PASS', f'Crawl URL export: {len(u)} URLs, {len(ok)} pages with status 200.')
                        seen.append(f'Crawl URL export: {os.path.basename(a.urls)} ({len(u)} URLs)')
        except Exception as e:  # noqa: BLE001
            add('FAIL', f'Crawl URL export: could not read ({e}).')
    # ---- links export
    if need('Internal links export', a.links):
        try:
            h = pd.read_csv(a.links, encoding='utf-8-sig', dtype=str, nrows=5)
            cols = {c.strip().lower() for c in h.columns}
            if {'linking url', 'target url'} <= cols or {'source', 'destination'} <= cols:
                add('PASS', 'Internal links export: columns recognised.')
                seen.append(f'Internal links export: {os.path.basename(a.links)}')
            else:
                add('FAIL', f'Internal links export: no Linking URL / Target URL (Sitebulb) or Source / Destination (Screaming Frog). Columns: {list(h.columns)[:10]}')
        except Exception as e:  # noqa: BLE001
            add('FAIL', f'Internal links export: could not read ({e}).')
    if a.redirects:
        add('INFO', f'Redirects export: {os.path.basename(a.redirects)} (optional) will be read.' if os.path.exists(a.redirects)
            else f'FAIL: redirects export {a.redirects} does not exist.')
    # ---- backlinks
    if need('Backlink export', a.backlinks):
        try:
            b = read_table(a.backlinks)
            if not col(b, 'target url', 'target'):
                add('FAIL', f'Backlink export: no Target URL column. Columns: {list(b.columns)[:10]}')
            elif len(b) == 0:
                add('FAIL', 'Backlink export: no rows.')
            else:
                add('PASS', f'Backlink export: {len(b)} backlinks.')
                seen.append(f'Backlink export: {os.path.basename(a.backlinks)} ({len(b)} backlinks)')
        except Exception as e:  # noqa: BLE001
            add('FAIL', f'Backlink export: could not read ({e}).')
    # ---- Search Console sheet
    if need('Search Console sheet', a.gsc):
        try:
            tabs = pd.read_excel(a.gsc, sheet_name=None, dtype=str, header=None)
            good = [n for n, d in tabs.items() if any({'page', 'impressions'} <= {str(c).strip().lower() for c in r} for r in d.fillna('').head(10).values.tolist())]
            if good:
                add('PASS', f'Search Console sheet: tab {good[0]!r} has Page and Impressions.')
                seen.append(f'Search Console sheet: {os.path.basename(a.gsc)} (tab {good[0]})')
            else:
                add('FAIL', 'Search Console sheet: no tab has Page and Impressions columns.')
        except Exception as e:  # noqa: BLE001
            add('FAIL', f'Search Console sheet: could not read ({e}).')
    # ---- audit workbooks
    read, bad, summary = [], [], []
    for name, path, fn in (('Content Prune & Merge workbook', a.prune, ia.read_prune), ('IA audit workbook', a.ia, ia.read_ia),
                           ('Service Gap workbook', a.gap, ia.read_gap)):
        if name.startswith('Service') and not path:
            add('INFO', 'Service Gap workbook: not provided (only med spa and plastic surgery sites have one).')
            continue
        if not need(name, path):
            continue
        try:
            data, b, r = fn(path, dom)
            read += r
            bad += b
            add('PASS' if not b else 'FAIL', f'{name}: {len(r)} tab(s) read' + ('' if not b else f', {len(b)} unresolved cell(s) below'))
            if name.startswith('Content'):
                summary.append(f"{len(data['keep'])} pages kept, {len(data['merge'])} merged, {len(data['remove'])} removed, "
                               f"{len(data['wildcards'])} wildcard rule(s), {len(data['update'])} with a new title or H1 (Content Prune)")
            elif name.startswith('IA'):
                summary.append(f"{len(data['moves'])} moves to a new URL (IA audit)")
            else:
                summary.append(f"{len(data['new_pages'])} new pages (Service Gap)")
        except SystemExit as e:
            add('FAIL', f'{name}: {e}')
    for b in bad:
        add('FAIL', f"Unresolved: {b['file']} / {b['tab']}: {b['page']} - {b['problem']}")
    if a.working_copy:
        if need('Working copy of the migration sheet', a.working_copy):
            T = workbook_tabs(a.working_copy)
            miss = [t for t in ('Pages to redirect', 'Media with backlinks', 'Final menu and nav') if t not in T]
            add('FAIL' if miss else 'PASS', f'Working copy: missing the tab(s) {miss}.' if miss else 'Working copy: the pass 1 tabs are there.')
    # ---- report
    fails = [m for lv, m in lines if lv == 'FAIL']
    out = ['# Migration sheet preflight', ''] + [f'{lv}: {m}' for lv, m in lines]
    out += ['', '## What I read (confirm this is the right set of files)', ''] + [f'- {s}' for s in seen]
    out += [f"- {x['file']} / {x['tab']}: {x['rows']} rows" for x in read] + [f'- Decisions taken: {s}' for s in summary]
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, 'preflight.md'), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('\n'.join(out))
    if fails:
        print(f'\nSTOPPED: {len(fails)} problem(s). Fix them (audit cells are fixed in the audit workbook) and run preflight again.')
        sys.exit(1)


if __name__ == '__main__':
    main()
