"""Build the prospect audit workbook from work/ (prep.py output plus the decisions files).

Reads:   work/config.json, work/crawl.csv, work/thin_candidates.csv, work/ranking.csv, work/gap.csv,
         work/gap_groups.json, work/thin_decisions.json (optional), work/other_audits.json (optional)
Writes:  the .xlsx (Read Me, Summary, Competitor Keyword Gap, Gap Keywords, Thin Content,
         Ranking URLs Not Live, Ranking Pages) and prints the QA checks.

Volume and traffic are the keyword tool's estimates. They are labeled as estimates everywhere and are
never summed across keywords or pages.
"""
import argparse
import os
import re
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from common import load_json
from prep import THIN_WORDS

EST = '(tool estimate)'
KINDS = ('service', 'concern', 'location', 'other', 'exclude')
HEAD = PatternFill('solid', fgColor='1F3864')


def words(s):
    return re.sub(r'[^a-z0-9]+', ' ', str(s).lower()).strip()


def term_re(term):
    w = words(term).split()
    return re.compile(r'(?<![a-z0-9])' + r'[^a-z0-9]+'.join(map(re.escape, w)) + r'(?:s|es)?(?![a-z0-9])')


def match_any(res, text):
    return any(r.search(text) for r in res)


def sheet(wb, title, header, rows, widths=None):
    ws = wb.create_sheet(title)
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical='top')
    for r in rows:
        ws.append(['' if (isinstance(v, float) and v != v) else v for v in r])
    ws.freeze_panes = 'A2'
    if rows:
        ws.auto_filter.ref = f'A1:{get_column_letter(len(header))}{len(rows) + 1}'
    for i, h in enumerate(header, 1):
        ws.column_dimensions[get_column_letter(i)].width = (widths or {}).get(h, min(max(len(h) + 2, 12), 40))
    return ws


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', default='work')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    w = a.work
    P = lambda n: os.path.join(w, n)
    cfg = load_json(P('config.json'), {})
    if not os.path.exists(P('crawl.csv')):
        raise SystemExit('work/crawl.csv is missing: run prep.py crawl first.')
    crawl = pd.read_csv(P('crawl.csv'), keep_default_na=False, na_values=[''])
    for c in ('title', 'h1', 'url', 'folder'):
        crawl[c] = crawl[c].fillna('')
    live = crawl[(crawl['status'] == 200) & crawl['indexable'].astype(bool)]
    checks = []

    def check(name, ok, detail=''):
        checks.append((name, ok, detail))
        print(('PASS ' if ok else 'FAIL ') + name + (f': {detail}' if detail else ''))

    ranking = pd.read_csv(P('ranking.csv')) if os.path.exists(P('ranking.csv')) else None
    gap = pd.read_csv(P('gap.csv')) if os.path.exists(P('gap.csv')) else None
    tool = open(P('tool.txt')).read() if os.path.exists(P('tool.txt')) else 'none'
    competitors = [c for c in (gap.columns if gap is not None else []) if c not in ('keyword', 'est_volume', 'kd', 'prospect_position')]

    # ---------------- thin content
    cand = pd.read_csv(P('thin_candidates.csv'), keep_default_na=False)
    dec = load_json(P('thin_decisions.json'), {})
    ex_f = {f.lower() for f in dec.get('exclude_folders', [])}
    ex_u = set(dec.get('exclude_urls', []))
    drop = cand['folder'].str.lower().isin(ex_f) | cand['url'].isin(ex_u)
    thin = cand[~drop].copy()
    tracked = {}
    if ranking is not None:
        tracked = ranking.groupby('norm')['keyword'].count().to_dict()
    from common import norm_url
    thin['tracked'] = thin['url'].map(lambda u: tracked.get(norm_url(u), 0) if ranking is not None else '')
    check('thin rows + excluded = candidates', len(thin) + int(drop.sum()) == len(cand),
          f'{len(thin)} kept, {int(drop.sum())} excluded (folders: {sorted(ex_f) or "none"})')

    # ---------------- ranking URLs vs crawl
    notlive_rows, page_rows = [], []
    if ranking is not None:
        st = crawl.drop_duplicates('norm').set_index('norm')['status'].to_dict()
        r = ranking.copy()
        r['rank_key'] = list(zip(-r['est_traffic'].fillna(-1), r['position'].fillna(999)))
        for norm, g in r.groupby('norm'):
            top = g.sort_values(['est_traffic', 'position'], ascending=[False, True]).iloc[0]
            s = st.get(norm)
            status = 'Not in crawl' if s is None else (int(s) if s == s else 'No status')
            page_rows.append([top['url'], status, len(g), top['keyword'], top['position'], top['est_volume'], top['est_traffic']])
            if status != 200:
                notlive_rows.append([top['url'], status, len(g), top['keyword'], top['position'], top['est_volume']])
        page_rows.sort(key=lambda x: -(x[6] if x[6] == x[6] else -1))
        notlive_rows.sort(key=lambda x: -x[2])
        check('ranking URLs reconcile', len(page_rows) == ranking['norm'].nunique(),
              f'{len(page_rows)} URLs, {len(notlive_rows)} not a live 200 page in the crawl')

    # ---------------- keyword gap groups
    group_rows, gap_detail, summary_gap = [], [], {}
    if gap is not None:
        spec = load_json(P('gap_groups.json'), None)
        if not spec:
            raise SystemExit('work/gap_groups.json is missing: write the groups (see references/rules.md).')
        groups = []
        for gdef in spec:
            kind = gdef.get('kind', 'other')
            if kind not in KINDS or not gdef.get('terms') or not gdef.get('group'):
                raise SystemExit(f'Group {gdef}: needs group, terms and kind in {KINDS}.')
            groups.append({**gdef, 'kind': kind, 're': [term_re(t) for t in gdef['terms']]})
        gap['kw'] = gap['keyword'].map(words)
        gap['group'] = '(unassigned)'
        for g in groups:
            m = (gap['group'] == '(unassigned)') & gap['kw'].map(lambda k: match_any(g['re'], k))
            gap.loc[m, 'group'] = g['group']
        by_name = {g['group']: g for g in groups}
        pages = live.assign(hay=(live['url'].map(lambda u: words(re.sub(r'^[a-z]+://[^/]+', '', u)))
                                 + ' ' + live['title'].map(words) + ' ' + live['h1'].map(words)))
        for g in groups:
            if g['kind'] == 'exclude':
                continue
            sub = gap[gap['group'] == g['group']]
            if sub.empty:
                continue
            top = sub.sort_values('est_volume', ascending=False).iloc[0]
            mp = pages[pages['hay'].map(lambda h: match_any(g['re'], h))]
            if mp.empty:
                pc = 'Possible missing service page' if g['kind'] == 'service' else 'No matching page in the crawl'
            elif (mp['words'].fillna(0) < THIN_WORDS).all():
                pc = 'Only thin pages match'
            else:
                pc = 'Has a matching page'
            row = [g['group'], g.get('practice_type', ''), g['kind'], len(sub), top['keyword'], top['est_volume']]
            for c in competitors:
                row += [sub[c].min() if sub[c].notna().any() else '', int(sub[c].notna().sum())]
            row += [len(mp), pc, g.get('service_gap_ref', ''), g.get('notes', '')]
            group_rows.append(row)
        group_rows.sort(key=lambda x: -(x[5] if x[5] == x[5] else -1))
        for _, r in gap.sort_values('est_volume', ascending=False).iterrows():
            gap_detail.append([r['keyword'], r['group'], r['est_volume'], r['kd']] + [r[c] for c in competitors])
        n_ex = int((gap['group'].map(lambda x: by_name.get(x, {}).get('kind')) == 'exclude').sum())
        n_un = int((gap['group'] == '(unassigned)').sum())
        n_as = len(gap) - n_ex - n_un
        summary_gap = dict(total=len(gap), excluded=n_ex, unassigned=n_un, assigned=n_as, groups=len(group_rows))
        check('gap keywords reconcile', n_as + n_ex + n_un == len(gap), f'{n_as} assigned + {n_ex} excluded + {n_un} unassigned = {len(gap)}')
        check('every group has at least one match term', all(g['terms'] for g in groups))
        if n_un / max(len(gap), 1) > 0.25:
            print(f'WARNING: {n_un / len(gap):.0%} of gap keywords are unassigned. Add groups for the largest unassigned keywords.')

    # ---------------- workbook
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet('Read Me')
    notes = [
        f'Prospect audit for {cfg.get("client", cfg.get("domain", ""))} ({cfg.get("domain", "")}).',
        'Built from outside data only: a site crawl and keyword exports. There is no Search Console or GA4 access.',
        f'Keyword data: {tool}. Search volume and traffic are the keyword tool\'s estimates {EST}. They are not clicks or impressions, '
        'and they are never added up across keywords or pages.',
        'Keyword data is a snapshot of current positions, so it shows no trend. It covers keywords the tool tracks, mostly the top 100 '
        'positions. A page marked "no tracked keywords" may still get visits.',
        'Competing pages are not checked: these exports list one ranking URL per keyword.',
        f'Thin content: indexable 200 pages under {THIN_WORDS} content words in the crawl, minus the folders and URLs a person excluded.',
        'Possible missing service page: no live, indexable page in the crawl has the group\'s terms in its URL, title or H1. Confirm the practice offers the service.',
    ]
    for n in notes:
        ws.append([n])
    ws.column_dimensions['A'].width = 140
    for row in ws.iter_rows():
        row[0].alignment = Alignment(wrap_text=True, vertical='top')

    s = [['Pages crawled (all statuses)', len(crawl)], ['Pages returning 200', int((crawl['status'] == 200).sum())],
         ['Indexable 200 pages', len(live)], [f'Thin pages (under {THIN_WORDS} words, after exclusions)', len(thin)],
         ['Thin candidates excluded by a person', len(cand) - len(thin)]]
    if ranking is not None:
        s += [['URLs with tracked keywords', len(page_rows)], ['Of those, not a live 200 page in the crawl', len(notlive_rows)]]
    if gap is not None:
        s += [['Gap keywords (competitors rank, prospect does not)', summary_gap['total']],
              ['  in groups', summary_gap['assigned']], ['  left out (competitor or brand searches)', summary_gap['excluded']],
              ['  not yet in a group', summary_gap['unassigned']], ['Gap groups', summary_gap['groups']],
              ['Service groups with a possible missing page', sum(1 for r in group_rows if r[2] == 'service' and r[-3] == 'Possible missing service page')]]
    others = load_json(P('other_audits.json'), [])
    ws = sheet(wb, 'Summary', ['Measure', 'Count'], s, {'Measure': 60, 'Count': 14})
    if others:
        ws.append([])
        ws.append(['Other audits in this engagement', 'Status', 'File', 'Note'])
        for c in ws[ws.max_row]:
            c.font = Font(bold=True)
        for o in others:
            ws.append([o.get('name', ''), o.get('status', ''), o.get('file', ''), o.get('note', '')])

    if gap is not None:
        h = ['Group', 'Practice type', 'Kind', 'Keywords in group', 'Largest search', f'Its est. monthly searches {EST}']
        for c in competitors:
            h += [f'{c}: best position', f'{c}: keywords ranked']
        h += ['Pages on site matching', 'Page check', 'Service gap result', 'Notes']
        sheet(wb, 'Competitor Keyword Gap', h, group_rows, {'Group': 28, 'Largest search': 30, 'Page check': 30, 'Notes': 40})
        sheet(wb, 'Gap Keywords', ['Keyword', 'Group', f'Est. monthly searches {EST}', 'Keyword difficulty'] + [f'{c}: position' for c in competitors],
              gap_detail, {'Keyword': 44, 'Group': 28})
    sheet(wb, 'Thin Content', ['URL', 'Content words', 'Reason', 'Title', 'H1', 'Folder', 'Tracked keywords' if ranking is not None else 'Tracked keywords (no export)'],
          [[r.url, r.words, r.reason, r.title, r.h1, r.folder, r.tracked if r.tracked != 0 or ranking is None else 'No tracked keywords'] for r in thin.itertuples()],
          {'URL': 60, 'Title': 40, 'H1': 40})
    if ranking is not None:
        sheet(wb, 'Ranking URLs Not Live', ['URL', 'Crawl status', 'Tracked keywords', 'Top keyword', 'Position', f'Est. monthly searches {EST}'],
              notlive_rows, {'URL': 70})
        sheet(wb, 'Ranking Pages', ['URL', 'Crawl status', 'Tracked keywords', 'Top keyword (by est. traffic)', 'Position',
                                    f'Est. monthly searches {EST}', f'Est. traffic {EST}'], page_rows, {'URL': 70})
    wb.save(a.out)

    heads = [ws_.title for ws_ in wb.worksheets]
    bad = []
    for ws_ in wb.worksheets:
        for c in ws_[1]:
            h = str(c.value or '').lower()
            if 'clicks' in h or 'impressions' in h or (('searches' in h or 'traffic' in h) and 'tracked' not in h and 'estimate' not in h and 'est.' not in h):
                bad.append(f'{ws_.title}: {c.value}')
    check('estimated columns are labeled as estimates, none called clicks or impressions', not bad, '; '.join(bad))
    check('workbook saved', os.path.exists(a.out), f'{a.out}; tabs: {", ".join(heads)}')
    if not all(ok for _, ok, _ in checks):
        sys.exit(1)
    print('All checks passed')


if __name__ == '__main__':
    main()
