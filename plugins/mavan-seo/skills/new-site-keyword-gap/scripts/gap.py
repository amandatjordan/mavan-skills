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
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, canon, norm_url, num, pick, read_table, resolve  # noqa: E402

TOP_N = 10               # a competitor at this position or better counts toward the 2+ rule
MULTI_MIN = 2            # 2+ rule: at least this many competitors in the top TOP_N
TOP_BEST = 3             # 1+ rule: any one competitor at this position or better
LEFTOVER_MIN = 3         # list a competitor-name word that still appears in at least this many non-branded keywords
BRAND_BROAD_SHARE = 0.05  # warn when one brand term removes more than this share of the gap keywords
MIN_COMPETITORS = 3
MAX_COMPETITORS = 5
ROUND_ROWS = {1000, 5000, 10000, 20000, 25000, 30000, 50000, 100000}
LOCAL_GENERIC = [r'near me', r'nearby', r'close to me']
BLOG_PATTERN = re.compile(r'/(blog|blogs|news|articles?|posts?|guides?|journal|resources|learn)(/|$)|/\d{4}/\d{1,2}/')
STOP = {'the', 'in', 'for', 'of', 'a', 'an', 'and', 'to', 'near', 'me', 'how', 'what', 'is', 'are', 'do', 'does', 'vs',
        'with', 'on', 'at', 'my', 'i', 'can', 'you', 'your', 'best', 'cost', 'much', 'much', 'price', 'prices'}

# "Other services" tab: words too generic to name a service, folders and slugs that mark a competitor service page
CAND_MIN = 3             # a candidate service needs at least this many keywords
CAND_MAX = 40            # at most this many candidate rows from keywords
GENERIC = {'plastic', 'cosmetic', 'surgery', 'surgeon', 'surgeons', 'surgical', 'treatment', 'treatments', 'doctor', 'doctors',
           'clinic', 'clinics', 'center', 'centre', 'centers', 'procedure', 'procedures', 'medical', 'aesthetic', 'aesthetics',
           'advanced', 'advance', 'top', 'good', 'side', 'effects', 'safe', 'work', 'works', 'like', 'look', 'looks', 'last',
           'lasts', 'need', 'time', 'day', 'days', 'week', 'weeks', 'month', 'months', 'year', 'years', 'women', 'men', 'woman',
           'man', 'many', 'long', 'get', 'rid', 'types', 'type', 'one', 'than', 'other', 'bigger', 'after', 'before', 'pictures',
           'picture', 'photos', 'photo', 'pics', 'reviews', 'review', 'results', 'result', 'recovery', 'price', 'prices', 'cost',
           'costs', 'much', 'units', 'unit', 'using', 'use', 'new', 'near', 'around', 'sc', 'nc', 'ga', 'south', 'carolina', 'upstate',
           'dr', 'md', 'office', 'offices', 'care', 'health', 'skin', 'face', 'body', 'will', 'should', 'would', 'could', 'make',
           'makes', 'without', 'about', 'from', 'that', 'this', 'when', 'where', 'who', 'why', 'which', 'there', 'their', 'put', 'different', 'sizes', 'size', 'while', 'pregnant', 'pregnancy', 'being', 'tip', 'tips'}
SERVICE_FOLDERS = {'services', 'service', 'procedures', 'procedure', 'treatments', 'treatment', 'surgery', 'surgical',
                   'cosmetic-procedures', 'our-services', 'what-we-do', 'aesthetics', 'aesthetic-services', 'body', 'face', 'breast', 'nonsurgical', 'non-surgical'}
NON_SERVICE = {'about', 'contact', 'team', 'doctor', 'doctors', 'dr', 'meet', 'testimonials', 'testimonial', 'reviews', 'review', 'gallery',
               'photo', 'photos', 'photogallery', 'before', 'after', 'financing', 'finance', 'specials', 'special', 'privacy', 'terms',
               'blog', 'locations', 'location', 'careers', 'shop', 'product', 'products', 'faq', 'faqs', 'video', 'videos', 'staff',
               'provider', 'providers', 'patient', 'patients', 'forms', 'form', 'appointment', 'consultation', 'cost', 'costs', 'recovery',
               'payment', 'payments', 'sitemap', 'login', 'cart', 'checkout', 'account', 'press', 'news', 'events', 'event', 'giving', 'donate'}
PAGE_FILLER = {'treatment', 'treatments', 'procedure', 'procedures', 'surgery', 'in', 'the', 'and', 'for', 'of'}

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
                      'url': df[m['url']].str.strip().str.split('#').str[0].str.split('?').str[0]})
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
    g['top10_multi'] = g['top10_count'] >= MULTI_MIN
    g['top3_any'] = (pos <= TOP_BEST).any(axis=1)
    best = pos.min(axis=1)
    g['best_position'] = best
    g['best_competitor'] = [', '.join(c for c in comps if pos.at[i, c] == b) if pd.notna(b) else ''
                            for i, b in best.items()]
    g['opportunity'] = g['top10_multi'] | g['top3_any']
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
        if m and m.group(1).split()[0] not in STOP:
            locs[m.group(1).strip()] += 1
    left = []
    for d, pats in ctx['comp_brands'].items():
        toks = {t for term in pats for t in re.findall(r'[a-z0-9]+', term) if len(t) >= 4 and t not in STOP}
        for t in sorted(toks):
            rx = term_re(t)
            hit = [k for k in g['keyword'] if rx.search(k.lower())]
            if len(hit) >= LEFTOVER_MIN:
                left.append((d, t, len(hit), hit[:4]))
    ctx['leftover'] = left
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
    lines += ['', '## Possible leftover brand words', '',
              'Words from a competitor name that still appear in non-branded keywords. If one is part of the name as people search it '
              '(a short form such as "ageless" for "Ageless Remedies"), add it to that competitor\'s names. If it is a service word, leave it.', '']
    lines += [f'- {d}: "{t}" in {n:,} keywords, e.g. {"; ".join(ex)}' for d, t, n, ex in sorted(left, key=lambda x: -x[2])] or ['- none found']
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
    if ctx.get('leftover'):
        lines.append(f'- WARN: {len(ctx["leftover"])} word(s) from competitor names still appear in non-branded keywords '
                     f'(for example "{max(ctx["leftover"], key=lambda x: x[2])[1]}"). See "Possible leftover brand words" in candidates.md and ask the SEO.')
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
INPUT_FILL = PatternFill('solid', fgColor='FFF2CC')


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


def page_type(url):
    p = path_of(url)
    return 'Home page' if p.strip('/') == '' else ('Blog or article' if BLOG_PATTERN.search(p.lower()) else 'Other page')


def best_page(rows, comps):
    """The competitor page with the most keywords in the top 10 among these keywords. Home pages are skipped (not a page to model).
    Ties: more keywords at any position, then the better best position. Same page with or without www counts once."""
    stats = {}
    for d in comps:
        for u, pos in zip(rows[f'url_{d}'], rows[d]):
            if isinstance(u, str) and pd.notna(pos) and path_of(u).strip('/') != '':
                t = stats.setdefault((norm_url(u), d), [0, 0, 1e9, u])
                t[0] += int(pos <= TOP_N)
                t[1] += 1
                t[2] = min(t[2], pos)
    ranked = [(k, v) for k, v in stats.items() if v[0] > 0]
    if not ranked:
        return 'No competitor page (other than a home page) in the top 10', '', '', ''
    (key, d), v = sorted(ranked, key=lambda kv: (-kv[1][0], -kv[1][1], kv[1][2], kv[0][0]))[0]
    return v[3], page_type(v[3]), d, v[0]


# ------------------------------------------------------------------ other services (candidates the SEO may have missed)

def label_of(term):
    return ' '.join(w if w.isupper() else w.capitalize() for w in term.split())


def slug_key(slug, skip):
    """A service page slug as a plain name: location and filler words removed, cut at 'in' / 'near'."""
    toks = [t for t in re.split(r'[-_]+', slug.lower()) if t]
    cut = [i for i, t in enumerate(toks) if t in ('in', 'near')]
    if cut and cut[0] > 0:
        toks = toks[:cut[0]]
    toks = [t for t in toks if t not in skip and t not in PAGE_FILLER and not t.isdigit()]
    return ' '.join(toks)


def service_pages(ranks, skip):
    """Competitor pages that look like a service page, from the ranking exports. Returns {name: {competitor: set(urls)}}.
    A service page sits under a service folder (/services/liposuction/) or is a short top-level page (/mommy-makeover/).
    Blog paths, the home page and about / contact / gallery style slugs are left out. A guess from the URL, like 'Looks like'."""
    out = defaultdict(lambda: defaultdict(set))
    for d, r in ranks.items():
        for u in set(r['url']):
            path = path_of(u).strip('/').lower()
            if not path or BLOG_PATTERN.search('/' + path):
                continue
            segs = path.split('/')
            slug = segs[-1]
            toks = re.split(r'[-_]+', slug)
            folder_toks = [t for sg in segs[:-1] for t in re.split(r'[-_]+', sg)]
            if any(t in NON_SERVICE for t in toks + folder_toks) or any(t.startswith(('product', 'shop')) for t in folder_toks):
                continue
            if segs[0] in SERVICE_FOLDERS and len(segs) >= 2:
                pass
            elif len(segs) == 1 and len(toks) <= 4:
                pass
            else:
                continue
            key = slug_key(slug, skip)
            if len(key) >= 4 and key not in SERVICE_FOLDERS:
                out[key][d].add(u)
    return out


def candidate_terms(pool, skip):
    """Greedy, non-overlapping candidate services from keywords that match no service: two-word phrases first, then single words."""
    grams = {}
    for i, kw in zip(pool.index, pool['kw_lower']):
        toks = re.findall(r"[a-z0-9']+", kw)
        ok = lambda t: t not in STOP and not t.isdigit() and len(t) > 2 and t not in skip
        bi = {f'{a} {b}' for a, b in zip(toks, toks[1:]) if ok(a) and ok(b) and not (a in GENERIC and b in GENERIC)}
        uni = {t for t in toks if ok(t) and t not in GENERIC and len(t) > 3}
        grams[i] = (bi, uni)
    remaining, cands = set(grams), []
    for level in (0, 1):
        while len(cands) < CAND_MAX:
            cnt = Counter(g for i in remaining for g in grams[i][level])
            if not cnt:
                break
            term, c = max(cnt.items(), key=lambda kv: (kv[1], kv[0]))
            if c < CAND_MIN:
                break
            members = [i for i in remaining if term in grams[i][level]]
            cands.append((term, members))
            remaining -= set(members)
    return cands


def other_services_rows(kept, comps, ranks, services, cities, brand_tokens, ignored):
    """Rows for the Other services tab: candidates from unmatched keywords, plus service pages competitors built that no
    service or candidate covers. Returns (rows, counts)."""
    skip = set(brand_tokens) | {t for c in cities for t in re.findall(r'[a-z0-9]+', c.lower())}
    ign_rx = [term_re(t) for t in ignored]
    covered_rx = [term_re(t) for _, terms in services for t in terms]
    pool = kept[kept['services'].map(len) == 0]
    if ign_rx:
        pool = pool[~pool['kw_lower'].map(lambda k: any(rx.search(k) for rx in ign_rx))]
    cands = candidate_terms(pool, skip)
    pages = service_pages(ranks, skip)
    pages = {k: v for k, v in pages.items() if not any(rx.search(k) for rx in covered_rx) and not any(rx.search(k) for rx in ign_rx)}
    used = set()

    def stats(rows, label, source, urls_by_comp):
        page, page_kind, page_comp, page_n = best_page(rows, comps) if len(rows) else ('', '', '', '')
        best = Counter(c for b in rows['best_competitor'] for c in b.split(', ') if c) if len(rows) else Counter()
        top = rows.sort_values('est_volume', ascending=False).head(3) if len(rows) else rows
        sp = '; '.join(f'{d}: {u}' for d, us in sorted(urls_by_comp.items()) for u in sorted(us)[:2])
        return [label_of(label), source, '', label, len(rows), int(rows['top10_multi'].sum()) if len(rows) else 0,
                int(rows['top3_any'].sum()) if len(rows) else 0, int(rows['opportunity'].sum()) if len(rows) else 0,
                best.most_common(1)[0][0] if best else '', page, page_kind, len(urls_by_comp), sp,
                '; '.join(f'{k} (est. {int(v):,})' if pd.notna(v) else k for k, v in zip(top['keyword'], top['est_volume']))]
    out = []
    for term, members in cands:
        rows = kept.loc[members]
        rx = term_re(term)
        match = {k: v for k, v in pages.items() if rx.search(k)}
        used |= set(match)
        by = defaultdict(set)
        for v in match.values():
            for d, us in v.items():
                by[d] |= us
        out.append(stats(rows, term, 'Both' if match else 'Keywords', by))
    for key, byc in pages.items():
        if key in used:
            continue
        urls = {d: us for d, us in byc.items()}
        idx = set()
        for d, us in urls.items():
            idx |= set(kept.index[kept[f'url_{d}'].isin(us)])
        rows = kept.loc[sorted(idx)] if idx else kept.iloc[0:0]
        out.append(stats(rows, key, 'Competitor service page', urls))
    # keep rows with some evidence: a keyword meeting a rule, 2+ competitors with a page, or at least CAND_MIN keywords
    out = [r for r in out if r[7] >= 1 or r[11] >= 2 or r[4] >= CAND_MIN]
    out.sort(key=lambda r: (-r[7], -r[4], -r[11], r[0]))
    return out


OTHER_HEAD = ['Candidate service', 'Source', 'Offered by our client (SEO fills in: Yes or No)', 'Terms to match (edit; separate with commas)',
              'Keywords', 'Keywords with 2+ competitors in top 10', 'Keywords with 1+ competitor in top 3', 'Keywords with 2+ in top 10 or 1+ in top 3',
              'Competitor best on most keywords', 'Best-performing competitor page', 'Looks like', 'Competitors with a service page',
              'Service pages competitors have', "Highest estimated-volume keywords (each volume is the tool's estimate)"]


def apply_review(path, cfg, cfg_path):
    """Read a filled workbook from an earlier build. A Yes on the Other services tab adds that service to service_terms;
    a No is remembered in not_services so it is not suggested again. Returns (added, ignored, answers_by_service)."""
    df = pd.read_excel(path, sheet_name=None, dtype=str, keep_default_na=False)
    if 'Other services' not in df:
        raise SystemExit(f'--review: no "Other services" tab in {path}. Pass the workbook from an earlier build of this skill.')
    o = df['Other services']
    ycol = next((c for c in o.columns if c.startswith('Offered by our client')), None)
    if ycol is None or 'Candidate service' not in o.columns or not any(c.startswith('Terms to match') for c in o.columns):
        raise SystemExit('--review: the Other services tab is missing its Candidate service, Offered by our client or Terms to match column.')
    tcol = next(c for c in o.columns if c.startswith('Terms to match'))
    have = {n.lower() for n, _ in service_list(cfg)}
    cfg.setdefault('service_terms', [])
    ignored = list(cfg.get('not_services') or [])
    added, newly_ignored = [], []
    for _, r in o.iterrows():
        ans, name = r[ycol].strip().lower(), r['Candidate service'].strip()
        terms = [t.strip().lower() for t in re.split(r'[,;]', r[tcol]) if t.strip()] or [name.lower()]
        if ans == 'yes' and name.lower() not in have:
            cfg['service_terms'].append({'service': name, 'terms': terms})
            have.add(name.lower())
            added.append(name)
        elif ans == 'no':
            for t in terms:
                if t not in ignored:
                    ignored.append(t)
                    newly_ignored.append(t)
    # Unassigned tab: a Yes adds the keyword as a term (to the service named in the next column, or as a service of its own);
    # a No hides that keyword from the suggestions
    if 'Unassigned' in df:
        u = df['Unassigned']
        ucol = next((c for c in u.columns if c.startswith('Offered by our client')), None)
        ncol = next((c for c in u.columns if c.startswith('Service name')), None)
        if ucol and ncol:
            entries = cfg['service_terms']
            for i, e in enumerate(entries):
                if isinstance(e, str):
                    entries[i] = {'service': e, 'terms': [e]}
            by_name = {e['service'].lower(): e for e in entries}
            for _, r in u.iterrows():
                ans, kw = r[ucol].strip().lower(), r['Keyword'].strip().lower()
                name = r[ncol].strip() or label_of(kw)
                if ans == 'yes' and kw:
                    e = by_name.get(name.lower())
                    if e is None:
                        e = {'service': name, 'terms': []}
                        entries.append(e)
                        by_name[name.lower()] = e
                        added.append(name)
                    if kw not in [t.lower() for t in e.get('terms') or []]:
                        e['terms'] = list(e.get('terms') or []) + [kw]
                elif ans == 'no' and kw and kw not in ignored:
                    ignored.append(kw)
                    newly_ignored.append(kw)
    cfg['not_services'] = ignored
    import json
    with open(cfg_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=1)
    answers = {}
    if 'Service opportunities' in df:
        so = df['Service opportunities']
        sc = next((c for c in so.columns if c.startswith('Offered by our client')), None)
        if sc:
            answers = {r['Service']: r[sc] for _, r in so.iterrows() if r[sc].strip()}
    return added, newly_ignored, answers


def cmd_build(a):
    print('Reading inputs')
    fails, warns, ctx = check_inputs(a)
    if fails:
        raise SystemExit('Preflight problems, fix these first:\n' + '\n'.join(f'- {m}' for m in fails))
    g, comps, ranks, cfg = ctx['g'], ctx['doms'], ctx['ranks'], ctx['cfg']
    answers = {}
    if getattr(a, 'review', None):
        added, newly_ignored, answers = apply_review(a.review, cfg, a.config)
        print(f'  Review: {len(added)} service(s) added from the Other services tab' + (f' ({", ".join(added)})' if added else '')
              + f'; {len(newly_ignored)} term(s) marked No will not be suggested again. Config updated: {a.config}')
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
        out += [r['location'], 'Yes' if r['top10_multi'] else '', 'Yes' if r['top3_any'] else '', int(r['top10_count']),
                r['best_competitor'], val(r['best_position']), r['best_url']]
        out += [val(r[d]) for d in comps]
        return out
    kw_head = ['Keyword', 'Estimated volume', 'Group', 'Services', 'Location', '2+ competitors in top 10',
               '1+ competitor in top 3', 'Competitors in top 10', 'Best-ranking competitor', 'Best position', 'Best competitor page'] + [f'{d} position' for d in comps]
    widths = {'Keyword': 38, 'Services': 28, 'Best competitor page': 50, 'Best-ranking competitor': 28}

    # service rows: a keyword counts under every service it matches
    comp_cols = [f'Keywords where {d} is top 10' for d in comps]
    svc_head = ['Service', 'Offered by our client (SEO fills in: Yes or No)', 'Non-branded keywords', 'Keywords with 2+ competitors in top 10',
                'Keywords with 1+ competitor in top 3', 'Keywords with 2+ in top 10 or 1+ in top 3', 'Local keywords for this service',
                'Local keywords with 2+ in top 10 or 1+ in top 3', 'Best-performing competitor page', 'Looks like', 'Competitor with that page',
                'Keywords that page has in top 10 (for this service)', 'Competitor best on most keywords'] + comp_cols + \
               ['Highest estimated-volume keywords (each volume is the tool\'s estimate)']
    srows = []
    for name, _ in services:
        s = kept[(kept['group'] == 'Service') & kept['services'].map(lambda x: name in x)]
        lc = kept[(kept['group'] == 'Local') & kept['services'].map(lambda x: name in x)]
        both = pd.concat([s, lc])
        page, page_kind, page_comp, page_n = best_page(both, comps)
        loc_cells = [len(lc), int(lc['opportunity'].sum())]
        if s.empty:
            srows.append([name, answers.get(name, ''), 0, 0, 0, 0, *loc_cells, page, page_kind, page_comp, page_n, '', *[0] * len(comps),
                          'No non-local competitor keywords matched. Not the same as no demand: check the term.'])
            continue
        best_counts = Counter(c for b in s['best_competitor'] for c in b.split(', ') if c)
        top = s.sort_values('est_volume', ascending=False).head(3)
        srows.append([name, answers.get(name, ''), len(s), int(s['top10_multi'].sum()), int(s['top3_any'].sum()), int(s['opportunity'].sum()), *loc_cells,
                      page, page_kind, page_comp, page_n, best_counts.most_common(1)[0][0], *[int((s[d] <= TOP_N).sum()) for d in comps],
                      '; '.join(f'{k} (est. {int(v):,})' if pd.notna(v) else k for k, v in zip(top['keyword'], top['est_volume']))])
    # most keywords with the 2+ or 1+ rule met (non-local plus local), then most keywords
    srows.sort(key=lambda r: (-(r[5] + r[7]), -(r[2] + r[6]), r[0]))

    # competitor pages
    long = []
    for d in comps:
        sub = kept[kept[d].notna() & kept[f'url_{d}'].notna()]
        for u, grp in sub.groupby(f'url_{d}'):
            p = path_of(u)
            ptype = page_type(u)
            svc = Counter(s for l in grp['services'] for s in l).most_common(1)
            long.append([d, u, ptype, len(grp), int((grp[d] <= TOP_N).sum()), int(grp['opportunity'].sum()),
                         svc[0][0] if svc else '', val(grp[d].min())])
    long.sort(key=lambda r: (-r[5], -r[3]))
    page_head = ['Competitor', 'Page', 'Looks like', 'Non-branded keywords it ranks for', 'Of those, top 10', 'Of those, with 2+ in top 10 or 1+ in top 3',
                 'Service it matches most', 'Best position']

    un = kept[kept['group'] == 'Unassigned']
    # other services: candidates the confirmed service list may have missed
    brand_tokens = {t for pats in ctx['comp_brands'].values() for term in pats for t in re.findall(r'[a-z0-9]+', term)}
    orows = other_services_rows(kept, comps, ranks, services, cities, brand_tokens, [str(x).lower() for x in cfg.get('not_services') or []])

    # summary
    grp_counts = kept['group'].value_counts()
    sumrows = [
        ['ACTION NEEDED', f'SEO must check the Other services tab ({len(orows)} candidates) and the Unassigned tab ({len(un):,} keywords) for services the client offers that are missing from the service list. Mark Yes or No on both.'],
        ['Tool detected', ctx['tool']], ['Competitors', ', '.join(comps)],
        ['Gap keywords in the export', len(g)], ['Removed as branded (a competitor name)', len(removed)],
        ['No competitor ranks (empty position columns)', no_rank], ['Non-branded keywords analysed', len(kept)],
        ['In a service group', int(grp_counts.get('Service', 0))], ['In the Local group (city or near me)', int(grp_counts.get('Local', 0))],
        ['Unassigned (no service or city term matched)', int(grp_counts.get('Unassigned', 0))],
        ['Candidate services on the Other services tab', len(orows)],
        ['Keywords with 2+ competitors in the top 10', int(kept['top10_multi'].sum())],
        ['Keywords with 1+ competitor in the top 3', int(kept['top3_any'].sum())],
        ['Keywords with 2+ in the top 10 or 1+ in the top 3', int(kept['opportunity'].sum())], [],
        ['Per competitor', 'Keywords in top 10 / top 3 / total ranking']]
    for d in comps:
        sumrows.append([d, f'{int((kept[d] <= TOP_N).sum())} / {int((kept[d] <= TOP_BEST).sum())} / {int(kept[d].notna().sum())}'])
    uw = Counter()
    for kw in un['kw_lower']:
        uw.update({t for t in re.findall(r"[a-z0-9']+", kw) if t not in STOP and len(t) > 2})
    top_un = uw.most_common(15)
    sumrows += [[], ['Most common words in Unassigned (add a service term or a competitor name for any that belongs)', ''],
                *[[w, c] for w, c in top_un]]
    readme = [
        ['ACTION NEEDED: SEO must check the Other services and Unassigned tabs',
         f'The service list this workbook was built from may be incomplete. {len(orows)} candidate services are on the Other services tab and {len(un):,} keywords matched no service or city (Unassigned tab). '
         'Open both tabs before relying on the service counts. Mark Yes for anything the client offers and No for anything it does not (Unassigned: optionally type the service name for a Yes). '
         'Then run the next build with --review pointing at this workbook: every Yes is added to the services and the counts update.'],
        ['What this is', 'Non-branded searches that competitors rank for, grouped by service, to choose what a new site should target. There is no site to crawl, so nothing here compares against an existing site.'],
        ['Opportunity rules', f'A keyword has 2+ competitors in the top {TOP_N} when at least {MULTI_MIN} competitors rank {TOP_N} or better, and 1+ competitor in the top {TOP_BEST} when at least one ranks {TOP_BEST} or better. Best-ranking competitor, position and page are shown for every keyword.'],
        ['Best-performing page', 'For each service: the competitor page with the most keywords in the top 10 among that service\'s keywords (non-local and local). Home pages are skipped. Ties go to the page with more keywords at any position. It is a count of keywords, not traffic.'],
        ['Offered by our client', 'Blank for the SEO to fill in (Yes or No) once the client confirms which services it offers.'],
        ['Estimated volume', 'The tool\'s estimate for the keyword. It is not a traffic forecast or a promise. Volumes are never added together here.'],
        ['Snapshot', 'Positions are a snapshot of keywords the tool tracks (mostly the top 100). A service with few keywords may be untracked, not undemanded.'],
        ['Groups', 'A keyword that matches a city or "near me" is in the Local group only. Other keywords are in every service group whose term they contain, so service rows can overlap. Keywords that match nothing are in Unassigned for review.'],
        ['Branded searches', 'Searches containing a competitor\'s name (or its domain name) were removed. See the Branded removed tab.'],
        ['Competitor pages', '"Looks like" is a guess from the URL path (blog folders and the home page). Check the page before relying on it.'],
        ['Other services', 'Services competitors rank or have a page for that are not in the confirmed service list: groups of keywords that matched no service (grouped by their most common phrase) and service pages competitors have built (a guess from the URL). Mark Yes for what the client offers and No for what it does not, then pass this workbook back with --review on the next build: Yes rows become services, No rows are not suggested again. Edit "Terms to match" to add other names people search.'],
        ['Unassigned', 'Every keyword that matched no service or city. Mark Yes on a keyword the client offers (type a service name in the next column to add it to a service, or leave it blank and the keyword becomes a service of its own) or No to hide it. Applied on the next build with --review.'],
        ['Competitors', 'Every domain column in the gap export is treated as a competitor, including the one used as the base domain. Competitors that overlap on only some services show up in those services only.'],
    ]
    wb = Workbook()
    wb.remove(wb.active)
    sheet(wb, 'Read Me', ['Topic', 'Detail'], readme, {'Topic': 24, 'Detail': 120})
    sheet(wb, 'Summary', ['Measure', 'Value'], sumrows, {'Measure': 52, 'Value': 60})
    ws = sheet(wb, 'Service opportunities', svc_head, srows, {'Service': 28, svc_head[1]: 22, 'Best-performing competitor page': 60, svc_head[-1]: 70})
    if srows:
        dv = DataValidation(type='list', formula1='"Yes,No"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f'B2:B{len(srows) + 1}')
        for r in range(2, len(srows) + 2):
            ws.cell(r, 2).fill = INPUT_FILL
    ws2 = sheet(wb, 'Other services', OTHER_HEAD, orows, {'Candidate service': 28, OTHER_HEAD[2]: 22, OTHER_HEAD[3]: 30, 'Best-performing competitor page': 60,
                                                          'Service pages competitors have': 60, OTHER_HEAD[-1]: 70, 'Competitor best on most keywords': 28})
    if orows:
        dv2 = DataValidation(type='list', formula1='"Yes,No"', allow_blank=True)
        ws2.add_data_validation(dv2)
        dv2.add(f'C2:C{len(orows) + 1}')
        for r in range(2, len(orows) + 2):
            ws2.cell(r, 3).fill = INPUT_FILL
            ws2.cell(r, 4).fill = INPUT_FILL
    sheet(wb, 'Keywords', kw_head, [row(r) for _, r in kept[kept['group'] != 'Local'].iterrows()], widths)
    sheet(wb, 'Local', kw_head, [row(r) for _, r in kept[kept['group'] == 'Local'].iterrows()], widths)
    sheet(wb, 'Competitor pages', page_head, long, {'Page': 70, 'Service it matches most': 28})
    un_head = ['Keyword', 'Estimated volume', 'Competitors in top 10', 'Best-ranking competitor', 'Best position',
               'Offered by our client (SEO fills in: Yes or No)', 'Service name for a Yes (optional; blank = the keyword is its own service)']
    ws3 = sheet(wb, 'Unassigned', un_head,
                [[r['keyword'], val(r['est_volume']), int(r['top10_count']), r['best_competitor'], val(r['best_position']), '', '']
                 for _, r in un.sort_values('est_volume', ascending=False).iterrows()],
                {'Keyword': 48, un_head[5]: 22, un_head[6]: 36})
    if len(un):
        dv3 = DataValidation(type='list', formula1='"Yes,No"', allow_blank=True)
        ws3.add_data_validation(dv3)
        dv3.add(f'F2:F{len(un) + 1}')
        for r in range(2, len(un) + 2):
            ws3.cell(r, 6).fill = INPUT_FILL
            ws3.cell(r, 7).fill = INPUT_FILL
    for w in (ws2, ws3):
        w.sheet_properties.tabColor = 'F4B183'
    sheet(wb, 'Branded removed', ['Keyword', 'Term matched'], [[r['keyword'], r['brand_term']] for _, r in removed.iterrows()], {'Keyword': 48})
    order = ['Summary', 'Service opportunities', 'Other services', 'Unassigned', 'Keywords', 'Local', 'Competitor pages', 'Branded removed', 'Read Me']
    wb._sheets = [wb[n] for n in order]
    wb.active = 0
    wb.save(a.out)

    # self-check: recompute from the raw positions
    problems = []
    if len(kept) != int(grp_counts.sum()):
        problems.append('group counts do not add up to the keywords analysed')
    raw_a = int(((kept[comps] <= TOP_N).sum(axis=1) >= MULTI_MIN).sum())
    raw_b = int((kept[comps].min(axis=1) <= TOP_BEST).sum())
    if raw_a != int(kept['top10_multi'].sum()) or raw_b != int(kept['top3_any'].sum()):
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
          f'{int(kept["top10_multi"].sum())} with 2+ in top 10, {int(kept["top3_any"].sum())} with 1+ in top 3.')
    if problems:
        raise SystemExit('CHECK FAILED: ' + '; '.join(problems))
    if top_un:
        print('  Most common words in Unassigned: ' + ', '.join(f'{w} ({c})' for w, c in top_un))
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
        if name == 'build':
            p.add_argument('--review', help='workbook from an earlier build with the Other services tab filled in (Yes / No); Yes rows are added to the config as services')
    a = ap.parse_args()
    (cmd_preflight if a.cmd == 'preflight' else cmd_build)(a)


if __name__ == '__main__':
    main()
