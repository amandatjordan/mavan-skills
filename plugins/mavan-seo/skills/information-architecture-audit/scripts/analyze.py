#!/usr/bin/env python3
"""IA audit analysis: page types, topics, duplicate intent, paths, links and suggested actions.

Usage:
  python analyze.py --work work

Reads   work/config.json, work/crawl_pages.csv, work/links.csv, work/redirects.csv,
        work/prep_report.json, work/gsc/*.csv (optional) and work/decisions.json (optional).
Writes  work/analysis/*.csv (one per template tab or section), work/analysis/summary.json,
        and work/review/*.csv + work/review/next_steps.md for the reviewer.

Run it, review work/review/, put corrections in work/decisions.json, and run it again until the
review files hold nothing left to fix. Every run starts from the exports, so it is safe to repeat.
"""
import argparse
import collections
import json
import os
import re
import statistics
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_json, save_json  # noqa: E402

# ---------------------------------------------------------------- vocab
QUESTION_WORDS = {'what', 'how', 'why', 'can', 'is', 'are', 'does', 'do', 'should', 'when', 'which', 'where', 'who'}
BLOG_PHRASES = ['vs', 'versus', 'benefits', 'benefit', 'guide', 'tips', 'cost', 'costs', 'explained', 'what to expect',
                'reasons', 'aftercare', 'before and after', 'myths', 'myth']
COMPANY_WORDS = {'about', 'contact', 'team', 'staff', 'meet', 'doctor', 'doctors', 'providers', 'reviews', 'review',
                 'testimonials', 'financing', 'finance', 'shop', 'store', 'membership', 'memberships', 'package',
                 'packages', 'gallery', 'press', 'media', 'careers', 'jobs', 'faq', 'faqs', 'book', 'booking',
                 'appointment', 'appointments', 'events', 'event', 'specials', 'offers', 'promotions', 'parties',
                 'gift', 'giftcards', 'giftcard', 'consultation', 'pricing', 'prices'}
UTILITY_WORDS = {'privacy', 'terms', 'hipaa', 'thank', 'thanks', 'thankyou', 'sitemap', 'test', 'accessibility',
                 'disclaimer', 'cookie', 'cookies', 'policy', 'policies', 'cancellation', 'template', 'login',
                 'cart', 'checkout', 'account', 'search', 'unsubscribe', 'confirmation'}
UTILITY_PHRASES = ['thank-you', 'privacy-policy', 'terms-of', 'terms-and', 'no-show', 'site-map', 'test-page']
ARCHIVE_FOLDERS = {'tag', 'tags', 'category', 'categories', 'author', 'authors', 'archive', 'archives', 'feed', 'date'}
GALLERY_FOLDERS = {'gallery', 'galleries', 'before-after', 'before-and-after', 'before-after-gallery',
                   'before-and-after-gallery', 'photo-gallery', 'portfolio', 'results', 'attachment', 'case', 'cases'}
SERVICE_FOLDERS = {'services', 'service', 'treatments', 'treatment', 'procedures', 'procedure'}
CONCERN_FOLDERS = {'concerns', 'concern', 'conditions', 'condition'}
BLOG_FOLDERS = {'blog', 'blogs', 'articles', 'article', 'news', 'resources', 'journal', 'insights', 'posts', 'post'}
LOCATION_FOLDERS = {'locations', 'location', 'areas', 'service-areas', 'areas-we-serve'}
BUSINESS_WORDS = {'med', 'spa', 'medspa', 'medical', 'clinic', 'aesthetics', 'aesthetic', 'plastic', 'surgery',
                  'surgeon', 'cosmetic', 'dermatology', 'dentist', 'dental', 'wellness', 'center', 'centre', 'and',
                  'near', 'me', 'best', 'the', 'in', 'of', 'top', 'office', 'practice', 'areas', 'we', 'serve'}
FILLER = {'in', 'near', 'me', 'treatment', 'treatments', 'services', 'service', 'the', 'a', 'an', 'best', 'top',
          'and', 'for', 'of', 'with', 'your', 'our', 'procedure', 'procedures'}
TOPIC_STRIP = {'near', 'me', 'best', 'the', 'in', 'top', 'and', 'of', 'a', 'for', 'your', 'our'}
INFO_ANCHOR = re.compile(r'\b(how|what|why|guide|cost|costs|vs|versus|benefits?|tips)\b', re.I)
COMMERCIAL = {'Home', 'Service hub', 'Service', 'Service-like (no folder)', 'Concern hub', 'Concern',
              'Location / Area', 'Location hub'}
CONTENT = {'Service', 'Service-like (no folder)', 'Concern', 'Blog', 'Location / Area'}
KEEPER_RANK = {'Service': 0, 'Service-like (no folder)': 1, 'Concern': 2, 'Location / Area': 3, 'Blog': 5}
FLOW_COLS = ['Home', 'Service hub', 'Service', 'Service-like', 'Concern hub', 'Concern', 'Location / Area', 'Blog hub',
             'Blog', 'Company / Info', 'Utility / Policy', 'Pagination', 'Query-string URL']
NOOWNER_MIN_IMPR = 100  # a search with fewer impressions in the window is not listed
# Words a person may use for a folder type in the confirmed mapping (decisions.json folder_types).
HUB_BASE = {'service': 'Service', 'service hub': 'Service', 'concern': 'Concern', 'concern hub': 'Concern',
            'blog': 'Blog', 'blog hub': 'Blog', 'location': 'Location', 'location / area': 'Location',
            'location hub': 'Location', 'service-like (no folder)': 'Service-like (no folder)'}
FLAT_TYPES = {'archive': 'Archive', 'gallery item': 'Gallery item', 'company / info': 'Company / Info',
              'utility / policy': 'Utility / Policy', 'pagination': 'Pagination', 'query-string url': 'Query-string URL'}
US_STATES = {'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga', 'hi', 'id', 'il', 'in', 'ia', 'ks', 'ky', 'la',
             'me', 'md', 'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 'nh', 'nj', 'nm', 'ny', 'nc', 'nd', 'oh', 'ok',
             'or', 'pa', 'ri', 'sc', 'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy', 'dc'}


def words(s):
    return re.findall(r'[a-z0-9]+', str(s).lower())


def segs(k):
    return [p for p in k.split('/') if p] if k.startswith('/') else []


def last_slug(k):
    s = segs(k)
    return s[-1] if s else ''


def num(x, default=0):
    try:
        v = float(x)
        return default if v != v else v
    except (TypeError, ValueError):
        return default


def median(vals):
    vals = [v for v in vals if v is not None and v == v]
    return round(statistics.median(vals), 1) if vals else ''


def folder_label(f):
    return f.replace('-', ' ').replace('_', ' ').capitalize() + ' (folder)'


# ---------------------------------------------------------------- classification
class Classifier:
    def __init__(self, live_keys, cfg, dec):
        self.live = set(live_keys)
        self.city_words = set()
        for c in [cfg.get('city', '')] + list(cfg.get('other_cities', [])):
            self.city_words |= set(words(c))
        self.state_words = {w for w in self.city_words if w in US_STATES}
        self.city_words -= {'and', 'the'}
        self.main_city = set(words(cfg.get('city', ''))) - self.state_words
        self.folder_types = {k.strip('/').lower(): v for k, v in dec.get('folder_types', {}).items()}
        # True once a person has confirmed the folder-to-type mapping (profile.py proposes it). Then folder
        # names are never guessed: only the confirmed mapping decides a folder's type.
        self.confirmed = bool(dec.get('mapping_confirmed'))
        self.overrides = dec.get('page_types', {})
        # folders that have children -> their in-folder parents act as hubs
        self.parents = set()
        for k in self.live:
            s = segs(k)
            for i in range(1, len(s)):
                self.parents.add('/' + '/'.join(s[:i]) + '/')

    def cities_in(self, text):
        """City words (not state codes) found in text."""
        return set(words(text)) & (self.city_words - self.state_words)

    def classify(self, k, raw, h1, title):
        if k in self.overrides:
            return self.overrides[k], 'Set by reviewer'
        s = segs(k)
        rl = str(raw).lower()
        if k == '/' and '?' not in rl:
            return 'Home', 'Rule 1: the homepage'
        if re.search(r'[?&](page|paged|pg)=\d+', rl) or re.search(r'/page/\d+/?$', k):
            return 'Pagination', 'Rule 2: ?page= or /page/N/'
        if '?' in rl:
            return 'Query-string URL', 'Rule 2: URL has a query string'
        if not s:
            return 'Unclassified', 'Not on the main domain'
        if self.confirmed:
            hit = self.classify_mapped(k, s)
            if hit:
                return hit
            return self.root_rules(s[-1], h1, utility=True)
        f0 = s[0]
        if f0 in ARCHIVE_FOLDERS or (re.fullmatch(r'(19|20)\d\d', f0) and len(s) <= 3):
            return 'Archive', f'Rule 3: /{f0}/ CMS archive'
        if f0 == 'attachment' or 'attachment' in s or (f0 in GALLERY_FOLDERS and len(s) >= 2):
            return 'Gallery item', f'Rule 4: entry inside /{f0}/'
        if f0 in GALLERY_FOLDERS and len(s) == 1:
            return 'Company / Info', 'Rule 4: main gallery page'
        slug = s[-1]
        sw = set(words(slug))
        if sw & UTILITY_WORDS or any(p in slug for p in UTILITY_PHRASES):
            return 'Utility / Policy', 'Rule 5: utility/policy wording in the slug'
        # rule 6: folders
        if len(s) >= 2 or f0 in self.folder_types or f0 in (SERVICE_FOLDERS | CONCERN_FOLDERS | BLOG_FOLDERS | LOCATION_FOLDERS):
            ftype = self.folder_types.get(f0)
            is_hub = len(s) == 1 or k in self.parents
            if ftype is None:
                if f0 in SERVICE_FOLDERS:
                    ftype = 'Service'
                elif f0 in CONCERN_FOLDERS:
                    ftype = 'Concern'
                elif f0 in BLOG_FOLDERS:
                    ftype = 'Blog'
                elif f0 in LOCATION_FOLDERS:
                    ftype = 'Location'
                elif f0 in COMPANY_WORDS or set(words(f0)) & COMPANY_WORDS:
                    return 'Company / Info', f'Rule 6: inside the /{f0}/ company folder'
                else:
                    if len(s) == 1:
                        pass  # a root page that merely has children: fall through to rule 7
                    else:
                        return folder_label(f0), f'Rule 6: other folder /{f0}/'
            if ftype:
                if ftype == 'Location':
                    return ('Location hub' if is_hub else 'Location / Area'), f'Rule 6: /{f0}/ folder' + (' hub' if is_hub else '')
                if is_hub:
                    why = f'Rule 6: /{f0}/ listing' if len(s) == 1 else f'Rule 6: /{f0}/ category page with pages under it'
                    return f'{ftype} hub', why
                return ('Service-like (no folder)' if ftype == 'Service-like (no folder)' else ftype), f'Rule 6: inside /{f0}/'
        return self.root_rules(slug, h1)

    def classify_mapped(self, k, s):
        """A page in a folder the person mapped. Returns None for root-level pages and for folders mapped
        as Mixed, which fall through to the content rules."""
        f0 = s[0]
        two = f'{s[0]}/{s[1]}' if len(s) >= 2 else ''
        if two and two in self.folder_types:  # a second-level folder mapped on its own ("folder/subfolder")
            raw, tag, at_top = self.folder_types[two], two, len(s) == 2
        else:
            raw, tag, at_top = self.folder_types.get(f0), f0, len(s) == 1
        if raw is None:
            if len(s) == 1:
                return None  # root-level page with no folder
            return folder_label(f0), f'Folder /{f0}/ is not in the confirmed mapping'
        low = str(raw).strip().lower()
        if low == 'mixed':
            return None
        is_hub = at_top or k in self.parents
        f0 = tag
        if low in FLAT_TYPES:
            t = FLAT_TYPES[low]
            if t == 'Gallery item' and at_top:
                return 'Company / Info', f'Confirmed mapping: /{f0}/ main gallery page'
            return t, f'Confirmed mapping: /{f0}/ = {t}'
        if low in HUB_BASE:
            base = HUB_BASE[low]
            if base == 'Location':
                return ('Location hub' if is_hub else 'Location / Area'), \
                    f'Confirmed mapping: /{f0}/ = Location' + (' hub' if is_hub else '')
            if base == 'Service-like (no folder)':
                return base, f'Confirmed mapping: /{f0}/ = {base}'
            if is_hub:
                return f'{base} hub', f'Confirmed mapping: /{f0}/ = {base}, ' + \
                    ('listing page' if at_top else 'category page with pages under it')
            return base, f'Confirmed mapping: /{f0}/ = {base}'
        label = str(raw).strip()
        if not label.endswith('(folder)'):
            label += ' (folder)'
        return label, f'Confirmed mapping: /{f0}/ is its own type'

    def root_rules(self, slug, h1, utility=False):
        """Content rules for root-level pages and folders mapped as Mixed."""
        sw = set(words(slug))
        if utility and (sw & UTILITY_WORDS or any(p in slug for p in UTILITY_PHRASES)):
            return 'Utility / Policy', 'Content rule: utility/policy wording in the slug'
        if sw & COMPANY_WORDS:
            return 'Company / Info', 'Rule 7: company/info wording in the slug'
        toks = words(slug)
        rest = [t for t in toks if t not in self.city_words and t not in BUSINESS_WORDS]
        if (set(toks) & self.city_words and not rest) or slug == 'areas-we-serve':
            return 'Location / Area', 'Rule 7: business words + city only'
        h1l = str(h1).strip().lower()
        text = ' '.join(toks)
        h1w = ' '.join(words(h1))
        if toks and toks[0] in QUESTION_WORDS:
            return 'Blog', f'Rule 7: slug starts with "{toks[0]}"'
        if len(toks) >= 6:
            return 'Blog', f'Rule 7: slug has {len(toks)} words'
        for p in BLOG_PHRASES:
            if re.search(r'\b' + p + r'\b', text) or re.search(r'\b' + p + r'\b', h1w):
                return 'Blog', f'Rule 7: blog wording "{p}"'
        if h1l.endswith('?'):
            return 'Blog', 'Rule 7: H1 is a question'
        if toks and len(toks) <= 5:
            return 'Service-like (no folder)', 'Rule 7: short root slug' + (' with a city' if set(toks) & self.city_words else '')
        return 'Unclassified', 'No rule matched'


# ---------------------------------------------------------------- topics
class Topics:
    def __init__(self, clf, dec):
        self.clf = clf
        self.vocab = {}  # phrase -> topic
        self.syn = {t.lower(): [p.lower() for p in ps] for t, ps in dec.get('synonyms', {}).items()}
        for t in dec.get('extra_topics', []):
            self.add(t.lower(), t.lower())

    def clean(self, text):
        toks = [t for t in words(text) if t not in self.clf.city_words and t not in TOPIC_STRIP]
        return ' '.join(toks)

    def add(self, phrase, topic):
        phrase = phrase.strip()
        if phrase and len(phrase) > 2:
            self.vocab.setdefault(phrase, topic)
            if ' ' in phrase:
                self.vocab.setdefault(phrase.replace(' ', ''), topic)

    def build(self, service_pages):
        for k in service_pages:
            t = self.clean(last_slug(k))
            if t:
                self.add(t, t)
        for t, ps in self.syn.items():  # reviewer synonyms override phrases taken from slugs
            for p in [t] + ps:
                p = p.strip()
                if p:
                    self.vocab[p] = t
                    if ' ' in p:
                        self.vocab[p.replace(' ', '')] = t
        self.pat = sorted(self.vocab, key=len, reverse=True)

    def match(self, text):
        """Longest vocabulary phrase found in text (patterns are sorted longest first)."""
        t = ' ' + ' '.join(words(text)) + ' '
        tj = t.replace(' ', '')
        for p in self.pat:
            if (' ' + p + ' ') in t or (len(p) >= 6 and ' ' not in p and p in tj):
                return self.vocab[p]
        return ''

    def topic_for(self, k, ptype, h1, title):
        if ptype in ('Service', 'Service-like (no folder)'):
            own = self.clean(last_slug(k))
            m = self.match(own)
            return m or own
        if ptype not in CONTENT and ptype not in ('Service hub', 'Concern hub'):
            return ''
        for text in (last_slug(k).replace('-', ' '), h1, re.split(r'\s[|\-–]\s', str(title))[0]):
            m = self.match(text)
            if m:
                return m
        return self.clean(last_slug(k)) if ptype in ('Concern', 'Location / Area') else ''


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work')
    ap.add_argument('--past', help='optional past prune decisions CSV (url, decision, target)')
    ap.add_argument('--allow-unconfirmed', action='store_true',
                    help='run without a confirmed folder mapping (folder types guessed from common names); '
                         'for tests and unattended runs only')
    a = ap.parse_args()
    W = a.work
    A = os.path.join(W, 'analysis'); R = os.path.join(W, 'review')
    os.makedirs(A, exist_ok=True); os.makedirs(R, exist_ok=True)
    cfg = load_json(os.path.join(W, 'config.json'))
    if not cfg:
        sys.exit(f'Missing {W}/config.json')
    dec = load_json(os.path.join(W, 'decisions.json'), {})
    if not dec.get('mapping_confirmed') and not a.allow_unconfirmed:
        sys.exit('The folder-to-type mapping has not been confirmed. Run folder_profile.py, show work/review/folder_mapping.md '
                 'to the person and STOP until they confirm or correct it. Then put their mapping in work/decisions.json '
                 'as "folder_types" and add "mapping_confirmed": true.')
    prep = load_json(os.path.join(W, 'prep_report.json'), {})
    crawl = pd.read_csv(os.path.join(W, 'crawl_pages.csv'), dtype={'url': str, 'key': str}, keep_default_na=False)
    links = pd.read_csv(os.path.join(W, 'links.csv'), keep_default_na=False)
    redir = pd.read_csv(os.path.join(W, 'redirects.csv'), keep_default_na=False)
    G = os.path.join(W, 'gsc')
    gsc = {n: pd.read_csv(os.path.join(G, f'{n}.csv'), keep_default_na=False)
           for n in ['meta', 'pages', 'pairs', 'noowner', 'home', 'pair_queries']
           if os.path.exists(os.path.join(G, f'{n}.csv'))}
    has_gsc = 'pages' in gsc
    meta = dict(zip(gsc['meta'].key, gsc['meta'].value)) if 'meta' in gsc else {}
    utm_lines = gsc['meta'][gsc['meta'].key == 'utm_home'].value.tolist() if 'meta' in gsc else []
    notes = []
    if not dec.get('mapping_confirmed'):
        notes.append('The folder-to-type mapping was not confirmed by a person: folder types were guessed from common '
                     'folder names. Treat the page types as unverified.')

    crawl['status'] = pd.to_numeric(crawl.status, errors='coerce')
    status_of = {}
    for r in crawl.itertuples():
        if not r.has_query or str(r.has_query) == 'False':
            status_of.setdefault(r.key, int(r.status) if r.status == r.status else 0)
    live_df = crawl[crawl.status == 200].copy()
    live_df['dupe_key'] = live_df.duplicated('key', keep='first') & ~live_df.has_query.astype(str).eq('True')
    live_keys = set(live_df[~live_df.has_query.astype(str).eq('True')].key)
    redirect_final = dict(zip(redir.source, redir.final))

    def resolve(k, n=0):
        while k in redirect_final and n < 10:
            k = redirect_final[k]; n += 1
        return k

    clf = Classifier(live_keys, cfg, dec)
    rows = []
    for r in live_df.itertuples():
        t, why = clf.classify(r.key, r.url, r.h1, r.title)
        rows.append((t, why))
    live_df['type'] = [x[0] for x in rows]
    live_df['why'] = [x[1] for x in rows]
    type_of = {r.key: r.type for r in live_df.itertuples() if str(r.has_query) != 'True'}

    # topics
    tp = Topics(clf, dec)
    tp.build([k for k, t in type_of.items() if t in ('Service', 'Service-like (no folder)')])
    topic_over = dec.get('topics', {})
    live_df['topic'] = [topic_over.get(r.key, tp.topic_for(r.key, r.type, r.h1, r.title)) for r in live_df.itertuples()]
    topic_of = {r.key: r.topic for r in live_df.itertuples() if str(r.has_query) != 'True'}

    # service page per topic: Service first, then Service-like, then most impressions later
    gp = None
    if has_gsc:
        gp = gsc['pages'].copy()
        for c in ['clicks', 'impressions', 'position', 'top_query_impr', 'nonbrand_query_impr', 'ga4_sessions',
                  'ga4_key_events']:
            gp[c] = pd.to_numeric(gp[c], errors='coerce')
        gid = dict(zip(gp.id.astype(int), gp.key))
        gd = gp.set_index('key').to_dict('index')
    else:
        gid, gd = {}, {}
        notes.append('No Search Console data was loaded, so clicks, impressions, prune candidates and duplicate intent by search overlap are missing.')

    def g(k, f, default=0):
        v = gd.get(k, {}).get(f, default)
        return default if v != v else v

    service_for = {}
    for k, t in sorted(type_of.items(), key=lambda kv: (KEEPER_RANK.get(kv[1], 9), -g(kv[0], 'impressions'))):
        if t in ('Service', 'Service-like (no folder)') and topic_of.get(k):
            service_for.setdefault(topic_of[k], k)
    for t, k in dec.get('service_pages', {}).items():
        service_for[t] = k

    # ---------------- link metrics
    L = links[links.src.isin(live_keys) & (links.src != links.dst)].copy()
    L['src_type'] = L.src.map(type_of).fillna('')
    body = L[L.cls == 'Body']
    body_nonarch = body[body.src_type != 'Archive']
    nav = L[L.cls == 'Nav']
    foot = L[L.cls == 'Footer']
    body_in = body_nonarch.groupby('dst').src.nunique().to_dict()
    body_in_arch = body[body.src_type == 'Archive'].groupby('dst').src.nunique().to_dict()
    nav_in = nav.groupby('dst').src.nunique().to_dict()
    nav_raw = nav.groupby('dst').raw_count.sum().to_dict()
    foot_in = foot.groupby('dst').src.nunique().to_dict()
    body_out = body.groupby('src').dst.apply(set).to_dict()
    body_in_srcs = body.groupby('dst').src.apply(lambda s: sorted(set(s))).to_dict()

    # ---------------- blog / service folders
    def first_folder(k):
        s = segs(k)
        return '/' + s[0] + '/' if len(s) >= 2 else ''
    blog_folders = collections.Counter(first_folder(k) for k, t in type_of.items() if t == 'Blog' and first_folder(k))
    blog_folder = dec.get('blog_folder') or (blog_folders.most_common(1)[0][0] if blog_folders else '')
    if not blog_folder:
        hub = [k for k, t in type_of.items() if t == 'Blog hub']
        blog_folder = hub[0] if hub else ''
    svc_folders = collections.Counter(first_folder(k) for k, t in type_of.items() if t == 'Service' and first_folder(k))
    service_folder = dec.get('service_folder') or (svc_folders.most_common(1)[0][0] if svc_folders else '')
    formula_blog_prefixes = ('/blog/', '/blogs/', '/articles/', '/news/', '/resources/')
    if blog_folder and blog_folder not in formula_blog_prefixes:
        notes.append(f'The blog folder is {blog_folder}, which the template Area formula does not know, so its posts '
                     f'will show as "Blog URLs" on All Pages. Edit the formula in the sheet or ignore those rows.')
    # a folder that only holds a listing page is a hub, not a blog folder
    blog_folder_has_posts = bool(blog_folder) and any(
        t == 'Blog' and k.startswith(blog_folder) for k, t in type_of.items())
    blog_hub = next((k for k, t in type_of.items() if t == 'Blog hub' and (not blog_folder or k == blog_folder)), '') or \
        next((k for k, t in type_of.items() if t == 'Blog hub'), '')
    service_hub = next((k for k, t in type_of.items() if t == 'Service hub' and segs(k) and len(segs(k)) == 1), '')

    # ---------------- duplicate intent
    ent = {}  # (a,b) -> evidence
    if has_gsc and 'pairs' in gsc:
        for r in gsc['pairs'].itertuples():
            ka, kb = gid.get(int(r.id_a)), gid.get(int(r.id_b))
            if not ka or not kb or ka not in live_keys or kb not in live_keys:
                continue
            if type_of.get(ka) not in CONTENT and not type_of.get(ka, '').endswith('(folder)'):
                continue
            if type_of.get(kb) not in CONTENT and not type_of.get(kb, '').endswith('(folder)'):
                continue
            ent[tuple(sorted((ka, kb)))] = {'overlap': float(r.overlap), 'shared': int(r.shared_queries),
                                            'impr': int(r.shared_impr), 'ids': (int(r.id_a), int(r.id_b)), 'h1': False}

    def h1_norm(h):
        return ' '.join(t for t in words(h) if t not in clf.city_words and t not in FILLER)
    by_h1 = collections.defaultdict(list)
    for r in live_df.itertuples():
        if str(r.has_query) != 'True' and (r.type in CONTENT or r.type.endswith('(folder)')) and h1_norm(r.h1):
            by_h1[h1_norm(r.h1)].append(r.key)
    for h, ks in by_h1.items():
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                p = tuple(sorted((ks[i], ks[j])))
                if p in ent:
                    ent[p]['h1'] = True
                else:
                    ent[p] = {'overlap': 0, 'shared': 0, 'impr': 0, 'ids': None, 'h1': True}

    verdict_over = {}
    for kk, v in dec.get('pair_verdicts', {}).items():
        parts = [x.strip() for x in kk.split('|')]
        if len(parts) == 2:
            verdict_over[tuple(sorted(parts))] = v.lower()

    def topic_relation(t1, t2):
        """'same' = same treatment; 'subset' = one topic is the other plus words. A subset can be a
        product line (Restylane / Restylane Silk = same treatment) or a different treatment in the same
        area (breast / breast lift), so it is left for the reviewer."""
        if not t1 or not t2:
            return ''
        w1, w2 = set(t1.split()), set(t2.split())
        if w1 == w2:
            return 'same'
        if w1 < w2 or w2 < w1:
            return 'subset'
        return ''

    def conf(e):
        if e['shared'] >= 3 and e['overlap'] >= 0.5:
            return 'High'
        if e['shared'] >= 2 and e['overlap'] >= 0.3:
            return 'Medium'
        return 'Low'

    pair_rows, city_rows, dup_pairs = [], [], []
    for (ka, kb), e in sorted(ent.items(), key=lambda x: -x[1]['impr']):
        ta, tb = topic_of.get(ka, ''), topic_of.get(kb, '')
        ca, cb = clf.cities_in(ka), clf.cities_in(kb)
        rel = topic_relation(ta, tb)
        auto = 'not'
        if rel == 'same':
            auto = 'city' if (ca and cb and ca != cb) else 'duplicate'
        elif rel == 'subset':
            auto = 'check'
        v = verdict_over.get((ka, kb), auto)
        e['verdict'] = v
        e['auto'] = auto
        e['conf'] = 'Low' if v == 'review' else conf(e)  # 'review' = could not be judged: kept, but only as Review
        if v in ('duplicate', 'review'):
            dup_pairs.append((ka, kb, e))
        elif v == 'city':
            city_rows.append((ka, kb, e))
        pair_rows.append({'page_a': ka, 'page_b': kb, 'type_a': type_of.get(ka), 'type_b': type_of.get(kb),
                          'topic_a': ta, 'topic_b': tb, 'overlap': e['overlap'], 'shared_queries': e['shared'],
                          'shared_impr': e['impr'], 'same_h1': 'Yes' if e['h1'] else '', 'auto_verdict': auto,
                          'verdict': v, 'override_key': f'{ka} | {kb}'})

    # union-find groups over duplicate pairs
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for ka, kb, e in dup_pairs:
        parent[find(ka)] = find(kb)
    groups = collections.defaultdict(list)
    for x in list(parent):
        groups[find(x)].append(x)
    keeper_over = dec.get('keepers', {})
    group_rows, dup_of = [], {}
    gnum = 0
    rank = {'High': 3, 'Medium': 2, 'Low': 1}
    for members in sorted(groups.values(), key=lambda m: -sum(g(k, 'impressions') for k in m)):
        gnum += 1
        def kscore(k):
            other_city = bool(clf.cities_in(k) - clf.main_city) if clf.main_city else False
            return (KEEPER_RANK.get(type_of.get(k), 4), other_city, -g(k, 'impressions'), k)
        keeper = sorted(members, key=kscore)[0]
        topic = topic_of.get(keeper) or topic_of.get(members[0]) or ''
        if topic in keeper_over and keeper_over[topic] in members:
            keeper = keeper_over[topic]
        best = {}  # page -> (confidence, pair) of its strongest pair inside the group
        for ka, kb, e in dup_pairs:
            if ka in members and kb in members:
                for x in (ka, kb):
                    if x not in best or rank[e['conf']] > rank[best[x][0]]:
                        best[x] = (e['conf'], e)
        gconf = max((best[m][0] for m in members if m in best), key=lambda c: rank[c], default='Low')
        k_clicks = g(keeper, 'clicks')
        for m in sorted(members, key=lambda x: (x != keeper, -g(x, 'impressions'))):
            c, e = best.get(m, ('Low', None))
            role = 'Keeper' if m == keeper else 'Competitor'
            if role == 'Keeper':
                action = 'Keep'
            else:
                action = 'Merge then Redirect' if c in ('High', 'Medium') else 'Review'
            outranks = 'Yes' if (role == 'Competitor' and type_of.get(m) == 'Blog' and
                                 type_of.get(keeper) in ('Service', 'Service-like (no folder)') and g(m, 'clicks') > k_clicks) else ''
            ev = ''
            if e:
                ev = (f"Overlap {e['overlap']:.2f} on {e['shared']} searches" if e['shared'] else '') + \
                     ('; same H1' if e['h1'] else '')
                ev = ev.strip('; ') or 'Same H1'
            group_rows.append({'group': gnum, 'treatment': topic, 'group_confidence': gconf, 'keeper': keeper,
                               'page': m, 'page_type': type_of.get(m), 'role': role, 'clicks': g(m, 'clicks'),
                               'impressions': g(m, 'impressions'), 'best_overlap': e['overlap'] if e else '',
                               'shared_queries': e['shared'] if e else '', 'shared_impr': e['impr'] if e else '',
                               'evidence': ev, 'outranks': outranks, 'action': action, 'conf': c})
            n_other = len(members) - 1
            tname = (topic or 'Same topic').capitalize()
            if role == 'Keeper':
                note = f'{tname} - keeper; {n_other} other page{"s" if n_other > 1 else ""} compete for the same searches. Keep it.'
            elif action == 'Merge then Redirect':
                note = f'{tname} - competes with {keeper} for the same searches. Merge into it.'
            else:
                note = f'{tname} - same heading as {keeper} but little search overlap. Review before merging.'
            dup_of[m] = {'note': note, 'action': action, 'target': '' if role == 'Keeper' else keeper}

    # pair queries for the evidence table
    pq = {}
    if 'pair_queries' in gsc:
        for r in gsc['pair_queries'].itertuples():
            pq[tuple(sorted((int(r.id_a), int(r.id_b))))] = r.top_shared
    need_pq = []
    for ka, kb, e in dup_pairs + city_rows:
        if e['ids'] and tuple(sorted(e['ids'])) not in pq:
            need_pq.append(e['ids'])

    def topq(e):
        return pq.get(tuple(sorted(e['ids'])), '') if e and e['ids'] else ''
    # evidence rows (duplicate pairs only) and city rows
    evid_rows = []
    for ka, kb, e in dup_pairs:
        evid_rows.append({'treatment': topic_of.get(ka) or topic_of.get(kb), 'page_a': ka, 'page_b': kb,
                          'confidence': e['conf'], 'overlap': e['overlap'] or '', 'shared_queries': e['shared'] or '',
                          'shared_impr': e['impr'] or '', 'evidence': ('Search overlap' if e['shared'] else '') +
                          (' + same H1' if e['h1'] and e['shared'] else 'Same H1 only' if e['h1'] else ''),
                          'top_shared': topq(e)})
    city_out = [{'page_a': ka, 'page_b': kb, 'overlap': e['overlap'] or '', 'shared_queries': e['shared'] or '',
                 'shared_impr': e['impr'] or '', 'top_shared': topq(e),
                 'note': 'Same treatment, different city. Needs a policy decision, not an automatic merge.'}
                for ka, kb, e in city_rows]
    # group rows: top shared queries via best pair
    best_pair_of = {}
    for ka, kb, e in dup_pairs:
        for x in (ka, kb):
            if x not in best_pair_of or e['impr'] > best_pair_of[x]['impr']:
                best_pair_of[x] = e
    for row in group_rows:
        row['top_shared'] = topq(best_pair_of.get(row['page']))

    # searches with no owner
    noowner_rows = []
    if 'noowner' in gsc:
        for r in gsc['noowner'].itertuples():
            if num(r.impressions) < NOOWNER_MIN_IMPR:
                continue
            pg = []
            for part in str(r.top_pages).split(';'):
                if ':' in part:
                    i, v = part.split(':', 1)
                    k = gid.get(int(i))
                    if k:
                        pg.append((k, int(num(v))))
            content = [(k, v) for k, v in pg if type_of.get(k) in CONTENT or str(type_of.get(k, '')).endswith('(folder)')]
            tops = {topic_of.get(k) for k, v in content if topic_of.get(k)}
            if len(tops) < 3:
                continue
            q = str(r.query)
            owner = next((k for k, v in sorted(content, key=lambda x: -x[1])
                          if topic_of.get(k) and topic_of[k] in ' '.join(words(q))), '')
            generic = ' '.join(t for t in words(q) if t not in clf.city_words and t not in TOPIC_STRIP)
            sugg = (f'Make {owner} the owner: link to it from the other pages' if owner
                    else f'Create one hub page for "{generic}" and link the treatments from it')
            noowner_rows.append({'query': q, 'impressions': int(num(r.impressions)), 'pages': int(num(r.pages)),
                                 'treatments': len(tops),
                                 'top_pages': '; '.join(f'{k} ({v})' for k, v in pg[:5]),
                                 'suggested': dec.get('noowner_owner', {}).get(q, sugg)})
    noowner_rows = noowner_rows[:30]

    home_rows = []
    if 'home' in gsc:
        for r in gsc['home'].itertuples():
            k = gid.get(int(r.id))
            if k in live_keys:
                home_rows.append({'page': k, 'page_type': type_of.get(k), 'share': float(r.share_on_home_queries),
                                  'shared_queries': int(r.shared_queries), 'nb_impr': int(r.nonbrand_query_impr)})

    # ---------------- paths
    def pattern(k):
        s = segs(k)
        if not s:
            return '/'
        toks = s[-1].split('-')
        tail = []
        while toks and (toks[-1] in clf.city_words):
            tail.insert(0, toks.pop())
        last = '{slug}' + ('-' + '-'.join(tail) if tail else '') if toks else '-'.join(tail)
        return '/' + '/'.join(s[:-1] + [last]) + '/'
    path_rows = []
    by_type = collections.defaultdict(list)
    for k, t in type_of.items():
        if t not in ('Pagination', 'Query-string URL'):
            by_type[t].append(k)
    for t, ks in sorted(by_type.items(), key=lambda x: -len(x[1])):
        pc = collections.Counter(pattern(k) for k in ks)
        main_p = pc.most_common(1)[0][0]
        for p, n in pc.most_common():
            ex = [k for k in ks if pattern(k) == p][:3]
            path_rows.append({'type': t, 'pattern': p, 'pages': n, 'pct': round(n / len(ks), 3),
                              'examples': ', '.join(ex), 'main': 'Yes' if p == main_p else 'No'})
    flags = []
    raw_of = dict(zip(live_df.key, live_df.url))
    extra_area = collections.defaultdict(set)
    for k, t in sorted(type_of.items()):
        s = segs(k)
        if t in ('Service', 'Service-like (no folder)') and len(s) >= 3:
            flags.append((k, t, f'Service URL {len(s)} folders deep'))
        if len(s) >= 2 and s[-1].startswith(s[0]):
            flags.append((k, t, f'Slug repeats its folder name (/{s[0]}/)'))
        if s and re.search(r'-\d$', s[-1]):
            flags.append((k, t, 'Trailing number (likely a duplicate, e.g. -2)'))
        rawp = re.sub(r'^https?://[^/]+', '', str(raw_of.get(k, '')))
        if rawp != rawp.lower():
            flags.append((k, t, 'Uppercase letters in the URL'))
        if t == 'Blog' and blog_folder and not k.startswith(blog_folder):
            flags.append((k, t, f'Blog outside the blog folder ({blog_folder})'))
        if t == 'Blog' and not blog_folder:
            flags.append((k, t, 'Blog with no blog folder on the site'))
        if t == 'Service-like (no folder)' and service_folder:
            flags.append((k, t, f'Service page outside the service folder ({service_folder})'))
            extra_area[k].add('Service paths')
    for k, t in type_of.items():
        if t in ('Archive', 'Gallery item'):
            extra_area[k].add('Junk pages')
    for k, ar in dec.get('extra_areas', {}).items():
        for x in ([ar] if isinstance(ar, str) else ar):
            extra_area[k].add(x)

    # ---------------- link flow (body links only)
    def flow_col(k):
        t = type_of.get(k)
        st = status_of.get(k)
        if t is None:
            if st and (300 <= st < 500):
                return 'Redirect (3xx)'
            if k in redirect_final:
                return 'Redirect (3xx)'
            return 'Other'
        t = 'Service-like' if t == 'Service-like (no folder)' else 'Location / Area' if t == 'Location hub' else t
        return t if t in FLOW_COLS else 'Other'
    flow = collections.defaultdict(collections.Counter)
    bl = links[(links.cls == 'Body') & links.src.isin(live_keys) & (links.src != links.dst)]
    for s_, d_ in zip(bl.src, bl.dst):
        flow[type_of.get(s_, 'Other')][flow_col(d_)] += 1
    flow_rows = []
    for t, c in sorted(flow.items(), key=lambda x: -sum(x[1].values())):
        tot = sum(c.values())
        com = sum(c[x] for x in ['Home', 'Service hub', 'Service', 'Service-like', 'Concern hub', 'Concern', 'Location / Area'])
        flow_rows.append({'type': t, **{x: c.get(x, 0) for x in FLOW_COLS + ['Redirect (3xx)']},
                          'other': c.get('Other', 0), 'total': tot,
                          'pct_commercial': round(com / tot, 3) if tot else 0,
                          'pct_redirect': round(c.get('Redirect (3xx)', 0) / tot, 3) if tot else 0})

    # ---------------- retarget links
    svc_vocab = Topics(clf, dec)
    svc_vocab.build([k for k in service_for.values()])
    ret_ref, ret = [], []
    for r in body.itertuples():
        if type_of.get(r.dst) != 'Blog' or r.src_type in ('Archive', 'Pagination', 'Blog hub'):
            continue
        if has_gsc and g(r.dst, 'clicks') > 2:
            continue
        an = str(r.anchor)
        named = svc_vocab.match(an) if an else ''
        info = bool(INFO_ANCHOR.search(an))
        target = service_for.get(named, '') if named else ''
        ret_ref.append({'src': r.src, 'src_type': r.src_type, 'blog': r.dst, 'anchor': an,
                        'image': 'Yes' if str(r.image) == 'True' else '', 'named': named,
                        'info': 'Yes' if info else '', 'blog_clicks': g(r.dst, 'clicks'), 'match': target})
        if named and not info and target and target != r.src and target not in body_out.get(r.src, set()):
            ret.append({'src': r.src, 'blog': r.dst, 'anchor': an, 'new_target': target,
                        'reason': f'Anchor names {named}; the blog has {int(g(r.dst, "clicks"))} clicks'})
    if not ret:
        n_svc_to_blog = sum(1 for x in ret_ref if x['src_type'] in ('Service', 'Service-like (no folder)'))
        ret_none = ('No body link into a low-click blog uses a service name as its anchor'
                    + ('' if n_svc_to_blog else '; no service page links to any low-click blog') + '.')
    else:
        ret_none = ''

    # ---------------- blog to service
    feed_types = {'Blog hub', 'Pagination'}
    b2s = []
    for r in live_df.itertuples():
        if r.type != 'Blog' or str(r.has_query) == 'True':
            continue
        k = r.key
        svc = service_for.get(r.topic, '') if r.topic else ''
        outs = body_out.get(k, set())
        old = [d for d in outs if d in redirect_final and resolve(d) == svc] if svc else []
        if svc and svc in outs:
            st, act = 'OK - links to service', 'No change'
        elif old:
            st, act = 'Links to OLD service URL (redirects) - update link', f'Update the link to {svc}'
        elif svc:
            st, act = 'Missing link to service', f'Add a link to {svc}'
        else:
            st, act = 'No service matched - review', 'Pick the matching service page'
        srcs = body_in_srcs.get(k, [])
        j = body_in.get(k, 0)
        feed = sum(1 for s_ in srcs if type_of.get(s_) in feed_types)
        kk = body_in_arch.get(k, 0)
        if j == 0 and kk > 0:
            risk = 'Yes - only linked from archives'
        elif j == 0:
            risk = 'Already orphaned (no body links in)'
        elif j == feed:
            risk = 'Low - only linked from the blog listing'
        else:
            risk = 'No'
        b2s.append({'blog': k, 'title': r.title, 'h1': r.h1, 'topic': r.topic, 'service': svc, 'status': st,
                    'old_url': ', '.join(old), 'clicks': g(k, 'clicks'), 'impressions': g(k, 'impressions'),
                    'body_in': j, 'arch_in': kk, 'feed_in': feed, 'other_in': j - feed,
                    'body_out': len(outs), 'action': act, 'risk': risk})

    # ---------------- suggested actions
    past = {}
    if a.past:
        p = pd.read_csv(a.past, dtype=str, keep_default_na=False)
        cols = {c.lower(): c for c in p.columns}
        uc = cols.get('url') or cols.get('address') or list(p.columns)[0]
        dc = cols.get('decision') or cols.get('action') or list(p.columns)[1]
        tc = cols.get('target') or cols.get('redirect target') or (list(p.columns)[2] if len(p.columns) > 2 else None)
        from common import key as _key
        for _, r in p.iterrows():
            past[_key(r[uc], cfg['domain'])] = (r[dc], r[tc] if tc else '')

    def wildcard(k, t):
        s = segs(k)
        f = s[0]
        if t == 'Archive':
            tgt = blog_hub or service_hub or '/'
            pat = f'/{f}/*' if not re.fullmatch(r'(19|20)\d\d', f) else '/' + f + '/*'
        else:
            gal = '/' + f + '/' if ('/' + f + '/') in live_keys else ''
            if not gal:
                gal = next((x for x, tt in type_of.items() if tt == 'Company / Info' and 'gallery' in x), '/')
            tgt = gal
            pat = f'/{f}/*'
        if tgt.startswith('/' + f + '/'):
            pat = f'^/{f}/.+$'  # regex form so the folder page itself stays live
        return pat, tgt

    out_pages = []
    for r in live_df.itertuples():
        k, t = r.key, r.type
        isq = str(r.has_query) == 'True'
        action, target, wild = 'Keep', '', ''
        if t in ('Pagination', 'Query-string URL'):
            action = 'Leave'
        elif t in ('Archive', 'Gallery item'):
            wild, target = wildcard(k, t)
            action = 'Remove then Redirect'
        elif k in dup_of and dup_of[k]['action'] != 'Keep':
            action, target = dup_of[k]['action'], dup_of[k]['target']
        elif t == 'Blog' and has_gsc and k not in dup_of and g(k, 'clicks') == 0 and g(k, 'impressions') < 50:
            action = 'Prune candidate'
            target = service_for.get(r.topic, '') or blog_hub or '/'
            target = dup_of.get(target, {}).get('target') or target  # follow a merge to its keeper
        gsc_ok = has_gsc and not isq and not r.dupe_key
        pd_, pt_ = past.get(k, ('', ''))
        final_a, final_t = (pd_, pt_) if pd_ else (action, target)
        depth = str(r.crawl_depth).strip()
        out_pages.append({
            'url': r.url, 'path': k if not isq else re.sub(r'^https?://[^/]+', '', str(r.url)),
            'type': t, 'why': r.why, 'topic': r.topic, 'status': int(r.status),
            'indexable': r.indexable, 'crawl_depth': 'Not linked' if depth in ('', 'Not Set', 'nan', 'None') else depth,
            'path_depth': len(segs(k)) + 1, 'title': r.title, 'h1': r.h1, 'h2': r.h2,
            'words': '' if r.words == '' else int(num(r.words)),
            'in_nav': 'Yes' if nav_in.get(k) else 'No', 'nav_in': nav_in.get(k, 0), 'menu_links': int(nav_raw.get(k, 0)),
            'body_in': body_in.get(k, 0), 'body_in_arch': body_in_arch.get(k, 0), 'footer_in': foot_in.get(k, 0),
            'clicks': g(k, 'clicks') if gsc_ok else '', 'impressions': g(k, 'impressions') if gsc_ok else '',
            'position': g(k, 'position', '') if gsc_ok else '', 'top_query': g(k, 'top_query', '') if gsc_ok else '',
            'top_query_impr': g(k, 'top_query_impr', '') if gsc_ok else '',
            'ga4_sessions': g(k, 'ga4_sessions', '') if gsc_ok else '',
            'ga4_key_events': g(k, 'ga4_key_events', '') if gsc_ok else '',
            'dup_note': dup_of.get(k, {}).get('note', ''), 'action': action, 'target': target, 'wildcard': wild,
            'final_action': final_a, 'final_target': final_t,
            'past_decision': pd_, 'past_target': pt_, 'match': ('Yes' if pd_.lower() == action.lower() else 'No') if pd_ else '',
            'extra_area': ', '.join(sorted(extra_area.get(k, []))), 'key': k})
    P = pd.DataFrame(out_pages)
    order = {'Home': 0, 'Service hub': 1, 'Service': 2, 'Service-like (no folder)': 3, 'Concern hub': 4, 'Concern': 5,
             'Location hub': 6, 'Location / Area': 7, 'Blog hub': 8, 'Blog': 9, 'Company / Info': 10}
    P['_o'] = P.type.map(lambda t: order.get(t, 11 if t.endswith('(folder)') else 12))
    P = P.sort_values(['_o', 'path']).drop(columns=['_o'])
    P.to_csv(os.path.join(A, 'all_pages.csv'), index=False)

    # ---------------- page type summary
    total_clicks = num(meta.get('clicks')) if meta else P.clicks.apply(num).sum()
    sum_rows = []
    for t, d in P.groupby('type'):
        cl = d.clicks.apply(num)
        sum_rows.append({'type': t, 'pages': len(d), 'pct_indexable': round((d.indexable == 'Indexable').mean(), 3),
                         'clicks': int(cl.sum()) if has_gsc else '',
                         'share': round(cl.sum() / total_clicks, 3) if has_gsc and total_clicks else '',
                         'impressions': int(d.impressions.apply(num).sum()) if has_gsc else '',
                         'pct_zero': round((cl == 0).mean(), 3) if has_gsc else '',
                         'med_body': median(d.body_in.tolist()), 'med_nav': median(d.nav_in.tolist()),
                         'med_depth': median([num(x, None) for x in d.crawl_depth if str(x) != 'Not linked']),
                         'med_words': median([num(x, None) for x in d.words if x != '']),
                         'ga4_sessions': int(d.ga4_sessions.apply(num).sum()) if has_gsc else '',
                         'ga4_key_events': int(d.ga4_key_events.apply(num).sum()) if has_gsc else ''})
    S = pd.DataFrame(sum_rows)
    S['_o'] = S.type.map(lambda t: order.get(t, 11 if t.endswith('(folder)') else 12))
    S = S.sort_values(['_o', 'type']).drop(columns=['_o'])
    S.to_csv(os.path.join(A, 'page_type_summary.csv'), index=False)

    # ---------------- nav pages
    nav_rows = []
    for r in P[P.in_nav == 'Yes'].itertuples():
        zero = has_gsc and num(r.clicks) == 0
        keep_types = {'Home', 'Service hub', 'Concern hub', 'Blog hub', 'Location hub'}
        essential = r.type in keep_types or bool(set(words(r.path)) & {'contact', 'about', 'book', 'booking'})
        sug = 'Consider removing from the menu (0 clicks)' if zero and not essential else 'Keep in menu'
        nav_rows.append({'page': r.path, 'type': r.type, 'title': r.title, 'h1': r.h1, 'crawl_depth': r.crawl_depth,
                         'nav_in': r.nav_in, 'menu_links': r.menu_links, 'body_in': r.body_in, 'footer_in': r.footer_in,
                         'words': r.words, 'clicks': r.clicks, 'impressions': r.impressions, 'position': r.position,
                         'top_query': r.top_query, 'indexable': r.indexable, 'suggested': sug})
    nav_targets_not_live = sorted(set(nav.dst) - live_keys)
    pd.DataFrame(nav_rows).sort_values(['nav_in', 'page'], ascending=[False, True]).to_csv(os.path.join(A, 'nav_pages.csv'), index=False) if nav_rows \
        else pd.DataFrame(columns=['page']).to_csv(os.path.join(A, 'nav_pages.csv'), index=False)

    # ---------------- redirects
    planned_targets = {}
    red_rows = []

    def inbound(src_keys):
        srcs = body_nonarch[body_nonarch.dst.isin(src_keys)]  # archives are being removed, so not counted
        pages_linking = sorted(set(srcs.src))
        n_nav = nav[nav.dst.isin(src_keys)].src.nunique()
        n_ft = foot[foot.dst.isin(src_keys)].src.nunique()
        return len(srcs), len(pages_linking), pages_linking[:5], n_nav, n_ft
    when = {'Remove then Redirect': 'Now', 'Merge then Redirect': 'After merge', 'Prune candidate': 'Now (if pruned)'}
    act = P[P.final_action.isin(when.keys())]
    being_redirected = set(act.key)
    wild_groups = collections.defaultdict(list)
    for r in act.itertuples():
        if r.wildcard and r.final_action == r.action:
            wild_groups[(r.wildcard, r.final_target)].append(r.key)
        else:
            planned_targets[r.key] = r.final_target
    for (pat, tgt), ks in wild_groups.items():
        n_body, n_pages, ex, n_nav, n_ft = inbound(ks)
        rx = pat[1:-1].replace('.+', '.+') if pat.startswith('^') else '^' + re.escape(pat[:-1]) + '.+$'
        self_match = bool(re.match(rx, tgt))
        red_rows.append({'kind': 'Planned', 'source': pat, 'target': tgt, 'when': 'Now',
                         'detail': f'Wildcard: {len(ks)} {type_of.get(ks[0], "")} page(s)' +
                                   (' (regex: keeps the folder page itself live)' if pat.startswith('^') else ''),
                         'status': 200, 'body_in': n_body, 'in_nav': 'Yes' if n_nav else 'No',
                         'footer_in': 'Sitewide' if n_ft >= 100 else n_ft, 'pages_linking': n_pages,
                         'examples': ', '.join(ex), 'target_live': 'Yes' if tgt in live_keys else 'No',
                         'target_redirected': 'Yes' if tgt in being_redirected else 'No',
                         'self_match': 'Yes' if self_match else 'No'})
    for k, tgt in planned_targets.items():
        r = P[P.key == k].iloc[0]
        n_body, n_pages, ex, n_nav, n_ft = inbound([k])
        red_rows.append({'kind': 'Planned', 'source': k, 'target': tgt, 'when': when.get(r.final_action, 'Now'),
                         'detail': r.final_action, 'status': 200, 'body_in': n_body, 'in_nav': 'Yes' if n_nav else 'No',
                         'footer_in': 'Sitewide' if n_ft >= 100 else n_ft, 'pages_linking': n_pages,
                         'examples': ', '.join(ex), 'target_live': 'Yes' if tgt in live_keys else 'No',
                         'target_redirected': 'Yes' if tgt in being_redirected else 'No', 'self_match': ''})
    linked_dsts = set(L.dst)
    for r in redir.itertuples():
        if r.source in linked_dsts and r.source not in live_keys:
            fin = resolve(r.source)
            n_body, n_pages, ex, n_nav, n_ft = inbound([r.source])
            red_rows.append({'kind': 'Existing redirect still linked', 'source': r.source, 'target': fin, 'when': 'Now',
                             'detail': 'Change the links on these pages to the target' +
                                       (' (from the client redirect list)' if r.origin == 'client list' else ''),
                             'status': int(num(r.status, 301)), 'body_in': n_body, 'in_nav': 'Yes' if n_nav else 'No',
                             'footer_in': 'Sitewide' if n_ft >= 100 else n_ft, 'pages_linking': n_pages,
                             'examples': ', '.join(ex), 'target_live': 'Yes' if fin in live_keys else 'No',
                             'target_redirected': 'Yes' if fin in being_redirected else 'No', 'self_match': ''})
    broken = sorted(k for k in linked_dsts if 400 <= status_of.get(k, 0) < 500)
    for k in broken:
        n_body, n_pages, ex, n_nav, n_ft = inbound([k])
        red_rows.append({'kind': 'Broken link (4xx)', 'source': k, 'target': '', 'when': 'Now',
                         'detail': 'Fix or remove the links, or redirect this URL', 'status': status_of.get(k),
                         'body_in': n_body, 'in_nav': 'Yes' if n_nav else 'No',
                         'footer_in': 'Sitewide' if n_ft >= 100 else n_ft, 'pages_linking': n_pages,
                         'examples': ', '.join(ex), 'target_live': '', 'target_redirected': '', 'self_match': ''})
    RD = pd.DataFrame(red_rows)
    RD.to_csv(os.path.join(A, 'redirects.csv'), index=False)

    # ---------------- outputs
    pd.DataFrame(group_rows).to_csv(os.path.join(A, 'dup_groups.csv'), index=False)
    pd.DataFrame(evid_rows).to_csv(os.path.join(A, 'dup_pairs.csv'), index=False)
    pd.DataFrame(city_out).to_csv(os.path.join(A, 'city_variants.csv'), index=False)
    pd.DataFrame(noowner_rows).to_csv(os.path.join(A, 'no_owner.csv'), index=False)
    pd.DataFrame(home_rows).to_csv(os.path.join(A, 'home_overlap.csv'), index=False)
    pd.DataFrame(path_rows).to_csv(os.path.join(A, 'path_patterns.csv'), index=False)
    pd.DataFrame(flags, columns=['url', 'type', 'flag']).to_csv(os.path.join(A, 'path_flags.csv'), index=False)
    pd.DataFrame(flow_rows).to_csv(os.path.join(A, 'link_flow.csv'), index=False)
    pd.DataFrame(ret).to_csv(os.path.join(A, 'retarget.csv'), index=False)
    pd.DataFrame(ret_ref).to_csv(os.path.join(A, 'retarget_ref.csv'), index=False)
    pd.DataFrame(b2s).to_csv(os.path.join(A, 'blog_to_service.csv'), index=False)

    # ---------------- review files
    pd.DataFrame(pair_rows).to_csv(os.path.join(R, 'dup_candidates.csv'), index=False)
    P[P.type == 'Unclassified'][['path', 'title', 'h1']].to_csv(os.path.join(R, 'unclassified.csv'), index=False)
    P[P.type.isin(list(CONTENT) + ['Service hub', 'Concern hub'])][['path', 'type', 'why', 'topic', 'h1']].to_csv(
        os.path.join(R, 'topics.csv'), index=False)
    P[['path', 'type', 'why', 'h1']].to_csv(os.path.join(R, 'page_types.csv'), index=False)

    # orphan risk from removals: pages whose only body links come from pages being removed
    removing = set(P[P.final_action.isin(['Remove then Redirect', 'Merge then Redirect', 'Prune candidate'])].key)
    orphan_risk = []
    for k in P.key:
        if k in removing:
            continue
        srcs = set(body_in_srcs.get(k, []))
        if srcs and srcs <= removing and not nav_in.get(k):
            orphan_risk.append(k)

    # folders the confirmed mapping does not cover (their pages carry a "(folder)" type)
    mapped = set(clf.folder_types)
    unmapped_folders = sorted({segs(k)[0] for k in type_of if len(segs(k)) >= 2 and segs(k)[0] not in mapped}) \
        if clf.confirmed else []

    blog_pages = P[P.type == 'Blog']
    outside = blog_pages[~blog_pages.path.str.startswith(blog_folder)] if blog_folder else blog_pages
    svc_out = [f for f in flags if f[2].startswith('Service page outside')]
    deep = [f for f in flags if f[2].startswith('Service URL')]
    summary = {
        'client': cfg.get('client'), 'domain': cfg.get('domain'), 'crawler': prep.get('crawler'),
        'url_counts': prep.get('url_counts'), 'urls_total': prep.get('urls_total'),
        'live_pages': int(len(P)), 'types': P.type.value_counts().to_dict(),
        'link_classes': prep.get('link_classes'), 'link_rows': prep.get('link_rows'),
        'links_unique': prep.get('links_unique'), 'nav_share': prep.get('nav_share'),
        'redirects_found': prep.get('redirects'), 'has_gsc': has_gsc, 'gsc_meta': meta, 'utm_home': utm_lines,
        'blog_folder': blog_folder, 'blog_folder_has_posts': blog_folder_has_posts,
        'service_folder': service_folder, 'blog_hub': blog_hub,
        'blogs': int(len(blog_pages)), 'blogs_outside': int(len(outside)),
        'service_like_outside': len(svc_out), 'deep_service': len(deep),
        'archive_pages': int((P.type == 'Archive').sum()), 'gallery_items': int((P.type == 'Gallery item').sum()),
        'dup_groups': gnum, 'dup_pages_merge': int((P.action == 'Merge then Redirect').sum()),
        'dup_pages_review': int((P.action == 'Review').sum()), 'city_variants': len(city_out),
        'no_owner': len(noowner_rows), 'pairs_to_check': sum(1 for x in pair_rows if x['verdict'] == 'check'), 'home_overlap': len(home_rows),
        'prune_candidates': int((P.action == 'Prune candidate').sum()),
        'menu_zero_click': int(((P.in_nav == 'Yes') & (P.clicks.apply(num) == 0)).sum()) if has_gsc else None,
        'menu_pages': int((P.in_nav == 'Yes').sum()),
        'nav_targets_not_live': nav_targets_not_live,
        'existing_redirects_linked': int((RD.kind == 'Existing redirect still linked').sum()) if len(RD) else 0,
        'broken_linked': len(broken),
        'body_links_to_redirects': int(sum(x['Redirect (3xx)'] for x in flow_rows)),
        'body_links_total': int(sum(x['total'] for x in flow_rows)),
        'location_pages': int(P.type.isin(['Location / Area']).sum()),
        'retarget': len(ret), 'retarget_none_reason': ret_none,
        'blog_status': pd.Series([b['status'] for b in b2s]).value_counts().to_dict() if b2s else {},
        'orphan_risk_after_removals': orphan_risk, 'notes': notes + prep.get('warnings', []),
        'unclassified': P[P.type == 'Unclassified'].path.tolist(),
        'other_folders': sorted({t for t in P.type if t.endswith('(folder)')}),
        'mapping_confirmed': clf.confirmed, 'folder_mapping': dec.get('folder_types', {}),
        'unmapped_folders': unmapped_folders,
        'pair_queries_needed': sorted({tuple(sorted(x)) for x in need_pq}),
        'pair_queries_loaded': 'pair_queries' in gsc,
        'no_gsc_pages_with_impr': (int(sum(1 for k in gd if k not in live_keys and g(k, 'impressions') > 0)) if has_gsc else 0),
    }
    save_json(os.path.join(A, 'summary.json'), summary)

    # ---------------- next steps for the reviewer
    lines = ['# Review before filling the template', '']
    lines.append(f"Live pages: {len(P)}. Types: " + ', '.join(f'{t} {n}' for t, n in P.type.value_counts().items()))
    lines.append(f"Link classes: {prep.get('link_classes')} (Nav share {prep.get('nav_share')})")
    if summary['unclassified']:
        lines.append(f"\n## {len(summary['unclassified'])} Unclassified pages\nLabel them in decisions.json page_types, "
                     f"or leave them and list them in the chat summary: {', '.join(summary['unclassified'][:40])}")
    if unmapped_folders:
        lines.append('\n## Folders missing from the confirmed mapping\nAsk the person which type these are, then add them '
                     'to folder_types in decisions.json: ' + ', '.join(f'/{f}/' for f in unmapped_folders))
    if summary['other_folders']:
        lines.append('\n## Other folders\nThese folders got their own type. If one is really a service, concern or blog '
                     'folder, set folder_types in decisions.json: ' + ', '.join(summary['other_folders']))
    blog_label = blog_folder or 'none exists'
    if blog_folder and not blog_folder_has_posts:
        blog_label = f'{blog_folder} (listing page only; no posts live in it)'
    lines.append(f"\n## Blog folder: {blog_label}; service folder: {service_folder or 'none exists'}")
    if summary['blogs_outside']:
        lines.append(f"{summary['blogs_outside']} blog post(s) sit outside a blog folder. The recommendations must say to move "
                     f"them all into one dedicated folder with 301s (SKILL.md, Step 6).")
    if has_gsc:
        if need_pq:
            pairs_arg = ','.join(f'{a}:{b}' for a, b in sorted({tuple(sorted(x)) for x in need_pq}))
            lines.append('\n## Top shared queries\nRun this (it reads the Search Console sheet data already loaded, no '
                         'Composio), then re-run analyze.py:\n'
                         f"python $SKILL/scripts/gsc_sheet.py pair-queries --pairs {pairs_arg} --out {os.path.join(W, 'gsc')}")
    n_check = sum(1 for x in pair_rows if x['verdict'] == 'check')
    lines.append(f"\n## Duplicate candidates: review/dup_candidates.csv ({len(pair_rows)} pairs; "
                 f"{len(dup_pairs)} duplicate, {len(city_rows)} city variant, {n_check} check, "
                 f"{len(pair_rows) - len(dup_pairs) - len(city_rows) - n_check} not)\n"
                 'Decide every "check" pair (one topic is the other plus words: a product line is a duplicate, '
                 'a different treatment in the same area is not; a pair you cannot judge from the table is "review"). Confirm every "duplicate" is the same treatment '
                 'and look down the "not" pairs with high overlap for synonyms (e.g. labiaplasty / labia reduction). '
                 'Fix with pair_verdicts, topics or synonyms in decisions.json. Unresolved "check" pairs count as not duplicates.')
    if orphan_risk:
        lines.append(f'\n## Orphan risk\n{len(orphan_risk)} pages lose all their body links if the suggested removals '
                     f'happen: {", ".join(orphan_risk[:20])}')
    for n in summary['notes']:
        lines.append(f'\nNOTE: {n}')
    open(os.path.join(R, 'next_steps.md'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
