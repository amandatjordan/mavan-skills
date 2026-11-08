---
name: client-diagnosis
description: Work out an existing client's biggest underlying SEO issue (authority / trust, content, or site architecture) from a crawl, Semrush or Ahrefs exports and at least 6 months of Search Console data (a year gives two 6-month periods; less is split into two equal halves). Lists the keywords whose clicks fell, scores every signal against fixed thresholds and builds a workbook with the verdict and its evidence. Use for client diagnosis, quarterly reviews, "what is this client's main problem", or before choosing which audit to run.
---

# Client Diagnosis (Mavan)

One question for an existing client: **which is the biggest underlying issue: authority / trust, content, or site architecture?** It is the prospect diagnosis plus Search Console, so real clicks and impressions strengthen the keyword-tool estimates, and it adds a **period-over-period comparison** (6 months against the 6 before when there is a year of data, otherwise two equal halves of whatever there is) with the keywords whose clicks fell. The answer is a verdict with the evidence behind it, not a full audit. The existing audits (service gap, information architecture, title and H1, backlinks) are follow-ups for the lens that leads; this skill does not run them. For page-level triage of a traffic drop use `site-diagnosis`; this skill does not replace it.

Work only from uploaded files: a fresh crawl, Semrush or Ahrefs exports, the Search Console download, and a few overview figures the person types in. **Never visit or fetch the live site** (the crawl is the site). **Never use Composio or a connector for Search Console** or for any other source here; the person attaches the download. Use no GA4 or DataForSEO. Use no tool, dependency, fallback or extra step beyond those named here without asking the person and explaining why. Every count, share and comparison is done by `scripts/diagnose.py`; never estimate a number by reading. Thresholds and what each signal means are in [references/rules.md](references/rules.md).

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
| Search Console export | Required | Mavan's Search Console sheet downloaded as .xlsx or .csv (tab "Claude Use This" when it has tabs): one row per **Date**, Query and Page with Clicks and Impressions (Position is used when present). **At least 6 months, a year is best**, ending on the newest date. If the person says the client has less than 6 months, use what they have: the preflight warns and the script splits it into two equal halves (14 days is the minimum). A sheet or add-on that caps rows (often at 25,000) can cut it short: the preflight checks, see "Capped exports" |
| Manual actions | Required | Whether Search Console > Security & Manual actions shows a manual action: `yes`, `no`, or `unknown`. The person checks it; never guess |
| Client facts | Required | Client name, domain, brand terms (whole words; confirm, never guess), and the client's current plan level for the report. Competitors come from the keyword gap export's domain columns; list them in config only to drop or replace one |

A page-level backlinks export is **not** needed (it is usually over the row cap). Brand terms are matched as whole words, so "balance" matches "balance spa" and "hormone balance" but not "balanced". Add the client's name as people search it, the domain root, and any short form. Competitor names may be added too: those searches are left out of the non-brand figures.

If the person sends a screenshot of the overview chart instead of figures, read the values off it, show them in one line and ask the person to confirm or correct them before writing them: values read from a chart are approximate.

## Step 1: Config and preflight

Write `work/config.json` (`manual_action` is `yes`, `no`, or left out when unknown). Leave out `competitors`: the script takes them from the keyword gap export's domain columns and the preflight lists them. Add a `competitors` list only to drop or replace one (a competitor in a different specialty skews the content scores). Brand terms cover the prospect's and competitors' names as people search them (with spaces): those searches are left out of the content signals.

```json
{"client": "Example Spa", "domain": "example-spa.com",
 "brand_terms": ["example spa", "rival one"], "manual_action": "no",
 "service_terms": ["botox", {"service": "Tummy tuck", "terms": ["abdominoplasty"]}],
 "overview": {
  "example-spa.com": {"authority_score": 22, "referring_domains": 6900, "referring_domains_12m_ago": 250},
  "rival-one.com":   {"authority_score": 26, "referring_domains": 2200, "referring_domains_12m_ago": 330}}}
```

**Service terms** drive the non-branded service ranking signal (C2) and the per-service table. Propose them from the crawl: the H1s and titles of the prospect's live service pages (not hubs, blogs or galleries), one entry per service, with the names people search ("abdominoplasty" under Tummy tuck). Ask the person to confirm the list in the same message as any other missing input. A service is a string or `{"service": name, "terms": [synonyms]}`; keep broad words ("laser", "facial") out unless that service is the broad one. Without the list, C2 falls back to non-branded buying searches and there is no per-service table; say so in the reply.

Optional keys: `archive_patterns` (extra regexes for this site's listing pages, only after checking examples in the crawl) and `reference_date` (YYYY-MM-DD, the export date, for the 90-day link window; defaults to the newest first-seen date in the referring domains export).

```
python $SKILL/scripts/diagnose.py preflight --config work/config.json --crawl URLS.csv --ranking RANK.csv --gap GAP.csv \
  --gsc GSC.csv [--gsc-tab NAME] [--refdomains REFDOMAINS.csv] [--backlink-gap BACKLINK_GAP.csv] --out work
```

Read `work/preflight.md`. On NOT READY, send one message listing each FAIL and exactly what is needed, then stop. WARN lines (no overview figures, no optional export) mean some authority signals are not scored; say so in the reply. If the tool cannot be detected, ask which tool made the file and pass `--tool`. Done when it says READY.

## Step 2: Build

```
python $SKILL/scripts/diagnose.py build --config work/config.json --crawl URLS.csv --ranking RANK.csv --gap GAP.csv --gsc GSC.csv \
  [--click-floor N] [--impr-floor N] [--refdomains REFDOMAINS.csv] [--backlink-gap BACKLINK_GAP.csv] --out "work/PROSPECT Prospect Diagnosis Month YYYY.xlsx"
```

It also writes `diagnosis.json` next to the workbook (lens scores, every signal with its numbers, the service table, `report_type: client`): the `prospect-sales-report` skill builds the client-facing report from it (it drops onboarding for a client).

**Periods.** With a year or more of data, period B is the latest 6 months ending on the newest date in the file and period A is the 6 months before it. With less, the file is split into two equal halves (A earlier, B later); the Read Me and the report footer say so. With under 6 months the preflight warns and trends are rougher: say that in the reply. Say both date ranges in the reply. **Floors.** `--click-floor` (default 3) is the clicks a keyword needs in either period to be judged by clicks only; `--impr-floor` (default 50) is the impressions a keyword needs in period A to be judged by impressions when its clicks are too low. Show the person the defaults and the counts they give, and confirm them or change them.

Read the printed column mappings (fix a wrong one with `--map crawl.words="Word Count"`, or a gap domain column with `--map "gapcol.domain.com=Column name"`). Done when it prints "All checks passed" and the verdict.

The crawl must have rendered: the build stops when fewer than 10 pages return 200 or 20% or more of them have no title, no H1 and no words. Ask for a re-crawl; do not diagnose around it.

## Step 3: Check

- Open the Signals tab and confirm each value against its source for 3 signals (one per lens): a crawl count, a gap count, an authority figure. Confirm the Search Console tab's clicks for period A plus period B equal the file's clicks inside the two periods.
- Look at 5 URLs counted as archive pages (Architecture tab and A1). If a site's listing pages use a pattern the script does not know, add it to `archive_patterns` and rebuild; if a real page was counted as an archive, say so in the reply.
- Read the buying searches list on the Content tab: brand and competitor searches should not be there. Add brand terms and rebuild if they are.
- Read the non-branded service rankings table: each service's keywords belong to it. A service that collects another's keywords means a synonym is too broad; fix `service_terms` and rebuild.

- Open Keyword Drops: the top 5 keywords' clicks in each period are right, and no brand search is in the list. A brand search there means a brand term is missing: add it and rebuild.

Say you did these checks.

## Step 4: Reply

Plain language, in this order:

1. **The verdict**: the lead lens (or co-leads) and its severity, in one sentence. Then the traffic change in one line: non-brand clicks in period B vs period A (with both date ranges), from the Search Console tab, and the 5 keywords that lost the most clicks (from Keyword Drops), saying which basis was used.
2. **The evidence**: for each lens, the 1-3 signals that scored, with their values from the Signals tab. Name a lens that was not scored or had too little data, and why.
3. **Non-branded service rankings**: the 3-5 services with the most keywords where a competitor is top 10 and the prospect is not top 20, with the top competitor and the prospect's top-10 count for each (from the Content tab). Services with no tracked keywords are not weak services: say they had no data.
4. **Trust risk**, when U4 scored: unusual link growth is a reason to check Search Console > Manual actions on the prospect's account, never a reason to disavow.
5. **Limits**, one line each: Search Console figures are real clicks and impressions but keyword tool volumes are estimates (never added together, never added to Search Console figures), small click counts make single keywords noisy, impressions are or are not comparable (and which signals that left unscored), rankings are a snapshot of tracked keywords, internal links between pages were not analysed, overview figures were typed in (or read from a chart and confirmed).
6. **Report**: offer the client report (`prospect-sales-report`, with the client's current plan level). The roadmap starts at month 1.
7. **Next step**: the follow-up audit for the lead lens. Architecture: information architecture audit (and content prune & merge when archive pages lead). Content: service gap audit (med spa and plastic surgery) and the prospect audit's keyword gap groups. Authority: backlink audit. Offer it; do not run it.

Never promise a result. Send the workbook.

## Capped exports

Sheet add-ons and exports often stop at a fixed row count (25,000 is common) and sort by clicks. The cap then keeps every row that had a click and drops the zero-click rows, which hold most of the impressions, for the latest dates. The result: **clicks are complete, impressions are not.** The preflight compares the share of zero-click rows in the two periods. When they differ a lot, it says so, every signal that needs impressions (A7, A8, A9, C6, and C5 when clicks are too low) shows **Not scored**, the keyword drops use clicks only, and the report leaves those findings out. Never read a falling impression count in a capped export as lost visibility. If the person wants the impression signals, ask for an export that is not capped (for example one export per quarter, joined before attaching) and rebuild.
