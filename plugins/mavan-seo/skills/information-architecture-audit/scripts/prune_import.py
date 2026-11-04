#!/usr/bin/env python3
"""Read a Content Prune & Merge workbook (optional input) for the IA audit.

Usage:
  python prune_import.py --workbook PRUNE.xlsx --domain example.com [--out work]

Give it the SEO's working copy of the prune workbook (the one that still has the Kept pages and Check page type tabs).
Tabs are matched by their exact names. Row 1 of each tab is a banner, so headers are in row 2; the dev
tab 'All redirects - Handoff to Dev' has headers in row 1. A tab the prune left out (it had no rows) is skipped.

Writes:
  work/prune.csv            url, key, prune_type, prune_reason, plan_action, plan_target, plan_source
                            prune_type is set only for pages whose type a person or a folder rule settled: Kept pages,
                            and Check page type rows where the SEO filled in the correct type. A guessed type nobody
                            corrected is left empty, so the IA audit types that page itself.
  work/past.csv             url, decision, target  -> analyze.py --past, so the IA audit assumes the prune plan is followed
  work/prune_wildcards.csv  wildcard redirects (written with * ) from Junk folders and the dev tab (Regex = 1)
  work/prune_disagree.csv   Kept pages the SEO typed a change for. Not guessed at: list them for the person.
"""
import argparse
import os
import re
import sys

import openpyxl
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, key  # noqa: E402

KEPT, CPT, DEV, JUNK = 'Kept pages', 'Check page type', 'All redirects - Handoff to Dev', 'Junk folders'
# tab -> (plan action, where the target sits: column index or None)
ACTION_TABS = {
    'Merge pages': ('Merge then Redirect', 1), 'Remove pages': ('Remove then Redirect', 1),
    'Update pages': ('Update', None), 'Repurpose pages': ('Repurpose', None),
    'Blog beats service': ('Keep', None), 'Needs discussion': ('Needs Discussion', None),
}
LOCATION = 'Per location service pages'
ALL_TABS = [KEPT, CPT, DEV, JUNK, LOCATION] + list(ACTION_TABS)


def table(ws):
    """(headers, rows) of a tab: headers are in row 1 when row 1 has several cells (dev tab), else in row 2 (banner in row 1)."""
    rows = [[('' if c is None else str(c).strip()) for c in r] for r in ws.iter_rows(values_only=True)]
    if not rows:
        return [], []
    h = 0 if sum(1 for c in rows[0] if c) >= 2 else 1
    return rows[h], [r for r in rows[h + 1:] if any(r)]


def cell(r, i):
    return r[i] if i is not None and i < len(r) else ''


def col(headers, *starts):
    low = [h.lower() for h in headers]
    for s in starts:
        for i, h in enumerate(low):
            if h.startswith(s):
                return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workbook', required=True)
    ap.add_argument('--domain', required=True)
    ap.add_argument('--out', default='work')
    a = ap.parse_args()
    dom = bare_domain(a.domain)
    wb = openpyxl.load_workbook(a.workbook, read_only=True, data_only=True)
    names = set(wb.sheetnames)
    if not names & set(ALL_TABS):
        sys.exit('None of the Content Prune & Merge tabs were found (Kept pages, Check page type, Remove pages, ...). '
                 'Is this the prune workbook? Give the working copy the SEO used.')
    rows, disagree, wild = {}, [], []

    def add(url, **kw):
        if str(url).startswith('http'):
            r = rows.setdefault(key(url, dom), {'url': url, 'key': key(url, dom), 'prune_type': '', 'prune_reason': '',
                                                'plan_action': '', 'plan_target': '', 'plan_source': ''})
            r.update({k: v for k, v in kw.items() if v != ''})

    def tgt(t):
        return key(t, dom) if t.startswith('http') or t.startswith('/') else t  # the audit keeps targets as paths

    if KEPT in names:
        h, rs = table(wb[KEPT])
        p, t, d = col(h, 'page'), col(h, 'page type'), col(h, 'disagree')
        for r in rs:
            add(cell(r, p), prune_type=cell(r, t), plan_action='Keep', plan_source=KEPT)
            if cell(r, d):
                disagree.append({'url': cell(r, p), 'prune_type': cell(r, t), 'change_requested': cell(r, d)})
    if CPT in names:
        h, rs = table(wb[CPT])
        p, g, c = col(h, 'page'), col(h, 'page type we guessed'), col(h, 'correct page type')
        for r in rs:
            fixed = cell(r, c)
            if fixed.lower().startswith('seo fill in'):
                fixed = ''
            add(cell(r, p), prune_type=fixed, prune_reason='' if fixed else 'Guessed from the URL', plan_source=CPT)
    for tab, (action, ti) in ACTION_TABS.items():
        if tab in names:
            h, rs = table(wb[tab])
            for r in rs:
                add(cell(r, 0), plan_action=action, plan_target=tgt(cell(r, ti)) if ti is not None else '', plan_source=tab)
    if LOCATION in names:
        h, rs = table(wb[LOCATION])
        w = col(h, 'what to do')
        for r in rs:
            merge = cell(r, w).lower().startswith('merge')
            add(cell(r, 0), plan_action='Merge then Redirect' if merge else 'Keep',
                plan_target=tgt(cell(r, 1)) if merge else '', plan_source=LOCATION)
    if JUNK in names:
        h, rs = table(wb[JUNK])
        for r in rs:
            if '*' in cell(r, 0):
                wild.append({'source': cell(r, 0), 'target': cell(r, 1)})
    if DEV in names:
        h, rs = table(wb[DEV])
        s, t, x = col(h, 'source'), col(h, 'target'), col(h, 'regex')
        for r in rs:
            if cell(r, x).strip() in ('1', '1.0') and cell(r, s):
                wild.append({'source': re.sub(r'\(\.\*\)$', '*', cell(r, s)), 'target': cell(r, t)})
    os.makedirs(a.out, exist_ok=True)
    df = pd.DataFrame(list(rows.values()), columns=['url', 'key', 'prune_type', 'prune_reason', 'plan_action', 'plan_target',
                                                    'plan_source'])
    df.to_csv(os.path.join(a.out, 'prune.csv'), index=False)
    past = df[df.plan_action != ''][['url', 'plan_action', 'plan_target']]
    past.columns = ['url', 'decision', 'target']
    past.to_csv(os.path.join(a.out, 'past.csv'), index=False)
    wd = pd.DataFrame(wild, columns=['source', 'target']).drop_duplicates('source')
    if len(wd):
        wd.to_csv(os.path.join(a.out, 'prune_wildcards.csv'), index=False)
    if disagree:
        pd.DataFrame(disagree).to_csv(os.path.join(a.out, 'prune_disagree.csv'), index=False)

    typed = df[df.prune_type != '']
    print(f'{len(df)} pages on the prune tabs; {len(typed)} have a page type to adopt. Tabs read: '
          + ', '.join(f'{k} x{v}' for k, v in df.plan_source.value_counts().items()))
    print('Plan actions: ' + ', '.join(f'{k} x{v}' for k, v in df.plan_action.value_counts().items()))
    if KEPT not in names and CPT not in names:
        print('NOTE: neither Kept pages nor Check page type is in this workbook, so it has no page types. This looks like the '
              "implementer copy. The IA audit will type every page itself. Ask for the SEO's working copy if you want the "
              "prune's types used.")
    guessed = int((df.prune_reason == 'Guessed from the URL').sum())
    if guessed:
        print(f'{guessed} page(s) on Check page type have no corrected type, so the IA audit types them itself.')
    if disagree:
        print(f'{len(disagree)} Kept page(s) have a change typed in the Disagree column (work/prune_disagree.csv). '
              'Do not guess: list them for the person.')
    if len(wd):
        print(f'{len(wd)} wildcard redirect(s) saved to prune_wildcards.csv')
    df['folder'] = df.key.map(lambda k: '/' + k.strip('/').split('/')[0] + '/' if k.strip('/').count('/') >= 1 else '(root level)')
    t2 = df[df.prune_type != '']
    if len(t2):
        print('\nPage types by first-level folder (show next to the folder mapping in Step 3):')
        for f, d in t2.groupby('folder'):
            print(f'  {f}: ' + ', '.join(f'{k} x{v}' for k, v in d.prune_type.value_counts().items()))


if __name__ == '__main__':
    main()
