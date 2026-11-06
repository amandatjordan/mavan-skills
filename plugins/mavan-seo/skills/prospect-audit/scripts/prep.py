"""Prospect audit prep. Two commands:

  crawl     Check the crawl is not empty, write work/crawl.csv, and list thin-content candidates.
  keywords  Read the Semrush or Ahrefs ranking-keywords export and keyword-gap export,
            detect which tool made each, and write work/ranking.csv, work/gap.csv and work/ranking_urls.txt.

Everything here is a count, join or column mapping. Search volume and traffic are the tool's estimates,
never clicks or impressions.
"""
import argparse
import os
import re
import sys

import pandas as pd

from common import bare_domain, load_json, norm_url, num, pick, read_table, resolve

THIN_WORDS = 300          # same threshold as the service gap audit
EMPTY_SHARE_FAIL = 0.20   # fail when this share of 200 pages has no title, no H1 and no words

CRAWL_SPEC = {
    'url': (['URL', 'Address'], True),
    'status': (['HTTP Status Code', 'Status Code', 'Status'], True),
    'title': (['Title', 'Title 1'], True),
    'h1': (['H1', 'H1-1', 'H1-1'], True),
    'words': (['No. Content Words', 'Word Count', 'Words'], True),
    'indexable': (['Indexability', 'Indexable Status', 'Indexable'], False),
    'ctype': (['Content Type'], False),
}

RANKING_SPEC = {
    'keyword': (['Keyword'], True),
    'position': (['Position', 'Current position'], True),
    'url': (['URL', 'Current URL', 'Landing page'], True),
    'volume': (['Search Volume', 'Volume'], True),
    'traffic': (['Traffic', 'Organic traffic', 'Current organic traffic'], False),
}

GAP_SPEC = {
    'keyword': (['Keyword'], True),
    'volume': (['Search Volume', 'Volume'], True),
    'kd': (['Keyword Difficulty', 'KD'], False),
}

SEMRUSH_SIGNALS = {'searchvolume', 'keyworddifficulty', 'trafficcost', 'competitivedensity', 'trafficpercent'}
AHREFS_SIGNALS = {'volume', 'kd', 'currentposition', 'currenturl', 'organictraffic'}

DOMAIN_RE = re.compile(r'^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$')


def canon(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def read_any(path):
    if path.lower().endswith(('.xlsx', '.xls')):
        df = pd.read_excel(path, dtype=str, keep_default_na=False)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    return read_table(path)


def clean_headers(df):
    # "Traffic (%)" and "Traffic" would collide once punctuation is stripped.
    df.columns = [c.replace('(%)', ' percent').replace('%', ' percent').strip() for c in df.columns]
    return df


def detect_tool(df, name):
    cols = {canon(c) for c in df.columns}
    s, a = len(cols & SEMRUSH_SIGNALS), len(cols & AHREFS_SIGNALS)
    if s == a:
        raise SystemExit(f'{name}: cannot tell whether this is Semrush or Ahrefs from its columns {list(df.columns)}. '
                         'Ask the person which tool made it, then re-run with --tool semrush|ahrefs.')
    return 'semrush' if s > a else 'ahrefs'


def folder_of(url):
    path = re.sub(r'^[a-z]+://[^/]+', '', str(url)).split('?')[0].split('#')[0]
    seg = [p for p in path.split('/') if p]
    return seg[0].lower() if len(seg) > 1 else '(root)'


# ---------------------------------------------------------------- crawl

def cmd_crawl(a):
    os.makedirs(a.out, exist_ok=True)
    df = clean_headers(read_any(a.crawl))
    m = resolve(df, CRAWL_SPEC, 'crawl', a.overrides)
    if m['ctype']:
        before = len(df)
        df = df[df[m['ctype']].str.lower().str.contains('html', na=False)]
        print(f'  Kept {len(df):,} of {before:,} rows with an HTML content type.')
    d = pd.DataFrame({
        'url': df[m['url']].str.strip(),
        'status': pd.to_numeric(df[m['status']], errors='coerce'),
        'title': df[m['title']].str.strip(),
        'h1': df[m['h1']].str.strip(),
        'words': df[m['words']].map(num),
    })
    if m['indexable']:
        d['indexable'] = df[m['indexable']].str.lower().str.strip().str.startswith('indexable')
    else:
        d['indexable'] = True
        print('  NOTE: no indexability column; every 200 page is treated as indexable.')
    d['norm'] = d['url'].map(norm_url)
    d['folder'] = d['url'].map(folder_of)
    d.to_csv(os.path.join(a.out, 'crawl.csv'), index=False)

    live = d[d['status'] == 200]
    print(f'  {len(d):,} URLs; {len(live):,} return 200; status counts: '
          + ', '.join(f'{int(k)}: {v}' for k, v in d['status'].value_counts().sort_index().items() if k == k))
    if len(live) < 10:
        print('FAIL: fewer than 10 pages return 200. The export is the wrong one or the crawl was blocked.')
        sys.exit(2)
    empty = live[(live['title'] == '') & (live['h1'] == '') & (live['words'].fillna(0) == 0)]
    share = len(empty) / len(live)
    print(f'  200 pages with no title, no H1 and no words: {len(empty):,} ({share:.0%}).')
    if share >= EMPTY_SHARE_FAIL:
        print(f'FAIL: {share:.0%} of 200 pages are empty (limit {EMPTY_SHARE_FAIL:.0%}). The crawl likely did not render '
              'the pages. Re-crawl (check JavaScript rendering and blocking) before auditing.')
        sys.exit(2)

    cand = live[live['indexable'] & (live['words'].fillna(0) < THIN_WORDS)].copy()
    cand['reason'] = cand['words'].fillna(0).map(lambda w: 'No content words' if w == 0 else f'Under {THIN_WORDS} content words')
    cand.drop(columns=['norm']).to_csv(os.path.join(a.out, 'thin_candidates.csv'), index=False)
    print(f'  Thin-content candidates (200, indexable, under {THIN_WORDS} words): {len(cand):,}.')
    prof = (live.assign(thin=live.index.isin(cand.index)).groupby('folder')
            .agg(live_pages=('url', 'size'), thin=('thin', 'sum')).sort_values('thin', ascending=False))
    print('  Folders with the most candidates (folder, live pages, thin candidates):')
    for f, r in prof.head(15).iterrows():
        print(f'    {f}: {int(r.live_pages)} live, {int(r.thin)} thin')
    print('PASS crawl')


# ---------------------------------------------------------------- keywords

def domain_columns(df, skip):
    """Map domain -> column for the per-domain position columns of a gap export."""
    out = {}
    for c in df.columns:
        low = c.lower()
        if c in skip or any(w in low for w in ('url', 'traffic', 'volume', 'difficulty')):
            continue
        cand = re.sub(r'\s*[-:(]*\s*(position|pos\.?|rank|ranking)\)?\s*$', '', low).strip()
        cand = bare_domain(cand)
        if DOMAIN_RE.match(cand):
            out[cand] = c
    return out


def cmd_keywords(a):
    os.makedirs(a.out, exist_ok=True)
    cfg = load_json(a.config, {})
    prospect = bare_domain(cfg.get('domain', ''))
    if not prospect:
        raise SystemExit('config.json needs "domain" (the prospect).')
    tools = set()
    ranking_urls = []

    if a.ranking:
        df = clean_headers(read_any(a.ranking))
        tool = a.tool or detect_tool(df, 'ranking keywords export')
        tools.add(tool)
        print(f'  Ranking keywords export: detected {tool.capitalize()}.')
        m = resolve(df, RANKING_SPEC, 'ranking', a.overrides)
        r = pd.DataFrame({
            'keyword': df[m['keyword']].str.strip(),
            'position': df[m['position']].map(num),
            'url': df[m['url']].str.strip(),
            'est_volume': df[m['volume']].map(num),
            'est_traffic': df[m['traffic']].map(num) if m['traffic'] else float('nan'),
        })
        r = r[(r['keyword'] != '') & (r['url'] != '')]
        r['norm'] = r['url'].map(norm_url)
        r.to_csv(os.path.join(a.out, 'ranking.csv'), index=False)
        ranking_urls = sorted(r['url'].unique())
        with open(os.path.join(a.out, 'ranking_urls.txt'), 'w') as f:
            f.write('\n'.join(ranking_urls) + '\n')
        print(f'  {len(r):,} ranking keywords on {len(ranking_urls):,} URLs. Add work/ranking_urls.txt (and the sitemap) '
              'to the crawl as a URL list so old and orphaned URLs are crawled.')
        if len(df) in (1000, 5000, 10000, 20000, 25000, 30000, 50000, 100000):
            print(f'  NOTE: {len(df):,} rows is a round number, so the export may be capped. Pages with more '
                  'keywords than were exported will show fewer tracked keywords.')

    if a.gap:
        df = clean_headers(read_any(a.gap))
        tool = a.tool or detect_tool(df, 'keyword gap export')
        tools.add(tool)
        print(f'  Keyword gap export: detected {tool.capitalize()}.')
        m = resolve(df, GAP_SPEC, 'gap', a.overrides)
        known = {c for c in m.values() if c}
        doms = domain_columns(df, known)
        for item in a.gap_col or []:
            dom, col = item.split('=', 1)
            if col not in df.columns:
                raise SystemExit(f'--gap-col: column "{col}" not in {list(df.columns)}')
            doms[bare_domain(dom)] = col
        if prospect not in doms:
            raise SystemExit(f'The prospect {prospect} has no position column in the gap export. Domain columns found: '
                             f'{sorted(doms)}. Use --gap-col "{prospect}=Column name" or check the export includes the prospect.')
        comps = [bare_domain(c) for c in cfg.get('competitors', [])] or [d for d in doms if d != prospect]
        missing = [c for c in comps if c not in doms]
        if missing:
            raise SystemExit(f'Competitors missing from the gap export: {missing}. Domain columns found: {sorted(doms)}.')
        print('  Domain columns: ' + ', '.join(f'{d}<-"{doms[d]}"' for d in [prospect] + comps))

        def pos(col):
            p = df[col].map(num)
            return p.where(p > 0)

        g = pd.DataFrame({'keyword': df[m['keyword']].str.strip(),
                          'est_volume': df[m['volume']].map(num),
                          'kd': df[m['kd']].map(num) if m['kd'] else float('nan'),
                          'prospect_position': pos(doms[prospect])})
        for c in comps:
            g[c] = pos(doms[c])
        total = len(g)
        has_comp = g[comps].notna().any(axis=1)
        g = g[(g['keyword'] != '') & g['prospect_position'].isna() & has_comp]
        g.to_csv(os.path.join(a.out, 'gap.csv'), index=False)
        print(f'  {total:,} gap rows; {len(g):,} are searches at least one competitor ranks for and the prospect does not.')

    if len(tools) > 1:
        print(f'  NOTE: the two exports come from different tools ({sorted(tools)}). Volume and position scales differ; '
              'say so in the reply.')
    if tools:
        with open(os.path.join(a.out, 'tool.txt'), 'w') as f:
            f.write('/'.join(sorted(t.capitalize() for t in tools)))
    print('PASS keywords')


def parse_map(items):
    out = {}
    for it in items or []:
        k, v = it.split('=', 1)
        out[k.strip()] = v.strip()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('crawl')
    c.add_argument('--crawl', required=True)
    c.add_argument('--out', default='work')
    c.add_argument('--map', action='append', help='crawl.FIELD="Column name"')
    k = sub.add_parser('keywords')
    k.add_argument('--config', required=True)
    k.add_argument('--ranking')
    k.add_argument('--gap')
    k.add_argument('--tool', choices=['semrush', 'ahrefs'])
    k.add_argument('--out', default='work')
    k.add_argument('--map', action='append', help='ranking.FIELD or gap.FIELD="Column name"')
    k.add_argument('--gap-col', action='append', help='domain.com="Column name" for a position column')
    a = ap.parse_args()
    a.overrides = parse_map(a.map)
    {'crawl': cmd_crawl, 'keywords': cmd_keywords}[a.cmd](a)


if __name__ == '__main__':
    main()
