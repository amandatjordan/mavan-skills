#!/usr/bin/env python3
"""New site information architecture: every page, its parent, URL path and main nav, plus the planned links with URLs.

Inputs : the new site content roadmap workbook (Roadmap and Internal links tabs) and a CSV of the other pages
         (Page, URL; URL optional).
Output : one workbook with Pages, Internal links and Read Me tabs. Needs only openpyxl. No connector, no live lookups.

  python3 ia.py preflight --roadmap R.xlsx [--csv PAGES.csv] --out work
  python3 ia.py build --roadmap R.xlsx --csv PAGES.csv [--client NAME] --out CLIENT_new_site_ia.xlsx

The roadmap owns the link plan. This script never adds, removes or re-anchors a link: it adds URLs and checks.
Rules are in ../references/rules.md. Change a constant here and update that file in the same pull request.
"""
import argparse
import csv
import os
import re
import sys
import unicodedata

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

SERVICE_PREFIX = '/services'      # Service, Sub-Service and Brand / Device pages live here
SERVICE_KINDS = ('Service', 'Sub-Service', 'Brand / Device')
BLOG_PREFIX = '/blog'
BLOG_INDEX_NAME = 'Blog'
MAX_SEGMENTS = 3                  # /services/service/child
MAX_NAV = 8                       # warn above this many Yes in the main nav
# A page whose name contains one of these is a legal / utility page and defaults to No in the main nav.
NAV_NO_WORDS = ('privacy', 'terms', 'cookie', 'accessibility', 'sitemap', 'disclaimer', 'hipaa', 'notice', 'thank', '404')
NAV_FIXED_KINDS = ('Home', 'blog_index', 'blog')   # not changeable by the SEO

YELLOW = PatternFill('solid', fgColor='FFF2CC')
HEAD = PatternFill('solid', fgColor='D9E1F2')


# ---------- helpers ----------
def slugify(name):
    s = re.sub(r'\([^)]*\)', ' ', name)                # text in brackets is dropped
    s = s.replace('+', ' plus ').replace('&', ' and ')
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def last_segment(name):
    return name.split('>')[-1].strip()


def norm(name):
    return re.sub(r'\s+', ' ', (name or '').strip()).lower()


def clean_path(p):
    p = (p or '').strip()
    if not p:
        return ''
    p = re.sub(r'^https?://[^/]+', '', p)
    if not p.startswith('/'):
        p = '/' + p
    return p if p == '/' else p.rstrip('/')


def read_roadmap(path):
    wb = load_workbook(path, data_only=True)
    for tab in ('Roadmap', 'Internal links'):
        if tab not in wb.sheetnames:
            raise SystemExit(f"The roadmap has no '{tab}' tab. Run the latest new-site-content-roadmap skill first.")
    client = ''
    if 'Read Me' in wb.sheetnames:
        for r in wb['Read Me'].iter_rows(values_only=True):
            if r[0] and str(r[0]).startswith('New site content roadmap'):
                client = r[1] or ''
    rows = list(wb['Roadmap'].iter_rows(values_only=True))
    head = [str(h or '') for h in rows[0]]

    def col(prefix, exact=False):
        for i, h in enumerate(head):
            if (h == prefix) if exact else h.lower().startswith(prefix.lower()):
                return i
        raise SystemExit(f"The Roadmap tab has no column starting with '{prefix}'.")

    c_page, c_type = col('Page', exact=True), col('Page type')
    c_parent, c_anchor = col('Parent page'), col('Must appear on page')
    pages = []
    for r in rows[1:]:
        if r[c_page]:
            pages.append(dict(name=str(r[c_page]).strip(), type=str(r[c_type] or '').strip(),
                              parent=str(r[c_parent] or '').strip(),
                              anchors=[a.strip() for a in str(r[c_anchor] or '').split(';') if a.strip()]))
    cut = 0
    if 'Cut for the 50-page cap' in wb.sheetnames:
        crow = list(wb['Cut for the 50-page cap'].iter_rows(values_only=True))
        hdr = next((i for i, r in enumerate(crow) if r and r[0] == '#'), 0)
        cut = sum(1 for r in crow[hdr + 1:] if r[1])
    lrows = list(wb['Internal links'].iter_rows(values_only=True))
    lh = [str(h or '') for h in lrows[0]]
    li = {k: next((i for i, h in enumerate(lh) if h.lower().startswith(k)), None) for k in ('from', 'to', 'priority', 'anchor', 'where')}
    for k in ('from', 'to', 'anchor'):
        if li[k] is None:
            raise SystemExit(f"The roadmap's Internal links tab has no '{k}' column.")
    links = [dict(src=str(r[li['from']]).strip(), tgt=str(r[li['to']]).strip(), anchor=r[li['anchor']] or '',
                  where=(r[li['where']] or '') if li['where'] is not None else '',
                  prio=(r[li['priority']] or '') if li['priority'] is not None else None)
             for r in lrows[1:] if r[li['from']] and r[li['to']]]
    return client, pages, cut, links


def read_csv(path):
    out = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames or 'Page' not in [h.strip() for h in rd.fieldnames]:
            raise SystemExit("The CSV needs a 'Page' column (and an optional 'URL' column).")
        for r in rd:
            r = {k.strip(): v for k, v in r.items() if k}
            name = (r.get('Page') or '').strip()
            if name:
                out.append((name, (r.get('URL') or '').strip()))
    return out


# ---------- plan ----------
def plan(roadmap_path, csv_path):
    client, rmap, cut_count, rlinks = read_roadmap(roadmap_path)
    extra_rows = read_csv(csv_path)
    warnings = []

    pages, by_name = [], {}
    for p in rmap:
        is_blog = p['type'] == 'Blog'
        parent = re.sub(r'\s+page$', '', p['parent']) if is_blog else p['parent']
        kind = 'blog' if is_blog else 'extra' if p['type'].startswith('Extra') else p['type']
        d = dict(name=p['name'], type=p['type'], parent=parent, anchors=p['anchors'], kind=kind,
                 notes=[], url_source='Recommended', content='Yes')
        pages.append(d)
        by_name[norm(d['name'])] = d

    for d in pages:
        if d['parent'] and norm(d['parent']) not in by_name:
            warnings.append(f"Parent '{d['parent']}' of '{d['name']}' is not on the roadmap (cut or missing). No parent used for it.")
            d['parent'] = ''

    def top_of(d):
        seen = set()
        while d['parent'] and norm(d['parent']) in by_name and id(d) not in seen:
            seen.add(id(d))
            d = by_name[norm(d['parent'])]
        return d

    for d in pages:
        if d['kind'] == 'Home':
            d['path'] = '/'
        elif d['kind'] == 'blog':
            parent_name = last_segment(d['parent']) if d['parent'] else ''
            m = re.search(r'Blog\s*(\d)', d['name'])
            node = slugify(parent_name) or slugify(re.sub(r'^Blog \d:\s*', '', d['name']))
            lead = 'prepare-for-' if (m and m.group(1) == '1') else 'choosing-a-provider-for-'
            d['path'] = f'{BLOG_PREFIX}/{lead}{node}'
            d['notes'].append('Placeholder: titles are not set, so confirm this URL once the writer picks the title.')
        else:
            slug = slugify(last_segment(d['name']))
            pre = SERVICE_PREFIX if d['kind'] in SERVICE_KINDS else ''
            if d['parent']:
                top = top_of(d)
                d['path'] = f"{pre}/{slugify(last_segment(top['name']))}/{slug}"
                if norm(top['name']) != norm(d['parent']):
                    d['notes'].append(f"URL sits directly under {last_segment(top['name'])} (not under {last_segment(d['parent'])}) "
                                      f"to keep URLs one level below the Service; the linking parent is {d['parent']}.")
            else:
                d['path'] = f'{pre}/{slug}'
            if '(' in last_segment(d['name']):
                d['notes'].append('Text in brackets dropped from the URL. Confirm it.')

    seen_names = set(by_name)
    for name, url in extra_rows:
        if norm(name) in seen_names:
            warnings.append(f"'{name}' is in the CSV and already on the roadmap. Kept the roadmap row only.")
            continue
        seen_names.add(norm(name))
        provided = clean_path(url)
        d = dict(name=name, type='Other (no content from us)', parent='', anchors=[], kind='other', notes=[], content='No',
                 url_source='Provided' if provided else 'Recommended', path=provided or f'/{slugify(name)}',
                 nav_forced='No' if any(w in norm(name) for w in NAV_NO_WORDS) else 'Yes')
        pages.append(d)
        by_name[norm(name)] = d

    blogs = [d for d in pages if d['kind'] == 'blog']
    if blogs and norm(BLOG_INDEX_NAME) not in by_name:
        d = dict(name=BLOG_INDEX_NAME, type='Blog index (added by this skill)', parent='', anchors=[], kind='blog_index',
                 notes=['Added by the IA skill: the blog posts need an index page. Remove it if the client has no blog section.'],
                 content='No', url_source='Recommended', path=BLOG_PREFIX)
        pages.append(d)
        by_name[norm(d['name'])] = d

    for d in pages:
        d['nav'] = d.get('nav_forced') or ('Yes' if d['kind'] in ('Home', 'About Us', 'Service', 'extra', 'blog_index') else 'No')

    paths = {}
    for d in pages:
        paths.setdefault(d['path'], []).append(d['name'])
    for p, names in paths.items():
        if len(names) > 1:
            warnings.append(f"URL {p} is used by more than one page: {', '.join(names)}.")
    n_nav = sum(1 for d in pages if d['nav'] == 'Yes')
    if n_nav > MAX_NAV:
        warnings.append(f'{n_nav} pages are marked Yes for the main nav. Group Services under one dropdown and trim the rest.')

    # Links: copied from the roadmap, URLs added. Nothing is added, removed or re-anchored.
    links, inbound = [], {}
    for l in rlinks:
        src, tgt = by_name.get(norm(l['src'])), by_name.get(norm(l['tgt']))
        if not src or not tgt:
            warnings.append(f"Roadmap link {l['src']} -> {l['tgt']} skipped: a page is not on the Pages tab.")
            continue
        if not l['anchor']:
            warnings.append(f"Link {l['src']} -> {l['tgt']} has no anchor text in the roadmap. SEO to add one.")
        links.append((src['name'], src['path'], tgt['name'], tgt['path'], l['anchor'], l['where'], l['prio']))
        inbound.setdefault(id(tgt), []).append(l['anchor'])
    for d in pages:
        if d['kind'] in SERVICE_KINDS + ('Concern',) and not inbound.get(id(d)):
            warnings.append(f"No planned link points at '{d['name']}'. Fix it in the roadmap's Internal links tab.")
        if d['anchors']:
            got = {norm(x) for x in inbound.get(id(d), [])}
            missed = [t for t in d['anchors'] if norm(t) not in got]
            if missed:
                warnings.append(f"Roadmap gap: '{d['name']}' must carry these terms because they are anchor text for links to it, "
                                f"but no link in the roadmap's Internal links tab uses them: {'; '.join(missed)}. Add a link in the roadmap.")
    return dict(client=client, pages=pages, blogs=blogs, links=links, warnings=warnings, cut=cut_count,
                rlinks=rlinks, rpages=rmap, n_nav=n_nav)


# ---------- workbook ----------
def write_workbook(res, out_path, client=''):
    pages, blogs, links, warnings = res['pages'], res['blogs'], res['links'], res['warnings']
    wb = Workbook()
    ws = wb.active
    ws.title = 'Pages'
    ws.append(['Page name', 'Page type', 'Recommended parent page', 'Recommended URL path', 'URL source (Provided / Recommended)',
               'In main nav (Yes / No). SEO: change any yellow cell if needed', 'Content from us (Yes / No)', 'Notes'])
    order = [d for d in pages if d['kind'] not in ('blog', 'blog_index')] + [d for d in pages if d['kind'] == 'blog_index'] + blogs
    for d in order:
        ws.append([d['name'], d['type'], d['parent'], d['path'], d['url_source'], d['nav'], d['content'], ' '.join(d['notes'])])
        if d['url_source'] == 'Recommended':
            ws.cell(ws.max_row, 4).fill = YELLOW
        if d['kind'] not in NAV_FIXED_KINDS:
            ws.cell(ws.max_row, 6).fill = YELLOW
    dv = DataValidation(type='list', formula1='"Yes,No"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(f'F2:F{ws.max_row}')
    widths = [48, 26, 34, 52, 20, 22, 16, 70]

    ws2 = wb.create_sheet('Internal links')
    has_prio = any(l[6] is not None for l in links)
    ws2.append(['From page', 'From URL', 'To page', 'To URL', 'Anchor text', 'Where this link came from'] + (['Priority'] if has_prio else []))
    for l in links:
        ws2.append(list(l) if has_prio else list(l[:6]))
    widths2 = [48, 40, 48, 40, 38, 34, 10]

    ws3 = wb.create_sheet('Read Me')
    ws3.append(['Item', 'Detail'])
    rows = [
        ('New site information architecture', client or res['client'] or ''),
        ('Built from', "The content roadmap (Roadmap and Internal links tabs) and the CSV of other pages. Nothing was looked up live."),
        ('What this is', f"Every page that goes on the new site with its parent, URL path and whether it is in the main nav: {len(order)} pages "
                         f"({len(blogs)} blog posts). {res['cut']} pages and blogs the roadmap cut for the 50-page cap are not here."),
        ('URL rules', 'Lowercase, hyphens, no accents, no trailing slash, text in brackets dropped. Service, Sub-Service and Brand / Device pages '
                      'sit under /services/ so performance can be tracked for all of them with one path filter. A Sub-Service or Brand / Device sits '
                      'one level under its top-level Service, so no URL has more than three segments (/services/service/child). /services/ itself is '
                      'not added as a page: add it only if the client wants a hub page with content, and link the Service pages straight from the nav. '
                      'Other pages (About Us, extras, Concerns) sit at the root; blog posts sit under /blog. Yellow URLs are recommended by us: the SEO '
                      'checks them. URLs the client provided are used as given.'),
        ('Blog URLs', 'Blog titles are not set, so these are placeholders built from the post angle and the page it supports. Confirm each once the title is chosen.'),
        ('Main nav', "Always Yes: Home and the blog index. Always No: individual blog posts. Otherwise Yes for About Us, Services, the SEO's extra pages "
                     'and other pages that are not legal / utility pages. Sub-Services, Brands / Devices and Concerns are No: they are reached from their '
                     'parent page. Yellow cells are recommendations the SEO can change (the column header says so). Home, the blog index and blog posts are fixed and not yellow.'),
        ('Internal links tab', "The roadmap's Internal links tab with the URL of each page added. The links and anchor text (and priority, when the roadmap "
                               "has it) are the roadmap's; this skill adds no links. It checks them: every Service, Sub-Service and Brand / Device page has "
                               "a link pointing at it, and every 'Must appear on page' term is used as anchor text on at least one link. Anything it finds "
                               'is listed as a warning, to be fixed in the roadmap. It never changes a link.'),
        ('Not planned', 'Links from the blog index to each post, and links from service pages to the booking page. The menu and footer are not on this tab.'),
    ]
    for r in rows:
        ws3.append(list(r))
    for w in warnings:
        ws3.append(('Warning', w))

    for sheet, w in ((ws, widths), (ws2, widths2)):
        for i, wd in enumerate(w):
            sheet.column_dimensions[chr(65 + i)].width = wd
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
    ws3.column_dimensions['A'].width = 32
    ws3.column_dimensions['B'].width = 130
    for sheet in (ws, ws2, ws3):
        for c in sheet[1]:
            c.font = Font(bold=True)
            c.fill = HEAD
            c.alignment = Alignment(wrap_text=True, vertical='top')
        for row in sheet.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical='top')
    wb.save(out_path)
    return order


# ---------- checks ----------
def run_checks(res, order, out_path):
    wb = load_workbook(out_path)
    pg = [r for r in wb['Pages'].iter_rows(min_row=2, values_only=True)]
    ln = [r for r in wb['Internal links'].iter_rows(min_row=2, values_only=True)]
    names = {r[0] for r in pg}
    paths = [r[3] for r in pg]
    checks = [
        ('every roadmap page is on the Pages tab', all(p['name'] in names for p in res['rpages'])),
        ('every roadmap link is on the Internal links tab', len(ln) + sum(1 for w in res['warnings'] if w.startswith('Roadmap link')) == len(res['rlinks'])),
        ('every URL starts with / and is unique', all(p.startswith('/') for p in paths) and len(set(paths)) == len(paths)),
        (f'no URL has more than {MAX_SEGMENTS} segments', all(p.count('/') <= MAX_SEGMENTS for p in paths)),
        ('Home and the blog index are Yes, blog posts are No',
         all((r[5] == 'Yes') for r in pg if r[1] == 'Home' or str(r[1]).startswith('Blog index')) and all(r[5] == 'No' for r in pg if r[1] == 'Blog')),
        ('links on the Internal links tab match the roadmap (page, anchor)',
         [(l['src'], l['tgt'], l['anchor']) for l in res['rlinks'] if norm(l['src']) in {norm(n) for n in names} and norm(l['tgt']) in {norm(n) for n in names}]
         == [(r[0], r[2], r[4] or '') for r in ln]),
    ]
    ok = True
    for name, passed in checks:
        print(('PASS ' if passed else 'FAIL ') + name)
        ok = ok and passed
    return ok


# ---------- preflight ----------
def preflight(roadmap, csv_path, out):
    info, warns, fails = [], [], []
    if not roadmap:
        fails.append('The content roadmap workbook is needed (the .xlsx from new-site-content-roadmap).')
    else:
        try:
            _, pages, cut, links = read_roadmap(roadmap)
            kinds = {}
            for p in pages:
                kinds[p['type']] = kinds.get(p['type'], 0) + 1
            info.append(f"Roadmap: {len(pages)} rows ({', '.join(f'{v} {k}' for k, v in kinds.items())}), {len(links)} planned links, {cut} cut for the 50-page cap.")
            if not any(p['type'] == 'Home' for p in pages):
                fails.append('The Roadmap tab has no Home row.')
            if not links:
                fails.append("The roadmap's Internal links tab is empty.")
        except SystemExit as e:
            fails.append(str(e))
    if not csv_path:
        fails.append('A CSV of every other page the site needs is required (Contact, Privacy Policy, booking, membership and so on). Columns: Page, URL. '
                     'The URL is optional: we recommend one when it is blank.')
    else:
        try:
            rows = read_csv(csv_path)
            blank = [n for n, u in rows if not u]
            info.append(f'CSV: {len(rows)} other pages, {len(blank)} without a URL (a path will be recommended).')
            if not rows:
                warns.append('The CSV lists no pages. Confirm the site needs none beyond the roadmap.')
        except SystemExit as e:
            fails.append(str(e))
    status = 'NOT READY' if fails else 'READY'
    lines = ['# Preflight', f'**{status}**', ''] + [f'- INFO {i}' for i in info] + [f'- WARN {w}' for w in warns] + [f'- FAIL {f}' for f in fails]
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'preflight.md'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    if fails:
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('preflight')
    p.add_argument('--roadmap')
    p.add_argument('--csv')
    p.add_argument('--out', default='work')
    b = sub.add_parser('build')
    b.add_argument('--roadmap', required=True)
    b.add_argument('--csv', required=True)
    b.add_argument('--client', default='')
    b.add_argument('--out', required=True)
    a = ap.parse_args()
    if a.cmd == 'preflight':
        preflight(a.roadmap, a.csv, a.out)
        return
    res = plan(a.roadmap, a.csv)
    order = write_workbook(res, a.out, a.client)
    print(f"{len(order)} pages ({len(res['blogs'])} blog posts), {len(res['links'])} links, {res['n_nav']} in the main nav")
    for w in res['warnings']:
        print('WARNING:', w)
    if not run_checks(res, order, a.out):
        sys.exit(1)


if __name__ == '__main__':
    main()
