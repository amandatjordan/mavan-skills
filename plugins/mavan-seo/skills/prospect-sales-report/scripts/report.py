"""Prospect sales report: one client-facing web page from a prospect diagnosis.

Reads diagnosis.json (from the prospect-diagnosis skill), the bundled client tracks and task labels, and an
optional Google Business Profile file, and writes a self-contained HTML page:

  1. Site Health Score summary (overall and per metric)
  2. Verdict: one underlying issue, by priority Architecture > Content > Authority
  3. Each health score metric with its main findings
  4. The recommended roadmap for the verdict's track, for one tier

Every number comes from diagnosis.json. Nothing is fetched from the live site.
"""
import argparse
import csv
import html
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, '..', 'references')

PRIORITY = ['Architecture', 'Content', 'Authority']           # verdict order (decided with Amanda)
LENS_NAME = {'Architecture': 'Site Architecture', 'Content': 'Content', 'Authority': 'Authority & Trust',
             'Maps': 'Google Maps'}
TRACK_FOR = {'Architecture': 'Site Architecture', 'Content': 'Poor Content', 'Authority': 'Authority & Trust',
             'Maps': 'Google Maps'}
TIER_COL = {'starter': 'Starter', 'vip': 'VIP', 'signature': 'Signature'}
TIER_NAME = {'starter': 'Starter', 'vip': 'VIP', 'signature': 'Signature'}
MONTHS = ['Onboarding', 'Month 1', 'Month 2', 'Month 3']
RECURRING = {'monthly am/pm', 'monthly reporting', 'monthly gbp posts', 'monthly gmb audit', 'text/ghl', 'front desk'}
GOOD, OK = 75, 50

LENS_ABOUT = {
    'Architecture': 'How your pages are organized, so Google and patients can find your services.',
    'Content': 'Whether your pages answer the searches patients make, compared with competitors.',
    'Authority': 'How much other reputable sites vouch for your practice through links.',
    'Maps': 'How your Google Business Profile shows up in local map results.',
}
# Shown only when another metric scored lower than the verdict: why it still comes first.
PRIORITY_WHY = {
    'Architecture': 'Site architecture affects which of your pages Google considers for search results. Fixing it first '
                    'addresses why your pages are not ranking, and gives the content and authority work a solid '
                    'foundation to build on.',
    'Content': 'Content affects both your regular Google rankings and your Google Maps rankings. Your site structure is '
               'sound enough for better pages to be found, so improving and adding service pages opens up visibility '
               'for the searches patients make. Links and reviews also point back to your content, so it comes before '
               'authority work.',
    'Maps': 'Your Google Business Profile drives a large share of the visibility and calls a local practice gets. '
            'It depends less on trust signals such as links than regular search results do{trust}, so your profile can '
            'be improved without waiting on that work.',
}
MAPS_TRUST_OK = ', and we found those signals are not a major issue for you'

VERDICT_WHY = {
    'Architecture': 'The way your site is organized is the underlying issue holding it back. Content and links build '
                    'on the structure, so fixing it is where the work starts.',
    'Content': 'Your site structure is workable, but competitors cover the searches patients make far more fully. '
               'Better and missing service pages are where the work starts.',
    'Authority': 'Your structure and content are workable; competitors are ahead on how many reputable sites vouch '
                 'for them. Earning those signals is where the work starts.',
    'Maps': 'Your Google Business Profile is the biggest opportunity we found for being seen by local patients, so '
            'this is where the work starts.',
}


def pct(x):
    return f'{x:.0%}'


def n(x):
    return f'{x:,.0f}' if isinstance(x, (int, float)) else str(x)


# ------------------------------------------------------------------ findings (plain language)

def finding(sig):
    """(is_issue, sentence) for a scored signal, or None when there is nothing worth saying."""
    d, sid, issue = sig.get('data') or {}, sig['id'], bool(sig['points'])
    try:
        if sid == 'A1':
            return (True, f'{n(d["archive"])} of your {n(d["indexable"])} indexable pages ({pct(d["share"])}) are '
                          'automatically generated listing pages (tags, categories, date archives), so your service '
                          'pages are a small part of what Google sees.') if issue else \
                   (False, f'Listing pages make up only {pct(d["share"])} of your indexable pages.')
        if sid == 'A2':
            return (True, f'{n(d["repeated"])} pages share the same title or heading with several others, which makes '
                          'them hard for Google to tell apart.') if issue else \
                   (False, 'Page titles and headings are mostly unique.')
        if sid == 'A3':
            return (True, f'{pct(d["share"])} of your regular pages ({n(d["no_keywords"])} of {n(d["pages"])}) do not '
                          'appear for any search we track.') if issue else \
                   (False, 'Most of your regular pages appear for at least one tracked search.')
        if sid == 'A4':
            return (True, f'{n(d["redirects"])} of the {n(d["crawled"])} addresses linked across your site redirect '
                          'somewhere else, adding an extra step for visitors and Google.') if issue else \
                   (False, 'Few links on your site point at redirected addresses.')
        if sid == 'A5':
            return (True, f'{pct(d["share"])} of your pages are more than {d["depth"]} clicks from the home page.') if issue \
                else (False, f'Pages are easy to reach: only {pct(d["share"])} are more than {d["depth"]} clicks deep.')
        if sid == 'A6':
            return (True, f'{n(d["not_live"])} pages that still appear in Google no longer load properly.') if issue else \
                   (False, 'Nearly every page that appears in Google loads properly.')
        if sid == 'C1':
            return (True, f'{d["competitor"]} appears for {d["ratio"]:.1f} times as many of the searches we compared '
                          f'({n(d["competitor_keywords"])} vs your {n(d["prospect_keywords"])}).') if issue else \
                   (False, 'You appear for a similar number of the compared searches as your competitors.')
        if sid == 'C2':
            what = 'non-branded searches for your services' if d.get('by_service') else 'non-branded booking searches'
            return (True, f'On {what}, you rank on page one {n(d["prospect_top10"])} times; the typical competitor does '
                          f'{n(d["median_competitor_top10"])}.') if issue else \
                   (False, f'On {what}, you hold your own on page one ({n(d["prospect_top10"])} vs '
                           f'{n(d["median_competitor_top10"])} for the typical competitor).')
        if sid == 'C3':
            return (True, f'{pct(d["share"])} of the searches competitors win and you miss are people ready to book or '
                          'compare providers.') if issue else None
        if sid == 'C4':
            return (True, f'{pct(d["share"])} of your regular pages have under {d["words"]} words of content.') if issue \
                else (False, 'Most pages have a reasonable amount of written content.')
        if sid == 'U1':
            return (True, f'Your authority score is {d["gap"]:g} points below the typical competitor '
                          f'({d["prospect"]:g} vs {d["median_competitor"]:g}).') if issue else \
                   (False, f'Your authority score is in line with competitors ({d["prospect"]:g} vs '
                           f'{d["median_competitor"]:g}).')
        if sid == 'U2':
            return (True, 'Fewer than half as many sites link to you as to the typical competitor.') if issue else \
                   (False, 'As many sites link to you as to your competitors, or more.')
        if sid == 'U3':
            return (True, f'{n(d["gap_quality"])} reputable sites link to your competitors but not to you; you have '
                          f'{n(d["own_quality"])} links from sites of that standing.') if issue else None
        if sid == 'U4':
            if not issue:
                return None
            extra = f' ({pct(d["recent_share"])} of linking sites appeared in the last {d["days"]} days)' \
                if d.get('recent_share') is not None else ''
            return (True, f'Links to your site grew unusually fast recently{extra}. This needs a check for spam links.')
    except (KeyError, TypeError):
        return None
    return None


def lens_findings(signals, lens, limit=3):
    rows = [s for s in signals if s['lens'] == lens and s['points'] is not None]
    rows.sort(key=lambda s: (-(s['points'] or 0), s['id']))
    issues = [f for f in (finding(s) for s in rows if s['points']) if f]
    good = [f for f in (finding(s) for s in rows if not s['points']) if f]
    out = issues[:limit]
    if len(out) < 2:
        out += good[:2 - len(out)] if issues else good[:2]
    return out


# ------------------------------------------------------------------ verdict and scores

def health(lens):
    return None if lens.get('share') is None else round(100 * (1 - lens['share']))


def band(score):
    if score is None:
        return ('Not scored', 'muted')
    return ('Good', 'good') if score >= GOOD else (('Needs work', 'warn') if score >= OK else ('Poor', 'bad'))


def pick_verdict(lenses, override=None):
    by = {v['lens']: v for v in lenses}
    if override:
        return override, 'override'
    for lens in PRIORITY:
        if by.get(lens, {}).get('severity') == 'High':
            return lens, 'first High lens in priority order'
    scored = [by[x] for x in PRIORITY if x in by and by[x].get('share')]
    if not scored:
        return None, 'no lens scored an issue'
    top = max(v['share'] for v in scored)
    return next(v['lens'] for v in scored if v['share'] == top), 'highest score (no lens scored High)'


# ------------------------------------------------------------------ roadmap

def load_tracks():
    with open(os.path.join(REF, 'tracks.csv'), newline='') as f:
        return list(csv.DictReader(f))


def load_labels():
    with open(os.path.join(REF, 'task_labels.json')) as f:
        return json.load(f)


def label(task, labels):
    k = re.sub(r'\s+', ' ', task.strip().lower())
    return labels.get(k, [task.strip(), ''])


def in_tier(row, tier):
    if row['Track'] == 'Onboarding':
        return True
    v = row[TIER_COL[tier]].strip()
    return v not in ('', '-')


def roadmap(track, tier, labels):
    rows = [r for r in load_tracks() if r['Track'] in ('Onboarding', track) and in_tier(r, tier)]
    if not any(r['Track'] == track for r in rows):
        raise SystemExit(f'No tasks for track "{track}" in references/tracks.csv.')
    months = {m: [] for m in MONTHS}
    recurring, missing = [], set()
    for r in rows:
        key = re.sub(r'\s+', ' ', r['Task'].strip().lower())
        if key not in labels:
            missing.add(r['Task'].strip())
        title, line = label(r['Task'], labels)
        m = 'Onboarding' if r['Track'] == 'Onboarding' else r['Month'].strip()
        if m not in months:
            continue
        if key in RECURRING and r['Track'] != 'Onboarding':
            if title not in [x[0] for x in recurring]:
                recurring.append((title, line))
            continue
        note = r['Notes']
        badge = ''
        if 'DO FIRST' in note.upper():
            badge = 'Start here'
        b = re.search(r'BLOCKED BY:\s*([^.(]+)', note, re.I)
        if b:
            badge = f'After: {label(b.group(1).strip(), labels)[0]}'
        if title in [x['title'] for x in months[m]]:
            continue
        months[m].append({'title': title, 'line': line, 'badge': badge})
    return months, recurring, sorted(missing)


# ------------------------------------------------------------------ HTML

CSS = """
:root{--ink:#1d2433;--muted:#667085;--line:#e4e7ec;--bg:#f7f8fa;--card:#fff;--accent:#2d5be3;
--good:#1f8a5b;--good-bg:#e7f6ee;--warn:#b26b00;--warn-bg:#fff4e0;--bad:#c2410c;--bad-bg:#fdece4;}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:var(--ink);background:var(--bg);line-height:1.5}
.page{max-width:980px;margin:0 auto;padding:40px 28px 56px}
header{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin-bottom:28px}
header h1{font-size:28px;margin:0 0 4px;letter-spacing:-.01em}header .sub{color:var(--muted);font-size:14px}
header .prep{color:var(--muted);font-size:13px;text-align:right}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:36px 0 12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}
.summary{display:grid;grid-template-columns:220px 1fr;gap:22px;align-items:center}
.overall{text-align:center}.overall .lbl{font-size:13px;color:var(--muted);margin-top:6px}
.scores{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.mini{border:1px solid var(--line);border-radius:12px;padding:14px;text-align:center}
.mini .name{font-size:13px;font-weight:600;margin-top:6px}.mini .state{font-size:12px;margin-top:2px}
.pill{display:inline-block;font-size:12px;font-weight:600;padding:2px 10px;border-radius:999px}
.good{color:var(--good)}.warn{color:var(--warn)}.bad{color:var(--bad)}.muted{color:var(--muted)}
.pill.good{background:var(--good-bg)}.pill.warn{background:var(--warn-bg)}.pill.bad{background:var(--bad-bg)}
.pill.muted{background:#eef0f3}
.verdict{border-left:6px solid var(--accent);display:grid;grid-template-columns:1fr auto;gap:18px;align-items:center}
.verdict .kicker{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--accent);font-weight:700}
.verdict h3{font-size:24px;margin:4px 0 8px}.why{margin-top:14px;background:#f2f5ff;border-radius:10px;padding:10px 14px}.why b{font-size:13px;color:var(--accent)}.why p{margin:4px 0 0;font-size:14px}.verdict p{margin:0;color:#344054}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.metric h4{margin:0;font-size:17px;display:flex;justify-content:space-between;align-items:center;gap:8px}
.metric .about{color:var(--muted);font-size:13px;margin:4px 0 12px}
.metric ul{margin:0;padding-left:0;list-style:none}.metric li{position:relative;padding-left:22px;margin:8px 0;font-size:14px}
.metric li:before{content:"";position:absolute;left:4px;top:8px;width:9px;height:9px;border-radius:50%}
.metric li.issue:before{background:var(--bad)}.metric li.ok:before{background:var(--good)}
.metric.lead{border:2px solid var(--accent)}
.svc{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}
.svc th{text-align:left;color:var(--muted);font-weight:600;border-bottom:1px solid var(--line);padding:6px 4px}
.svc td{border-bottom:1px solid var(--line);padding:6px 4px}.svc td.num{text-align:right}.svc th.num{text-align:right}
.road-intro{margin:0 0 14px;color:#344054}
.road{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;position:relative}
.col{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;position:relative}
.col .head{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.col .dot{width:26px;height:26px;border-radius:50%;background:var(--accent);color:#fff;font-size:12px;font-weight:700;
display:flex;align-items:center;justify-content:center}.col.onb .dot{background:#98a2b3}
.col .head b{font-size:14px}.col .head span{font-size:12px;color:var(--muted)}
.task{border:1px solid var(--line);border-radius:10px;padding:9px 10px;margin-bottom:8px;background:#fcfcfd}
.task b{font-size:13px;display:block}.task.compact{padding:6px 10px;margin-bottom:6px}.task small{display:block;color:var(--muted);font-size:12px;margin-top:2px}
.badge{display:inline-block;font-size:11px;font-weight:600;color:var(--accent);background:#e9efff;border-radius:6px;
padding:1px 7px;margin-top:6px}.badge.first{color:#fff;background:var(--accent)}
.col:not(:last-child):after{content:"";position:absolute;right:-12px;top:26px;width:12px;height:2px;background:var(--accent)}
.recurring{margin-top:12px;background:#eef2ff;border:1px dashed #b7c4f5;border-radius:12px;padding:12px 14px}
.recurring b{font-size:13px}.recurring .items{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.recurring .items span{background:#fff;border:1px solid #d5ddfb;border-radius:999px;padding:3px 10px;font-size:12px}
p.note{color:var(--muted);font-size:12px;margin:8px 2px 0}
footer{margin-top:36px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
@media (max-width:820px){.summary,.metrics,.verdict{grid-template-columns:1fr}.scores,.road{grid-template-columns:1fr 1fr}
.col:after{display:none}}
@media print{body{background:#fff}.page{padding:0}.card,.col{break-inside:avoid}h2{break-after:avoid}}
"""


def ring(score, size=150, stroke=14, font=34):
    cls = band(score)[1]
    color = {'good': '#1f8a5b', 'warn': '#d38a0b', 'bad': '#d9541e', 'muted': '#c4c9d2'}[cls]
    r = (size - stroke) / 2
    circ = 2 * 3.14159265 * r
    frac = 0 if score is None else max(0, min(100, score)) / 100
    label_txt = '—' if score is None else str(score)
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" '
            f'aria-label="Score {label_txt} out of 100">'
            f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="#eef0f3" stroke-width="{stroke}"/>'
            f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-linecap="round" stroke-dasharray="{circ*frac:.1f} {circ:.1f}" '
            f'transform="rotate(-90 {size/2} {size/2})"/>'
            f'<text x="50%" y="50%" text-anchor="middle" dominant-baseline="central" font-size="{font}" '
            f'font-weight="700" fill="#1d2433">{label_txt}</text></svg>')


def esc(s):
    return html.escape(str(s))


def priority_note(verdict, scores, lenses):
    """Scored metrics with a lower health score than the verdict (empty = no explanation needed)."""
    mine = scores.get(verdict)
    if mine is None:
        return []
    return [k for k in PRIORITY + ['Maps'] if k != verdict and scores.get(k) is not None and scores[k] < mine]


def priority_text(verdict, lenses):
    text = PRIORITY_WHY.get(verdict, '')
    if verdict == 'Maps':
        auth = next((v for v in lenses.values() if v['lens'] == 'Authority'), None)
        ok = auth is not None and auth.get('severity') in ('Low', 'Medium')
        text = text.format(trust=MAPS_TRUST_OK if ok else '')
    return text


def render(d, verdict, tier, months, recurring, maps, prepared_by, report_date):
    lenses = {v['lens']: v for v in d['lenses']}
    scores = {k: health(lenses[k]) if k in lenses else None for k in PRIORITY}
    scores['Maps'] = maps.get('score') if maps else None
    scored = [s for s in scores.values() if s is not None]
    overall = round(sum(scored) / len(scored)) if scored else None
    ob, oc = band(overall)

    minis = ''
    for k in PRIORITY + ['Maps']:
        name = LENS_NAME.get(k, 'Google Maps')
        state = band(scores[k]) if not (k == 'Maps' and scores[k] is None) else ('Checked separately', 'muted')
        minis += (f'<div class="mini">{ring(scores[k], 84, 9, 20)}<div class="name">{esc(name)}</div>'
                  f'<div class="state {state[1]}">{esc(state[0])}</div></div>')

    metric_cards = ''
    for k in PRIORITY:
        if k not in lenses:
            continue
        s = scores[k]
        b = band(s)
        items = lens_findings(d['signals'], k)
        lis = ''.join(f'<li class="{"issue" if i else "ok"}">{esc(t)}</li>' for i, t in items) or \
            '<li class="ok">Not enough data to score this area.</li>'
        extra = ''
        if k == 'Content':
            svc = [x for x in d.get('services', []) if x.get('lost')][:4]
            if svc:
                extra = ('<table class="svc"><tr><th>Service</th><th class="num">Your page-one rankings</th>'
                         '<th class="num">Top competitor\'s</th><th>Top competitor</th></tr>' +
                         ''.join(f'<tr><td>{esc(x["service"])}</td><td class="num">{n(x["prospect_top10"])}</td>'
                                 f'<td class="num">{n(x["competitor_top10"])}</td><td>{esc(x["top_competitor"])}</td></tr>'
                                 for x in svc) + '</table>')
        metric_cards += (f'<div class="card metric{" lead" if k == verdict else ""}"><h4>{esc(LENS_NAME[k])}'
                         f'<span class="pill {b[1]}">{"" if s is None else str(s) + " · "}{esc(b[0])}</span></h4>'
                         f'<div class="about">{esc(LENS_ABOUT[k])}</div><ul>{lis}</ul>{extra}</div>')
    if maps and maps.get('findings'):
        mb = band(maps.get('score'))
        lis = ''.join(f'<li class="{"issue" if f.get("issue") else "ok"}">{esc(f["text"])}</li>' for f in maps['findings'])
        metric_cards += (f'<div class="card metric"><h4>Google Maps<span class="pill {mb[1]}">'
                         f'{"" if maps.get("score") is None else str(maps["score"]) + " · "}{esc(mb[0])}</span></h4>'
                         f'<div class="about">{esc(LENS_ABOUT["Maps"])}</div><ul>{lis}</ul></div>')
    else:
        metric_cards += ('<div class="card metric"><h4>Google Maps<span class="pill muted">Checked separately</span></h4>'
                         f'<div class="about">{esc(LENS_ABOUT["Maps"])}</div><ul><li class="ok">Your strategist reviews '
                         'your Google Business Profile with you on the call.</li></ul></div>')

    cols = ''
    for i, m in enumerate(MONTHS):
        compact = m == 'Onboarding'
        tasks = ''.join(
            f'<div class="task{" compact" if compact else ""}" title="{esc(t["line"])}"><b>{esc(t["title"])}</b>' +
            (f'<small>{esc(t["line"])}</small>' if t['line'] and not compact else '') +
            (f'<span class="badge{" first" if t["badge"] == "Start here" else ""}">{esc(t["badge"])}</span>'
             if t['badge'] else '') + '</div>' for t in months[m])
        sub = 'Setup' if m == 'Onboarding' else 'Focus'
        cols += (f'<div class="col{" onb" if m == "Onboarding" else ""}"><div class="head"><div class="dot">'
                 f'{"0" if m == "Onboarding" else i}</div><div><b>{esc(m)}</b><br><span>{sub}</span></div></div>{tasks}</div>')
    rec = ''
    if recurring:
        rec = ('<div class="recurring"><b>Every month</b><div class="items">' +
               ''.join(f'<span title="{esc(l)}">{esc(t)}</span>' for t, l in recurring) + '</div></div>')

    track = TRACK_FOR[verdict]
    why_box = ''
    lower = priority_note(verdict, scores, lenses)
    if lower:
        names = ' and '.join(f'{LENS_NAME[k]} ({scores[k]})' for k in lower)
        why_box = (f'<div class="why"><b>Why we start here</b><p>{esc(LENS_NAME[verdict])} scores {scores[verdict]}, '
                   f'higher than {esc(names)}, but it comes first. {esc(priority_text(verdict, lenses))}</p></div>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(d.get('client') or d['domain'])}: Site Health Report</title><style>{CSS}</style></head>
<body><div class="page">
<header><div><h1>Site Health Report</h1><div class="sub">{esc(d.get('client') or '')} · {esc(d['domain'])}</div></div>
<div class="prep">Prepared by {esc(prepared_by)}<br>{esc(report_date)}</div></header>

<h2>Site health score</h2>
<div class="card summary"><div class="overall">{ring(overall)}<div class="lbl">Overall site health</div>
<span class="pill {oc}">{esc(ob)}</span></div><div class="scores">{minis}</div></div>
<p class="note">Each score is out of 100: 100 means none of our checks found an issue in that area. Good is 75 and
above, Needs work 50 to 74, Poor below 50.</p>

<h2>Verdict</h2>
<div class="card verdict"><div><div class="kicker">Main underlying issue</div><h3>{esc(LENS_NAME[verdict])}</h3>
<p>{esc(VERDICT_WHY[verdict])}</p>{why_box}</div>{ring(scores[verdict], 110, 11, 26)}</div>

<h2>What we found</h2>
<div class="metrics">{metric_cards}</div>

<h2>Recommended roadmap · {esc(track)} track</h2>
<p class="road-intro">The first three months for your {esc(TIER_NAME[tier])} plan, built around fixing
{esc(LENS_NAME[verdict].lower())} first.</p>
<div class="road">{cols}</div>{rec}

<footer>Based on a crawl of {esc(d['domain'])} and keyword and link data from {esc(', '.join(d.get('tool') or ['the keyword tool']))},
compared with {esc(', '.join(d.get('competitors', [])))}. Rankings are a snapshot of tracked searches; search figures are
the tool's estimates. Scores show where the site stands today, not a forecast of results.</footer>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--diagnosis', required=True, help='diagnosis.json from the prospect-diagnosis skill')
    ap.add_argument('--tier', required=True, choices=sorted(TIER_COL))
    ap.add_argument('--gbp', help='optional Google Business Profile JSON: {"score": 0-100, "findings": [{"text", "issue"}]}')
    ap.add_argument('--verdict', choices=['architecture', 'content', 'authority', 'maps'],
                    help='override the verdict (only when the person says so, e.g. maps after the manual GBP check)')
    ap.add_argument('--prepared-by', default='Mavan')
    ap.add_argument('--date', default=date.today().strftime('%B %-d, %Y'))
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    d = json.load(open(a.diagnosis))
    maps = json.load(open(a.gbp)) if a.gbp else None
    override = a.verdict.capitalize() if a.verdict else None
    verdict, why = pick_verdict(d['lenses'], override)
    if verdict is None:
        print('STOP: no lens scored an issue, so there is no verdict. Ask the person which track to show and pass --verdict.')
        sys.exit(2)
    labels = load_labels()
    months, recurring, missing = roadmap(TRACK_FOR[verdict], a.tier, labels)
    page = render(d, verdict, a.tier, months, recurring, maps, a.prepared_by, a.date)

    checks = []

    def check(name, ok, detail=''):
        checks.append(ok)
        print(f'{"PASS" if ok else "FAIL"} {name}' + (f': {detail}' if detail else ''))

    check('verdict chosen', True, f'{LENS_NAME[verdict]} ({why})')
    check('roadmap has tasks in every month', all(months[m] for m in MONTHS),
          ', '.join(f'{m}: {len(months[m])}' for m in MONTHS))
    check('every task has a client label', not missing, ', '.join(missing) or 'all labelled')
    banned = re.compile(r'\b(guarantee|will rank|will increase|you can expect|#1 ranking)\b', re.I)
    check('no promised results in the page', not banned.search(page))
    check('no internal signal codes in the page', not re.search(r'>\s*[ACU][1-6]\b', page))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, 'w').write(page)
    check('page written', os.path.exists(a.out), a.out)
    if not all(checks):
        sys.exit(1)
    print('All checks passed')


if __name__ == '__main__':
    main()
