"""New-site keyword gap: what competitors rank for in non-branded searches, grouped by service, for a business with no website yet.

  python gap.py preflight --config work/config.json --gap GAP.csv --ranking "rival.com=RIVAL.csv" ... --out work
  python gap.py build     --config work/config.json --gap GAP.csv --ranking "rival.com=RIVAL.csv" ... --out "work/Name Keyword Gap.xlsx"

The script does every count. Volumes are the tool's estimates and are never added together.
Thresholds are the constants below; references/rules.md explains them.
"""
import argparse
import os
import re
import sys
from collections import Counter, defaultdict

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, canon, num, pick, read_table, resolve  # noqa: E402

TOP_N = 10               # flag A: a competitor in the top 10 counts toward "several competitors rank"
MULTI_MIN = 2            # flag A: at least this many competitors in the top TOP_N
TOP_BEST = 3             # flag B: any one competitor at this position or better
BRAND_BROAD_SHARE = 0.05  # warn when one brand term removes more than this share of the gap keywords
MIN_COMPETITORS = 3
MAX_COMPETITORS = 5
ROUND_ROWS = {1000, 5000, 10000, 20000, 25000, 30000, 50000, 100000}
LOCAL_GENERIC = [r'near me', r'nearby', r'close to me']
BLOG_PATTERN = re.compile(r'/(blog|blogs|news|articles?|posts?|guides?|journal|resources|learn)(/|$)|/\d{4}/\d{1,2}/')
STOP = {'the', 'in', 'for', 'of', 'a', 'an', 'and', 'to', 'near', 'me', 'how', 'what', 'is', 'are', 'do', 'does', 'vs',
        'with', 'on', 'at', 'my', 'i', 'can', 'you', 'your', 'best', 'cost', 'much', 'much', 'price', 'prices'}

GAP_SPEC = {
    'keyword': (['Keyword'], True),
    'volume': (['Search Volume', 'Volume'], True),
    'intent': (['Intents', 'Keyword Intents', 'Intent'], False),
}
RANKING_SPEC = {
    'keyword': (['Keyword'], True),
    'position': (['Position', 'Current position'], True),
    'url': (['URL', 'Current URL'], True),
}
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
    return re.compile(r'(?<![a-z0-9])' + re.escape(t.lower().strip()) + r'(e?s)?(?![a-z0-9])')


def parse_map(items):
    out = {}
    for it in items or []:
        k, v = it.split('=', 1)
        out[k.strip()] = v.strip().strip('"')
    return out


def parse_rankings(items):
    out = {}
    for it in items or []:
        if '=' not in it:
            raise SystemExit(f'--ranking must look like "rival.com=file.csv", got: {it}')
        d, p = it.split('=', 1)
        out[bare_domain(d)] = p.strip().strip('"')
    return out


def path_of(url):
    return re.sub(r'^[a-z]+://[^/]+', '', str(url), flags=re.I).split('?')[0].split('#')[0] or '/'


def brand_patterns(domain, names):
    """The names the SEO gave plus the domain itself (rival-one.com -> 'rival one', 'rivalone', 'rival-one')."""
    stem = bare_domain(domain).split('.')[0]
    terms = {n.strip().lower() for n in names if n.strip()}
    terms |= {stem.replace('-', ' '), stem.replace('-', ''), stem}
    terms = {re.sub(r'\s+', ' ', t) for t in terms if len(t) >= 3}
    return {t: term_re(t) for t in sorted(terms)}


def load_config(path):
    import json
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def service_list(cfg):
    out = []
    for s in cfg.get('service_terms') or []:
        if isinstance(s, str):
            out.append((s, [s]))
        else:
            out.append((s['service'], [s['service']] + list(s.get('terms') or [])))
    return out


def load_gap(path, ov, tool):
    df = read_any(path)
    tool = tool or detect_tool(df)
    m = resolve(df, GAP_SPEC, 'gap', ov)
    doms = domain_columns(df, {c for c in m.values() if c})
    for k, v in ov.items():
        if k.startswith('gapcol.'):
            doms[bare_domain(k[7:])] = v
    g = pd.DataFrame({'keyword': df[m['keyword']].str.strip(), 'est_volume': df[m['volume']].map(num)})
    for d, col in doms.items():
        p = df[col].map(num)
        g[d] = p.where(p > 0)
    g = g[g['keyword'] != ''].copy()
    g['kw_lower'] = g['keyword'].str.lower()
    return g, tool, sorted(doms), len(df)


def load_ranking(path, ov, domain):
    df = read_any(path)
    m = resolve(df, RANKING_SPEC, f'ranking.{domain}', ov)
    r = pd.DataFrame({'keyword': df[m['keyword']].str.strip().str.lower(), 'position': df[m['position']].map(num),
                      'url': df[m['url']].str.strip()})
    r = r[(r['keyword'] != '') & (r['url'] != '')]
    return r.sort_values('position').drop_duplicates('keyword'), len(df)


# ------------------------------------------------------------------ classification

def brand_hits(g, comp_brands):
    """Per keyword: the first brand term found, or ''."""
    flat = [(t, rx) for pats in comp_brands.values() for t, rx in pats.items()]

    def first(kw):
        for t, rx in flat:
            if rx.search(kw):
                return t
        return ''
    return g['kw_lower'].map(first)


def classify(g, comps, services, cities):
    svc_rx = [(name, [term_re(t) for t in terms]) for name, terms in services]
    city_rx = [(c, term_re(c)) for c in cities]
    gen_rx = [re.compile(p) for p in LOCAL_GENERIC]
    svc, loc = [], []
    for kw in g['kw_lower']:
        hit_c = [c for c, rx in city_rx if rx.search(kw)]
        if not hit_c and any(rx.search(kw) for rx in gen_rx):
            hit_c = ['near me']
        loc.append(', '.join(hit_c))
        svc.append([n for n, rxs in svc_rx if any(rx.search(kw) for rx in rxs)])
    g = g.copy()
    g['services'] = svc
    g['location'] = loc
    g['group'] = ['Local' if l else ('Service' if s else 'Unassigned') for l, s in zip(loc, svc)]
    return g


def add_flags(g, comps):
    pos = g[comps]
    g = g.copy()
    g['top10_count'] = (pos <= TOP_N).sum(axis=1)
    g['flag_a'] = g['top10_count'] >= MULTI_MIN
    g['flag_b'] = (pos <= TOP_BEST).any(axis=1)
    best = pos.min(axis=1)
    g['best_position'] = best
    g['best_competitor'] = [', '.join(c for c in comps if pos.at[i, c] == b) if pd.notna(b) else ''
                            for i, b in best.items()]
    g['opportunity'] = g['flag_a'] | g['flag_b']
    return g


# ------------------------------------------------------------------ preflight

def check_inputs(a):
    """Shared by preflight and build. Returns (problems, warnings, context)."""
    cfg = load_config(a.config)
    ov = parse_map(a.map)
    fails, warns = [], []
    g, tool, doms, nrows = load_gap(a.gap, ov, a.tool)
    rankings = parse_rankings(a.ranking)
    if not tool:
        fails.append('Could not tell whether the keyword gap export is from Semrush or Ahrefs. Ask which tool made it and pass --tool.')
    if len(doms) < 2:
        fails.append(f'The keyword gap export has {len(doms)} domain position column(s) ({doms}). It needs one per competitor. '
                     'Pass --map "gapcol.domain.com=Column name" for any it missed.')
    if len(doms) < MIN_COMPETITORS and len(doms) >= 2:
        warns.append(f'Only {len(doms)} competitors in the gap export; {MIN_COMPETITORS}-{MAX_COMPETITORS} give a more reliable picture.')
    if len(doms) > MAX_COMPETITORS:
        warns.append(f'{len(doms)} competitors in the gap export; more than {MAX_COMPETITORS} makes the top-10 rule easy to meet.')
    if nrows in ROUND_ROWS:
        warns.append(f'The gap export has exactly {nrows:,} rows, which looks like an export cap. Some keywords may be missing; say so in the reply.')
    names = {bare_domain(k): v for k, v in (cfg.get('competitors') or {}).items()}
    for d in doms:
        if not [n for n in (names.get(d) or []) if str(n).strip()]:
            fails.append(f'No competitor name for {d}. Ask the SEO for the name people search for {d} (and any variants) '
                         f'and add "competitors": {{"{d}": ["name"]}} to the config.')
    extra = sorted(set(names) - set(doms))
    if extra:
        warns.append(f'Config lists competitors that are not columns in the gap export, so they are ignored: {extra}.')
    for d in doms:
        if d not in rankings:
            fails.append(f'No Organic Positions export for {d}. Pass --ranking "{d}=file.csv".')
        elif not os.path.exists(rankings[d]):
            fails.append(f'--ranking file for {d} not found: {rankings[d]}')
    for d in set(rankings) - set(doms):
        warns.append(f'--ranking given for {d}, which is not a competitor in the gap export. It is ignored.')
    if not service_list(cfg):
        fails.append('No "service_terms" in the config. Propose them from work/candidates.md, confirm them with the SEO and add them.')
    if 'cities' not in cfg:
        warns.append('No "cities" key in the config. Ask the SEO which cities or areas the business serves (an empty list is fine if there are none). '
                     'Only "near me" searches go to the Local group until it is set.')
    ranks = {}
    for d in doms:
        if d in rankings and os.path.exists(rankings[d]):
            try:
                ranks[d], n = load_ranking(rankings[d], ov, d)
            except SystemExit as e:
                fails.append(str(e))
                continue
            hosts = ranks[d]['url'].map(bare_domain)
            share = (hosts.map(lambda h: h == d or h.endswith('.' + d))).mean() if len(hosts) else 0
            if share < 0.5:
                warns.append(f'Fewer than half the URLs in the {d} ranking export are on {d} ({share:.0%}). Check it is the right file.')
    comp_brands = {d: brand_patterns(d, names.get(d) or []) for d in doms}
    g = g.copy()
    g['brand_term'] = brand_hits(g, comp_brands)
    n_brand = int((g['brand_term'] != '').sum())
    for t, c in Counter(g.loc[g['brand_term'] != '', 'brand_term']).items():
        if c / max(len(g), 1) > BRAND_BROAD_SHARE:
            warns.append(f'The brand term "{t}" removes {c:,} of {len(g):,} keywords ({c/len(g):.0%}). It may be too broad; check it is a name and not a service word.')
    ctx = dict(cfg=cfg, ov=ov, g=g, tool=tool, doms=doms, ranks=ranks, comp_brands=comp_brands, n_brand=n_brand, rows=nrows)
    return fails, warns, ctx


def write_candidates(ctx, out):
    g = ctx['g'][ctx['g']['brand_term'] == '']
    words = Counter()
    pairs = Counter()
    locs = Counter()
    for kw in g['kw_lower']:
        toks = [t for t in re.findall(r"[a-z0-9']+", kw)]
        words.update({t for t in toks if t not in STOP and len(t) > 2})
        pairs.update({' '.join(p) for p in zip(toks, toks[1:]) if not (p[0] in STOP and p[1] in STOP)})
        m = re.search(r'\b(?:in|near|around)\s+([a-z][a-z .\-]{2,30})$', kw)
        if m and 'me' != m.group(1).strip():
            locs[m.group(1).strip()] += 1
    segs = defaultdict(lambda: [0, set()])
    for d, r in ctx['ranks'].items():
        for u in set(r['url']):
            p = path_of(u).strip('/')
            if p:
                s = segs['/' + p.split('/')[0] + '/']
                s[0] += 1
                s[1].add(d)
    lines = ['# Candidates for service terms and cities', '',
             'Only for proposing config values. Confirm each list with the SEO; do not use it as the final list.', '',
             '## Words in non-branded gap keywords (number of keywords)', '']
    lines += [f'- {w}: {c}' for w, c in words.most_common(40)]
    lines += ['', '## Two-word phrases (number of keywords)', '']
    lines += [f'- {w}: {c}' for w, c in pairs.most_common(40)]
    lines += ['', '## Locations after "in" / "near" / "around" (number of keywords)', '']
    lines += [f'- {w}: {c}' for w, c in locs.most_common(30)] or ['- none found']
    lines += ['', '## First folder of competitor ranking URLs (number of URLs, competitors)', '']
    lines += [f'- {s}: {n} URLs, {", ".join(sorted(ds))}' for s, (n, ds) in sorted(segs.items(), key=lambda x: -x[1][0])[:40]]
    with open(os.path.join(out, 'candidates.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def cmd_preflight(a):
    os.makedirs(a.out, exist_ok=True)
    print('Reading inputs')
    fails, warns, ctx = check_inputs(a)
    write_candidates(ctx, a.out)
    ready = not fails
    lines = ['# Preflight', '', f'**{"READY" if ready else "NOT READY"}**', '',
             f'- Tool detected: {ctx["tool"] or "unknown"}',
             f'- Competitors (gap export domain columns): {", ".join(ctx["doms"]) or "none"}',
             f'- Gap keywords: {len(ctx["g"]):,}; removed as branded: {ctx["n_brand"]:,}', '']
    lines += [f'- FAIL: {m}' for m in fails] + [f'- WARN: {m}' for m in warns]
    lines += ['', 'Candidates for service terms and cities are in candidates.md.']
    with open(os.path.join(a.out, 'preflight.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    if not ready:
        sys.exit(1)


# ------------------------------------------------------------------ build

HEAD = Font(bold=True, color='FFFFFF')
FILL = PatternFill('solid', fgColor='111111')
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


def val(x):
    return None if pd.isna(x) else (int(x) if float(x).is_integer() else float(x))


def cmd_build(a):
    print('Reading inputs')
    fails, warns, ctx = check_inputs(a)
    if fails:
        raise SystemExit('Preflight problems, fix these first:\n' + '\n'.join(f'- {m}' for m in fails))
    g, comps, ranks, cfg = ctx['g'], ctx['doms'], ctx['ranks'], ctx['cfg']
    services = service_list(cfg)
    cities = [str(c) for c in cfg.get('cities') or []]
    removed = g[g['brand_term'] != ''].copy()
    kept = g[g['brand_term'] == ''].copy()
    kept = kept[kept[comps].notna().any(axis=1)].copy()
    no_rank = len(g) - len(removed) - len(kept)
    kept = add_flags(classify(kept, comps, services, cities), comps)
    # URL of each competitor's page for each keyword, from that competitor's own ranking export
    url = {d: dict(zip(ranks[d]['keyword'], ranks[d]['url'])) for d in comps}
    for d in comps:
        kept[f'url_{d}'] = kept['kw_lower'].map(url[d])
    kept['best_url'] = ['; '.join(r[f'url_{c}'] for c in r['best_competitor'].split(', ')
                                   if c and isinstance(r[f'url_{c}'], str)) for _, r in kept.iterrows()]
    kept = kept.sort_values(['opportunity', 'top10_count', 'est_volume'], ascending=[False, False, False])

    def row(r, with_services=True):
        out = [r['keyword'], val(r['est_volume']), r['group']]
        if with_services:
            out.append(', '.join(r['services']))
        out += [r['location'], 'Yes' if r['flag_a'] else '', 'Yes' if r['flag_b'] else '', int(r['top10_count']),
                r['best_competitor'], val(r['best_position']), r['best_url']]
        out += [val(r[d]) for d in comps]
        return out
    kw_head = ['Keyword', 'Estimated volume', 'Group', 'Services', 'Location', 'A: several competitors top 10',
               'B: a competitor top 3', 'Competitors in top 10', 'Best-ranking competitor', 'Best position', 'Best competitor page'] + [f'{d} position' for d in comps]
    widths = {'Keyword': 38, 'Services': 28, 'Best competitor page': 50, 'Best-ranking competitor': 28}

    # service rows: a keyword counts under every service it matches
    srows = []
    for name, _ in services:
        s = kept[(kept['group'] == 'Service') & kept['services'].map(lambda x: name in x)]
        if s.empty:
            srows.append([name, 0, 0, 0, 0, '', *[0] * len(comps), 'No competitor keywords matched. Not the same as no demand: check the term.'])
            continue
        best_counts = Counter(c for b in s['best_competitor'] for c in b.split(', ') if c)
        top = s.sort_values('est_volume', ascending=False).head(3)
        srows.append([name, len(s), int(s['flag_a'].sum()), int(s['flag_b'].sum()), int(s['opportunity'].sum()),
                      best_counts.most_common(1)[0][0], *[int((s[d] <= TOP_N).sum()) for d in comps],
                      '; '.join(f'{k} (est. {int(v):,})' if pd.notna(v) else k for k, v in zip(top['keyword'], top['est_volume']))])
    srows.sort(key=lambda r: (-r[4], -r[1], r[0]))
    svc_head = ['Service', 'Non-branded keywords', 'A: several competitors top 10', 'B: a competitor top 3', 'A or B',
                'Competitor best on most keywords'] + [f'Keywords where {d} is top 10' for d in comps] + ['Highest estimated-volume keywords (each volume is the tool\'s estimate)']

    # competitor pages
    long = []
    for d in comps:
        sub = kept[kept[d].notna() & kept[f'url_{d}'].notna()]
        for u, grp in sub.groupby(f'url_{d}'):
            p = path_of(u)
            ptype = 'Home page' if p.strip('/') == '' else ('Blog or article' if BLOG_PATTERN.search(p.lower()) else 'Other page')
            svc = Counter(s for l in grp['services'] for s in l).most_common(1)
            long.append([d, u, ptype, len(grp), int((grp[d] <= TOP_N).sum()), int(grp['opportunity'].sum()),
                         svc[0][0] if svc else '', val(grp[d].min())])
    long.sort(key=lambda r: (-r[5], -r[3]))
    page_head = ['Competitor', 'Page', 'Looks like', 'Non-branded keywords it ranks for', 'Of those, top 10', 'Of those, flagged A or B',
                 'Service it matches most', 'Best position']

    # summary
    grp_counts = kept['group'].value_counts()
    sumrows = [
        ['Tool detected', ctx['tool']], ['Competitors', ', '.join(comps)],
        ['Gap keywords in the export', len(g)], ['Removed as branded (a competitor name)', len(removed)],
        ['No competitor ranks (empty position columns)', no_rank], ['Non-branded keywords analysed', len(kept)],
        ['In a service group', int(grp_counts.get('Service', 0))], ['In the Local group (city or near me)', int(grp_counts.get('Local', 0))],
        ['Unassigned (no service or city term matched)', int(grp_counts.get('Unassigned', 0))],
        ['Flagged A (2 or more competitors in the top 10)', int(kept['flag_a'].sum())],
        ['Flagged B (a competitor in the top 3)', int(kept['flag_b'].sum())],
        ['Flagged A or B', int(kept['opportunity'].sum())], [],
        ['Per competitor', 'Keywords in top 10 / top 3 / total ranking']]
    for d in comps:
        sumrows.append([d, f'{int((kept[d] <= TOP_N).sum())} / {int((kept[d] <= TOP_BEST).sum())} / {int(kept[d].notna().sum())}'])
    readme = [
        ['What this is', 'Non-branded searches that competitors rank for, grouped by service, to choose what a new site should target. There is no site to crawl, so nothing here compares against an existing site.'],
        ['Flags', f'A = at least {MULTI_MIN} competitors rank in the top {TOP_N}. B = at least one competitor ranks in the top {TOP_BEST}. Best-ranking competitor, position and page are shown for every keyword.'],
        ['Estimated volume', 'The tool\'s estimate for the keyword. It is not a traffic forecast or a promise. Volumes are never added together here.'],
        ['Snapshot', 'Positions are a snapshot of keywords the tool tracks (mostly the top 100). A service with few keywords may be untracked, not undemanded.'],
        ['Groups', 'A keyword that matches a city or "near me" is in the Local group only. Other keywords are in every service group whose term they contain, so service rows can overlap. Keywords that match nothing are in Unassigned for review.'],
        ['Branded searches', 'Searches containing a competitor\'s name (or its domain name) were removed. See the Branded removed tab.'],
        ['Competitor pages', '"Looks like" is a guess from the URL path (blog folders and the home page). Check the page before relying on it.'],
        ['Competitors', 'Every domain column in the gap export is treated as a competitor, including the one used as the base domain. Competitors that overlap on only some services show up in those services only.'],
    ]
    wb = Workbook()
    wb.remove(wb.active)
    sheet(wb, 'Read Me', ['Topic', 'Detail'], readme, {'Topic': 24, 'Detail': 120})
    sheet(wb, 'Summary', ['Measure', 'Value'], sumrows, {'Measure': 52, 'Value': 60})
    sheet(wb, 'Service opportunities', svc_head, srows, {'Service': 28, svc_head[-1]: 70})
    sheet(wb, 'Keywords', kw_head, [row(r) for _, r in kept[kept['group'] != 'Local'].iterrows()], widths)
    sheet(wb, 'Local', kw_head, [row(r) for _, r in kept[kept['group'] == 'Local'].iterrows()], widths)
    sheet(wb, 'Competitor pages', page_head, long, {'Page': 70, 'Service it matches most': 28})
    sheet(wb, 'Unassigned', ['Keyword', 'Estimated volume', 'Competitors in top 10', 'Best-ranking competitor', 'Best position'],
          [[r['keyword'], val(r['est_volume']), int(r['top10_count']), r['best_competitor'], val(r['best_position'])]
           for _, r in kept[kept['group'] == 'Unassigned'].iterrows()], {'Keyword': 48})
    sheet(wb, 'Branded removed', ['Keyword', 'Term matched'], [[r['keyword'], r['brand_term']] for _, r in removed.iterrows()], {'Keyword': 48})
    wb.save(a.out)

    # self-check: recompute from the raw positions
    problems = []
    if len(kept) != int(grp_counts.sum()):
        problems.append('group counts do not add up to the keywords analysed')
    raw_a = int(((kept[comps] <= TOP_N).sum(axis=1) >= MULTI_MIN).sum())
    raw_b = int((kept[comps].min(axis=1) <= TOP_BEST).sum())
    if raw_a != int(kept['flag_a'].sum()) or raw_b != int(kept['flag_b'].sum()):
        problems.append('flag counts differ from a recount')
    if len(g) != len(removed) + no_rank + len(kept):
        problems.append('removed + empty + analysed does not equal the gap rows')
    for d in comps:
        miss = int(kept[d].notna().sum()) - int(kept[f'url_{d}'].notna().sum())
        if miss > 0:
            print(f'  Note: {miss:,} {d} keywords in the gap export have no matching row in its ranking export, so no page is shown for them.')
    for m in warns:
        print(f'  WARN: {m}')
    print(f'Wrote {a.out}')
    print(f'{len(kept):,} non-branded keywords: {grp_counts.get("Service", 0)} service, {grp_counts.get("Local", 0)} local, {grp_counts.get("Unassigned", 0)} unassigned; '
          f'{int(kept["flag_a"].sum())} flagged A, {int(kept["flag_b"].sum())} flagged B.')
    if problems:
        raise SystemExit('CHECK FAILED: ' + '; '.join(problems))
    print('All checks passed')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('preflight', 'build'):
        p = sub.add_parser(name)
        p.add_argument('--config', required=True)
        p.add_argument('--gap', required=True)
        p.add_argument('--ranking', action='append', help='one per competitor: "domain.com=file.csv" (repeat the option)')
        p.add_argument('--tool', choices=['semrush', 'ahrefs'])
        p.add_argument('--map', action='append', help='field override, e.g. gap.volume="Vol" or gapcol.x.com="Col"')
        p.add_argument('--out', required=(name == 'build'), default='work')
    a = ap.parse_args()
    (cmd_preflight if a.cmd == 'preflight' else cmd_build)(a)


if __name__ == '__main__':
    main()
