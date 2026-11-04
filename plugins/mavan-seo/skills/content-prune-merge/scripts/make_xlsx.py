#!/usr/bin/env python3
"""Build the Content Prune & Merge workbook from build.py's output.

Usage:
  python make_xlsx.py --work work --rules $SKILL/references/rules.md --out "Client Content Prune & Merge.xlsx"

Reads work/audit.tsv, work/existing_redirects.tsv and work/run.json (written by build.py), and the
"Workbook README" table in references/rules.md (so the README always matches the rules).

Tabs, in this order, each only when it has rows: Recommendations, Check page type, Kept pages,
Needs discussion, Junk folders, Remove pages, All redirects - Handoff to Dev, Redirects needing a target,
Merge pages, Per location service pages, Redirect after merge, Menu cleanup, Update pages,
Repurpose pages, Blog beats service, README. Each page appears on one action tab; each redirect source
appears on one redirect tab. All wording below is fixed: Claude does not rewrite it per run.

Text that looks like a number or a formula (a leading = + - @) is stored as text, never evaluated.
"""
import argparse
import csv
import json
import math
import os
import re
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# ---------- colors (from the Working Improvements prototype) ----------
YELLOW, GREY, GREEN, BLUE, ORANGE = 'FFF2C6', 'D8D8D8', 'D1EAD1', 'CCE0FF', 'FCE5CD'
TAB_ORANGE, TAB_GREY, TAB_GREEN, TAB_BLUE = 'F28C19', '7F7F7F', '339E4C', '3366D8'
FONT = 'Arial'
FILL_IN = 'SEO fill in'
WHY = 'Why Claude made this recommendation (SEO QA only; delete before handoff)'

# ---------- tab names (banners and other tabs refer to these) ----------
REC, CPT, KEPT, DISC = 'Recommendations', 'Check page type', 'Kept pages', 'Needs discussion'
JUNK, REM, DEV, NEED = 'Junk folders', 'Remove pages', 'All redirects - Handoff to Dev', 'Redirects needing a target'
MERGE, LOC, RAM, MENU = 'Merge pages', 'Per location service pages', 'Redirect after merge', 'Menu cleanup'
UPD, REP, BBS, README = 'Update pages', 'Repurpose pages', 'Blog beats service', 'README'

DONE_REDIRECT = 'SEO QA REVIEW: check every row and edit any cell that is wrong before sending. Redirects are already in dev handoff. If you update these, please ask Claude to review the sheet for updates on this tab or manually update the affected tabs'
UPDATE_NOTE = ('When you are done, ask Claude in the same chat where this audit was run to review this tab and update the other tabs. '
               'A new chat will not have the audit rules or data.')

# Recommendations rows: Issue | Priority | Fix | Tab(s) for SEO to Review | Tab(s) to hand off | Handoff to | Order.
# The count column is filled in code.
RECS = {
    CPT: ('Pages where the page type is a guess (SEO only)', 'Medium', 'SEO checks and corrects the page type. Not sent to the implementer.',
          CPT, 'None (SEO only)', 'Nobody (SEO only)', 1),
    DISC: ('Pages that need a decision from the client (SEO only)', 'Medium', 'SEO asks the client the question on each row. Not sent to the implementer.',
           DISC, 'None (SEO only)', 'Nobody (SEO only)', 1),
    JUNK: ('Junk archive folders', 'High', 'Redirect each folder and turn the archives off in the SEO plugin.',
           f'{JUNK}, and {DEV}', DEV, 'Dev', 2),
    REM: ('Blog posts with no traffic', 'Medium', 'Delete each post and redirect it.', f'{REM}, and {DEV}', DEV, 'Dev', 3),
    'old': ('Old redirects that end on dead or wrong pages', 'High', 'Change each old redirect to point at the correct live page.',
            DEV, DEV, 'Dev', 4),
    NEED: ('Old URLs with no page to redirect to (SEO only)', 'Medium',
           f'SEO picks a live page for each one, then adds the row to {DEV}.', NEED, f'{DEV} (after SEO fills in)', 'Dev', 4),
    MERGE: ('Pages that overlap a stronger page', 'High', 'Merge each page into the stronger page, then redirect it.',
            f'{MERGE}, and {RAM}', f'{MERGE} (Content), then {RAM} (Dev)', 'Content (merge), then Dev (redirect)', '5 - Redirect AFTER merge'),
    LOC: ('Service pages copied for another location', 'High',
          'Merge each page marked Merge into its main page, then redirect it. Pages marked Keep earn their own clicks and stay.',
          f'{LOC}, and {RAM}', f'{LOC} (Content), then {RAM} (Dev)', 'Content (merge), then Dev (redirect)', '5 - Redirect AFTER merge'),
    MENU: ('Menu items that point to merged or redirected pages', 'Medium', 'Replace each menu item with the page we keep.',
           MENU, MENU, 'Dev', '6 - After the merges are live'),
    UPD: ('Service pages named after a brand instead of the treatment', 'Medium', 'Replace the title, H1 and first sentence with the text provided.',
          UPD, UPD, 'Content', '7 - Anytime'),
    REP: ('Blog posts that get buying searches', 'Medium', 'SEO decides what each one becomes before handoff.',
          REP, REP, 'Content (after SEO decides what to do with the pages)', '8 - After SEO decides'),
    BBS: ('Blog posts that get more clicks than the service page', 'Medium', 'SEO decides what each one needs before handoff.',
          BBS, BBS, 'Content (after SEO decides what to do with the pages)', '8 - After SEO decides'),
}
TWO_CITY = ' With only two locations, also make the main page name both in its title and H1.'

HOW_TO = [
    'Check every green tab. Look at each row and fix any cell that is wrong.',
    "Fill every orange 'SEO fill in' cell. Do not send the sheet with any left.",
    'Check the grey tabs (Check page type and Kept pages). If you disagree with Claude, type the change in the tab.',
    'If you change anything, ask Claude in the same chat where this audit was run to review the tab and update the other tabs. '
    'Claude updates the counts and the redirect tabs, so do not edit those by hand. A new chat will not have the audit rules or data.',
    "Before sending: delete the banner row on each tab, the 'Why Claude made this recommendation' columns, the grey tabs and this README.",
    f"Redirects: after QA, download '{DEV}' as a CSV for the developer. '{RAM}' is sent only after the merges are live.",
]


# ---------- reading ----------
def read_tsv(path, width):
    rows = []
    if not path or not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
            if any(c.strip() for c in r):
                rows.append((r + [''] * width)[:width])
    return rows


def readme_rules(path):
    """The '## Workbook README' table in rules.md: Tab | Rule Claude applied | What you need to QA | Handoff to."""
    text = open(path, encoding='utf-8').read()
    m = re.search(r'^## Workbook README\n(.*?)(?=^## |\Z)', text, re.S | re.M)
    if not m:
        sys.exit('rules.md has no "## Workbook README" table')
    out = {}
    for line in m.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) == 4 and cells[0] not in ('Tab', '---') and not set(cells[0]) <= set('-: '):
            out[cells[0]] = cells[1:]
    return out


def why(notes):
    return re.sub(r'^Suggested because:\s*', '', notes).strip()


# ---------- writing helpers ----------
def put(ws, r, c, v, fill=None, bold=False):
    cell = ws.cell(row=r, column=c)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        cell.value = v
    else:
        v = '' if v is None else str(v)
        cell.value = v
        cell.data_type = 's'  # text, even when it starts with = + - @ or looks like a number
        cell.number_format = '@'
    cell.font = Font(name=FONT, bold=bold)
    cell.alignment = Alignment(wrap_text=True, vertical='top')
    if fill:
        cell.fill = PatternFill('solid', fgColor=fill)
    return cell


def as_num(v):
    try:
        x = float(str(v).replace(',', ''))
        return int(x) if x == int(x) else x
    except ValueError:
        return v


def sheet(wb, name, tab_color, banner, cols, rows, widths):
    """cols: list of (header, kind) where kind is 'impl' (green), 'why' (grey), 'fill' (orange), 'info' (grey)."""
    ws = wb.create_sheet(name)
    ws.sheet_properties.tabColor = tab_color
    n = len(cols)
    start = 1
    if banner:
        put(ws, 1, 1, banner, fill=YELLOW, bold=True)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
        chars = sum(widths) * 0.9  # bold text runs wider than the column width units
        ws.row_dimensions[1].height = max(45, 15 * math.ceil(len(banner) / chars) + 8)
        start = 2
    for i, (h, kind) in enumerate(cols, 1):
        put(ws, start, i, h, fill={'impl': GREEN, 'why': GREY, 'fill': ORANGE, 'info': GREY, 'dev': BLUE}[kind], bold=True)
    for r, row in enumerate(rows, start + 1):
        for i, v in enumerate(row, 1):
            kind = cols[i - 1][1]
            put(ws, r, i, v, fill=ORANGE if (kind == 'fill' and v == FILL_IN) else None)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=start + 1, column=1)
    return ws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work')
    ap.add_argument('--rules', required=True, help='references/rules.md of this skill')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    W = lambda f: os.path.join(a.work, f)
    audit = read_tsv(W('audit.tsv'), 25)
    existing = read_tsv(W('existing_redirects.tsv'), 3)
    run = json.load(open(W('run.json'), encoding='utf-8'))
    rules = readme_rules(a.rules)
    copies = run.get('copies', {})
    beats = run.get('blog_beats', {})

    by = lambda step: [r for r in audit if r[19] == step]
    merged = by('Merge then Redirect')
    removed = by('Remove then Redirect')

    T = {}  # tab -> rows
    T[CPT] = [[r[0], r[1], FILL_IN, r[2]] for r in audit if 'Root-level' in r[2] or 'No rule matched' in r[2]]
    T[DISC] = [[r[0], FILL_IN, why(r[24])] for r in by('Needs Discussion')]
    T[LOC] = [[r[0], copies[r[0]], as_num(r[16]), 'Merge into the main page' if r[19] == 'Merge then Redirect' else 'Keep',
               FILL_IN if r[19] == 'Merge then Redirect' else '', why(r[24])] for r in audit if r[0] in copies]
    T[MERGE] = [[r[0], r[20], FILL_IN, why(r[24])] for r in merged if r[0] not in copies]
    T[REM] = [[r[0], r[20], why(r[24])] for r in removed]
    T[UPD] = [[r[0], FILL_IN, FILL_IN, FILL_IN, f'{why(r[24])} Current title: {r[6]}. Current H1: {r[7]}.'] for r in by('Update')]
    T[REP] = [[r[0], FILL_IN, why(r[24])] for r in by('Repurpose')]
    T[BBS] = [[r[0], beats[r[0]], FILL_IN, why(r[24])] for r in audit if r[0] in beats and r[19] in ('Keep', 'Update')]
    on_action = {x[0] for t in (LOC, MERGE, REM, UPD, REP, BBS, DISC) for x in T[t]}
    T[KEPT] = [[r[0], r[1], as_num(r[16]), as_num(r[17]), why(r[24]), ''] for r in audit
               if r[19] == 'Keep' and r[0] not in on_action]

    wild = [x for x in existing if x[0].endswith('*')]
    old = [x for x in existing if not x[0].endswith('*') and x[1]]
    need = [x for x in existing if not x[0].endswith('*') and not x[1]]
    T[JUNK] = [[x[0], x[1], x[2]] for x in wild]
    T[NEED] = [[x[0], FILL_IN, x[2]] for x in need]
    dev = [[x[0][:-1] + '(.*)', x[1], 1, 301] for x in wild] + [[r[0], r[20], 0, 301] for r in removed] + \
          [[x[0], x[1], 0, 301] for x in old]
    T[DEV] = dev
    T[RAM] = [[r[0], r[20], f'Page is being merged ({LOC if r[0] in copies else MERGE} tab)',
               "Add after the merge is live. Old URL lands on the 'Redirect to' page in one step."] for r in merged]
    # With an IA audit workbook, its Menu cleanup and Fix links tabs already decide these menu items: do not repeat them.
    ia_menu = set(run.get('ia_menu', []))
    menu, seen = [], set(ia_menu)
    for r in merged + removed:
        if 'In main menu' in r[24] and r[0] not in seen:
            seen.add(r[0])
            tab = LOC if r[0] in copies else (MERGE if r in merged else REM)
            menu.append([r[0], r[20], f'In the main menu. Page is being {"merged" if r in merged else "removed"} ({tab} tab).'])
    for s, t in ({} if run.get('ia') else run.get('menu_redirects', {})).items():
        if s not in seen:
            seen.add(s)
            menu.append([s, t, 'In the main menu, but this URL redirects. Link straight to the page it lands on.'])
    T[MENU] = menu

    # every redirect source on exactly one redirect tab
    srcs = [x[0] for x in dev] + [x[0] for x in T[RAM]] + [x[0] for x in T[NEED]]
    dupes = sorted({s for s in srcs if srcs.count(s) > 1})
    if dupes:
        sys.exit(f'A source URL appears on two redirect tabs: {dupes[:5]}')

    present = {t for t, rows in T.items() if rows}
    merge_tabs = ' or '.join(t for t in (MERGE, LOC) if t in present) or MERGE

    banners = {
        CPT: 'SEO ONLY, do not send to the implementer. Nothing on the site says what kind of page each of these is, so the page type is a guess '
             'from the URL. Check each page and type the correct page type in column C. ' + UPDATE_NOTE +
             " A changed page type can change that page's recommendation, the Recommendations counts and the redirect tabs. Delete this tab before handoff.",
        KEPT: 'SEO ONLY, do not send to the implementer. These are the pages Claude decided to leave alone. Check the page type and the reason. '
              'If you disagree, type the change you want in column F (if the page should merge or redirect, include the target URL). Then ask Claude '
              'in the same chat where this audit was run to review this tab and update the sheet. A new chat will not have the audit rules or data. '
              'Claude will move the page to the right issue tab and update the Recommendations counts and redirect tabs. Delete this tab before handoff.',
        DISC: 'SEO ONLY, do not send to the implementer. Each page needs a business decision the audit cannot make. Ask the client the question in '
              'column B and record the answer. ' + UPDATE_NOTE + ' Delete this tab before handoff.',
        JUNK: DONE_REDIRECT,
        REM: DONE_REDIRECT,
        NEED: f'SEO ONLY. These old URLs get searches or links, but no live page has the same slug, so Claude did not guess a target. '
              f'Type a live page in column B, then add the row to {DEV}. Delete this tab before handoff.',
        MERGE: "SEO QA REVIEW: check every row, edit any cell that is wrong, and fill every cell marked 'SEO fill in' before sending. "
               'In column C add the content that should be added to the page in column B. Delete this row before handoff.',
        LOC: "SEO QA REVIEW: check every row, edit any cell that is wrong, and fill every cell marked 'SEO fill in' before sending. "
             'Each page copies a main page for another location. Rows marked Merge: add the content in column E to the main page in column B. '
             'Rows marked Keep earn their own clicks and stay. Delete this row before handoff.',
        RAM: f'SEO QA REVIEW: check every row and edit any cell that is wrong before sending. Add these redirects ONLY after the merges on the '
             f'{merge_tabs} tab are live. Delete this row before handoff.',
        MENU: f'SEO QA REVIEW: check every row and edit any cell that is wrong before sending. Do this AFTER the merges on the {merge_tabs} tab are live. '
              'In the main menu, replace the menu item in column A with the page in column B. Delete this row before handoff.',
        UPD: "SEO QA REVIEW: check every row and fill every cell marked 'SEO fill in' before sending. On the page in column A, replace the title, "
             'H1 and first sentence with the text in columns B, C and D. Keep the brand name only as a supporting term. Delete this row before handoff.',
        REP: f'SEO QA REVIEW: these blog posts get buying searches. Fill column B with one plain sentence telling the implementer exactly what to do '
             f'with each page before sending. If a URL changes, add the redirect to the {DEV} tab. Delete this row before handoff.',
        BBS: 'SEO QA REVIEW: each blog post gets more clicks than the service page on the same topic. Fill column C with one plain sentence telling '
             'the implementer exactly what to do before sending. Delete this row before handoff.',
    }

    wb = Workbook()
    ws = wb.active
    ws.title = REC
    ws.sheet_properties.tabColor = TAB_ORANGE
    head = ['Issue', 'Priority', 'Fix', 'Number of Pages Affected', 'Tab(s) for SEO to Review', 'Tab(s) to hand off', 'Handoff to',
            'Order (do in this order)']
    for i, h in enumerate(head, 1):
        put(ws, 1, i, h, fill=GREY, bold=True)
    ws.freeze_panes = 'A2'
    counts = {t: len(T[t]) for t in T}
    counts[JUNK] = sum(run.get('junk_pages', {}).values())
    counts['old'] = len(old)
    r = 2
    for k, (issue, pri, fix, review, hand, who, order) in RECS.items():
        n = counts.get(k, 0)
        if not n:
            continue
        if k == LOC and run.get('separate_cities') == 1:
            fix += TWO_CITY
        for i, v in enumerate([issue, pri, fix, n, review, hand, who, order], 1):
            put(ws, r, i, v)
        r += 1
    for i, w in enumerate([37.6, 10.1, 42.6, 13.9, 32.6, 32.6, 25.1, 22], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    G = lambda t: T[t]
    if G(CPT):
        sheet(wb, CPT, TAB_GREY, banners[CPT], [('Page (SEO: QA this URL)', 'info'), ('Page type we guessed', 'info'),
              ('Correct page type (SEO fill in)', 'fill'), ('Why we guessed', 'info')], G(CPT), [50.1, 22.6, 27.6, 30.1])
    if G(KEPT):
        sheet(wb, KEPT, TAB_GREY, banners[KEPT], [('Page (SEO: QA this URL)', 'info'), ('Page type', 'info'), ('Clicks', 'info'),
              ('Impressions', 'info'), (WHY, 'why'), ('Disagree? Type the change you want (SEO fill in)', 'fill')], G(KEPT),
              [47.6, 21.4, 8.9, 11.4, 50.1, 32.6])
    if G(DISC):
        sheet(wb, DISC, TAB_GREY, banners[DISC], [('Page (SEO: QA this URL)', 'info'), ('Question for the client (SEO fill in)', 'fill'),
              (WHY, 'why')], G(DISC), [47.6, 45.1, 50.1])
    if G(JUNK):
        sheet(wb, JUNK, TAB_GREEN, banners[JUNK], [('Folder to redirect (SEO: QA this folder)', 'impl'),
              ('Redirect to (SEO: confirm or change)', 'impl'), (WHY, 'why')], G(JUNK), [41.4, 41.4, 47.6])
    if G(REM):
        sheet(wb, REM, TAB_GREEN, banners[REM], [('Page to remove (SEO: QA this URL)', 'impl'),
              ('Redirect to (SEO: confirm or change)', 'impl'), (WHY, 'why')], G(REM), [47.6, 41.4, 45.1])
    if G(DEV):
        sheet(wb, DEV, TAB_BLUE, None, [('Source URL', 'dev'), ('Target URL', 'dev'), ('Regex (0 = no, 1 = yes)', 'dev'),
              ('HTTP Code', 'dev')], G(DEV), [60.1, 50.1, 18.9, 11.4])
    if G(NEED):
        sheet(wb, NEED, TAB_GREY, banners[NEED], [('Old URL (SEO: QA this URL)', 'info'), ('Redirect to (SEO fill in)', 'fill'),
              (WHY, 'why')], G(NEED), [47.6, 41.4, 50.1])
    if G(MERGE):
        sheet(wb, MERGE, TAB_GREEN, banners[MERGE], [('Page that will be removed after merge (SEO: QA this URL)', 'impl'),
              ('Page we are keeping (SEO: confirm or change)', 'impl'),
              ("Unique content to copy over (SEO fill in; write 'none' if nothing)", 'fill'), (WHY, 'why')], G(MERGE), [41.4, 41.4, 27.6, 45.1])
    if G(LOC):
        sheet(wb, LOC, TAB_GREEN, banners[LOC], [('Location page (SEO: QA this URL)', 'impl'), ('Main page (SEO: confirm or change)', 'impl'),
              ('Clicks', 'info'), ('What to do (SEO: confirm or change)', 'impl'),
              ("Unique content to copy over (SEO fill in on Merge rows; write 'none' if nothing)", 'fill'), (WHY, 'why')],
              G(LOC), [41.4, 41.4, 8.9, 18, 27.6, 45.1])
    if G(RAM):
        sheet(wb, RAM, TAB_GREEN, banners[RAM], [('Old URL (SEO: QA this URL)', 'impl'), ('Redirect to (SEO: confirm or change)', 'impl'),
              (WHY, 'why'), ('Done when', 'impl')], G(RAM), [47.6, 41.4, 32.6, 35.1])
    if G(MENU):
        sheet(wb, MENU, TAB_GREEN, banners[MENU], [('Menu item to replace (SEO: QA this URL)', 'impl'),
              ('Replace with (SEO: confirm or change)', 'impl'), (WHY, 'why')], G(MENU), [72.0, 45.1, 42.6])
    if G(UPD):
        sheet(wb, UPD, TAB_GREEN, banners[UPD], [('Page to update (SEO: QA this URL)', 'impl'), ('New title (SEO fill in)', 'fill'),
              ('New H1 (SEO fill in)', 'fill'), ('New first sentence (SEO fill in)', 'fill'), (WHY, 'why')], G(UPD),
              [42.6, 25.1, 25.1, 27.6, 50.1])
    if G(REP):
        sheet(wb, REP, TAB_GREEN, banners[REP], [('Blog post (SEO: QA this URL)', 'impl'), ('What to do (SEO fill in)', 'fill'),
              (WHY, 'why')], G(REP), [42.6, 30.1, 57.6])
    if G(BBS):
        sheet(wb, BBS, TAB_GREEN, banners[BBS], [('Blog post (SEO: QA this URL)', 'impl'), ('Service page (SEO: confirm or change)', 'impl'),
              ('What to do (SEO fill in)', 'fill'), (WHY, 'why')], G(BBS), [42.6, 41.4, 30.1, 50.1])

    # README
    ws = wb.create_sheet(README)
    ws.sheet_properties.tabColor = TAB_GREY
    put(ws, 1, 1, 'README - SEO ONLY. This tab tells you what to QA before sending. Delete this tab before handoff.', fill=YELLOW, bold=True)
    ws.merge_cells('A1:D1')
    ws.row_dimensions[1].height = 30
    row = 2

    def line(cells, fill=None, bold=False, merge_from=None):
        nonlocal row
        for i, v in enumerate(cells, 1):
            if v is not None:
                put(ws, row, i, v, fill=fill, bold=bold)
        if merge_from:
            ws.merge_cells(start_row=row, start_column=merge_from, end_row=row, end_column=4)
        row += 1
    line(['HOW TO USE'], fill=GREY, bold=True)
    for i, s in enumerate(HOW_TO, 1):
        line([f'Step {i}', s], merge_from=2)
    line(['WHAT CLAUDE CHECKED (tab)', 'Rule Claude applied', 'What you need to QA', 'Handoff to'], fill=GREY, bold=True)
    for t, (rule, qa, who) in rules.items():
        tab = DEV if t.startswith(DEV) else t
        if tab in present or (t.startswith(DEV) and old):
            line([t, rule, qa, who])
    ga4 = str(run.get('ga4', ''))
    fm = run.get('folder_map', {})
    cities = run.get('cities', {})
    line(['SETTINGS (this audit)', 'Setting', 'Value used on this audit', 'Notes'], fill=GREY, bold=True)
    line(['Merge overlap', "Share of a page's searches that overlap with a stronger page", f"{run.get('overlap', 0.3):.0%} or more", ''])
    line(['Remove: clicks', 'Clicks a blog post got in the window', '0', 'A post with this few clicks is a candidate to remove.'])
    line(['Remove: impressions', 'Impressions a blog post got in the window', f"Under {run.get('remove_impressions', 50)}",
          'A post below this is a candidate to remove.'])
    line(['Data window', 'How long the search data covers', run.get('window') or FILL_IN, ''])
    line(['GA4', 'Used only when Search Console has 300+ clicks and GA4 has 200+ sessions', ga4 or FILL_IN, ''])
    ia_fm = run.get('ia_folder_map', {})
    line(['Folder map', 'Page type per folder, confirmed in the chat', '; '.join(f'{k} = {v}' for k, v in fm.items()) or 'none', ''])
    if ia_fm:
        line(['Folder map from the IA audit', 'Page type of the pages inside each folder, approved in the IA audit',
              '; '.join(f'{k} = {v}' for k, v in ia_fm.items()), 'Used for folders the map above does not cover.'])
    line(['Locations', 'Main location, and locations treated as separate markets',
          f"Main: {cities.get('main', '')}. Separate: {', '.join(cities.get('separate', [])) or 'none'}", ''])
    line(['DATA USED', 'Source', 'What was taken', 'Notes'], fill=GREY, bold=True)
    line(['Crawl', 'Sitebulb or Screaming Frog export', 'URL, status code, title, H1, links, redirects and canonicals for each page', ''])
    line(['Search Console', 'Search Console export from the person', 'Clicks, impressions and searches for each page, for the window above', ''])
    if run.get('ia'):
        line(['IA audit workbook', 'The SEO\'s working copy', 'Page types, folder map, cities, moves and menu cleanup',
              'Its decisions are treated as approved and are not repeated here.'])
    if ga4 and not ga4.lower().startswith(('skipped', 'not used')):
        line(['GA4', 'Google Analytics 4', 'Sessions, new users, views and key events for each landing page, for the window above', ga4])
        if 'composio' in ga4.lower():
            line(['Composio', None, 'Only the listed fields were pulled.', None], merge_from=None)
    for i, w in enumerate([30.1, 45.1, 52.6, 23.9], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'

    wb.save(a.out)
    print(f'Wrote {a.out}')
    for t in [CPT, KEPT, DISC, JUNK, REM, DEV, NEED, MERGE, LOC, RAM, MENU, UPD, REP, BBS]:
        if T[t]:
            print(f'  {t}: {len(T[t])} rows')
    print(f'  Recommendations: {r - 2} rows; junk folder pages: {counts[JUNK]}; old redirect fixes: {len(old)}')


if __name__ == '__main__':
    sys.exit(main())
