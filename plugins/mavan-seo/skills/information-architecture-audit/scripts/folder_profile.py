#!/usr/bin/env python3
"""Profile the site's folders and propose a folder-to-page-type mapping for a person to confirm.

Usage:
  python folder_profile.py --work work [--deep folder1,folder2]

Reads   work/crawl_pages.csv (written by prep.py).
Writes  work/review/folder_profile.csv           every profiled folder with its numbers and samples
        work/review/folder_mapping.md            the table to show the person (also printed)
        work/review/folder_mapping_proposal.json the proposal in decisions.json form

Nothing is assumed about the site's URL structure. For every first-level folder and for the root
level it reports the number of live pages, the share of live pages, sample pages with their titles and
H1s, the median content words, and how many pages read like articles. Folders with more than 30 pages
(or named in --deep) also get their second-level folders profiled. The proposed type is a starting
point: a common folder name (services, blog, ...) is only one piece of evidence, and the person
confirms or corrects every row before analyze.py will run.
"""
import argparse
import collections
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import (ARCHIVE_FOLDERS, BLOG_FOLDERS, BLOG_PHRASES, COMPANY_WORDS, CONCERN_FOLDERS,  # noqa: E402
                     GALLERY_FOLDERS, LOCATION_FOLDERS, QUESTION_WORDS, SERVICE_FOLDERS, median, segs, words)
from common import load_json, save_json  # noqa: E402

FORMULA_BLOG_FOLDERS = ('blog', 'blogs', 'articles', 'news', 'resources')  # what the template Area formula knows
SAMPLES = 5
BIG_FOLDER = 30


def article_like(slug, h1):
    """True if a page reads like an article: question or long slug, blog wording, or a question H1."""
    toks = words(slug)
    text = ' '.join(toks)
    h1w = ' '.join(words(h1))
    if toks and toks[0] in QUESTION_WORDS:
        return True
    if len(toks) >= 6:
        return True
    if any(re.search(r'\b' + p + r'\b', text) or re.search(r'\b' + p + r'\b', h1w) for p in BLOG_PHRASES):
        return True
    return str(h1).strip().endswith('?')


def pick(keys, n=SAMPLES):
    keys = sorted(keys)
    if len(keys) <= n:
        return keys
    return [keys[round(i * (len(keys) - 1) / (n - 1))] for i in range(n)]


def trim(x, n=60):
    x = re.sub(r'\s+', ' ', str(x)).strip()
    return x if len(x) <= n else x[:n - 1] + '…'


def propose(name, pages, art_pct):
    """(type, confidence, evidence) for a folder. The folder name is one piece of evidence, not the answer."""
    low = name.lower().split('/')[-1]
    if re.fullmatch(r'(19|20)\d\d', low):
        return 'Archive', 'Medium', 'year folder, looks like a date archive'
    if low in ARCHIVE_FOLDERS:
        return 'Archive', 'High', 'common CMS archive folder name'
    if low in GALLERY_FOLDERS:
        return 'Gallery item', 'Medium', 'common gallery or media folder name; the folder\'s own page would be Company / Info'
    by_name = ('Blog' if low in BLOG_FOLDERS else 'Service' if low in SERVICE_FOLDERS else
               'Concern' if low in CONCERN_FOLDERS else 'Location / Area' if low in LOCATION_FOLDERS else
               'Company / Info' if (low in COMPANY_WORDS or set(words(low)) & COMPANY_WORDS) else None)
    reads_like_articles = art_pct >= 0.4
    if by_name == 'Blog' and reads_like_articles:
        return 'Blog', 'High', f'common blog folder name and {art_pct:.0%} of pages read like articles'
    if by_name == 'Blog':
        return 'Blog', 'Medium', f'common blog folder name, but only {art_pct:.0%} of pages read like articles'
    if by_name and reads_like_articles:
        return 'Mixed', 'Low', (f'name suggests {by_name}, but {art_pct:.0%} of pages read like articles: '
                                f'probably holds more than one kind of page')
    if by_name:
        return by_name, 'Medium', f'common folder name for {by_name}; {art_pct:.0%} of pages read like articles'
    if reads_like_articles and pages >= 5:
        return 'Blog', 'Medium', f'{art_pct:.0%} of pages read like articles, though the folder name is not a usual blog name'
    if pages < 3:
        return 'Mixed', 'Low', 'too few pages to tell; the content rules will type each page'
    return f'{name.split("/")[-1].replace("-", " ").capitalize()} (folder)', 'Low', \
        'no usual name and the samples do not settle it: please say what this folder holds'


def profile_group(label, level, rows, total):
    rows = list(rows)
    keys = [r.key for r in rows]
    art = [article_like(r.key.rstrip('/').split('/')[-1], r.h1) for r in rows]
    q = [str(r.h1).strip().endswith('?') or bool(words(r.key.rstrip('/').split('/')[-1])[:1] and
                                                 words(r.key.rstrip('/').split('/')[-1])[0] in QUESTION_WORDS)
         for r in rows]
    by_key = {r.key: r for r in rows}
    samples = [f'{k} - {trim(by_key[k].h1 or by_key[k].title)}' for k in pick(keys)]
    words_ = [float(r.words) for r in rows if str(r.words) not in ('', 'nan')]
    art_pct = sum(art) / len(rows) if rows else 0
    return {'folder': label, 'level': level, 'pages': len(rows), 'share': round(len(rows) / total, 3) if total else 0,
            'median_words': median(words_), 'question_pct': round(sum(q) / len(rows), 2) if rows else 0,
            'article_pct': round(art_pct, 2), 'samples': samples}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work')
    ap.add_argument('--deep', default='', help='comma-separated first-level folders to profile at second level too')
    a = ap.parse_args()
    W = a.work
    R = os.path.join(W, 'review')
    os.makedirs(R, exist_ok=True)
    crawl = pd.read_csv(os.path.join(W, 'crawl_pages.csv'), dtype={'url': str, 'key': str}, keep_default_na=False)
    live = crawl[(pd.to_numeric(crawl.status, errors='coerce') == 200) & ~crawl.has_query.astype(str).eq('True')]
    live = live.drop_duplicates('key')
    live = live[live.key.str.startswith('/') & (live.key != '/')]
    total = len(live)
    deep = {d.strip().strip('/').lower() for d in a.deep.split(',') if d.strip()}

    # group pages: first-level folder = first path part of pages that sit at least two parts deep
    folders = collections.defaultdict(list)
    root_pages = []
    folder_names = {segs(k)[0] for k in live.key if len(segs(k)) >= 2}
    for r in live.itertuples():
        s = segs(r.key)
        if len(s) >= 2:
            folders[s[0]].append(r)
        elif s[0] in folder_names:
            folders[s[0]].append(r)   # the folder's own index page counts with the folder
        else:
            root_pages.append(r)

    out = []
    for name, rows in sorted(folders.items(), key=lambda kv: -len(kv[1])):
        p = profile_group('/' + name + '/', 'first', rows, total)
        t, c, ev = propose(name, p['pages'], p['article_pct'])
        p.update({'proposed_type': t, 'confidence': c, 'evidence': ev})
        out.append(p)
        if p['pages'] > BIG_FOLDER or name.lower() in deep:
            sub = collections.defaultdict(list)
            for r in rows:
                s = segs(r.key)
                if len(s) >= 3:
                    sub[s[1]].append(r)
            for sname, srows in sorted(sub.items(), key=lambda kv: -len(kv[1])):
                if len(srows) < 3:
                    continue
                sp = profile_group(f'/{name}/{sname}/', 'second', srows, total)
                st, sc, sev = propose(f'{name}/{sname}', sp['pages'], sp['article_pct'])
                sp.update({'proposed_type': st, 'confidence': sc, 'evidence': sev})
                out.append(sp)
    if root_pages:
        p = profile_group('(root level: pages with no folder)', 'root', root_pages, total)
        p.update({'proposed_type': 'Mixed', 'confidence': '-',
                  'evidence': 'root-level pages are typed one by one from their slug and H1 (company, city, article or service wording)'})
        out.append(p)

    df = pd.DataFrame(out)
    df['samples_text'] = df.samples.map(lambda x: ' || '.join(x))
    df.drop(columns=['samples']).to_csv(os.path.join(R, 'folder_profile.csv'), index=False)

    # CMS-looking URL patterns (all crawled URLs, any status)
    pats = collections.Counter()
    where = collections.defaultdict(set)
    for u, k in zip(crawl.url.str.lower(), crawl.key):
        s = segs(k)
        f0 = s[0] if s else ''
        if re.search(r'[?&](page|paged|pg)=\d+', u):
            pats['pagination with ?page=N'] += 1
        elif re.search(r'/page/\d+/?$', k):
            pats['pagination with /page/N/'] += 1
            where['pagination with /page/N/'].add(f'/{f0}/')
        elif '?' in u:
            pats['other URLs with a query string'] += 1
        if f0 in ARCHIVE_FOLDERS or (re.fullmatch(r'(19|20)\d\d', f0) and len(s) <= 3):
            pats[f'/{f0}/ archive pages'] += 1
        if 'attachment' in s:
            pats['attachment pages'] += 1
            where['attachment pages'].add(f'/{f0}/')

    blog_candidates = df[(df.proposed_type == 'Blog') & (df.level == 'first')]
    service_candidates = df[(df.proposed_type == 'Service') & (df.level == 'first')]
    blog_folder = blog_candidates.iloc[0].folder if len(blog_candidates) else ''
    service_folder = service_candidates.iloc[0].folder if len(service_candidates) else ''
    in_formula = bool(blog_folder) and blog_folder.strip('/').lower() in FORMULA_BLOG_FOLDERS

    lines = [f'# Folder profile and proposed mapping: {total} live pages', '',
             '| Folder | Pages | Share | Proposed type | Confidence | Evidence | Sample pages |',
             '| --- | ---: | ---: | --- | --- | --- | --- |']
    for r in df.itertuples():
        lines.append(f'| {r.folder} | {r.pages} | {r.share:.0%} | {r.proposed_type} | {r.confidence} | '
                     f'{r.evidence.replace("|", "/")} | ' + '<br>'.join(x.replace('|', '/') for x in r.samples[:3]) + ' |')
    lines += ['', 'Second-level rows (level "second" in folder_profile.csv) are shown for large folders. To type them '
                  'separately, map the first-level folder as Mixed and add the second-level folder to folder_types '
                  'as "folder/subfolder".']
    if pats:
        lines += ['', 'URL patterns that look like automatic CMS pages:']
        for k, n in pats.most_common():
            w = f' (in {", ".join(sorted(where[k]))})' if where.get(k) else ''
            lines.append(f'- {n} x {k}{w}')
    lines += ['', f'Blog folder: {blog_folder or "none proposed"}. Service folder: {service_folder or "none proposed"}.']
    if blog_folder and not in_formula:
        lines.append(f'NOTE: {blog_folder} is not one of /blog/, /blogs/, /articles/, /news/ or /resources/, which is all the '
                     f'template Area formula recognises, so every post would be tagged "Blog URLs" on All Pages.')
    unsure = df[df.confidence == 'Low']
    if len(unsure):
        lines.append('Not sure about: ' + ', '.join(unsure.folder) + '.')
    lines += ['', 'STOP. Show this table to the person and wait. Do not classify pages until they confirm or correct it.']
    text = '\n'.join(lines)
    open(os.path.join(R, 'folder_mapping.md'), 'w', encoding='utf-8').write(text + '\n')

    proposal = {'folder_types': {r.folder.strip('/'): r.proposed_type for r in df.itertuples() if r.level == 'first'},
                'blog_folder': blog_folder, 'service_folder': service_folder}
    save_json(os.path.join(R, 'folder_mapping_proposal.json'), proposal)
    print(text)


if __name__ == '__main__':
    main()
