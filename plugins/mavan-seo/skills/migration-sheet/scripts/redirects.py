#!/usr/bin/env python3
"""Decisions, redirect target resolution, the discrepancy list and the redirect checks. Pure functions, no file reads here
(build.py reads the files and calls resolve_all).

Who decides what (Amanda, Nov 15):
  Content Prune decides whether a page stays, merges or is removed. The IA audit decides the URL of a page that stays.
  Order per URL: Content Prune's action, then the IA move for a page that stays, then keep at the same URL.

The audits already cross-check each other. This is the safety net: where a redirect target is itself moving, merged or
redirected, the redirect points to the page's final URL in one hop, and every such change is listed (option A).
"""
import re


def wild_prefix(src):
    """'/folder/*', 'https://example.com/folder/*' or '/folder/(.*)' -> '/folder/' (lowercase path before the star)."""
    s = re.sub(r'^https?://[^/]+', '', str(src).strip().lower())
    s = re.sub(r'\(\.\*\)\$?$', '*', s)
    return s.split('*')[0] if '*' in s else ''


def gone_code(target):
    return 410 if str(target).upper().endswith('410') else 404


def resolve_all(master, live, audits, crawl_redirects, new_urls=(), seo=None):
    """
    master           {key: {'backlinks': int, 'impressions': float, 'media': bool}}  every old URL worth deciding
    live             set of keys the crawl found with status 200 (pages only)
    audits           the audits.json structure (prune, ia, gap)
    crawl_redirects  {source key: final key} redirects already on the old site
    new_urls         keys of new pages (URL filled in by the SEO)
    seo              pass 2 only: {'targets': {old: target or 'GONE'/'GONE 410'}, 'reasons': {old: text},
                                    'media': {key: {'decision': 'keep'|'redirect', 'new': key}}}
    Returns {'rows', 'discrepancies', 'problems', 'finals', 'counts'}.
    """
    seo = seo or {}
    pr, ia = audits['prune'], audits['ia']
    problems, disc = [], []
    d = {}  # key -> {'act': keep|move|merge|redirect|gone, 'to': target, 'by': text}

    # ---- wildcard rules (counted once as a rule, not once per URL)
    wild = []
    for w in pr['wildcards']:
        p = wild_prefix(w['source'])
        if p:
            wild.append({'source': w['source'], 'prefix': p, 'target': w['target'], 'regex': w.get('regex', 0)})
    covered = lambda k: next((w for w in wild if k.startswith(w['prefix'])), None)

    # ---- Content Prune decisions
    for kind, by in (('merge', 'Content Prune (Merge pages)'), ('remove', 'Content Prune (Remove pages)')):
        for r in pr[kind]:
            s, t = r['source'], r['target']
            if s in d and d[s]['to'] != t:
                problems.append(f"{s} is on the prune tabs with two different targets ({d[s]['to']} and {t}).")
                continue
            act = 'gone' if str(t).startswith('GONE') else ('merge' if kind == 'merge' else 'redirect')
            if act == 'gone' and kind == 'merge':
                problems.append(f'{s} is merged into "Gone": a merge needs a surviving page.')
                continue
            d[s] = {'act': act, 'to': t, 'by': by}
    # ---- IA moves (only for pages that stay)
    moves = {}
    for m in ia['moves']:
        o, n = m['old'], m['new']
        if o in d:
            disc.append({'kind': 'IA move dropped', 'old': o,
                         'said': f"IA audit: move to {n}. Content Prune: {d[o]['act']} to {d[o]['to']}",
                         'did': 'Kept the Content Prune decision and dropped the move', 'source': 'IA audit (Moves) vs Content Prune'})
            continue
        moves[o] = n
    # ---- live pages with no prune action stay (at the moved URL when the IA moves them)
    for k in sorted(set(live) | set(moves)):
        if k not in d:
            explicit = k in moves or k in pr['keep'] or k in pr['update']
            if covered(k) and not explicit:
                continue  # a page inside a Junk folder rule is removed by the rule
            d[k] = {'act': 'move' if k in moves else 'keep', 'to': moves.get(k, k),
                    'by': 'IA audit (Moves)' if k in moves else 'Stays (no prune action)'}
    # ---- existing site redirects carry over unless an audit already decided that URL
    for s, f in crawl_redirects.items():
        if s not in d and not covered(s):
            d[s] = {'act': 'redirect', 'to': f, 'by': 'Existing site redirect (crawl)', 'existing': True}

    def keep_final(k):
        return d[k]['to'] if d[k]['act'] in ('keep', 'move') else None

    def final(t):
        """Follow a target to the URL it ends at. Returns (url or None, why-not)."""
        seen, cur = [], t
        while True:
            if cur in seen:
                return None, 'loop: ' + ' -> '.join(seen + [cur])
            seen.append(cur)
            a = d.get(cur)
            if a is None:
                return cur, None
            if a['act'] in ('keep', 'move'):
                return a['to'], None
            if a['act'] == 'gone':
                return None, f'{cur} is being removed (Gone)'
            cur = a['to']

    finals = {k: keep_final(k) for k in d if keep_final(k)}
    valid = set(finals.values()) | set(new_urls)
    rows, used_src = [], set()

    def row(old, action, final_url, code, by, **kw):
        m = master.get(old, {})
        r = {'old': old, 'action': action, 'final': final_url, 'code': code, 'by': by,
             'backlinks': int(m.get('backlinks', 0)), 'impressions': m.get('impressions', 0), 'open': False, 'reason': '', 'note': ''}
        r.update(kw)
        rows.append(r)
        if old in used_src and action in ('merge', 'redirect', 'gone'):
            problems.append(f'{old} appears twice as a redirect source.')
        used_src.add(old)
        return r

    for k, a in sorted(d.items()):
        if covered(k) and a['act'] in ('merge', 'redirect', 'gone') and not a.get('existing'):
            continue
        if a['act'] in ('keep', 'move'):
            w = covered(k)
            if w:
                problems.append(f'{k} stays but is inside the wildcard rule {w["source"]}.')
            row(k, 'keep', a['to'], 200, a['by'], moved=(a['act'] == 'move'))
            continue
        if a['act'] == 'gone':
            r = row(k, 'gone', '', gone_code(a['to']), a['by'], reason=seo.get('reasons', {}).get(k, ''))
            r['open'] = not r['reason']
            continue
        written = a['to']
        end, why = final(written)
        if end is None:
            problems.append(f'{k} redirects to {written}, which cannot be resolved ({why}).')
            row(k, a['act'], written, 301, a['by'], note=why or '')
            continue
        if end != written:
            disc.append({'kind': 'Redirect chain fixed' if not a.get('existing') else 'Existing redirect repointed', 'old': k,
                         'said': f'{a["by"]}: {written}', 'did': f'Points to {end} in one hop',
                         'source': a['by'] + ' + the page that target ended at'})
        if end == k:
            problems.append(f'{k} redirects to itself.')
        if end not in valid:
            problems.append(f'{k} redirects to {end}, which is not a page that stays or a new page.')
        row(k, a['act'], end, 301, a['by'], written=written)

    # ---- wildcard rules: one row per rule, and a target may not sit inside a wildcard
    for w in wild:
        end, why = final(w['target']) if w['target'] and not str(w['target']).startswith('GONE') else (w['target'], None)
        tgt = end if end else w['target']
        if tgt and not str(tgt).startswith('GONE') and any(tgt.startswith(x['prefix']) for x in wild):
            problems.append(f'The target {tgt} of wildcard rule {w["source"]} matches a wildcard rule.')
        if tgt and not str(tgt).startswith('GONE') and tgt not in valid:
            problems.append(f'Wildcard rule {w["source"]} redirects to {tgt}, which is not a page that stays or a new page.')
        rows.append({'old': re.sub(r'^https?://[^/]+', '', w['source']), 'action': 'wildcard', 'final': tgt, 'code': 301, 'by': 'Content Prune (Junk folders)',
                     'backlinks': 0, 'impressions': 0, 'open': False, 'reason': '', 'note': '', 'regex': w['regex'],
                     'covers': sum(1 for k in master if k.startswith(w['prefix']))})

    # ---- master URLs that nobody has decided yet (backlinks or impressions, not live, not in the audits)
    for k, m in sorted(master.items()):
        if k in d or covered(k):
            continue
        if m.get('media'):
            continue
        t = seo.get('targets', {}).get(k, '')
        if not t:
            r = row(k, 'redirect', '', 301, 'No decision yet: SEO decides', open=True)
            continue
        if str(t).upper().startswith('GONE'):
            r = row(k, 'gone', '', gone_code(t), 'SEO (Pages to redirect)', reason=seo.get('reasons', {}).get(k, ''))
            r['open'] = not r['reason']
            continue
        end, why = final(t)
        if end is None:
            problems.append(f'{k}: the target {t} cannot be resolved ({why}).')
            continue
        if end != t:
            disc.append({'kind': 'Redirect chain fixed', 'old': k, 'said': f'SEO target: {t}', 'did': f'Points to {end} in one hop',
                         'source': 'SEO (Pages to redirect)'})
        if end not in valid:
            problems.append(f'{k} redirects to {end}, which is not a page that stays or a new page.')
        row(k, 'redirect', end, 301, 'SEO (Pages to redirect)')

    # ---- media files with backlinks: the SEO decides each one
    media_rows = []
    for k, m in sorted(master.items()):
        if not m.get('media') or covered(k):
            continue
        dec = seo.get('media', {}).get(k, {})
        media_rows.append({'old': k, 'backlinks': int(m.get('backlinks', 0)), 'decision': dec.get('decision', ''), 'new': dec.get('new', '')})

    # ---- checks that hold in every pass
    finals_seen = {}
    for r in rows:
        if r['action'] == 'keep':
            finals_seen.setdefault(r['final'], []).append(r['old'])
    for f, olds in finals_seen.items():
        if len(olds) > 1:
            problems.append(f'{len(olds)} pages end at {f}: {", ".join(olds[:4])}.')
    srcs = {r['old'] for r in rows if r['action'] in ('merge', 'redirect')}
    for r in rows:
        if r['action'] in ('merge', 'redirect') and r['final'] and r['final'] in srcs:
            problems.append(f'Redirect chain: {r["old"]} -> {r["final"]} -> another redirect.')
    for nu in new_urls:
        if nu in finals_seen:
            problems.append(f'The new page URL {nu} is already used by a page that stays.')

    counts = {a: sum(1 for r in rows if r['action'] == a) for a in ('keep', 'merge', 'redirect', 'gone', 'wildcard')}
    counts['moved'] = sum(1 for r in rows if r.get('moved'))
    counts['media'] = len(media_rows)
    counts['covered'] = sum(r.get('covers', 0) for r in rows if r['action'] == 'wildcard')
    return {'rows': rows, 'discrepancies': disc, 'problems': problems, 'finals': finals, 'counts': counts, 'media': media_rows}
