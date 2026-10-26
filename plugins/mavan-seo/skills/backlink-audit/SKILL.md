---
name: backlink-audit
description: Run Mavan's backlink audit for a client site from two Ahrefs or Semrush exports (client backlinks and link gap), checking broken backlinks live, and build the two-tab workbook: recommendations (broken backlinks to fix, link opportunities) and a disavow review list. Use for backlink audits, link gap or link intersect analysis, broken backlinks, toxic links or disavow questions.
---

# Backlink Audit (Mavan SOP)

This skill holds the whole process: goal, disavow rule, exports, review rules, workbook and the person's next steps ([references/process.md](references/process.md)). It runs from the attached CSV exports and Composio only. Don't look for the process anywhere else; a written copy elsewhere is documentation for people.

The deliverable is one workbook with two tabs, in this order: **Recommendations** (broken backlinks to fix, and link opportunities from competitors) and **Disavow Review** (sketchy links for a person to look at). It matches the Google Sheets template in the SOP.

**Disavow rule.** Nothing is marked for disavow unless Google Search Console shows a manual action for *Unnatural links to your site*. Ahrefs and Semrush risk scores are hints to look closer, never a reason to disavow. build.py enforces this.

Scripts do every count, match and join; never estimate a number by reading. `$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). Scripts need Python 3 with pandas and openpyxl (`pip install --break-system-packages pandas openpyxl` if missing). Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## What you need

- **Two exports** from one tool (Ahrefs or Semrush): **client backlinks** and the **link gap** (Semrush Backlink Gap, Ahrefs Link Intersect). That is all an audit needs: referring domains, anchor mix and broken backlinks are derived from the backlinks export plus a live URL check. [references/exports.md](references/exports.md) says where each export is in each tool and lists the optional ones (referring domains, Backlink Audit, GSC Links, redirect map); they only fill extra columns, so don't ask for them unless the person already has them. Only ask for an export that file lists for their tool, and ask for whatever required one is missing in one message.
- **Client facts**: client name, domain, brand terms (name, doctor's name, nicknames), 3-5 competitors (how to pick them: references/process.md § Competitors).
- **GSC Manual Actions result** from the person: *No issues detected*, *Unnatural links to your site*, *Unnatural links from your site*, or other, with the date checked. The Search Console API can't read manual actions, so you can't check it yourself: if the person hasn't said, ask. If they can't answer now, use `unknown` (references/process.md § Disavow rule).
- **Optional**: a planned redirect map as CSV (e.g. a prune & merge Redirects tab), so broken-backlink redirects match planned redirects.
- **Composio**, for the live URL checks ([references/composio.md](references/composio.md)). Search Console doesn't need to be connected. Without Composio, ask the person to run the status check snippet themselves or list the URLs for them to check.

## Step 1: Config and exports

Identify each attached file by its header row (references/exports.md), then write `work/config.json`:

```json
{"client": "Example Med Spa", "domain": "example.com", "tool": "ahrefs",
 "competitors": ["competitor1.com", "competitor2.com", "competitor3.com"],
 "brand_terms": ["example", "dr smith"],
 "manual_action": "none", "manual_action_checked": "2026-10-25",
 "safe_domains": []}
```

`manual_action` is one of `none`, `unnatural-to`, `unnatural-from`, `other` or `unknown` (meanings in references/process.md). `safe_domains` lists domains that must never be flagged (the client's other sites, known partners). `toxic_threshold` (default 60) sets the Semrush score that counts as a flag.

```
python $SKILL/scripts/prep.py --config work/config.json --out work \
  --backlinks B.csv --gap G.csv [--gap G2.csv] \
  [--refdomains R.csv] [--audit AUDIT.csv] [--gsc-links GSC.csv] \
  [--redirect-map MAP.csv] [--broken BR.csv] [--gap-pages GP.csv]
```

Read the printed column mapping for every file. Done when each file mapped the fields its row in references/exports.md needs, and every competitor has a column in the gap file(s) (no NOTE saying one is missing). Fix mappings with `--map` and re-run. The NOTE lines list what stays blank because an optional export wasn't attached; carry them into the report.

## Step 2: Live status

`work/status_needed.txt` lists every client URL the backlinks point at, plus the homepage. Check them all from the Composio workbench and save the results to `work/status.tsv` (references/composio.md). This check is how broken backlinks are found, so don't skip it or sample it. Done when status.tsv has a line for every URL in status_needed.txt.

## Step 3: Review and decide

Open `work/disavow.csv` and `work/opportunities.csv`, run build.py once (Step 4) so it writes `work/broken_found.csv`, and write `work/decisions.json` following [references/review.md](references/review.md):

In the order of the tabs:

1. **Broken backlinks** (Recommendations): `work/broken_found.csv` lists the client URLs that status.tsv shows as broken, with who links to them. Give each a target and action. Done when every still-broken URL has a target or `drop`.
2. **Link opportunities** (Recommendations): set the real type, a specific `do_this` for High rows and every Other row, the target page, and `include: false` for link sellers and irrelevant sites. For High rows where the type isn't obvious, open the Evidence URL when there is one (Semrush has none: search the domain). Done when no kept row is type Other without a `do_this`.
3. **Disavow Review**: look at every row; drop false positives, move scrapers to noise, group patterns, add anything prep.py missed. Done when every remaining row is something a person should actually look at, and no row says disavow candidate unless `manual_action` is `unnatural-to`.

## Step 4: Build and check

```
python $SKILL/scripts/build.py --work work --out "work/CLIENT Backlink Audit Month YYYY.xlsx"
```

build.py finds the broken backlinks from status.tsv, writes the two tabs (formatting, dropdowns for Final Decision, Status and Priority, yellow columns for the person to fill) and runs the QA: every target answers 200, no broken URL listed twice, no opportunity domain on the Disavow Review tab, no disavow candidate without the manual action, valid priorities and types. If it lists URLs with no status, check them (Step 2) and run again. Warnings (not blocking) cover URLs the status check couldn't settle; mention them in the reply. Done when it prints "All checks passed". Fix problems in decisions.json or status.tsv, never in the workbook. Then spot-check 10 rows of each tab against the source exports (authority, counts, URLs) and say you did.

## Step 5: Deliver

Send the .xlsx. To use it in Google Sheets, the person opens a new blank sheet and uses File > Import > Upload > Replace spreadsheet; the tabs and dropdowns come through.

Reply in plain language:
- The GSC manual actions result and what it means for disavowing (one line). If it was `unknown`, say it still needs checking and where.
- The 3 biggest findings and the top 5 actions.
- Counts: broken URLs to fix and already fixed, opportunities kept, removed and over the 75 cap, Disavow Review rows (and noise domains summarized). Include the client's referring domains and backlinks, and the link-gap domains per competitor, from `work/prep_summary.json`: there is no Rollup tab, so this is the baseline the next audit compares against.
- What's missing or uncertain: capped exports, columns left blank because an optional export wasn't attached (linking-domain authority on Semrush without referring domains, GSC and risk-score columns), URLs that blocked the status check.
- What the person reviews next, from references/process.md § After delivery, for this audit's manual action result.
