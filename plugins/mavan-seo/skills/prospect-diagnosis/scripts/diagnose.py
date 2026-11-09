"""Prospect diagnosis: which of authority / trust, content or site architecture is the prospect's biggest issue.

Two commands:

  preflight  Check every input is present and the right kind. Writes work/preflight.md (READY / NOT READY).
  build      Read the inputs, score every signal in references/rules.md, and write the workbook:
             Read Me, Verdict, Signals, Architecture, Content, Authority, Ranking URLs Not Live.

Every number is a count, share, join or comparison done here. Search volume is the keyword tool's estimate
and is never added across keywords. Nothing is fetched from the live site.
"""
import argparse
import os
import re
import statistics
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from common import bare_domain, canon, load_json, norm_url, num, pick, read_table, resolve, save_json

# ------------------------------------------------------------------ thresholds (references/rules.md)
THIN_WORDS = 300
EMPTY_SHARE_FAIL = 0.20
MIN_LIVE = 10
REPEAT_MIN = 5            # a title or H1 shared by this many indexable pages or more is "repeated"
DEEP_DEPTH = 3            # crawl depth deeper than this is "deep"
QUALITY_SCORE = 30        # Semrush AS / Ahrefs DR at or above this is a quality referring domain
LOW_SCORE = 5             # at or below this is a low-score referring domain
RECENT_DAYS = 90
WIN_POS = 20             # a competitor at this position or better is winning the search
CO_LEAD_MARGIN = 0.10
GBP_MIN_COMPS = 3         # Google Business Profile: at least this many competitors with data
GBP_RATING_GAP = 0.3      # G1: prospect rating at least this many stars below the median competitor
GBP_REVIEW_SHARE = 0.5    # G2: prospect review count under this share of the median competitor
GBP_TOP = 3               # G3: local pack = positions 1-3
GBP_POOR_KEYWORDS = 2     # G3: outside the top 3 on at least this many of the priority keywords
GBP_CAT_MIN_COMPS = 2     # G4: a category counts as missing when this many competitors use it and the prospect does not
GBP_KEYWORDS = 3          # priority keywords the SEO checks
ROUND_ROWS = {1000, 5000, 10000, 20000, 25000, 30000, 50000, 100000}

ARCHIVE_PATTERNS = [
    r'/tags?/', r'/categor(y|ies)/', r'/authors?/', r'/archives?/', r'/page/\d+/?$', r'[?&](page|paged|p)=\d+',
    r'/\d{4}/(\d{1,2}/)?$', r'/feed/?$', r'\.(rss|atom)$',
]
COMMERCIAL_RE = re.compile(
    r'\b(near me|cost|costs|price|prices|pricing|cheap|affordable|best|top|clinic|clinics|doctor|doctors|'
    r'surgeon|surgeons|specialist|consultation|financing|book|appointment|before and after|reviews?)\b')

CRAWL_SPEC = {
    'url': (['URL', 'Address'], True),
    'status': (['HTTP Status Code', 'Status Code'], True),
    'title': (['Title', 'Title 1'], True),
    'h1': (['H1', 'H1-1'], True),
    'words': (['No. Content Words', 'Word Count'], True),
    'indexable': (['Indexable Status', 'Indexability', 'Indexable'], False),
    'depth': (['Crawl Depth'], False),
    'ctype': (['Content Type'], False),
}
RANKING_SPEC = {
    'keyword': (['Keyword'], True),
    'position': (['Position', 'Current position'], True),
    'url': (['URL', 'Current URL'], True),
    'volume': (['Search Volume', 'Volume'], True),
}
GAP_SPEC = {
    'keyword': (['Keyword'], True),
    'volume': (['Search Volume', 'Volume'], True),
    'intent': (['Intents', 'Keyword Intents', 'Intent'], False),
}
REFDOM_SPEC = {
    'domain': (['Domain', 'Referring domain'], True),
    'score': (['Domain ascore', 'Domain rating', 'DR', 'Authority Score'], True),
    'first_seen': (['First seen', 'First Seen'], False),
}
BLGAP_SPEC = {
    'domain': (['Domain', 'Referring domain'], True),
    'score': (['Domain ascore', 'Domain rating', 'DR'], True),
}

# Semrush keyword gap exports use "Volume", which Ahrefs also uses, so Semrush-only columns decide it.
SEMRUSH_SIGNALS = {'searchvolume', 'keyworddifficulty', 'trafficcost', 'competitivedensity', 'competitiondensity',
                   'trafficpercent', 'results', 'numberofresults', 'serpfeaturesbykeyword', 'keywordintents',
                   'previousposition'}
AHREFS_SIGNALS = {'kd', 'currentposition', 'currenturl', 'organictraffic', 'currentorganictraffic', 'parenttopic'}
DOMAIN_RE = re.compile(r'^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$')


# ------------------------------------------------------------------ reading

def read_any(path):
    if str(path).lower().endswith(('.xlsx', '.xls')):
        df = pd.read_excel(path, dtype=str, keep_default_na=False)
        df.columns = [str(c).strip() for c in df.columns]
    else:
        df = read_table(path)
    df.columns = [c.replace('(%)', ' percent').strip() for c in df.columns]
    return df.loc[:, [c for c in df.columns if c and not c.startswith('Unnamed')]]


def detect_tool(df):
    cols = {canon(c) for c in df.columns}
    s, a = len(cols & SEMRUSH_SIGNALS), len(cols & AHREFS_SIGNALS)
    if s == a:
        return None
    return 'semrush' if s > a else 'ahrefs'


def domain_columns(df, skip):
    out = {}
    for c in df.columns:
        low = c.lower()
        if c in skip or any(w in low for w in ('url', 'traffic', 'volume', 'difficulty', 'pages', 'ascore')):
            continue
        cand = bare_domain(re.sub(r'\s*[-:(]*\s*(position|pos\.?|rank|ranking)\)?\s*$', '', low).strip())
        if DOMAIN_RE.match(cand):
            out[cand] = c
    return out


def term_re(t):
    """Whole word or phrase, optional plural s / es."""
    return re.compile(r'(?<![a-z0-9])' + re.escape(t.lower()) + r'(e?s)?(?![a-z0-9])')


def parse_map(items):
    out = {}
    for it in items or []:
        k, v = it.split('=', 1)
        out[k.strip()] = v.strip().strip('"')
    return out


def path_of(url):
    return re.sub(r'^[a-z]+://[^/]+', '', str(url), flags=re.I) or '/'


def host_of(url):
    return bare_domain(url)


# ------------------------------------------------------------------ preflight

def cmd_preflight(a):
    os.makedirs(a.out, exist_ok=True)
    rows = []

    def add(level, item, detail):
        rows.append((level, item, detail))

    cfg = load_json(a.config, None)
    if cfg is not None and getattr(a, 'gbp', None):
        cfg['gbp'] = read_gbp_sheet(a.gbp)
    if cfg is None:
        add('FAIL', 'config.json', f'not found at {a.config}')
        cfg = {}
    for key, label in (('client', 'Prospect name'), ('domain', 'Prospect domain')):
        add('OK' if cfg.get(key) else 'FAIL', label, cfg.get(key) or 'missing from config.json')
    comps = [bare_domain(c) for c in cfg.get('competitors') or []]

    def load(path, item, spec):
        if not path:
            add('FAIL', item, 'not provided')
            return None
        if not os.path.exists(path):
            add('FAIL', item, f'file not found: {path}')
            return None
        df = read_any(path)
        missing = [f for f, (al, req) in spec.items() if req and not pick(df, al)]
        if missing:
            add('FAIL', item, f'missing required columns {missing}; columns are {list(df.columns)}')
            return None
        return df

    crawl = load(a.crawl, 'Crawl URL export', CRAWL_SPEC)
    if crawl is not None:
        add('OK', 'Crawl URL export', f'{len(crawl):,} rows')
        if not pick(crawl, CRAWL_SPEC['indexable'][0]):
            add('WARN', 'Crawl indexability column', 'not found: every 200 page is treated as indexable')
        if not pick(crawl, CRAWL_SPEC['depth'][0]):
            add('WARN', 'Crawl depth column', 'not found: the deep pages signal is not scored')
    rank = load(a.ranking, 'Ranking keywords export', RANKING_SPEC)
    if rank is not None:
        tool = a.tool or detect_tool(rank)
        add('OK' if tool else 'FAIL', 'Ranking keywords export',
            f'{tool.capitalize()}, {len(rank):,} rows' if tool else 'cannot tell Semrush from Ahrefs: re-run with --tool')
    gap = load(a.gap, 'Keyword gap export', GAP_SPEC)
    if gap is not None:
        tool = a.tool or detect_tool(gap)
        doms = domain_columns(gap, set())
        source = 'config.json'
        if not comps:
            comps = [d for d in doms if d != bare_domain(cfg.get('domain', ''))]
            source = 'the keyword gap export'
        add('OK' if 2 <= len(comps) <= 4 else 'FAIL', 'Competitors (2-4)',
            f'{", ".join(comps)} (from {source})' if comps else 'none found in the keyword gap export')
        need = [bare_domain(cfg.get('domain', ''))] + comps
        miss = [d for d in need if d and d not in doms]
        if not tool:
            add('FAIL', 'Keyword gap export', 'cannot tell Semrush from Ahrefs: re-run with --tool')
        elif miss:
            add('FAIL', 'Keyword gap export', f'no position column for {miss}; domain columns found: {sorted(doms)}')
        else:
            add('OK', 'Keyword gap export', f'{tool.capitalize()}, {len(gap):,} rows, domains: {", ".join(sorted(doms))}')

    ov = cfg.get('overview') or {}
    need = [bare_domain(cfg.get('domain', ''))] + comps
    have = [d for d in need if d in {bare_domain(k) for k in ov}]
    if len(have) == len(need) and need[0]:
        add('OK', 'Authority overview (config)', f'{len(have)} domains')
    else:
        add('WARN', 'Authority overview (config)',
            f'missing for {[d for d in need if d not in have]}: authority score and referring domain signals are not scored')
    gp = gbp_problems(cfg)
    if not gp:
        add('OK', 'Google Business Profile (sheet)', f'prospect and {len(cfg["gbp"]["competitors"])} competitors')
    else:
        add('WARN', 'Google Business Profile (sheet)',
            '; '.join(gp) + ': the GBP findings are not assessed')
    for path, item, spec in ((a.refdomains, 'Referring domains export (optional)', REFDOM_SPEC),
                             (a.backlink_gap, 'Backlink gap export (optional)', BLGAP_SPEC)):
        if path:
            df = load(path, item, spec)
            if df is not None:
                add('OK', item, f'{len(df):,} rows')
        else:
            add('WARN', item, 'not provided: the signals that need it are not scored')

    ready = not any(r[0] == 'FAIL' for r in rows)
    lines = ['# Preflight', '', '| Result | Item | Detail |', '| --- | --- | --- |']
    lines += [f'| {r[0]} | {r[1]} | {r[2]} |' for r in rows]
    lines += ['', 'READY' if ready else 'NOT READY']
    text = '\n'.join(lines) + '\n'
    open(os.path.join(a.out, 'preflight.md'), 'w').write(text)
    print(text)
    sys.exit(0 if ready else 2)


# ------------------------------------------------------------------ loading for build

def load_crawl(path, ov):
    df = read_any(path)
    m = resolve(df, CRAWL_SPEC, 'crawl', ov)
    if m['ctype']:
        df = df[df[m['ctype']].str.contains('html', case=False, na=False) | (df[m['ctype']] == '')]
    c = pd.DataFrame({
        'url': df[m['url']].str.strip(),
        'status': df[m['status']].map(num),
        'title': df[m['title']].fillna('').str.strip(),
        'h1': df[m['h1']].fillna('').str.strip(),
        'words': df[m['words']].map(num).fillna(0),
        'indexable': (df[m['indexable']].str.strip().str.lower() == 'indexable') if m['indexable'] else True,
        'depth': df[m['depth']].map(num) if m['depth'] else float('nan'),
    })
    c = c[c['url'] != '']
    for col in ('title', 'h1'):
        c.loc[c[col].isin(['--', '-']), col] = ''
    c['norm'] = c['url'].map(norm_url)
    c['host'] = c['url'].map(host_of)
    return c, bool(m['depth'])


def classify(c, extra_patterns):
    pats = [re.compile(p, re.I) for p in ARCHIVE_PATTERNS + list(extra_patterns or [])]
    c['archive'] = c['url'].map(lambda u: any(p.search(path_of(u)) for p in pats))
    return c


def load_ranking(path, ov, tool):
    df = read_any(path)
    tool = tool or detect_tool(df)
    m = resolve(df, RANKING_SPEC, 'ranking', ov)
    r = pd.DataFrame({'keyword': df[m['keyword']].str.strip(), 'position': df[m['position']].map(num),
                      'url': df[m['url']].str.strip(), 'est_volume': df[m['volume']].map(num)})
    r = r[(r['keyword'] != '') & (r['url'] != '')]
    r['norm'] = r['url'].map(norm_url)
    r['host'] = r['url'].map(host_of)
    return r, tool, len(df)


def load_gap(path, ov, tool, prospect, comps, exclude_terms):
    df = read_any(path)
    tool = tool or detect_tool(df)
    m = resolve(df, GAP_SPEC, 'gap', ov)
    doms = domain_columns(df, {c for c in m.values() if c})
    for k, v in ov.items():
        if k.startswith('gapcol.'):
            doms[bare_domain(k[7:])] = v
    for d in [prospect] + comps:
        if d not in doms:
            raise SystemExit(f'Keyword gap export has no position column for {d}. Domain columns: {sorted(doms)}. '
                             f'Pass --map "gapcol.{d}=Column name".')
    g = pd.DataFrame({'keyword': df[m['keyword']].str.strip(), 'est_volume': df[m['volume']].map(num),
                      'intent': df[m['intent']].fillna('') if m['intent'] else ''})
    for d in [prospect] + comps:
        p = df[doms[d]].map(num)
        g[d] = p.where(p > 0)
    g = g[g['keyword'] != '']
    ex = [canon(t) for t in exclude_terms if canon(t)]
    g['excluded'] = g['keyword'].map(lambda k: any(t in canon(k) for t in ex)) if ex else False
    if m['intent']:
        g['commercial'] = g['intent'].str.contains('commercial|transactional', case=False)
        intent_source = f'the "{m["intent"]}" column (Commercial or Transactional)'
    else:
        g['commercial'] = g['keyword'].str.lower().str.contains(COMMERCIAL_RE)
        intent_source = 'buying words in the keyword (near me, cost, best, surgeon and so on)'
    return g, tool, intent_source


def load_scored_domains(path, spec, label, ov):
    df = read_any(path)
    m = resolve(df, spec, label, ov)
    out = pd.DataFrame({'domain': df[m['domain']].map(bare_domain), 'score': df[m['score']].map(num)})
    if m.get('first_seen'):
        out['first_seen'] = pd.to_datetime(df[m['first_seen']], errors='coerce')
    return out, df


# ------------------------------------------------------------------ Google Business Profile
# Typed in config.json by the SEO. Findings are listed with a priority; they do not add points to any lens.

def _cat_key(x):
    return re.sub(r'\s+', ' ', str(x).strip().lower())


def _pos(v):
    """Local position as a number, or None when the business did not show (blank, null, 'none')."""
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def read_gbp_sheet(path):
    """Reads the GBP template (tabs 'Keywords' and 'GBP') into the structure score_gbp uses."""
    if not path or not os.path.exists(path):
        return None
    x = pd.read_excel(path, sheet_name=None, dtype=str, keep_default_na=False)
    kw = []
    if 'Keywords' in x:
        kw = [k.strip() for k in x['Keywords'].iloc[:, 0].tolist() if k.strip()]
    df = x.get('GBP')
    if df is None:
        return {'prospect': {}, 'competitors': [], 'sheet_error': 'no GBP tab'}
    df.columns = [str(c).strip() for c in df.columns]
    pos_cols = [c for c in df.columns if c.lower().startswith('position')]

    def cell(row, name):
        return str(row.get(name, '')).strip()

    def split(v):
        return [t.strip() for t in re.split(r'[;\n]', v) if t.strip()]

    out = {'prospect': {}, 'competitors': []}
    for _, row in df.iterrows():
        if not cell(row, 'Business'):
            continue
        e = {'name': cell(row, 'Business'), 'rating': cell(row, 'Rating'), 'reviews': cell(row, 'Number of reviews').replace(',', ''),
             'categories': split(cell(row, 'Categories')),
             'rankings': {kw[i] if i < len(kw) else f'keyword {i + 1}': cell(row, c) for i, c in enumerate(pos_cols)},
             'photos': cell(row, 'Photos (optional)'), 'linked_page': cell(row, 'Linked page (optional)'),
             'attributes': split(cell(row, 'Attributes (optional)')), 'services': split(cell(row, 'Services listed (optional)'))}
        role = cell(row, 'Role').lower()
        if role == 'prospect':
            out['prospect'] = e
        elif role == 'competitor':
            out['competitors'].append(e)
        else:
            out.setdefault('role_errors', []).append(e['name'])
    if len(kw) != GBP_KEYWORDS:
        out['sheet_error'] = f'the Keywords tab needs exactly {GBP_KEYWORDS} priority keywords, found {len(kw)}'
    return out


def gbp_problems(cfg):
    """What is missing or wrong in config.json 'gbp'. Empty list = ready to assess."""
    g = cfg.get('gbp')
    if not g:
        return ['no GBP sheet provided']
    out = []
    if g.get('sheet_error'):
        out.append(g['sheet_error'])
    for n in g.get('role_errors') or []:
        out.append(f'"{n}": Role must be Prospect or Competitor')
    if not g.get('prospect'):
        out.append('no row with Role = Prospect')
        return out
    ents = [('the prospect', g.get('prospect') or {})] + \
           [(f'competitor "{c.get("name", i + 1)}"', c) for i, c in enumerate(g.get('competitors') or [])]
    if len(g.get('competitors') or []) < GBP_MIN_COMPS:
        out.append(f'need at least {GBP_MIN_COMPS} competitors, found {len(g.get("competitors") or [])}')
    kws = None
    for label, e in ents:
        try:
            r = float(e.get('rating'))
            if not 1 <= r <= 5:
                raise ValueError
        except (TypeError, ValueError):
            out.append(f'{label}: rating missing or not between 1 and 5')
        try:
            if float(e.get('reviews')) < 0:
                raise ValueError
        except (TypeError, ValueError):
            out.append(f'{label}: review count missing')
        if not [x for x in e.get('categories') or [] if str(x).strip()]:
            out.append(f'{label}: no categories')
        rk = e.get('rankings') or {}
        if len(rk) != GBP_KEYWORDS:
            out.append(f'{label}: rankings needed for exactly {GBP_KEYWORDS} priority keywords, found {len(rk)}')
        elif kws is None:
            kws = {_cat_key(k) for k in rk}
        elif {_cat_key(k) for k in rk} != kws:
            out.append(f'{label}: rankings must use the same {GBP_KEYWORDS} keywords as the prospect')
    return out


def score_gbp(cfg):
    """Returns None when the data is missing or invalid (reason in 'problems'), else the findings."""
    problems = gbp_problems(cfg)
    if problems:
        return {'assessed': False, 'problems': problems}
    g = cfg['gbp']
    pr, comps = g['prospect'], g['competitors']
    f = []

    def finding(fid, name, priority, hit, value, detail):
        f.append({'id': fid, 'name': name, 'priority': priority, 'found': hit, 'value': value, 'detail': detail})

    med_rating = float(statistics.median([float(c['rating']) for c in comps]))
    gap = round(med_rating - float(pr['rating']), 2)
    finding('G1', 'Low review rating', 'High', gap >= GBP_RATING_GAP - 1e-9,
            f'prospect {float(pr["rating"]):.1f} vs median competitor {med_rating:.1f}',
            f'Flagged when the prospect is {GBP_RATING_GAP} stars or more below the median competitor.')
    med_rev = float(statistics.median([float(c['reviews']) for c in comps]))
    finding('G2', 'Low number of reviews', 'High', float(pr['reviews']) < GBP_REVIEW_SHARE * med_rev,
            f'prospect {int(float(pr["reviews"])):,} vs median competitor {med_rev:,.0f}',
            f'Flagged when the prospect has under {pct(GBP_REVIEW_SHARE)} of the median competitor\'s reviews.')
    kws = {_cat_key(k): k for k in pr['rankings']}
    outside = [kws[_cat_key(k)] for k, v in pr['rankings'].items() if _pos(v) is None or _pos(v) > GBP_TOP]
    finding('G3', 'Poor local ranking on priority keywords', 'High', len(outside) >= GBP_POOR_KEYWORDS,
            f'outside the top {GBP_TOP} on {len(outside)} of {GBP_KEYWORDS}: ' + (', '.join(outside) or 'none'),
            f'Flagged when the prospect is outside the top {GBP_TOP} (or not shown) on {GBP_POOR_KEYWORDS} or more of the '
            f'{GBP_KEYWORDS} priority keywords.')
    have = {_cat_key(x) for x in pr['categories']}
    use = {}
    for c in comps:
        for x in {_cat_key(x): x for x in c['categories'] if str(x).strip()}.items():
            use.setdefault(x[0], [x[1], 0])[1] += 1
    missing = sorted([(v[0], v[1]) for k, v in use.items() if k not in have and v[1] >= GBP_CAT_MIN_COMPS],
                     key=lambda t: (-t[1], t[0]))
    finding('G4', 'Missing GBP categories competitors use', 'Medium', bool(missing),
            ', '.join(f'{n} ({k} of {len(comps)})' for n, k in missing) or 'none',
            f'A category counts as missing when {GBP_CAT_MIN_COMPS}+ competitors use it and the prospect does not.')
    return {'assessed': True, 'findings': f, 'prospect': pr, 'competitors': comps,
            'median_rating': med_rating, 'median_reviews': med_rev, 'missing_categories': missing}


# ------------------------------------------------------------------ signals

class Signals:
    def __init__(self):
        self.rows = []

    def add(self, lens, sid, name, value, threshold, points, possible, note=''):
        """points None = not scored (input missing)."""
        self.rows.append({'lens': lens, 'id': sid, 'name': name, 'value': value, 'threshold': threshold,
                          'points': points, 'possible': possible, 'note': note, 'data': {}})

    def data(self, **kw):
        """Structured numbers for the last signal, written to diagnosis.json for the sales report."""
        self.rows[-1]['data'] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in kw.items()}


def pct(x):
    return f'{x:.0%}'


def share(n, d):
    return n / d if d else 0.0


def score_architecture(S, c, has_depth, r):
    live = c[c['status'] == 200]
    idx = live[live['indexable']]
    arch = idx[idx['archive']]
    a_share = share(len(arch), len(idx))
    pts = 2 if a_share >= 0.50 else (1 if a_share >= 0.25 else 0)
    S.add('Architecture', 'A1', 'Archive and listing pages (tags, categories, dates, paged lists) as a share of indexable pages',
          f'{len(arch):,} of {len(idx):,} ({pct(a_share)})', '25% = 1 point, 50% = 2 points', pts, 2)
    S.data(archive=len(arch), indexable=len(idx), share=a_share)

    other = idx[~idx['archive']]
    counts = {}
    for col in ('title', 'h1'):
        vc = other[other[col] != ''][col].value_counts()
        counts[col] = set(vc[vc >= REPEAT_MIN].index)
    rep = other[other['title'].isin(counts['title']) | other['h1'].isin(counts['h1'])]
    r_share = share(len(rep), len(other))
    S.add('Architecture', 'A2', f'Non-archive indexable pages whose title or H1 is shared with {REPEAT_MIN - 1}+ other pages',
          f'{len(rep):,} of {len(other):,} ({pct(r_share)})', '20% = 1 point', int(r_share >= 0.20), 1)
    S.data(repeated=len(rep), pages=len(other), share=r_share)

    ranked = set(r['norm']) if r is not None else set()
    no_kw = other[~other['norm'].isin(ranked)]
    n_share = share(len(no_kw), len(other))
    if len(other) >= 200:
        S.add('Architecture', 'A3', 'Non-archive indexable pages with no tracked keywords',
              f'{len(no_kw):,} of {len(other):,} ({pct(n_share)})', '80% = 1 point (sites with 200+ such pages)',
              int(n_share >= 0.80), 1)
        S.data(no_keywords=len(no_kw), pages=len(other), share=n_share)
    else:
        S.add('Architecture', 'A3', 'Non-archive indexable pages with no tracked keywords',
              f'{len(no_kw):,} of {len(other):,} ({pct(n_share)})', 'only scored with 200+ such pages', None, 1,
              'Site too small for this signal')

    redir = c[(c['status'] >= 300) & (c['status'] < 400)]
    d_share = share(len(redir), len(c))
    S.add('Architecture', 'A4', 'Redirecting URLs the crawler reached through internal links, as a share of crawled URLs',
          f'{len(redir):,} of {len(c):,} ({pct(d_share)})', '20% = 1 point', int(d_share >= 0.20), 1)
    S.data(redirects=len(redir), crawled=len(c), share=d_share)

    if has_depth:
        deep = idx[idx['depth'] > DEEP_DEPTH]
        p_share = share(len(deep), len(idx))
        S.add('Architecture', 'A5', f'Indexable pages deeper than {DEEP_DEPTH} clicks from the home page',
              f'{len(deep):,} of {len(idx):,} ({pct(p_share)})', '20% = 1 point', int(p_share >= 0.20), 1)
        S.data(deep=len(deep), indexable=len(idx), share=p_share, depth=DEEP_DEPTH)
    else:
        S.add('Architecture', 'A5', f'Indexable pages deeper than {DEEP_DEPTH} clicks', 'no crawl depth column', '20% = 1 point',
              None, 1, 'Not in the crawl export')

    nl_rows, nl_share, on_host = not_live(c, r)
    if r is not None:
        n_on = len(on_host)
        bad = sum(1 for x in nl_rows if x[1] != 'Other host (not crawled)')
        S.add('Architecture', 'A6', 'Ranking URLs on the crawled host that are not a live 200 page',
              f'{bad:,} of {n_on:,} ({pct(share(bad, n_on))})', '10% = 1 point', int(share(bad, n_on) >= 0.10), 1)
        S.data(not_live=bad, ranking_urls=n_on, share=share(bad, n_on))
    detail = {'live': len(live), 'indexable': len(idx), 'archive': len(arch), 'other': len(other),
              'repeated': rep, 'counts': counts, 'thin': other[other['words'] < THIN_WORDS], 'not_live': nl_rows,
              'redirects': len(redir), 'crawled': len(c), 'nonidx': len(live) - len(idx)}
    return detail


def not_live(c, r):
    """Ranking URLs vs crawl. The live 200 row wins when several crawl rows normalize to the same URL."""
    if r is None:
        return [], 0, []
    cc = c.assign(_o=(c['status'] != 200).astype(int)).sort_values('_o', kind='stable')
    st = cc.drop_duplicates('norm').set_index('norm')['status'].to_dict()
    hosts = set(c['host'])
    rows, on_host = [], []
    for norm, g in r.groupby('norm'):
        top = g.sort_values(['position']).iloc[0]
        host = top['host']
        if host not in hosts:
            rows.append([top['url'], 'Other host (not crawled)', len(g), top['keyword'], top['position'], top['est_volume']])
            continue
        on_host.append(norm)
        s = st.get(norm)
        if s is None:
            rows.append([top['url'], 'Not in crawl', len(g), top['keyword'], top['position'], top['est_volume']])
        elif s != 200:
            rows.append([top['url'], int(s), len(g), top['keyword'], top['position'], top['est_volume']])
    rows.sort(key=lambda x: (x[1] == 'Other host (not crawled)', -x[2]))
    return rows, 0, on_host


def score_content(S, g, prospect, comps, c_detail, intent_source, service_terms):
    base = g[~g['excluded']]
    ranked = {d: int(base[d].notna().sum()) for d in [prospect] + comps}
    top10 = {d: int((base[d] <= 10).sum()) for d in [prospect] + comps}
    best = max(comps, key=lambda d: ranked[d])
    ratio = ranked[best] / ranked[prospect] if ranked[prospect] else float('inf')
    pts = 2 if ratio >= 3 else (1 if ratio >= 2 else 0)
    S.add('Content', 'C1', 'Keywords in the gap export the top competitor ranks for, compared with the prospect',
          f'{best}: {ranked[best]:,} vs {ranked[prospect]:,} ({ratio:.1f}x)', '2x = 1 point, 3x = 2 points', pts, 2)
    S.data(competitor=best, competitor_keywords=ranked[best], prospect_keywords=ranked[prospect], ratio=float(ratio))

    services = []   # (service name, [terms]); an entry is "name" or {"service": name, "terms": [...]}
    for e in service_terms:
        if isinstance(e, dict) and e.get('service'):
            services.append((e['service'].strip(), [t.strip().lower() for t in [e['service']] + list(e.get('terms', []))
                                                     if t.strip()]))
        elif isinstance(e, str) and e.strip():
            services.append((e.strip(), [e.strip().lower()]))
    terms = [n for n, _ in services]
    if services:
        pats = sorted(((n, t, term_re(t)) for n, ts in services for t in ts), key=lambda x: -len(x[1]))
        base = base.assign(service=base['keyword'].str.lower().map(
            lambda k: next((n for n, t, rx in pats if rx.search(k)), '')))
        svc = base[base['service'] != '']
        scope = f'non-branded service keywords ({len(svc):,} keywords matching {len(terms)} services)'
    else:
        base = base.assign(service='')
        svc = base[base['commercial']]
        scope = f'non-branded buying searches ({len(svc):,}; no service_terms in config.json)'
    s10 = {d: int((svc[d] <= 10).sum()) for d in [prospect] + comps}
    med = statistics.median(s10[d] for d in comps)
    if len(svc):
        S.add('Content', 'C2', 'Top-10 rankings on non-branded service keywords: prospect vs the median competitor',
              f'{s10[prospect]:,} vs {med:,.0f}', 'prospect below the median = 1 point', int(s10[prospect] < med), 1,
              f'Scope: {scope}.')
        S.data(prospect_top10=s10[prospect], median_competitor_top10=float(med), keywords=len(svc),
               services=len(terms), by_service=bool(terms))
    else:
        S.add('Content', 'C2', 'Top-10 rankings on non-branded service keywords', 'no matching keywords in the gap export',
              '', None, 1, f'Scope: {scope}.')
    svc_rows = []
    for t in terms:
        k = svc[svc['service'] == t]
        if k.empty:
            svc_rows.append([t, 0, '', '', '', '', '', '', 'No tracked keywords'])
            continue
        top = {d: int((k[d] <= 10).sum()) for d in comps}
        bc = max(comps, key=lambda d: (top[d], -(k[d].min() if k[d].notna().any() else 999)))
        lost = k[(k[comps] <= 10).any(axis=1) & ~(k[prospect] <= WIN_POS)]
        pbest = k[prospect].min()
        cbest = k[bc].min()
        no_comp = pd.isna(cbest)
        svc_rows.append([t, len(k), int((k[prospect] <= 10).sum()), '' if pd.isna(pbest) else int(pbest),
                         '' if no_comp else bc, '' if no_comp else top[bc], '' if no_comp else int(cbest), len(lost),
                         'No competitor ranks' if no_comp else ''])
    svc_rows.sort(key=lambda r: (r[8] == 'No tracked keywords', -(r[7] or 0), -(r[1] or 0)))

    gap = base[base[prospect].isna() & base[comps].notna().any(axis=1)]
    won = gap[(gap[comps] <= WIN_POS).any(axis=1)]
    com = won[won['commercial']]
    c_share = share(len(com), len(won))
    S.add('Content', 'C3', f'Gap keywords a competitor ranks top {WIN_POS} for (prospect absent) that are buying searches',
          f'{len(com):,} of {len(won):,} ({pct(c_share)})', '30% = 1 point', int(c_share >= 0.30), 1,
          f'Buying searches from {intent_source}. Competitor and brand searches left out.')
    S.data(buying=len(com), competitor_won=len(won), share=c_share, win_position=WIN_POS)

    thin = c_detail['thin']
    t_share = share(len(thin), c_detail['other'])
    S.add('Content', 'C4', f'Non-archive indexable pages under {THIN_WORDS} content words',
          f'{len(thin):,} of {c_detail["other"]:,} ({pct(t_share)})', '15% = 1 point', int(t_share >= 0.15), 1)
    S.data(thin=len(thin), pages=c_detail['other'], share=t_share, words=THIN_WORDS)
    return {'ranked': ranked, 'top10': top10, 's10': s10, 'svc_rows': svc_rows, 'svc_scope': scope,
            'gap': gap, 'won': won, 'commercial': com, 'excluded': int(g['excluded'].sum()),
            'total': len(g)}


def score_authority(S, cfg, prospect, comps, refd, blgap):
    ov = {bare_domain(k): v for k, v in (cfg.get('overview') or {}).items()}
    have = all(d in ov for d in [prospect] + comps)
    det = {'overview': ov if have else {}, 'refd': refd, 'blgap': blgap}

    if have and all('authority_score' in ov[d] for d in [prospect] + comps):
        med = statistics.median(num(ov[d]['authority_score']) for d in comps)
        diff = med - num(ov[prospect]['authority_score'])
        pts = 2 if diff >= 10 else (1 if diff >= 5 else 0)
        S.add('Authority', 'U1', 'Authority score: median competitor minus prospect',
              f'{med:g} - {num(ov[prospect]["authority_score"]):g} = {diff:g}', '5 = 1 point, 10 = 2 points', pts, 2)
        S.data(prospect=num(ov[prospect]['authority_score']), median_competitor=float(med), gap=float(diff))
    else:
        S.add('Authority', 'U1', 'Authority score: median competitor minus prospect', 'no overview figures', '', None, 2,
              'Add "overview" to config.json')

    if have and all('referring_domains' in ov[d] for d in [prospect] + comps):
        med = statistics.median(num(ov[d]['referring_domains']) for d in comps)
        mine = num(ov[prospect]['referring_domains'])
        S.add('Authority', 'U2', 'Referring domains: prospect as a share of the median competitor',
              f'{mine:,.0f} vs {med:,.0f} ({pct(share(mine, med))})', 'under 50% = 1 point', int(share(mine, med) < 0.5), 1)
        S.data(prospect=mine, median_competitor=float(med), share=share(mine, med))
    else:
        S.add('Authority', 'U2', 'Referring domains vs the median competitor', 'no overview figures', '', None, 1,
              'Add "overview" to config.json')

    if refd is not None and blgap is not None:
        own_q = int((refd['score'] >= QUALITY_SCORE).sum())
        gap_q = int((blgap['score'] >= QUALITY_SCORE).sum())
        S.add('Authority', 'U3', f'Domains scoring {QUALITY_SCORE}+ that link to competitors and not the prospect, vs the '
              f'prospect\'s own {QUALITY_SCORE}+ domains', f'{gap_q:,} vs {own_q:,}', 'more in the gap = 1 point',
              int(gap_q > own_q), 1)
        S.data(gap_quality=gap_q, own_quality=own_q, score=QUALITY_SCORE)
    else:
        S.add('Authority', 'U3', f'Quality ({QUALITY_SCORE}+) link gap', 'needs the referring domains and backlink gap exports',
              '', None, 1, 'Optional exports not attached')

    growth_pt, notes, evaluated = 0, [], False
    g_mine = g_med = recent_n = None
    if have and all('referring_domains_12m_ago' in ov[d] and 'referring_domains' in ov[d] for d in [prospect] + comps):
        evaluated = True

        def gr(d):
            then = num(ov[d]['referring_domains_12m_ago'])
            return num(ov[d]['referring_domains']) / then if then else float('nan')
        mine, med = gr(prospect), statistics.median(gr(d) for d in comps)
        fast = mine >= 2 * med
        g_mine, g_med = mine, med
        notes.append(f'12-month growth {mine:.1f}x vs median competitor {med:.1f}x')
    else:
        fast = None
    recent_share = None
    if refd is not None and 'first_seen' in refd and refd['first_seen'].notna().any():
        evaluated = True
        ref_date = pd.to_datetime(cfg.get('reference_date')) if cfg.get('reference_date') else refd['first_seen'].max()
        recent = refd[refd['first_seen'] >= ref_date - pd.Timedelta(days=RECENT_DAYS)]
        recent_share = share(len(recent), len(refd))
        recent_n = len(recent)
        notes.append(f'{len(recent):,} of {len(refd):,} referring domains ({pct(recent_share)}) first seen in the '
                     f'{RECENT_DAYS} days to {ref_date.date()}')
    if evaluated:
        checks = [x for x in (fast, None if recent_share is None else recent_share >= 0.5) if x is not None]
        growth_pt = int(all(checks))
        S.add('Authority', 'U4', 'Unusual link growth (trust risk)', '; '.join(notes),
              'growth 2x the median competitor; 50%+ first seen in the last 90 days (each available check must hold) = 1 point',
              growth_pt, 1,
              'A risk to check in Search Console > Manual actions, not a reason to disavow')
        S.data(growth=g_mine, median_competitor_growth=g_med, recent=recent_n,
               referring_domains=None if refd is None else len(refd), recent_share=recent_share, days=RECENT_DAYS)
    else:
        S.add('Authority', 'U4', 'Unusual link growth (trust risk)', 'needs overview growth figures or the referring domains export',
              '', None, 1, 'Not enough data')
    if refd is not None:
        det['low'] = int((refd['score'] <= LOW_SCORE).sum())
        det['quality'] = int((refd['score'] >= QUALITY_SCORE).sum())
    return det


def verdict(S):
    out = []
    for lens in ('Authority', 'Content', 'Architecture'):
        rows = [r for r in S.rows if r['lens'] == lens and r['points'] is not None]
        pts = sum(r['points'] for r in rows)
        poss = sum(r['possible'] for r in rows)
        n = len(rows)
        if n < 2:
            out.append({'lens': lens, 'points': pts, 'possible': poss, 'share': None, 'severity': 'Not enough data',
                        'scored': n})
            continue
        s = pts / poss
        sev = 'High' if s >= 0.5 else ('Medium' if s >= 0.25 else 'Low')
        out.append({'lens': lens, 'points': pts, 'possible': poss, 'share': s, 'severity': sev, 'scored': n})
    scored = sorted([v for v in out if v['share'] is not None], key=lambda v: -v['share'])
    lead = []
    if scored and scored[0]['share'] > 0:
        lead = [v['lens'] for v in scored if scored[0]['share'] - v['share'] <= CO_LEAD_MARGIN and v['share'] > 0]
    return out, lead


# ------------------------------------------------------------------ workbook

HEAD = Font(bold=True, color='FFFFFF')
FILL = PatternFill('solid', fgColor='1F3A5F')
WRAP = Alignment(wrap_text=True, vertical='top')


def sheet(wb, name, header, rows, widths=None):
    ws = wb.create_sheet(name)
    ws.append(header)
    for cell in ws[1]:
        cell.font, cell.fill, cell.alignment = HEAD, FILL, WRAP
    for r in rows:
        ws.append(list(r))
    for i, h in enumerate(header, 1):
        w = (widths or {}).get(h) or min(60, max(12, len(str(h)) + 2))
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = WRAP
    ws.freeze_panes = 'A2'
    return ws


def cmd_build(a):
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    cfg = load_json(a.config, {})
    if a.gbp:
        cfg['gbp'] = read_gbp_sheet(a.gbp)
    prospect = bare_domain(cfg.get('domain', ''))
    ov = parse_map(a.map)
    comps = [bare_domain(x) for x in cfg.get('competitors', [])]
    if not prospect:
        raise SystemExit('config.json needs "domain".')
    if not comps:   # competitors come from the keyword gap export's domain columns unless config.json lists them
        gdf = read_any(a.gap)
        doms = domain_columns(gdf, {c for c in resolve(gdf, GAP_SPEC, 'gap', ov).values() if c})
        doms.update({bare_domain(k[7:]): v for k, v in ov.items() if k.startswith('gapcol.')})
        comps = [d for d in doms if d != prospect]
        print(f'  Competitors from the keyword gap export: {", ".join(comps)}')
    if not 2 <= len(comps) <= 4:
        raise SystemExit(f'Need 2-4 competitors; found {comps}. List them in config.json "competitors".')
    checks = []

    def check(name, ok, detail=''):
        checks.append(ok)
        print(f'{"PASS" if ok else "FAIL"} {name}' + (f': {detail}' if detail else ''))

    c, has_depth = load_crawl(a.crawl, ov)
    live = c[c['status'] == 200]
    empty = live[(live['title'] == '') & (live['h1'] == '') & (live['words'] == 0)]
    if len(live) < MIN_LIVE or share(len(empty), len(live)) >= EMPTY_SHARE_FAIL:
        print(f'FAIL crawl: {len(live)} pages return 200 and {len(empty)} of them have no title, no H1 and no words. '
              'The crawl did not render the pages: ask for a re-crawl.')
        sys.exit(2)
    c = classify(c, cfg.get('archive_patterns'))
    r, rtool, rrows = load_ranking(a.ranking, ov, a.tool)
    excl = [prospect.split('.')[0]] + [x.split('.')[0] for x in comps] + list(cfg.get('brand_terms', [])) + \
        list(cfg.get('exclude_terms', []))
    g, gtool, intent_source = load_gap(a.gap, ov, a.tool, prospect, comps, excl)
    tools = {t for t in (rtool, gtool) if t}
    print(f'  Tool: {", ".join(sorted(t.capitalize() for t in tools)) or "unknown (pass --tool)"}')
    notes = []
    if len(tools) > 1:
        notes.append('The ranking and gap exports come from different tools; their scales differ.')
    if rrows in ROUND_ROWS:
        notes.append(f'The ranking export has {rrows:,} rows, a round number: it may be capped.')

    refd = blgap = None
    if a.refdomains:
        refd, raw = load_scored_domains(a.refdomains, REFDOM_SPEC, 'refdomains', ov)
        if len(raw) in ROUND_ROWS:
            notes.append(f'The referring domains export has {len(raw):,} rows, a round number: it may be capped.')
    if a.backlink_gap:
        blgap, raw = load_scored_domains(a.backlink_gap, BLGAP_SPEC, 'backlink_gap', ov)
        doms = domain_columns(raw, set())
        if prospect in doms:
            pcol = raw[doms[prospect]].map(num).fillna(0)
            blgap = blgap[(pcol == 0).values]
            comp_cols = [doms[d] for d in comps if d in doms]
            blgap['competitors'] = raw.loc[(pcol == 0).values, comp_cols].apply(
                lambda row: ', '.join(d for d, col in zip([d for d in comps if d in doms], comp_cols) if num(row[col]) > 0),
                axis=1).values

    S = Signals()
    arch = score_architecture(S, c, has_depth, r)
    cont = score_content(S, g, prospect, comps, arch, intent_source, cfg.get('service_terms') or [])
    auth = score_authority(S, cfg, prospect, comps, refd, blgap)
    lenses, lead = verdict(S)
    gbp = score_gbp(cfg)

    # --- QA
    check('every signal has a lens and an id', all(x['lens'] and x['id'] for x in S.rows))
    check('points never exceed possible', all(x['points'] is None or 0 <= x['points'] <= x['possible'] for x in S.rows))
    check('crawl rows reconcile', arch['live'] == arch['indexable'] + arch['nonidx'] and
          arch['indexable'] == arch['archive'] + arch['other'],
          f'{arch["live"]} live = {arch["archive"]} archive + {arch["other"]} other indexable + {arch["nonidx"]} not indexable')
    check('gap keywords reconcile', len(cont['gap']) <= cont['total'] - cont['excluded'],
          f'{len(cont["gap"])} gap keywords of {cont["total"]} rows ({cont["excluded"]} competitor or brand searches left out)')

    check('GBP findings are only made from complete data', gbp['assessed'] or not gbp.get('findings'))
    # --- workbook
    wb = Workbook()
    wb.remove(wb.active)
    tool_name = ' and '.join(sorted(t.capitalize() for t in tools)) or 'the keyword tool'
    lead_text = ' and '.join(lead) if lead else 'No lens stands out'
    readme = [
        ['Prospect', f'{cfg.get("client", "")} ({prospect})'],
        ['Competitors', ', '.join(comps)],
        ['Question', 'Which is the biggest underlying issue: authority / trust, content, or site architecture?'],
        ['Answer', f'{lead_text}. See the Verdict tab; every point comes from a signal on the Signals tab.'],
        ['How it is scored', 'Each signal adds points when its value passes the threshold shown. A lens\'s score is its points '
         'divided by the points possible from the signals that could be scored. High = 50%+, Medium = 25-49%, Low = under 25%. '
         'Lenses within 10 points of the top score are co-leads. A lens with fewer than 2 scored signals is "Not enough data".'],
        ['Inputs', f'Crawl URL export ({len(c):,} URLs), {tool_name} ranking keywords ({len(r):,} rows) and keyword gap '
         f'({cont["total"]:,} rows)' + (', referring domains export' if refd is not None else '') +
         (', backlink gap export' if blgap is not None else '') +
         (', authority overview figures typed in config.json' if auth['overview'] else '') + '.'],
        ['Keyword numbers', 'Search volumes are the keyword tool\'s estimates for each search, not visits, clicks or impressions, '
         'and are never added together. Rankings are a snapshot of tracked keywords (mostly the top 100).'],
        ['Google Business Profile', 'Typed in by the SEO on the GBP template, from the profiles themselves. Findings are on the Google Business Profile '
         'tab and carry their own priority (High / Medium). They do not add points to any lens and do not change which lens leads.'
         if gbp['assessed'] else 'Not assessed: ' + '; '.join(gbp['problems']) + '.'],
        ['Not checked', 'Nothing was fetched from the live site. Internal links between pages are not analysed (no link export '
         'is needed). Search Console data is not used.'],
    ] + [['Note', n] for n in notes]
    sheet(wb, 'Read Me', ['Item', 'Detail'], readme, {'Item': 18, 'Detail': 110})

    vrows = []
    for v in lenses:
        ev = [f'{x["id"]}: {x["name"]}: {x["value"]}' for x in S.rows if x['lens'] == v['lens'] and x['points']]
        vrows.append([v['lens'], v['severity'], '' if v['share'] is None else pct(v['share']), f'{v["points"]} of {v["possible"]}',
                      'Yes' if v['lens'] in lead else '', '\n'.join(ev) or 'No signal passed its threshold'])
    vrows.sort(key=lambda x: (x[4] != 'Yes', x[2] == '', -(float(x[2].rstrip('%')) if x[2] else 0)))
    sheet(wb, 'Verdict', ['Lens', 'Severity', 'Score', 'Points', 'Lead issue', 'Evidence (signals that scored)'], vrows,
          {'Evidence (signals that scored)': 100})

    sheet(wb, 'Signals', ['Lens', 'Signal', 'What it measures', 'Value', 'Threshold', 'Points', 'Possible', 'Note'],
          [[x['lens'], x['id'], x['name'], x['value'], x['threshold'], 'Not scored' if x['points'] is None else x['points'],
            x['possible'], x['note']] for x in S.rows],
          {'What it measures': 55, 'Value': 40, 'Threshold': 35, 'Note': 40})

    if gbp['assessed']:
        fr = [[x['id'], x['name'], x['priority'], 'Yes' if x['found'] else 'No', x['value'], x['detail']] for x in gbp['findings']]
        ws = sheet(wb, 'Google Business Profile', ['ID', 'Finding', 'Priority', 'Found', 'Value', 'Rule'], fr,
                   {'Finding': 42, 'Value': 60, 'Rule': 70})
        ws.append([])
        ws.append(['Business', 'Role', 'Rating (typed)', 'Reviews (typed)', 'Categories (typed)'] + [
            f'Local position: {k}' for k in gbp['prospect']['rankings']])
        for cell in ws[ws.max_row]:
            cell.font, cell.fill, cell.alignment = HEAD, FILL, WRAP
        for role, e in [('Prospect', gbp['prospect'])] + [('Competitor', c) for c in gbp['competitors']]:
            ws.append([e.get('name', cfg.get('client', '')), role, float(e['rating']), int(float(e['reviews'])),
                       ', '.join(e['categories'])] + [(_pos(v) if _pos(v) is not None else 'Not shown')
                                                       for v in e['rankings'].values()])
        opt = [k for k in ('photos', 'linked_page', 'attributes', 'services') if any(
            e.get(k) not in (None, '', []) for e in [gbp['prospect']] + gbp['competitors'])]
        if opt:
            ws.append([])
            ws.append(['Optional details (typed; not scored)', 'Role'] + [k.replace('_', ' ').capitalize() for k in opt])
            for cell in ws[ws.max_row]:
                cell.font, cell.fill, cell.alignment = HEAD, FILL, WRAP
            for role, e in [('Prospect', gbp['prospect'])] + [('Competitor', c) for c in gbp['competitors']]:
                ws.append([e.get('name', cfg.get('client', '')), role] + [
                    ', '.join(map(str, e.get(k))) if isinstance(e.get(k), list) else ('' if e.get(k) is None else e.get(k))
                    for k in opt])
        ws.column_dimensions['E'].width = 45

    rep = arch['repeated']
    groups = []
    for col, label in (('title', 'Title'), ('h1', 'H1')):
        for val in sorted(arch['counts'][col], key=lambda v: -int((rep[col] == v).sum())):
            sub = rep[rep[col] == val]
            groups.append([label, val, len(sub), sub['url'].iloc[0]])
    groups.sort(key=lambda x: -x[2])
    mix = [['Archive and listing pages (indexable)', arch['archive']], ['Other indexable pages', arch['other']],
           ['Live but not indexable', arch['nonidx']], ['Redirecting URLs reached by the crawler', arch['redirects']],
           ['All crawled HTML URLs', arch['crawled']]]
    ws = sheet(wb, 'Architecture', ['Page group', 'Count'], mix, {'Page group': 45})
    ws.append([])
    ws.append(['Repeated title or H1 (non-archive pages)', 'Text', 'Pages', 'Example URL'])
    for cell in ws[ws.max_row]:
        cell.font, cell.fill = HEAD, FILL
    for row in groups[:50]:
        ws.append(row)
    ws.append([])
    ws.append([f'Non-archive pages under {THIN_WORDS} words', 'Content words', 'Title'])
    for cell in ws[ws.max_row]:
        cell.font, cell.fill = HEAD, FILL
    for _, t in arch['thin'].sort_values('words').iterrows():
        ws.append([t['url'], int(t['words']), t['title']])
    ws.column_dimensions['B'].width = 50
    ws.column_dimensions['D'].width = 70

    brows = [[d, 'Prospect' if d == prospect else 'Competitor', cont['ranked'][d], cont['top10'][d], cont['s10'][d]]
             for d in [prospect] + comps]
    ws = sheet(wb, 'Content', ['Domain', 'Role', 'Keywords ranked in the gap export', 'Of those in the top 10',
                               'Top 10 on non-branded service keywords'], brows, {'Domain': 35})
    if cont['svc_rows']:
        ws.append([])
        ws.append(['Non-branded service rankings (service)', 'Keywords tracked', 'Prospect top 10', 'Prospect best position',
                   'Top competitor', 'Its top 10', 'Its best position',
                   f'Competitor top 10, prospect not top {WIN_POS}', 'Note'])
        for cell in ws[ws.max_row]:
            cell.font, cell.fill, cell.alignment = HEAD, FILL, WRAP
        for row in cont['svc_rows']:
            ws.append(row)
    ws.append([])
    hdr = [f'Buying searches a competitor ranks top {WIN_POS} for and the prospect does not', 'Est. monthly searches (tool estimate)',
           'Best competitor', 'Its position']
    ws.append(hdr)
    for cell in ws[ws.max_row]:
        cell.font, cell.fill = HEAD, FILL
    com = cont['commercial'].sort_values('est_volume', ascending=False).head(100)
    for _, k in com.iterrows():
        posd = {d: k[d] for d in comps if pd.notna(k[d])}
        bd = min(posd, key=posd.get)
        ws.append([k['keyword'], k['est_volume'], bd, posd[bd]])
    ws.column_dimensions['A'].width = 55

    arow = []
    for d in [prospect] + comps:
        o = auth['overview'].get(d, {})
        arow.append([d, o.get('authority_score', ''), o.get('referring_domains', ''), o.get('referring_domains_12m_ago', '')])
    ws = sheet(wb, 'Authority', ['Domain', 'Authority score (typed from the tool)', 'Referring domains now',
                                 'Referring domains 12 months ago'], arow, {'Domain': 35})
    if refd is not None:
        ws.append([])
        ws.append(['Prospect referring domains', 'Count'])
        for cell in ws[ws.max_row]:
            cell.font, cell.fill = HEAD, FILL
        ws.append(['Total', len(refd)])
        ws.append([f'Score {QUALITY_SCORE} or higher', auth['quality']])
        ws.append([f'Score {LOW_SCORE} or lower', auth['low']])
        if 'first_seen' in refd:
            ws.append([])
            ws.append(['First seen (month)', 'Referring domains'])
            for cell in ws[ws.max_row]:
                cell.font, cell.fill = HEAD, FILL
            by = refd.dropna(subset=['first_seen']).groupby(refd['first_seen'].dt.to_period('M')).size().tail(13)
            for p, n in by.items():
                ws.append([str(p), int(n)])
    if blgap is not None:
        ws.append([])
        ws.append([f'Domains scoring {QUALITY_SCORE}+ linking to competitors, not the prospect', 'Score', 'Links to'])
        for cell in ws[ws.max_row]:
            cell.font, cell.fill = HEAD, FILL
        q = blgap[blgap['score'] >= QUALITY_SCORE].sort_values('score', ascending=False)
        for _, x in q.iterrows():
            ws.append([x['domain'], x['score'], x.get('competitors', '')])

    sheet(wb, 'Ranking URLs Not Live', ['URL', 'Crawl status', 'Tracked keywords', 'Top keyword', 'Position',
                                        'Est. monthly searches (tool estimate)'], arch['not_live'], {'URL': 80})
    check('estimate columns are labeled as estimates',
          all('estimate' in str(cell.value) for ws_ in wb for cell in ws_[1] if 'search' in str(cell.value).lower()
              and 'monthly' in str(cell.value).lower()))
    wb.save(a.out)
    check('workbook saved', os.path.exists(a.out), f'{a.out}; tabs: {", ".join(wb.sheetnames)}')

    svc_keys = ['service', 'keywords', 'prospect_top10', 'prospect_best', 'top_competitor', 'competitor_top10',
                'competitor_best', 'lost', 'note']
    out_json = a.json or os.path.join(os.path.dirname(os.path.abspath(a.out)), 'diagnosis.json')
    save_json(out_json, {
        'client': cfg.get('client', ''), 'domain': prospect, 'competitors': comps,
        'generated': pd.Timestamp.today().strftime('%Y-%m-%d'), 'tool': sorted(t.capitalize() for t in tools),
        'lenses': lenses, 'lead': lead, 'signals': S.rows,
        'services': [dict(zip(svc_keys, r)) for r in cont['svc_rows']],
        'pages': {'crawled': arch['crawled'], 'live': arch['live'], 'indexable': arch['indexable'],
                  'archive': arch['archive'], 'other': arch['other']},
        'gbp': gbp,
        'notes': notes,
    })
    check('diagnosis.json written', os.path.exists(out_json), out_json)

    print('\nVerdict:')
    for v in lenses:
        print(f'  {v["lens"]}: {v["severity"]}' + ('' if v['share'] is None else f' ({pct(v["share"])}, {v["points"]} of '
                                                     f'{v["possible"]} points)'))
    print(f'  Lead issue: {lead_text}')
    if gbp['assessed']:
        print('  Google Business Profile (separate from the lead issue):')
        for x in gbp['findings']:
            print(f'    {x["id"]} {x["name"]} ({x["priority"]}): ' + ('FOUND' if x['found'] else 'not found') + f' - {x["value"]}')
    else:
        print('  Google Business Profile: not assessed (' + '; '.join(gbp['problems']) + ')')
    if not all(checks):
        sys.exit(1)
    print('All checks passed')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('preflight', 'build'):
        p = sub.add_parser(name)
        p.add_argument('--config', required=True)
        p.add_argument('--crawl')
        p.add_argument('--ranking')
        p.add_argument('--gap')
        p.add_argument('--refdomains')
        p.add_argument('--backlink-gap')
        p.add_argument('--gbp', help='the filled Google Business Profile template (xlsx)')
        p.add_argument('--tool', choices=['semrush', 'ahrefs'])
        p.add_argument('--map', action='append', help='field override, e.g. crawl.words="Word Count" or gapcol.x.com="Col"')
        if name == 'preflight':
            p.add_argument('--out', default='work')
        else:
            p.add_argument('--json', help='where to write diagnosis.json (default: next to the workbook)')
        if name == 'preflight':
            pass
        else:
            p.add_argument('--out', required=True)
    a = ap.parse_args()
    if a.cmd == 'build':
        for f in ('crawl', 'ranking', 'gap'):
            if not getattr(a, f):
                raise SystemExit(f'--{f} is required for build')
    (cmd_preflight if a.cmd == 'preflight' else cmd_build)(a)


if __name__ == '__main__':
    main()
