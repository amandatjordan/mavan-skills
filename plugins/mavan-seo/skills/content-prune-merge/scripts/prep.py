#!/usr/bin/env python3
"""Normalize Sitebulb or Screaming Frog exports and classify every internal link.

Usage:
  python prep.py --domain example.com --urls URLS.csv --links LINKS.csv --redirects REDIRECTS.csv
                 [--client-redirects LIST.csv] [--out work]
                 [--nav-regex R] [--footer-regex R] [--breadcrumb-regex R]

Writes to --out:
  crawl_pages.csv   one row per crawled URL (all statuses)
  links.csv         one row per linking page + target page + link class (Nav/Footer/Breadcrumb/Body)
  redirects.csv     source key -> final key for every redirect the crawl found
  prep_report.json  counts used by the Read Me

Links are classed from the CSS path (Sitebulb) or link path / XPath (Screaming Frog), not from
the crawler's location label, which Sitebulb sets to "Navigation" for almost everything. The
label is used only when a link has no path. Run once, read the class counts and the pattern
table, and re-run with the regex options if a menu or footer is being missed.
"""
import argparse
import collections
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, key, save_json  # noqa: E402

NAV_RE = (r'(?:^|[^a-z])(?:nav|navbar|navigation|menu|mega-?menu|menu-item|sub-menu|accordion|'
          r'site-header|main-header|header-menu|masthead|off-?canvas|top-?bar|hamburger|mobile-menu)(?:[^a-z]|$)'
          r'|(?:^|[\s>/])header(?:[\s>.#\[:/]|$)|#header')
FOOTER_RE = r'footer|colophon'
BREADCRUMB_RE = r'breadcrumb'


def find(df, *names):
    """First column whose name matches one of names (case-insensitive)."""
    low = {c.lower().strip(): c for c in df.columns}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None


def col(df, *names, default=''):
    c = find(df, *names)
    return df[c] if c else pd.Series([default] * len(df), index=df.index)


def read(path, **kw):
    return pd.read_csv(path, encoding='utf-8-sig', low_memory=False, dtype=str, **kw)


# Column names only one crawler uses. The URL column alone is not enough: some Screaming Frog
# exports call it "URL", so the crawler is chosen by how many of its own columns are present.
SF_COLS = ['Address', 'Content Type', 'Status Code', 'Status', 'Indexability Status', 'Title 1', 'H1-1',
           'Inlinks', 'Outlinks', 'Redirect URL', 'Redirect Type', 'Canonical Link Element 1']
SB_COLS = ['HTTP Status Code', 'Indexable', 'URLs with Duplicate H1', 'URLs with Duplicate Titles',
           'URLs with Similar Content', 'No. Internal Linking URLs', 'No. Content Words', 'Indexable Status']


def detect_crawler(u, forced=None):
    """Return (crawler, reason). Override with --crawler when the guess is wrong."""
    if forced:
        return forced, 'set with --crawler'
    sf = [c for c in SF_COLS if find(u, c)]
    sb = [c for c in SB_COLS if find(u, c)]
    if not find(u, 'Address', 'URL'):
        return None, ''
    if len(sf) > len(sb) or (len(sf) == len(sb) and find(u, 'Address')):
        return 'Screaming Frog', 'columns: ' + ', '.join(sf)
    if sb or find(u, 'URL'):
        return 'Sitebulb', 'columns: ' + (', '.join(sb) or 'URL only, no Screaming Frog columns')
    return None, ''


def pick(df, *names):
    """Column name for the first of names present (case-insensitive), else None."""
    return find(df, *names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domain', required=True)
    ap.add_argument('--urls', required=True)
    ap.add_argument('--links', required=True)
    ap.add_argument('--redirects', help='redirects export (required unless the URL export has a redirect target for every 3XX)')
    ap.add_argument('--crawler', choices=['Screaming Frog', 'Sitebulb'], help='force the crawler if detection guesses wrong')
    ap.add_argument('--client-redirects', help='optional existing redirect list (source, target columns)')
    ap.add_argument('--out', default='work')
    ap.add_argument('--nav-regex', default=NAV_RE)
    ap.add_argument('--footer-regex', default=FOOTER_RE)
    ap.add_argument('--breadcrumb-regex', default=BREADCRUMB_RE)
    a = ap.parse_args()
    dom = bare_domain(a.domain)
    os.makedirs(a.out, exist_ok=True)
    report = {'domain': dom, 'warnings': []}

    # ---------- URL export ----------
    u = read(a.urls)
    crawler, why = detect_crawler(u, a.crawler)
    if not crawler:
        sys.exit(f'Unrecognised URL export columns: {list(u.columns)[:20]}')
    report['crawler'] = crawler
    report['crawler_detected_from'] = why
    raw = col(u, 'Address', 'URL')
    status = pd.to_numeric(col(u, 'Status Code', 'HTTP Status Code'), errors='coerce')
    idx_text = col(u, 'Indexability Status', 'Indexable Status', 'Indexability').fillna('')
    idx_flag = col(u, 'Indexability', 'Indexable', 'Indexable Status').fillna('')
    indexable = idx_flag.str.strip().str.lower().isin(['indexable', 'yes', 'true'])
    depth_raw = col(u, 'Crawl Depth').fillna('')
    pages = pd.DataFrame({
        'url': raw,
        'key': raw.map(lambda x: key(x, dom)),
        'has_query': raw.fillna('').str.contains(r'\?', regex=True),
        'status': status,
        'indexable': indexable.map({True: 'Indexable', False: ''}),
        'index_detail': idx_text,
        'crawl_depth': depth_raw,
        'title': col(u, 'Title 1', 'Title').fillna(''),
        'h1': col(u, 'H1-1', 'H1').fillna(''),
        'h2': col(u, 'H2-1', 'H2s', 'H2', 'H2-1 (First)').fillna(''),
        'words': pd.to_numeric(col(u, 'Word Count', 'No. Content Words', 'Content Word Count'), errors='coerce'),
        'crawl_source': col(u, 'Crawl Source', 'Source').fillna(''),
        'redirect_to': col(u, 'Redirect URL', 'Redirect URL 1', 'Redirects To', 'Redirect Destination').fillna(''),
        'canonical': col(u, 'Canonical Link Element 1', 'Canonical URL', 'Canonical URLs', 'Canonical').fillna(''),
    })
    # indexability text for non-indexable pages: say why (Canonicalized, Noindex, ...)
    pages.loc[pages.indexable == '', 'indexable'] = pages.index_detail.where(pages.index_detail.str.strip() != '', 'Not indexable')
    pages = pages[pages.key != ''].drop(columns=['index_detail'])
    pages['h2'] = pages.h2.str.split(r'\s*[|\n]\s*').str[0].fillna('')
    pages = pages.sort_values(['has_query', 'status']).reset_index(drop=True)
    pages.to_csv(os.path.join(a.out, 'crawl_pages.csv'), index=False)
    counts = pages.status.fillna(0).astype(int).map(
        lambda s: '200' if s == 200 else '3xx' if 300 <= s < 400 else '4xx' if 400 <= s < 500 else '5xx' if s >= 500 else 'no response').value_counts().to_dict()
    report['url_counts'] = counts
    report['urls_total'] = int(len(pages))
    # Pagination variants (?e-page-1a2b=2, ?page=3, ?paged=2) canonicalize to the listing and get no audit row.
    report['pagination_query_urls'] = int(pages.url.fillna('').str.contains(r'[?&](?:e-page[^=&]*|page|paged)=\d+', regex=True).sum())

    # ---------- redirects ----------
    redir = {}
    is3 = (pages.status >= 300) & (pages.status < 400)
    for _, r in pages[is3 & (pages.redirect_to != '')].iterrows():
        redir[r.key] = (int(r.status), key(r.redirect_to, dom))
    missing_targets = int((is3 & (pages.redirect_to == '')).sum())
    if missing_targets and not a.redirects:
        sys.exit(f'{missing_targets} of the crawl\'s 3XX URLs have no redirect target in the URL export. The redirects export is '
                 'required: Sitebulb: the redirected URLs export; Screaming Frog: Response Codes > Redirection (3xx) > Export '
                 '(or Reports > Redirects > All Redirects). Pass it with --redirects. Do not resolve redirects with live requests.')
    if a.redirects:
        rd = read(a.redirects)
        src = col(rd, 'Address', 'Source URL', 'Source', 'URL')
        st = pd.to_numeric(col(rd, 'Status Code', 'HTTP Status Code', 'Status'), errors='coerce')
        dst = col(rd, 'Final Address', 'Redirect URL', 'Redirect Destination', 'Destination URL',
                  'Redirects To', 'Final Destination', 'Target URL')
        for s, c, d in zip(src, st, dst):
            if isinstance(s, str) and isinstance(d, str) and d.strip():
                redir[key(s, dom)] = (int(c) if c == c else 301, key(d, dom))
    rows = [{'source': k, 'status': v[0], 'final': v[1], 'origin': 'crawl'} for k, v in redir.items()]
    if a.client_redirects:
        cr = read(a.client_redirects)
        s_col = find(cr, 'source', 'source url', 'from', 'old url', 'redirect from', 'url')
        t_col = find(cr, 'target', 'target url', 'to', 'new url', 'redirect to', 'destination')
        if s_col and t_col:
            for s, t in zip(cr[s_col], cr[t_col]):
                if isinstance(s, str) and isinstance(t, str):
                    rows.append({'source': key(s, dom), 'status': 301, 'final': key(t, dom), 'origin': 'client list'})
            report['client_redirects'] = int(len(cr))
        else:
            report['warnings'].append(f'Client redirect list: could not find source/target columns in {list(cr.columns)[:10]}')
    pd.DataFrame(rows, columns=['source', 'status', 'final', 'origin']).to_csv(os.path.join(a.out, 'redirects.csv'), index=False)
    report['redirects'] = len(rows)

    # ---------- canonicals that point at a non-200 URL (including one that redirects back) ----------
    st_by_key = dict(zip(pages.key, pages.status))
    cano = []
    for _, r in pages[(pages.status == 200) & (pages.canonical != '')].iterrows():
        ck = key(r.canonical, dom)
        if ck == r.key or not ck.startswith('/'):
            continue
        cs = st_by_key.get(ck)
        back = redir.get(ck, (0, ''))[1] == r.key
        if (cs is not None and cs == cs and int(cs) != 200) or back:
            cano.append({'url': r.key, 'canonical': ck, 'canonical_status': '' if cs != cs or cs is None else int(cs),
                         'redirects_back': back})
    pd.DataFrame(cano, columns=['url', 'canonical', 'canonical_status', 'redirects_back']).to_csv(
        os.path.join(a.out, 'canonical_issues.csv'), index=False)
    report['canonical_issues'] = len(cano)
    report['canonical_redirect_loops'] = sum(1 for c in cano if c['redirects_back'])

    # ---------- links ----------
    # Map each field on its own, so a hybrid export (Sitebulb-style names from Screaming Frog, or the reverse) still works.
    head = read(a.links, nrows=0)
    m = {'src': find(head, 'Linking URL', 'Source', 'From', 'Linking Page'),
         'dst': find(head, 'Target URL', 'Destination', 'To', 'Target'),
         'anchor': find(head, 'Anchor Text', 'Anchor'),
         'pos': find(head, 'Location', 'Link Position', 'Position', 'Link Location'),
         'path': find(head, 'CSS Path', 'Link Path', 'XPath', 'Path'),
         'img': find(head, 'Image'),
         'type': find(head, 'Type', 'Link Type'),
         'alt': find(head, 'Alt Text')}
    if not (m['src'] and m['dst']):
        sys.exit(f'Unrecognised links export columns: {list(head.columns)[:20]}')
    if not (m['pos'] or m['path']):
        report['warnings'].append('Links export has neither a Location/Link Position column nor a CSS/Link Path: every link will count as Body.')
    use = [c for c in m.values() if c]
    raw_counts = collections.Counter()
    acc = {}
    n_rows = 0
    path_patterns = collections.Counter()
    for ch in read(a.links, usecols=use, chunksize=200000):
        if m.get('type'):
            ch = ch[ch[m['type']].fillna('').str.lower().isin(['hyperlink', 'ahref', ''])]
        n_rows += len(ch)
        src = ch[m['src']].map(lambda x: key(x, dom))
        dst = ch[m['dst']].map(lambda x: key(x, dom))
        anchor = ch[m['anchor']].fillna('') if m['anchor'] else pd.Series([''] * len(ch), index=ch.index)
        if m.get('alt'):
            anchor = anchor.where(anchor.str.strip() != '', ch[m['alt']].fillna(''))
        pos = ch[m['pos']].fillna('').str.lower() if m['pos'] else pd.Series([''] * len(ch), index=ch.index)
        path = ch[m['path']].fillna('').str.lower() if m['path'] else pd.Series([''] * len(ch), index=ch.index)
        img = (ch[m['img']].fillna('').str.lower().isin(['true', 'yes', '1']) if m['img']
               else anchor.str.strip().eq(''))
        cls = pd.Series('Body', index=ch.index)
        has_path = path.str.strip() != ''
        cls[~has_path & pos.str.contains('nav|header')] = 'Nav'
        cls[~has_path & pos.str.contains('footer')] = 'Footer'
        cls[~has_path & pos.str.contains('breadcrumb')] = 'Breadcrumb'
        cls[has_path & path.str.contains(a.nav_regex, regex=True)] = 'Nav'
        cls[has_path & path.str.contains(a.footer_regex, regex=True)] = 'Footer'
        cls[has_path & path.str.contains(a.breadcrumb_regex, regex=True)] = 'Breadcrumb'
        keep = src.str.startswith('/') & dst.str.startswith('/')
        pat = path.str.replace(r':nth-(child|of-type)\(\d+\)', '', regex=True).str.replace(r'\[\d+\]', '', regex=True)
        pat = pat.str.replace(r'\d+', 'N', regex=True).str[-90:]
        for s, d, c, an, im, p in zip(src[keep], dst[keep], cls[keep], anchor[keep], img[keep], pat[keep]):
            k = (s, d, c)
            raw_counts[k] += 1
            path_patterns[(c, p)] += 1
            if k not in acc:
                acc[k] = [an.strip()[:150], bool(im)]
            elif not acc[k][0] and an.strip():
                acc[k][0] = an.strip()[:150]
    L = pd.DataFrame([{'src': k[0], 'dst': k[1], 'cls': k[2], 'anchor': v[0], 'image': v[1],
                       'raw_count': raw_counts[k]} for k, v in acc.items()])
    if L.empty:
        sys.exit('No internal links found. Check --domain matches the links export.')
    L.to_csv(os.path.join(a.out, 'links.csv'), index=False)
    by_cls = L.cls.value_counts().to_dict()
    report['link_rows'] = int(n_rows)
    report['links_unique'] = int(len(L))
    report['link_classes'] = {c: int(by_cls.get(c, 0)) for c in ['Nav', 'Footer', 'Breadcrumb', 'Body']}
    nav_share = by_cls.get('Nav', 0) / len(L)
    report['nav_share'] = round(nav_share, 3)
    if nav_share >= 0.95:
        report['warnings'].append('95%+ of links classed as Nav: the classification failed. Read the pattern table and pass --nav-regex.')
    if by_cls.get('Body', 0) == 0:
        report['warnings'].append('No Body links at all: the classification failed or the export has no CSS/link paths.')
    save_json(os.path.join(a.out, 'prep_report.json'), report)

    print(f'{crawler} export ({why}): {len(pages)} URLs ({", ".join(f"{k}: {v}" for k, v in counts.items())}), '
          f'{len(redir)} redirects found by the crawl')
    print(f'Canonicals pointing at a non-200 URL: {len(cano)} ({report["canonical_redirect_loops"]} redirect back to the page); '
          f'pagination query URLs (no audit rows): {report["pagination_query_urls"]}')
    print(f'Links: {n_rows} internal link rows -> {len(L)} unique linking page + target + class')
    print('Link classes (unique linking page + target page):',
          ', '.join(f'{c} {report["link_classes"][c]}' for c in report['link_classes']))
    print('\nMost common link paths per class (check menus land in Nav and article copy in Body):')
    for c in ['Nav', 'Footer', 'Breadcrumb', 'Body']:
        top = [(p, n) for (cc, p), n in path_patterns.most_common() if cc == c][:6]
        for p, n in top:
            print(f'  {c:<10} {n:>7}  ...{p}')
    for w in report['warnings']:
        print('WARNING:', w)


if __name__ == '__main__':
    main()
