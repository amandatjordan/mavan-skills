---
name: prospect-diagnosis
description: Work out a potential client's biggest underlying SEO issue (authority / trust, content, or site architecture) from a crawl and Semrush or Ahrefs exports, with no Search Console. Scores every signal against fixed thresholds and builds a short workbook with the verdict and its evidence. Use for prospect diagnosis, sales calls, "what is this prospect's main problem", or before choosing which audit to sell.
---

# Prospect Diagnosis (Mavan)

One question for a potential client: **which is the biggest underlying issue: authority / trust, content, or site architecture?** The answer is a verdict with the evidence behind it, not a full audit. The existing audits (service gap, information architecture, title and H1, backlinks) are follow-ups for the lens that leads; this skill does not run them.

Work only from uploaded files: a fresh crawl, Semrush or Ahrefs exports, and a few overview figures the person types in. **Never visit or fetch the live site** (the crawl is the site), and use no Search Console, GA4, Composio or DataForSEO. Use no tool, dependency, fallback or extra step beyond those named here without asking the person and explaining why. Every count, share and comparison is done by `scripts/diagnose.py`; never estimate a number by reading. Thresholds and what each signal means are in [references/rules.md](references/rules.md).

`$SKILL` below is this skill's folder (the base directory shown when the skill loads). The script needs Python 3 with pandas and openpyxl. Work in a folder named after the prospect with a `work/` subfolder, and keep a task list with one item per step.

## What you need

Ask for what is missing in **one** message.

| Input | Required? | Notes |
| --- | --- | --- |
| Crawl URL export (Sitebulb or Screaming Frog) | Required | Every status code. URL, status, title, H1, content words; indexability and crawl depth are used when present. **No internal links export is needed.** |
| Ranking keywords for the prospect | Required | Semrush Organic Positions or Ahrefs Organic Keywords |
| Keyword gap, prospect plus 2-4 competitors | Required | Semrush Keyword Gap or Ahrefs Content Gap, all keywords (not only "missing") |
| Authority overview figures | Strongly recommended | For the prospect and each competitor: Authority Score (or DR), referring domains now, and referring domains 12 months ago. From the tool's overview or the "compare domains" chart. Typed into `config.json` |
| Prospect referring domains export | Optional | Semrush Backlink Analytics > Referring Domains (or Ahrefs). Adds the link-growth timing and quality counts |
| Backlink gap export | Optional | Semrush Backlink Gap or Ahrefs Link Intersect. Adds the quality link gap |
| Client facts | Required | Prospect name, domain, competitors, brand terms |

A page-level backlinks export is **not** needed (it is usually over the row cap). If the person sends a screenshot of the overview chart instead of figures, read the values off it, show them in one line and ask the person to confirm or correct them before writing them: values read from a chart are approximate.

## Step 1: Config and preflight

Write `work/config.json`. Brand terms cover the prospect's and competitors' names as people search them (with spaces): those searches are left out of the content signals.

```json
{"client": "Example Spa", "domain": "example-spa.com",
 "competitors": ["rival-one.com", "rival-two.com"],
 "brand_terms": ["example spa", "rival one"],
 "overview": {
  "example-spa.com": {"authority_score": 22, "referring_domains": 6900, "referring_domains_12m_ago": 250},
  "rival-one.com":   {"authority_score": 26, "referring_domains": 2200, "referring_domains_12m_ago": 330}}}
```

Optional keys: `archive_patterns` (extra regexes for this site's listing pages, only after checking examples in the crawl) and `reference_date` (YYYY-MM-DD, the export date, for the 90-day link window; defaults to the newest first-seen date in the referring domains export).

```
python $SKILL/scripts/diagnose.py preflight --config work/config.json --crawl URLS.csv --ranking RANK.csv --gap GAP.csv \
  [--refdomains REFDOMAINS.csv] [--backlink-gap BACKLINK_GAP.csv] --out work
```

Read `work/preflight.md`. On NOT READY, send one message listing each FAIL and exactly what is needed, then stop. WARN lines (no overview figures, no optional export) mean some authority signals are not scored; say so in the reply. If the tool cannot be detected, ask which tool made the file and pass `--tool`. Done when it says READY.

## Step 2: Build

```
python $SKILL/scripts/diagnose.py build --config work/config.json --crawl URLS.csv --ranking RANK.csv --gap GAP.csv \
  [--refdomains REFDOMAINS.csv] [--backlink-gap BACKLINK_GAP.csv] --out "work/PROSPECT Prospect Diagnosis Month YYYY.xlsx"
```

Read the printed column mappings (fix a wrong one with `--map crawl.words="Word Count"`, or a gap domain column with `--map "gapcol.domain.com=Column name"`). Done when it prints "All checks passed" and the verdict.

The crawl must have rendered: the build stops when fewer than 10 pages return 200 or 20% or more of them have no title, no H1 and no words. Ask for a re-crawl; do not diagnose around it.

## Step 3: Check

- Open the Signals tab and confirm each value against its source for 3 signals (one per lens): a crawl count, a gap count, an authority figure.
- Look at 5 URLs counted as archive pages (Architecture tab and A1). If a site's listing pages use a pattern the script does not know, add it to `archive_patterns` and rebuild; if a real page was counted as an archive, say so in the reply.
- Read the buying searches list on the Content tab: brand and competitor searches should not be there. Add brand terms and rebuild if they are.

Say you did these checks.

## Step 4: Reply

Plain language, in this order:

1. **The verdict**: the lead lens (or co-leads) and its severity, in one sentence.
2. **The evidence**: for each lens, the 1-3 signals that scored, with their values from the Signals tab. Name a lens that was not scored or had too little data, and why.
3. **Trust risk**, when U4 scored: unusual link growth is a reason to check Search Console > Manual actions on the prospect's account, never a reason to disavow.
4. **Limits**, one line each: volumes are the tool's estimates (never added together), rankings are a snapshot of tracked keywords, internal links between pages were not analysed, overview figures were typed in (or read from a chart and confirmed).
5. **Next step**: the follow-up audit for the lead lens. Architecture: information architecture audit (and content prune & merge when archive pages lead). Content: service gap audit (med spa and plastic surgery) and the prospect audit's keyword gap groups. Authority: backlink audit. Offer it; do not run it.

Never promise a result. Send the workbook.
