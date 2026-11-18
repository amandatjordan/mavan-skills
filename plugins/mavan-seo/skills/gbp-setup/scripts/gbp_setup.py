#!/usr/bin/env python3
"""GBP setup: category recommendations from competitor local-search exports, services and products from the
new-site content roadmap, and the GBP completion checklist, as one Word document.

Commands
  preflight   check the inputs and say what is missing
  categories  count categories per export, write categories.json, service_match.tsv and descriptions.tsv for Claude to fill in
  build       read the confirmed files and write the Word document and the services / products sheet

Every count and ranking is done here. Nothing is fetched from the web.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

TOP_N = 3                    # categories kept from each export
MIN_COMPETITORS = 3          # fewer competitors in an export gets a warning (never blocks)
MIN_EXPORTS = 3              # fewer exports for a specialty gets a warning (never blocks)
CAT_COLS = ['Primary Category', 'Category 2', 'Category 3', 'Category 4', 'Category 5']
SERVICE_DESC_MAX = 275       # GBP service description
PRODUCT_NAME_MAX = 45        # GBP product name
PRODUCT_DESC_MAX = 750       # GBP product description
SERVICE_LEVELS = ('Service', 'Sub-Service')
PRODUCT_LEVELS = ('Brand / Device',)
CUT_TAB = 'Cut for the 50-page cap'

CHECKLIST = [
    ('Accurate NAP', 'Business name, address and phone number are exactly the same as on the website and everywhere else.'),
    ('Photos', 'Facility, team, exterior, interior, and results if approved.'),
    ('Services', 'Add the services listed in section 2.'),
    ('Products', 'Add the products listed in section 3.'),
    ('Hours of operation', ''),
    ('Website link', ''),
    ('Booking link', 'Only when available. This depends on the categories chosen: confirm in the GBP dashboard.'),
    ('Menu / services link', 'Only when available. This depends on the categories chosen: confirm in the GBP dashboard.'),
    ('Accessibility', ''),
    ('Social accounts', ''),
    ('Business description', ''),
]


def s(v):
    return '' if v is None or (isinstance(v, float) and v != v) else str(v).strip()


def norm(v):
    return re.sub(r'\s+', ' ', s(v).lower())


# ------------------------------------------------------------------ exports
def parse_spec(spec):
    """'Specialty|search words=path'. Returns (specialty, search, path) or raises ValueError."""
    if '|' not in spec:
        raise ValueError(f'"{spec}": use "Specialty|search words=file" (the specialty label is required)')
    spec_label, rest = spec.split('|', 1)
    if '=' in rest and not os.path.exists(rest):
        search, path = [x.strip() for x in rest.split('=', 1)]
    else:
        search, path = '', rest.strip()
    spec_label = spec_label.strip()
    if not spec_label:
        raise ValueError(f'"{spec}": the specialty label is empty')
    return spec_label, search or Path(path).stem, path


def read_export(path):
    if path.lower().endswith('.json'):
        with open(path, encoding='utf-8') as fh:
            raw = json.load(fh)
        df = pd.DataFrame((raw.get('data') if isinstance(raw, dict) else raw) or [])
    else:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_exports(specs, business):
    """Returns (exports, problems). Each export: specialty, search, path, businesses [{name, categories[]}], client_found."""
    exports, problems = [], []
    for spec in specs:
        try:
            spec_label, search, path = parse_spec(spec)
        except ValueError as e:
            problems.append(str(e))
            continue
        if not os.path.exists(path):
            problems.append(f'{path}: file not found')
            continue
        try:
            df = read_export(path)
        except Exception as e:
            problems.append(f'{path}: could not be read ({e})')
            continue
        miss = [c for c in ('Business Name', 'Primary Category') if c not in df.columns]
        if miss:
            problems.append(f'{path}: columns not found: {", ".join(miss)}')
            continue
        cols = [c for c in CAT_COLS if c in df.columns]
        seen, biz = set(), []
        for _, r in df.iterrows():
            name = s(r.get('Business Name'))
            if not name or norm(name) in seen:
                continue
            seen.add(norm(name))
            cats = []
            for c in cols:
                v = s(r.get(c))
                if v and v not in cats:
                    cats.append(v)
            biz.append({'name': name, 'categories': cats})
        exports.append({'specialty': spec_label, 'search': search, 'path': path, 'businesses': biz,
                        'client_found': bool(business) and norm(business) in seen})
    return exports, problems


# ------------------------------------------------------------------ roadmap
def read_roadmap(path):
    """Returns (rows, problems). rows: {page, level, parent, source}. Service / Sub-Service / Brand / Device only."""
    problems, rows = [], []
    try:
        xl = pd.ExcelFile(path)
    except Exception as e:
        return [], [f'{path}: could not be read ({e})']
    if 'Roadmap' not in xl.sheet_names:
        return [], [f'{path}: no "Roadmap" tab. This is not a new-site content roadmap workbook.']
    tabs = [('Roadmap', 0, 'Roadmap')]
    if CUT_TAB in xl.sheet_names:
        tabs.append((CUT_TAB, 1, 'Cut for the 50-page cap'))     # the cut tab has an instruction row above its headers
    for tab, header, source in tabs:
        df = xl.parse(tab, header=header, dtype=str).fillna('')
        df.columns = [str(c).strip() for c in df.columns]
        miss = [c for c in ('Page', 'Page type') if c not in df.columns]
        if miss:
            problems.append(f'{tab} tab: columns not found: {", ".join(miss)}')
            continue
        for _, r in df.iterrows():
            lvl = s(r['Page type'])
            if lvl in SERVICE_LEVELS + PRODUCT_LEVELS and s(r['Page']):
                rows.append({'page': s(r['Page']), 'level': lvl, 'source': source,
                             'parent': s(r.get('Parent page / links to', ''))})
    return rows, problems


# ------------------------------------------------------------------ category counting
def count_categories(exports, business):
    """Per export: competitors (everyone except the client), categories ranked by competitors using them, top N."""
    out = []
    for ex in exports:
        comps = [b for b in ex['businesses'] if not (business and norm(b['name']) == norm(business))]
        use, prim = {}, {}
        for b in comps:
            for i, c in enumerate(b['categories']):
                use[c] = use.get(c, 0) + 1
                if i == 0:
                    prim[c] = prim.get(c, 0) + 1
        ranked = sorted(use, key=lambda c: (-use[c], -prim.get(c, 0), c.lower()))
        top = []
        for i, c in enumerate(ranked[:TOP_N]):
            nxt = ranked[i + 1] if i + 1 < len(ranked) else None
            tied = nxt is not None and i == TOP_N - 1 and (use[nxt], prim.get(nxt, 0)) == (use[c], prim.get(c, 0))
            top.append({'category': c, 'competitors': use[c], 'primary': prim.get(c, 0), 'tied_with_next': tied})
        out.append({'specialty': ex['specialty'], 'search': ex['search'], 'n_competitors': len(comps), 'top': top,
                    'client_categories': next((b['categories'] for b in ex['businesses']
                                               if business and norm(b['name']) == norm(business)), None)})
    return out


def recommend(counts, matched_cats):
    """Per specialty: categories in some export's top N that a service is matched to, with a suggested primary."""
    specs = {}
    for c in counts:
        specs.setdefault(c['specialty'], []).append(c)
    result = {}
    for spec, cs in specs.items():
        info = {}
        for c in cs:
            for t in c['top']:
                d = info.setdefault(t['category'], {'exports': 0, 'primary': 0, 'competitors': 0})
                d['exports'] += 1
                d['primary'] += t['primary']
                d['competitors'] += t['competitors']
        rec = [k for k in info if norm(k) in matched_cats]
        unmatched = [k for k in info if norm(k) not in matched_cats]
        order = lambda k: (-info[k]['primary'], -info[k]['exports'], -info[k]['competitors'], k.lower())
        rec.sort(key=order)
        unmatched.sort(key=order)
        result[spec] = {'n_exports': len(cs), 'info': info, 'recommended': rec, 'no_service': unmatched,
                        'primary': rec[0] if rec and info[rec[0]]['primary'] > 0 else None}
    return result


# ------------------------------------------------------------------ commands
def cmd_preflight(a):
    fails, warns = [], []
    if not a.roadmap:
        fails.append('the content roadmap workbook (.xlsx from new-site-content-roadmap) is missing')
        rows = []
    else:
        rows, p = read_roadmap(a.roadmap)
        fails += p
        if not p and not any(r['level'] in SERVICE_LEVELS for r in rows):
            fails.append('the roadmap has no Service or Sub-Service rows')
    if not a.gbp:
        fails.append('no Pleper Search Export files: send one per priority search, each labelled with its specialty')
        exports = []
    else:
        exports, p = load_exports(a.gbp, a.business)
        fails += p
    by = {}
    for ex in exports:
        by.setdefault(ex['specialty'], []).append(ex)
        if len(ex['businesses']) < MIN_COMPETITORS:
            warns.append(f'"{ex["search"]}" ({ex["specialty"]}) has only {len(ex["businesses"])} businesses: its top {TOP_N} will be thin')
    for spec, exs in by.items():
        if len(exs) < MIN_EXPORTS:
            warns.append(f'{spec}: {len(exs)} export(s), fewer than {MIN_EXPORTS}. The top {TOP_N} comes from fewer searches')
    if not a.client:
        fails.append('the client name is missing')
    if a.business and exports and not any(ex['client_found'] for ex in exports):
        warns.append(f'"{a.business}" is not in any export: every recommended category will show as new. Check the spelling against the export')
    if not a.business:
        warns.append('no GBP business name given: categories will not be compared with what the client already has')
    lines = ['# Preflight', '', 'NOT READY' if fails else 'READY', '']
    lines += [f'- FAIL: {f}' for f in fails] + [f'- WARN: {w}' for w in warns]
    if exports:
        lines += ['', '## Exports'] + [f'- {e["specialty"]} | {e["search"]}: {len(e["businesses"])} businesses' for e in exports]
    if rows:
        lines += ['', f'Roadmap: {sum(r["level"] in SERVICE_LEVELS for r in rows)} services / sub-services, '
                      f'{sum(r["level"] in PRODUCT_LEVELS for r in rows)} brands / devices']
    Path(a.out).mkdir(parents=True, exist_ok=True)
    Path(a.out, 'preflight.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    sys.exit(1 if fails else 0)


def _load_all(a):
    rows, p1 = read_roadmap(a.roadmap)
    exports, p2 = load_exports(a.gbp, a.business)
    if p1 + p2:
        sys.exit('Stop: ' + '; '.join(p1 + p2))
    return rows, exports


def cmd_categories(a):
    rows, exports = _load_all(a)
    counts = count_categories(exports, a.business)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'categories.json').write_text(json.dumps(counts, indent=2), encoding='utf-8')
    services = [r for r in rows if r['level'] in SERVICE_LEVELS]
    pd.DataFrame([{'page': r['page'], 'level': r['level'], 'parent': r['parent'], 'source': r['source'], 'category': ''}
                  for r in services]).to_csv(out / 'service_match.tsv', sep='\t', index=False)
    products = [r for r in rows if r['level'] in PRODUCT_LEVELS]
    pd.DataFrame([{'type': 'Service' if r['level'] in SERVICE_LEVELS else 'Product', 'name': r['page'], 'parent': r['parent'],
                   'source': r['source'], 'title': r['page'], 'description': ''} for r in services + products]
                 ).to_csv(out / 'descriptions.tsv', sep='\t', index=False)
    print('Top categories per export (competitors using the category / using it as primary):')
    for c in counts:
        print(f'\n{c["specialty"]} | {c["search"]} ({c["n_competitors"]} competitors)')
        for t in c['top']:
            print(f'  {t["category"]}: {t["competitors"]} / {t["primary"]}' + ('  (tied with the next category)' if t['tied_with_next'] else ''))
    cands = sorted({t['category'] for c in counts for t in c['top']}, key=str.lower)
    print('\nCandidate categories for service_match.tsv:', '; '.join(cands))
    print(f'Wrote {out / "categories.json"} and {out / "service_match.tsv"} ({len(services)} services to match) and {out / "descriptions.tsv"} ({len(services)} services, {len(products)} products to write).')


def read_match(path, counts):
    df = pd.read_csv(path, sep='\t', dtype=str, keep_default_na=False)
    cands = {norm(t['category']): t['category'] for c in counts for t in c['top']}
    bad = [(r['page'], r['category']) for _, r in df.iterrows() if r['category'].strip() and norm(r['category']) not in cands]
    if bad:
        sys.exit('Stop: category not in any top 3 (use the exact name or leave blank): ' + '; '.join(f'{p} -> {c}' for p, c in bad))
    df['category'] = df['category'].map(lambda v: cands.get(norm(v), ''))
    return df


def read_descriptions(path, rows):
    """Reads descriptions.tsv and enforces the GBP limits. Stops with every problem listed; never truncates."""
    df = pd.read_csv(path, sep='\t', dtype=str, keep_default_na=False)
    want = {(('Service' if r['level'] in SERVICE_LEVELS else 'Product'), r['page']) for r in rows if r['level'] in SERVICE_LEVELS + PRODUCT_LEVELS}
    have = set(zip(df['type'], df['name']))
    errs = []
    if want != have:
        errs.append('descriptions.tsv does not list the same services and products as the roadmap. Run categories again')
    for _, r in df.iterrows():
        title, desc, kind = r['title'].strip(), r['description'].strip(), r['type']
        if not title or not desc:
            errs.append(f'{kind} "{r["name"]}": title or description is blank')
        if kind == 'Service' and len(desc) > SERVICE_DESC_MAX:
            errs.append(f'Service "{r["name"]}": description is {len(desc)} characters (limit {SERVICE_DESC_MAX})')
        if kind == 'Product':
            if len(title) > PRODUCT_NAME_MAX:
                errs.append(f'Product "{r["name"]}": name is {len(title)} characters (limit {PRODUCT_NAME_MAX})')
            if len(desc) > PRODUCT_DESC_MAX:
                errs.append(f'Product "{r["name"]}": description is {len(desc)} characters (limit {PRODUCT_DESC_MAX})')
    if errs:
        sys.exit('Stop, rewrite these (do not just cut them off):\n- ' + '\n- '.join(errs))
    df['title'], df['description'] = df['title'].str.strip(), df['description'].str.strip()
    return df


def build_sheet(df, path):
    from openpyxl import Workbook
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    head = PatternFill('solid', fgColor='1F3864')
    red = PatternFill('solid', bgColor='F4CCCC', fgColor='F4CCCC')

    def tab(ws, kind, cols, widths):
        sub = df[df['type'] == kind]
        ws.append(cols)
        for c in ws[1]:
            c.font, c.fill, c.alignment = Font(bold=True, color='FFFFFF'), head, Alignment(wrap_text=True, vertical='center')
        for i, (_, r) in enumerate(sub.iterrows(), 2):
            if kind == 'Service':
                ws.append([r['title'], r['description'], f'=LEN(B{i})', r['parent'], r['source']])
            else:
                ws.append([r['title'], r['description'], f'=LEN(A{i})', f'=LEN(B{i})', r['parent'], r['source']])
            for c in ws[i]:
                c.alignment = Alignment(wrap_text=True, vertical='top')
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
        ws.freeze_panes = 'A2'
        return len(sub) + 1

    ws = wb.active
    ws.title = 'Services'
    n = tab(ws, 'Service', ['Service', f'Description (max {SERVICE_DESC_MAX} characters)', 'Description characters', 'Parent page', 'Roadmap tab'],
            [30, 80, 14, 24, 22])
    ws.conditional_formatting.add(f'C2:C{n}', FormulaRule(formula=[f'$C2>{SERVICE_DESC_MAX}'], fill=red))
    ws2 = wb.create_sheet('Products')
    n = tab(ws2, 'Product', [f'Product name (max {PRODUCT_NAME_MAX} characters)', f'Description (max {PRODUCT_DESC_MAX} characters)',
                              'Name characters', 'Description characters', 'Parent page', 'Roadmap tab'], [32, 80, 12, 14, 24, 22])
    ws2.conditional_formatting.add(f'C2:C{n}', FormulaRule(formula=[f'$C2>{PRODUCT_NAME_MAX}'], fill=red))
    ws2.conditional_formatting.add(f'D2:D{n}', FormulaRule(formula=[f'$D2>{PRODUCT_DESC_MAX}'], fill=red))
    wb.save(path)


def cmd_build(a):
    rows, exports = _load_all(a)
    counts = count_categories(exports, a.business)
    match = read_match(a.match, counts)
    services = [r for r in rows if r['level'] in SERVICE_LEVELS]
    if set(match['page']) != {r['page'] for r in services}:
        sys.exit('Stop: service_match.tsv does not list the same services as the roadmap. Run categories again.')
    cat_of = dict(zip(match['page'], match['category']))
    matched = {norm(v) for v in cat_of.values() if v}
    rec = recommend(counts, matched)
    cat_services = {}
    for pg, c in cat_of.items():
        if c:
            cat_services.setdefault(norm(c), []).append(pg)
    client_has = {norm(c) for ex in counts for c in (ex['client_categories'] or [])}
    client_known = any(ex['client_categories'] is not None for ex in counts)
    data = {'client': a.client, 'business': a.business, 'client_known': client_known, 'counts': counts,
            'rec': rec, 'cat_services': cat_services, 'client_has': sorted(client_has), 'services': services,
            'cat_of': cat_of, 'products': [r for r in rows if r['level'] in PRODUCT_LEVELS]}
    # checks
    checks = [
        ('every export has at most %d categories listed' % TOP_N, all(len(c['top']) <= TOP_N for c in counts)),
        ('every recommended category has a matched service', all(norm(k) in matched for r in rec.values() for k in r['recommended'])),
        ('no category is both recommended and flagged', all(not set(r['recommended']) & set(r['no_service']) for r in rec.values())),
        ('every service is in the document once', len({r['page'] for r in services}) == len(services)),
    ]
    desc = read_descriptions(a.descriptions, rows)
    build_docx(data, a.out)
    build_sheet(desc, a.sheet)
    print(f'Wrote {a.out} and {a.sheet}')
    for spec, r in rec.items():
        print(f'{spec}: primary {r["primary"] or "none suggested"}; recommended {len(r["recommended"])}; no matching service {len(r["no_service"])}')
    print(f'Services without a category: {sum(1 for v in cat_of.values() if not v)} of {len(cat_of)}')
    bad = False
    for n, ok in checks:
        print(('PASS ' if ok else 'FAIL ') + n)
        bad |= not ok
    sys.exit(1 if bad else 0)


# ------------------------------------------------------------------ document
def build_docx(d, path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    doc = Document()
    st = doc.styles['Normal']
    st.font.name, st.font.size = 'Arial', Pt(10.5)
    for name, size in (('Title', 22), ('Heading 1', 16), ('Heading 2', 13)):
        h = doc.styles[name]
        h.font.name, h.font.size, h.font.color.rgb = 'Arial', Pt(size), RGBColor(0x1F, 0x38, 0x64)

    def shade(cell, color):
        tcPr = cell._tc.get_or_add_tcPr()
        sh = OxmlElement('w:shd')
        sh.set(qn('w:val'), 'clear')
        sh.set(qn('w:color'), 'auto')
        sh.set(qn('w:fill'), color)
        tcPr.append(sh)

    def table(headers, rows, widths=None):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = 'Table Grid'
        for i, h in enumerate(headers):
            c = t.rows[0].cells[i]
            c.text = ''
            run = c.paragraphs[0].add_run(h)
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            shade(c, '1F3864')
        for r in rows:
            cells = t.add_row().cells
            for i, v in enumerate(r):
                cells[i].text = s(v)
        if widths is None:
            widths = [6.5 / len(headers)] * len(headers)
        if widths:
            from docx.shared import Inches
            t.autofit = False
            for row in t.rows:
                for i, w in enumerate(widths):
                    row.cells[i].width = Inches(w)
        doc.add_paragraph()
        return t

    def note(text, color='FFF2CC'):
        t = doc.add_table(rows=1, cols=1)
        t.style = 'Table Grid'
        c = t.rows[0].cells[0]
        c.text = text
        shade(c, color)
        doc.add_paragraph()

    doc.add_heading(f'Google Business Profile setup: {d["client"]}', 0)
    note('This is a draft. Every category, service and product here is a recommendation built from competitor data and the content '
         'roadmap. The SEO must confirm each one is correct for this business before it goes into the profile.')

    # 1. Categories
    doc.add_heading('1. Categories', 1)
    doc.add_paragraph('For each local search export we took the three categories most competitors use (any of their five category '
                      'slots). Categories that also match one of the client\'s services make the final recommendation below.')
    for spec, r in d['rec'].items():
        doc.add_heading(spec, 2)
        p = doc.add_paragraph()
        p.add_run('Suggested primary category: ').bold = True
        p.add_run(r['primary'] or 'none suggested (no competitor in the exports uses a matching category as its primary)')
        rows = []
        for k in r['recommended']:
            i = r['info'][k]
            svc = '; '.join(d['cat_services'].get(norm(k), []))
            has = ''
            if d['client_known']:
                has = 'Has it' if norm(k) in {norm(x) for x in d['client_has']} else 'Missing'
            rows.append([k, f'{i["exports"]} of {r["n_exports"]}', i['competitors'], i['primary'], svc] + ([has] if d['client_known'] else []))
        if rows:
            table(['Recommended category', 'In top 3 of exports', 'Competitor uses (total)', 'As primary (total)', 'Matching services'] +
                  (['On client\'s profile'] if d['client_known'] else []), rows,
                  [1.5, 0.8, 0.9, 0.8, 1.7, 0.8] if d['client_known'] else [1.7, 0.9, 1.0, 0.9, 2.0])
        else:
            doc.add_paragraph('No category in the top 3 of these exports matched a service on the roadmap.')
        if r['no_service']:
            p = doc.add_paragraph()
            p.add_run('Competitors use these, but no roadmap service matches, so they are not recommended: ').bold = True
            p.add_run('; '.join(r['no_service']) + '. Add one only if the client really offers the service.')
        doc.add_paragraph()
        for c in [c for c in d['counts'] if c['specialty'] == spec]:
            p = doc.add_paragraph()
            p.add_run(f'Search "{c["search"]}" ({c["n_competitors"]} competitors): ').bold = True
            p.add_run('; '.join(f'{t["category"]} ({t["competitors"]} use it, {t["primary"]} as primary)' + (', tied with the next category' if t['tied_with_next'] else '')
                                for t in c['top']))
    unmatched = [pg for pg, c in d['cat_of'].items() if not c]
    doc.add_heading('Services with no matching GBP category', 2)
    if unmatched:
        doc.add_paragraph('None of the top categories fit these services. The SEO decides whether a category is needed for them, '
                          'or whether they only go in the Services list.')
        for pg in unmatched:
            doc.add_paragraph(pg, style='List Bullet')
    else:
        doc.add_paragraph('Every service matched a category.')

    # 2. Services
    doc.add_heading('2. Services', 1)
    doc.add_paragraph('From the Service and Sub-Service rows of the content roadmap, including pages cut from the 50-page cap '
                      '(a GBP list has no page cap). Services the client does not offer are not on the roadmap, so they are not here.')
    table(['Service', 'Type', 'Parent page', 'Matched category', 'Roadmap tab'],
          [[r['page'], r['level'], r['parent'], d['cat_of'].get(r['page']) or 'None', r['source']] for r in d['services']])

    # 3. Products
    doc.add_heading('3. Products', 1)
    if d['products']:
        doc.add_paragraph('From the Brand / Device rows of the content roadmap.')
        table(['Product', 'Parent page', 'Roadmap tab'], [[r['page'], r['parent'], r['source']] for r in d['products']])
    else:
        doc.add_paragraph('The roadmap has no Brand / Device rows. Add products here only if the client sells them.')

    # 4. Checklist
    doc.add_heading('4. Everything else to complete the profile', 1)
    for item, hint in CHECKLIST:
        p = doc.add_paragraph()
        p.add_run('☐  ' + item).bold = True
        if hint:
            p.add_run(': ' + hint)
    doc.add_heading('Limits', 2)
    for t in ('The exports list at most five categories per business, so a category a competitor has beyond its fifth is not counted.',
              'Competitors are every other business in the exports. Businesses from another specialty can appear, so check the lists.',
              'Category names are written as the exports show them. Pick the matching name in Google\'s own category list.',
              'Nothing was looked up live. The counts are a snapshot of the exports.'):
        doc.add_paragraph(t, style='List Bullet')
    doc.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('preflight', 'categories', 'build'):
        p = sub.add_parser(name)
        p.add_argument('--roadmap')
        p.add_argument('--gbp', action='append', default=[], help='"Specialty|search words=export.json" (repeat the option)')
        p.add_argument('--business', default='', help='the client\'s exact GBP business name as written in the exports (optional)')
        if name == 'preflight':
            p.add_argument('--client', default='')
            p.add_argument('--out', default='work')
        elif name == 'categories':
            p.add_argument('--out', default='work')
        else:
            p.add_argument('--client', required=True)
            p.add_argument('--match', required=True)
            p.add_argument('--descriptions', required=True)
            p.add_argument('--out', required=True, help='the Word document')
            p.add_argument('--sheet', required=True, help='the services and products sheet (.xlsx)')
    a = ap.parse_args()
    {'preflight': cmd_preflight, 'categories': cmd_categories, 'build': cmd_build}[a.cmd](a)


if __name__ == '__main__':
    main()
