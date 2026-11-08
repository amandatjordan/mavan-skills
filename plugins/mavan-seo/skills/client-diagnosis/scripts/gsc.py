"""Search Console (GSC) helpers for client-diagnosis.

Reads Mavan's GSC export (one row per date + page + query), splits it into two consecutive 6-month periods that end on
the newest date in the file, checks whether impressions can be compared between the two periods, lists the keywords
whose clicks fell, and scores the GSC signals. Every count, share and sum is computed here. No API and no connector:
the downloaded .xlsx or .csv is the only source.

Why impressions can be "not comparable": GSC exports and sheet add-ons cap the row count (often 25,000) and sort by
clicks. The cap then keeps every row that had a click but drops zero-click rows, which are most of the impressions,
from whichever dates come last. Clicks stay complete; impressions of the affected period are far too low.
"""
import re
import sys

import pandas as pd

from common import norm_url, num, pick, read_table

GSC_TAB = 'Claude Use This'   # the tab of Mavan's Search Console template that is used when it exists
GSC_SPEC = {
    'date': (['Date', 'Day', 'Month'], True),
    'query': (['Query', 'Top queries', 'Search query'], True),
    'page': (['Page', 'Landing page', 'Top pages', 'URL'], True),
    'clicks': (['Clicks'], True),
    'impr': (['Impressions'], True),
    'pos': (['Position', 'Average position', 'Avg. position'], False),
}
ROUND_ROWS = {1000, 5000, 10000, 20000, 25000, 30000, 50000, 100000}
PERIOD_MONTHS = 6
MIN_SPAN_DAYS_SLACK = 14       # the data must start within this many days of the start of period A
COMPARABLE_RATIO = 0.5         # zero-click rows' share of a period must be at least this fraction of the other period's

# Defaults for the thresholds the person confirms each run (references/rules.md)
CLICK_FLOOR = 3                # a keyword with at least this many clicks in either period is judged by clicks
IMPR_FLOOR = 50                # impressions a keyword needs in period A to be judged by impressions
IMPR_DROP = 0.5                # impressions down this share or more count as a drop (impressions basis only)
TREND_MIN_CLICKS = 10          # non-brand clicks in period A needed to score the traffic trend by clicks
TREND_DROP = 0.20              # non-brand clicks (or impressions) down this share or more = 1 point
MIN_QUERY_IMPR = 20            # impressions a search needs in period B to count as a real search
MIN_PAGE_IMPR = 10             # impressions a URL needs on one search to count as competing for it
COMPETING_SHARE = 0.30         # competing searches as a share of real searches = 1 point
ARCHIVE_IMPR_SHARE = 0.30      # archive pages' share of non-brand impressions in period B = 1 point
ZERO_IMPR_SHARE = 0.80         # indexable pages with no impressions in period B = 1 point
STRIKE_LOW, STRIKE_HIGH = 8, 20
STRIKE_MIN = 6                 # striking-distance searches needed for 1 point


def term_re(t):
    """Whole word or phrase, optional plural s / es."""
    return re.compile(r'(?<![a-z0-9])' + re.escape(t.lower()) + r'(e?s)?(?![a-z0-9])')


def brand_re(terms):
    """Whole-word match for any brand term (spaces match any run of spaces); None when there are no terms."""
    parts = [re.escape(t.strip().lower()).replace(r'\ ', r'\s+') for t in terms if t and t.strip()]
    if not parts:
        return None
    return re.compile(r'(?<![a-z0-9])(' + '|'.join(parts) + r')(?![a-z0-9])')


# ------------------------------------------------------------------ loading

def _tabs(path):
    if str(path).lower().endswith(('.xlsx', '.xlsm', '.xls')):
        out = {}
        for name, df in pd.read_excel(path, sheet_name=None, dtype=str, keep_default_na=False).items():
            df.columns = [str(c).strip() for c in df.columns]
            out[name] = df
        return out
    return {'(file)': read_table(path)}


def load(path, tab, domain, brand_terms):
    """-> (DataFrame [date, page, query, clicks, impr, pos, brand], info). Page keys use common.norm_url, the same
    as the crawl, so a GSC page and its crawl row join. Stops with a message the person can act on."""
    tabs = {n: d for n, d in _tabs(path).items() if all(pick(d, al) for f, (al, req) in GSC_SPEC.items() if req)}
    if not tabs:
        sys.exit(f'{path}: no tab has Date, Query, Page, Clicks and Impressions columns. Ask the person for the '
                 'Search Console sheet with a Date column (one row per date, page and query).')
    if tab:
        if tab not in tabs:
            sys.exit(f"--gsc-tab '{tab}' is not a tab with those columns. Tabs: {', '.join(tabs)}")
        use = tab
    else:
        use = next((n for n in tabs if n.strip().lower() == GSC_TAB.lower()), None) or \
            (next(iter(tabs)) if len(tabs) == 1 else None)
        if use is None:
            sys.exit(f'{path} has several tabs with GSC columns: {", ".join(tabs)}. Ask the person which tab, then pass '
                     '--gsc-tab. Never add tabs together.')
    raw = tabs[use]
    m = {f: pick(raw, al) for f, (al, req) in GSC_SPEC.items()}
    df = pd.DataFrame({
        'date': pd.to_datetime(raw[m['date']], errors='coerce'),
        'page': raw[m['page']].map(norm_url),
        'query': raw[m['query']].str.strip().str.lower(),
        'clicks': raw[m['clicks']].map(num),
        'impr': raw[m['impr']].map(num),
        'pos': raw[m['pos']].map(num) if m['pos'] else float('nan'),
    })
    n_raw = len(df)
    df = df.dropna(subset=['date', 'clicks', 'impr'])
    df = df[(df['query'] != '') & (df['page'] != '')]
    rx = brand_re(brand_terms)
    df['brand'] = df['query'].map(lambda q: bool(rx.search(q))) if rx else False
    foreign = sorted({p for p in df['page'] if domain and p.split('/')[2] != domain})
    info = {'tab': use, 'rows_read': n_raw, 'rows_used': len(df), 'dropped': n_raw - len(df),
            'has_position': bool(m['pos']), 'columns': {k: v for k, v in m.items() if v}, 'foreign': foreign}
    return df.reset_index(drop=True), info


# ------------------------------------------------------------------ periods

def periods(df):
    """Two consecutive 6-month periods ending on the newest date. B = the later one."""
    end = df['date'].max().normalize()
    b_start = end - pd.DateOffset(months=PERIOD_MONTHS) + pd.Timedelta(days=1)
    a_start = b_start - pd.DateOffset(months=PERIOD_MONTHS)
    return {'a_start': a_start, 'a_end': b_start - pd.Timedelta(days=1), 'b_start': b_start, 'b_end': end}


def split(df, p):
    a = df[(df['date'] >= p['a_start']) & (df['date'] <= p['a_end'])]
    b = df[(df['date'] >= p['b_start']) & (df['date'] <= p['b_end'])]
    return a, b


def profile(df):
    """Coverage and impression-comparability facts used by preflight and build."""
    p = periods(df)
    a, b = split(df, p)

    def zshare(x):
        return float((x['clicks'] == 0).mean()) if len(x) else 0.0
    za, zb = zshare(a), zshare(b)
    hi, lo = max(za, zb), min(za, zb)
    comparable = bool(len(a) and len(b)) and (hi == 0 or lo >= COMPARABLE_RATIO * hi)
    covered = df['date'].min() <= p['a_start'] + pd.Timedelta(days=MIN_SPAN_DAYS_SLACK)
    reason = ''
    if not comparable and len(a) and len(b):
        thin = 'B' if zb < za else 'A'
        reason = (f'Zero-click rows are {za:.0%} of period A but {zb:.0%} of period B: the export looks capped at '
                  f'{len(df):,} rows' + (' (a round number)' if len(df) in ROUND_ROWS else '') +
                  f' and sorted by clicks, so impressions in period {thin} are mostly missing. Clicks are complete; '
                  'impressions are not comparable between the periods.')
    return {**p, 'min_date': df['date'].min().normalize(), 'rows': len(df), 'rows_a': len(a), 'rows_b': len(b),
            'zero_a': za, 'zero_b': zb, 'comparable': comparable, 'covered': bool(covered), 'reason': reason,
            'capped': len(df) in ROUND_ROWS}


# ------------------------------------------------------------------ aggregation

def agg_query(df):
    """One row per query: clicks, impressions and impression-weighted average position."""
    d = df.assign(pw=df['pos'].fillna(0) * df['impr'].where(df['pos'].notna(), 0),
                  pi=df['impr'].where(df['pos'].notna(), 0))
    g = d.groupby('query', as_index=False).agg(clicks=('clicks', 'sum'), impr=('impr', 'sum'), pw=('pw', 'sum'),
                                               pi=('pi', 'sum'))
    g['pos'] = (g['pw'] / g['pi']).where(g['pi'] > 0)
    return g.drop(columns=['pw', 'pi'])


def query_table(a, b):
    """Non-brand queries, both periods side by side. Change = B minus A."""
    qa, qb = agg_query(a[~a['brand']]), agg_query(b[~b['brand']])
    q = qa.merge(qb, on='query', how='outer', suffixes=('_a', '_b'))
    for c in ('clicks_a', 'clicks_b', 'impr_a', 'impr_b'):
        q[c] = q[c].fillna(0)
    q['change'] = q['clicks_b'] - q['clicks_a']
    top = a[~a['brand']].groupby(['query', 'page'])['clicks'].sum().reset_index().sort_values(
        ['clicks', 'page'], ascending=[False, True]).drop_duplicates('query').set_index('query')['page']
    q['top_page_a'] = q['query'].map(top)
    return q


def drops(q, comparable, click_floor, impr_floor):
    """Keywords whose clicks fell. Where neither period reached click_floor clicks and impressions can be compared,
    a keyword whose impressions fell by IMPR_DROP or more also counts (basis 'impressions')."""
    rows = []
    for r in q.itertuples():
        low = max(r.clicks_a, r.clicks_b) < click_floor
        if r.clicks_b < r.clicks_a:
            rows.append((r, 'Clicks (low numbers)' if low else 'Clicks'))
        elif low and comparable and r.impr_a >= impr_floor and r.impr_b <= r.impr_a * (1 - IMPR_DROP):
            rows.append((r, 'Impressions (clicks too low)'))
    out = pd.DataFrame([{'query': r.query, 'basis': basis, 'clicks_a': r.clicks_a, 'clicks_b': r.clicks_b,
                         'change': r.change, 'impr_a': r.impr_a, 'impr_b': r.impr_b, 'pos_a': r.pos_a, 'pos_b': r.pos_b,
                         'top_page_a': r.top_page_a} for r, basis in rows])
    if out.empty:
        return out
    out['_i'] = out['basis'].str.startswith('Impr').astype(int)
    out['_d'] = out['impr_b'] - out['impr_a']
    return out.sort_values(['_i', 'change', '_d', 'query']).drop(columns=['_i', '_d']).reset_index(drop=True)


def service_matcher(service_terms):
    """query -> service name or '' (longest matching term wins), the same rule as the gap service terms."""
    services = []
    for e in service_terms or []:
        if isinstance(e, dict) and e.get('service'):
            services.append((e['service'].strip(), [t.strip().lower() for t in [e['service']] + list(e.get('terms', []))
                                                    if t.strip()]))
        elif isinstance(e, str) and e.strip():
            services.append((e.strip(), [e.strip().lower()]))
    pats = sorted(((n, t, term_re(t)) for n, ts in services for t in ts), key=lambda x: -len(x[1]))
    return [n for n, _ in services], (lambda q: next((n for n, t, rx in pats if rx.search(q)), ''))


def service_rows(q, service_terms, comparable):
    """Per service: non-brand GSC clicks and impressions in each period and the average position in period B."""
    names, match = service_matcher(service_terms)
    if not names:
        return [], names
    q = q.assign(service=q['query'].map(match))
    out = []
    for n in names:
        s = q[q['service'] == n]
        pi = s['impr_b'].where(s['pos_b'].notna(), 0)
        pos = float((s['pos_b'].fillna(0) * pi).sum() / pi.sum()) if pi.sum() > 0 else None
        out.append([n, int(s['clicks_a'].sum()), int(s['clicks_b'].sum()), int(s['clicks_b'].sum() - s['clicks_a'].sum()),
                    int(s['impr_a'].sum()) if comparable else '', int(s['impr_b'].sum()) if comparable else '',
                    '' if pos is None or not comparable else round(pos, 1), len(s)])
    out.sort(key=lambda r: (r[3], -r[2]))
    return out, names


# ------------------------------------------------------------------ signals

def pct(x):
    return f'{x:.0%}'


def share(n, d):
    return n / d if d else 0.0


def score_gsc(S, G, other_pages, service_terms, click_floor, impr_floor):
    """Add the GSC signals to S. G has df, a, b, prof (profile), q (query table). other_pages = crawl keys of indexable
    non-archive pages. Signals that need impressions are Not scored when impressions are not comparable."""
    prof, a, b, q = G['prof'], G['a'], G['b'], G['q']
    comp = prof['comparable']
    why = 'Impressions are not comparable between the periods (see Search Console tab)'
    out = {}

    # --- A7: indexable pages with no impressions in period B
    have = set(b.loc[b['impr'] > 0, 'page'])
    zero = [p for p in other_pages if p not in have]
    z_share = share(len(zero), len(other_pages))
    if comp and len(other_pages):
        S.add('Architecture', 'A7', 'Indexable non-archive pages with no Search Console impressions in the last 6 months',
              f'{len(zero):,} of {len(other_pages):,} ({pct(z_share)})', f'{pct(ZERO_IMPR_SHARE)} = 1 point',
              int(z_share >= ZERO_IMPR_SHARE), 1)
        S.data(no_impressions=len(zero), pages=len(other_pages), share=z_share)
    else:
        S.add('Architecture', 'A7', 'Indexable non-archive pages with no Search Console impressions in the last 6 months',
              'not scored', f'{pct(ZERO_IMPR_SHARE)} = 1 point', None, 1, why)
    out['a7_scored'] = bool(comp and len(other_pages))
    out['zero_pages'] = zero

    # --- A8: archive pages' share of non-brand impressions in period B
    arch_re = G['archive_re']
    nb = b[~b['brand']]
    is_arch = nb['page'].map(lambda u: bool(arch_re.search(re.sub(r'^https://[^/]+', '', u) or '/')))
    arch_i, tot_i = float(nb.loc[is_arch, 'impr'].sum()), float(nb['impr'].sum())
    if comp and tot_i > 0:
        S.add('Architecture', 'A8', 'Archive and listing pages as a share of non-brand Search Console impressions (last 6 months)',
              f'{arch_i:,.0f} of {tot_i:,.0f} ({pct(share(arch_i, tot_i))})', f'{pct(ARCHIVE_IMPR_SHARE)} = 1 point',
              int(share(arch_i, tot_i) >= ARCHIVE_IMPR_SHARE), 1)
        S.data(archive_impressions=arch_i, impressions=tot_i, share=share(arch_i, tot_i))
    else:
        S.add('Architecture', 'A8', 'Archive and listing pages as a share of non-brand Search Console impressions',
              'not scored', f'{pct(ARCHIVE_IMPR_SHARE)} = 1 point', None, 1, why)

    # --- A9: searches where 2+ URLs compete
    comp_rows = []
    if comp:
        per = nb.groupby(['query', 'page'], as_index=False)['impr'].sum()
        tot = per.groupby('query')['impr'].sum()
        real = tot[tot >= MIN_QUERY_IMPR].index
        multi = per[(per['impr'] >= MIN_PAGE_IMPR) & per['query'].isin(real)].groupby('query').size()
        competing = multi[multi >= 2].index
        c_share = share(len(competing), len(real))
        for qq in competing:
            sub = per[(per['query'] == qq) & (per['impr'] >= MIN_PAGE_IMPR)].sort_values('impr', ascending=False)
            comp_rows.append([qq, int(tot[qq]), len(sub), ', '.join(sub['page'].head(4))])
        comp_rows.sort(key=lambda r: -r[1])
        if len(real):
            S.add('Architecture', 'A9', 'Searches where 2+ of the site\'s URLs each get impressions (non-brand, last 6 months)',
                  f'{len(competing):,} of {len(real):,} ({pct(c_share)})', f'{pct(COMPETING_SHARE)} = 1 point',
                  int(c_share >= COMPETING_SHARE), 1,
                  f'Searches with {MIN_QUERY_IMPR}+ impressions; a URL competes with {MIN_PAGE_IMPR}+ on that search.')
            S.data(competing=len(competing), searches=len(real), share=c_share)
        else:
            S.add('Architecture', 'A9', 'Searches where 2+ of the site\'s URLs each get impressions', 'no searches with enough '
                  'impressions', '', None, 1, 'Too little data')
    else:
        S.add('Architecture', 'A9', 'Searches where 2+ of the site\'s URLs each get impressions (non-brand, last 6 months)',
              'not scored', f'{pct(COMPETING_SHARE)} = 1 point', None, 1, why)
    out['competing_rows'] = comp_rows

    # --- C5: non-brand traffic change
    ca, cb = float(q['clicks_a'].sum()), float(q['clicks_b'].sum())
    ia, ib = float(q['impr_a'].sum()), float(q['impr_b'].sum())
    if ca >= TREND_MIN_CLICKS:
        change = (cb - ca) / ca
        S.add('Content', 'C5', 'Non-brand Search Console clicks: last 6 months vs the 6 months before',
              f'{ca:,.0f} to {cb:,.0f} ({change:+.0%})', f'down {pct(TREND_DROP)} or more = 1 point', int(change <= -TREND_DROP),
              1, 'Clicks and impressions from Search Console.')
        S.data(clicks_a=ca, clicks_b=cb, change=change, basis='clicks')
    elif comp and ia >= impr_floor:
        change = (ib - ia) / ia
        S.add('Content', 'C5', 'Non-brand Search Console impressions: last 6 months vs the 6 months before (clicks too low)',
              f'{ia:,.0f} to {ib:,.0f} ({change:+.0%})', f'down {pct(TREND_DROP)} or more = 1 point',
              int(change <= -TREND_DROP), 1, f'Clicks in period A were under {TREND_MIN_CLICKS}, so impressions were used.')
        S.data(impressions_a=ia, impressions_b=ib, change=change, basis='impressions')
    else:
        S.add('Content', 'C5', 'Non-brand Search Console traffic: last 6 months vs the 6 months before', 'not scored',
              f'down {pct(TREND_DROP)} or more = 1 point', None, 1,
              f'Fewer than {TREND_MIN_CLICKS} non-brand clicks in period A' + ('' if comp else ' and impressions are not comparable'))

    # --- C6: striking distance
    names, match = service_matcher(service_terms)
    strike_rows = []
    if comp and G['has_position']:
        qb = agg_query(nb)
        qb = qb[(qb['impr'] >= MIN_QUERY_IMPR) & qb['pos'].between(STRIKE_LOW, STRIKE_HIGH + 0.999)]
        if names:
            qb = qb[qb['query'].map(match) != '']
        for r in qb.sort_values('impr', ascending=False).itertuples():
            strike_rows.append([r.query, match(r.query) if names else '', int(r.impr), int(r.clicks), round(r.pos, 1)])
        scope = 'non-brand service searches' if names else 'non-brand searches (no service_terms)'
        S.add('Content', 'C6', f'{scope.capitalize()} at average position {STRIKE_LOW}-{STRIKE_HIGH} with real impressions',
              f'{len(strike_rows):,} searches', f'{STRIKE_MIN}+ = 1 point', int(len(strike_rows) >= STRIKE_MIN), 1,
              f'Searches with {MIN_QUERY_IMPR}+ impressions in the last 6 months.')
        S.data(searches=len(strike_rows), low=STRIKE_LOW, high=STRIKE_HIGH)
    else:
        S.add('Content', 'C6', 'Non-brand service searches at average position 8-20 with real impressions', 'not scored',
              f'{STRIKE_MIN}+ = 1 point', None, 1, why if not comp else 'The export has no Position column')
    out['strike_rows'] = strike_rows
    return out


def manual_action_signal(S, value):
    """value: 'yes', 'no' or anything else (unknown). Yes forces Authority & Trust to High in verdict()."""
    v = str(value or '').strip().lower()
    name = 'Manual action reported in Search Console (Security & Manual actions)'
    if v == 'yes':
        S.add('Authority', 'U5', name, 'Yes: a manual action is reported', 'any = Authority & Trust is High', 1, 1,
              'Checked by the person in Search Console')
        S.data(manual_action='yes')
        return 'yes'
    if v == 'no':
        S.add('Authority', 'U5', name, 'None found', 'any = Authority & Trust is High', 0, 1,
              'Checked by the person in Search Console')
        S.data(manual_action='no')
        return 'no'
    S.add('Authority', 'U5', name, 'not checked', 'any = Authority & Trust is High', None, 1,
          'Ask the person to check Search Console > Security & Manual actions')
    return 'unknown'
