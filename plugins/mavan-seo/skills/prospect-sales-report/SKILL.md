---
name: prospect-sales-report
description: Build the client-facing prospect report sales goes over with a potential client - Site Health Score summary, one verdict (site architecture, content or authority & trust), each health metric with its findings, and the 3-month roadmap for that track and the chosen tier - as one shareable web page, from a prospect diagnosis. Use for prospect reports, sales reports, pitch decks for a prospect, or "make the report for the sales call".
---

# Prospect Sales Report (Mavan)

One page sales screen-shares or sends after the call. In this order:

1. **Site Health Score**: overall and per metric (Site Architecture, Content, Authority & Trust, Google Maps).
2. **Verdict**: **one** underlying issue.
3. **What we found**: each metric with its score and 2-3 plain-language findings.
4. **Recommended roadmap**: onboarding plus months 1-3 of the verdict's track only, for the prospect's tier.

It reads `diagnosis.json` from the `prospect-diagnosis` skill, the bundled client tracks and task labels, and optional Google Business Profile data. **Never visit the live site.** Every number comes from `diagnosis.json`; the script writes all the wording and picks the verdict, so never write or reword findings or change the verdict by hand. Use no tool, dependency or extra step beyond those named here without asking the person and explaining why.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads). Python 3, standard library only.

## What you need

- **`diagnosis.json`** from `prospect-diagnosis` for this prospect. If there is none, run that skill first (its inputs: crawl, ranking keywords, keyword gap, authority overview figures, service terms).
- **Tier**: Starter, VIP or Signature. Ask with one multiple-choice question if the person has not said. Tasks not in that tier are dropped; hours are never shown.
- **Google Business Profile data** (optional, not defined yet): without it, Google Maps shows as "Checked separately" and is left out of the overall score. When it exists it is a JSON file: `{"score": 0-100, "findings": [{"text": "...", "issue": true}]}`, and it is added to the overall score and gets its own card. The Maps track is never picked automatically.

## Rules the script applies

- **Health score** per metric = 100 minus that lens's issue score from the diagnosis (a lens with 4 of 7 issue points scores 43). Overall = the average of the scored metrics. Good 75+, Needs work 50-74, Poor under 50.
- **Verdict**: the first lens scoring **High** in priority order **Site Architecture, then Content, then Authority & Trust**. When none is High, the highest-scoring lens (priority order breaks ties). When no lens scored any issue, the script stops: ask the person which track to show and pass `--verdict`. Use `--verdict` only when the person asks, and say why in the reply; `--verdict maps` is how sales picks the Google Maps track after the manual GBP check.
- **Why we start here**: when another metric scored lower than the verdict, the verdict card explains why the verdict still comes first (wording per track in `PRIORITY_WHY` in the script). The Maps wording mentions that trust signals are not a major issue only when Authority & Trust scored Low or Medium.
- **Roadmap**: the track for the verdict (Site Architecture, Poor Content, or Authority & Trust) from `references/tracks.csv`. Onboarding first, then months 1-3. Monthly AM/PM, reporting, GBP posts, GMB audit, Text/GHL and front desk go in one "Every month" band. "DO FIRST" shows as "Start here"; "BLOCKED BY" shows as "After: <task>". Task names show as the client labels in `references/task_labels.json`.
- **Copy**: written for a business owner, no signal codes, tool jargon or keyword volumes, no promised results.

## Step 1: Build

```
python $SKILL/scripts/report.py --diagnosis work/diagnosis.json --tier vip [--gbp gbp.json] \
  --out "work/PROSPECT Site Health Report.html"
```

Done when it prints "All checks passed". On "every task has a client label: FAIL", add the listed tasks to `task_labels.json` (title and one plain line) in a pull request; do not ship a page with raw task names.

## Step 2: Look at it

Open the page rendered (a headless browser screenshot, or the published page) and check: the verdict card names the verdict the script printed; the scores add up (overall = average of the scored metrics); the roadmap shows only the verdict's track; nothing overlaps or is cut off. Read every finding once against the diagnosis Signals tab.

## Step 3: Deliver

Publish the HTML file as an artifact (a private page sales can share), or send the file when no artifact tool is available. Reply in a few lines: the verdict and why (the rule the script printed), the overall score, the tier shown, whether Google Maps was included, and anything overridden.

## Updating the tracks

The tracks come from the New Client Tracks Google Sheet. When it changes, update `references/tracks.csv` (columns Track, Task, Month, Starter, VIP, Signature, Notes; "-" or blank = not in that tier; Onboarding rows apply to every tier), add any new task to `task_labels.json`, raise the plugin version and open a pull request.
