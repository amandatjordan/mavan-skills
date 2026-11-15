"""A small made-up site and its audit workbooks for the migration-sheet tests. No client data.

The site (https://example-medspa.com) is set up so each rule in the skill is hit once:
  /botox-tips/   prune merges into /botox/        /botox/  the IA audit moves to /services/botox/   -> chain fixed
  /thin-page/    IA moves it, prune removes it     -> IA move dropped, prune decision stands
  /old-botox/    existing site redirect to /botox/ -> repointed to /services/botox/
  /junk/*        wildcard rule covering /junk/a/ and /junk/b/ (counted once)
  /gone-page/    404 with backlinks, nobody decided it
  /gsc-only/     in Search Console only, nobody decided it
  brochure.pdf, menu.pdf  media with backlinks; logo.png has none and is ignored
"""
import csv
from pathlib import Path

import openpyxl

SITE = 'https://example-medspa.com'

PAGES = [  # path, status, indexable, title, h1, redirect
    ('/', 200, 'Indexable', 'Home', 'Welcome', ''),
    ('/services/', 200, 'Indexable', 'Services', 'Services', ''),
    ('/botox/', 200, 'Indexable', 'Botox', 'Botox', ''),
    ('/botox-tips/', 200, 'Indexable', 'Botox tips', 'Botox tips', ''),
    ('/fillers/', 200, 'Indexable', 'Fillers', 'Fillers', ''),
    ('/about/', 200, 'Indexable', 'About', 'About us', ''),
    ('/contact/', 200, 'Indexable', 'Contact', 'Contact', ''),
    ('/blog/', 200, 'Indexable', 'Blog', 'Blog', ''),
    ('/blog/old-post/', 200, 'Indexable', 'Old post', 'Old post', ''),
    ('/blog/new-post/', 200, 'Indexable', 'New post', 'New post', ''),
    ('/thin-page/', 200, 'Indexable', 'Thin', 'Thin', ''),
    ('/junk/a/', 200, 'Indexable', 'Junk a', 'Junk a', ''),
    ('/junk/b/', 200, 'Indexable', 'Junk b', 'Junk b', ''),
    ('/old-botox/', 301, '', '', '', '/botox/'),
    ('/gone-page/', 404, '', '', '', ''),
    ('/wp-content/uploads/logo.png', 200, 'Indexable', '', '', ''),
]
LINKS = [  # from, to, location, css path
    ('/', '/botox/', 'Navigation', 'header>nav>ul>li>a'),
    ('/', '/about/', 'Navigation', 'header>nav>ul>li>a'),
    ('/', '/fillers/', 'Content', 'main>section>p>a'),
    ('/botox-tips/', '/botox/', 'Content', 'main>article>p>a'),
    ('/botox-tips/', '/fillers/', 'Content', 'main>article>p>a'),
    ('/botox/', '/fillers/', 'Content', 'main>article>p>a'),
    ('/botox/', '/contact/', 'Content', 'main>article>ul>li>a'),
    ('/about/', '/botox-tips/', 'Content', 'main>article>p>a'),
    ('/fillers/', '/botox/', 'Content', 'main>article>p>a'),
    ('/blog/new-post/', '/botox/', 'Content', 'main>article>p>a'),
    ('/', '/contact/', 'Footer', 'footer>ul>li>a'),
]
BACKLINKS = [  # target path, several rows for the count
    ('/botox-tips/', 3), ('/gone-page/', 2), ('/wp-content/uploads/brochure.pdf', 4), ('/wp-content/uploads/menu.pdf', 1), ('/botox/', 5),
]
GSC = [('/gsc-only/', 120), ('/botox/', 800), ('/fillers/', 300)]


def write_csv(path, header, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def sheet(wb, name, headers, rows, banner='SEO QA REVIEW: banner row'):
    ws = wb.create_sheet(name)
    if banner:
        ws.cell(1, 1, banner)
        start = 2
    else:
        start = 1
    for i, h in enumerate(headers, 1):
        ws.cell(start, i, h)
    for r, row in enumerate(rows, start + 1):
        for i, v in enumerate(row, 1):
            ws.cell(r, i, v)
    return ws


def make_inputs(d, *, disagree='', gap_next='Create new page', drop=(), extra_prune=None):
    """Write every input file into folder d and return a dict of paths. `drop` names tabs to leave out."""
    d = Path(d)
    p = {}
    write_csv(d / 'urls.csv', ['URL', 'HTTP Status Code', 'Indexable Status', 'Title', 'H1', 'No. Content Words', 'Redirect URL'],
              [(SITE + u, s, i, t, h, 300, SITE + r if r else '') for u, s, i, t, h, r in PAGES])
    write_csv(d / 'links.csv', ['Linking URL', 'Target URL', 'Anchor Text', 'Location', 'CSS Path'],
              [(SITE + a, SITE + b, 'x', loc, css) for a, b, loc, css in LINKS])
    write_csv(d / 'redirects.csv', ['URL', 'Status Code', 'Redirect URL'], [(SITE + '/old-botox/', 301, SITE + '/botox/')])
    write_csv(d / 'backlinks.csv', ['Referring page URL', 'Target URL'],
              [(f'https://ref{i}.com/p', SITE + t) for t, n in BACKLINKS for i in range(n)])
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    sheet(wb, 'Claude Use This', ['Page', 'Query', 'Clicks', 'Impressions'], [(SITE + u, 'q', 1, n) for u, n in GSC], banner=None)
    wb.save(d / 'gsc.xlsx')

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    sheet(wb, 'Kept pages', ['Page (SEO: QA this URL)', 'Page type', 'Clicks', 'Impressions', 'Why', 'Disagree? Type the change you want (SEO fill in)'],
          [(SITE + '/about/', 'Company / Info', 5, 50, 'ok', disagree), (SITE + '/fillers/', 'Service', 9, 90, 'ok', '')])
    sheet(wb, 'Merge pages', ['Page that will be removed after merge', 'Page we are keeping', 'Unique content to copy over', 'Why'],
          [(SITE + '/botox-tips/', SITE + '/botox/', 'Two tips about aftercare', 'dup')])
    sheet(wb, 'Remove pages', ['Page to remove', 'Redirect to', 'Why'],
          [(SITE + '/blog/old-post/', SITE + '/blog/', 'old'), (SITE + '/thin-page/', SITE + '/services/', 'thin')])
    sheet(wb, 'Junk folders', ['Folder to redirect', 'Redirect to', 'Why'], [(SITE + '/junk/*', SITE + '/', 'junk')])
    sheet(wb, 'Update pages', ['Page to update', 'New title (SEO fill in)', 'New H1 (SEO fill in)', 'New first sentence (SEO fill in)', 'Why'],
          [(SITE + '/fillers/', 'Dermal Fillers Denver', 'Dermal Fillers', 'SEO fill in', 'why')])
    for name, rows in (extra_prune or {}).items():
        sheet(wb, name, ['Page', 'Question for the client (SEO fill in)', 'Why'], rows)
    for t in drop:
        if t in wb.sheetnames:
            wb.remove(wb[t])
    wb.save(d / 'prune.xlsx')
    p['prune'] = d / 'prune.xlsx'

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    sheet(wb, 'Check page type', ['Page (SEO: QA this URL)', 'Page type we guessed', 'Correct page type (SEO fill in)', 'Why'],
          [(SITE + '/services/', 'Service hub', '', 'g')])
    sheet(wb, 'Moves', ['Page to move (old URL)', 'Move it to (new URL)', 'Why'],
          [(SITE + '/botox/', SITE + '/services/botox/', 'folder'), (SITE + '/thin-page/', SITE + '/services/thin/', 'folder')])
    sheet(wb, 'README', ['Setting', '', 'Value'], [('Folder to page type map', '', '/services/ = Service')])
    wb.save(d / 'ia.xlsx')
    p['ia'] = d / 'ia.xlsx'

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet('Recommendations')
    ws.cell(1, 1, 'Page')
    ws.cell(1, 6, 'Search Volume')
    for i, h in enumerate(['Service Page Recommended', 'Current URL', 'Next Steps', 'Existing Brand / Sub-Service Page(s)', 'Why Recommended',
                           'Relevant Keywords', 'Total National Search Volume'], 1):
        ws.cell(2, i, h)
    for i, v in enumerate(['Lip Filler', '', gap_next, '', 'gap', 'lip filler', 900], 1):
        ws.cell(3, i, v)
    for i, v in enumerate(['Chemical Peel', '', 'Ignore', '', 'gap', 'peel', 100], 1):
        ws.cell(4, i, v)
    wb.save(d / 'gap.xlsx')
    p['gap'] = d / 'gap.xlsx'
    p.update({k: d / f for k, f in (('urls', 'urls.csv'), ('links', 'links.csv'), ('redirects', 'redirects.csv'),
                                     ('backlinks', 'backlinks.csv'), ('gsc', 'gsc.xlsx'))})
    return p
