#!/usr/bin/env python3
"""Schema markup templates: one JSON-LD template per page type, written from a real page of that type.

Inputs : the new site content roadmap workbook (Roadmap tab), the business type, and (written by Claude from a real
         page the person pastes) one template file per group.
Output : the roadmap with a recommended schema type per page, a plan of the templates to write, a filled test copy of
         each template for the schema.org validator, and one document with every template once each has passed.
Needs only the standard library and openpyxl. No connector, no live lookups, and it does not validate against
schema.org: the person runs the schema.org validator and tells us the result.

  python3 schema.py preflight --roadmap R.xlsx --business-type medspa --out work
  python3 schema.py build     --roadmap R.xlsx --business-type medspa [--client NAME] --out CLIENT_schema_types.xlsx --work work
  python3 schema.py check     --work work --slug treatment --page-url URL
  python3 schema.py fill      --work work --slug treatment --values values.json
  python3 schema.py mark      --work work --slug treatment --status passed|failed [--note TEXT]
  python3 schema.py doc       --work work [--client NAME] --out CLIENT_schema_templates.md

Files under work/: plan.json, status.json, templates/<slug>.json (the template), templates/<slug>.map.json
(placeholders and notes), test/<slug>.filled.json (the template filled with the real page).
Rules are in ../references/rules.md. Change a constant here and update that file in the same pull request.
"""
import argparse
import datetime
import json
import os
import re
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

# Business type words (the same practice types as the service gap audit) -> the schema type for the Home page.
BUSINESS_TYPES = {
    'medspa': ('MedicalClinic', 'a med spa run by a medical practice'),
    'surgical': ('PlasticSurgery', 'a plastic surgery practice'),
    'dental': ('Dentist', 'a dental practice'),
}
SERVICE_KINDS = ('Service', 'Sub-Service', 'Brand / Device')   # one MedicalProcedure template for all three
# Extra pages: the word after "Extra:" -> (group label, schema type, why)
EXTRA_TYPES = {
    'package': ('Package', 'Service', 'A bundled offer: a Service with an Offer.'),
    'provider': ('Provider', 'Person', 'A page about one practitioner. Person, not Physician: Physician describes a practice, not a person.'),
    'location': ('Location', None, 'A page for one location of the business: the business type with its own address.'),
    'event': ('Event', 'Event', 'A dated event.'),
}
PLACEHOLDER = re.compile(r'\{\{([A-Za-z0-9_]+)\}\}')
NAME_OK = re.compile(r'^[a-z0-9_]+$')
HEAD = PatternFill('solid', fgColor='D9E1F2')
YELLOW = PatternFill('solid', fgColor='FFF2CC')


def jload(path):
    with open(path) as f:
        return json.load(f)


def jdump(obj, path, **kw):
    with open(path, 'w') as f:
        json.dump(obj, f, **kw)


def write_text(path, text):
    with open(path, 'w') as f:
        f.write(text)


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def business_schema_type(value):
    """Return (schema type, note). Accepts medspa / surgical / dental or a schema.org type name."""
    v = (value or '').strip()
    if v.lower() in BUSINESS_TYPES:
        t, why = BUSINESS_TYPES[v.lower()]
        return t, f'{t} for {why}'
    if re.match(r'^[A-Z][A-Za-z]+$', v):
        return v, f'{v} (given by the person; confirm it in the validator)'
    return None, None


# ---------- roadmap ----------
def read_roadmap(path):
    wb = load_workbook(path, data_only=True)
    if 'Roadmap' not in wb.sheetnames:
        raise SystemExit("The workbook has no 'Roadmap' tab. Run the new-site-content-roadmap skill first.")
    rows = list(wb['Roadmap'].iter_rows(values_only=True))
    head = [str(h or '') for h in rows[0]]
    try:
        c_page, c_type = head.index('Page'), head.index('Page type')
    except ValueError:
        raise SystemExit("The Roadmap tab needs 'Page' and 'Page type' columns.")
    client = ''
    if 'Read Me' in wb.sheetnames:
        for r in wb['Read Me'].iter_rows(values_only=True):
            if r[0] and str(r[0]).startswith('New site content roadmap'):
                client = r[1] or ''
    pages = [dict(name=str(r[c_page]).strip(), type=str(r[c_type] or '').strip()) for r in rows[1:] if r[c_page]]
    return client, pages


def classify(page_type, business_type):
    """-> (group slug, group label, schema type, why, needs SEO confirmation)."""
    t = page_type.strip()
    if t == 'Home':
        return 'home', 'Home', business_type, f'The home page describes the business, so it carries the business markup ({business_type}).', False
    if t == 'About Us':
        return 'about-us', 'About Us', 'AboutPage', 'A page about the business and its team.', False
    if t in SERVICE_KINDS:
        return 'treatment', 'Service, Sub-Service and Brand / Device', 'MedicalProcedure', \
            'A treatment page. Shares one template with the other treatment pages (the breadcrumb is one level deeper on Sub-Service and Brand / Device pages).', False
    if t == 'Concern':
        return 'concern', 'Concern', 'MedicalCondition', 'A page about a condition or concern, not a treatment.', False
    if t == 'Blog':
        return 'blog', 'Blog', 'BlogPosting', 'An informational blog post.', False
    if t.lower().startswith('extra'):
        word = t.split(':', 1)[1].strip() if ':' in t else ''
        key = word.lower()
        if key in EXTRA_TYPES:
            label, stype, why = EXTRA_TYPES[key]
            return f'extra-{slugify(label)}', f'Extra: {label}', stype or business_type, why, True
        return f'extra-{slugify(word) or "page"}', f'Extra: {word or "page"}', 'WebPage', \
            'No fixed type for this kind of page. WebPage is the safe starting point.', True
    return f'other-{slugify(t) or "page"}', t or 'Other', 'WebPage', 'Page type the skill has no rule for. WebPage is the safe starting point.', True


def build_plan(pages, business_type):
    groups, order = {}, []
    for p in pages:
        slug, label, stype, why, confirm = classify(p['type'], business_type)
        p.update(group=slug, schema=stype, why=why, confirm=confirm)
        if slug not in groups:
            groups[slug] = dict(slug=slug, label=label, schema=stype, pages=[], confirm=confirm)
            order.append(slug)
        groups[slug]['pages'].append(p['name'])
    return [groups[s] for s in order]


def preflight(args):
    os.makedirs(args.out, exist_ok=True)
    lines, fails = [], 0
    stype, note = business_schema_type(args.business_type)
    if not stype:
        lines.append("FAIL: the business type must be medspa, surgical, dental or a schema.org type name such as MedicalClinic.")
        fails += 1
    else:
        lines.append(f'PASS: business type -> {note}')
    try:
        _, pages = read_roadmap(args.roadmap)
        lines.append(f'PASS: the Roadmap tab has {len(pages)} pages')
        if not pages:
            lines.append('FAIL: the Roadmap tab has no pages')
            fails += 1
    except SystemExit as e:
        lines.append(f'FAIL: {e}')
        fails += 1
    lines.append('NOT READY' if fails else 'READY')
    write_text(os.path.join(args.out, 'preflight.md'), '\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return 1 if fails else 0


def build(args):
    stype, _ = business_schema_type(args.business_type)
    if not stype:
        raise SystemExit('The business type must be medspa, surgical, dental or a schema.org type name.')
    client, pages = read_roadmap(args.roadmap)
    client = args.client or client
    groups = build_plan(pages, stype)

    # Roadmap tab + two columns only. Other tabs are dropped.
    wb = load_workbook(args.roadmap)
    for name in list(wb.sheetnames):
        if name != 'Roadmap':
            del wb[name]
    ws = wb['Roadmap']
    head = [c.value for c in ws[1]]
    c_page = head.index('Page') + 1
    first_new = ws.max_column + 1
    for off, title in enumerate(('Primary schema type', 'Why this schema type')):
        cell = ws.cell(row=1, column=first_new + off, value=title)
        cell.font = Font(bold=True)
        cell.fill = HEAD
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        ws.column_dimensions[cell.column_letter].width = 28 if off == 0 else 70
    by_name = {p['name']: p for p in pages}
    for r in range(2, ws.max_row + 1):
        name = ws.cell(row=r, column=c_page).value
        p = by_name.get(str(name).strip()) if name else None
        if not p:
            continue
        a = ws.cell(row=r, column=first_new, value=p['schema'])
        b = ws.cell(row=r, column=first_new + 1, value=p['why'] + (' SEO to confirm.' if p['confirm'] else ''))
        for c in (a, b):
            c.alignment = Alignment(wrap_text=True, vertical='top')
        if p['confirm']:
            a.fill = YELLOW

    rm = wb.create_sheet('Read Me', 0)
    rm.append(['Item', 'Detail'])
    rm.append(['Schema types', f'Recommended primary schema type for every page on the Roadmap tab{" for " + client if client else ""}. '
                               'Built from the page type column only; nothing was looked up live.'])
    rm.append(['Business type', f'{stype}. Used for the Home page and for the business that other pages point to.'])
    rm.append(['Yellow cells', 'A type the skill has no fixed rule for (extra pages and unknown page types). The SEO confirms it after the real page is read.'])
    rm.append(['Templates', f'{len(groups)} templates will be written, one per distinct schema structure: ' +
               '; '.join(f"{g['label']} ({len(g['pages'])})" for g in groups) + '.'])
    rm.append(['Next', 'Paste one real, finished page of each type. The template for that type is written from it. These are schema templates, not final markup: test each one in the schema.org validator, paste any error messages back into the chat, and the SEO confirms the result.'])
    rm.append(['Other tabs', 'The roadmap\'s Internal links and Cut tabs are not copied here.'])
    for c in rm[1]:
        c.font = Font(bold=True)
        c.fill = HEAD
    rm.column_dimensions['A'].width = 22
    rm.column_dimensions['B'].width = 110
    for row in rm.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical='top')
    wb.save(args.out)

    os.makedirs(os.path.join(args.work, 'templates'), exist_ok=True)
    plan = dict(client=client, business_schema_type=stype, groups=groups)
    jdump(plan, os.path.join(args.work, 'plan.json'), indent=2)
    status_path = os.path.join(args.work, 'status.json')
    old = jload(status_path) if os.path.exists(status_path) else {}
    status = {g['slug']: old.get(g['slug'], dict(status='not started')) for g in groups}
    jdump(status, status_path, indent=2)

    lines = [f'# Templates to write ({len(groups)})', '']
    for g in groups:
        lines.append(f"- {g['slug']}: {g['label']}, schema type {g['schema']}, {len(g['pages'])} page{'s' if len(g['pages']) != 1 else ''}, e.g. {g['pages'][0]}"
                     + (' (SEO to confirm the type)' if g['confirm'] else ''))
    write_text(os.path.join(args.work, 'plan.md'), '\n'.join(lines) + '\n')
    print('\n'.join(lines))
    print(f'PASS: {len(pages)} pages typed, workbook written to {args.out}')
    return 0


# ---------- templates ----------
def load_plan(work):
    p = os.path.join(work, 'plan.json')
    if not os.path.exists(p):
        raise SystemExit('No plan.json in the work folder. Run build first.')
    return jload(p)


def walk(node, path=''):
    """Yield (path, value) for every leaf string, and report empty values."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f'{path}/{k}')
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f'{path}[{i}]')
    else:
        yield path, node


def empties(node, path=''):
    out = []
    if isinstance(node, dict):
        if not node:
            out.append(path or '/')
        for k, v in node.items():
            out += empties(v, f'{path}/{k}')
    elif isinstance(node, list):
        if not node:
            out.append(path or '/')
        for i, v in enumerate(node):
            out += empties(v, f'{path}[{i}]')
    elif node is None or (isinstance(node, str) and not node.strip()):
        out.append(path)
    return out


def types_in(node):
    found = []
    if isinstance(node, dict):
        t = node.get('@type')
        if isinstance(t, str):
            found.append(t)
        elif isinstance(t, list):
            found += [x for x in t if isinstance(x, str)]
        for v in node.values():
            found += types_in(v)
    elif isinstance(node, list):
        for v in node:
            found += types_in(v)
    return found


def paths(slug, work):
    d = os.path.join(work, 'templates')
    return os.path.join(d, f'{slug}.json'), os.path.join(d, f'{slug}.map.json')


def check(args):
    plan = load_plan(args.work)
    group = next((g for g in plan['groups'] if g['slug'] == args.slug), None)
    if not group:
        raise SystemExit(f"No template '{args.slug}' in the plan. Slugs: " + ', '.join(g['slug'] for g in plan['groups']))
    tpath, mpath = paths(args.slug, args.work)
    problems = []
    try:
        tpl = jload(tpath)
    except FileNotFoundError:
        raise SystemExit(f'Missing {tpath}')
    except json.JSONDecodeError as e:
        raise SystemExit(f'FAIL: {tpath} is not valid JSON: {e}')
    try:
        meta = jload(mpath)
    except FileNotFoundError:
        raise SystemExit(f'Missing {mpath}')
    except json.JSONDecodeError as e:
        raise SystemExit(f'FAIL: {mpath} is not valid JSON: {e}')

    ctx = tpl.get('@context') if isinstance(tpl, dict) else None
    if not (isinstance(ctx, str) and ctx.rstrip('/') == 'https://schema.org'):
        problems.append('the template needs "@context": "https://schema.org" at the top')
    used = set()
    for path, val in walk(tpl):
        if isinstance(val, str):
            found = PLACEHOLDER.findall(val)
            used.update(found)
            if path.endswith('/@type') or path.endswith('/@context') or re.search(r'/@type\[\d+\]$', path):
                if found:
                    problems.append(f'{path} is a placeholder; types come from the real page and are written out')
            if re.search(r'\[[^\]]*\]', val) and not found and val.startswith('['):
                problems.append(f'{path} looks like leftover bracket text: {val[:40]}')
    for e in empties(tpl):
        problems.append(f'{e} is empty. Leave a property out instead of leaving it blank')
    described = meta.get('placeholders', {})
    for name in sorted(used):
        if not NAME_OK.match(name):
            problems.append(f'placeholder {{{{{name}}}}} must be lowercase letters, numbers and underscores')
        if name not in described:
            problems.append(f'placeholder {{{{{name}}}}} is used but not described in the map file')
    for name in sorted(described):
        if name not in used:
            problems.append(f'placeholder {name} is described but not used in the template')
        elif not str(described[name]).strip():
            problems.append(f'placeholder {name} has no description')
    primary = group['schema']
    if primary not in types_in(tpl):
        problems.append(f"the primary type {primary} for this group is not in the template; if the real page shows it should be a different type, change the group type and tell the SEO")
    if problems:
        print('FAIL: ' + args.slug)
        for p in problems:
            print('  - ' + p)
        return 1
    status = jload(os.path.join(args.work, 'status.json'))
    status[args.slug] = dict(status='draft', page_url=args.page_url or status.get(args.slug, {}).get('page_url', ''))
    jdump(status, os.path.join(args.work, 'status.json'), indent=2)
    print(f'PASS: {args.slug}: valid JSON, {len(used)} placeholders all described, no empty values, primary type {primary} present')
    return 0


def substitute(node, values, missing):
    if isinstance(node, dict):
        return {k: substitute(v, values, missing) for k, v in node.items()}
    if isinstance(node, list):
        return [substitute(v, values, missing) for v in node]
    if isinstance(node, str):
        whole = PLACEHOLDER.fullmatch(node)
        if whole:
            if whole.group(1) not in values:
                missing.add(whole.group(1))
                return node
            return values[whole.group(1)]
        def rep(m):
            if m.group(1) not in values:
                missing.add(m.group(1))
                return m.group(0)
            return str(values[m.group(1)])
        return PLACEHOLDER.sub(rep, node)
    return node


def fill(args):
    tpath, mpath = paths(args.slug, args.work)
    tpl = jload(tpath)
    meta = jload(mpath)
    values = jload(args.values)
    missing = set()
    out = substitute(tpl, values, missing)
    unused = sorted(set(values) - set(meta.get('placeholders', {})))
    if missing or unused:
        print('FAIL: ' + args.slug)
        if missing:
            print('  - no value for: ' + ', '.join(sorted(missing)))
        if unused:
            print('  - values given for placeholders the template does not have: ' + ', '.join(unused))
        return 1
    leftovers = [e for e in empties(out)]
    if leftovers:
        print('FAIL: empty values after filling: ' + ', '.join(leftovers))
        return 1
    os.makedirs(os.path.join(args.work, 'test'), exist_ok=True)
    dest = os.path.join(args.work, 'test', f'{args.slug}.filled.json')
    jdump(out, dest, indent=2, ensure_ascii=False)
    print(f'PASS: {args.slug}: every placeholder filled, written to {dest}')
    return 0


def mark(args):
    sp = os.path.join(args.work, 'status.json')
    status = jload(sp)
    if args.slug not in status:
        raise SystemExit(f"No template '{args.slug}' in status.json")
    if status[args.slug].get('status') == 'not started':
        raise SystemExit(f"'{args.slug}' has no template yet. Write it and run check first.")
    status[args.slug].update(status=args.status, note=args.note or '',
                             date=datetime.date.today().isoformat())
    jdump(status, sp, indent=2)
    print(f'{args.slug}: {args.status}')
    return 0


def doc(args):
    plan = load_plan(args.work)
    status = jload(os.path.join(args.work, 'status.json'))
    pending = [g['slug'] for g in plan['groups'] if status.get(g['slug'], {}).get('status') != 'passed']
    if pending:
        print('FAIL: these templates have not passed the schema.org validator: ' + ', '.join(pending))
        return 1
    client = args.client or plan.get('client') or ''
    lines = [f'# Schema markup templates{" - " + client if client else ""}', '',
             'One JSON-LD template per page type. Every `{{placeholder}}` is a value the WordPress schema plugin fills '
             'from the page; the table under each template says what it maps to. A block marked "repeat" is repeated once '
             'per item on the page (each question, review or breadcrumb level). Each template was filled with one real '
             'page and passed the schema.org validator; the page is listed with it. These are templates, not final markup: if the plugin\'s output shows an error or warning on a live page, test that page in the validator at validator.schema.org and paste the messages back to the SEO.', '']
    for g in plan['groups']:
        tpath, mpath = paths(g['slug'], args.work)
        tpl = jload(tpath)
        meta = jload(mpath)
        st = status[g['slug']]
        lines += [f"## {g['label']}", '',
                  f"- Primary schema type: {g['schema']}",
                  f"- Applies to: {len(g['pages'])} pages, e.g. " + ', '.join(g['pages'][:3]),
                  f"- Tested on: {st.get('page_url') or 'real page (URL not recorded)'} (passed {st.get('date', '')})", '']
        for n in meta.get('notes', []):
            lines.append(f'- {n}')
        if meta.get('notes'):
            lines.append('')
        lines += ['```json', json.dumps(tpl, indent=2, ensure_ascii=False), '```', '',
                  '| Placeholder | Maps to |', '| --- | --- |']
        for name, desc in meta.get('placeholders', {}).items():
            lines.append(f'| `{{{{{name}}}}}` | {str(desc).replace("|", "/")} |')
        lines.append('')
    write_text(args.out, '\n'.join(lines))
    print(f'PASS: {len(plan["groups"])} templates written to {args.out}')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('preflight')
    p.add_argument('--roadmap', required=True)
    p.add_argument('--business-type', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('build')
    p.add_argument('--roadmap', required=True)
    p.add_argument('--business-type', required=True)
    p.add_argument('--client', default='')
    p.add_argument('--out', required=True)
    p.add_argument('--work', required=True)
    p = sub.add_parser('check')
    p.add_argument('--work', required=True)
    p.add_argument('--slug', required=True)
    p.add_argument('--page-url', default='')
    p = sub.add_parser('fill')
    p.add_argument('--work', required=True)
    p.add_argument('--slug', required=True)
    p.add_argument('--values', required=True)
    p = sub.add_parser('mark')
    p.add_argument('--work', required=True)
    p.add_argument('--slug', required=True)
    p.add_argument('--status', required=True, choices=['passed', 'failed'])
    p.add_argument('--note', default='')
    p = sub.add_parser('doc')
    p.add_argument('--work', required=True)
    p.add_argument('--client', default='')
    p.add_argument('--out', required=True)
    args = ap.parse_args()
    return {'preflight': preflight, 'build': build, 'check': check, 'fill': fill, 'mark': mark, 'doc': doc}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
