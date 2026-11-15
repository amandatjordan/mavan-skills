#!/usr/bin/env python3
"""Write the migration workbook (and, after the QA check, the developer redirect CSV) from work/sheet.json.

Usage:
  python make_xlsx.py --work work --out migration-sheet.xlsx [--client "Name"]
The template run writes the workbook for the SEO to finish. The QA run writes the final workbook and, next to it, the developer redirect CSV
(the only copy of the developer list: the workbook has no dev tab). All wording is fixed here; Claude writes none of it.
"""
import argparse
import csv
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

YELLOW, GREY, GREEN, BLUE, ORANGE, REVIEW = 'FFF2C6', 'D8D8D8', 'D1EAD1', 'CCE0FF', 'FCE5CD', 'FFF0D9'
TAB_GREY, TAB_GREEN, TAB_BLUE, TAB_ORANGE = '7F7F7F', '339E4C', '3366D8', 'F28C19'
FILL_IN = 'SEO fill in'
FONT = 'Arial'
ALLP, MENU, MERGE, REDIR, MEDIA, NEWP, DEV, SUMMARY, README = (
    'All pages', 'Final menu and nav', 'Pages to merge', 'Pages to redirect', 'Media with backlinks', 'New pages',
    'Redirects - Handoff to Dev', 'Summary', 'README')

BANNERS = {
    ALLP: 'SEO: REVIEW AND UPDATE the light orange columns (Page type, Title at migration, H1 at migration). They start from the crawl, with Update pages\' '
          'new title and H1 where the prune filled them in; this is the title and H1 the new site will launch with, so change any that are wrong or will '
          'change. Fill in the same for new pages. This tab lists every page that will exist on the new site (stays, moved, new). Merged pages are not '
          'listed because they redirect to the page they merge into. Every internal link on a page that stays is kept. Delete this row before handoff.',
    MENU: 'The SEO MUST set the final navigation here, always with parent and child levels. Parent label, Parent URL (leave blank for a label-only '
          'dropdown), Child label, Child URL, order. Every URL must be a page on the All pages tab. The QA check fails while this tab is empty.',
    MERGE: 'Pages that go away and are folded into another page. Column C is the unique content to copy over to the surviving page. The redirect for '
           'each is on the Pages to redirect tab and in the developer list. Delete this row before handoff.',
    REDIR: "Every old URL that does not stay, with the one-hop target. Fill every orange cell: a target for URLs nobody decided (type Gone to remove "
           "with no redirect; type 410 in the code column for 410, otherwise it is 404), and a written reason for every Gone row. Merge redirects are "
           "here too because they all go live at launch. Delete this row before handoff.",
    MEDIA: 'Images, PDFs and other files with backlinks. Nobody can know whether the new site keeps a file at the same URL, so decide each one: '
           'Keep at the same URL, or Redirect (and fill in the new URL). Files without backlinks are ignored.',
    NEWP: 'Pages to create (Service Gap rows set to Create new page). Service Gap names the page but not its URL, so fill in the URL. Up to 3 existing '
          'pages that should link TO the new page are suggested from the Service Gap data, shown at their final URLs: change or add pages, and fill in the '
          'anchor text each one uses to link to the new page. The QA check fails while an orange cell is left.',
}
HEADS = {
    ALLP: [('Final URL', 'impl'), ('Old URL (when it moves)', 'info'), ('Origin', 'info'), ('Page type (SEO: review and update)', 'review'),
           ('Title at migration (SEO: review and update)', 'review'), ('H1 at migration (SEO: review and update)', 'review'), ('Notes', 'info')],
    MENU: [('Parent label (SEO fill in)', 'fill'), ('Parent URL', 'fill'), ('Child label', 'fill'), ('Child URL', 'fill'), ('Order', 'fill')],
    MERGE: [('Page that goes away', 'impl'), ('Page it merges into (final URL)', 'impl'), ('Unique content to copy over', 'impl')],
    REDIR: [('Old URL', 'impl'), ('Redirects to (SEO fill in where blank; type Gone to remove)', 'fill'), ('HTTP code', 'impl'),
            ('Reason for Gone (SEO fill in)', 'fill'), ('Decided by', 'info')],
    MEDIA: [('Media URL', 'impl'), ('Backlinks', 'info'), ('SEO decision', 'fill'), ('New URL (when redirecting)', 'fill')],
    NEWP: [('Page to create', 'impl'), ('URL (SEO fill in)', 'fill'), ('Keywords', 'info'), ('Page that links to it 1 (suggested)', 'opt'),
           ('Anchor text 1', 'opt'), ('Page that links to it 2 (suggested)', 'opt'), ('Anchor text 2', 'opt'),
           ('Page that links to it 3 (suggested)', 'opt'), ('Anchor text 3', 'opt')],
    DEV: [('Source URL', 'dev'), ('Target URL', 'dev'), ('Regex (0 = no, 1 = yes)', 'dev'), ('HTTP Code', 'dev')],
}
WIDTHS = {ALLP: [44, 32, 12, 30, 46, 40, 30], MENU: [28, 40, 28, 40, 10], MERGE: [44, 44, 44],
          REDIR: [48, 48, 11, 36, 44], MEDIA: [60, 10, 26, 48], NEWP: [30, 36, 30, 34, 26, 34, 26, 34, 26], DEV: [60, 50, 19, 11]}
KIND = {'impl': GREEN, 'info': GREY, 'fill': ORANGE, 'opt': ORANGE, 'review': REVIEW, 'dev': BLUE}


def put(ws, r, c, v, fill=None, bold=False, wrap=True):
    x = ws.cell(r, c, v)
    x.font = Font(name=FONT, bold=bold, size=10)
    x.alignment = Alignment(wrap_text=wrap, vertical='top')
    if fill:
        x.fill = PatternFill('solid', fgColor=fill)
    return x


def tab(wb, name, color, rows, banner=True):
    ws = wb.create_sheet(name)
    ws.sheet_properties.tabColor = color
    heads, start = HEADS[name], 1
    if banner:
        put(ws, 1, 1, BANNERS[name], fill=YELLOW, bold=True)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(heads))
        ws.row_dimensions[1].height = 62
        start = 2
    for i, (h, k) in enumerate(heads, 1):
        put(ws, start, i, h, fill=KIND[k], bold=True)
    for r, row in enumerate(rows, start + 1):
        for i, v in enumerate(row, 1):
            fill_col = heads[i - 1][1] == 'fill'
            put(ws, r, i, v, fill=ORANGE if (fill_col and v in ('', FILL_IN)) or v == FILL_IN else REVIEW if heads[i - 1][1] == 'review' else None)
    for i, w in enumerate(WIDTHS[name], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=start + 1, column=1)
    return ws, start


def block(ws, r, title, heads, rows, width=5):
    put(ws, r, 1, title, fill=YELLOW, bold=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=width)
    for i, h in enumerate(heads, 1):
        put(ws, r + 1, i, h, fill=GREY, bold=True)
    for j, row in enumerate(rows, r + 2):
        for i, v in enumerate(row, 1):
            put(ws, j, i, v)
    return r + len(rows) + 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work')
    ap.add_argument('--out', default='migration-sheet.xlsx')
    ap.add_argument('--client', default='')
    a = ap.parse_args()
    S = json.load(open(os.path.join(a.work, 'sheet.json'), encoding='utf-8'))
    pass2, T, c = S['pass'] == 2, S['tabs'], S['counts']
    wb = Workbook()
    ws = wb.active
    ws.title = SUMMARY
    ws.sheet_properties.tabColor = TAB_ORANGE
    put(ws, 1, 1, f"Migration sheet{' for ' + a.client if a.client else ''}: {S['domain']} ({'QA check' if pass2 else 'template'}). "
        + ('Final: every check passed.' if pass2 else 'Fill in every orange cell on the other tabs, then send the finished sheet back for the QA check.'),
        fill=YELLOW, bold=True)
    ws.merge_cells('A1:E1')
    r = block(ws, 3, 'What the SEO does with this sheet', ['Step', 'Where'], [
        ['1. Read every discrepancy below and the check results. To change an outcome, edit the audit workbook and re-run.', 'This tab'],
        ['2. Review and update the page type, title and H1 each page will launch with (light orange columns).', 'All pages'],
        ['3. Fill in every orange cell: the navigation, media decisions, new page URLs and anchor text, and redirect targets or Gone reasons.',
         'Final menu and nav, Media with backlinks, New pages, Pages to redirect']], 2)
    r = block(ws, r, 'What happens to every old URL', ['Decision', 'URLs'], [
        ['Stay (same URL)', c['keep'] - c['moved']], ['Stay at a new URL (IA audit move)', c['moved']], ['Merge into another page', c['merge']],
        ['Redirect (one hop)', c['redirect']], ['Gone (404 or 410, no redirect)', c['gone']],
        ['Inside a wildcard rule (counted once per rule)', f"{c['covered']} URLs, {c['wildcard']} rule(s)"],
        ['Media files with backlinks (SEO decides each)', c['media']]])
    r = block(ws, r, 'Script checks (all must be PASS before client approval)', ['Check', 'Result', 'Detail'],
              [[x['check'], x['status'], x['detail']] for x in S['checks']], 3)
    r = block(ws, r, f"Discrepancies the sheet found and fixed ({len(S['discrepancies'])}). Review each one. To change an outcome, edit the audit workbook and re-run.",
              ['What', 'URL', 'What the audits said', 'What this sheet did', 'Where each came from'],
              [[d['kind'], d['old'], d['said'], d['did'], d['source']] for d in S['discrepancies']] or [['None', '', '', '', '']])
    cut = [[t, v['pages'], v['cutoff'] if v['cutoff'] is not None else 'fewer than 4 pages, not used'] for t, v in S['cutoffs'].items()]
    r = block(ws, r, 'Internal link cutoff used at staging: a page with fewer pages linking to it than this is in the bottom quartile of its page type',
              ['Page type', 'Pages that stay', 'Cutoff (pages linking in)'], cut, 3)
    for i, w in enumerate([46, 36, 50, 40, 44], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'

    tab(wb, ALLP, TAB_GREEN, T[ALLP])
    ws2, st = tab(wb, MENU, TAB_ORANGE, T[MENU])
    tab(wb, MERGE, TAB_GREEN, T[MERGE])
    tab(wb, REDIR, TAB_GREEN, T[REDIR])
    ws3, st = tab(wb, MEDIA, TAB_ORANGE, T[MEDIA])
    dv = DataValidation(type='list', formula1='"Keep at the same URL,Redirect,SEO fill in"', allow_blank=True, showErrorMessage=False)
    ws3.add_data_validation(dv)
    dv.add(f'C{st + 1}:C{st + 1 + max(len(T[MEDIA]), 1)}')
    tab(wb, NEWP, TAB_ORANGE, T[NEWP])
    ws = wb.create_sheet(README)
    ws.sheet_properties.tabColor = TAB_GREY
    put(ws, 1, 1, 'README - SEO ONLY. Delete this tab before handoff.', fill=YELLOW, bold=True)
    ws.merge_cells('A1:C1')
    files = sorted({x['file'] for x in S['read']})
    lines = [
        ('How to use', 'This is the template for the SEO to finish. Review and update the light orange columns on All pages (page type, title and H1 at launch). Fill every orange cell (the Final menu and nav tab, Media with backlinks, New pages, and the Pages to '
                       'redirect cells marked SEO fill in). Send the finished sheet back for the QA check, which re-runs every check and writes the final workbook '
                       'and the developer redirect CSV. A change to a keep, merge, remove or move decision is made in the audit workbook, never here.'),
        ('Audit workbooks read', ', '.join(files) or 'none'),
        ('Tabs read', '; '.join(f"{x['file']} / {x['tab']} ({x['rows']} rows)" for x in S['read'])),
        ('Who decides what', 'Content Prune decides stay, merge or remove. The IA audit decides the URL of a page that stays. Where the two disagree the '
                             'Content Prune decision stands and the IA move is dropped; every such case is on the Summary tab.'),
        ('Internal link cutoff', 'Bottom quartile of pages linking in, per page type (needs 4 pages of a type). Used in the staging check.'),
        ('Not checked', 'The live and staging sites are never fetched. Crawl exports of staging or the live site are checked later by the migration-check skill. '
                        'Media without backlinks is ignored. Service Gap rows other than Create new page are not read.'),
    ]
    for i, (k, v) in enumerate(lines, 3):
        put(ws, i, 1, k, bold=True)
        put(ws, i, 2, v)
    ws.column_dimensions['A'].width, ws.column_dimensions['B'].width = 28, 120
    wb.save(a.out)
    msg = f'Wrote {a.out}'
    if pass2:
        csv_path = os.path.splitext(a.out)[0] + '-redirects.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow([h for h, _ in HEADS[DEV]])
            w.writerows(T[DEV])
        msg += f' and {csv_path} ({len(T[DEV])} redirect rows)'
    print(msg)


if __name__ == '__main__':
    main()
