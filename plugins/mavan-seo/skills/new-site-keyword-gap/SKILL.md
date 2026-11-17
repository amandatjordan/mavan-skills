---
name: new-site-keyword-gap
description: Find the service and search terms a brand-new site should target, for a business that has no website yet, from a competitor keyword gap export (Semrush Keyword Gap or Ahrefs Content Gap) plus each competitor's Organic Positions. Removes competitor-branded searches, groups the rest by service and a local group, flags terms several competitors rank for and terms a competitor ranks top 3 for, and builds a workbook. Use for new site keyword research, "business has no website", or a service gap for a site that does not exist yet.
---

# New-site keyword gap (Mavan)

One question for a business with **no website yet**: which non-branded services and searches do competitors rank best for, so the new site can target them? It is a service gap for a site that does not exist, so nothing is compared against an existing site.

Work only from uploaded CSV or XLSX files and what the person types in. **Never visit or fetch a live site**, and use no crawl, Search Console, GA4, Composio or DataForSEO. Use no tool, dependency, fallback or extra step beyond those named here without asking the person and explaining why. Every count, flag and comparison is done by `scripts/gap.py`; never estimate a number by reading. What each flag means is in [references/rules.md](references/rules.md).

`$SKILL` below is this skill's folder (the base directory shown when the skill loads). The script needs Python 3 with pandas and openpyxl. Work in a folder named after the business with a `work/` subfolder, and keep a task list with one item per step.

## What you need

Ask for what is missing in **one** message.

| Input | Required? | Notes |
| --- | --- | --- |
| Keyword gap export, 3-5 competitors | Required | Semrush Keyword Gap or Ahrefs Content Gap, **all keywords** (not only "missing"). The business has no domain, so the SEO uses one competitor as the base domain; every domain column is treated as a competitor |
| Organic Positions export for **each** competitor | Required | Semrush Organic Positions or Ahrefs Organic Keywords. Gives the page that ranks for each keyword |
| The name of **every** competitor | Required | The name people search for each competitor, plus common variants (with spaces). Searches containing these are removed. The domain name is added automatically |
| Business name | Optional | Used only to name the workbook |
| Service terms and cities | Confirmed in Step 1 | Proposed from the exports, never assumed |

## Step 1: Config and preflight

Write `work/config.json`. Preflight does not pass until every domain column in the gap export has at least one competitor name, so ask for the names first.

```json
{"business": "New Spa",
 "competitors": {"rival-one.com": ["rival one"], "rival-two.com": ["rival two spa", "rival two"]},
 "service_terms": ["botox", {"service": "Tummy tuck", "terms": ["abdominoplasty"]}],
 "cities": ["miami", "coral gables"]}
```

Run preflight once with the competitor names and no lists yet. It reports NOT READY for the missing service terms, which is expected; it still writes the candidates file:

```
python $SKILL/scripts/gap.py preflight --config work/config.json --gap GAP.csv \
  --ranking "rival-one.com=RIVAL1.csv" --ranking "rival-two.com=RIVAL2.csv" ... --out work
```

It writes `work/preflight.md` and `work/candidates.md` (common words and phrases in the non-branded keywords, locations after "in" or "near", possible leftover brand words, and the first folder of the URLs competitors rank with). Use candidates only to **propose** two lists, then ask the person to confirm them in one message with any other missing input:

- **Service terms:** one entry per service the new business could offer, with the names people search (`{"service": "Tummy tuck", "terms": ["abdominoplasty"]}`). Keep broad words ("laser", "facial") out unless that service is the broad one. Competitors may overlap on only some services; do not drop a service because only one competitor ranks for it.
- **Leftover brand words:** candidates.md lists words from a competitor's name that still appear in non-branded keywords ("ageless" for "Ageless Remedies"). Ask the SEO which are part of the name people search and add those as extra names; leave service words alone ("medical", "medspa").
- **Cities:** the cities or areas the business will serve. An empty list is allowed when there are none. Keywords with a city, and "near me" searches, go to the Local group instead of a service group.

Read `work/preflight.md`. On NOT READY, send one message listing each FAIL and exactly what is needed, then stop. Read each WARN (an export that looks capped, a brand term that removes too many keywords) and mention it in the reply. If the tool cannot be detected, ask which tool made the file and pass `--tool`. Done when it says READY.

## Step 2: Build

```
python $SKILL/scripts/gap.py build --config work/config.json --gap GAP.csv \
  --ranking "rival-one.com=RIVAL1.csv" ... --out "work/BUSINESS Keyword Gap Month YYYY.xlsx"
```

Read the printed column mappings (fix a wrong one with `--map gap.volume="Vol"`, or a gap domain column with `--map "gapcol.domain.com=Column name"`). Done when it prints "All checks passed".

## Step 3: Check

- Read the **Branded removed** tab: every row should contain a competitor name. If a service word was removed, take it out of that competitor's names and rebuild.
- Read the **Unassigned** tab (sorted by estimated volume) and the common words the build prints and the Summary lists. A product, device or treatment name belongs in `service_terms`; a competitor's short name belongs in its names. Rebuild after each change. A large Unassigned tab means the service list is incomplete.
- Read the **Local** tab: each keyword should carry a confirmed city or "near me". Add a missing city and rebuild.
- Open the Keywords tab and confirm 3 flagged keywords against the raw gap export: positions, the A and B flags, and the best-ranking competitor.
- Look at the Service opportunities tab: the first columns count non-local keywords and the Local columns count that service's local searches, so read both. A service with zero keywords means its term did not match anything, not that there is no demand.

Say you did these checks.

## Step 4: Reply

Plain language, in this order:

1. **The headline**: the 3-5 services with the most keywords flagged A or B, and the competitor that ranks best most often for each.
2. **Evidence**: for each of those services, 2-3 example keywords with the best competitor, its position and its page. Volumes are the tool's estimates and are never added together.
3. **Local**: how many local keywords there are and which cities or "near me" terms carry them.
4. **Pages competitors win with**: what the Competitor pages tab shows (service pages, blog articles, the home page), and that "looks like" is a guess from the URL.
5. **Gaps in the data**: services with no matching keywords, the size of Unassigned, and any warning from preflight.
6. **Limits**, one line each: volumes are the tool's estimates, rankings are a snapshot of tracked keywords, every competitor's own branded searches were removed, and competitors that overlap on only some services appear in those services only.
7. **Next step**: the services to plan pages for first. Offer it; do not build it.

Never promise a result. Send the workbook.
