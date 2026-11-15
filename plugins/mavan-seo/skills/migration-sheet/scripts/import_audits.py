#!/usr/bin/env python3
"""Read the SEO's working copies of the Content Prune & Merge, IA audit and Service Gap workbooks.

Usage:
  python import_audits.py --domain example.com --prune PRUNE.xlsx --ia IA.xlsx [--gap GAP.xlsx] [--out work]

Tabs are matched by their exact names. Row 1 of each audit tab is a banner, so headers are in row 2; the dev tab has
headers in row 1. A tab the audit left out (it had no rows) is skipped. The SEO's working copy is the approval: a row
still on a tab is part of the plan, and a change the SEO wants is made in the workbook.

Writes work/audits.json:
  prune   keep {key: page type}, merge [{source, target}], remove [{source, target}], update {key: {title, h1}},
          wildcards [{source, target, regex}], carry {source: unique content to copy over}
  ia      moves [{old, new}], types {key: page type}, fix_links, menu [{item, decision}]
  gap     new_pages [{name, url, existing}]
  unresolved  every cell that is still waiting for the SEO (the build is blocked while this list is not empty)
  read    every file and tab used, with row counts
A target of 'GONE' or 'GONE 410' means the SEO chose to remove the URL with no redirect (404, or 410).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, cell, col, is_open, key, table, workbook_tabs  # noqa: E402

KEPT, CPT, DEV, JUNK, LOC = 'Kept pages', 'Check page type', 'All redirects - Handoff to Dev', 'Junk folders', 'Per location service pages'
MERGE, REMOVE, RAM, NEED, DISC, UPD = ('Merge pages', 'Remove pages', 'Redirect after merge', 'Redirects needing a target',
                                       'Needs discussion', 'Update pages')
PRUNE_TABS = {KEPT, JUNK, LOC, MERGE, REMOVE, RAM, NEED, DISC, UPD}  # tabs only the prune workbook has
MOVES, FIX, MENU, IA_README = 'Moves', 'Fix links', 'Menu cleanup', 'README'
IA_TABS = {MOVES, FIX, IA_README}  # tabs only the IA workbook has
REC = 'Recommendations'


def gone(v):
    return str(v).strip().lower().startswith('gone')


def target(v, dom):
    """A redirect target as the audits write it: a URL or path becomes a key; 'Gone' stays as a marker."""
    v = str(v).strip()
    if gone(v):
        return 'GONE 410' if '410' in v else 'GONE'
    return key(v, dom) if (v.startswith('http') or v.startswith('/')) else v


def read_prune(path, dom):
    T = workbook_tabs(path)
    if not set(T) & PRUNE_TABS:
        sys.exit(f'{os.path.basename(path)} has none of the Content Prune & Merge tabs (Kept pages, Remove pages, Merge pages ...). '
                 'Is this the prune workbook? Give the working copy the SEO used.')
    if KEPT not in T and CPT not in T:
        sys.exit(f'{os.path.basename(path)} has neither Kept pages nor Check page type: this looks like the implementer copy of the prune '
                 "workbook, so there is no way to see what the SEO approved. Give the SEO's working copy.")
    out = {'keep': {}, 'merge': [], 'remove': [], 'update': {}, 'wildcards': [], 'carry': {}}
    bad, read = [], []

    def need(tab, page, why):
        bad.append({'file': os.path.basename(path), 'tab': tab, 'page': page, 'problem': why})

    def rows(tab, first=None):
        if tab not in T:
            return None, []
        h, rs = table(T[tab], first)
        read.append({'file': os.path.basename(path), 'tab': tab, 'rows': len(rs)})
        return h, rs

    h, rs = rows(KEPT)
    if h is not None and rs:
        p, t, d = col(h, 'page'), col(h, 'page type'), col(h, 'disagree')
        for r in rs:
            out['keep'][key(cell(r, p), dom)] = cell(r, t)
            if cell(r, d).strip():
                need(KEPT, cell(r, p), f'Disagree cell has a change typed in it ({cell(r, d)[:60]!r}): make the change in the prune workbook first')
    h, rs = rows(CPT)
    for r in rs:
        if cell(r, 2).lower().startswith('seo fill in'):
            need(CPT, cell(r, 0), 'Correct page type is still "SEO fill in"')
    h, rs = rows(DISC)
    for r in rs:
        if is_open(cell(r, 1)):
            need(DISC, cell(r, 0), 'Needs discussion row has no answer recorded in column B')
    for tab in (MERGE, RAM):
        h, rs = rows(tab)
        for r in rs:
            src, tgt = cell(r, 0), cell(r, 1)
            if not src:
                continue
            if is_open(tgt):
                need(tab, src, 'Merge target is blank or "SEO fill in"')
                continue
            if tab == MERGE:
                out['merge'].append({'source': key(src, dom), 'target': target(tgt, dom)})
                if cell(r, 2) and not is_open(cell(r, 2)) and cell(r, 2).lower() != 'none':
                    out['carry'][key(src, dom)] = cell(r, 2)
            elif not any(m['source'] == key(src, dom) for m in out['merge']):
                out['merge'].append({'source': key(src, dom), 'target': target(tgt, dom)})
    h, rs = rows(LOC)
    for r in rs:
        if cell(r, 3).lower().startswith('merge'):
            if is_open(cell(r, 1)):
                need(LOC, cell(r, 0), 'Main page for a Merge row is blank or "SEO fill in"')
            else:
                out['merge'].append({'source': key(cell(r, 0), dom), 'target': target(cell(r, 1), dom)})
                if cell(r, 4) and not is_open(cell(r, 4)) and cell(r, 4).lower() != 'none':
                    out['carry'][key(cell(r, 0), dom)] = cell(r, 4)
        elif not cell(r, 3).strip() or is_open(cell(r, 3)):
            need(LOC, cell(r, 0), 'What to do (Merge or Keep) is blank or "SEO fill in"')
        else:
            out['keep'].setdefault(key(cell(r, 0), dom), 'Service Area / Location')
    for tab in (REMOVE, NEED):
        h, rs = rows(tab)
        for r in rs:
            src, tgt = cell(r, 0), cell(r, 1)
            if not src:
                continue
            if is_open(tgt):
                need(tab, src, 'Redirect target is blank, "SEO fill in" or NEEDS TARGET')
            else:
                out['remove'].append({'source': key(src, dom), 'target': target(tgt, dom)})
    h, rs = rows(JUNK)
    for r in rs:
        if '*' not in cell(r, 0):
            continue
        if is_open(cell(r, 1)):
            need(JUNK, cell(r, 0), 'Junk folder target is blank or "SEO fill in"')
        else:
            out['wildcards'].append({'source': cell(r, 0), 'target': target(cell(r, 1), dom), 'regex': 0})
    h, rs = rows(DEV)
    if h is not None:
        s, t, x = col(h, 'source'), col(h, 'target'), col(h, 'regex')
        for r in rs:
            if cell(r, x).strip() in ('1', '1.0') and cell(r, s):
                src = re.sub(r'\(\.\*\)\$?$', '*', cell(r, s))
                if not any(w['source'] == src for w in out['wildcards']):
                    out['wildcards'].append({'source': src, 'target': target(cell(r, t), dom), 'regex': 1})
    h, rs = rows(UPD)
    if h is not None:
        for r in rs:
            ti, hi = cell(r, 1), cell(r, 2)
            out['update'][key(cell(r, 0), dom)] = {'title': '' if is_open(ti) else ti, 'h1': '' if is_open(hi) else hi}
    return out, bad, read


def read_ia(path, dom):
    T = workbook_tabs(path)
    if not set(T) & IA_TABS:
        sys.exit(f'{os.path.basename(path)} has none of the IA audit tabs (Moves, Check page type, Menu cleanup ...). '
                 'Is this the IA audit workbook? Give the working copy the SEO used.')
    if IA_README not in T and CPT not in T:
        sys.exit(f'{os.path.basename(path)} has no README and no Check page type tab: this is the implementer copy of the IA workbook. '
                 "Give the SEO's working copy.")
    out = {'moves': [], 'types': {}, 'fix_links': 0, 'menu': []}
    bad, read = [], []
    fn = os.path.basename(path)

    def need(tab, page, why):
        bad.append({'file': fn, 'tab': tab, 'page': page, 'problem': why})

    def rows(tab):
        if tab not in T:
            return []
        h, rs = table(T[tab])
        read.append({'file': fn, 'tab': tab, 'rows': len(rs)})
        return rs

    for r in rows(CPT):
        fixed = cell(r, 2)
        if fixed.lower().startswith('seo fill in'):
            need(CPT, cell(r, 0), 'Correct page type is still "SEO fill in"')
        out['types'][key(cell(r, 0), dom)] = fixed or cell(r, 1)
    for r in rows(MOVES):
        if is_open(cell(r, 1)):
            need(MOVES, cell(r, 0), 'New URL is blank or "SEO fill in"')
        else:
            out['moves'].append({'old': key(cell(r, 0), dom), 'new': key(cell(r, 1), dom)})
    for r in rows(FIX):
        out['fix_links'] += 1
        if is_open(cell(r, 2)):
            need(FIX, cell(r, 0), 'New URL to link to instead is blank or "SEO fill in"')
    for r in rows(MENU):
        if is_open(cell(r, 2)) or cell(r, 2).strip().lower() not in ('keep', 'remove'):
            need(MENU, cell(r, 0), 'Keep or Remove is blank or "SEO fill in"')
        else:
            out['menu'].append({'item': key(cell(r, 0), dom), 'decision': cell(r, 2).strip().lower()})
    return out, bad, read


def read_gap(path, dom):
    T = workbook_tabs(path)
    if REC not in T:
        sys.exit(f'{os.path.basename(path)} has no Recommendations tab. Is this the Service Gap workbook?')
    fn = os.path.basename(path)
    h, rs = table(T[REC], 'Service Page Recommended')
    n, u, x, e = col(h, 'service page recommended'), col(h, 'current url'), col(h, 'next steps'), col(h, 'existing')
    kw, rel = col(h, 'relevant keywords'), col(h, 'relevant pages')
    out, bad = {'new_pages': []}, []
    for r in rs:
        if not cell(r, n).strip():
            continue
        step = cell(r, x).strip()
        if not step:
            bad.append({'file': fn, 'tab': REC, 'page': cell(r, n), 'problem': 'Next Steps is empty'})
        elif step.lower() == 'create new page':
            out['new_pages'].append({'name': cell(r, n), 'url': key(cell(r, u), dom) if cell(r, u).startswith(('http', '/')) else '',
                                     'existing': cell(r, e), 'relevant': cell(r, rel), 'keywords': cell(r, kw)})
    return out, bad, [{'file': fn, 'tab': REC, 'rows': len(rs)}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domain', required=True)
    ap.add_argument('--prune', required=True)
    ap.add_argument('--ia', required=True)
    ap.add_argument('--gap')
    ap.add_argument('--out', default='work')
    a = ap.parse_args()
    dom = bare_domain(a.domain)
    prune, b1, r1 = read_prune(a.prune, dom)
    ia, b2, r2 = read_ia(a.ia, dom)
    gap, b3, r3 = read_gap(a.gap, dom) if a.gap else ({'new_pages': []}, [], [])
    data = {'prune': prune, 'ia': ia, 'gap': gap, 'unresolved': b1 + b2 + b3, 'read': r1 + r2 + r3}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'audits.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    print(f"Prune: {len(prune['keep'])} kept, {len(prune['merge'])} merged, {len(prune['remove'])} removed, "
          f"{len(prune['wildcards'])} wildcard rules, {len(prune['update'])} updates. IA: {len(ia['moves'])} moves. "
          f"Service Gap: {len(gap['new_pages'])} new pages.")
    if data['unresolved']:
        print(f"{len(data['unresolved'])} unresolved cell(s) in the audit workbooks (preflight blocks the build):")
        for u in data['unresolved']:
            print(f"  {u['file']} / {u['tab']}: {u['page']} - {u['problem']}")


if __name__ == '__main__':
    main()
