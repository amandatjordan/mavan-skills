#!/usr/bin/env python3
"""Build the Information Architecture audit workbook from analyze.py's output.

Usage:
  python make_xlsx.py --work work --out "Client Information Architecture Audit.xlsx"

Reads work/config.json, work/decisions.json, work/analysis/*.csv and work/analysis/summary.json.
Tabs, in this order, each only when it has rows: Recommendations, Check page type, Moves,
All redirects - Handoff to Dev, Fix links, Menu cleanup, Internal linking opportunities, README.
All wording is fixed here: Claude does not rewrite it per run. The only per-row text is the Why column.
The one exception is decisions.json "extra_recommendations": rows Claude adds when the analysis found an issue
this script has no wording for (see references/deliverable.md). They are marked for the SEO to review.

Style constants are copied into every Mavan skill's script on purpose (no shared module).
Text that looks like a number or a formula (a leading = + - @) is stored as text, never evaluated.
"""
import argparse
import json
import math
import os
import re
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

YELLOW, GREY, GREEN, BLUE, ORANGE = 'FFF2C6', 'D8D8D8', 'D1EAD1', 'CCE0FF', 'FCE5CD'
TAB_ORANGE, TAB_GREY, TAB_GREEN, TAB_BLUE = 'F28C19', '7F7F7F', '339E4C', '3366D8'
FONT = 'Arial'
FILL_IN = 'SEO fill in'
WHY = 'Why Claude made this recommendation (SEO QA only; delete before handoff)'

REC, CPT, MOVES, DEV = 'Recommendations', 'Check page type', 'Moves', 'All redirects - Handoff to Dev'
FIX, MENU, LINK, README = 'Fix links', 'Menu cleanup', 'Internal linking opportunities', 'README'

UPDATE_NOTE = ('When you are done, ask Claude in the same chat where this audit was run to review this tab and update the other tabs. '
               'A new chat will not have the audit rules or data.')
NOOWNER_MIN = 100  # impressions; must match analyze.py NOOWNER_MIN_IMPR (shown in the README)

# Recommendations rows: Issue | Priority | Fix | Tab(s) for SEO to Review | Tab(s) to hand off | Handoff to | Order
RECS = {
    CPT: ('Pages where the page type is a guess (SEO only)', 'Medium', 'SEO checks and corrects the page type. Not sent to the implementer.',
          CPT, 'None (SEO only)', 'Nobody (SEO only)', '1'),
    MOVES: ('Blog posts and service pages that sit outside their folder', 'High',
            'Move each page into the folder shown. Then set up the redirects from the old URLs.',
            f'{MOVES}, and {DEV}', f'{MOVES}, and {DEV}', 'Dev', '2 - After any prune removals and merges are live'),
    FIX: ('Pages that link to a page that no longer exists or redirects', 'Medium',
          'On each page listed, change the link to point to the new URL. Keep the anchor text.',
          FIX, FIX, 'Dev', '3 - After the Moves and redirects are live'),
    MENU: ('Menu items Claude recommends removing', 'Medium',
           'SEO marks each item Keep or Remove. Dev removes the items marked Remove from the main menu.',
           MENU, MENU, 'Dev', '4 - After the Moves and redirects are live'),
    LINK: ('Searches where no page clearly owns the topic', 'Medium',
           'Add each link listed, using the anchor text given. SEO first checks the anchor text exists on the page and writes the sentence '
           'to add if it does not. Where Link to is a new hub page, Content creates that page first.',
           LINK, LINK, 'Content', '5 - Anytime (create hub pages first)'),
}

HOW_TO = [
    'Check Check page type first. Page types decide which pages are blogs, and the Moves tab depends on that.',
    'Check every green tab. Look at each row and fix any cell that is wrong.',
    "Fill every orange 'SEO fill in' cell. Do not send the sheet with any left.",
    'Check the grey tab (Check page type). If you disagree with Claude, type the change in the tab.',
    'If you change anything, ask Claude in the same chat where this audit was run to review the tab and update the other tabs. '
    'Claude updates the counts and dependent tabs, so do not edit those by hand. A new chat will not have the audit rules or data.',
    "Before sending: delete the banner row on each tab, the 'Why Claude made this recommendation' columns, the grey tab and this README.",
    f"If the client also has a prune workbook, send the two workbooks in the order shown in each Recommendations tab. Redirects for removed and "
    f"merged pages are in the prune workbook. Redirects for moved pages are in {DEV} here: download it as a CSV for the developer after QA.",
]

README_RULES = {
    CPT: ('Page type is a guess from the URL wording (root-level pages, short or long slugs, company or utility words). '
          'If a prune workbook was provided, its page types are used instead.',
          'Correct the page type. A different type can change the Moves, Menu and Searches tabs.', 'Nobody (SEO only)'),
    MOVES: (f'Blog post sitting outside a blog folder, or service page sitting outside the service folder. Pages the prune removes or merges are '
            f'not moved. The redirects are in {DEV}.',
            'Confirm each page is really a blog or service page. Confirm the folder. Decide the pages marked SEO fill in. The dev tab has no '
            'separate QA copy, so edit it directly; it holds only rows that are ready now.', 'Dev'),
    FIX: ('Page that links to an old URL that no longer exists (404) or that redirects. One row per linking page. The new URL is the final live '
          'URL after the Moves and any prune redirects. The anchor text stays as it is.',
          'Confirm each new URL is the final live page. Decide the broken links marked SEO fill in.', 'Dev'),
    MENU: ('Claude recommends removing every menu item that is not the homepage, a hub page or a core company page. These are recommendations only.',
           'Type Keep or Remove for every item. Check each hub links to the pages that leave the menu so none is orphaned. Send only the Remove rows.',
           'Dev'),
    LINK: (f'Search reaches 3 or more treatments with no page holding half the impressions, and {NOOWNER_MIN} or more impressions. One row per page '
           'that should link to the page that should own the topic, or to a new hub.',
           'Confirm each page to link to. Check the anchor text exists on each Link from page; if not, write the sentence to add. '
           'Write the URL for each new hub. Check the flagged rows.', 'Content'),
}


# ---------- writing helpers ----------
def put(ws, r, c, v, fill=None, bold=False):
    cell = ws.cell(row=r, column=c)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        cell.value = v
    else:
        v = '' if v is None else str(v)
        cell.value = v
        cell.data_type = 's'
        cell.number_format = '@'
    cell.font = Font(name=FONT, size=10, bold=bold)
    cell.alignment = Alignment(wrap_text=True, vertical='top')
    if fill:
        cell.fill = PatternFill('solid', fgColor=fill)
    return cell


def sheet(wb, name, tab_color, banner, cols, rows, widths):
    """cols: list of (header, kind): 'impl' green, 'why' grey, 'fill' orange, 'info' grey, 'dev' blue."""
    ws = wb.create_sheet(name)
    ws.sheet_properties.tabColor = tab_color
    n, start = len(cols), 1
    if banner:
        put(ws, 1, 1, banner, fill=YELLOW, bold=True)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
        ws.row_dimensions[1].height = max(45, 15 * math.ceil(len(banner) / (sum(widths) * 0.9)) + 8)
        start = 2
    for i, (h, kind) in enumerate(cols, 1):
        put(ws, start, i, h, fill={'impl': GREEN, 'why': GREY, 'fill': ORANGE, 'info': GREY, 'dev': BLUE}[kind], bold=True)
    for r, row in enumerate(rows, start + 1):
        for i, v in enumerate(row, 1):
            put(ws, r, i, v, fill=ORANGE if (cols[i - 1][1] == 'fill' and v == FILL_IN) else None)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=start + 1, column=1)
    return ws


def read(work, name):
    p = os.path.join(work, 'analysis', name)
    if not os.path.exists(p) or os.path.getsize(p) < 2:
        return pd.DataFrame()
    try:
        return pd.read_csv(p, keep_default_na=False, dtype=str)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def num(x, d=0):
    try:
        return float(str(x).replace(',', ''))
    except ValueError:
        return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    W = a.work
    cfg = json.load(open(os.path.join(W, 'config.json'), encoding='utf-8'))
    dec = json.load(open(os.path.join(W, 'decisions.json'), encoding='utf-8')) if os.path.exists(os.path.join(W, 'decisions.json')) else {}
    summ = json.load(open(os.path.join(W, 'analysis', 'summary.json'), encoding='utf-8'))
    dom = cfg['domain'].replace('https://', '').replace('http://', '').strip('/')
    full = lambda p: p if str(p).startswith('http') else f'https://{dom}{p}'
    P, MV, RD, NAV, NO = (read(W, f) for f in ('all_pages.csv', 'moves.csv', 'redirects.csv', 'nav_pages.csv', 'no_owner.csv'))
    gsc_meta = summ.get('gsc_meta') or {}
    prune_used = os.path.exists(os.path.join(W, 'prune.csv'))
    T = {}

    # ---- Check page type: a type guessed from the URL wording (content rules) that no prune workbook or reviewer settled
    guess = P[P.why.str.startswith('Rule 7') | P.why.str.startswith('No rule matched') | P.why.str.startswith('Content rule')] if len(P) else P
    T[CPT] = [[r.path, r.type, FILL_IN, r.why] for r in guess.itertuples() if r.type not in ('Pagination', 'Query-string URL')] if len(P) else []

    # ---- Moves and the dev redirect tab
    T[MOVES] = [[full(r.old), full(r.new) if r.new else FILL_IN, r.why] for r in MV.itertuples()] if len(MV) else []
    T[DEV] = [[full(r.old), full(r.new), 0, 301] for r in MV.itertuples() if r.new] if len(MV) else []
    move_to = {r.old: r.new for r in MV.itertuples() if r.new} if len(MV) else {}
    planned = {r.source: r.target for r in RD.itertuples()
               if r.kind == 'Planned' and r.target and not any(c in r.source for c in '*^$')} if len(RD) else {}

    def final(t):
        for _ in range(6):
            nt = planned.get(t) or move_to.get(t)
            if not nt or nt == t:
                break
            t = nt
        return t

    # ---- Fix links: one row per page that has the link
    fix = []
    if len(RD):
        for r in RD.itertuples():
            if r.kind not in ('Existing redirect still linked', 'Broken link (4xx)', 'Moved page still linked') or not r.linkers:
                continue
            tgt = final(r.target) if r.target else ''
            if r.kind == 'Broken link (4xx)':
                why = 'The old URL returns an error (404). Link to a live page or remove the link.'
            elif r.kind == 'Moved page still linked':
                why = 'The page is being moved (Moves tab). Link straight to the new URL.'
            else:
                why = 'The old URL redirects. Link straight to the page it lands on.'
            for lp in str(r.linkers).split(';'):
                fix.append([lp if lp in ('Main menu', 'Footer') else lp, r.source, tgt if tgt else FILL_IN, 'Keep the current anchor text',
                            why + (' Linked from every page.' if lp in ('Main menu', 'Footer') else '')])
    T[FIX] = fix

    # ---- Menu cleanup: recommend removing every menu item that is not the homepage, a hub or a core company page
    keep_types = {'Home', 'Service hub', 'Concern hub', 'Blog hub', 'Location hub'}
    core_words = {'contact', 'about', 'book', 'booking', 'gallery'}
    menu, kept = [], []
    if len(NAV):
        gone = set(P[P.final_action.isin(['Remove then Redirect', 'Merge then Redirect'])].path) if len(P) and 'final_action' in P else set()
        for r in NAV.itertuples():
            essential = r.type in keep_types or bool(set(re.findall(r'[a-z0-9]+', r.page.lower())) & core_words)
            if essential:
                kept.append(r.page)
            elif r.page not in gone:
                why = {'Query-string URL': 'Tracking URL, not a real page.', 'Pagination': 'Listing page 2+, not a real page.'}.get(
                    r.type, f'{r.type} page in the main menu. Hubs and core pages stay; the hubs link to this page.')
                menu.append([r.page, r.type, FILL_IN, why])
    T[MENU] = menu

    # ---- Internal linking opportunities: one link-from page per row
    link, seen_q = [], set()
    if len(NO):
        for r in NO.itertuples():
            frm = [x.split('|') for x in r.from_pages.split(';') if x]
            first = r.query not in seen_q
            seen_q.add(r.query)
            for k, v in frm:
                to = r.owner or FILL_IN
                if first:
                    why = (f"Search '{r.query}': {r.impressions} impressions, {r.pages} pages show for it across {r.treatments} treatments. "
                           + (f'The linked page already gets the most ({r.owner_impr}).' if r.owner else
                              'No page owns this topic, so a new hub page is needed.'))
                    first = False
                else:
                    why = f"Search '{r.query}' (see above)."
                link.append([k, to, r.anchor, FILL_IN, why])
    T[LINK] = link

    # extra rows Claude added for issues this script has no wording for
    extra = dec.get('extra_recommendations', [])

    present = [t for t in (CPT, MOVES, FIX, MENU, LINK) if T[t]]
    wb = Workbook()
    ws = wb.active
    ws.title = REC
    ws.sheet_properties.tabColor = TAB_ORANGE
    head = ['Issue', 'Priority', 'Fix', 'Number of Pages Affected', 'Tab(s) for SEO to Review', 'Tab(s) to hand off', 'Handoff to',
            'Order (do in this order)']
    for i, h in enumerate(head, 1):
        put(ws, 1, i, h, fill=GREY, bold=True)
    ws.freeze_panes = 'A2'
    counts = {CPT: len(T[CPT]), MOVES: len(T[MOVES]), FIX: len({x[0] for x in T[FIX]}), MENU: len(T[MENU]), LINK: len({x[0] for x in T[LINK]})}
    r = 2
    for k in present:
        issue, pri, fx, review, hand, who, order = RECS[k]
        for i, v in enumerate([issue, pri, fx, counts[k], review, hand, who, order], 1):
            put(ws, r, i, v)
        r += 1
    for x in extra:
        for i, v in enumerate([x['issue'], x['priority'], x['fix'], x.get('pages', ''), x.get('review', ''), x.get('hand_off', ''),
                               x.get('handoff_to', ''), 'SEO to set: ' + str(x.get('order', ''))], 1):
            put(ws, r, i, v, fill=ORANGE if i == 8 else None)
        r += 1
    for i, w in enumerate([300, 80, 340, 110, 260, 260, 200, 200], 1):
        ws.column_dimensions[get_column_letter(i)].width = w / 7  # house widths are in pixels; Excel units are ~7 px

    prune_line = ('' if prune_used else
                  ' No prune workbook was provided, so junk archive folders, blog posts to remove, duplicate and merge pages and their redirects '
                  'are not covered here. Run the Content Prune & Merge audit for those.')
    G = lambda t: T[t]
    if G(CPT):
        sheet(wb, CPT, TAB_GREY,
              'SEO ONLY, do not send to the implementer. Nothing on the site says what kind of page each of these is, so the page type is a guess '
              'from the URL wording. Check each page and type the correct page type in column C (leave it empty if the guess is right). '
              + UPDATE_NOTE + ' A changed page type can change the Moves, Menu and Searches tabs. '
              + ('If a prune workbook was provided, its page types were used and these pages are not on this tab. ' if prune_used else '')
              + 'Delete this tab before handoff.',
              [('Page (SEO: QA this URL)', 'info'), ('Page type we guessed', 'info'), ('Correct page type (SEO fill in)', 'fill'),
               ('Why we guessed', 'info')], G(CPT), [50, 23, 28, 30])
    if G(MOVES):
        sheet(wb, MOVES, TAB_GREEN,
              "SEO QA REVIEW: check every row, edit any cell that is wrong, and fill every cell marked 'SEO fill in' before sending. "
              f"The redirects for these pages are in '{DEV}' (the only copy; edit it there). Send only after any prune removals and merges are live: "
              'pages the prune workbook removes or merges are not moved. Delete this row before handoff.',
              [('Page to move (old URL)', 'impl'), ('Move it to (new URL)', 'impl'), (WHY, 'why')], G(MOVES), [60, 60, 60])
    if G(DEV):
        sheet(wb, DEV, TAB_BLUE, None, [('Source URL', 'dev'), ('Target URL', 'dev'), ('Regex (0 = no, 1 = yes)', 'dev'), ('HTTP Code', 'dev')],
              G(DEV), [60, 50, 19, 11])
    if G(FIX):
        n_links = len(G(FIX))
        sheet(wb, FIX, TAB_GREEN,
              'SEO QA REVIEW: these are pages that link to a page that no longer exists or that redirects to another page. Check every row, edit any '
              "cell that is wrong, and fill every cell marked 'SEO fill in' before sending. Send only after the Moves and the redirects are live, so "
              f'each link is changed once. {n_links} links in total. Delete this row before handoff.',
              [('Page that has the link (edit this page)', 'impl'), ('Old URL it links to now (this page no longer exists or redirects)', 'impl'),
               ('New URL to link to instead', 'impl'), ('Anchor text to use', 'impl'), (WHY, 'why')], G(FIX), [45, 45, 40, 28, 50])
    if G(MENU):
        ws2 = sheet(wb, MENU, TAB_GREEN,
                    'SEO QA REVIEW: Claude recommends removing every item below from the main menu and keeping only the homepage, the hub pages and the '
                    'core company pages' + (f" ({', '.join(kept)})" if kept else '') + '. These are recommendations, not decisions. For every row, '
                    'type Keep or Remove in the orange column. Before sending, check each hub links to the pages that leave the menu so none becomes '
                    'orphaned. Send the implementer only the rows marked Remove. Delete this row before handoff.',
                    [('Menu item Claude recommends removing', 'impl'), ('Page type', 'info'),
                     ('Keep or remove from menu (SEO fill in: type Keep or Remove)', 'fill'), (WHY, 'why')], G(MENU), [72, 24, 32, 55])
        dv = DataValidation(type='list', formula1='"Keep,Remove,SEO fill in"', allow_blank=True, showErrorMessage=False)
        ws2.add_data_validation(dv)
        dv.add(f'C3:C{len(G(MENU)) + 2}')
    if G(LINK):
        sheet(wb, LINK, TAB_GREEN,
              "SEO QA REVIEW: these are new internal links to add. For every row, open the 'Link from' page and check whether the anchor text we want "
              "to use already appears on the page. If it does, write 'none' in the orange column. If it does not, write the sentence to add to the page "
              "in the orange column so the anchor text exists. Also fill every other cell marked 'SEO fill in': where 'Link to' is 'SEO fill in', no page "
              'owns that topic, so name the new hub page URL and write it in every row for that topic. Delete this row before handoff.',
              [('Page to add the link on (Link from)', 'impl'), ('Page to link to (Link to)', 'impl'), ('Anchor text to use', 'impl'),
               ("Add text to page to create anchor text opportunity (SEO fill in; write 'none' if the anchor text is already on the link from page)", 'fill'),
               (WHY, 'why')], G(LINK), [45, 45, 24, 40, 60])

    # ---- README
    ws = wb.create_sheet(README)
    ws.sheet_properties.tabColor = TAB_GREY
    put(ws, 1, 1, 'README - SEO ONLY. This tab tells you what to QA before sending. Delete this tab before handoff.', fill=YELLOW, bold=True)
    ws.merge_cells('A1:D1')
    row = [2]

    def line(cells, fill=None, bold=False, merge_from=None):
        for i, v in enumerate(cells, 1):
            if v is not None:
                put(ws, row[0], i, v, fill=fill, bold=bold)
        if merge_from:
            ws.merge_cells(start_row=row[0], start_column=merge_from, end_row=row[0], end_column=4)
        row[0] += 1
    line(['HOW TO USE'], fill=GREY, bold=True)
    for i, s in enumerate(HOW_TO, 1):
        if i == 1 and not G(CPT):
            continue
        if i == 4 and not G(CPT):
            continue
        line([f'Step {i}', s], merge_from=2)
    line(['WHAT CLAUDE CHECKED (tab)', 'Rule Claude applied', 'What you need to QA', 'Handoff to'], fill=GREY, bold=True)
    for t in (CPT, MOVES, FIX, MENU, LINK):
        if G(t):
            rule, qa, who = README_RULES[t]
            line([f'{MOVES}, and {DEV}' if t == MOVES else t, rule, qa, who])
    for x in extra:
        line([x['issue'], x.get('rule', ''), 'Added by Claude for an issue with no standard wording. Check it carefully.', x.get('handoff_to', '')])
    fm = dec.get('folder_types', {})
    oc = cfg.get('other_cities', [])
    ga4 = 'SEO fill in'
    line(['SETTINGS (change per site)', 'Setting', 'Value used on this audit', 'Notes'], fill=GREY, bold=True)
    line(['Date range', 'Search data window used', (f"{gsc_meta['window_start']} to {gsc_meta['window_end']}" if gsc_meta.get('window_start') else FILL_IN),
          'Dates as stated by the person who supplied the sheet.'])
    line(['Brand terms excluded', 'Queries left out of the search analysis', ', '.join(cfg.get('brand_terms', [])) or 'none',
          'Excluded because the brand name appears in most queries.' if cfg.get('brand_terms') else ''])
    line(['Other cities', 'Cities treated as relevant', ', '.join(oc) if oc else 'none', ''])
    line(['Folder to page type map', 'Confirmed by a person before pages were typed',
          '; '.join(f'/{k.strip("/")}/ = {v}' for k, v in fm.items()) or 'none', 'Used for pages inside a folder.'])
    line(['Searches with no owner: impressions', 'Minimum impressions in the window', str(NOOWNER_MIN), 'Smaller searches are noise.'])
    line(['GA4', 'Whether GA4 was merged into the search data', 'Merged' if str(gsc_meta.get('ga4_rows', '0')) not in ('', '0') else 'Not used',
          'No tab on this workbook depends on GA4.'])
    line(['DATA USED', 'Source', 'What was taken', 'Notes'], fill=GREY, bold=True)
    line(['Crawl', f"{summ.get('crawler') or cfg.get('crawler', '')} export, {cfg.get('crawl_date', '')}".strip(' ,'),
          'URL, status code, title, H1, links, redirects and crawl depth for each page', ''])
    line(['Search Console', 'Google Sheet' if gsc_meta else 'Not provided', 'Page, query, clicks and impressions for the date range above'
          if gsc_meta else 'Search columns are blank and the Searches tab is empty.',
          'Page clicks and impressions are the sum of the listed queries, so they can be lower than the Performance report.' if gsc_meta else ''])
    line(['Prune workbook', 'Used' if prune_used else 'Not provided for this audit',
          'Page types and the planned removals and merges' if prune_used else '',
          'Its pages are not repeated here.' if prune_used else prune_line.strip()])
    if not G(MOVES):
        line(['NOTHING TO DO', 'Blog posts and service pages outside their folder', '0 pages', ''])
    line(['NOT CHECKED (guess, confirm)', 'This sheet does not check:',
          'Page copy quality, anchor text of existing links, backlinks, page speed, structured data and images.',
          'Ask for a separate audit if you need these.'])
    for n in summ.get('notes', []):
        line(['NOTE', n, '', ''])
    for i, w in enumerate([30, 45, 52, 24], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'

    wb.save(a.out)
    print(f'Wrote {a.out}')
    for t in (CPT, MOVES, DEV, FIX, MENU, LINK):
        if G(t):
            print(f'  {t}: {len(G(t))} rows')
    print(f'  Recommendations: {len(present) + len(extra)} rows')


if __name__ == '__main__':
    sys.exit(main())
