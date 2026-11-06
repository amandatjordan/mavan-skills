---
name: site-diagnosis
description: Work out what is going wrong on an existing client's site. Compares two periods of Search Console page + query data (clicks and impressions, which pages and searches gained or lost, which pages compete for the same search, which losing URLs no longer return 200), then runs the information architecture audit and the service gap audit as the evidence calls for. Use for traffic drops, "what happened to this site", site diagnosis or triage, cannibalization checks, or before choosing which audit to run.
---

# Site Diagnosis (Mavan SOP)

One entry point for an existing client's site. Triage runs first and reports what changed and what it affected. The evidence then decides which existing audits to run: `mavan-seo:information-architecture-audit` and `mavan-seo:service-gap-audit` are loaded as they are and still work on their own. Content Prune & Merge and the backlink audit are recommended, not run from here.

**Triage reports the change. It does not explain it.** Do not claim a migration, site change, launch date, algorithm update or seasonality caused anything, and do not go looking for one. Say what moved and which pages and searches it moved on.

Scripts do every count, join and sum; Claude reads the output and asks questions. Never type or estimate a number. Assume nothing about the site's URL structure, folders, page types, cities or services: learn them from the data and confirm with the person. **Never use Composio or any connector for Search Console**, and never use one for anything else in this skill without asking first. If a later audit wants GA4 through Composio, that audit's own rules apply (it asks first and pulls only the fields it names). Add no tool, dependency, fallback chain or extra step beyond those named here without telling the person why and getting approval. If a step proves unreliable or expensive, stop and say so.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads). The script needs Python 3 with pandas and openpyxl. Work in a folder named after the client with the files in it, and keep a task list with one item per step.

## How to ask the person questions

Ask with AskUserQuestion (multiple choice) whenever the answer is a choice; use one plain-text message only when that tool is not available (an unattended run), and then say which reading you took at the top of your work.
- Build every option from this site's own data (the files, the profile output), never from a list written into this skill.
- Put the best-supported option first, marked "(Recommended)", then the plausible others with one line on what each leads to. The person can always type their own answer.
- Never fill in a default silently. A guess (brand terms inferred from the name or domain, a threshold) goes in a question to confirm.
- Make each question stand on its own: the dialog may be all the person sees, so name the file, tab or number in it. 1-4 questions per call, 2-4 options each.
- Ask only what the data cannot settle.

## What you need

- **Search Console data for two periods**, as a Google Sheet or .xlsx / .csv download: page + query rows with the columns Page, Query, Clicks, Impressions (Position is used when present, CTR is not needed). One set per period, either two files or two tabs of one file. If a file has a tab named "Claude Use This" that tab is used; otherwise the one tab with those columns; several candidate tabs mean ask which is which. Never add tabs together.
- **The two date ranges.** The sheets do not say which dates they cover, and there is no default comparison. Ask which range each set covers as a multiple-choice question, with options built from any dates visible in the sheet, tab names or file names and the export date, plus Other. Period A is the earlier period, period B the later one. Write the answer down; never guess.
- **Client facts**: business name and domain. Derive brand-term candidates from the name and domain (name, shortened forms, domain without the extension) and confirm them: offer the candidates, "none, do not filter" and Other.
- **Optional crawl URL export** (Sitebulb or Screaming Frog, every status code): lets triage flag losing URLs that no longer return 200. Needs a URL column (URL / Address) and a status column (HTTP Status Code / Status Code). Without it, triage lists the URLs for the person to check.

## Step 1: Profile

```
python $SKILL/scripts/triage.py profile --domain DOMAIN --a A.xlsx [--a-tab NAME] --b B.xlsx [--b-tab NAME] \
  --brand "term,term" [--crawl CRAWL.csv]
```

It writes nothing. It prints each period's rows, pages, clicks and impressions, a warning for pages on other domains, the top non-brand searches (look for brand terms you missed and confirm any with the person), how many searches have competing pages at several impression levels, and the crawl status mix. Fix any input problem it reports before going on.

## Step 2: Confirm the thresholds (stop and ask)

Four numbers have no default in the script. Ask them as multiple-choice questions, built from the profile output, and wait:
1. **Minimum impressions for a page to count as competing** for a search (options: the levels the profile printed, with their search counts, recommended = the one that gives a list the person can actually read, typically tens of searches, not hundreds).
2. **How many competing searches count as "many"** (the number at which Content Prune & Merge is suggested). Offer values around the count the chosen level produced.
3. **What share of period A non-brand impressions on non-200 URLs triggers the IA audit suggestion** (only when a crawl is attached).
4. **How many losses and gains to list** (Top N), and whether to rank by impressions (recommended) or clicks.

## Step 3: Build

```
python $SKILL/scripts/triage.py build --domain DOMAIN --client "Client Name" --brand "term,term" \
  --a A.xlsx --a-start YYYY-MM-DD --a-end YYYY-MM-DD --b B.xlsx --b-start YYYY-MM-DD --b-end YYYY-MM-DD \
  --min-page-impr N --top-n N --prune-if N --dead-share-pct N [--rank-by impressions|clicks] \
  [--include-brand-competing] [--crawl CRAWL.csv] --out "CLIENT Site Triage.xlsx"
```

It writes the workbook and `CLIENT Site Triage URLs to crawl.txt`: every Search Console URL, one per line, for the IA audit's crawl (see Step 5). Tabs, see [references/workbook.md](references/workbook.md): Summary, Pages, Searches, Pages behind searches, Competing pages, What to run next. Read the printed totals and warnings and compare them with the profile. Done when it prints "Wrote".

## Step 4: Review and report

Open the workbook and read it before reporting. Check that the totals match the profile, that the biggest losses make sense as pages and searches for this site, and that the brand filter did not hide or keep the wrong searches. Then tell the person, in plain language and from the workbook only:
- The overall change in clicks and impressions, total and non-brand.
- The pages and searches that drove it (name the biggest few with their numbers).
- With a crawl: how much of period A's visibility sits on URLs that do not return 200, and that "Not in crawl" is not proof a URL is dead. Without a crawl: the losing URLs to check.
- The competing-pages count and two or three clear examples (the search, the pages and their numbers).
- That Search Console page + query totals can be lower than the Performance report.

Send the .xlsx. Do not say why anything happened.

## Step 5: Choose what to run next (ask)

Read the What to run next tab. Present each row's evidence and ask which audits to run, with the suggested ones first. Then:
- **Information architecture audit**: load it with the Skill tool and carry out its steps. Before the person crawls, tell them: **add the URLs in `CLIENT Site Triage URLs to crawl.txt` as a URL list in Sitebulb or Screaming Frog**, because a sitemap-only crawl misses old URLs that still have search visibility. If a crawl already exists and the triage status counts show many "Not in crawl" URLs, ask for a new crawl with that list. Give the IA audit this Search Console sheet (period B, or the combined window if the person prefers) and the dates it needs; do not ask for them twice.
- **Service gap audit**: it only covers med spa and plastic surgery sites (its bundled taxonomy has those two industries). Ask what the client offers. If it is neither, say the audit does not apply and do not run it.
- **Content Prune & Merge** and **backlink audit**: say they are suggested and what the evidence was; the person starts them.

When an audit is loaded, follow that skill's own steps and rules. Do not copy its scripts or reword its workbook.

## Step 6: Deliver

One summary reply: the triage findings (Step 4), then one line per audit that was run with its workbook, and one line per audit suggested but not run with the evidence. Send each workbook. Mention anything that could not be done (no crawl, a sheet with warnings, an audit that does not apply). Close with the one natural next step.
