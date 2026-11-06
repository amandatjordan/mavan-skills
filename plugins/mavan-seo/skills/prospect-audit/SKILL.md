---
name: prospect-audit
description: Run Mavan's prospect audit for a potential client where Mavan has no Search Console or GA4. From a crawl plus Semrush or Ahrefs exports (ranking keywords, keyword gap, and optionally backlinks and backlink gap) it builds a workbook with the competitor keyword gap, thin content and ranking URLs that are not live, runs the service gap, information architecture, service page title and H1 and backlink audits, and drafts a prospect-facing report. Use for prospect audits, sales audits, pitch audits, or any audit of a site we have no Search Console for.
---

# Prospect Audit (Mavan)

An outside-in audit to support a sales conversation. It finds real, site-specific problems using only what can be collected without access to the site: a crawl and Semrush or Ahrefs exports. It is the prospect version of the site diagnosis flow, with no trend or timing analysis because that needs Search Console.

This skill is the orchestrator. It does three things itself (the competitor keyword gap, a thin content flag, and a check of which URLs ranking in the keyword tool are not live pages in the crawl), then runs four existing skills and delivers one summary. It does not change those skills.

Scripts do every count, join and column mapping; never estimate a number by reading. `$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). Scripts need Python 3 with pandas and openpyxl. Work in a folder named after the prospect with a `work/` subfolder, and keep a task list with one item per step.

**No Composio, no live site visits, no DataForSEO, no Search Console.** Inputs are uploaded files only. Use no tool, dependency, fallback or extra step beyond those named here without asking the person and explaining why. If a step is unreliable or expensive, stop and say so. If a tool is blocked, say what you tried and ask. Assume nothing about the site: structure, services and cities come from the crawl and the person confirms them.

## What the keyword numbers are

Say this in the reply and the workbook's Read Me says it too.

- **Volume and traffic are the tool's estimates**, from its model, not the site's clicks or impressions. Label them "estimated" everywhere. Never call them clicks or impressions. Scripts never add them across keywords or pages, so no group or page has a total.
- **It is a snapshot** of current positions. It cannot show a trend or change over time.
- **It covers keywords the tool tracks**, mostly the top 100 positions. A page with none shows "No tracked keywords", never "no traffic".
- **Competing pages are not checked.** These exports list one ranking URL per keyword, so a second page competing for the same search is mostly invisible. Close keyword variants are grouped together in the keyword gap instead.

## What you need

Ask for what is missing in one message (use the AskUserQuestion tool for choices; see Step 0).

1. **Crawl** (Sitebulb or Screaming Frog, the site-crawling tools): the exports the information architecture audit asks for (URL export, all internal links, redirects).
2. **Ranking keywords** from Semrush (Organic Positions) or Ahrefs (Organic Keywords) for the prospect: CSV.
3. **Keyword gap** from Semrush (Keyword Gap) or Ahrefs (Content Gap) with the prospect and 2-4 competitors: CSV. Use the same tool as the ranking export where possible.
4. **Optional, for the backlink audit**: the prospect's backlinks (live and lost) and the backlink gap from the same tool (the backlink-audit skill lists which exports). If the person has neither, skip the backlink audit and say so.
5. **Client facts**: prospect name, domain, brand terms, 2-4 competitors, practice type, and the cities served.

[references/exports.md](references/exports.md) lists the columns each tool's export has and how the scripts detect the tool.

## Step 0: Confirm the plan, then preflight

Ask in one multiple-choice call, with options built from the person's files and chat: the competitors (offer the domain columns found in the gap export), brand terms (offer candidates from the business name and domain, plus "none"), and practice type. If the practice type is not med spa or plastic surgery, the service gap audit does not apply (its taxonomy covers only those): say so now and skip it.

Write `work/config.json`:

```json
{"client": "Example Spa", "domain": "example-spa.com",
 "competitors": ["rival-one.com", "rival-two.com"],
 "brand_terms": ["example spa"], "practice_type": "medspa"}
```

Then run the preflight. It checks every file is there and the right kind (crawl has the needed columns, the ranking and gap exports are Semrush or Ahrefs files with the right fields, the gap export has a position column for the prospect and each competitor) and that the facts above are filled in. Run it again whenever the person adds a file.

```
python $SKILL/scripts/prep.py preflight --config work/config.json --crawl URLS.csv --ranking RANK.csv --gap GAP.csv \
  [--backlinks BACKLINKS.csv --backlink-gap BACKLINK_GAP.csv] --out work
```

Read `work/preflight.md`. If it says NOT READY, send the person **one** message listing each FAIL and exactly which export or answer is needed and where to get it, then stop. Do not build around a missing input. The backlink exports are the only inputs that can be skipped: if they are missing, ask whether to wait or continue without the backlink audit, and note it in the reply. Done when the preflight says READY.

## Step 1: Keyword exports

```
python $SKILL/scripts/prep.py keywords --config work/config.json --ranking RANK.csv --gap GAP.csv --out work
```

It prints which tool it detected for each file ("Detected Semrush") and the column mapping. Read the mapping and tell the person which tool it found. If it cannot tell, ask which tool made the file and pass `--tool`. Fix a wrong mapping with `--map ranking.volume="Column name"`; a domain column it missed with `--gap-col "domain.com=Column name"`. It writes `work/ranking.csv` and `work/gap.csv` (searches a competitor ranks for and the prospect does not).

Done when each required field mapped, the prospect and every competitor have a position column, and any NOTE (capped export, mixed tools) is carried into the reply.

## Step 2: Crawl

The person crawls the site the usual way and exports the files the information architecture audit asks for. No extra URL file is needed. The catch: a crawl that follows links will not find old or orphaned pages, so a URL that ranks in the keyword tool but is missing from the crawl shows as "Not in crawl" on the Ranking URLs Not Live tab. That means "the crawl did not find it", not "the page is gone"; say so in the reply.

```
python $SKILL/scripts/prep.py crawl --crawl URLS.csv --out work
```

It stops (exit 2, FAIL) when fewer than 10 pages return 200, or when 20% or more of the 200 pages have no title, no H1 and no words; that crawl did not render the pages. Tell the person and ask for a re-crawl; do not audit around it. Otherwise it writes `work/crawl.csv` and `work/thin_candidates.csv` and prints the folders with the most thin candidates.

Done when it prints PASS.

## Step 3: Thin content decisions

Thin means an indexable page that returns 200 with under 300 content words (the same line the service gap audit uses), listed from the crawl. Many of these are not problems (contact, galleries, tag archives). From the printed folder profile, ask the person (multiple choice, built from this site's folders, biggest first) which folders are not worth flagging, and write `work/thin_decisions.json`:

```json
{"exclude_folders": ["gallery", "tag"], "exclude_urls": ["https://example-spa.com/contact/"]}
```

Never decide a folder is junk from its name alone: check the examples and word counts first. Done when every folder with five or more candidates is either excluded or confirmed as real thin content.

## Step 4: Keyword gap groups

Read `work/gap.csv` (top 300 by `est_volume`, not the whole file) and write `work/gap_groups.json` following [references/rules.md](references/rules.md): one group per service, concern or location, each with match terms, a kind, and a practice type. Put competitor-name and prospect-brand searches in a group with kind `exclude`. Run the build (Step 6), read the unassigned count, add groups for the largest unassigned keywords, and repeat until the unassigned share is small. Done when build.py prints no WARNING about unassigned keywords and you have read the top 10 groups against their keywords.

## Step 5: Run the existing audits

Load each with the Skill tool and follow it, with these prospect adjustments. Each produces its own workbook in the prospect's folder.

- **Service gap** (`service-gap-audit`): only for med spa or plastic surgery. Otherwise skip and record "Does not apply: no taxonomy for this practice type" in `other_audits.json`. When it runs, fill each service group's `service_gap_ref` from its result.
- **Information architecture** (`information-architecture-audit`): there is no Search Console sheet, and Semrush or Ahrefs volume must never be fed in as impressions. Run it without the sheet (its preflight offers "continue without it"; pick that). The internal linking opportunities tab comes out empty; say so.
- **Service page titles and H1s** (`service-page-title-h1-review`): run it on the service pages without a Search Console sheet. The Suggested Keywords column is then judgment, not data. For each page, this skill's workbook (Ranking Pages tab) shows the top tracked keyword and its estimated search volume, so the writer can compare.
- **Backlinks** (`backlink-audit`): only when the person has the backlink exports. Set `manual_action` to `unknown` in its config, since Search Console is not available: nothing will be marked as a disavow candidate. Say that in the reply.

Write `work/other_audits.json`: `[{"name": "Service gap", "status": "Ran", "file": "x.xlsx", "note": ""}, ...]`. Status is `Ran`, `Skipped` or `Does not apply`; note says why, in words only (no numbers).

## Step 6: Build and check

```
python $SKILL/scripts/build.py --work work --out "work/PROSPECT Prospect Audit Month YYYY.xlsx"
```

Tabs: Read Me, Summary, Competitor Keyword Gap, Gap Keywords, Thin Content, Ranking URLs Not Live, Ranking Pages. It checks that gap keywords reconcile (assigned + left out + unassigned = total), that thin counts reconcile, that ranking URLs reconcile, and that estimate columns are labeled and none is called clicks or impressions. Done when it prints "All checks passed". Fix problems in the decisions files, never in the workbook. Then spot-check 5 gap groups against the source export and 5 thin pages against the crawl, and say you did.

## Step 7: Prospect report

Build the short prospect-facing report with the `seo-audit-client-report` skill, from the five workbooks. Its rules apply (no promised results, no internal labels or tab names, only the prospect's own data, plain words), with one exception decided for prospects: **the keyword gap may show a search's estimated monthly volume**, always worded "estimated monthly searches" with this caveat next to it: "These are the keyword tool's estimates for the search, not a forecast of visits or leads." Never add volumes across searches. Where the report would say the prospect's pages "get no traffic", say "no tracked keywords" instead.

## Step 8: Reply

Plain language:
- The tool detected (Semrush or Ahrefs) and the three limits above, in one line each.
- The biggest findings and what each audit found, with counts from the workbooks.
- Ranking URLs that are not live pages (the count and the top examples): this is often the main finding.
- Which audits ran, were skipped or do not apply, and why.
- What the person reviews next. Also propose, without making it: a Semrush/Ahrefs input option for the title and H1 review, so ranking keywords can replace the Search Console queries column.
