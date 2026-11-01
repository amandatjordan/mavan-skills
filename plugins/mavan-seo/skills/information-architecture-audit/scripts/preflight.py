#!/usr/bin/env python3
"""Preflight check for the IA audit: are all the inputs here, readable and the right kind of export?

Run it first, before prep.py. It reads only headers and the first few thousand rows, so it is quick even on a
60MB links export. It prints PASS / WARN / FAIL / INFO lines and writes work/preflight.md.

Usage:
  python preflight.py --domain example.com --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv \
      --template TEMPLATE.xlsx --gsc-sheet GSC.xlsx [--gsc-start 2026-04-01 --gsc-end 2026-09-30] \
      [--prune PRUNE.xlsx] [--client-redirects LIST.csv] [--ga4 yes|no] \
      [--client "Name" --city "City, ST" --brand "term,term"] [--skip redirects,gsc,template] [--out work]

Any argument that is left out is reported as missing. Exit code 1 when anything FAILs, so the audit does not
start on bad inputs. WARN means the audit can run but something will be thinner, and the message says what.
--skip names an input the person has said they do not have (redirects, gsc, template); it is reported as
SKIPPED with what the audit loses, and does not fail.
"""
import argparse
import datetime as dt
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain  # noqa: E402
import gsc_sheet  # noqa: E402

TEMPLATE_SHEETS = ['Read Me', 'Recommendations', 'All Pages', 'Page Type Summary', 'Duplicate Intent',
                   'Path Consistency', 'Link Flow', 'Retarget Links', 'Blog to Service Links', 'Nav Pages', 'Redirects']

URL_COLS = {  # role: (required?, names)
    'url': (True, ('url', 'address')),
    'status': (True, ('http status code', 'status code')),
    'indexable': (False, ('indexable status', 'indexability', 'indexability status')),
    'depth': (False, ('crawl depth',)),
    'title': (False, ('title', 'title 1')),
    'h1': (False, ('h1', 'h1-1')),
    'words': (False, ('no. content words', 'word count', 'no. words')),
    'inlinks': (False, ('no. internal linking urls', 'unique inlinks', 'no. internal links to url', 'inlinks')),
}
URL_WHY = {
    'indexable': 'indexable status will be unknown, so noindex and canonicalised pages cannot be told apart',
    'depth': 'crawl depth columns on All Pages will be blank',
    'title': 'titles will be missing for duplicate and topic checks',
    'h1': 'H1s will be missing for page typing and duplicate checks',
    'words': 'thin-page and article-vs-service typing will be weaker',
    'inlinks': 'link counts will come from the links export only',
}
LINK_COLS = {
    'target': ('target url', 'destination', 'to'),
    'source': ('linking url', 'source', 'from'),
}
LINK_PATH = ('css path', 'link path', 'xpath', 'link path', 'path')
REDIR_COLS = {'source': ('url', 'address', 'source', 'from'),
              'target': ('redirect url', 'redirect destination', 'destination', 'final address', 'to')}

rows = []  # (level, name, message)


def add(level, name, msg):
    rows.append((level, name, msg))


def find(cols, names):
    low = {str(c).lower().strip(): c for c in cols}
    for n in names:
        if n in low:
            return low[n]
    return None


def head(path, n=3000):
    return pd.read_csv(path, encoding='utf-8-sig', dtype=str, nrows=n, keep_default_na=False, low_memory=False)


def file_date(path):
    m = re.search(r'(20\d{2})[-_]?(\d{2})[-_]?(\d{2})', os.path.basename(path))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def check_exists(name, path, skip, why_skip):
    if name in skip:
        add('SKIPPED', name, why_skip)
        return False
    if not path:
        add('FAIL', name, 'not provided. Ask the person for it (see "What you need" in SKILL.md).')
        return False
    if not os.path.isfile(path):
        add('FAIL', name, f'file not found: {path}')
        return False
    return True


def check_urls(a):
    if not check_exists('URL export', a.urls, set(), ''):
        return None
    try:
        d = head(a.urls)
    except Exception as e:  # noqa: BLE001
        add('FAIL', 'URL export', f'could not read it as a CSV: {e}')
        return None
    cols = list(d.columns)
    got = {}
    for role, (req, names) in URL_COLS.items():
        c = find(cols, names)
        got[role] = c
        if not c:
            if req:
                add('FAIL', 'URL export', f'no {role} column (looked for: {", ".join(names)}). Columns found: '
                    f'{", ".join(str(x) for x in cols[:12])}. This is not the crawler\'s full URL export.')
            else:
                add('WARN', 'URL export', f'no {role} column: {URL_WHY[role]}.')
    if not got['url'] or not got['status']:
        return None
    full = pd.read_csv(a.urls, encoding='utf-8-sig', dtype=str, usecols=[got['url'], got['status']] +
                       ([got['indexable']] if got['indexable'] else []), keep_default_na=False, low_memory=False)
    n = len(full)
    st = full[got['status']].str.strip()
    non200 = int((st != '200').sum())
    dom = bare_domain(a.domain)
    on_dom = full[got['url']].str.lower().str.contains(re.escape(dom)).mean() if n else 0
    add('INFO', 'URL export', f'{n} URLs: ' + ', '.join(f'{k} x{v}' for k, v in st.value_counts().head(5).items()))
    if n < 30:
        add('WARN', 'URL export', f'only {n} rows. A full-site audit needs every URL, not a filtered list. If the '
            'person wants to focus on certain pages (e.g. service pages), the audit still needs the whole crawl.')
    if non200 == 0:
        add('WARN', 'URL export', 'every URL is 200: redirects and errors are missing. Export all URLs, not only '
            'indexable HTML, or the redirect and error checks will be empty.')
    if on_dom < 0.9:
        add('FAIL' if on_dom < 0.5 else 'WARN', 'URL export', f'only {on_dom:.0%} of URLs contain {dom}. Wrong domain or '
            'a mixed export?')
    home = full[got['url']].str.lower().str.rstrip('/').str.replace(r'^https?://(www\.)?', '', regex=True).eq(dom).any()
    if not home:
        add('WARN', 'URL export', 'the homepage is not in the export, so it is probably filtered. Ask for the unfiltered export.')
    return n


def check_links(a):
    if not check_exists('Links export', a.links, set(), ''):
        return
    try:
        d = head(a.links, 2000)
    except Exception as e:  # noqa: BLE001
        add('FAIL', 'Links export', f'could not read it as a CSV: {e}')
        return
    cols = list(d.columns)
    t, s = find(cols, LINK_COLS['target']), find(cols, LINK_COLS['source'])
    if not t or not s:
        add('FAIL', 'Links export', 'needs a target and a linking-page column (Sitebulb: Target URL + Linking URL; '
            f'Screaming Frog: Destination + Source). Columns found: {", ".join(str(x) for x in cols[:10])}. '
            'This is probably the URL list, not the all-internal-links export.')
        return
    pc = find(cols, LINK_PATH)
    if not pc:
        add('WARN', 'Links export', 'no CSS path / link path column: menu, footer and body links cannot be told apart, '
            'so Nav/Footer/Body link counts will be unreliable.')
    elif (d[pc].str.strip() == '').mean() > 0.5:
        add('WARN', 'Links export', f'{(d[pc].str.strip() == "").mean():.0%} of link paths are empty in the first rows.')
    size = os.path.getsize(a.links) / 1e6
    add('INFO', 'Links export', f'{size:.0f} MB; columns OK ({t}, {s}' + (f', {pc}' if pc else '') + ')')


def check_redirects(a):
    if not check_exists('Redirects export', a.redirects, set(a.skip), 'no redirects export: redirect chains, loops and '
                        'old URLs are checked from the URL export only, and the Redirects tab will be thinner.'):
        return
    try:
        d = head(a.redirects)
    except Exception as e:  # noqa: BLE001
        add('FAIL', 'Redirects export', f'could not read it as a CSV: {e}')
        return
    s, t = find(d.columns, REDIR_COLS['source']), find(d.columns, REDIR_COLS['target'])
    if not s or not t:
        add('FAIL', 'Redirects export', f'needs a source and a redirect-target column. Columns found: '
            f'{", ".join(str(x) for x in d.columns[:10])}')
        return
    add('INFO', 'Redirects export', f'{len(d)} redirecting URLs')


def check_dates(a):
    ds = {n: file_date(p) for n, p in [('URL export', a.urls), ('Links export', a.links), ('Redirects export', a.redirects)]
          if p}
    ds = {k: v for k, v in ds.items() if v}
    if len(ds) >= 2:
        span = (max(ds.values()) - min(ds.values())).days
        txt = ', '.join(f'{k} {v.isoformat()}' for k, v in ds.items())
        if span > 7:
            add('WARN', 'Crawl dates', f'the exports were made {span} days apart ({txt}). Pages added or removed in '
                'between will not line up. Prefer exports from one crawl; otherwise note it in the Read Me.')
        elif span:
            add('INFO', 'Crawl dates', f'exports are {span} day(s) apart ({txt}); fine if it is the same crawl.')
    elif not ds:
        add('INFO', 'Crawl dates', 'no dates in the file names; ask the person for the crawl date (config crawl_date).')


def check_template(a):
    if not check_exists('Template', a.template, set(a.skip), 'no template: the audit analysis can run but the '
                        'workbook cannot be filled.'):
        return
    try:
        import openpyxl
        names = openpyxl.load_workbook(a.template, read_only=True).sheetnames
    except Exception as e:  # noqa: BLE001
        add('FAIL', 'Template', f'could not open it as .xlsx: {e}')
        return
    missing = [s for s in TEMPLATE_SHEETS if s not in names]
    if missing:
        hint = ''
        if any(n.lower().startswith('sas_') or n.lower() == 'claude use this' for n in names):
            hint = ' This looks like the Search Console data sheet, not the IA template.'
        add('FAIL', 'Template', f'tabs missing: {", ".join(missing)}. Tabs found: {", ".join(names)}.{hint} '
            'Use the IA Audit template (Step 1).')
    else:
        add('PASS', 'Template', 'all 11 tabs present')


def check_gsc(a):
    if not check_exists('Search Console sheet', a.gsc_sheet, set(a.skip), 'no Search Console data: all search columns '
                        'stay blank, duplicate-intent pairs cannot be found from searches, and the Read Me says why.'):
        return
    try:
        tabs = gsc_sheet.read_tabs(a.gsc_sheet)
    except Exception as e:  # noqa: BLE001
        add('FAIL', 'Search Console sheet', f'could not read it: {e}')
        return
    if not tabs:
        add('FAIL', 'Search Console sheet', 'no tab has Page, Query, Clicks and Impressions columns. The sheet must be a '
            'page + query export (not queries only or pages only).')
        return
    named = next((n for n in tabs if n.strip().lower() == gsc_sheet.GSC_TAB.lower()), None)
    use = named or (next(iter(tabs)) if len(tabs) == 1 else None)
    if not use:
        add('FAIL', 'Search Console sheet', 'several tabs have GSC columns and none is named "' + gsc_sheet.GSC_TAB +
            '": ' + '; '.join(f"'{n}' ({len(r)} rows)" for n, r in tabs.items()) + '. Ask the person which one to use.')
        return
    data = tabs[use]
    dom = bare_domain(a.domain)
    pages = {p for p, *_ in data}
    on = sum(1 for p in pages if dom in re.sub(r'^https?://(www\.)?', '', p.lower()).split('/')[0]) / max(len(pages), 1)
    add('INFO', 'Search Console sheet', f"tab '{use}': {len(data)} page+query rows, {len(pages)} pages, "
        f'{int(sum(r[2] for r in data))} clicks, {int(sum(r[3] for r in data))} impressions')
    if on < 0.9:
        add('FAIL' if on < 0.5 else 'WARN', 'Search Console sheet', f'only {on:.0%} of its pages are on {dom}. Wrong client?')
    if len(data) < 100:
        add('WARN', 'Search Console sheet', f'only {len(data)} rows. Duplicate-intent and no-owner checks need a fuller '
            'export (all queries for the window), not a top-20 list.')
    if len(data) in (1000, 5000, 10000, 25000, 50000):
        add('WARN', 'Search Console sheet', f'exactly {len(data)} rows, which looks like an export cut-off. Ask whether the '
            'sheet holds every page+query row.')
    if all(r[4] is None for r in data):
        add('WARN', 'Search Console sheet', 'no Position column: the Position column on All Pages stays blank.')
    if not (a.gsc_start and a.gsc_end):
        add('WARN', 'Search Console sheet', 'the date range the sheet covers is not given (--gsc-start/--gsc-end). Ask '
            'the person: the Read Me needs it and GA4, if used, must use the same dates.')
    else:
        try:
            s, e = dt.date.fromisoformat(a.gsc_start), dt.date.fromisoformat(a.gsc_end)
            days = (e - s).days + 1
            add('INFO', 'Search Console sheet', f'window {s} to {e} ({days} days)')
            if days < 90:
                add('WARN', 'Search Console sheet', f'only {days} days. Mavan uses about 6 months; a short window '
                    'undercounts low-traffic pages.')
            if (dt.date.today() - e).days > 120:
                add('WARN', 'Search Console sheet', 'the window ended more than 4 months ago.')
        except ValueError:
            add('FAIL', 'Search Console sheet', 'dates must be YYYY-MM-DD.')


def check_prune(a):
    if not a.prune:
        add('INFO', 'Content prune', 'none provided. That is fine: page types come from the folder mapping and rules alone. '
            'If the client has a prune & merge workbook, provide it so the page types and planned redirects can be '
            'checked against it.')
        return
    if not os.path.isfile(a.prune):
        add('FAIL', 'Content prune', f'file not found: {a.prune}')
        return
    try:
        x = pd.read_excel(a.prune, sheet_name=None, dtype=str)
    except Exception as e:  # noqa: BLE001
        add('FAIL', 'Content prune', f'could not open it: {e}')
        return
    aud = next((d for n, d in x.items() if {'URL', 'Page Type'} <= set(d.columns)), None)
    if aud is None:
        add('FAIL', 'Content prune', 'no tab with URL and Page Type columns. Is this the Prune & Merge workbook?')
        return
    ns = find(aud.columns, ('next steps',))
    sg = find(aud.columns, ('suggested next step',))
    filled = int((aud[ns].fillna('').str.strip() != '').sum()) if ns else 0
    sug = int((aud[sg].fillna('').str.strip() != '').sum()) if sg else 0
    add('INFO', 'Content prune', f'{len(aud)} audited URLs; Next Steps filled for {filled}, Suggested Next Step for {sug}. '
        + ('Using the filled Next Steps as the plan.' if filled else 'Next Steps is empty, so the Suggested Next Step '
           'is treated as the plan; confirm with the person.'))


def check_facts(a):
    missing = [n for n, v in [('client name', a.client), ('main city and state', a.city), ('brand terms', a.brand)] if not v]
    if missing:
        add('WARN', 'Client facts', f'missing: {", ".join(missing)}. Ask in one question; other cities targeted are also '
            'needed (say "none" if there are none).')
    else:
        add('PASS', 'Client facts', f'{a.client}, {a.city}; brand terms: {a.brand}')
    if not a.domain:
        add('FAIL', 'Client facts', 'no domain')


def check_ga4(a):
    if a.ga4 == 'no':
        add('SKIPPED', 'GA4', 'skipped at the person\'s request: session and key-event columns stay blank and the Read '
            'Me says so. Composio is not needed.')
    elif a.ga4 == 'yes':
        add('INFO', 'GA4', 'wanted. Check that Composio has Google Analytics connected (COMPOSIO_SEARCH_TOOLS shows the '
            'connection) before Step 4; if it does not, tell the person and continue without GA4.')
    else:
        add('WARN', 'GA4', 'not decided. Ask whether to include GA4 (traffic too low to matter on some sites). '
            'Search Console no longer needs Composio.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domain', required=True)
    for k in ['urls', 'links', 'redirects', 'template', 'gsc-sheet', 'prune', 'client-redirects',
              'gsc-start', 'gsc-end', 'client', 'city', 'brand']:
        ap.add_argument('--' + k)
    ap.add_argument('--ga4', choices=['yes', 'no'])
    ap.add_argument('--skip', default='', help='comma list of inputs the person does not have: redirects, gsc, template')
    ap.add_argument('--out', default='work')
    a = ap.parse_args()
    a.skip = {s.strip() for s in a.skip.split(',') if s.strip()}
    a.skip = {{'redirects': 'Redirects export', 'gsc': 'Search Console sheet', 'template': 'Template'}.get(s, s) for s in a.skip}

    check_facts(a)
    check_urls(a)
    check_links(a)
    check_redirects(a)
    check_dates(a)
    check_template(a)
    check_gsc(a)
    if a.client_redirects and not os.path.isfile(a.client_redirects):
        add('FAIL', 'Client redirect list', f'file not found: {a.client_redirects}')
    elif a.client_redirects:
        add('INFO', 'Client redirect list', 'provided')
    check_prune(a)
    check_ga4(a)

    os.makedirs(a.out, exist_ok=True)
    order = {'FAIL': 0, 'WARN': 1, 'SKIPPED': 2, 'INFO': 3, 'PASS': 4}
    out = sorted(rows, key=lambda r: order[r[0]])
    lines = [f'{lv:<8} {nm}: {msg}' for lv, nm, msg in out]
    nf = sum(1 for r in rows if r[0] == 'FAIL')
    nw = sum(1 for r in rows if r[0] == 'WARN')
    verdict = ('NOT READY: fix the FAIL lines first.' if nf else
               f'READY, with {nw} warning(s) to tell the person about.' if nw else 'READY.')
    text = '\n'.join(lines) + f'\n\n{verdict}\n'
    print(text)
    with open(os.path.join(a.out, 'preflight.md'), 'w') as fh:
        fh.write('# Preflight\n\n```\n' + text + '```\n')
    sys.exit(1 if nf else 0)


if __name__ == '__main__':
    main()
