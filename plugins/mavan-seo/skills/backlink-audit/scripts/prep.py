#!/usr/bin/env python3
"""Load the Ahrefs or Semrush exports and build the candidate rows for all three tabs.

Usage (two exports are enough: client backlinks and the link gap):
  python prep.py --config work/config.json --out work --backlinks B.csv --gap G.csv [--gap G2.csv] \
    [--refdomains R.csv] [--compare C.csv] [--broken BR.csv] [--audit SEMRUSH_AUDIT.csv] \
    [--gsc-links GSC.csv] [--gap-pages GP.csv] [--redirect-map MAP.csv] \
    [--map backlinks.anchor="Anchor text"]

Everything else is derived: referring-domain counts, the client Rollup row and the anchor mix come from the
backlinks export, and broken backlinks come from a live status check of every client URL the backlinks point
at (build.py reads status.tsv). The optional exports only add detail (see references/exports.md).

Writes to --out:
  links.csv            every client backlink, normalized
  rollup.csv           Competitor Rollup rows
  disavow.csv          flagged referring domains (Disavow Review candidates)
  noise.json           domains summarized as noise on the Disavow Review tab
  broken.csv           broken client URLs from a --broken export (empty without one; build.py derives them)
  opportunities.csv    link-gap domains after filtering, with competitors linking and a type guess
  gap_all.csv          every link-gap domain with the reason it was filtered (so decisions.json can add it back)
  redirect_map.json    planned redirects from --redirect-map
  status_needed.txt    every client URL to check live in the Composio workbench
  prep_summary.json    counts and notes for the reviewer
"""
import argparse
import os
import re
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (load_json, norm_url, num, read_table, reg_domain, resolve, save_json,  # noqa: E402
                    truthy, bare_domain, canon)

# ---------------------------------------------------------------- column aliases (Ahrefs, Semrush, GSC)
SPEC = {
    'backlinks': {
        'source_url': (['Referring page URL', 'Source url', 'Source URL', 'Linking page', 'Referring page'], True),
        'target_url': (['Target URL', 'Target url'], True),
        'anchor': (['Anchor', 'Anchor text'], False),
        'title': (['Referring page title', 'Source title', 'Title'], False),
        'authority': (['Domain rating', 'DR', 'Domain ascore', 'Authority Score', 'AS'], False),
        'traffic': (['Domain traffic', 'Referring domain traffic'], False),
        'nofollow': (['Nofollow', 'No follow'], False),
        'sitewide': (['Sitewide'], False),
        'first_seen': (['First seen', 'First Seen'], False),
        'lang': (['Language'], False),
        'lost': (['Lost status', 'Lost link', 'Lost'], False),
    },
    'refdomains': {
        'domain': (['Domain', 'Referring domain', 'Root domain'], True),
        'authority': (['Domain rating', 'DR', 'Domain ascore', 'Authority Score', 'Ascore', 'AS'], False),
        'traffic': (['Domain traffic', 'Traffic'], False),
        'links': (['Links to target', 'Backlinks', 'Links'], False),
        'dofollow': (['Dofollow links', 'Dofollow'], False),
        'first_seen': (['First seen'], False),
    },
    'broken': {
        'source_url': (['Referring page URL', 'Source url', 'Source URL'], False),
        'target_url': (['Target URL', 'Target url', 'URL', 'Page URL'], True),
        'authority': (['Domain rating', 'DR', 'Domain ascore'], False),
        'code': (['Target HTTP code', 'HTTP code', 'Response code', 'Status code', 'Target status code'], False),
        'refdomains': (['Referring domains', 'Domains', 'Ref domains'], False),
    },
    'compare': {
        'target': (['Target', 'Domain', 'URL', 'Website'], True),
        'authority': (['Domain Rating', 'DR', 'Domain ascore', 'Authority Score', 'Ascore', 'AS'], False),
        'refdomains': (['Ref domains All', 'Referring domains', 'Ref domains', 'Referring Domains'], False),
        'dofollow_refdomains': (['Ref domains Dofollow', 'Dofollow referring domains', 'Dofollow ref domains'], False),
        'backlinks': (['Total Backlinks', 'Backlinks', 'Backlinks All'], False),
        'traffic': (['Total Traffic', 'Organic traffic', 'Organic Traffic', 'Traffic'], False),
        'gained': (['New referring domains', 'Ref domains new', 'New ref domains'], False),
        'lost': (['Lost referring domains', 'Ref domains lost', 'Lost ref domains'], False),
    },
    'gap': {
        'domain': (['Domain', 'Referring domain', 'Referring Domain'], True),
        'authority': (['Domain rating', 'DR', 'Domain ascore', 'Authority Score', 'AS', 'Ascore'], False),
        'traffic': (['Domain traffic', 'Traffic'], False),
        'matches': (['Intersect', 'Matches'], False),
    },
    'gap_pages': {
        'source_url': (['Referring page URL', 'Source url', 'Referring page'], True),
        'target_url': (['Target URL', 'Target url'], False),
    },
    'audit': {
        'source_url': (['Source url', 'Source URL'], True),
        'toxic': (['Toxic score', 'Toxicity score', 'Toxicity Score', 'Score'], False),
        'markers': (['Toxic markers', 'Toxicity markers', 'Markers'], False),
    },
    'gsc_links': {
        'page': (['Linking page', 'Linking pages URL', 'Site', 'Top linking sites', 'Linking site'], True),
    },
    'redirect_map': {
        'source': (['Source URL', 'Source', 'From'], True),
        'target': (['Target URL', 'Target', 'To'], True),
    },
}

# ---------------------------------------------------------------- pattern lists
SPAM_SUB = ['casino', 'gambl', 'poker', 'porn', 'viagra', 'cialis', 'levitra', 'payday', 'bitcoin',
            'escort', 'replica', 'essaywrit', 'writemyessay', 'betting', 'sportsbook', 'slotgacor',
            'togel', 'onlyfans', 'hentai', 'camgirl', 'xxx']
SPAM_TOKEN = {'bet', 'sex', 'slot', 'slots', 'loan', 'loans', 'pills', 'crypto', 'forex', 'essay', 'nude',
              'adult', 'dating', 'judi', 'cbd', 'vape'}
SPAMMY_TLD = {'xyz', 'top', 'pw', 'icu', 'buzz', 'tk', 'ml', 'ga', 'cf', 'gq', 'work', 'click', 'loan',
              'bid', 'win', 'ru', 'cn', 'su', 'rest', 'monster', 'cyou', 'sbs', 'cfd', 'quest'}
PAID = ['sponsored', 'guest-post', 'guestpost', 'write-for-us', 'writeforus', 'advertorial', 'paid-post',
        'submit-guest', 'guest-blog', 'sponsored-post', 'partner-content', 'buy-backlinks']
NOISE = ['stat', 'worth', 'whois', 'siteprice', 'sitevalue', 'websiteoutlook', 'similarsite', 'sitelike',
         'hypestat', 'domaintools', 'seoanalyz', 'seo-analyz', 'websiteinformer', 'site-analyzer', 'urlscan',
         'webrank', 'rankwatch', 'checkwebsite', 'sitechecker', 'traffic-estimate', 'trafficestimate',
         'domainstats', 'ipaddress', 'ip-address', 'dnslytics', 'hostingchecker', 'builtwith', 'siteindices',
         'webstatsdomain', 'linkody', 'backlinkchecker', 'seoprofiler', 'pagerank', 'alexa', 'semrush',
         'ahrefs', 'moz.com', 'majestic', 'spyfu', 'serpstat', 'freshwebsite', 'websitelooker', 'webstats',
         'sitesummaries', 'aboutus', 'zoominfo-like', 'linkcheck', 'sur.ly', 'xranks', 'iwebchk', 'cutestat']
SAFE = ['yelp', 'facebook', 'instagram', 'linkedin', 'twitter', 'x.com', 'tiktok', 'youtube', 'pinterest',
        'google', 'bbb.org', 'healthgrades', 'realself', 'vitals', 'zocdoc', 'yellowpages', 'mapquest',
        'nextdoor', 'allergan', 'alle.com', 'galderma', 'evolus', 'merz', 'revance', 'sciton', 'cutera',
        'candela', 'lumenis', 'inmode', 'cynosure', 'bbl', 'hydrafacial', 'zeltiq', 'coolsculpting',
        'webmd', 'wikipedia', 'apple.com', 'bing.com', 'yahoo', 'tripadvisor', 'angi', 'thumbtack',
        'manta', 'chamberofcommerce', 'patch.com', 'groupon', 'square.site', 'vagaro', 'mindbodyonline',
        'boulevard', 'joinblvd', 'carecredit', 'cherry', 'plasticsurgery.org', 'americanmedspa', 'asds.net',
        'aafprs', 'theaestheticsociety', 'abcs']
GENERIC = {'', 'here', 'click here', 'website', 'this website', 'link', 'read more', 'learn more', 'visit',
           'visit website', 'this', 'source', 'more', 'home', 'homepage', 'site', 'web', 'view', 'details',
           'more info', 'more information', 'see more', 'go', 'continue', 'this article', 'url', 'www', 'img',
           '[image]', 'image', 'noname', 'empty anchor', 'no anchor', 'view website', 'official website'}
# Link-seller / PBN networks: matched against a domain's linking page URLs, anchors and page titles.
# These domains go to the noise summary row, not one Disavow Review row each.
NOISE_TEXT = re.compile(r'link-outreach-services|premium link building|dofollow link building|dofollow backlinks|'
                        r'guest posts, my sales|backlink|\bpbn\b|aged domains', re.I)
# Link-gap domains that are never real opportunities: junk TLDs and SEO-tool names in the domain.
JUNK_TLD = {'shop', 'store', 'space', 'site', 'online', 'website', 'xyz'}
JUNK_WORDS = ['seo', 'backlink', 'checker', 'dapa', 'serp']
COMMERCIAL = ['botox', 'filler', 'lip ', 'laser', 'hair removal', 'med spa', 'medspa', 'medical spa',
              'plastic surg', 'cosmetic', 'facelift', 'rhinoplasty', 'liposuction', 'lipo', 'tummy tuck',
              'breast', 'coolsculpting', 'microneedling', 'hydrafacial', 'weight loss', 'semaglutide',
              'tirzepatide', 'iv therapy', 'dentist', 'dental', 'implant', 'near me', 'best ', 'top ',
              'cheap', 'affordable', ' cost', 'price', 'clinic', 'surgeon', 'dermal', 'injector', 'facial',
              'skin care', 'skincare', 'wellness', 'hormone', 'trt', 'chiropract', 'spine']
TYPES = {
    'Manufacturer / provider locator': ['allergan', 'alle.com', 'galderma', 'evolus', 'merz', 'revance', 'sciton',
                                         'cutera', 'candela', 'lumenis', 'inmode', 'cynosure', 'hydrafacial',
                                         'coolsculpting', 'zeltiq', 'skinmedica', 'zoskin', 'jeuveau', 'xeomin',
                                         'daxxify', 'restylane', 'juvederm', 'sculptra', 'emsculpt', 'btlaesthetics',
                                         'morpheus8', 'venus', 'solta', 'thermage', 'ultherapy', 'evoke', 'provider'],
    'Local directory / citation': ['yelp', 'yellowpages', 'mapquest', 'manta', 'citysearch', 'superpages', 'hotfrog',
                                   'brownbook', 'cylex', 'merchantcircle', 'directory', 'listing', 'local', 'find',
                                   'healthgrades', 'vitals', 'zocdoc', 'realself', 'bbb.org', 'nextdoor', 'angi',
                                   'thumbtack', 'foursquare', 'ezlocal', 'n49', 'showmelocal', 'chamberofcommerce'],
    'Association / chamber / nonprofit': ['chamber', 'association', 'society', 'academy', 'council', 'foundation',
                                          'rotary', 'kiwanis', 'lions', 'alliance', 'federation', 'guild', 'board'],
    'Local news / media': ['news', 'times', 'gazette', 'tribune', 'herald', 'journal', 'post', 'patch', 'courier',
                           'chronicle', 'observer', 'register', 'sentinel', 'dispatch', 'daily', 'magazine', 'mag',
                           'press', 'tv', 'radio', 'fox', 'abc', 'nbc', 'cbs', 'wsj', 'today', 'living', 'lifestyle'],
    'Podcast / interview': ['podcast', 'episode', 'show', 'interview', 'radio'],
    'Education / .edu / .gov': ['.edu', '.gov', '.k12.', 'school', 'university', 'college'],
    'Listicle / "best of" roundup': ['best', 'top', 'expertise', 'threebest', 'bestof', 'reviews', 'rated'],
    'Sponsorship / event': ['event', 'festival', 'gala', '5k', 'marathon', 'tournament', 'fundrais', 'charity'],
}
OPP_TYPES = ['Local directory / citation', 'Local news / media', 'Association / chamber / nonprofit',
             'Manufacturer / provider locator', 'Industry publication / blog', 'Listicle / "best of" roundup',
             'Sponsorship / event', 'Podcast / interview', 'Education / .edu / .gov', 'Partner / vendor', 'Other']


def has_any(text, words):
    return [w for w in words if w in text]


def tokens(text):
    return set(t for t in re.split(r'[^a-z0-9]+', text.lower()) if t)


def is_noise(dom):
    return any(w in dom for w in NOISE) and not any(s in dom for s in SAFE)


def is_safe(dom, extra=()):
    return any(s in dom for s in SAFE) or dom.endswith('.gov') or dom.endswith('.edu') or dom in extra


def spam_hits(text):
    t = text.lower()
    hits = has_any(t, SPAM_SUB) + sorted(tokens(t) & SPAM_TOKEN)
    return sorted(set(hits))


def link_seller_text(g):
    """True when a domain's linking pages (URL, anchor or title) match the link-seller / PBN patterns."""
    return any(g[c].astype(str).str.contains(NOISE_TEXT).any() for c in ('source_url', 'anchor', 'title'))


def junk_domain(dom):
    """Junk TLD, or an SEO-tool word in the domain name. 'rank' only counts at the start of a word, so
    rankbooster.com and best-rankings.com match but frankfurt.com and frank.com do not."""
    d = dom.lower()
    label = d.rsplit('.', 1)[0]
    if d.rsplit('.', 1)[-1] in JUNK_TLD or any(w in label for w in JUNK_WORDS):
        return True
    return bool(re.search(r'(^|-)rank', label))


def default_priority(n, auth, t):
    """High = 3+ competitors, or a typed site with authority 40+; Medium = 2 competitors or authority 20+."""
    if n >= 3 or (auth == auth and auth >= 40 and t != 'Other'):
        return 'High'
    if n == 2 or (auth == auth and auth >= 20):
        return 'Medium'
    return 'Low'


def guess_type(dom):
    d = dom.lower()
    if d.endswith('.edu') or d.endswith('.gov') or '.k12.' in d:
        return 'Education / .edu / .gov'
    for t, words in TYPES.items():
        if any(w in d for w in words):
            return t
    if d.endswith('.org'):
        return 'Association / chamber / nonprofit'
    return 'Other'


def parse_map(items):
    out = {}
    for it in items or []:
        if '=' not in it:
            raise SystemExit(f'--map {it}: use label.field="Column name"')
        k, v = it.split('=', 1)
        out[k.strip()] = v.strip().strip('"')
    return out


def load(path, label, overrides):
    df = read_table(path)
    cols = resolve(df, SPEC[label], label, overrides)
    return df, cols


def col(df, c, conv=None):
    if not c:
        return pd.Series([None] * len(df), index=df.index)
    s = df[c]
    return s.map(conv) if conv else s


def domain_cols(df, domains):
    """Columns in a gap export that belong to each domain (header contains the domain)."""
    out = {}
    for d in domains:
        cd = canon(d)
        for c in df.columns:
            if cd and cd in canon(c):
                out[d] = c
                break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--backlinks', required=True)
    for f in ['refdomains', 'broken', 'compare', 'audit', 'gsc-links', 'redirect-map']:
        ap.add_argument('--' + f)
    ap.add_argument('--gap', action='append', default=[])
    ap.add_argument('--gap-pages', action='append', default=[])
    ap.add_argument('--map', action='append')
    a = ap.parse_args()
    if not a.gap:
        raise SystemExit('--gap is required: attach the link gap export (Semrush Backlink Gap, Ahrefs Link Intersect).')
    cfg = load_json(a.config)
    for k in ['client', 'domain', 'tool', 'competitors', 'brand_terms', 'manual_action']:
        if k not in cfg:
            raise SystemExit(f'config.json needs "{k}"')
    os.makedirs(a.out, exist_ok=True)
    ov = parse_map(a.map)
    client = bare_domain(cfg['domain'])
    comps = [bare_domain(c) for c in cfg['competitors']]
    brand = [b.lower() for b in cfg['brand_terms']] + [client.split('.')[0]]
    metric = 'DR' if cfg['tool'].lower().startswith('a') else 'AS'
    strong_toxic = float(cfg.get('toxic_threshold', 60))
    notes, summary = [], {'metric': metric, 'tool': cfg['tool'], 'optional_not_attached': []}
    print('Loading exports')

    # ------------------------------------------------ client referring domains (optional: derived from backlinks)
    ref = pd.DataFrame(columns=['domain', 'authority', 'traffic', 'links'])
    if a.refdomains:
        df, c = load(a.refdomains, 'refdomains', ov)
        ref = pd.DataFrame({'domain': col(df, c['domain'], reg_domain), 'authority': col(df, c['authority'], num),
                            'traffic': col(df, c['traffic'], num), 'links': col(df, c['links'], num)})
        ref = ref.sort_values('authority', ascending=False).drop_duplicates('domain')
    else:
        summary['optional_not_attached'].append('client referring domains (derived from the backlinks export)')
    ref_auth = dict(zip(ref['domain'], ref['authority']))
    ref_traffic = dict(zip(ref['domain'], ref['traffic']))
    client_refs = set(ref['domain'])

    # ------------------------------------------------ client backlinks
    df, c = load(a.backlinks, 'backlinks', ov)
    links = pd.DataFrame({
        'source_url': col(df, c['source_url']), 'target_url': col(df, c['target_url'], norm_url),
        'anchor': col(df, c['anchor']).fillna('').astype(str) if c['anchor'] else '',
        'title': col(df, c['title']).fillna('') if c['title'] else '',
        'authority': col(df, c['authority'], num), 'traffic': col(df, c['traffic'], num),
        'nofollow': col(df, c['nofollow'], truthy) if c['nofollow'] else False,
        'sitewide': col(df, c['sitewide'], truthy) if c['sitewide'] else False,
        'first_seen': pd.to_datetime(col(df, c['first_seen']), errors='coerce', utc=True)
        if c['first_seen'] else pd.NaT,
        'lang': col(df, c['lang']).fillna('') if c['lang'] else '',
        'lost': col(df, c['lost']).fillna('') if c['lost'] else '',
    })
    if c['lost']:
        lost = links['lost'].astype(str).str.strip().str.lower()
        dropped = (~lost.isin(['', 'false', '0', 'no', 'live', 'active'])).sum()
        if dropped:
            links = links[lost.isin(['', 'false', '0', 'no', 'live', 'active'])]
            notes.append(f'Dropped {dropped:,} lost links from the backlinks export (export live links only).')
    links['domain'] = links['source_url'].map(reg_domain)
    links = links[links['domain'] != client]
    links['authority'] = links['authority'].fillna(links['domain'].map(ref_auth))
    links['traffic'] = links['traffic'].fillna(links['domain'].map(ref_traffic))
    links.to_csv(os.path.join(a.out, 'links.csv'), index=False)
    if not client_refs:
        client_refs = set(links['domain'])
    if links['authority'].isna().all():
        notes.append(f'{metric} is blank on the Disavow Review tab: the backlinks export has page-level scores '
                     f'only, not the linking domain\'s {metric}. Attach the referring domains export to fill it.')

    # ------------------------------------------------ Semrush Backlink Audit (optional)
    tox = {}
    if a.audit:
        df, c = load(a.audit, 'audit', ov)
        for _, r in df.iterrows():
            d = reg_domain(r[c['source_url']])
            score = num(r[c['toxic']]) if c['toxic'] else float('nan')
            mk = str(r[c['markers']]).strip() if c['markers'] else ''
            cur = tox.setdefault(d, {'score': float('nan'), 'markers': set()})
            if score == score and not (cur['score'] >= score):
                cur['score'] = score
            for m in re.split(r'[;,|]\s*', mk):
                if m:
                    cur['markers'].add(m)

    # ------------------------------------------------ GSC Links
    gsc = set()
    if a.gsc_links:
        df, c = load(a.gsc_links, 'gsc_links', ov)
        gsc = set(df[c['page']].map(reg_domain))
    else:
        summary['optional_not_attached'].append('GSC Links report (the "In GSC Links Report?" column stays blank)')
    if not a.audit:
        summary['optional_not_attached'].append('Semrush Backlink Audit (Tool Risk columns stay blank)')

    # ------------------------------------------------ Disavow Review candidates
    dis_rows, noise_domains = [], []
    if len(links):
        months = links['first_seen'].dropna().dt.strftime('%Y-%m') if links['first_seen'].notna().any() else None
        spike_months = {}
        if months is not None:
            per_month = links.dropna(subset=['first_seen']).assign(m=months).groupby('m')['domain'].nunique()
            med = per_month.median() if len(per_month) else 0
            for m, n in per_month.items():
                if n >= max(10, 3 * med):
                    spike_months[m] = int(n)
        nb = links[~links['anchor'].str.lower().apply(
            lambda x: any(b in x for b in brand) or bool(re.search(r'https?://|www\.|\.[a-z]{2,6}\b', x))
            or x.strip() in GENERIC)]
        anchor_domains = nb.groupby(nb['anchor'].str.lower().str.strip())['domain'].nunique()
        repeated = {k for k, v in anchor_domains.items() if v >= 3}
        extra_safe = set(bare_domain(d) for d in cfg.get('safe_domains', []))
        for dom, g in links.groupby('domain'):
            if dom in comps:
                continue
            if is_noise(dom) or (link_seller_text(g) and not is_safe(dom, extra_safe)):
                noise_domains.append(dom)
                continue
            if is_safe(dom, extra_safe):
                continue
            anchors = g['anchor'].str.strip()
            top_anchor = anchors[anchors != ''].mode().iloc[0] if (anchors != '').any() else ''
            text = ' '.join([dom] + g['source_url'].astype(str).head(20).tolist() + g['title'].astype(str).head(5).tolist())
            reasons, groups, strong = [], [], False
            sp = spam_hits(text)
            if sp:
                reasons.append('Spam topic (' + ', '.join(sp[:3]) + ')')
                groups.append('Spam topic: ' + sp[0])
                strong = True
            paid = has_any(text.lower(), PAID)
            if paid:
                reasons.append('Paid or guest-post page (' + paid[0] + ' in URL/title)')
                groups.append('Paid / guest post pages')
                strong = True
            commercial = []
            for an in anchors.str.lower().unique():
                if an in repeated:
                    commercial.append(an)
                elif an and an not in GENERIC and not any(b in an for b in brand) \
                        and not re.search(r'https?://|www\.|\.[a-z]{2,6}\b', an) and has_any(' ' + an + ' ', COMMERCIAL):
                    commercial.append(an)
            if commercial:
                rep = [x for x in commercial if x in repeated]
                if rep:
                    reasons.append(f'Commercial anchor "{rep[0]}" used by {anchor_domains[rep[0]]} different domains')
                    groups.append(f'Repeated anchor: {rep[0]}')
                    strong = True
                else:
                    reasons.append(f'Exact-match commercial anchor "{commercial[0]}"')
                    groups.append('Commercial anchors')
            tld = dom.rsplit('.', 1)[-1]
            if tld in SPAMMY_TLD:
                reasons.append(f'Spam-prone domain ending (.{tld})')
                groups.append(f'Spam-prone TLD (.{tld})')
            langs = set(x for x in g['lang'].astype(str).str.lower() if x and x not in ('en', 'english', 'nan'))
            if langs:
                reasons.append('Page language ' + ', '.join(sorted(langs)))
                groups.append('Foreign-language pages')
            n = len(g)
            if g['sitewide'].any() or n >= 50:
                reasons.append(f'Sitewide or repeated link ({n:,} links)')
                groups.append('Sitewide links')
            auth = g['authority'].max()
            traf = g['traffic'].max()
            if auth == auth and auth >= 30 and traf == traf and traf < 50:
                reasons.append(f'{metric} {auth:.0f} but almost no organic traffic ({traf:.0f})')
                groups.append(f'High {metric}, no traffic (possible network)')
            t = tox.get(dom)
            if t and t['score'] == t['score'] and t['score'] >= strong_toxic:
                reasons.append(f'Semrush risk score {t["score"]:.0f}')
                groups.append('Tool risk score')
            first = g['first_seen'].min()
            fm = first.strftime('%Y-%m') if pd.notna(first) else ''
            if reasons and fm in spike_months:
                reasons.append(f'First seen in a spike month ({spike_months[fm]} new referring domains in {fm})')
            if not reasons:
                continue
            dis_rows.append({
                'Referring Domain': dom, 'Example Linking URL': g['source_url'].iloc[0],
                'Client URL Linked To': g['target_url'].mode().iloc[0], 'Anchor Text (most common)': top_anchor,
                'Links from Domain': n, metric: auth, 'Domain Organic Traffic': traf,
                'Dofollow?': 'Yes' if (~g['nofollow'].astype(bool)).any() else 'No',
                'First Seen': first.strftime('%Y-%m-%d') if pd.notna(first) else '',
                'Tool Risk Score': (t['score'] if t else None), 'Tool Risk Markers': '; '.join(sorted(t['markers'])) if t else '',
                'In GSC Links Report?': ('Y' if dom in gsc else 'N') if gsc else '',
                'Why Flagged': '; '.join(reasons), 'Pattern Group': groups[0],
                'Suggested Status': 'Review closer' if (strong or len(reasons) >= 2) else 'Monitor',
            })
        summary['spike_months'] = spike_months
    dis = pd.DataFrame(dis_rows)
    dis.to_csv(os.path.join(a.out, 'disavow.csv'), index=False)
    save_json(os.path.join(a.out, 'noise.json'), sorted(noise_domains))
    summary['disavow_candidates'] = len(dis)
    summary['noise_domains'] = len(noise_domains)

    # ------------------------------------------------ broken backlinks
    rmap = {}
    if a.redirect_map:
        df, c = load(a.redirect_map, 'redirect_map', ov)
        rmap = {norm_url(s): norm_url(t) for s, t in zip(df[c['source']], df[c['target']]) if '*' not in str(s)}
    br_rows = []
    if a.broken:
        df, c = load(a.broken, 'broken', ov)
        b = pd.DataFrame({'target': col(df, c['target_url'], norm_url), 'code': col(df, c['code']),
                          'authority': col(df, c['authority'], num),
                          'source': col(df, c['source_url']) if c['source_url'] else None,
                          'refdomains': col(df, c['refdomains'], num)})
        b = b[b['target'].map(reg_domain) == reg_domain(client)]
        for tgt, g in b.groupby('target'):
            if c['source_url']:
                g = g.assign(domain=g['source'].map(reg_domain))
                g['authority'] = g['authority'].fillna(g['domain'].map(ref_auth))
                best = g.sort_values('authority', ascending=False).iloc[0]
                n_dom, best_dom, best_auth, ev = g['domain'].nunique(), best['domain'], best['authority'], best['source']
            else:
                n_dom = g['refdomains'].max()
                best_dom, best_auth, ev = '', float('nan'), ''
                if len(links):
                    lk = links[links['target_url'] == tgt]
                    if len(lk):
                        bl = lk.sort_values('authority', ascending=False).iloc[0]
                        best_dom, best_auth, ev = bl['domain'], bl['authority'], bl['source_url']
                        n_dom = max(n_dom if n_dom == n_dom else 0, lk['domain'].nunique())
            br_rows.append({'url': tgt, 'code': str(g['code'].iloc[0] or ''), 'refdomains': int(n_dom or 0),
                            'best_domain': best_dom, 'best_authority': best_auth, 'evidence': ev,
                            'map_target': rmap.get(tgt, '')})
    else:
        summary['optional_not_attached'].append('broken backlinks (derived: build.py finds them from the live status '
                                                'of every client URL the backlinks point at)')
    br = pd.DataFrame(br_rows, columns=['url', 'code', 'refdomains', 'best_domain', 'best_authority', 'evidence',
                                        'map_target'])
    br.sort_values(['refdomains', 'best_authority'], ascending=False).to_csv(os.path.join(a.out, 'broken.csv'), index=False)
    save_json(os.path.join(a.out, 'redirect_map.json'), rmap)
    summary['broken_urls_from_export'] = len(br)

    # ------------------------------------------------ link gap
    gap_rows = {}
    shared = Counter()
    client_in_gap = False  # True once any gap row shows the client linking (the Missing view never does)
    for path in a.gap:
        df, c = load(path, 'gap', ov)
        dcols = domain_cols(df, [client] + comps)
        missing = [d for d in comps if d not in dcols]
        if missing:
            notes.append(f'{os.path.basename(path)}: no column found for {", ".join(missing)}; '
                         f'competitor counts for them come from other gap files only.')
        for _, r in df.iterrows():
            dom = reg_domain(r[c['domain']])
            linked = [d for d in comps if d in dcols and num(r[dcols[d]]) > 0]
            client_has = client in dcols and num(r[dcols[client]]) > 0
            if client_has:
                client_in_gap = True
                for d in linked:
                    shared[d] += 1
            e = gap_rows.setdefault(dom, {'domain': dom, 'authority': float('nan'), 'traffic': float('nan'),
                                          'competitors': set(), 'client_links': False, 'evidence': ''})
            e['competitors'].update(linked)
            if not linked and c['matches']:
                e.setdefault('matches', num(r[c['matches']]))
            e['client_links'] = e['client_links'] or client_has
            au = num(r[c['authority']]) if c['authority'] else float('nan')
            if au == au:
                e['authority'] = au
            tr = num(r[c['traffic']]) if c['traffic'] else float('nan')
            if tr == tr:
                e['traffic'] = tr
    for path in a.gap_pages:
        df, c = load(path, 'gap_pages', ov)
        for u in df[c['source_url']]:
            d = reg_domain(u)
            if d in gap_rows and not gap_rows[d]['evidence']:
                gap_rows[d]['evidence'] = u

    # ------------------------------------------------ rollup
    # The client row comes from the backlinks export; competitor rows carry only their link-gap counts unless a
    # comparison export (optional) adds authority, referring domains, backlinks and traffic for them.
    nan = float('nan')
    derived = {'rd': links['domain'].nunique(), 'backlinks': len(links),
               'dof': links.loc[~links['nofollow'].astype(bool), 'domain'].nunique()}
    by, cc = {}, {}
    if a.compare:
        df = read_table(a.compare)
        if not any(canon(x) in [canon(x2) for x2 in df.columns] for x in SPEC['compare']['target'][0]):
            dc = domain_cols(df, [client] + comps)
            if len(dc) >= 2:  # metrics as rows, domains as columns: transpose
                first = df.columns[0]
                df = df.set_index(first).T.reset_index().rename(columns={'index': 'Target'})
                df['Target'] = df['Target'].astype(str)
        cc = resolve(df, SPEC['compare'], 'compare', ov)
        for _, r in df.iterrows():
            by[bare_domain(r[cc['target']])] = r
    else:
        summary['optional_not_attached'].append(
            'competitor comparison (competitor Referring Domains, Backlinks, traffic and Gap vs Client stay blank)')
    roll = []
    for d in [client] + comps:
        r = by.get(d)
        if r is None and by:
            r = next((v for k, v in by.items() if reg_domain(k) == reg_domain(d)), None)
        if r is None and a.compare:
            notes.append(f'Comparison export has no row for {d}.')
        g = (lambda f, r=r: num(r[cc[f]]) if cc.get(f) else nan) if r is not None else (lambda f: nan)
        rd, dof, bl = g('refdomains'), g('dofollow_refdomains'), g('backlinks')
        if rd != rd and dof == dof:
            notes.append('Comparison export has dofollow referring domains only; Referring Domains column uses them.')
            rd = dof
        if d == client:  # fill whatever the comparison lacks from the backlinks export
            rd = derived['rd'] if rd != rd else rd
            bl = derived['backlinks'] if bl != bl else bl
            dof = derived['dof'] if dof != dof else dof
        roll.append({'Domain': d, 'Client or Competitor': 'Client' if d == client else 'Competitor',
                     metric: g('authority'), 'Referring Domains': rd, 'Backlinks': bl,
                     'Dofollow Referring Domains': dof,
                     '% Dofollow': (dof / rd) if (rd == rd and dof == dof and rd) else None,
                     'Referring Domains Gained (90 days)': g('gained'), 'Referring Domains Lost (90 days)': g('lost'),
                     'Organic Traffic (tool estimate)': g('traffic')})
    roll = pd.DataFrame(roll)
    crd = roll.loc[roll['Client or Competitor'] == 'Client', 'Referring Domains'].iloc[0]
    gap_count = Counter()
    for e in gap_rows.values():
        if e['client_links'] or e['domain'] in client_refs:
            continue
        for d in e['competitors']:
            gap_count[d] += 1
    roll['Domains Linking to Them but Not the Client'] = roll['Domain'].map(
        lambda d: None if d == client else gap_count.get(d, 0))
    # With the Missing view the client column is all zeros, so "shared" would read 0 for everyone: leave it blank.
    roll['Shared Referring Domains with Client'] = roll['Domain'].map(
        lambda d: None if d == client or not client_in_gap else shared.get(d, 0))
    roll['Gap vs Client'] = roll.apply(lambda r: None if r['Domain'] == client else r['Referring Domains'] - crd, axis=1)
    comp_rows = roll[roll['Client or Competitor'] != 'Client'].assign(
        _g=lambda x: x['Domains Linking to Them but Not the Client'])
    roll = pd.concat([roll[roll['Client or Competitor'] == 'Client'],
                      comp_rows.sort_values(['Referring Domains', '_g'], ascending=False, na_position='last')
                      .drop(columns='_g')])
    blank = [k for k in roll.columns if roll[k].isna().all()]
    if blank:
        notes.append('Rollup columns left blank (not in the exports): ' + ', '.join(blank))
    if not a.compare:
        notes.append(f'Rollup client row is built from the backlinks export ({derived["rd"]:,} referring domains, '
                     f'{derived["backlinks"]:,} backlinks); competitor rows show link-gap counts only.')
    roll.to_csv(os.path.join(a.out, 'rollup.csv'), index=False)

    # ------------------------------------------------ opportunities
    opp, removed, gap_all = [], Counter(), []
    flagged = set(dis['Referring Domain']) if len(dis) else set()
    for dom, e in gap_rows.items():
        n = len(e['competitors']) or int(e.get('matches') or 0)
        why = None
        if e['client_links'] or dom in client_refs:
            why = 'already links to client'
        elif dom in comps or dom == client:
            why = 'competitor'
        elif is_noise(dom):
            why = 'noise'
        elif spam_hits(dom) or dom in flagged or has_any(dom, PAID):
            why = 'spam / flagged'
        elif junk_domain(dom):
            why = 'junk domain (spam TLD or SEO-tool name)'
        elif n < 1:
            why = 'links to no listed competitor'
        elif n == 1 and not (e['authority'] == e['authority'] and e['authority'] >= 40):
            why = 'one competitor, low authority'
        gap_all.append({'domain': dom, 'authority': e['authority'], 'traffic': e['traffic'], 'n_competitors': n,
                        'competitors': ', '.join(sorted(e['competitors'])), 'evidence': e['evidence'],
                        'removed_reason': why or ''})
        if why:
            removed[why] += 1
            continue
        t = guess_type(dom)
        auth = e['authority']
        opp.append({'domain': dom, 'authority': auth, 'traffic': e['traffic'], 'n_competitors': n,
                    'competitors': ', '.join(sorted(e['competitors'])), 'type_guess': t,
                    'priority': default_priority(n, auth, t), 'evidence': e['evidence']})
    opp = pd.DataFrame(opp, columns=['domain', 'authority', 'traffic', 'n_competitors', 'competitors', 'type_guess',
                                     'priority', 'evidence'])
    opp['_p'] = opp['priority'].map({'High': 0, 'Medium': 1, 'Low': 2})
    opp = opp.sort_values(['_p', 'n_competitors', 'authority'], ascending=[True, False, False]).drop(columns='_p')
    opp.to_csv(os.path.join(a.out, 'opportunities.csv'), index=False)
    pd.DataFrame(gap_all, columns=['domain', 'authority', 'traffic', 'n_competitors', 'competitors', 'evidence',
                                   'removed_reason']).to_csv(os.path.join(a.out, 'gap_all.csv'), index=False)
    summary['gap_domains'] = len(gap_rows)
    summary['opportunities_kept'] = len(opp)
    summary['opportunities_removed'] = dict(removed)

    # ------------------------------------------------ anchor mix (from the backlinks export)
    real = links[~links['domain'].isin(noise_domains)]
    if len(real):
        an = real['anchor'].astype(str).str.lower().str.strip()
        isbrand = an.map(lambda x: any(b in x for b in brand) or bool(re.search(r'https?://|www\.|\.[a-z]{2,6}\b', x)))
        iscomm = an.map(lambda x: not any(b in x for b in brand) and bool(has_any(' ' + x + ' ', COMMERCIAL)))
        summary['anchor_mix'] = {'basis': f'{len(real):,} links from non-noise domains',
                                 'branded_or_url_pct': round(100 * isbrand.mean(), 1),
                                 'commercial_pct': round(100 * iscomm.mean(), 1)}

    # ------------------------------------------------ URLs to check live
    # Every client URL a backlink points at: build.py finds the broken ones from these results.
    targets = {t for t in links['target_url'] if t and reg_domain(t) == reg_domain(client)}
    need = targets | set(br['url']) | set(x for x in br['map_target'] if x) | {f'https://{client}/'}
    with open(os.path.join(a.out, 'status_needed.txt'), 'w') as f:
        f.write('\n'.join(sorted(need)) + '\n')
    summary['client_target_urls'] = len(targets)
    summary['notes'] = notes
    save_json(os.path.join(a.out, 'prep_summary.json'), summary)

    print('\nSummary')
    for k in ['disavow_candidates', 'noise_domains', 'client_target_urls', 'gap_domains', 'opportunities_kept']:
        print(f'  {k}: {summary.get(k)}')
    print(f'  opportunities removed: {dict(removed)}')
    if summary.get('anchor_mix'):
        print(f'  anchor mix: {summary["anchor_mix"]}')
    if summary.get('spike_months'):
        print(f'  spike months: {summary["spike_months"]}')
    for n in notes:
        print('  NOTE:', n)
    if summary['optional_not_attached']:
        print('  Not attached (optional):', '; '.join(summary['optional_not_attached']))
    print(f'\nNext: check the {len(need)} URLs in {a.out}/status_needed.txt in the Composio workbench '
          f'(references/composio.md) and save the result as {a.out}/status.tsv')


if __name__ == '__main__':
    main()
