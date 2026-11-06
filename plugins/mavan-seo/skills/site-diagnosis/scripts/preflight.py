#!/usr/bin/env python3
"""Preflight for the site-diagnosis skill: check every file and answer before any work starts.

Usage:
  python preflight.py --domain example.com --client "Name" --brand "term,term" \
        --a A.xlsx [--a-tab NAME] --a-start YYYY-MM-DD --a-end YYYY-MM-DD \
        --b B.xlsx [--b-tab NAME] --b-start YYYY-MM-DD --b-end YYYY-MM-DD \
        [--crawl URLS.csv] [--links LINKS.csv] [--redirects REDIRECTS.csv] [--out work]

Leave out anything you do not have yet and the preflight reports it. It reads headers and the
Search Console rows only, so it takes seconds. It writes OUT/preflight.md and exits 1 when anything FAILs.
Pass --brand none when the person said not to filter brand searches.

What it checks:
- Search Console: each period's file has a tab with Page, Query, Clicks and Impressions; the tab is clear
  (or given with --a-tab / --b-tab); A and B are not the same tab; the pages are on this domain.
- Dates: both ranges given, valid, A before B, not overlapping; similar lengths.
- Crawl URL export: one export with every column triage, the IA audit and the service gap audit need,
  every status code, the homepage, this domain. Missing columns are reported with the audit that needs them.
- Links and redirects exports: only if given (the IA audit needs them; its own preflight checks them in full).
- Client facts: domain, client name, brand terms.
"""
import argparse
import datetime as dt
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from triage import GSC_TAB, bare_domain, read_raw, read_tabs  # noqa: E402

# role: (names accepted, which steps need it). Triage needs only url and status.
CRAWL_COLS = {
    'url': (('url', 'address'), 'triage, IA audit, service gap audit'),
    'status': (('http status code', 'status code'), 'triage, IA audit, service gap audit'),
    'indexable': (('indexable status', 'indexability status', 'indexability'), 'IA audit, service gap audit'),
    'crawl depth': (('crawl depth',), 'IA audit'),
    'title': (('title', 'title 1', 'page title'), 'IA audit, service gap audit (required there)'),
    'meta description': (('meta description', 'meta description 1'), 'service gap audit'),
    'h1': (('h1', 'h1-1'), 'IA audit, service gap audit (required there)'),
    'h2': (('h2', 'h2-1', 'h2s', 'h2-1 (first)'), 'IA audit, service gap audit'),
    'second h2': (('h2 (second)', 'h2-2'), 'service gap audit'),
    'word count': (('no. content words', 'word count', 'no. words'), 'IA audit, service gap audit (required there)'),
    'internal links to URL': (('no. internal linking urls', 'unique inlinks', 'no. internal links to url', 'inlinks'),
                              'IA audit'),
    'canonical': (('canonical url', 'canonical link element 1', 'canonical'), 'service gap audit'),
}
TRIAGE_REQUIRED = ('url', 'status')
SEARCH_COLS = ('clicks', 'impressions', 'ctr', 'position', 'sessions', 'users', 'ga4 sessions')
LINK_COLS = {'target': ('target url', 'destination', 'to'), 'source': ('linking url', 'source', 'from')}
REDIR_COLS = {'source': ('url', 'address', 'source', 'from'),
              'target': ('redirect url', 'redirect destination', 'destination', 'final address', 'to')}

rows = []


def add(level, name, msg):
    rows.append((level, name, msg))


def find(cols, names):
    low = {str(c).lower().strip(): c for c in cols}
    return next((low[n] for n in names if n in low), None)


def exists(name, path, missing_level, missing_msg):
    if not path:
        add(missing_level, name, missing_msg)
        return False
    if not os.path.isfile(path):
        add('FAIL', name, f'file not found: {path}')
        return False
    return True


def table(path):
    """-> DataFrame of the first table found in a CSV or the first sheet of an xlsx, header detected in the first 10 rows."""
    raw = read_raw(path)
    data = next(iter(raw.values()))
    known = {n for names, _ in CRAWL_COLS.values() for n in names} | {n for v in LINK_COLS.values() for n in v} | \
            {n for v in REDIR_COLS.values() for n in v}
    hi = next((i for i, r in enumerate(data[:10]) if sum(str(c).strip().lower() in known for c in r) >= 2), 0)
    return pd.DataFrame(data[hi + 1:], columns=[str(c).strip() for c in data[hi]]).fillna('')


# ---------------------------------------------------------------- Search Console
def pick(tabs, tab):
    if tab:
        return tab if tab in tabs else None
    named = next((n for n in tabs if n.strip().lower() == GSC_TAB.lower()), None)
    if named:
        return named
    return next(iter(tabs)) if len(tabs) == 1 else None


def check_period(tag, path, tab, domain):
    name = f'Search Console period {tag}'
    if not exists(name, path, 'FAIL', f'not provided. Ask for the page + query export for period {tag} '
                  '(Page, Query, Clicks, Impressions; Position used when present).'):
        return None
    try:
        tabs = read_tabs(path)
    except Exception as e:  # noqa: BLE001
        add('FAIL', name, f'could not read it: {e}')
        return None
    if not tabs:
        add('FAIL', name, 'no tab has Page, Query, Clicks and Impressions columns. It must be a page + query export: '
            'the Performance report download (separate Pages and Queries tables) does not work.')
        return None
    use = pick(tabs, tab)
    if use is None:
        if tab:
            add('FAIL', name, f"tab '{tab}' has no Page, Query, Clicks and Impressions columns. Tabs that do: "
                f"{', '.join(tabs)}")
        else:
            add('FAIL', name, 'several tabs have Search Console columns: ' +
                '; '.join(f"'{n}' ({len(r)} rows)" for n, r in tabs.items()) +
                f'. Ask which tab is period {tag}, then pass --{tag.lower()}-tab. Never add tabs together.')
        return None
    data = tabs[use]
    if not data:
        add('FAIL', name, f"tab '{use}' has the columns but no rows.")
        return None
    pages = {p for p, *_ in data}
    on = sum(domain in re.sub(r'^https?://(www\.)?', '', p.lower()).split('/')[0] or p.startswith('/') for p in pages)
    share = on / len(pages)
    if share < 0.5:
        add('FAIL', name, f'only {share:.0%} of its pages are on {domain}. Wrong property or wrong domain?')
    elif share < 1:
        add('WARN', name, f'{len(pages) - on} of {len(pages)} pages are not on {domain} (another subdomain or site); '
            'they are kept under their full URL.')
    if all(r[4] is None for r in data):
        add('INFO', name, 'no Position column: average positions will be blank.')
    add('PASS', name, f"tab '{use}': {len(data)} page + query rows, {len(pages)} pages, "
        f'{sum(r[2] for r in data):,.0f} clicks, {sum(r[3] for r in data):,.0f} impressions')
    return (os.path.abspath(path), use)


def check_dates(a):
    got = {k: getattr(a, k) for k in ('a_start', 'a_end', 'b_start', 'b_end')}
    if not all(got.values()):
        add('FAIL', 'Date ranges', 'missing: ' + ', '.join('--' + k.replace('_', '-') for k, v in got.items() if not v) +
            '. The sheets do not say which dates they cover: ask the person (multiple choice) and never guess.')
        return
    try:
        d = {k: dt.date.fromisoformat(v) for k, v in got.items()}
    except ValueError:
        add('FAIL', 'Date ranges', 'dates must be YYYY-MM-DD.')
        return
    if d['a_start'] > d['a_end'] or d['b_start'] > d['b_end']:
        add('FAIL', 'Date ranges', 'a period starts after it ends.')
        return
    if d['a_start'] >= d['b_start']:
        add('FAIL', 'Date ranges', 'period A must be the earlier period. Swap the sheets or the dates.')
        return
    if d['a_end'] >= d['b_start']:
        add('WARN', 'Date ranges', f"the periods overlap ({a.a_end} is on or after {a.b_start}): the same days are counted "
            'in both, which shrinks the change.')
    la, lb = (d['a_end'] - d['a_start']).days + 1, (d['b_end'] - d['b_start']).days + 1
    if abs(la - lb) / max(la, lb) > 0.1:
        add('WARN', 'Date ranges', f'period A is {la} days and period B {lb} days: totals are not like for like. '
            'Confirm with the person or use equal lengths.')
    oldest = dt.date.today() - dt.timedelta(days=486)
    if d['a_start'] < oldest:
        add('WARN', 'Date ranges', f'period A starts {a.a_start}; Search Console keeps about 16 months, so an export '
            'that far back may be incomplete.')
    add('PASS', 'Date ranges', f'A {a.a_start} to {a.a_end} ({la} days), B {a.b_start} to {a.b_end} ({lb} days)')


# ---------------------------------------------------------------- crawl
def check_crawl(a, domain):
    name = 'Crawl URL export'
    if not exists(name, a.crawl, 'WARN', 'not provided. Ask for it now (one URL export with every column, from a crawl '
                  'with the XML sitemap added as a crawl source). Triage can run without it but cannot flag losing URLs '
                  'that no longer return 200, and the IA and service gap audits cannot run.'):
        return
    try:
        d = table(a.crawl)
    except Exception as e:  # noqa: BLE001
        add('FAIL', name, f'could not read it: {e}')
        return
    cols = list(d.columns)
    got = {role: find(cols, names) for role, (names, _) in CRAWL_COLS.items()}
    for role in TRIAGE_REQUIRED:
        if not got[role]:
            add('FAIL', name, f'no {role} column (looked for: {", ".join(CRAWL_COLS[role][0])}). Columns found: '
                f'{", ".join(cols[:12])}. This is not the crawler\'s URL export.')
    if not all(got[r] for r in TRIAGE_REQUIRED):
        return
    missing = [r for r in CRAWL_COLS if not got[r]]
    for r in missing:
        add('WARN', name, f'no {r} column; needed by the {CRAWL_COLS[r][1]}. Re-export with it before that audit runs.')
    extra = [c for c in cols if str(c).strip().lower() in SEARCH_COLS]
    if extra:
        add('WARN', name, f'has search or analytics columns ({", ".join(extra)}). Re-export without them: Search '
            'Console comes from the sheets, so crawl columns with the same names cause confusion.')
    st = d[got['status']].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    n = len(d)
    if n == 0:
        add('FAIL', name, 'no rows.')
        return
    add('INFO', name, f'{n} URLs: ' + ', '.join(f'{k} x{v}' for k, v in st.value_counts().head(5).items()))
    if (st != '200').sum() == 0:
        add('WARN', name, 'every URL is 200: redirects and errors are missing. Export every status code, not only '
            'indexable pages, or triage cannot flag dead URLs.')
    urls = d[got['url']].astype(str).str.lower()
    on = urls.str.contains(re.escape(domain)).mean()
    if on < 0.5:
        add('FAIL', name, f'only {on:.0%} of URLs contain {domain}. Wrong site?')
    elif on < 0.9:
        add('WARN', name, f'only {on:.0%} of URLs contain {domain}. A mixed export?')
    home = urls.str.rstrip('/').str.replace(r'^https?://(www\.)?', '', regex=True).eq(domain).any()
    if not home:
        add('WARN', name, 'the homepage is not in the export, so it is probably filtered. Ask for the unfiltered export.')
    if n < 30:
        add('WARN', name, f'only {n} rows. The audits need the whole site, not a filtered list.')
    if not missing:
        add('PASS', name, 'has every column triage, the IA audit and the service gap audit use.')


def check_links(a):
    if not exists('Links export', a.links, 'INFO', 'not provided. Only needed if the IA audit runs; ask for it from the '
                  'same crawl then.'):
        return
    try:
        d = table(a.links)
    except Exception as e:  # noqa: BLE001
        add('FAIL', 'Links export', f'could not read it: {e}')
        return
    if not all(find(d.columns, v) for v in LINK_COLS.values()):
        add('FAIL', 'Links export', 'needs a target and a linking-page column (Sitebulb: Target URL + Linking URL; '
            f'Screaming Frog: Destination + Source). Columns found: {", ".join(list(d.columns)[:10])}.')
        return
    add('PASS', 'Links export', 'columns OK. The IA audit\'s preflight checks it in full.')


def check_redirects(a):
    if not exists('Redirects export', a.redirects, 'INFO', 'not provided. Only needed if the IA audit runs; ask for it '
                  'from the same crawl then.'):
        return
    try:
        d = table(a.redirects)
    except Exception as e:  # noqa: BLE001
        add('FAIL', 'Redirects export', f'could not read it: {e}')
        return
    if not all(find(d.columns, v) for v in REDIR_COLS.values()):
        add('FAIL', 'Redirects export', 'needs a source and a redirect-target column. Columns found: '
            f'{", ".join(list(d.columns)[:10])}.')
        return
    add('PASS', 'Redirects export', f'{len(d)} redirecting URLs.')


def check_facts(a):
    if not a.domain:
        add('FAIL', 'Client facts', 'no domain.')
    if not a.client:
        add('FAIL', 'Client facts', 'no client name (it heads the workbook).')
    if not a.brand:
        add('FAIL', 'Client facts', 'brand terms not confirmed. Offer the candidates from the business name and domain '
            '(multiple choice); pass --brand none if the person says not to filter.')
    elif a.domain and a.client:
        add('PASS', 'Client facts', f'{a.client}, {bare_domain(a.domain)}; brand terms: {a.brand}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ('domain', 'client', 'brand', 'a', 'a-tab', 'a-start', 'a-end', 'b', 'b-tab', 'b-start', 'b-end',
              'crawl', 'links', 'redirects'):
        ap.add_argument(f'--{k}')
    ap.add_argument('--out', default='work')
    a = ap.parse_args()
    domain = bare_domain(a.domain) if a.domain else ''

    check_facts(a)
    pa = check_period('A', a.a, a.a_tab, domain)
    pb = check_period('B', a.b, a.b_tab, domain)
    if pa and pb and pa == pb:
        add('FAIL', 'Search Console', f"period A and period B are the same tab ('{pa[1]}'). Each period needs its own "
            'sheet or tab.')
    check_dates(a)
    check_crawl(a, domain)
    check_links(a)
    check_redirects(a)

    os.makedirs(a.out, exist_ok=True)
    order = {'FAIL': 0, 'WARN': 1, 'INFO': 2, 'PASS': 3}
    lines = [f'{lv:<5} {nm}: {msg}' for lv, nm, msg in sorted(rows, key=lambda r: order[r[0]])]
    nf = sum(r[0] == 'FAIL' for r in rows)
    nw = sum(r[0] == 'WARN' for r in rows)
    verdict = ('NOT READY: fix the FAIL lines first.' if nf else
               f'READY, with {nw} warning(s) to tell the person about.' if nw else 'READY.')
    text = '\n'.join(lines) + f'\n\n{verdict}\n'
    print(text)
    with open(os.path.join(a.out, 'preflight.md'), 'w', encoding='utf-8') as fh:
        fh.write('# Preflight\n\n```\n' + text + '```\n')
    sys.exit(1 if nf else 0)


if __name__ == '__main__':
    main()
