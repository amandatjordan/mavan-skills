#!/usr/bin/env python3
"""New-site keyword research: match a client's services, products and concerns to the service taxonomy, then build the workbook.

  research.py match --services "A; B" --products "C; D" [--concerns "E; F"] --out work
  research.py build --selection work/selection.tsv --client "Name" --out NAME_new_site_keyword_research.xlsx

Output tabs: Pages (everything a person works from, including a Client offers it? column and the internal links), Keywords, Not in the plan, Read Me.
Every count, join and cutoff is done here. Nothing is typed or estimated by hand. Volumes are never added together.
"""
import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TAXONOMY = SKILL_DIR / 'references' / 'service-taxonomy.xlsx'

# --- Rules (explained in references/rules.md) --------------------------------------------------
# A Sub-Service or Brand / Device gets its own page when its highest-volume keyword is at least this.
# Below it, the item is a section on its parent page. Services and listed concerns always get a page.
PAGE_MIN_VOLUME = 1000
RELATED_KEYWORDS_SHOWN = 10          # keywords shown on the Pages tab (all of them are on the Keywords tab)
MAX_CONCERNS = 5                     # "very limited concern pages" for a new site; more only warns
CONFIRM_MIN_VOLUME = PAGE_MIN_VOLUME  # unlisted Sub-Services / Brands are offered for confirmation at this volume
# Treatments the taxonomy marks as not approved, investigational or discontinued are never recommended.
NOT_RECOMMENDED = re.compile(r'do not flag|usually exclude|not (fda|us)[- ]approved|discontinued|not approved|investigational', re.I)
# Simple word checks that only decide which sections a page should cover. They never change a page decision.
MODIFIERS = {
    'Cost': r'\b(cost|costs|price|prices|pricing|how much|cheap|financing)\b',
    'Before & After': r'before ?(and|&) ?after|before/after',
    'Recovery / Risks': r'recover\w*|side effects?|\brisks?\b|downtime|healing|aftercare|complications?',
    'Comparison': r'\bvs\.?\b|versus|difference between|compare|comparison|alternatives?',
    'Candidacy': r'candidate|candidacy|who (is|should)|am i a|good for|right for|eligible',
    'Best / Top': r'\b(best|top)\b',
}
VOLUME_LABEL = ('National volume from the taxonomy keyword list (what competitors rank for, often with a city in the search). '
                'Use it to rank pages against each other. It is not local demand and not a traffic forecast.')

OFFERS_COL = 'Client offers it? (Yes / No)'
LINKS_COL = 'Internal links out (priority)'
ANCHOR_COL = 'Anchor text for links to this page (SEO fills in)'
LEVELS = ('Service', 'Sub-Service', 'Brand / Device', 'Concern')
# A concern the taxonomy does not have, which the person chose to keep as a target anyway. It gets a Concern page
# with no keyword data, and links only to the Services / Sub-Services named in its treated_by column.
CUSTOM_CONCERN = 'Custom concern'
DEPTH = {'Service': 1, 'Sub-Service': 2, 'Brand / Device': 3}
SELECTION_COLS = ['kind', 'input', 'level', 'service', 'sub_service', 'brand_device', 'concern', 'treated_by', 'status', 'candidates']


def s(v):
    return '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text)) if not unicodedata.combining(c))


def norm(text):
    t = re.sub(r'\(family\)', ' ', fold(text).lower().replace('&', ' and '))
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', t)).strip()


def display(name):
    """A taxonomy name as people read it: the taxonomy's "(family)" tag means nothing to them, so it is never shown."""
    return re.sub(r'\s*\(family\)', '', name).strip()


def split_list(text):
    return [p.strip() for p in re.split(r'[;\n]+', text or '') if p.strip()]


# --- Taxonomy ------------------------------------------------------------------------------------
class Taxonomy:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            sys.exit(f'Taxonomy file not found: {self.path}')
        tax = pd.read_excel(self.path, sheet_name='Taxonomy')
        kw = pd.read_excel(self.path, sheet_name='All Keywords')
        need = {'Level', 'Category', 'Service', 'Sub-Service', 'Brand / Device', 'Concern', 'Practice Type',
                'Implies Offered', 'Status / Notes', 'Match Terms (regex)'}
        if need - set(tax.columns):
            sys.exit(f'Taxonomy tab is missing columns: {sorted(need - set(tax.columns))}')
        need_kw = {'Keyword', 'Volume', 'Keyword Difficulty', 'CPC', 'Class', 'Matched Level', 'Service', 'Sub-Service',
                   'Brand / Device', 'Concern', 'Near Me', 'Geo Modified'}
        if need_kw - set(kw.columns):
            sys.exit(f'All Keywords tab is missing columns: {sorted(need_kw - set(kw.columns))}')
        try:
            self.version = s(pd.read_excel(self.path, sheet_name='Read Me', header=None).iloc[0, 0])
        except Exception:
            self.version = self.path.name
        self.nodes = []
        for _, r in tax.iterrows():
            if s(r['Level']) not in LEVELS:
                continue
            n = {k: s(r[k]) for k in ('Level', 'Category', 'Service', 'Sub-Service', 'Brand / Device', 'Concern',
                                      'Practice Type', 'Implies Offered', 'Status / Notes', 'Match Terms (regex)')}
            n['dental'] = n['Practice Type'].lower() == 'dental' or n['Category'].lower().startswith('dental')
            n['name'] = n[{'Service': 'Service', 'Sub-Service': 'Sub-Service', 'Brand / Device': 'Brand / Device',
                           'Concern': 'Concern'}[n['Level']]]
            self.nodes.append(n)
        self.kw = kw[kw['Class'].isin(['Service', 'Concern'])].copy()
        for c in ('Keyword', 'Service', 'Sub-Service', 'Brand / Device', 'Concern', 'Matched Level'):
            self.kw[c] = self.kw[c].map(s)
        self.kw['geo'] = self.kw['Geo Modified'].map(s) != ''
        self.kw['near_me'] = self.kw['Near Me'].map(s) != ''

    def find(self, level, service='', sub='', brand='', concern=''):
        same = lambda a, b: norm(a) == norm(b)   # a reviewer may type Juvéderm for the taxonomy's Juvéderm (family)
        for n in self.nodes:
            if n['Level'] != level:
                continue
            if level == 'Service' and same(n['Service'], service):
                return n
            if level == 'Sub-Service' and same(n['Service'], service) and same(n['Sub-Service'], sub):
                return n
            if level == 'Brand / Device' and same(n['Service'], service) and same(n['Brand / Device'], brand):
                return n
            if level == 'Concern' and same(n['Concern'], concern):
                return n
        return None

    def keywords(self, n):
        k = self.kw
        if n.get('custom'):   # not in the taxonomy, so no keyword can belong to it
            return k.iloc[0:0]
        if n['Level'] == 'Service':
            m = (k['Matched Level'] == 'Service') & (k['Service'] == n['Service'])
        elif n['Level'] == 'Sub-Service':
            m = (k['Matched Level'] == 'Sub-Service') & (k['Service'] == n['Service']) & (k['Sub-Service'] == n['Sub-Service'])
        elif n['Level'] == 'Brand / Device':
            m = (k['Matched Level'] == 'Brand / Device') & (k['Service'] == n['Service']) & (k['Brand / Device'] == n['Brand / Device'])
        else:
            m = (k['Matched Level'] == 'Concern') & (k['Concern'] == n['Concern'])
        return k[m]


def num(v, cast=int):
    """A number from a keyword cell, or None when the taxonomy leaves it blank (Keyword Difficulty and CPC are blank for the concern keywords added in v5.3)."""
    return None if v is None or pd.isna(v) else cast(v)


def label(n):
    if n['Level'] == 'Service' or n['Level'] == 'Concern':
        return display(n['name'])
    return f"{display(n['Service'])} > {display(n['name'])}"


# --- match ---------------------------------------------------------------------------------------
def match_one(tax, text, kind):
    """Return (status, basis, candidate nodes) for one typed item."""
    pool = [n for n in tax.nodes if (n['Level'] == 'Concern') == (kind == 'concern')]
    t = norm(text)
    exact = [n for n in pool if norm(n['name']) == t]
    if exact:
        return ('ok' if len(exact) == 1 else 'review'), 'name', exact
    raw = fold(text).lower()
    hits = []
    for n in pool:
        pat = n['Match Terms (regex)']
        if not pat:
            continue
        try:
            if re.search(pat, raw, re.I) or re.search(pat, text.lower(), re.I):
                hits.append(n)
        except re.error:
            continue
    if not hits:
        return 'none', '', []
    if kind != 'concern':
        deepest = max(DEPTH[n['Level']] for n in hits)
        hits = [n for n in hits if DEPTH[n['Level']] == deepest]
    return ('ok' if len(hits) == 1 else 'review'), 'pattern', hits


def cmd_match(a):
    tax = Taxonomy(a.taxonomy)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    items = [('service', t) for t in split_list(a.services)] + [('product', t) for t in split_list(a.products)] \
        + [('concern', t) for t in split_list(a.concerns)]
    if not items:
        sys.exit('Nothing to match: pass --services, --products and/or --concerns.')
    rows = []
    for kind, text in items:
        status, basis, cands = match_one(tax, text, kind)
        first = cands[0] if cands else None
        rows.append({
            'kind': kind, 'input': text,
            'level': first['Level'] if first else '', 'service': first['Service'] if first else '',
            'sub_service': first['Sub-Service'] if first and first['Level'] == 'Sub-Service' else '',
            'brand_device': first['Brand / Device'] if first and first['Level'] == 'Brand / Device' else '',
            'concern': first['Concern'] if first and first['Level'] == 'Concern' else '',
            'treated_by': '',
            'status': status,
            'candidates': ' | '.join(f"{n['Level']}: {label(n)}" for n in cands)})
    with open(out / 'selection.tsv', 'w', newline='') as f:
        w = csv.DictWriter(f, SELECTION_COLS, delimiter='\t')
        w.writeheader()
        w.writerows(rows)
    print(f'Taxonomy: {tax.version}')
    print(f'Wrote {out / "selection.tsv"} ({len(rows)} rows)')
    counts = pd.Series([r['status'] for r in rows]).value_counts().to_dict()
    print('Status counts:', counts)
    for r in rows:
        if r['status'] != 'ok':
            print(f"  [{r['status']}] {r['kind']}: {r['input']!r} -> {r['candidates'] or 'no match'}")
    print('Review every row: correct level, service, sub_service, brand_device and concern in place.')
    if any(r['kind'] == 'concern' and r['status'] == 'none' for r in rows):
        print(f"Unmatched concern: map it to a taxonomy concern, leave level blank to drop it, or set level to '{CUSTOM_CONCERN}' "
              "to keep it as a target anyway (name in concern, linked pages in treated_by).")


# --- build ---------------------------------------------------------------------------------------
def modifier_counts(keywords):
    out = []
    for name, pat in MODIFIERS.items():
        n = int(sum(bool(re.search(pat, k.lower())) for k in keywords))
        if n:
            out.append(f'{name} ({n})')
    return ', '.join(out)


def node_stats(tax, n):
    k = tax.keywords(n)
    local = k[k['geo']]
    k = k[~k['geo']].sort_values(['Volume', 'Keyword'], ascending=[False, True]).reset_index(drop=True)
    st = {'kw': k, 'count': len(k), 'city_count': len(local), 'head': None, 'head_vol': 0}
    if len(k):
        st['head'] = k.iloc[0]
        st['head_vol'] = int(k.iloc[0]['Volume'])
    return st


def whole_service(tax, n):
    """Service rows only: the highest-volume keyword anywhere under the service (sub-services and brands included). Shown as text, never summed."""
    k = tax.kw[(tax.kw['Service'] == n['Service']) & ~tax.kw['geo']]
    for x in tax.nodes:  # keywords of items the plan never recommends (not approved, discontinued) must not raise the figure
        if x['Service'] == n['Service'] and x['Level'] in ('Sub-Service', 'Brand / Device') and NOT_RECOMMENDED.search(x['Status / Notes']):
            col = 'Brand / Device' if x['Level'] == 'Brand / Device' else 'Sub-Service'
            k = k[~((k['Matched Level'] == x['Level']) & (k[col] == x['name']))]
    if not len(k):
        return ''
    top = k.sort_values(['Volume', 'Keyword'], ascending=[False, True]).iloc[0]
    return f"{top['Keyword']} ({int(top['Volume']):,})"


def custom_concern(tax, r):
    """A Concern node for a concern the taxonomy does not have. Its links come from treated_by, checked against real Service / Sub-Service names."""
    real = {n['name'] for n in tax.nodes if n['Level'] in ('Service', 'Sub-Service')}
    treated = [x.strip() for x in r['treated_by'].split(';') if x.strip()]
    return {'Level': 'Concern', 'Category': 'Concerns', 'Service': '', 'Sub-Service': '', 'Brand / Device': '',
            'Concern': r['concern'], 'Practice Type': '', 'Implies Offered': '; '.join(treated), 'Status / Notes': '',
            'Match Terms (regex)': '', 'dental': False, 'name': r['concern'], 'custom': True}, [t for t in treated if t not in real]


def parse_selection(tax, path):
    rows = list(csv.DictReader(open(path, newline=''), delimiter='\t'))
    if not rows:
        sys.exit('selection.tsv has no rows.')
    problems = []
    listed, unmatched, blocked = [], [], []
    for i, r in enumerate(rows, start=2):
        r = {c: s(r.get(c)) for c in SELECTION_COLS}
        if not r['level']:
            unmatched.append({'input': r['input'], 'kind': r['kind'], 'reason': 'No taxonomy match. Ask the person what it is, or leave it out of this research.'})
            continue
        if r['level'] == CUSTOM_CONCERN:
            if not r['concern']:
                problems.append(f"line {i}: {CUSTOM_CONCERN} needs a name in the concern column")
                continue
            if tax.find('Concern', concern=r['concern']):
                problems.append(f"line {i}: {r['concern']!r} is a taxonomy concern: set level to Concern, not {CUSTOM_CONCERN}")
                continue
            n, bad = custom_concern(tax, r)
            if bad:
                problems.append(f"line {i}: treated_by names no taxonomy Service or Sub-Service: {bad}")
                continue
            listed.append((r, n))
            continue
        if r['level'] not in LEVELS:
            problems.append(f"line {i}: level {r['level']!r} is not one of {LEVELS}")
            continue
        n = tax.find(r['level'], r['service'], r['sub_service'], r['brand_device'], r['concern'])
        if n is None:
            problems.append(f"line {i}: no taxonomy row for {r['level']} service={r['service']!r} sub_service={r['sub_service']!r} "
                            f"brand_device={r['brand_device']!r} concern={r['concern']!r}")
            continue
        if NOT_RECOMMENDED.search(n['Status / Notes']):
            blocked.append({'input': r['input'], 'kind': r['kind'], 'reason': 'Not recommended per the taxonomy: ' + n['Status / Notes']})
            continue
        listed.append((r, n))
    if problems:
        sys.exit('Fix these selection.tsv rows and run again:\n  ' + '\n  '.join(problems))
    return listed, unmatched + blocked


def build_plan(tax, listed):
    """Decide the nodes in the plan, then page or section for each."""
    plan = {}  # key -> dict

    def add(n, how, why=''):
        key = (n['Level'], n['Service'], n['Sub-Service'], n['Brand / Device'], n['Concern'])
        if key not in plan:
            plan[key] = {'node': n, 'listed': False, 'suggested': False, 'implied_by': []}
        if how == 'listed':
            plan[key]['listed'] = True
        elif how == 'suggested':
            plan[key]['suggested'] = True
        elif why and why not in plan[key]['implied_by']:
            plan[key]['implied_by'].append(why)
        return plan[key]

    for r, n in listed:
        add(n, 'listed')
    for r, n in listed:
        if n['Level'] in ('Sub-Service', 'Brand / Device'):
            svc = tax.find('Service', service=n['Service'])
            if svc:
                add(svc, 'implied', f"{n['name']}")
    # Sub-Services and Brands / Devices the client did not list but that have real volume (every unlisted dental one):
    # they join the plan as suggested pages and the Client offers it? column asks the client about each.
    plan_services = {k[1] for k in plan if k[0] == 'Service'}
    for n in tax.nodes:
        if n['Level'] not in ('Sub-Service', 'Brand / Device') or n['Service'] not in plan_services:
            continue
        key = (n['Level'], n['Service'], n['Sub-Service'], n['Brand / Device'], n['Concern'])
        if key in plan or NOT_RECOMMENDED.search(n['Status / Notes']):
            continue
        if n['dental'] or node_stats(tax, n)['head_vol'] >= CONFIRM_MIN_VOLUME:
            add(n, 'suggested')
    for p in plan.values():
        n = p['node']
        st = node_stats(tax, n)
        p.update(st)
        p['label'] = label(n)
    # page or section
    for p in plan.values():
        n = p['node']
        if n['Level'] in ('Service', 'Concern'):
            p['own'] = True
            p['why'] = ('Service the client lists' if p['listed'] else 'Parent of ' + ', '.join(p['implied_by'])) if n['Level'] == 'Service' \
                else ('Concern the client lists. Not in the taxonomy: kept as a target at the person\'s request' if n.get('custom')
                      else 'Concern the client lists (new sites get very few concern pages)')
        else:
            p['own'] = n['dental'] or p['head_vol'] >= PAGE_MIN_VOLUME
            if n['dental']:
                p['why'] = 'Dental: no minimum volume is applied, so every listed dental item gets its own page'
            elif not p['count']:
                p['why'] = 'No keyword data in the taxonomy, so the volume cutoff cannot decide: section by default. Check volume before building a page'
            elif p['own']:
                p['why'] = f"Highest keyword volume {p['head_vol']:,} is at least {PAGE_MIN_VOLUME:,}: own page"
            else:
                p['why'] = f"Highest keyword volume {p['head_vol']:,} is under {PAGE_MIN_VOLUME:,}: cover as a section"
    own_names = {}
    for key, p in plan.items():
        if p['own'] and p['node']['Level'] in ('Service', 'Sub-Service'):
            own_names.setdefault(p['node']['name'], []).append(key)
    # parents
    for key, p in plan.items():
        n = p['node']
        parents = []
        if n['Level'] == 'Sub-Service':
            parents = [('Service', n['Service'], '', '', '')]
        elif n['Level'] == 'Brand / Device':
            subs = [x.strip() for x in n['Sub-Service'].split(';') if x.strip()]
            parents = [k for k in ((('Sub-Service', n['Service'], x, '', '')) for x in subs) if k in plan and plan[k]['own'] and not plan[k]['suggested']]  # a page nobody has confirmed is never a parent
            if not parents:
                parents = [('Service', n['Service'], '', '', '')]
        p['parents'] = [k for k in parents if k in plan]
    return plan, own_names


def build_links(plan, own_names):
    links = []

    def add(frm, to, rel, prio):
        links.append({'From page': plan[frm]['label'], 'To page': plan[to]['label'], 'Relationship': rel, 'Priority': prio,
                      'To confirmed': not plan[to]['suggested']})

    own = {k for k, p in plan.items() if p['own']}
    for key, p in plan.items():
        if key not in own:
            continue
        n = p['node']
        if n['Level'] in ('Sub-Service', 'Brand / Device'):
            kind = 'Sub-Service' if n['Level'] == 'Sub-Service' else 'Brand / Device'
            for par in p['parents']:
                if par in own:
                    ptype = plan[par]['node']['Level']
                    add(par, key, f'{ptype} page links down to its {kind} page', 'High')
                    add(key, par, f'{kind} page links up to its {ptype} page', 'High')
    subs_by_service = {}
    for key in own:
        if key[0] == 'Sub-Service':
            subs_by_service.setdefault(key[1], []).append(key)
    for svc, keys in subs_by_service.items():
        for a in keys:
            for b in keys:
                if a != b:
                    add(a, b, f'Sibling Sub-Services under {svc}', 'Low')
    for key in own:
        if key[0] != 'Concern':
            continue
        p = plan[key]
        targets = []
        for nm in [x.strip() for x in p['node']['Implies Offered'].split(';') if x.strip()]:
            targets += [k for k in own_names.get(nm, []) if k in own]
        p['linked'] = bool(targets)
        for t in targets:
            add(key, t, 'Concern page links to a page that treats it', 'Medium')
            add(t, key, 'Service page links to the Concern page for the problem it treats', 'Medium')
    order = {'High': 0, 'Medium': 1, 'Low': 2}
    links.sort(key=lambda r: (order[r['Priority']], r['From page'], r['To page']))
    return links


def fmt_keywords(kw, n):
    return '; '.join(f"{r['Keyword']} ({int(r['Volume']):,})" for _, r in kw.head(n).iterrows())


def cmd_build(a):
    tax = Taxonomy(a.taxonomy)
    listed, skipped = parse_selection(tax, a.selection)
    if not listed:
        sys.exit('Nothing to build: no selection row matched a taxonomy item.')
    plan, own_names = build_plan(tax, listed)
    links = build_links(plan, own_names)
    concerns_listed = [p for p in plan.values() if p['node']['Level'] == 'Concern']
    warnings = []
    if len(concerns_listed) > MAX_CONCERNS:
        warnings.append(f'{len(concerns_listed)} concerns listed. A new site usually gets at most {MAX_CONCERNS} concern pages: confirm the list.')
    for p in concerns_listed:
        if not p.get('linked'):
            warnings.append(f"Concern '{p['node']['name']}' points to no service on this plan ({p['node']['Implies Offered'] or 'none'}): nothing links to its page.")
        if p['node'].get('custom'):
            warnings.append(f"Concern '{p['node']['name']}' is not in the taxonomy: no keyword data. Research its volume separately and add it to service-taxonomy.xlsx.")

    # order: Service groups in the order they were listed, then Concerns
    service_order = []
    for key, p in plan.items():
        if key[0] != 'Concern' and key[1] not in service_order:
            service_order.append(key[1])
    rows = []

    def sort_key(item):
        key, p = item
        if key[0] == 'Concern':
            return (len(service_order), 0, -p['head_vol'], p['label'])
        return (service_order.index(key[1]), DEPTH[key[0]], -p['head_vol'], p['label'])

    ordered = sorted(plan.items(), key=sort_key)
    links_out = {}
    for l in links:   # already sorted High > Medium > Low
        links_out.setdefault(l['From page'], []).append(f"{l['To page']} ({l['Priority']})" + ('' if l['To confirmed'] else ' [only if the client offers it]'))
    mentions = {k: [] for k in plan}
    for key, p in plan.items():
        if not p['own']:
            for par in p['parents']:
                mentions[par].append(f"{display(p['node']['name'])} ({p['head_vol']:,})" if p['count'] else f"{display(p['node']['name'])} (no keywords)")
    for key, p in ordered:
        n = p['node']
        parent_labels = ', '.join(plan[k]['label'] for k in p['parents'])
        if p['own']:
            rec = 'Own page'
        else:
            rec = f'Section on {parent_labels} page' + ('s' if len(p['parents']) > 1 else '')
        head = p['head']
        note = []
        if p['suggested']:
            note.append('The client did not list this. Ask whether they offer it; if not, drop the row and skip links to it')
        elif p['listed'] is False and n['Level'] != 'Concern':
            note.append('Added because it is the parent of a listed item')
        if n['Status / Notes'] and not n['Status / Notes'].startswith(('NEW v5.1', 'Dental')) and 'Not a page gap' not in n['Status / Notes']:
            note.append('Taxonomy note: ' + n['Status / Notes'])
        if n.get('custom'):
            note.append('Not in the taxonomy: kept as a target at the person\'s request. No keyword data, so research its volume separately, '
                        'and add it to service-taxonomy.xlsx. Its links come from the treated_by column, not the taxonomy')
        elif not p['count']:
            note.append('No keywords in the taxonomy for this item (dental has none yet): research its volume separately')
        if n['Status / Notes'].startswith('NEW v5.1'):
            note.append('New in the taxonomy and not yet confirmed')
        rows.append({
            'Level': n['Level'], 'Service / sub-service': p['label'], 'Category': n['Category'] or ('Concerns' if n['Level'] == 'Concern' else ''),
            OFFERS_COL: '' if p['suggested'] else 'Yes',
            'Where it came from': 'Listed by the client' if p['listed'] else ('Suggested from the taxonomy, not listed' if p['suggested'] else 'Parent of a listed item'),
            'Recommendation': rec, 'Why': p['why'], 'Parent page': parent_labels if n['Level'] in ('Sub-Service', 'Brand / Device') else '',
            'Primary keyword': head['Keyword'] if head is not None else '',
            'Primary keyword volume (national)': int(head['Volume']) if head is not None else None,
            'Primary keyword difficulty': num(head['Keyword Difficulty']) if head is not None else None,
            'Primary keyword CPC (USD)': (round(num(head['CPC'], float), 2) if num(head['CPC'], float) is not None else None) if head is not None else None,
            'Highest keyword in the whole service (national)': whole_service(tax, n) if n['Level'] == 'Service' else '',
            f'Related keywords (top {RELATED_KEYWORDS_SHOWN}, volume)': fmt_keywords(p['kw'], RELATED_KEYWORDS_SHOWN),
            'Keywords in taxonomy': p['count'],
            'City-modified searches (not listed)': p['city_count'],
            'Sections searchers look for (keywords)': modifier_counts(p['kw']['Keyword']),
            'Mention on this page as a section': ', '.join(mentions[key]) if p['own'] else '',
            LINKS_COL: '\n'.join(links_out.get(p['label'], [])),
            ANCHOR_COL: '',
            'Notes': '. '.join(note)})
    pages = pd.DataFrame(rows)
    for c in ('Primary keyword volume (national)', 'Primary keyword difficulty'):
        pages[c] = pages[c].astype('Int64')

    kwrows = []
    for key, p in ordered:
        target = p['label'] if p['own'] else ', '.join(plan[k]['label'] for k in p['parents'])
        for _, r in p['kw'].iterrows():
            mods = [m for m, pat in MODIFIERS.items() if re.search(pat, r['Keyword'].lower())]
            kwrows.append({'Target page': target, 'Topic': p['label'], 'Level': p['node']['Level'],
                           'Keyword': r['Keyword'], 'Volume (national)': int(r['Volume']),
                           'Keyword difficulty': num(r['Keyword Difficulty']),
                           'CPC (USD)': round(num(r['CPC'], float), 2) if num(r['CPC'], float) is not None else None,
                           'Near me': 'Y' if r['near_me'] else '', 'Modifier': ', '.join(mods)})
    keywords = pd.DataFrame(kwrows)

    skipped = pd.DataFrame(skipped, columns=['input', 'kind', 'reason']).rename(columns={'input': 'What was typed', 'kind': 'List', 'reason': 'Why it is not in the plan'})

    # checks
    checks = []
    own_labels = {p['label'] for p in plan.values() if p['own']}
    checks.append(('Every listed item resolved to a taxonomy row or a custom concern', True))
    checks.append(('Every Section row has a parent page that is an own page', all(plan[k]['own'] for p in plan.values() if not p['own'] for k in p['parents']) and all(p['parents'] for p in plan.values() if not p['own'])))
    checks.append(('Every internal link joins two own pages', all(l['From page'] in own_labels and l['To page'] in own_labels for l in links)))
    checks.append(('No page label appears twice', len(pages['Service / sub-service']) == pages['Service / sub-service'].nunique()))
    checks.append(('Keywords tab rows equal the Pages tab keyword counts', len(keywords) == int(pages['Keywords in taxonomy'].sum())))
    checks.append(('No not-recommended item is in the plan', all(not NOT_RECOMMENDED.search(p['node']['Status / Notes']) for p in plan.values())))

    read_me = [
        ('New site keyword research', a.client or ''),
        ('Built from', f'{tax.version}. Taxonomy keyword list: {len(tax.kw):,} keywords. Nothing was looked up live.'),
        ('Volume: read this first', VOLUME_LABEL),
        ('How to read the Pages tab', 'One row per service, sub-service, brand or device and concern in the plan. "Own page" rows need a page. "Section on ..." rows are too small to need their own page: '
                                      'cover them as a section on the parent page named, and use their keywords for that section.'),
        ('Client offers it? column', 'Yes is filled in for what the client listed and for the parent Service of a listed item. Rows left blank (yellow) are Sub-Services and Brands / Devices the client did not list but that have '
                                     f'a keyword of {CONFIRM_MIN_VOLUME:,}+ volume (all unlisted dental items, since dental has no minimum). Ask the client, then fill in Yes or No. '
                                     'A No means no page: drop the row and skip links to it.'),
        ('Page or section rule', f'A Sub-Service or Brand / Device gets its own page when its highest-volume keyword is {PAGE_MIN_VOLUME:,} or more. '
                                 'Services, concerns and dental items the client lists always get a page (no minimum volume for dental). Highest keyword is used, not a sum, because many keywords are the same search worded differently.'),
        ('Service rows', 'A Service row counts only searches that name the service itself. Searches for its brands and devices (for example Botox under Neurotoxin) sit on their own rows, so the Service row also shows the highest keyword anywhere under the service to compare services fairly.'),
        ('Related keywords', f'Top {RELATED_KEYWORDS_SHOWN} by volume on the Pages tab. All of them are on the Keywords tab. City-modified searches (a city name in the keyword) are left out of every figure and only counted.'),
        ('Internal links', 'The "Internal links out" column lists the pages each page should link to, with a priority. Built from the taxonomy hierarchy: Service and Sub-Service pages link both ways, '
                           'Brand / Device pages link both ways to the Sub-Service (or Service) pages above them, Sub-Services under one Service link to each other (low priority), '
                           'and each Concern page links both ways to the Service or Sub-Service pages that treat it. Sections have no link of their own.'),
        ('Anchor text', 'Not suggested. The SEO fills in the anchor text to use for links to each page in the yellow column.'),
        ('Sections searchers look for', 'Counts of keywords with a cost, before & after, recovery / risks, comparison, candidacy or best / top word. A simple word check that suggests sections to add to the page; it does not change any page decision.'),
        ('Dental', 'Dental is in the plan with no minimum volume: every listed dental service, sub-service, brand and concern gets its own page. The taxonomy has keyword data for dental concerns only, so other dental rows show no keywords and a note to research volume separately.'),
        ('Custom concerns', f'A concern the taxonomy does not have can be kept as a target anyway ("{CUSTOM_CONCERN}" in the selection). It gets a Concern page '
                            'with no keywords, volume, difficulty or CPC (research those separately), and links only to the Service or Sub-Service pages chosen for it. '
                            'Add it to service-taxonomy.xlsx so the next plan has its keywords.'),
        ('Left out', 'Treatments the taxonomy marks as not approved, investigational or discontinued (listed on the Not in the plan tab), and local pages. City searches are not part of this workbook.'),
        ('What the client listed', '; '.join(f"{r['kind']}: {r['input']}" for r, n in listed)),
        ('Warnings', ' | '.join(warnings) if warnings else 'None'),
    ]
    out = Path(a.out)
    with pd.ExcelWriter(out, engine='openpyxl') as xw:
        pages.to_excel(xw, sheet_name='Pages', index=False)
        keywords.to_excel(xw, sheet_name='Keywords', index=False)
        skipped.to_excel(xw, sheet_name='Not in the plan', index=False)
        pd.DataFrame(read_me, columns=['Item', 'Detail']).to_excel(xw, sheet_name='Read Me', index=False)
    style(out)
    to_confirm = int((pages[OFFERS_COL] == '').sum())
    print(f'Wrote {out}')
    print(f"Pages tab: {len(pages)} rows ({(pages['Recommendation'] == 'Own page').sum()} own pages, "
          f"{(pages['Recommendation'] != 'Own page').sum()} sections). Client offers it? left blank to ask the client: {to_confirm}. "
          f"Internal links: {len(links)}. Keywords: {len(keywords)}. Not in the plan: {len(skipped)}.")
    for w in warnings:
        print('WARNING:', w)
    ok = True
    for name, passed in checks:
        print(('PASS ' if passed else 'FAIL ') + name)
        ok &= bool(passed)
    if not ok:
        sys.exit(1)


def style(path):
    wb = load_workbook(path)
    head_fill = PatternFill('solid', fgColor='1F3864')
    yellow = PatternFill('solid', fgColor='FFF2CC')
    for ws in wb:
        for c in ws[1]:
            c.font = Font(bold=True, color='FFFFFF')
            c.fill = head_fill
            c.alignment = Alignment(wrap_text=True, vertical='center')
        ws.freeze_panes = 'A2'
        for col in ws.columns:
            letter = get_column_letter(col[0].column)
            longest = max((len(str(c.value)) for c in col[:200] if c.value is not None), default=10)
            ws.column_dimensions[letter].width = min(max(12, longest + 2), 60)
            for c in col[1:]:
                c.alignment = Alignment(wrap_text=True, vertical='top')
        if ws.title != 'Read Me':
            ws.auto_filter.ref = ws.dimensions
    rm = wb['Read Me']
    rm.column_dimensions['A'].width = 28
    rm.column_dimensions['B'].width = 120
    for row in rm.iter_rows(min_row=2):
        row[0].font = Font(bold=True)
    rm['B4'].fill = yellow
    rm['A4'].fill = yellow
    pw = wb['Pages']
    col = {c.value: c.column for c in pw[1]}
    offers, anchor, rec = col[OFFERS_COL], col[ANCHOR_COL], col['Recommendation']
    dv = DataValidation(type='list', formula1='"Yes,No"', allow_blank=True)
    pw.add_data_validation(dv)
    dv.add(f'{get_column_letter(offers)}2:{get_column_letter(offers)}{pw.max_row}')
    for r in range(2, pw.max_row + 1):
        own = pw.cell(r, rec).value == 'Own page'
        pw.cell(r, offers).fill = yellow
        if own:
            pw.cell(r, anchor).fill = yellow
        else:
            for c in range(1, pw.max_column + 1):
                pw.cell(r, c).font = Font(color='595959')
    for name in (OFFERS_COL, ANCHOR_COL):
        pw.cell(1, col[name]).fill = PatternFill('solid', fgColor='BF9000')
    wb.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('match')
    m.add_argument('--services', default='')
    m.add_argument('--products', default='')
    m.add_argument('--concerns', default='')
    m.add_argument('--out', default='work')
    m.add_argument('--taxonomy', default=str(DEFAULT_TAXONOMY))
    b = sub.add_parser('build')
    b.add_argument('--selection', required=True)
    b.add_argument('--client', default='')
    b.add_argument('--out', required=True)
    b.add_argument('--taxonomy', default=str(DEFAULT_TAXONOMY))
    a = ap.parse_args()
    {'match': cmd_match, 'build': cmd_build}[a.cmd](a)


if __name__ == '__main__':
    main()
