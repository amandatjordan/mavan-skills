#!/usr/bin/env python3
"""Read an IA audit workbook (optional input) for the content prune.

Usage:
  python ia_import.py --workbook IA_FILE --domain example.com [--out work]

IA_FILE is the IA audit workbook as .xlsx, or the attached Google Sheet (tabs separated by '## Sheet name:' lines).
Use the SEO's working copy: the Check page type tab is deleted before the IA workbook goes to an implementer.

Everything the IA audit decided is treated as approved by the SEO:
  - Check page type: the Correct page type when filled, else the guess (an empty cell means the guess was confirmed).
  - README 'Folder to page type map': the folder map a person confirmed.
  - README 'Other cities': cities treated as their own markets.

Writes to --out (build.py and make_xlsx.py read them when they exist; without an IA workbook, skip this script):
  ia_types.csv        key, ia_type, page_type   pages the IA typed (prune Page Type values)
  ia_folder_map.json  {"/folder/": "Page Type"}  the IA's confirmed folder map, in prune Page Type values. It types the
                                                 pages INSIDE each folder; the folder's own page is its listing (Hub)
  ia_moves.csv        old, new                   pages the IA moves to a new URL
  ia_menu.csv         key                        menu items already on the IA's Menu cleanup tab
  ia.json             other cities, which IA tabs were present, counts
It prints the folder map and cities for SKILL.md Step 2.
"""
import argparse
import csv
import io
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, key  # noqa: E402

CPT, MOVES, MENU, README, FIX = 'Check page type', 'Moves', 'Menu cleanup', 'README', 'Fix links'
NFS = 'Not for SEO (contact, legal, etc.)'
# IA audit page type -> prune Page Type. Not used: Unclassified, Pagination, Query-string URL (no page type to adopt).
IA_TO_PRUNE = {
    'Home': 'Home', 'Service': 'Service', 'Service-like (no folder)': 'Service', 'Concern': 'Concern / Condition',
    'Location / Area': 'Service Area / Location', 'Location': 'Service Area / Location',
    'Service hub': 'Hub / Category Page', 'Concern hub': 'Hub / Category Page', 'Location hub': 'Hub / Category Page',
    'Blog hub': 'Hub / Category Page', 'Blog': 'Blog Post', 'Gallery item': 'Gallery', 'Utility / Policy': NFS,
    'Company / Info': 'Other', 'Other': 'Other', 'Archive': 'Blog Category / Tag',
}


def to_prune(t, path=''):
    t = str(t).strip()
    if t == 'Archive' and re.search(r'^/(author|authors)/|/\d{4}/', path or ''):
        return 'Author / Archive'
    return IA_TO_PRUNE.get(t, '')


def tabs(path):
    """{tab name: list of rows (lists of strings)}."""
    if path.lower().endswith(('.xlsx', '.xls')):
        x = pd.read_excel(path, sheet_name=None, header=None, dtype=str)
        return {n: d.fillna('').values.tolist() for n, d in x.items()}
    text = open(path, encoding='utf-8-sig').read()
    parts = re.split(r'^## Sheet name:\s*(.*)$', text, flags=re.M)
    if len(parts) < 2:
        sys.exit('Could not find the IA workbook tabs. Attach the IA audit workbook as .xlsx or as the Google Sheet.')
    return {parts[i].strip(): list(csv.reader(io.StringIO(parts[i + 1].strip()))) for i in range(1, len(parts), 2)}


def body(rows, first_header):
    """Rows under the header row whose first cell starts with first_header (row 1 is often a banner)."""
    for i, r in enumerate(rows):
        if r and str(r[0]).strip().startswith(first_header):
            return [x + [''] * 8 for x in rows[i + 1:] if x and str(x[0]).strip()]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workbook', required=True)
    ap.add_argument('--domain', required=True)
    ap.add_argument('--out', default='work')
    a = ap.parse_args()
    dom = bare_domain(a.domain)
    k = lambda u: key(u, dom)
    T = tabs(a.workbook)
    if not ({CPT, MOVES, MENU, README} & set(T)):
        sys.exit(f'This does not look like an IA audit workbook (tabs: {list(T)}).')
    if README not in T and CPT not in T:
        sys.exit('The README and Check page type tabs are missing: this is the copy sent to the implementer. '
                 "Ask for the SEO's working copy of the IA workbook.")
    os.makedirs(a.out, exist_ok=True)

    types = []
    for r in body(T.get(CPT, []), 'Page'):
        page, guess, fixed = r[0].strip(), r[1].strip(), r[2].strip()
        t = fixed if fixed and fixed != 'SEO fill in' else guess
        pt = to_prune(t, k(page))
        if pt:
            types.append({'key': k(page), 'ia_type': t, 'page_type': pt})
    pd.DataFrame(types, columns=['key', 'ia_type', 'page_type']).to_csv(os.path.join(a.out, 'ia_types.csv'), index=False)

    settings = {str(r[0]).strip(): str(r[2]).strip() for r in T.get(README, []) if len(r) > 2}
    fm = {}
    for part in settings.get('Folder to page type map', '').split(';'):
        if '=' in part:
            left, t = (x.strip() for x in part.split('=', 1))
            for f in (x.strip() for x in left.split(',')):  # several folders can share one entry
                pt = to_prune(t, f)
                if f.startswith('/') and pt:
                    fm['/' + f.strip('/') + '/'] = pt
    with open(os.path.join(a.out, 'ia_folder_map.json'), 'w', encoding='utf-8') as fh:
        json.dump(fm, fh, indent=1)
    oc = settings.get('Other cities', '')
    m = re.search(r'\(([^)]*)\)', oc)
    cities = [c.strip() for c in (m.group(1) if m else oc).split(',') if c.strip() and c.strip().lower() != 'none']

    moves = [{'old': k(r[0]), 'new': k(r[1])} for r in body(T.get(MOVES, []), 'Page to move')
             if r[1].strip() and r[1].strip() != 'SEO fill in']
    pd.DataFrame(moves, columns=['old', 'new']).to_csv(os.path.join(a.out, 'ia_moves.csv'), index=False)
    menu = [{'key': k(r[0])} for r in body(T.get(MENU, []), 'Menu item')]
    pd.DataFrame(menu, columns=['key']).to_csv(os.path.join(a.out, 'ia_menu.csv'), index=False)

    info = {'other_cities': cities, 'tabs': list(T), 'fix_links_tab': FIX in T,
            'types': len(types), 'folders': len(fm), 'moves': len(moves), 'menu_items': len(menu)}
    with open(os.path.join(a.out, 'ia.json'), 'w', encoding='utf-8') as fh:
        json.dump(info, fh, indent=1)

    print(f'IA audit workbook: {len(types)} page types from Check page type (all treated as approved), '
          f'{len(moves)} moves, {len(menu)} menu items on its Menu cleanup tab.')
    print('Folder map the IA audit confirmed (prune Page Types):')
    for f, t in fm.items():
        print(f'  {f} = {t}')
    print('Other cities the IA audit treated as their own markets: ' + (', '.join(cities) or 'none'))


if __name__ == '__main__':
    main()
