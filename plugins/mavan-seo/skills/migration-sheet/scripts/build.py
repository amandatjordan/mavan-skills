#!/usr/bin/env python3
"""Build the migration sheet content: every decision, the redirect list, the checks. make_xlsx.py writes the workbook.

Usage:
  python build.py --domain example.com --work work                      # template run
  python build.py --domain example.com --work work --working-copy MIGRATION_SHEET.xlsx   # QA check (the SEO's finished copy)

Reads work/ (prep.py, import_audits.py output). Writes work/sheet.json. Exit code 1 when the checks fail:
  template run  only structural problems stop the run (a chain or loop, a target that is not a page that stays, ...). Cells the SEO
          still has to fill in are expected and listed on the Summary tab.
  QA check  anything still open also stops the run, so no final workbook or dev CSV is written until every check passes.
Never makes a live request: every number comes from the uploaded exports.
"""
import argparse
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, cell, col, is_media, is_open, key, table, workbook_tabs  # noqa: E402
from redirects import resolve_all  # noqa: E402

# tab names
ALLP, MENU, MERGE, REDIR, MEDIA, NEWP, DEV, SUMMARY, README = (
    'All pages', 'Final menu and nav', 'Pages to merge', 'Pages to redirect', 'Media with backlinks', 'New pages',
    'Redirects - Handoff to Dev', 'Summary', 'README')
GONE_NOTE = 'Gone'


def csv_or_empty(path, cols):
    return pd.read_csv(path, dtype=str, keep_default_na=False) if os.path.exists(path) else pd.DataFrame(columns=cols)


def read_working_copy(path, dom):
    """What the SEO filled in on the template workbook: redirect targets and Gone reasons, media decisions, new page URLs, the menu."""
    T = workbook_tabs(path)
    seo = {'targets': {}, 'reasons': {}, 'media': {}, 'new_pages': {}, 'new_links': {}, 'menu': [], 'all_pages': {}}
    missing = [t for t in (REDIR, MEDIA, NEWP, MENU) if t not in T and t != NEWP]
    if missing:
        sys.exit(f'{os.path.basename(path)} is missing the tab(s) {missing}. Give the SEO\'s finished copy of the migration sheet (the template, filled in).')
    h, rs = table(T[REDIR])
    for r in rs:
        o = cell(r, 0)
        if not o or '*' in o:
            continue
        k = key(o, dom)
        t, code, why = cell(r, 1), cell(r, 2), cell(r, 3)
        if t.lower().startswith('gone'):
            seo['targets'][k] = 'GONE 410' if '410' in (t + ' ' + code) else 'GONE'
        elif t and not is_open(t):
            seo['targets'][k] = key(t, dom) if t.startswith(('http', '/')) else t
        if why and not is_open(why):
            seo['reasons'][k] = why
    if MEDIA in T:
        h, rs = table(T[MEDIA])
        for r in rs:
            d, n = cell(r, 2).strip().lower(), cell(r, 3)
            seo['media'][key(cell(r, 0), dom)] = {'decision': 'keep' if d.startswith('keep') else 'redirect' if d.startswith('redirect') else '',
                                                  'new': '' if is_open(n) else key(n, dom)}
    if NEWP in T:
        h, rs = table(T[NEWP])
        for r in rs:
            u = cell(r, 1)
            seo['new_pages'][cell(r, 0)] = '' if is_open(u) else key(u, dom)
            seo['new_links'][cell(r, 0)] = [
                {'link': key(cell(r, i), dom) if cell(r, i).startswith(('http', '/')) else cell(r, i),
                 'anchor': '' if is_open(cell(r, i + 1)) else cell(r, i + 1)}
                for i in (3, 5, 7) if cell(r, i) and not is_open(cell(r, i))]
    if ALLP in T:
        h, rs = table(T[ALLP])
        for r in rs:
            note = cell(r, 6)
            # a new page is matched by its Service Gap note (its URL may not be filled in yet), every other page by its final URL
            seo['all_pages'][note if note.startswith('Service Gap:') else cell(r, 0)] = {'type': cell(r, 3), 'title': cell(r, 4), 'h1': cell(r, 5)}
    if MENU in T:
        h, rs = table(T[MENU])
        for r in rs:
            if any(cell(r, i).strip() for i in range(5)):
                seo['menu'].append({'parent': cell(r, 0), 'parent_url': cell(r, 1), 'child': cell(r, 2), 'child_url': cell(r, 3),
                                    'order': cell(r, 4)})
    return seo


def full(dom, k):
    return k if k.startswith('http') else f'https://{dom}{k}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domain', required=True)
    ap.add_argument('--work', default='work')
    ap.add_argument('--working-copy')
    a = ap.parse_args()
    dom = bare_domain(a.domain)
    W = lambda f: os.path.join(a.work, f)
    pass2 = bool(a.working_copy)
    audits = json.load(open(W('audits.json'), encoding='utf-8'))
    pages = csv_or_empty(W('crawl_pages.csv'), ['key', 'status', 'has_query', 'title', 'h1'])
    links = csv_or_empty(W('links.csv'), ['src', 'dst', 'cls'])
    red = csv_or_empty(W('redirects.csv'), ['source', 'status', 'final'])
    bl = csv_or_empty(W('backlinks.csv'), ['key', 'links', 'is_media'])
    gsc = csv_or_empty(W('gsc_pages.csv'), ['key', 'impressions'])
    seo = read_working_copy(a.working_copy, dom) if pass2 else {}

    # ---- the master list of old URLs
    pages['status'] = pd.to_numeric(pages['status'], errors='coerce')
    is_q = pages['has_query'].astype(str).str.lower().eq('true')
    live = {k for k, s, q in zip(pages.key, pages.status, is_q) if s == 200 and not q and k.startswith('/') and not is_media(k)}
    crawl_red = {r.source: r.final for r in red.itertuples() if str(r.final).startswith('/') and str(r.source).startswith('/')
                 and not is_media(r.source)}
    master = {k: {'backlinks': 0, 'impressions': 0, 'media': False} for k in live | set(crawl_red)}
    for r in bl.itertuples():
        m = master.setdefault(r.key, {'backlinks': 0, 'impressions': 0, 'media': False})
        m['backlinks'] += int(r.links)
        m['media'] = str(r.is_media).lower() == 'true'
    for r in gsc.itertuples():
        if not is_media(r.key):
            m = master.setdefault(r.key, {'backlinks': 0, 'impressions': 0, 'media': False})
            m['impressions'] += float(r.impressions)
    new_pages = audits['gap']['new_pages']
    new_urls = {u for u in seo.get('new_pages', {}).values() if u}

    res = resolve_all(master, live, audits, crawl_red, new_urls, seo)
    rows, disc, problems = res['rows'], res['discrepancies'], list(res['problems'])
    old2final = {r['old']: r['final'] for r in rows if r['action'] in ('keep', 'merge', 'redirect') and r['final']}
    gone_set = {r['old'] for r in rows if r['action'] == 'gone'}
    titles = pages.drop_duplicates('key').set_index('key')[['title', 'h1']].to_dict('index')

    # internal links in per page, for the bottom-quartile cutoff shown on the Summary tab
    inl = links.groupby('dst')['src'].nunique().to_dict() if len(links) else {}

    # ---- tabs
    keep_rows, ptype, type_inl = [], {}, []
    upd = audits['prune']['update']
    for r in rows:
        if r['action'] != 'keep':
            continue
        k = r['old']
        t = audits['prune']['keep'].get(k) or audits['ia']['types'].get(k) or ''
        ptype[k] = t
        c = titles.get(k, {'title': '', 'h1': ''})
        u = upd.get(k, {})
        keep_rows.append([r['final'], k if r['final'] != k else '', 'Moved' if r['final'] != k else 'Stays', t,
                          u.get('title') or c['title'], u.get('h1') or c['h1'], ''])
        type_inl.append((t or 'Page type not set', int(inl.get(k, 0))))
    # bottom quartile of internal links in, per page type (needs 4 pages of the type)
    cutoffs, by_type = {}, {}
    for t, n in type_inl:
        by_type.setdefault(t, []).append(n)
    for t, v in sorted(by_type.items()):
        cutoffs[t] = {'pages': len(v), 'cutoff': float(pd.Series(v).quantile(0.25)) if len(v) >= 4 else None}
    merge_rows = [[r['old'], r['final'], audits['prune']['carry'].get(r['old'], '')] for r in rows if r['action'] == 'merge']
    redir_rows = []
    for r in rows:
        if r['action'] in ('merge', 'redirect'):
            redir_rows.append([r['old'], r['final'] or 'SEO fill in', 301, '', r['by'] + (' (merge)' if r['action'] == 'merge' else '')])
        elif r['action'] == 'gone':
            redir_rows.append([r['old'], GONE_NOTE, r['code'], r['reason'] or 'SEO fill in', r['by']])
        elif r['action'] == 'wildcard':
            redir_rows.append([r['old'], r['final'], 301, '', f'{r["by"]} (rule covers {r["covers"]} URLs, counted once)'])
    media_rows = [[m['old'], m['backlinks'], {'keep': 'Keep at the same URL', 'redirect': 'Redirect'}.get(m['decision'], 'SEO fill in'),
                   m['new'] or ('SEO fill in' if m['decision'] == 'redirect' else '')] for m in res['media']]
    def reviewed(row, k):
        e = seo.get('all_pages', {}).get(k)
        if e:
            row[3], row[4], row[5] = e['type'], e['title'], e['h1']
        return row

    keep_rows = [reviewed(r, r[0]) for r in keep_rows]
    keep_rows.sort(key=lambda r: r[0])
    valid_finals = set(res['finals'].values())

    def suggest(n):
        """Up to 3 pages that should link TO the new page: Service Gap's existing related pages first, then pages that name the
        service, each shown at its final URL. Pages that are removed or not on the new site are skipped."""
        out = []
        for c in re.split(r'[;\n]\s*', (n['existing'] or '') + ';' + (n['relevant'] or '')):
            c = c.strip()
            if not c.startswith(('http', '/')):
                continue
            k = key(c, dom)
            f = old2final.get(k, k) if k not in gone_set else None
            if f in valid_finals and f not in out:
                out.append(f)
        return out[:3]

    def new_links(n):
        mine = seo.get('new_links', {}).get(n['name'])
        return (mine or []) if pass2 else [{'link': f, 'anchor': ''} for f in suggest(n)]

    new_rows = []
    for n in new_pages:
        lk = new_links(n)
        row = [n['name'], seo.get('new_pages', {}).get(n['name'], '') or 'SEO fill in', n['keywords']]
        for i in range(3):
            if i < len(lk):
                row += [lk[i]['link'], lk[i]['anchor'] or 'SEO fill in']
            else:
                row += ['', '']
        new_rows.append(row)
        keep_rows.append(reviewed([seo.get('new_pages', {}).get(n['name'], '') or 'SEO fill in', '', 'New page', '', '', '', f"Service Gap: {n['name']}"],
                                  f"Service Gap: {n['name']}"))
    menu_rows = [[m['parent'], m['parent_url'], m['child'], m['child_url'], m['order']] for m in seo.get('menu', [])]

    # ---- developer redirect list (final targets only)
    dev = []
    for r in rows:
        if r['action'] in ('merge', 'redirect') and r['final']:
            dev.append([full(dom, r['old']), full(dom, r['final']), 0, 301])
        elif r['action'] == 'gone' and not r['open']:
            dev.append([full(dom, r['old']), '', 0, r['code']])
        elif r['action'] == 'wildcard':
            p = re.sub(r'^https?://[^/]+', '', r['old']).split('*')[0]
            dev.append([full(dom, p) + '(.*)', full(dom, r['final']), 1, 301])
    for m in res['media']:
        if m['decision'] == 'redirect' and m['new']:
            dev.append([full(dom, m['old']), full(dom, m['new']), 0, 301])

    # ---- checks
    valid = set(res['finals'].values()) | new_urls
    open_redirects = [r['old'] for r in rows if r['open']]
    undecided = [r['old'] for r in rows if r['open'] and r['by'].startswith('No decision')]
    gone_no_reason = [r['old'] for r in rows if r['action'] == 'gone' and not r['reason']]
    media_open = [m['old'] for m in res['media'] if m['decision'] not in ('keep', 'redirect')]
    media_no_url = [m['old'] for m in res['media'] if m['decision'] == 'redirect' and not m['new']]
    new_open, new_bad = [], []
    for n in new_pages:
        lk = new_links(n)
        if not seo.get('new_pages', {}).get(n['name']):
            new_open.append(f"{n['name']} has no URL")
        if not any(x['anchor'] for x in lk):
            new_open.append(f"{n['name']} has no page linking to it with anchor text")
        new_open += [f"{n['name']}: the link from {x['link']} has no anchor text" for x in lk if x['link'] and not x['anchor'] and any(y['anchor'] for y in lk)]
        new_bad += [f"{n['name']}: {x['link']} is set to link to it but is not a page on the new site" for x in lk
                    if x['link'] not in (valid_finals | new_urls)]
    menu_problems = []
    redirect_sources = {r['old'] for r in rows if r['action'] in ('merge', 'redirect', 'gone')}
    for m in seo.get('menu', []):
        if (m['child'] or m['child_url']) and not (m['parent'] or m['parent_url']):
            menu_problems.append(f'Child {m["child"] or m["child_url"]} has no parent')
        for u in (m['parent_url'], m['child_url']):
            if u:
                k = key(u, dom)
                if k in redirect_sources or (k not in valid and k not in set(res['finals'])):
                    menu_problems.append(f'{u} is in the menu but is not a page that stays or a new page')
    menu_open = [] if seo.get('menu') else ['The Final menu and nav tab is empty: the SEO must set the navigation']

    def group(words):
        return [p for p in problems if any(w in p for w in words)]

    checks = [
        ('Every old URL has exactly one decision (keep, merge, redirect or Gone)', group(['twice', 'two different', 'end at', 'new page URL']),
         undecided),
        ('No blank redirect target', [], [f'{o} has no target yet' for o in open_redirects if o not in gone_no_reason]),
        ('Every Gone URL has a reason and a 404 or 410 code', [], [f'{o} is Gone with no reason' for o in gone_no_reason]),
        ('No redirect chains or loops, no redirect to itself', group(['chain', 'loop', 'itself', 'cannot be resolved']), []),
        ('Every redirect target is a page that stays or a new page', group(['not a page that stays']), []),
        ('No kept page or target sits inside a wildcard rule', group(['wildcard']), []),
        ('Every media file with backlinks has an SEO decision, and every redirect has a new URL', [],
         [f'{m} has no decision' for m in media_open] + [f'{m} is set to redirect with no new URL' for m in media_no_url]),
        ('Every new page has a URL and at least one page linking to it with anchor text, and those pages are on the new site', new_bad if pass2 else [], new_open),
        ('Final menu and nav: every URL is a page that stays or a new page, every child has a parent', menu_problems if pass2 else [], menu_open),
    ]
    structural = [p for _, bad, _ in checks for p in bad]
    open_items = [p for _, _, o in checks for p in o]
    result = [{'check': n, 'status': 'FAIL' if bad else ('OPEN' if o and not pass2 else 'FAIL' if o else 'PASS'),
               'detail': '; '.join((bad + o)[:5]) + (f' (+{len(bad + o) - 5} more)' if len(bad + o) > 5 else '')}
              for n, bad, o in checks]
    if pass2 and not menu_problems and seo.get('menu'):
        pass
    sheet = {
        'domain': dom, 'pass': 2 if pass2 else 1, 'counts': res['counts'], 'discrepancies': disc, 'checks': result,
        'cutoffs': cutoffs, 'read': audits['read'], 'tabs': {ALLP: keep_rows, MENU: menu_rows, MERGE: merge_rows, REDIR: redir_rows,
                                                              MEDIA: media_rows, NEWP: new_rows, DEV: dev},
        'open': len(open_items), 'problems': structural + (open_items if pass2 else []),
    }
    os.makedirs(a.work, exist_ok=True)
    json.dump(sheet, open(W('sheet.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    c = res['counts']
    print(f"Pass {sheet['pass']}: {c['keep']} pages stay ({c['moved']} at a new URL), {c['merge']} merged, {c['redirect']} redirected, "
          f"{c['gone']} Gone, {c['wildcard']} wildcard rule(s) covering {c['covered']} URLs, {c['media']} media files with backlinks, "
          f"{len(new_pages)} new pages. {len(disc)} discrepancies listed.")
    for r in result:
        print(f"  {r['status']:<5} {r['check']}" + (f": {r['detail']}" if r['detail'] else ''))
    if structural or (pass2 and open_items):
        print('STOPPED: fix the items above (in the audit workbooks for structural problems, in the migration sheet for open cells).')
        sys.exit(1)


if __name__ == '__main__':
    main()
