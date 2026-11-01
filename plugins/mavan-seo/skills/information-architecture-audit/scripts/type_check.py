#!/usr/bin/env python3
"""Compare the IA audit's page types with the Content Prune & Merge workbook's page types.

Run after analyze.py, only when a prune workbook was provided (prune_import.py wrote work/prune.csv).

Usage:
  python type_check.py --work work

Writes work/review/type_conflicts.csv and work/review/type_conflicts.md, and prints a summary.

A conflict is a page both audits cover whose types cannot be reconciled (for example the prune says Blog Post
and the IA audit says Service-like). The script does not decide which is right: a person confirms the real
page type, the answer goes in decisions.json page_types, and the prune workbook should be updated to match
because its Suggested Next Step depends on its Page Type.
"""
import argparse
import os
import sys

import pandas as pd

# prune Page Type -> IA audit types that agree with it
AGREE = {
    'Home': {'Home'},
    'Service': {'Service', 'Service-like (no folder)'},
    'Concern / Condition': {'Concern', 'Concern hub'},
    'Service Area / Location': {'Location / Area', 'Location hub'},
    'Hub / Category Page': {'Service hub', 'Concern hub', 'Location hub', 'Blog hub'},
    'Blog Post': {'Blog'},
    'Blog Category / Tag': {'Archive'},
    'Author / Archive': {'Archive'},
    'Gallery': {'Gallery item'},
    'Not for SEO (contact, legal, etc.)': {'Utility / Policy', 'Company / Info'},
    'Other': {'Company / Info', 'Utility / Policy'},
}
LEAF = {'Service', 'Service-like (no folder)', 'Concern', 'Location / Area'}
HUB = {'Service hub', 'Concern hub', 'Location hub', 'Blog hub'}
MONEY = {'Service', 'Service-like (no folder)', 'Service hub'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work')
    a = ap.parse_args()
    pr = os.path.join(a.work, 'prune.csv')
    ap_ = os.path.join(a.work, 'analysis', 'all_pages.csv')
    if not os.path.exists(pr):
        sys.exit('work/prune.csv not found: no prune workbook was imported (prune_import.py). Nothing to compare.')
    if not os.path.exists(ap_):
        sys.exit('work/analysis/all_pages.csv not found: run analyze.py first.')
    prune = pd.read_csv(pr, keep_default_na=False, dtype=str).drop_duplicates('key')
    ia = pd.read_csv(ap_, keep_default_na=False, dtype=str)
    m = ia.merge(prune, left_on='path', right_on='key', how='inner', suffixes=('', '_p'))
    out = []
    for r in m.itertuples():
        ok = AGREE.get(r.prune_type)
        if ok is None or r.type in ok or r.type.endswith('(folder)'):
            continue
        guess = 'Root-level' in r.prune_reason or 'No rule matched' in r.prune_reason
        kind = ('prune type was a guess from the URL wording' if guess else
                'prune type came from its folder map or a site signal')
        hubleaf = (r.prune_type == 'Hub / Category Page' and r.type in LEAF) or (r.type in HUB and r.prune_type in
                   ('Service', 'Concern / Condition', 'Service Area / Location'))
        out.append({'url': r.url, 'severity': 'Hub or page?' if hubleaf else 'Different type', 'path': r.path, 'ia_type': r.type, 'ia_why': r.why, 'prune_type': r.prune_type,
                    'prune_reason': r.prune_reason, 'prune_basis': kind, 'h1': r.h1,
                    'matters_for_services': 'Yes' if (r.type in MONEY or r.prune_type == 'Service') else '',
                    'plan_action': r.plan_action, 'plan_target': r.plan_target})
    c = pd.DataFrame(out)
    R = os.path.join(a.work, 'review')
    os.makedirs(R, exist_ok=True)
    cols = ['url', 'severity', 'path', 'ia_type', 'ia_why', 'prune_type', 'prune_reason', 'prune_basis', 'h1', 'matters_for_services',
            'plan_action', 'plan_target']
    (c if len(c) else pd.DataFrame(columns=cols)).to_csv(os.path.join(R, 'type_conflicts.csv'), index=False)
    lines = [f'# Page type conflicts with the content prune\n',
             f'{len(m)} pages are in both audits; {len(c)} have types that disagree.\n']
    if len(c):
        g = c.groupby(['severity', 'prune_type', 'ia_type', 'prune_basis']).size().reset_index(name='pages')
        lines.append('"Different type" = the two audits disagree about what the page is. "Hub or page?" = one calls it a listing/hub page and the other an ordinary page; lower stakes, ask in one question.\n')
        lines.append('| Kind | Prune says | IA audit says | Why the prune typed it so | Pages |\n| --- | --- | --- | --- | ---: |')
        for x in g.sort_values(['severity', 'pages'], ascending=[True, False]).itertuples():
            lines.append(f'| {x.severity} | {x.prune_type} | {x.ia_type} | {x.prune_basis} | {x.pages} |')
        lines.append('\nExamples (up to 3 per row):')
        for (pt, it), d in c.groupby(['prune_type', 'ia_type']):
            for x in d.head(3).itertuples():
                lines.append(f'- {x.path} - H1 "{x.h1}" - prune: {pt}; IA: {it} ({x.ia_why})')
        lines.append('\nAsk the person for the correct type of each group (not each page). Put the answers in '
                     'decisions.json page_types. Then tell them the prune workbook should be updated to the same '
                     'types, because its Suggested Next Step depends on Page Type, and give them the URL list '
                     '(work/review/type_conflicts.csv).')
    open(os.path.join(R, 'type_conflicts.md'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    svc = int((c.matters_for_services == 'Yes').sum()) if len(c) else 0
    nd = int((c.severity == 'Different type').sum()) if len(c) else 0
    print(f'\nCONFLICTS: {len(c)} of {len(m)} shared pages ({nd} different type, {len(c) - nd} hub-or-page; {svc} involve a service page).')


if __name__ == '__main__':
    main()
