#!/usr/bin/env python3
"""Apply the audit rules (references/rules.md, data.md, redirects-qa.md) to one site.

Usage:
  python build.py --domain example.com --work work --gsc GSC.csv [--gsc-tab TAB] --window "last 90 days" \
                  [--ga4 GA4.csv] [--ga4-status "skipped: 100 Search Console clicks"]

Run prep.py first. This script makes no site-specific decision of its own: everything that depends on
how the site is built comes from files the person confirmed in the chat, all in --work:

  folder_map.json   required. {"folders": {"/services/": "Service", "/a-single-page/": "Hub / Category Page"},
                    "blog_listing": "/blog/", "concern_hubs": ["/conditions/"]}. A key is a first-level folder
                    or one exact page path (exact pages win). blog_listing and concern_hubs may be "" / [].
  cities.json       required. {"main": "...", "separate": [...], "ignore": [...], "copy_pairs": [[copy, original]]}
  title_groups.json optional. [["/page-a/", "/page-b/"], ...] topic groups the person confirmed for pages
                    with under 20 impressions.
  junk.json         optional. {"/tag/": "/blog/", ...} the folders the person picked as junk, with the
                    wildcard target. Without it nothing is treated as junk (candidates are still listed).
  ia_*.csv, ia_folder_map.json, ia.json   optional. Written by ia_import.py when an IA audit workbook was given. IA page
                    types win over the folder map and the URL rules (they were approved by the SEO); the IA folder map types the
                    pages inside folders this chat's folder_map.json does not cover. Without them nothing changes.
  overrides.json    optional. Calls made in the chat, one entry per page:
                    {"/page/": {"page_type": "...", "step": "...", "target": "/other/", "why": "..."}}.
                    page_type is applied before the rules; step/target after them, and is marked "judgment".
                    A rule 5 or rule 6 candidate the person or Claude confirmed is {"step": "Repurpose", "rule": 5,
                    "query": "<top matching query>"} (or "Update", 6): the rule's fixed sentence is used, no "judgment".
                    When the SEO edits Check page type or Kept pages, their changes go here too.

Writes to --work (TSVs have no header row, the format make_xlsx.py reads):
  audit.tsv               25 columns, references/rules.md order
  existing_redirects.tsv  Source URL | Target URL | Notes
  not_in_crawl.tsv        url | clicks | impressions | sessions | redirect target (header row)
  run.json                settings and counts for the workbook README and the report
  junk_candidates.csv, title_group_candidates.csv, rule5_candidates.csv, rule6_candidates.csv,
  overlap_groups.tsv, qa.txt   for Claude to show the person or read before the next step
  internal_links_to_update.csv, case_duplicates.csv   for the report
"""
import argparse
import collections
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bare_domain, key, load_json, save_json  # noqa: E402

TYPES = ['Home', 'Service', 'Concern / Condition', 'Service Area / Location', 'Hub / Category Page', 'Blog Post',
         'Blog Category / Tag', 'Gallery', 'Author / Archive', 'Not for SEO (contact, legal, etc.)', 'Other']
NFS = 'Not for SEO (contact, legal, etc.)'
KEEPISH = {'Keep', 'Update', 'Repurpose', 'Needs Discussion'}
OVERLAP = 0.30           # rules.md rule 3
REMOVE_IMPR = 50         # rules.md rule 4: 0 clicks and under this
GROUP_MIN_IMPR = 20      # data.md: pages grouped by Search Console queries
SHARED_MIN = 10          # data.md: shared impressions floor

# rules.md Page Type rule 4 slug words (kept as written in the rules)
NFS_WORDS = ['contact', 'privacy', 'terms', 'hipaa', 'thank-you', 'thank', 'sitemap', 'login', 'cart', 'checkout',
             'account', 'financing', 'shop', 'packages', 'memberships', 'booking', 'book', 'events', 'policies',
             'policy', 'patient-resources', 'patient-information', 'forms', 'accessibility', 'disclaimer']
OTHER_WORDS = ['about', 'about-us', 'team', 'our-team', 'meet', 'reviews', 'testimonials', 'press']
QUESTION = ('what', 'how', 'why', 'can', 'is', 'are', 'does', 'do', 'should', 'when', 'which', 'where', 'who')
BLOG_WORDS = ['vs', 'versus', 'benefits', 'guide', 'tips', 'cost', 'explained', 'what-to-expect', 'reasons',
              'aftercare', 'before-and-after', 'myths']
PRICE_WORDS = re.compile(r'\b(cost|costs|price|prices|pricing|how much)\b|\bnear me\b')
STATE = re.compile(r'-[a-z]{2}$')
ARCHIVE = re.compile(r'^(tag|tags|category|categories|author|authors|attachment|archive|archives|\d{4})$')


def num(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(',', '').str.replace('%', ''), errors='coerce').fillna(0)


def plural(n, word):
    return f'{n:,} {word}' + ('' if n == 1 else 's')


def find(cols, *names):
    low = {c.lower().strip(): c for c in cols}
    for n in names:
        if n in low:
            return low[n]
    return None


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')


class Run:
    def __init__(self, a):
        self.a = a
        self.dom = bare_domain(a.domain)
        self.w = a.work
        self.base = 'https://' + self.dom
        self.fm = load_json(self.p('folder_map.json'))
        self.cities = load_json(self.p('cities.json'))
        if self.fm is None or self.cities is None:
            sys.exit('folder_map.json and cities.json are required in --work (SKILL.md Step 2). Confirm them with the person first.')
        self.title_groups = load_json(self.p('title_groups.json'), [])
        self.junk = {self.k(f): self.k(t) for f, t in (load_json(self.p('junk.json'), {}) or {}).items()}
        self.over = {self.k(u): v for u, v in (load_json(self.p('overrides.json'), {}) or {}).items()}
        # optional IA audit workbook, read by ia_import.py: everything in it is treated as approved by the SEO
        rd = lambda f: pd.read_csv(self.p(f), keep_default_na=False, dtype=str) if os.path.exists(self.p(f)) else None
        t, mv, mn = rd('ia_types.csv'), rd('ia_moves.csv'), rd('ia_menu.csv')
        self.ia = load_json(self.p('ia.json'))
        self.ia_types = dict(zip(t.key, t.page_type)) if t is not None else {}
        self.ia_fm = load_json(self.p('ia_folder_map.json'), {}) or {}
        self.ia_moves = dict(zip(mv.old, mv.new)) if mv is not None else {}
        self.ia_menu = set(mn.key) if mn is not None else set()
        self.sep = [slugify(c) for c in self.cities.get('separate', [])]
        self.allcity = self.sep + [slugify(c) for c in [self.cities.get('main', '')] + self.cities.get('ignore', []) if c]
        self.qa = []

    def p(self, f):
        return os.path.join(self.w, f)

    def k(self, u):
        return key(u, self.dom)

    def full(self, k):
        return k if not k.startswith('/') else self.base + k

    # ---------------- data ----------------
    def load(self):
        pages = pd.read_csv(self.p('crawl_pages.csv'), keep_default_na=False, dtype=str)
        pages['status'] = num(pages.status).astype(int).values
        pages['primary'] = pages.primary.astype(str) == 'True'
        pages['has_query'] = pages.has_query.astype(str) == 'True'
        self.crawl = pages
        live = pages[pages.primary & (pages.status == 200) & ~pages.has_query & pages.key.str.startswith('/')].copy()
        live['words'] = num(live.words.values).values
        self.live = live.set_index('key')
        self.status = dict(zip(pages[pages.primary].key, pages[pages.primary].status))
        self.links = pd.read_csv(self.p('links.csv'), keep_default_na=False, dtype=str)
        self.redirects = pd.read_csv(self.p('redirects.csv'), keep_default_na=False, dtype=str)
        self.canon = pd.read_csv(self.p('canonical_issues.csv'), keep_default_na=False, dtype=str)

        g = self.read_gsc()
        pc, qc = find(g.columns, 'page', 'landing page', 'url'), find(g.columns, 'query', 'queries', 'search query')
        cc, ic = find(g.columns, 'clicks'), find(g.columns, 'impressions')
        if not (pc and qc and cc and ic):
            sys.exit(f'Search Console file needs Page, Query, Clicks and Impressions columns; found {list(g.columns)}')
        g = pd.DataFrame({'key': g[pc].map(self.k), 'query': g[qc].str.strip().str.lower(),
                          'clicks': num(g[cc].values).values, 'impr': num(g[ic].values).values})
        self.gsc = g[g.key != ''].groupby(['key', 'query'], as_index=False)[['clicks', 'impr']].sum()
        self.gpage = self.gsc.groupby('key')[['clicks', 'impr']].sum()
        self.ga4 = pd.DataFrame(columns=['sessions', 'new_users', 'views', 'key_events'])
        if self.a.ga4:
            ga = pd.read_csv(self.a.ga4, dtype=str, keep_default_na=False)
            lc = find(ga.columns, 'landing page', 'landingpage', 'page', 'path', 'url')
            cols = {'sessions': find(ga.columns, 'sessions'), 'new_users': find(ga.columns, 'new users', 'newusers'),
                    'views': find(ga.columns, 'views', 'screenpageviews'), 'key_events': find(ga.columns, 'key events', 'keyevents', 'conversions')}
            if not lc:
                sys.exit(f'GA4 file needs a landing page column; found {list(ga.columns)}')
            d = pd.DataFrame({'key': ga[lc].map(self.k)})
            for n, c in cols.items():
                d[n] = num(ga[c].values).values if c else 0
            self.ga4 = d[d.key != ''].groupby('key').sum()

    def read_gsc(self):
        """A CSV or XLSX, or a pasted Google Sheet (tabs separated by '## Sheet name:' lines; --gsc-tab picks one)."""
        import io
        if self.a.gsc.lower().endswith(('.xlsx', '.xls')):
            return pd.read_excel(self.a.gsc, sheet_name=self.a.gsc_tab or 0, dtype=str).fillna('')
        text = open(self.a.gsc, encoding='utf-8-sig').read()
        parts = re.split(r'^## Sheet name:\s*(.*)$', text, flags=re.M)
        if len(parts) > 1:
            tabs = {parts[i].strip(): parts[i + 1] for i in range(1, len(parts), 2)}
            if self.a.gsc_tab not in tabs:
                sys.exit(f'The Search Console file has several tabs: {list(tabs)}. Pick one with --gsc-tab (data.md says which).')
            text = tabs[self.a.gsc_tab]
        return pd.read_csv(io.StringIO(text.strip()), dtype=str, keep_default_na=False)

    # ---------------- page types ----------------
    def folder(self, k):
        parts = [x for x in k.split('/') if x]
        return '/' + parts[0] + '/' if len(parts) > 1 else ''

    def blog_listed(self):
        bl = self.fm.get('blog_listing') or ''
        if not bl:
            return set(), False
        bl = self.k(bl)
        pag = re.compile('^' + re.escape(bl) + r'(page/\d+/)?$')
        body = self.links[self.links.cls == 'Body']
        src = body[body.src.map(lambda s: bool(pag.match(s)))]
        # The listing only proves a page is not a post when every listing page is in the links export. Query-string
        # pagination (?page=2, ?e-page-1a2b=2) is stripped from link keys, so it can never be checked: then unknown.
        qpag = self.crawl.url.str.contains(r'^[^?]*' + re.escape(bl) + r'\?.*\b(?:e-page[^=&]*|page|paged)=\d+', regex=True).any()
        return set(src.dst), len(src) > 0 and not qpag

    def page_types(self):
        folders = {self.k(f) if f.startswith('/') else f: t for f, t in self.fm.get('folders', {}).items()}
        listed, blog_known = self.blog_listed()
        hubs = [self.k(h) for h in self.fm.get('concern_hubs', []) or []]
        body = self.links[self.links.cls == 'Body']
        on_hub = set(body[body.src.isin(hubs)].dst) if hubs else set()
        # a folder's own page lists the pages inside it: folders that hold live pages, folders the IA map names, the blog listing
        parents = ({self.folder(k) for k in self.live.index} | set(self.ia_fm) | {self.k(self.fm.get('blog_listing') or '')}) - {''}
        out = {}
        for k, r in self.live.iterrows():
            slug = k.strip('/').split('/')[-1] if k != '/' else ''
            f = self.folder(k)
            ftype = folders.get(k) or self.ia_fm.get(k) or ''
            if k in self.over and self.over[k].get('page_type'):
                out[k] = (self.over[k]['page_type'], 'judgment: ' + self.over[k].get('why', 'set by the person'))
            elif k in self.ia_types:
                out[k] = (self.ia_types[k], 'From the IA audit (approved by the SEO)')
            elif k == '/':
                out[k] = ('Home', 'Home page')
            elif k in parents and ftype != 'Hub / Category Page':
                # a folder's own page lists the pages inside it (rules.md Page Type rule 2)
                out[k] = (NFS, f'Listing page of {k}') if ftype == NFS else ('Hub / Category Page', f'Listing page of {k}')
            elif k in folders:
                out[k] = (folders[k], f'Folder map: {k}')
            elif f in folders:
                out[k] = (folders[f], f'Folder map: {f}')
            elif f in self.ia_fm:
                out[k] = (self.ia_fm[f], f'Folder map from the IA audit: {f}')
            elif f and ARCHIVE.match(f.strip('/')):
                t = 'Author / Archive' if f.strip('/') in ('author', 'authors') or f.strip('/').isdigit() else 'Blog Category / Tag'
                out[k] = (t, f'Archive folder {f}')
            elif f:
                out[k] = ('Other', f'No rule matched - check (folder {f} is not in the folder map)')
            elif k in listed:
                out[k] = ('Blog Post', 'Listed on the blog listing')
            elif k in on_hub:
                out[k] = ('Concern / Condition', 'Listed on the concern hub')
            else:
                out[k] = self.slug_type(slug, r.h1, k in listed, blog_known)
        self.types = out

    def slug_type(self, slug, h1, listed, blog_known):
        words = [w for w in slug.split('-') if w]
        if any(slug == w or slug.startswith(w + '-') for w in NFS_WORDS):
            return (NFS, 'Slug: legal, contact or user page')
        if any(slug == w or slug.startswith(w + '-') for w in OTHER_WORDS):
            return ('Other', 'Slug: about, team or reviews page')
        q = words and words[0] in QUESTION
        h = ' ' + re.sub(r'[^a-z0-9]+', ' ', str(h1).lower()) + ' '
        bw = any(('-' + b + '-') in ('-' + slug + '-') or (' ' + b.replace('-', ' ') + ' ') in h for b in BLOG_WORDS)
        hq = '?' in str(h1) or h.split()[:1] in [[w] for w in QUESTION]
        if q or bw or hq:
            return ('Blog Post', 'Root-level, slug reads like a post')
        if len(words) >= 6:
            if blog_known and not listed:
                return ('Service', 'Root-level, long slug but not on the blog - check')
            return ('Blog Post', 'Root-level, slug reads like a post')
        if slug == 'areas-we-serve' or any(slug == c or slug.startswith(c + '-') for c in self.sep):
            return ('Service Area / Location', 'Root-level, city page')
        if any(('-' + c + '-') in ('-' + slug + '-') for c in self.sep):
            return ('Service Area / Location', 'Root-level, city in slug')
        if words:
            return ('Service', 'Root-level, no folder match')
        return ('Other', 'No rule matched - check')

    # ---------------- junk ----------------
    def junk_candidates(self):
        live = self.live.copy()
        live['folder'] = [self.folder(k) for k in live.index]
        body = self.links[self.links.cls == 'Body']
        rows = []
        for f, d in live[live.folder != ''].groupby('folder'):
            name = f.strip('/')
            g = self.gpage.reindex(d.index).fillna(0)
            rule = ''
            if ARCHIVE.match(name) or 'category' in name or 'archive' in name or name == 'page':
                rule = 'Archive-style folder name'
            else:
                tit = d.title.str.lower().str.split().map(lambda w: ' '.join(w[1:]) if w else '')
                same = tit.duplicated(keep=False)
                ins = body[body.dst.isin(d.index) & ~body.src.map(self.folder).eq(f)]
                weak = (g.clicks == 0) & (g.impr < 10) & ((d.words < 150) | same) & ~d.index.isin(ins.dst)
                if len(d) and weak.mean() >= 0.8:
                    rule = '80%+ of pages: no clicks, under 10 impressions, thin or same title, no Body links from outside'
            if rule:
                tgt = self.fm.get('blog_listing') if rule.startswith('Archive') else ''
                rows.append({'folder': f, 'rule': rule, 'pages': len(d), 'impressions': int(g.impr.sum()),
                             'examples': ' '.join(list(d.index[:5])), 'suggested_target': tgt or ''})
        pd.DataFrame(rows, columns=['folder', 'rule', 'pages', 'impressions', 'examples', 'suggested_target']).to_csv(
            self.p('junk_candidates.csv'), index=False)

    def in_junk(self, k):
        f = self.folder(k)
        return f in self.junk

    # ---------------- topic groups and overlap ----------------
    def groups(self):
        aud = [k for k in self.audited]
        g = self.gsc[self.gsc.key.isin(aud)]
        tot = self.gpage.impr
        big = [k for k in aud if tot.get(k, 0) >= GROUP_MIN_IMPR]
        top = g[g.key.isin(big)].sort_values(['key', 'impr'], ascending=[True, False]).drop_duplicates('key').set_index('key')['query']
        qsets = g.groupby('key')['query'].apply(set)
        parent = {k: k for k in aud}

        def root(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def join(a, b):
            parent[root(a)] = root(b)
        bytop = collections.defaultdict(list)
        for k, q in top.items():
            bytop[q].append(k)
        for ks in bytop.values():
            for x in ks[1:]:
                join(x, ks[0])
        for k, q in top.items():
            for o in big:
                if o != k and q in qsets.get(o, ()):
                    join(k, o)
        src = {}
        for grp in self.title_groups or []:
            ks = [self.k(u) for u in grp if self.k(u) in parent]
            for x in ks[1:]:
                join(x, ks[0])
            for x in ks:
                src[x] = 'title'
        groups = collections.defaultdict(list)
        for k in aud:
            groups[root(k)].append(k)
        self.group_of = {}
        lines = []
        for i, (r, ks) in enumerate(sorted(groups.items(), key=lambda x: -len(x[1])), 1):
            if len(ks) < 2:
                continue
            for x in ks:
                self.group_of[x] = i
            lab = top.get(r, '') or ''
            lines.append(f'{i}\t{"title" if any(src.get(x) for x in ks) else "GSC"}\t{" ".join(ks)}\t{lab}')
        with open(self.p('overlap_groups.tsv'), 'w') as f:
            f.write('group\tsource\turls\tshared top query\n' + '\n'.join(lines) + '\n')
        # pages under 20 impressions not in a confirmed title group: for Claude to propose groups
        small = [k for k in aud if tot.get(k, 0) < GROUP_MIN_IMPR and k not in src]
        pd.DataFrame({'url': small, 'type': [self.types[k][0] for k in small],
                      'title': [self.live.title.get(k, '') for k in small]}).to_csv(self.p('title_group_candidates.csv'), index=False)

    def overlap(self):
        g = self.gsc[self.gsc.key.isin(self.audited)]
        tot = self.gpage.impr
        byq = g.groupby('query')
        pairs = collections.defaultdict(lambda: [0.0, collections.Counter()])
        for q, d in byq:
            rows = list(zip(d.key, d.impr))
            if len(rows) < 2 or len(rows) > 200:
                continue
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    a, ia = rows[i]
                    b, ib = rows[j]
                    pk = (a, b) if a < b else (b, a)
                    m = min(ia, ib)
                    pairs[pk][0] += m
                    pairs[pk][1][q] += m
        self.share = {}
        for (a, b), (sh, qs) in pairs.items():
            ta, tb = tot.get(a, 0), tot.get(b, 0)
            if ta < GROUP_MIN_IMPR or tb < GROUP_MIN_IMPR or sh < SHARED_MIN:
                continue
            s = sh / min(ta, tb)
            q = qs.most_common(1)[0][0]
            self.share[(a, b)] = self.share[(b, a)] = (s, q)

    def sh(self, a, b):
        return self.share.get((a, b), (0, ''))

    # ---------------- suggestions ----------------
    def city_copies(self):
        def base(slug):
            s = '-' + slug + '-'
            for c in self.allcity:
                s = s.replace('-' + c + '-', '-')
            s = s.strip('-')
            return STATE.sub('', s)

        def has_sep(slug):
            return any(('-' + c + '-') in ('-' + slug + '-') for c in self.sep)
        main_by = {}
        for k in self.audited:
            slug = k.strip('/').split('/')[-1]
            if not has_sep(slug):
                main_by.setdefault((self.folder(k), base(slug)), k)
        cp = {}
        for k in self.audited:
            slug = k.strip('/').split('/')[-1]
            if has_sep(slug):
                m = main_by.get((self.folder(k), base(slug)))
                if m:
                    cp[k] = m
        for c, o in self.cities.get('copy_pairs', []) or []:
            if self.k(c) in self.live.index and self.k(o) in self.live.index:
                cp[self.k(c)] = self.k(o)
        self.copies = cp
        self.copy_city = {k: next((c for c in self.sep if ('-' + c + '-') in ('-' + k.strip('/').split('/')[-1] + '-')), '')
                          for k in cp}

    def suggest(self):
        T = {k: t for k, (t, _) in self.types.items()}
        clicks = self.gpage.clicks
        impr = self.gpage.impr
        step, target, why, flags = {}, {}, {}, collections.defaultdict(list)
        main_rank = lambda k: 1 if any(('-' + c + '-') in ('-' + k.strip('/').split('/')[-1] + '-') for c in self.sep) else 0
        for k in self.audited:
            if T[k] == NFS:
                step[k], why[k] = 'Keep', 'Not a page for search, so it stays.'
        # rule 2 city copies
        for c, m in self.copies.items():
            if c in step:
                continue
            n = int(clicks.get(c, 0))
            city = self.copy_city.get(c, '').replace('-', ' ').title() or 'City'
            flags[c].append(f'{city}-style city copy of {self.full(m)}')
            if n < 2:
                step[c], target[c] = 'Merge then Redirect', m
                why[c] = f'City copy of {self.full(m)} with {plural(n, "click")}, so it merges into the main-city page.'
            else:
                step[c] = 'Keep'
                why[c] = f'City copy of {self.full(m)}, but it earns {plural(n, "click")} of its own.'
        # rule 3a: concern into service
        for k in self.audited:
            if k in step or T[k] != 'Concern / Condition':
                continue
            best = max(((self.sh(k, s)[0], s) for s in self.audited if T.get(s) == 'Service' and s not in step), default=(0, ''))
            if best[0] >= OVERLAP:
                s, q = self.sh(k, best[1])
                step[k], target[k] = 'Merge then Redirect', best[1]
                why[k] = f'Concern page sharing {s:.0%} of its impressions with service page {self.full(best[1])}.'
                flags[k].append(f'Concern merges into service page {self.full(best[1])}')
        # rule 3b: within topic groups, keeper order Service, Concern, Blog Post; main city first; impressions
        order = {'Service': 0, 'Concern / Condition': 1, 'Blog Post': 2}
        bygroup = collections.defaultdict(list)
        for k, gid in self.group_of.items():
            if k not in step and T[k] in order:
                bygroup[gid].append(k)
        for ks in bygroup.values():
            ks.sort(key=lambda k: (order[T[k]], main_rank(k), -impr.get(k, 0), k))
            keepers = []
            for k in ks:
                cand = [(self.sh(k, x)[0], x) for x in keepers if self.sh(k, x)[0] >= OVERLAP]
                if cand:
                    s, x = max(cand)
                    step[k], target[k] = 'Merge then Redirect', x
                    why[k] = f'Shares {s:.0%} of its impressions with {self.full(x)}, the page kept for this topic.'
                else:
                    keepers.append(k)
        # rule 4 remove
        bl = self.k(self.fm.get('blog_listing') or '') if self.fm.get('blog_listing') else ''
        for k in self.audited:
            if k in step or T[k] != 'Blog Post':
                continue
            if clicks.get(k, 0) == 0 and impr.get(k, 0) < REMOVE_IMPR:
                gid = self.group_of.get(k)
                svc = [x for x, g in self.group_of.items() if g == gid and T.get(x) == 'Service'] if gid else []
                t = max(svc, key=lambda x: impr.get(x, 0)) if svc else bl
                step[k], target[k] = 'Remove then Redirect', t
                n = int(impr.get(k, 0))
                why[k] = f'Blog post with 0 clicks and {plural(n, "impression")}.'
                flags[k].append('0 clicks, under 50 impressions')
                if not t:
                    self.qa.append(f'BREAKING: {k} is suggested Remove but there is no blog_listing in folder_map.json and no service page in its group')
        # overrides (step / target)
        for k, o in self.over.items():
            if k in self.live.index and o.get('step'):
                step[k] = o['step']
                if o.get('target'):
                    target[k] = self.k(o['target'])
                elif o['step'] not in ('Merge then Redirect', 'Remove then Redirect'):
                    target.pop(k, None)
                q = o.get('query', '')
                if o.get('rule') == 5:   # a rule 5 candidate Claude confirmed: the rule decided, not judgment
                    why[k] = f'Blog post showing for buying searches such as "{q}", with no service page on the topic.'
                elif o.get('rule') == 6:
                    why[k] = f'Named for a brand or product, but searchers use "{q}".'
                else:
                    why[k] = o.get('why', '') + " (Claude's judgment call, not a fixed rule)"
        for k in self.audited:
            if k not in step:
                step[k], why[k] = 'Keep', 'No rule called for a change.'
        # follow targets to a page whose own suggestion is kept
        for k in list(target):
            seen, t = {k}, target[k]
            while t in step and step[t] not in KEEPISH and t in target and t not in seen:
                seen.add(t)
                t = target[t]
            target[k] = t
        self.step, self.target, self.why, self.flags = step, target, why, flags

    def rule5_6_candidates(self):
        T = {k: t for k, (t, _) in self.types.items()}
        g = self.gsc[self.gsc.key.isin(self.audited)]
        cityre = re.compile(r'\b(' + '|'.join(re.escape(c.replace('-', ' ')) for c in self.allcity) + r')\b') if self.allcity else None
        r5 = []
        for k, d in g.groupby('key'):
            if T.get(k) != 'Blog Post' or self.step.get(k) != 'Keep':
                continue
            gid = self.group_of.get(k)
            if gid and any(T.get(x) == 'Service' for x, gg in self.group_of.items() if gg == gid):
                continue
            hit = d[d['query'].map(lambda q: bool(PRICE_WORDS.search(q) or (cityre and cityre.search(q))))]
            if len(hit):
                h = hit.sort_values('impr', ascending=False)
                r5.append({'url': k, 'impressions': int(d.impr.sum()), 'matching_impressions': int(h.impr.sum()),
                           'top_matching_queries': ' | '.join(h['query'].head(5))})
        pd.DataFrame(r5, columns=['url', 'impressions', 'matching_impressions', 'top_matching_queries']).to_csv(self.p('rule5_candidates.csv'), index=False)
        r6 = []
        for k, d in g.groupby('key'):
            if T.get(k) != 'Service' or self.step.get(k) != 'Keep' or d.impr.sum() < GROUP_MIN_IMPR:
                continue
            toks = [t for t in k.strip('/').split('/')[-1].split('-') if len(t) > 2 and t not in self.allcity and not STATE.match('-' + t)]
            tot = d.impr.sum()
            sh = {t: d[d['query'].str.contains(r'\b' + re.escape(t) + r'\b', regex=True)].impr.sum() / tot for t in toks}
            low = [t for t, s in sh.items() if s < 0.50]
            if low:
                top = d.sort_values('impr', ascending=False)['query'].head(3)
                r6.append({'url': k, 'title': self.live.title.get(k, ''), 'h1': self.live.h1.get(k, ''), 'impressions': int(tot),
                           'slug_words_rarely_searched': ' '.join(low), 'top_queries': ' | '.join(top)})
        pd.DataFrame(r6, columns=['url', 'title', 'h1', 'impressions', 'slug_words_rarely_searched', 'top_queries']).to_csv(self.p('rule6_candidates.csv'), index=False)

    def notes(self):
        T = {k: t for k, (t, _) in self.types.items()}
        clicks = self.gpage.clicks
        nav = set(self.links[self.links.cls == 'Nav'].dst)
        live_r = self.redirects[(self.redirects.normalization_only != 'True')]
        into = live_r.groupby('final').size()
        canon = {r.url: r for r in self.canon.itertuples()}
        pag = re.compile(r'/page/\d+/$')
        body = self.links[self.links.cls == 'Body']
        body_src = body.groupby('dst')['src'].apply(list)
        merged_into = collections.Counter(t for k, t in self.target.items() if self.step[k] in ('Merge then Redirect', 'Remove then Redirect'))
        self.blog_beats = {}
        out = {}
        for k in self.audited:
            f = list(self.flags.get(k, []))
            best = max(((self.sh(k, x)[0], x) for x in self.audited if x != k and self.group_of.get(x) and
                        (self.group_of.get(x) == self.group_of.get(k) or {T[k], T[x]} == {'Concern / Condition', 'Service'})),
                       default=(0, ''))
            overlap_note = ''
            if best[0] >= OVERLAP and self.step[k] != 'Merge then Redirect':
                s, q = self.sh(k, best[1])
                if self.step[k] == 'Keep':  # said in plain words in the Why sentence, so no separate flag
                    o = self.full(best[1])
                    # the share is measured on the smaller page, so name that page as the one whose searches overlap
                    who = ('of its searches', f'also show {o}') if self.gpage.impr.get(k, 0) <= self.gpage.impr.get(best[1], 0) \
                        else (f'of the searches for {o}', 'also show this page')
                    overlap_note = (f' But {s:.0%} {who[0]} (for example "{q}") {who[1]}, '
                                    'and no rule merges these two kinds of page. Check whether both should stay.')
                else:
                    f.append(f'Competes with {self.full(best[1])} for "{q}" ({s:.0%} shared)')
            if self.step[k] == 'Merge then Redirect' and k in self.target and 'city copy' not in ' '.join(f):
                s, q = self.sh(k, self.target[k])
                if s:
                    f.append(f'Competes with {self.full(self.target[k])} for "{q}" ({s:.0%} shared)')
            if T[k] == 'Blog Post' and self.group_of.get(k):
                svc = [x for x in self.audited if self.group_of.get(x) == self.group_of[k] and T[x] == 'Service']
                beaten = [x for x in svc if clicks.get(k, 0) > clicks.get(x, 0)]
                if beaten and clicks.get(k, 0) > 0:
                    x = max(beaten, key=lambda x: self.gpage.impr.get(x, 0))
                    f.append(f'Blog outranks service page {self.full(x)}')
                    self.blog_beats[k] = x
            for c, m in self.copies.items():
                if m == k:
                    city = self.copy_city.get(c, '').replace('-', ' ').title() or 'City'
                    f.append(f'{city}-style city copy of {self.full(k)}')
                    break
            if into.get(k, 0):
                f.append(f'Already redirected to by {into[k]} old URL(s)')
            if k in nav:
                f.append('In main menu')
            srcs = body_src.get(k, [])
            if srcs and all(pag.search(s) for s in srcs):
                f.append('Only linked from blog pagination')
            if k in canon:
                c = canon[k]
                if str(c.redirects_back) == 'True':
                    f.append(f'Canonical points to {self.full(c.canonical)} which redirects back to this page - fix the canonical')
                else:
                    f.append(f'Canonical points to {self.full(c.canonical)} which {c.canonical_status}s - fix the canonical')
            if self.step[k] == 'Repurpose':
                f.append('If the URL changes, update anything redirecting to it')
            # IA audit moves: only where the two plans collide (the same URL redirected twice, or a redirect chain)
            gone = self.step[k] in ('Merge then Redirect', 'Remove then Redirect')
            if gone and k in self.ia_moves:
                f.append(f'The IA audit plans to move this page to {self.full(self.ia_moves[k])}. Drop that move: this page is being '
                         f'{"merged" if self.step[k].startswith("Merge") else "removed"}')
            t = self.target.get(k, '')
            if gone and t in self.ia_moves:
                f.append(f'The IA audit moves {self.full(t)} to {self.full(self.ia_moves[t])}. Once that move is live, point this redirect '
                         f'at {self.full(self.ia_moves[t])}')
            if k not in self.gpage.index and k not in self.ga4.index:
                f.append('No Search Console or GA4 data in the window')
            w = self.why[k]
            if merged_into.get(k) and self.step[k] in KEEPISH:
                w = f'Strongest page on this topic; {plural(merged_into[k], "page")} merge into it.' if 'No rule' in w else w + f' {plural(merged_into[k], "page")} merge into it.'
            w += overlap_note
            out[k] = '; '.join(['Suggested because: ' + w] + list(dict.fromkeys(f)))
        self.note = out

    # ---------------- redirects ----------------
    def find_target(self, k):
        slug = k.strip('/').split('/')[-1]
        if not slug:
            return '', 'NEEDS TARGET - no live page with the same slug'
        hits = [x for x in self.audited if x != k and x.strip('/').split('/')[-1] == slug]
        if not hits:
            return '', 'NEEDS TARGET - no live page with the same slug'
        svc = [x for x in hits if self.types[x][0] == 'Service']
        t = (svc or hits)[0]
        return self.resolve(t), 'SUGGESTED - check target'

    def resolve(self, t):
        seen = set()
        while t in self.step and self.step[t] not in KEEPISH and t in self.target and t not in seen:
            seen.add(t)
            t = self.target[t]
        return t

    def existing(self):
        rows, covered = [], set()
        jre = [(f, re.compile('^' + re.escape(f))) for f in self.junk]
        injunk = lambda k: any(r.match(k) for _, r in jre)
        for r in self.redirects.itertuples():
            if r.normalization_only == 'True' or injunk(r.source):
                continue
            covered.add(r.source)
            fin = r.final
            if str(r.final_status) == '200' and fin in self.step:
                if self.step[fin] in KEEPISH:
                    if int(r.hops) > 1:
                        rows.append((r.source, fin, f'Chain removed (was {" -> ".join(self.full(x) for x in r.chain.split(" -> "))})'))
                else:
                    t = self.resolve(fin)
                    rows.append((r.source, t, f'Existing redirect - repointed (was {self.full(fin)})'))
            else:
                t, note = self.find_target(fin if fin.startswith('/') else r.source)
                rows.append((r.source, t, f'{note}; Existing redirect ends on {self.full(fin)}, which is not a live page'))
        # demand that is not a live page
        nic = []
        ga = self.ga4
        keys = set(self.gpage.index) | set(ga.index)
        linked = self.links.groupby('dst')['src'].nunique()
        for k in sorted(keys):
            if not k.startswith('/') or (k in self.live.index):
                continue
            c, i = int(self.gpage.clicks.get(k, 0)), int(self.gpage.impr.get(k, 0))
            s = int(ga['sessions'].get(k, 0)) if len(ga) else 0
            fin = self.redirects.set_index('source')['final'].get(k, '') if k in set(self.redirects.source) else ''
            nic.append((self.full(k), c, i, s, self.full(fin) if fin else ''))
        for r in self.crawl[self.crawl.primary & (self.crawl.status != 200) & ~((self.crawl.status >= 300) & (self.crawl.status < 400))].itertuples():
            if r.key.startswith('/'):
                keys.add(r.key)
        for k in sorted(keys):
            if not k.startswith('/') or k in self.live.index or k in covered or injunk(k) or k in self.junk_pages:
                continue
            i = int(self.gpage.impr.get(k, 0))
            s = int(ga['sessions'].get(k, 0)) if len(ga) else 0
            n = int(linked.get(k, 0))
            if not (i or s or n):
                continue
            covered.add(k)
            t, note = self.find_target(k)
            dem = ', '.join(x for x in [plural(i, 'impression') if i else '', plural(s, 'session') if s else '',
                                        f'linked from {plural(n, "page")}' if n else ''] if x)
            rows.append((k, t, f'{note}; Not a live page per the crawl; {dem}'))
        # junk wildcards
        for f, t in self.junk.items():
            d = [k for k in self.live.index if self.folder(k) == f]
            im = int(self.gpage.impr.reindex(d).fillna(0).sum())
            rows.insert(0, (f + '*', t, f'Junk folder wildcard - {f} archive pages, {plural(len(d), "page")}, {plural(im, "impression")}. '
                                         'Disable these archives in the SEO plugin so they do not regenerate'))
        self.ex = rows
        self.nic = nic

    # ---------------- QA ----------------
    def run_qa(self):
        q = self.qa
        for k in self.audited:
            if self.step[k] in ('Merge then Redirect', 'Remove then Redirect'):
                t = self.target.get(k, '')
                if not t or t not in self.step or self.step[t] not in KEEPISH:
                    q.append(f'BREAKING: {k} -> target {t or "(blank)"} is not a live kept page')
        sources = collections.defaultdict(set)
        for k in self.audited:
            if self.step[k] in ('Merge then Redirect', 'Remove then Redirect'):
                sources[k].add(self.target.get(k, ''))
        for s, t, n in self.ex:
            if not t and not n.startswith('NEEDS TARGET'):
                q.append(f'BREAKING: {s} has a blank target without NEEDS TARGET')
            if t and (t not in self.step or self.step[t] not in KEEPISH):
                q.append(f'BREAKING: {s} -> {t} is not a live kept page')
            if s == t:
                q.append(f'BREAKING: self-redirect {s}')
            if s.endswith('*') and t.startswith(s[:-1]):
                q.append(f'BREAKING: wildcard {s} targets its own pattern')
            sources[s].add(t)
        for s, ts in sources.items():
            if len(ts) > 1:
                q.append(f'BREAKING: {s} has several targets {sorted(ts)}')
        allt = {t for ts in sources.values() for t in ts if t}
        for t in allt & set(sources):
            q.append(f'BREAKING: {t} is both a target and a source')
        for t in allt:
            for f in self.junk:
                if t.startswith(f):
                    q.append(f'BREAKING: target {t} is caught by the junk wildcard {f}*')
        missing = [k for k in self.live.index if k not in self.step and not self.in_junk(k)]
        if missing:
            q.append(f'GAP: {len(missing)} live page(s) have no audit row: {missing[:10]}')
        with open(self.p('qa.txt'), 'w') as f:
            f.write('\n'.join(q) + ('\n' if q else 'No problems found.\n'))

    # ---------------- write ----------------
    def write(self):
        T = self.types
        clicks, impr = self.gpage.clicks, self.gpage.impr
        nkw = self.gsc.groupby('key')['query'].nunique()
        h1c = self.live.loc[self.audited].h1.str.strip().replace('', pd.NA).value_counts()
        tc = self.live.loc[self.audited].title.str.strip().replace('', pd.NA).value_counts()
        inl = self.links.groupby('dst')['src'].nunique()
        outl = self.links.groupby('src')['dst'].nunique()
        ga = self.ga4
        rank = {t: i for i, t in enumerate(TYPES)}
        rows = []
        for k in self.audited:
            r = self.live.loc[k]
            gv = lambda c: (int(ga[c].get(k, 0)) if k in ga.index else '') if len(ga) else ''
            rows.append([self.full(k), T[k][0], T[k][1], '200', int(inl.get(k, 0)), int(outl.get(k, 0)), r.title, r.h1,
                         int(h1c.get(r.h1.strip(), 1) - 1) if r.h1.strip() else 0, int(tc.get(r.title.strip(), 1) - 1) if r.title.strip() else 0,
                         '', gv('key_events'), gv('new_users'), gv('sessions'), gv('views'), int(nkw.get(k, 0)),
                         int(clicks.get(k, 0)), int(impr.get(k, 0)), '', self.step[k],
                         self.full(self.target[k]) if self.target.get(k) else '', '', '', '', self.note[k]])
        rows.sort(key=lambda r: (rank.get(r[1], 99), -r[17]))
        clean = lambda v: str(v).replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
        with open(self.p('audit.tsv'), 'w', encoding='utf-8') as f:
            for r in rows:
                f.write('\t'.join(clean(v) for v in r) + '\n')
        with open(self.p('existing_redirects.tsv'), 'w', encoding='utf-8') as f:
            for s, t, n in self.ex:
                f.write('\t'.join(clean(v) for v in [self.full(s) if not s.endswith('*') else self.base + s, self.full(t) if t else '', n]) + '\n')
        with open(self.p('not_in_crawl.tsv'), 'w', encoding='utf-8') as f:
            f.write('url\tclicks\timpressions\tsessions\tredirect target\n')
            for r in self.nic:
                f.write('\t'.join(clean(v) for v in r) + '\n')
        run = load_json(self.p('run.json'), {}) or {}
        run.update({'domain': self.dom, 'window': self.a.window, 'ga4': self.a.ga4_status or ('file' if self.a.ga4 else 'not used'),
                    'gsc_clicks': int(clicks.sum()), 'folder_map': self.fm.get('folders', {}),
                    'blog_listing': self.fm.get('blog_listing', ''), 'cities': self.cities,
                    'separate_cities': len(self.sep), 'overlap': OVERLAP, 'remove_impressions': REMOVE_IMPR,
                    'junk_pages': {f: sum(1 for k in self.live.index if self.folder(k) == f) for f in self.junk},
                    'blog_beats': {self.full(k): self.full(v) for k, v in self.blog_beats.items()},
                    'copies': {self.full(k): self.full(v) for k, v in self.copies.items()},
                    'menu_redirects': self.menu_redirects(),
                    'ia': bool(self.ia), 'ia_folder_map': self.ia_fm, 'ia_menu': sorted(self.full(x) for x in self.ia_menu),
                    'ia_moved_targets': sorted({f'{self.full(sr)} -> {self.full(tg)} (IA moves it to {self.full(self.ia_moves[tg])})'
                                               for sr, tg, _ in self.ex if tg in self.ia_moves})})
        save_json(self.p('run.json'), run)
        return rows

    def menu_redirects(self):
        nav = self.links[self.links.cls == 'Nav']
        r = self.redirects[self.redirects.normalization_only != 'True'].set_index('source')
        out = {}
        for d in sorted(set(nav.dst) & set(r.index)):
            fin = r.loc[d, 'final'] if isinstance(r.loc[d, 'final'], str) else r.loc[d, 'final'].iloc[0]
            if fin in self.step:
                out[self.full(d)] = self.full(self.resolve(fin))
        return out

    def report_files(self):
        """Report-only lists (references/redirects-qa.md, Internal links to update; SKILL.md report)."""
        r = self.redirects[self.redirects.normalization_only != 'True'].drop_duplicates('source').set_index('source')['final']
        dead = {k for k, st in self.status.items() if k.startswith('/') and st >= 400}
        L = self.links[self.links.dst.isin(set(r.index) | dead) & self.links.src.isin(self.live.index)]
        out = pd.DataFrame({'linking_page': L.src.map(self.full), 'old_url': L.dst.map(self.full),
                            'final_url': L.dst.map(lambda d: self.full(self.resolve(r[d])) if d in r.index else '(404, no redirect)'),
                            'link_class': L.cls}).drop_duplicates().sort_values(['link_class', 'linking_page'])
        out.to_csv(self.p('internal_links_to_update.csv'), index=False)
        c = self.crawl[(self.crawl.status == 200) & self.crawl.url.str.contains(r'^https?://[^/]+/[^?#]*[A-Z]', regex=True)]
        pd.DataFrame({'url': c.url, 'lowercase_page': c.key.map(self.full)}).to_csv(self.p('case_duplicates.csv'), index=False)
        return len(out), len(c)

    def main(self):
        self.load()
        self.page_types()
        self.junk_candidates()
        self.junk_pages = set()
        keep_anyway = set()
        for k in self.live.index:
            if self.in_junk(k):
                c = self.gpage.clicks.get(k, 0)
                ke = self.ga4['key_events'].get(k, 0) if len(self.ga4) else 0
                if c >= 5 or ke > 0:
                    keep_anyway.add(k)
                else:
                    self.junk_pages.add(k)
        self.audited = [k for k in self.live.index if k not in self.junk_pages]
        self.groups()
        self.overlap()
        self.city_copies()
        self.suggest()
        self.rule5_6_candidates()
        self.notes()
        self.existing()
        self.run_qa()
        rows = self.write()
        nl, nc = self.report_files()
        st = collections.Counter(r[19] for r in rows)
        ty = collections.Counter(r[1] for r in rows)
        print(f'{len(rows)} audit rows, {len(self.junk_pages)} pages in junk folders ({len(keep_anyway)} kept as rows: 5+ clicks or conversions)')
        print('Page types:', ', '.join(f'{t} {n}' for t, n in ty.most_common()))
        print('Suggestions:', ', '.join(f'{t} {n}' for t, n in st.most_common()))
        print(f'Existing redirect rows: {len(self.ex)}; not in crawl: {len(self.nic)}; city copies: {len(self.copies)}')
        print(f'Check page type (Root-level / No rule matched): {sum(1 for r in rows if "Root-level" in r[2] or "No rule matched" in r[2])}')
        print(f'Internal links to redirected or 404 URLs: {nl} (internal_links_to_update.csv); case duplicates: {nc} (case_duplicates.csv)')
        for f in ['junk_candidates.csv', 'title_group_candidates.csv', 'rule5_candidates.csv', 'rule6_candidates.csv']:
            print(f'{f}: {len(pd.read_csv(self.p(f)))} rows')
        print('QA:', open(self.p('qa.txt')).read().strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domain', required=True)
    ap.add_argument('--work', default='work')
    ap.add_argument('--gsc', required=True, help='Search Console page + query file (CSV, XLSX, or the attached Google Sheet)')
    ap.add_argument('--gsc-tab', help='which tab to use when the file has several (references/data.md)')
    ap.add_argument('--window', required=True, help='how long the Search Console data covers, e.g. "last 90 days"')
    ap.add_argument('--ga4')
    ap.add_argument('--ga4-status', help='one line for the README, e.g. "skipped: 100 Search Console clicks (under 300)"')
    Run(ap.parse_args()).main()


if __name__ == '__main__':
    main()
