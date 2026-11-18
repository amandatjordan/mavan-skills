#!/usr/bin/env python3
"""New-site content roadmap: the pages (and blogs) to write for a new site, at most 50, from the new-site keyword
research workbook, the new-site keyword gap workbook and the bundled blog taxonomy.

  roadmap.py preflight --research R.xlsx --gap G.xlsx [--extras "Name|Type; Name|Type"] --out work
  roadmap.py match     --research R.xlsx --gap G.xlsx --out work
  roadmap.py build     --research R.xlsx --gap G.xlsx --match work/gap_match.tsv [--extras "..."] [--client "Name"] --out NAME.xlsx

Every count, join, rank and cut is done here. Nothing is typed or estimated by hand. Volumes are never added together.
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
DEFAULT_BLOG = SKILL_DIR / 'references' / 'blog-taxonomy.xlsx'

# --- Rules (explained in references/rules.md) --------------------------------------------------
MAX_PAGES = 50                                   # Home, About Us, extra pages, pages and blogs all count
FIXED_PAGES = [                                  # never in the keyword sheets; always on the roadmap
    ('Home', 'Every site needs one. It is not in the keyword sheets.'),
    ('About Us', 'Every site needs one. It is not in the keyword sheets.'),
]
# Pages are added in this order until the cap is reached. Home, About Us and the SEO's extra pages come first and are never cut.
TIER_ORDER = ['Service', 'Sub-Service', 'Brand / Device', 'Blog', 'Concern']
SOURCE_RANK = {'Yes': 0, 'Implied': 1, 'Suggested': 2, 'Gap only': 3}   # within a tier: client-listed first
SOURCE_TEXT = {
    'Yes': 'The client listed it.',
    'Implied': 'Added because it is the parent of a listed item. Confirm the client offers it.',
    'Suggested': 'The taxonomy suggested it (the client did not list it) and the SEO confirmed the client offers it.',
    'Gap only': 'A service the client offers that competitors rank for. It was not in the keyword research.',
}
PRIORITIES = 'High,Medium,Low'
CUT_TAB = 'Cut for the 50-page cap'
KW_COL = 'Primary keyword (SEO: check it fits the page, then replace it or add keywords)'
ANCHOR_COL = 'Must appear on page (anchor text other pages use to link here)'
ANCHOR_SRC = 'Anchor text for links to this page (SEO fills in)'
LINKS_SRC = 'Internal links out (priority)'
LINK_TAB = 'Internal links'
LINK_LEVELS = ('Service', 'Sub-Service', 'Brand / Device')   # every one of these must receive at least one internal link
PRIORITY_COL = 'SEO priority (High / Medium / Low)'
CUT_INSTRUCTIONS = (f'These pages and blogs did not fit under the {MAX_PAGES}-page cap. The SEO makes the final list: move a row to the Roadmap tab to write it, '
                    f'or move a Roadmap row here to drop it. The columns match the Roadmap (the reason it was cut is the last column), so a row can be cut and pasted as it is. '
                    f'Keep the Roadmap at {MAX_PAGES} rows or fewer, and move a page\'s blogs with it.')
VOLUME_LABEL = ('National volume from the taxonomy keyword list (what competitors rank for, often with a city in the search). '
                'Use it to rank pages against each other. It is not local demand and not a traffic forecast.')
RESEARCH_COLS = ['Level', 'Service / sub-service', 'Recommendation', 'Primary keyword', 'Primary keyword volume (national)',
                 'Parent page', 'Mention on this page as a section', 'Client offers it? (Yes / No)', 'Where it came from', ANCHOR_SRC, LINKS_SRC, 'Why']
MATCH_COLS = ['gap_service', 'offered', 'gap_keywords', 'local_gap_keywords', 'page', 'level', 'status', 'candidates']
GAP_LEVELS = ('Service', 'Sub-Service', 'Brand / Device', 'Concern')


def s(v):
    return '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def norm(text):
    t = ''.join(c for c in unicodedata.normalize('NFKD', str(text)) if not unicodedata.combining(c)).lower().replace('&', ' and ')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', re.sub(r'\(family\)', ' ', t))).strip()


def tokens(text):
    return {w[:-1] if len(w) > 3 and w.endswith('s') and not w.endswith('ss') else w for w in norm(text).split()}


def num(v):
    try:
        return None if s(v) == '' else float(v)
    except ValueError:
        return None


def find_col(df, start):
    hits = [c for c in df.columns if str(c).lower().startswith(start.lower())]
    return hits[0] if hits else None


def parse_extras(text):
    out, seen = [], set()
    for part in re.split(r'[;\n]+', text or ''):
        if not part.strip():
            continue
        name, _, kind = part.partition('|')
        name, kind = name.strip(), kind.strip() or 'Other'
        if name and norm(name) not in seen:
            seen.add(norm(name))
            out.append((name, kind))
    return out


# --- Inputs ------------------------------------------------------------------------------------
def read_research(path):
    xl = pd.ExcelFile(path)
    if 'Pages' not in xl.sheet_names:
        return None, ['Research workbook has no "Pages" tab. It must be the output of new-site-keyword-research.']
    pages = xl.parse('Pages').fillna('')
    missing = [c for c in RESEARCH_COLS if c not in pages.columns]
    if missing:
        return None, ['Research Pages tab is missing columns: ' + ', '.join(missing)]
    # Only rows the client offers are used. A blank is a suggested row nobody has asked the client about yet, and a No is not offered.
    offers = pages['Client offers it? (Yes / No)'].astype(str).str.strip().str.lower()
    kept = pages[offers == 'yes'].copy()
    kept.attrs['blank'] = int((offers == '').sum())
    kept.attrs['no'] = int((offers == 'no').sum())
    return kept, []


def read_gap(path):
    xl = pd.ExcelFile(path)
    if 'Service opportunities' not in xl.sheet_names:
        return None, ['Gap workbook has no "Service opportunities" tab. It must be the output of new-site-keyword-gap.']
    g = xl.parse('Service opportunities').fillna('')
    need = {'Service': 'Service', 'offered': 'Offered by our client', 'sig': 'Keywords with 2+ in top 10 or 1+ in top 3',
            'lsig': 'Local keywords with 2+ in top 10 or 1+ in top 3'}
    cols = {k: ('Service' if k == 'Service' else find_col(g, v)) for k, v in need.items()}
    missing = [need[k] for k, v in cols.items() if v is None or v not in g.columns]
    if missing:
        return None, ['Gap Service opportunities tab is missing columns: ' + ', '.join(missing)]
    g = g.rename(columns={cols['offered']: 'offered', cols['sig']: 'sig', cols['lsig']: 'lsig'})
    return g[['Service', 'offered', 'sig', 'lsig']], []


def read_blog(path):
    xl = pd.ExcelFile(path)
    look = xl.parse('Lookup').fillna('')
    rules = xl.parse('Blog Rules').fillna('')
    over = xl.parse('Overrides').fillna('') if 'Overrides' in xl.sheet_names else pd.DataFrame()
    title = s(pd.read_excel(path, 'Read Me', header=None).iloc[0, 0])
    return look, rules, over, title


# --- preflight ---------------------------------------------------------------------------------
def cmd_preflight(a):
    fails, warns, info = [], [], []
    pages, prob = read_research(a.research) if a.research else (None, ['Research workbook not provided (output of new-site-keyword-research).'])
    fails += prob
    gap, prob = read_gap(a.gap) if a.gap else (None, ['Gap workbook not provided (output of new-site-keyword-gap).'])
    fails += prob
    extras = parse_extras(a.extras)
    if not Path(a.blog_taxonomy).exists():
        fails.append('The bundled blog taxonomy is missing from the skill.')
    if pages is not None:
        own = pages[pages['Recommendation'] == 'Own page']
        info.append(f'Research: {len(pages)} rows the client offers, {len(own)} own pages, {len(pages) - len(own)} sections.')
        if pages.attrs.get('blank'):
            warns.append(f"{pages.attrs['blank']} research rows have a blank \"Client offers it?\". They are left out until the SEO fills in Yes. A No is never used.")
        if len(own) == 0:
            fails.append('The research Pages tab has no "Own page" rows.')
        noanchor = int((own[ANCHOR_SRC].astype(str).str.strip() == '').sum())
        if noanchor:
            warns.append(f'{noanchor} pages have no anchor text on the research Pages tab, so "Must appear on page" is blank for them.')
    if gap is not None:
        blank = int((gap['offered'].astype(str).str.strip() == '').sum())
        info.append(f'Gap: {len(gap)} services.')
        if blank:
            warns.append(f'{blank} gap services have a blank "Offered by our client". Only Yes counts as offered; the rest are left out.')
    if len(extras) > MAX_PAGES - len(FIXED_PAGES):
        fails.append(f'{len(extras)} extra pages plus Home and About Us is more than {MAX_PAGES}.')
    info.append(f'Extra pages from the SEO: {len(extras)}' + (' (' + ', '.join(n for n, _ in extras) + ')' if extras else ''))
    lines = ['# Preflight', ''] + [f'- INFO {i}' for i in info] + [f'- WARN {w}' for w in warns] + [f'- FAIL {f}' for f in fails]
    lines += ['', 'NOT READY' if fails else 'READY']
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'preflight.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    if fails:
        sys.exit(1)


# --- match gap services to research pages ------------------------------------------------------
def cmd_match(a):
    pages, prob = read_research(a.research)
    gap, prob2 = read_gap(a.gap)
    if prob or prob2:
        sys.exit('; '.join(prob + prob2))
    labels = [x for x in pages['Service / sub-service'] if s(x)]
    rows = []
    for _, g in gap.iterrows():
        gt = tokens(g['Service'])
        last = lambda p: tokens(p.split(' > ')[-1])
        exact = [p for p in labels if last(p) == gt or tokens(p) == gt]
        partial = sorted([p for p in labels if gt and (gt <= tokens(p) or (last(p) and last(p) <= gt))], key=lambda p: (p.count(' > '), p))
        cand = exact or partial
        rows.append({'gap_service': s(g['Service']), 'offered': s(g['offered']), 'gap_keywords': int(num(g['sig']) or 0),
                     'local_gap_keywords': int(num(g['lsig']) or 0), 'page': cand[0] if cand else '',
                     'level': '' if cand else 'Service', 'status': 'ok' if exact else ('review' if partial else 'none'),
                     'candidates': '; '.join(cand[:5])})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'gap_match.tsv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=MATCH_COLS, delimiter='\t')
        w.writeheader()
        w.writerows(rows)
    print(f'Wrote {out / "gap_match.tsv"}: {len(rows)} gap services')
    for r in rows:
        if r['status'] != 'ok':
            print(f"  {r['status'].upper():6} {r['gap_service']} (offered: {r['offered'] or 'blank'}) -> {r['page'] or 'no research page'}   [{r['candidates']}]")


# --- build -------------------------------------------------------------------------------------
def parse_links(text, warnings):
    """The research sheet's "Internal links out (priority)" cell: one "Page name (High)" per line, optionally followed by [a note]."""
    out = []
    for line in text.split('\n'):
        if not line.strip():
            continue
        m = re.match(r'^(.*?) \((High|Medium|Low)\)(?: \[.*\])?\s*$', line.strip())
        if m:
            out.append((m.group(1).strip(), m.group(2)))
        else:
            warnings.append(f'Could not read this internal link on the research sheet: "{line.strip()}".')
    return out


def build_links(kept_pages, kept_blogs):
    """Links between the pages on the roadmap. The research sheet's links are used when both pages are on the roadmap. A Service,
    Sub-Service or Brand / Device page that still has no link pointing at it gets one from its parent page (its Service if the parent
    is not on the roadmap, Home if neither is)."""
    byname = {c['label']: c for c in kept_pages}
    links = {}
    for c in kept_pages:
        for target, prio in c['links']:
            if target in byname and target != c['label']:
                links.setdefault((c['label'], target), (prio, 'From the keyword research'))
    added = 0
    for c in kept_pages:
        if c['level'] in LINK_LEVELS and not any(to == c['label'] for (_, to) in links):
            src = c['parent'] if c['parent'] in byname else (c['service'] if c['service'] in byname and c['service'] != c['label'] else 'Home')
            links[(src, c['label'])] = ('High', 'Added so every page gets a link')
            added += 1
    rank = {'Home': -1, **{c['label']: i for i, c in enumerate(kept_pages)}}
    prio = {'High': 0, 'Medium': 1, 'Low': 2}
    rows = [{'From page': f, 'To page': to, 'Priority': p, 'Anchor text': byname[to]['own_anchor'], 'Where this link came from': src}
            for (f, to), (p, src) in sorted(links.items(), key=lambda kv: (rank[kv[0][0]], prio[kv[1][0]], rank[kv[0][1]]))]
    for b in kept_blogs:
        if b['page'] in byname:
            rows.append({'From page': b['label'], 'To page': b['page'], 'Priority': 'High', 'Anchor text': byname[b['page']]['own_anchor'],
                         'Where this link came from': 'The blog links to its page'})
    return pd.DataFrame(rows, columns=['From page', 'To page', 'Priority', 'Anchor text', 'Where this link came from']), added, byname


def build_candidates(pages, match, warnings):
    """One dict per page that could be written, plus section rows (not pages). A gap service the client does not offer is dropped, not listed."""
    cands, sections = [], []
    for _, r in pages.iterrows():
        label, level = s(r['Service / sub-service']), s(r['Level'])
        came = s(r['Where it came from']).lower()
        base = {'label': label, 'level': level, 'source': 'Implied' if came.startswith('parent') else 'Yes' if came.startswith('listed') else 'Suggested',
                'parent': s(r['Parent page']), 'keyword': s(r['Primary keyword']), 'volume': num(r['Primary keyword volume (national)']),
                'sections': s(r['Mention on this page as a section']), 'why': s(r['Why']), 'service': label.split(' > ')[0],
                'anchor': s(r[ANCHOR_SRC]), 'own_anchor': s(r[ANCHOR_SRC]), 'links': parse_links(s(r[LINKS_SRC]), warnings)}
        (cands if s(r['Recommendation']) == 'Own page' else sections).append(base)
    # a section's anchor text is for links to its topic, which live on the parent page: the parent must contain it
    by_label = {c['label']: c for c in cands}
    for sec in sections:
        par = by_label.get(sec['parent'])
        if par and sec['anchor'] and norm(sec['anchor']) not in {norm(x) for x in re.split(r'[;\n]+', par['anchor'])}:
            par['anchor'] = (par['anchor'] + '; ' if par['anchor'] else '') + sec['anchor']
    names = {norm(c['label']) for c in cands + sections}
    for m in match:
        if m['page']:
            if m['offered'].lower() == 'no':
                warnings.append(f"Gap says the client does not offer \"{m['gap_service']}\" but it is matched to the research page \"{m['page']}\".")
            continue
        if m['offered'].lower() != 'yes':
            continue
        if norm(m['gap_service']) in names:
            sys.exit(f'Gap service "{m["gap_service"]}" has no page set but matches a research page name. Set its page in the match file.')
        cands.append({'label': m['gap_service'], 'level': m['level'], 'source': 'Gap only', 'parent': '', 'keyword': '', 'volume': None,
                      'sections': '', 'why': '', 'service': m['gap_service'], 'anchor': '', 'own_anchor': '', 'links': []})
    return cands, sections


def attach_gap(cands, match):
    sig = {}
    for m in match:
        if m['page']:
            sig.setdefault(m['page'], [0, []])
            sig[m['page']][0] += int(m['gap_keywords']) + int(m['local_gap_keywords'])
            sig[m['page']][1].append(m['gap_service'])
    for c in cands:
        if c['source'] == 'Gap only':
            m = next(m for m in match if m['gap_service'] == c['label'])
            c['gap'], c['gap_note'] = int(m['gap_keywords']) + int(m['local_gap_keywords']), 'from the gap workbook'
        elif c['label'] in sig:
            c['gap'], c['gap_note'] = sig[c['label']][0], 'gap service: ' + ', '.join(sig[c['label']][1])
        elif c['level'] in ('Sub-Service', 'Brand / Device') and c['service'] in sig:
            c['gap'], c['gap_note'] = sig[c['service']][0], f"inherited from the {c['service']} service"
        else:
            c['gap'], c['gap_note'] = 0, ''


def rank_key(c):
    return (SOURCE_RANK[c['source']], -c['gap'], -(c['volume'] or 0), c['label'])


def blog_rows(kept, sections, look, rules, over, notes):
    """Two blog rows per kept Service / Sub-Service (and per Brand / Device the blog taxonomy adds), linked to the page that exists."""
    lk = {s(r['Key']): r for _, r in look.iterrows()}
    adds = {}
    for _, r in over.iterrows():
        if s(r.get('Action')) == 'Add' and s(r.get('Level')) == 'Brand / Device':
            adds[f"{s(r['Service'])} > {s(r['Brand / Device'])}"] = r
    tmpl = {(s(r['Level']), int(r['Blog #'])): s(r['Blog angle (template)']) for _, r in rules.iterrows() if s(r['Level']) and s(r['Blog #']) != ''}
    kept_labels = {c['label'] for c in kept}
    nodes = []
    for c in kept:
        if c['level'] in ('Service', 'Sub-Service'):
            nodes.append((c, c['label']))
    for sec in sections:
        if sec['level'] == 'Sub-Service' and sec['parent'] in kept_labels:
            nodes.append((sec, sec['parent']))
    for c in kept:
        if c['label'] in adds:
            nodes.append((c, c['label']))
    rows, seen = [], set()
    for node, page in nodes:
        label = node['label']
        if label in seen:
            continue
        seen.add(label)
        parts = label.split(' > ')
        if node['level'] == 'Service':
            key = f'Service|{parts[0]}||'
        elif node['level'] == 'Sub-Service':
            key = f'Sub-Service|{parts[0]}|{parts[-1]}|'
        else:
            key = None
        row = adds.get(label) if key is None else lk.get(key)
        if row is None:
            notes.append(f'No blogs for {label}: it is not in the blog taxonomy.')
            continue
        if s(row.get('Action')) == 'Exclude':
            notes.append(f'No blogs for {label}: excluded in the blog taxonomy.')
            continue
        for n in (1, 2):
            angle = s(row.get(f'Blog {n} angle'))
            if not angle and (node['level'], n) in tmpl:
                angle = tmpl[(node['level'], n)].replace('{node}', parts[-1]).replace('{service}', parts[0])
            if angle:
                rows.append({'label': f'Blog {n}: {angle}', 'level': 'Blog', 'node': label, 'page': page, 'source': node['source'],
                             'is_own': page == label})
    return rows


def cmd_build(a):
    pages, prob = read_research(a.research)
    gap, prob2 = read_gap(a.gap)
    if prob or prob2:
        sys.exit('; '.join(prob + prob2))
    with open(a.match, newline='') as f:
        match = list(csv.DictReader(f, delimiter='\t'))
    labels = {s(x) for x in pages['Service / sub-service']}
    bad = [m['gap_service'] for m in match if m['page'] and m['page'] not in labels]
    if bad:
        sys.exit('These gap services point to a page that is not on the research Pages tab: ' + '; '.join(bad))
    bad = [m['gap_service'] for m in match if not m['page'] and m['offered'].lower() == 'yes' and m['level'] not in GAP_LEVELS]
    if bad:
        sys.exit('Gap-only services need a level (Service, Sub-Service, Brand / Device or Concern): ' + '; '.join(bad))
    gap_names = set(gap['Service'].map(s))
    missing = [m['gap_service'] for m in match if m['gap_service'] not in gap_names]
    if missing:
        sys.exit('The match file lists gap services that are not in the gap workbook: ' + '; '.join(missing))
    look, rules, over, blog_title = read_blog(a.blog_taxonomy)
    extras = parse_extras(a.extras)
    warnings = []
    cands, sections = build_candidates(pages, match, warnings)
    attach_gap(cands, match)

    slots = MAX_PAGES - len(FIXED_PAGES) - len(extras)
    if slots < 0:
        sys.exit(f'{len(extras)} extra pages plus Home and About Us is more than {MAX_PAGES}.')
    by_tier = {t: sorted([c for c in cands if c['level'] == t], key=rank_key) for t in ('Service', 'Sub-Service', 'Brand / Device', 'Concern')}
    main = by_tier['Service'] + by_tier['Sub-Service'] + by_tier['Brand / Device']
    kept, cut = main[:slots], main[slots:]
    blogs_all = blog_rows(kept, sections, look, rules, over, warnings)
    room = slots - len(kept)
    kept_blogs, cut_blogs = blogs_all[:room], blogs_all[room:]
    room -= len(kept_blogs)
    kept_concerns, cut_concerns = by_tier['Concern'][:max(room, 0)], by_tier['Concern'][max(room, 0):]
    skipped_blog_nodes = [c['label'] for c in cut if c['level'] in ('Service', 'Sub-Service')]

    # --- assemble roadmap rows
    rows = []

    cut_rows = []

    def add(page, ptype, content, why, parent='', kw='', vol=None, gapn='', sect='', anchor='', into=None):
        (rows if into is None else into).append({'Page': page, 'Page type': ptype, 'Content to write': content, 'Why it is on the roadmap': why, 'Parent page / links to': parent,
                     KW_COL: kw, 'Primary keyword volume (national)': vol, ANCHOR_COL: anchor,
                     'Competitor gap keywords (2+ in top 10 or 1+ in top 3)': gapn, 'Sections to cover on this page': sect,
                     PRIORITY_COL: ''})

    for name, why in FIXED_PAGES:
        add(name, name, 'Page', why)
    for name, kind in extras:
        add(name, f'Extra: {kind}', 'Page', 'Added by the SEO in the preflight. Set its priority.')
    def page_rows(c, into=None):
        extra = '' if re.search(r'client lists', c['why']) else c['why']
        why = SOURCE_TEXT[c['source']] + (' ' + extra + ('' if extra.endswith('.') else '.') if extra else '')
        add(c['label'], c['level'], 'Page', why, c['parent'], c['keyword'], c['volume'],
            f"{c['gap']} ({c['gap_note']})" if c['gap_note'] else '', c['sections'], c['anchor'], into)

    for c in kept:
        page_rows(c)
    def blog_row(b, into=None):
        add(b['label'], 'Blog', 'Blog post', f"Companion to {b['node']}. Informational only; the writer sets the title and target query.",
            f"{b['page']} page" + ('' if b['is_own'] else f" ({b['node']} is covered as a section there)"), into=into)

    for b in kept_blogs:
        blog_row(b)
    for c in kept_concerns:
        page_rows(c)
    roadmap = pd.DataFrame(rows)
    link_df, links_added, link_pages = build_links(kept + kept_concerns, kept_blogs)
    roadmap.insert(0, '#', range(1, len(roadmap) + 1))

    # --- over the cap: same columns as the Roadmap, so the SEO can move a row between the two tabs. The reason is the last column.
    # (Sections are on their parent page, and what the client does not offer is not listed anywhere.)
    reasons = []
    for c in cut:
        page_rows(c, cut_rows)
        reasons.append(f"Ranked below the pages that were kept in the {c['level']} group.")
    for b in cut_blogs:
        blog_row(b, cut_rows)
        reasons.append('Blogs come after Service, Sub-Service and Brand / Device pages.')
    for c in cut_concerns:
        page_rows(c, cut_rows)
        reasons.append('Concerns come last.')
    not_df = pd.DataFrame(cut_rows)
    if len(not_df):
        not_df.insert(0, '#', '')
        not_df[f'Why it is over the {MAX_PAGES}-page cap'] = reasons
    if skipped_blog_nodes:
        warnings.append('Blogs were not considered for pages that were cut: ' + '; '.join(skipped_blog_nodes) + '. Their 2 blogs each come with them if the SEO moves the page onto the Roadmap.')

    # --- checks
    checks = []
    checks.append((f'Roadmap has at most {MAX_PAGES} rows ({len(roadmap)})', len(roadmap) <= MAX_PAGES))
    checks.append(('Home and About Us are on the roadmap', {'Home', 'About Us'} <= set(roadmap['Page'])))
    checks.append(('Every extra page the SEO listed is on the roadmap', all(n in set(roadmap['Page']) for n, _ in extras)))
    checks.append(('No page appears twice', len(roadmap) == roadmap['Page'].map(norm).nunique()))
    order = {'Home': 0, 'About Us': 1, 'Service': 3, 'Sub-Service': 4, 'Brand / Device': 5, 'Blog': 6, 'Concern': 7}
    seq = [order.get(t, 2) for t in roadmap['Page type']]
    checks.append(('Rows follow the order Home, About Us, extras, Service, Sub-Service, Brand / Device, Blog, Concern', seq == sorted(seq)))
    page_names = set(roadmap['Page'])
    checks.append(('Every blog links to a page that is on the roadmap',
                   all(re.sub(r' page.*$', '', p) in page_names for p in roadmap.loc[roadmap['Page type'] == 'Blog', 'Parent page / links to'])))
    checks.append(('Every roadmap page (not extra) came from the research workbook or an offered gap service',
                   all(c['label'] in labels or c['source'] == 'Gap only' for c in kept + kept_concerns)))
    checks.append(('Cut pages plus kept pages equal all candidates', len(kept) + len(cut) + len(kept_concerns) + len(cut_concerns) == len(cands)))

    page_link = link_df[link_df['Where this link came from'] != 'The blog links to its page']
    checks.append(('Every Service, Sub-Service and Brand / Device page on the roadmap receives a link from another page',
                   all(c['label'] in set(page_link['To page']) for c in kept if c['level'] in LINK_LEVELS)))
    ok_names = set(link_pages) | {'Home'} | {b['label'] for b in kept_blogs}
    checks.append(('Every link joins two pages that are on the roadmap', all(f in ok_names and t in ok_names for f, t in zip(link_df['From page'], link_df['To page']))))
    checks.append(('No page links to itself', all(f != t for f, t in zip(link_df['From page'], link_df['To page']))))
    if links_added:
        warnings.append(f'{links_added} links were added because no link pointed at those pages (see "Where this link came from" on the Internal links tab).')

    note = ' | '.join(warnings) if warnings else 'None'
    read_me = [
        ('New site content roadmap', a.client or ''),
        ('Built from', f'The new-site keyword research workbook, the new-site keyword gap workbook and the blog taxonomy ({blog_title}). Nothing was looked up live.'),
        ('Volume: read this first', VOLUME_LABEL),
        ('What this is', f'The pages and blog posts we recommend writing content for, {MAX_PAGES} at most. Home, About Us and every extra page the SEO listed always count toward the {MAX_PAGES} and are never cut.'),
        ('Order', 'Home, About Us, the SEO\'s extra pages, then Service, Sub-Service, Brand / Device, Blog and Concern pages, until the cap is reached. Inside a group: pages the client listed first, then Implied parents, then gap-only services; ties go to more competitor gap keywords, then higher volume.'),
        ('Competitor gap keywords', 'Keywords with 2+ competitors in the top 10 or 1+ in the top 3, non-local plus local, from the gap workbook service matched to the page. A Sub-Service or Brand / Device with no gap service of its own shows its Service\'s number (marked "inherited").'),
        ('Keywords: SEO to check', 'The primary keyword column (yellow) comes from the keyword research and is only the highest-volume search for the page. Some are searches from someone looking at pictures or reading about a topic, not looking for the service (for example "face with wrinkles"). Check each one, then replace it, or add keywords to the same cell. Home, About Us and extra pages have none: add them.'),
        ('Must appear on page', 'The anchor text the keyword research sheet lists for links to this page. Content must include these words on the page, so other pages can link to it with them. A Sub-Service or Brand / Device that is only a section on a parent page adds its anchor text to the parent page. Blank where the research sheet has none; Home, About Us, extra pages and blogs have none.'),
        ('Internal links tab', 'Every link between pages on the roadmap: from page, to page, priority and the anchor text (the research sheet\'s anchor text for the page being linked to). The links come from the keyword research sheet. Where a page would receive no link at all (the pages that linked to it were cut, it is not linked from the research, or it came from the gap), a link from its parent page, or from Home, is added and marked. Blogs link to their page. If the SEO moves pages between the Roadmap and Cut tabs, the links to and from those pages need updating by hand.'),
        ('SEO priority', 'The last yellow column is for the SEO. The roadmap order is a recommendation: the SEO makes the final call and can change the priority of any page (High, Medium or Low).'),
        ('Blogs', 'Two blog posts per Service and Sub-Service page from the blog taxonomy (prep / maintenance and choosing a provider). Titles are not set: the writer picks each post\'s title and query. Blogs must not promise results: say results vary and defer to the provider\'s own instructions.'),
        ('Sections', 'Sub-Services and Brands / Devices the research workbook marked "Section on ..." are not pages. They appear in "Sections to cover on this page" on their parent page.'),
        ('Cut tab', f'Only exists when something is over the {MAX_PAGES}-page cap: the pages and blogs that did not fit, with the same columns as the Roadmap and the reason in the last column. The SEO moves rows between the two tabs to make the final list, keeping the Roadmap at {MAX_PAGES} or fewer.'),
        ('Warnings', note),
    ]
    out = Path(a.out)
    with pd.ExcelWriter(out, engine='openpyxl') as xw:
        pd.DataFrame(read_me, columns=['Item', 'Detail']).to_excel(xw, sheet_name='Read Me', index=False)
        roadmap.to_excel(xw, sheet_name='Roadmap', index=False)
        link_df.to_excel(xw, sheet_name=LINK_TAB, index=False)
        if len(not_df):
            not_df.to_excel(xw, sheet_name=CUT_TAB, index=False, startrow=1)
    style(out, len(roadmap))
    counts = roadmap['Page type'].value_counts().to_dict()
    print(f'Wrote {out}')
    print(f'Roadmap: {len(roadmap)} of {MAX_PAGES} rows. ' + ', '.join(f'{k}: {v}' for k, v in counts.items()))
    print(f'Internal links: {len(link_df)} rows ({links_added} added so every page gets a link).')
    print(f'Over the cap: {len(not_df)} rows ({len(cut)} pages, {len(cut_blogs)} blogs, {len(cut_concerns)} concerns).')
    for w in warnings:
        print('WARNING:', w)
    ok = True
    for name, passed in checks:
        print(('PASS ' if passed else 'FAIL ') + name)
        ok &= bool(passed)
    if not ok:
        sys.exit(1)


def style(path, n):
    wb = load_workbook(path)
    head, yellow = PatternFill('solid', fgColor='1F3864'), PatternFill('solid', fgColor='FFF2CC')
    for ws in wb:
        top = 2 if ws.title == CUT_TAB else 1          # the cut tab has an instruction row above its headers
        for c in ws[top]:
            c.font, c.fill, c.alignment = Font(bold=True, color='FFFFFF'), head, Alignment(wrap_text=True, vertical='center')
        ws.freeze_panes = f'A{top + 1}'
        for col in ws.columns:
            longest = max((len(str(c.value)) for c in col[top - 1:200] if c.value is not None), default=10)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(12, longest + 2), 60)
            for c in col[top:]:
                c.alignment = Alignment(wrap_text=True, vertical='top')
        if ws.title != 'Read Me':
            ws.auto_filter.ref = f'A{top}:{get_column_letter(ws.max_column)}{ws.max_row}'
    if CUT_TAB in wb.sheetnames:
        cw = wb[CUT_TAB]
        cw['A1'] = CUT_INSTRUCTIONS
        cw.merge_cells(start_row=1, start_column=1, end_row=1, end_column=min(cw.max_column, 8))
        cw['A1'].font, cw['A1'].fill = Font(bold=True), yellow
        cw['A1'].alignment = Alignment(wrap_text=True, vertical='center')
        cw.row_dimensions[1].height = 62
    rm = wb['Read Me']
    rm.column_dimensions['A'].width, rm.column_dimensions['B'].width = 28, 120
    for row in rm.iter_rows(min_row=2):
        row[0].font = Font(bold=True)
    rm['A4'].fill = rm['B4'].fill = yellow
    ws = wb['Roadmap']
    heads = {c.value: c.column for c in ws[1]}
    for name in (KW_COL, PRIORITY_COL):
        for r in range(1, n + 2):
            ws.cell(r, heads[name]).fill = yellow if r > 1 else PatternFill('solid', fgColor='BF8F00')
        ws.column_dimensions[get_column_letter(heads[name])].width = 34
    col = get_column_letter(heads[PRIORITY_COL])
    dv = DataValidation(type='list', formula1=f'"{PRIORITIES}"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f'{col}2:{col}{n + 1}')
    wb.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('preflight', 'match', 'build'):
        p = sub.add_parser(name)
        p.add_argument('--research', required=(name != 'preflight'))
        p.add_argument('--gap', required=(name != 'preflight'))
        p.add_argument('--blog-taxonomy', default=str(DEFAULT_BLOG))
        if name != 'match':
            p.add_argument('--extras', default='')
        if name == 'build':
            p.add_argument('--match', required=True)
            p.add_argument('--client', default='')
            p.add_argument('--out', required=True)
        else:
            p.add_argument('--out', default='work')
    a = ap.parse_args()
    {'preflight': cmd_preflight, 'match': cmd_match, 'build': cmd_build}[a.cmd](a)


if __name__ == '__main__':
    main()
