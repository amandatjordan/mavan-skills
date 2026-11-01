#!/usr/bin/env python3
"""Read a Content Prune & Merge workbook (optional input) for the IA audit.

Usage:
  python prune_import.py --workbook PRUNE.xlsx --domain example.com [--out work]

Writes:
  work/prune.csv   url, key, prune_type, prune_reason, plan_action, plan_target, plan_source
                   (plan_action is the filled-in Next Steps when the team has filled it in, else the skill's
                   Suggested Next Step; plan_source says which)
  work/past.csv    url, decision, target  -> pass to analyze.py --past so the IA audit assumes the plan is followed
  work/prune_wildcards.csv  wildcard redirects (source with *) from the Existing Redirects tab, if there is one

Not every IA audit has a content prune. When there is none, skip this script and type_check.py.
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, key  # noqa: E402


def pick(cols, *names):
    low = {str(c).strip().lower(): c for c in cols}
    return next((low[n] for n in names if n in low), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workbook', required=True)
    ap.add_argument('--domain', required=True)
    ap.add_argument('--out', default='work')
    a = ap.parse_args()
    dom = bare_domain(a.domain)
    x = pd.read_excel(a.workbook, sheet_name=None, dtype=str)
    aud = next((d for d in x.values() if pick(d.columns, 'url') and pick(d.columns, 'page type')), None)
    if aud is None:
        sys.exit('No tab with URL and Page Type columns: this is not a Prune & Merge workbook.')
    u, t, r = pick(aud.columns, 'url'), pick(aud.columns, 'page type'), pick(aud.columns, 'page type reason')
    ns, nt = pick(aud.columns, 'next steps'), pick(aud.columns, 'target url')
    ss, st = pick(aud.columns, 'suggested next step'), pick(aud.columns, 'suggested target')
    rows, past = [], []
    for _, row in aud.fillna('').iterrows():
        url = str(row[u]).strip()
        if not url.startswith('http'):
            continue
        final = str(row[ns]).strip() if ns else ''
        act, tgt, src = ((final, str(row[nt]).strip() if nt else '', 'Next Steps (final)') if final else
                         (str(row[ss]).strip() if ss else '', str(row[st]).strip() if st else '', 'Suggested Next Step'))
        tgt = key(tgt, dom) if tgt.startswith('http') or tgt.startswith('/') else tgt  # the audit keeps targets as paths
        rows.append({'url': url, 'key': key(url, dom), 'prune_type': str(row[t]).strip(),
                     'prune_reason': str(row[r]).strip() if r else '', 'plan_action': act, 'plan_target': tgt,
                     'plan_source': src})
        if act:
            past.append({'url': url, 'decision': act, 'target': tgt})
    os.makedirs(a.out, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(a.out, 'prune.csv'), index=False)
    pd.DataFrame(past).to_csv(os.path.join(a.out, 'past.csv'), index=False)
    wild = 0
    for d in x.values():
        s = pick(d.columns, 'source url')
        if s is not None:
            w = d[d[s].fillna('').str.contains(r'\*', regex=True)]
            if len(w):
                w.to_csv(os.path.join(a.out, 'prune_wildcards.csv'), index=False)
                wild = len(w)
    df = pd.DataFrame(rows)
    print(f'{len(df)} audited URLs. Page types: ' + ', '.join(f'{k} x{v}' for k, v in df.prune_type.value_counts().items()))
    print('Plan source: ' + ', '.join(f'{k} x{v}' for k, v in df.plan_source.value_counts().items())
          + '; actions: ' + ', '.join(f'{k} x{v}' for k, v in df.plan_action.value_counts().items()))
    df['folder'] = df.key.map(lambda k: '/' + k.strip('/').split('/')[0] + '/' if k.strip('/').count('/') >= 1 else '(root level)')
    print('\nPage types by first-level folder (show next to the folder mapping in Step 3):')
    for f, d in df.groupby('folder'):
        print(f'  {f}: ' + ', '.join(f'{k} x{v}' for k, v in d.prune_type.value_counts().items()))
    if wild:
        print(f'{wild} wildcard redirect(s) saved to prune_wildcards.csv')


if __name__ == '__main__':
    main()
