---
name: backlink-audit
description: Run Mavan's backlink audit for a client site from Ahrefs or Semrush exports (backlinks, link gap, broken backlinks, and Semrush Backlink Audit), and build the workbook with a competitor rollup, a disavow review list and recommendations. Use for backlink audits, link gap or link intersect analysis, broken backlinks, toxic links or disavow questions.
---

# Backlink Audit (Mavan SOP)

The Notion SOP is the **source of truth** for scope, the disavow rule, exports and review steps: [Backlink Gap](https://app.notion.com/p/Backlink-Gap-40418945155e80b8b51df8114ffd2d16). This skill is the execution layer for its Step 4. When the SOP and this skill disagree, the SOP wins; say so in the final report.

The deliverable is one workbook with three tabs: **Competitor Rollup**, **Disavow Review** (sketchy links for a person to look at) and **Recommendations** (broken backlinks to fix, and link opportunities from competitors).

**Disavow rule.** Nothing is marked for disavow unless Google Search Console shows a manual action for *Unnatural links to your site*. Ahrefs and Semrush risk scores are hints to look closer, never a reason to disavow. build.py enforces this.

Scripts do every count, match and join; never estimate a number by reading. `$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). Scripts need Python 3 with pandas and openpyxl (`pip install --break-system-packages pandas openpyxl` if missing). Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## What you need

- **Exports** from one tool (Ahrefs or Semrush): client backlinks, client referring domains, broken backlinks, competitor comparison, link gap; optional anchors, Semrush Backlink Audit, link gap in pages mode. Plus the **GSC Links report** export. [references/exports.md](references/exports.md) says where each one is in each tool. Ask for whatever is missing in one message, and carry on with what you have.
- **Client facts**: client name, domain, brand terms (name, doctor's name, nicknames), 3-5 competitors.
- **GSC Manual Actions result** from the person (SOP Step 2): *No issues detected*, *Unnatural links to your site*, *Unnatural links from your site*, or other, with the date checked. The Search Console API can't read manual actions, so you can't check it yourself: if the person hasn't said, ask. If they can't answer now, treat it as no manual action and say so at the top of the report.
- **Optional**: the client's prune & merge sheet or redirect map (as CSV), so broken-backlink redirects match planned redirects.
- **Composio** with Google Search Console connected, for live URL checks and page clicks ([references/composio.md](references/composio.md)).

## Step 1: Load the SOP fresh

Fetch the Notion page above at the start of every run, even if an older copy is in context, and note its last-edited time. Take from it: the disavow rule, the export list, the tab columns and the review rules in its Step 4 prompt and Steps 5-6. Done when you can list anything in the SOP that differs from this skill.

## Step 2: Config and exports

Identify each attached file by its header row (references/exports.md), then write `work/config.json`:

```json
{"client": "Balance Aesthetics", "domain": "balanceawfl.com", "tool": "ahrefs",
 "competitors": ["competitor1.com", "competitor2.com", "competitor3.com"],
 "brand_terms": ["balance", "dr smith"],
 "manual_action": "none", "manual_action_checked": "2026-10-25",
 "safe_domains": []}
```

`manual_action` is one of `none`, `unnatural-to` (Unnatural links to your site), `unnatural-from` (from your site: fix outbound links, never disavow), `other`, or `unknown`. `safe_domains` lists domains that must never be flagged (the client's other sites, known partners). `toxic_threshold` (default 60) sets the Semrush score that counts as a flag.

```
python $SKILL/scripts/prep.py --config work/config.json --out work \
  --backlinks B.csv --refdomains R.csv --broken BR.csv --compare C.csv --gap G.csv [--gap G2.csv] \
  [--anchors A.csv] [--audit AUDIT.csv] [--gsc-links GSC.csv] [--gap-pages GP.csv] [--redirect-map MAP.csv]
```

Read the printed column mapping for every file. Done when each file mapped the fields its row in references/exports.md needs, every competitor has a column in the gap file(s) (no NOTE saying one is missing), and the comparison export has a row for the client and every competitor. Fix mappings with `--map` and re-run.

## Step 3: Live status

Check every URL in `work/status_needed.txt` from the Composio workbench and save the results to `work/status.tsv` (references/composio.md). Done when status.tsv has a line for every URL in status_needed.txt.

## Step 4: Review and decide

Open `work/disavow.csv`, `work/broken.csv` and `work/opportunities.csv`, and write `work/decisions.json` following [references/review.md](references/review.md):

1. **Disavow Review**: look at every row; drop false positives, move scrapers to noise, group patterns, add anything prep.py missed. Done when every remaining row is something a person should actually look at, and no row says disavow candidate unless `manual_action` is `unnatural-to`.
2. **Broken backlinks**: a target and action for every broken URL that status.tsv shows is still broken. Pull GSC page clicks through Composio when two targets are equally close. Done when every still-broken URL has a target or `drop`.
3. **Link opportunities**: set the real type, a specific `do_this` for High rows and every Other row, the target page, and `include: false` for link sellers and irrelevant sites. Open the Evidence URL (or search the domain) for High rows when the type isn't obvious. Done when no kept row is type Other without a `do_this`.
4. **Takeaways**: 3-5 sentences, each with a number from the CSVs.

## Step 5: Build and check

```
python $SKILL/scripts/build.py --work work --out "work/CLIENT Backlink Audit Month YYYY.xlsx"
```

build.py writes the three tabs (formatting, dropdowns for Final Decision, Status and Priority, yellow columns for the person to fill) and runs the QA: every target answers 200, no broken URL listed twice, no opportunity domain on the Disavow Review tab, no disavow candidate without the manual action, valid priorities and types, 3-5 takeaways. If it lists URLs with no status, check them (Step 3) and run again. Done when it prints "All checks passed". Fix problems in decisions.json or status.tsv, never in the workbook. Then spot-check 10 rows of each tab against the source exports (authority, counts, URLs) and say you did.

## Step 6: Deliver

If the Google Drive connector is available, upload the .xlsx as a Google Sheet named "[Client] Backlink Audit [Month YYYY]" (convert on upload) and check that the three tabs and dropdowns came through. Otherwise send the .xlsx and tell the person to import it with File > Import > Upload > Replace spreadsheet.

Reply in plain language:
- The GSC manual actions result and what it means for disavowing (one line).
- The 3 biggest findings and the top 5 actions.
- Counts: Disavow Review rows (and noise domains summarized), broken URLs to fix and already fixed, opportunities kept, removed and over the 75 cap.
- What's missing or uncertain: exports not attached or capped, blank Rollup columns, URLs that blocked the status check, anything that disagreed with the SOP.
