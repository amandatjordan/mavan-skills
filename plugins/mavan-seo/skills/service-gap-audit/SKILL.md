---
name: service-gap-audit
description: Run Mavan's Service Gap Audit for a medspa or plastic surgery site from a Sitebulb or Screaming Frog export and the bundled Service Taxonomy, and build the gap audit workbook. Use for service gap audits, missing service pages, or thin and non-indexable service pages.
---

# Service Gap Audit (Mavan SOP)

This skill carries the whole process and does not need the written SOP; a copy in a project management tool is documentation for people.

The audit answers four questions for every service in the taxonomy: does the practice offer it, does it have a page Google can index, does that page have real content, and how much national search demand is behind it. The deliverable is the Recommendations tab: one row per page to build or fix.

Work only from files: the crawl export, the bundled taxonomy, and anything the person attaches. Every count, match and join is done in Python (pandas, openpyxl); never estimate a number by reading. `$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## What you need

- **Crawl export** (CSV, internal HTML URLs, every status code). Sitebulb: URL, HTTP Status Code, Indexable Status, Title, Meta Description, H1, H2, H2 (second), No. Content Words, and the canonical URL column if exported. Screaming Frog: Address, Status Code, Indexability, Indexability Status, Title 1, Meta Description 1, H1-1, H2-1, H2-2, Word Count, Canonical Link Element 1. Ask for it if missing.
- **Client facts**: domain, practice type (medspa, surgical, or both), service-area cities. Ask in one question for whatever the request doesn't give.
- **Taxonomy**: `$SKILL/references/service-taxonomy.xlsx`. Tabs: Taxonomy (match terms per Service / Sub-Service / Brand / Device / Concern), Filters (exclusion, city/state, modifier patterns, place-name word lists), All Keywords (the competitor keyword list with US national volume, already classified). If the person attaches a newer taxonomy or keyword list, use theirs and say so.
- **Optional**: a Search Console queries export (CSV from the GSC web UI).

## Vocabulary

Use these names in every column, label and message: **Category > Service > Sub-Service > Brand / Device**. A **Concern** is a problem people search for; it points to Services and is never a page gap on its own. A **Modifier** (Cost, Before & After, Recovery / Risks, Comparison, Candidacy, Best / Top) is a flag on a keyword, never a level. Name every page for what it is: a Botox page is Botox (Brand / Device under Neurotoxin), never "Neurotoxin".

## Step 1: Load and classify

Load the crawl into a standard frame (path, status, indexable status, title, H1, H2, H2b, meta description, content words, canonical). Load the Taxonomy and Filters tabs. If you use the bundled All Keywords tab, its Class / Service / Sub-Service / Brand columns are already set; re-classify only when the person attached a different keyword list, using the rules in [references/rules.md](references/rules.md) § Keyword classification.

Done when you can print: page count by status code, keyword count by Class, and the number of taxonomy rows by Level.

## Step 2: Type and label every page

Apply [references/rules.md](references/rules.md) § Pages: page type, indexability (including the canonical loop), and each Service page's primary node.

Done when every Service page has a primary node or is on a printed "not in taxonomy" list, and you have opened the label for 5 Service pages and agree with each one (the page's path, title and H1 name that node).

## Step 3: Coverage, offered status and gaps

Apply [references/rules.md](references/rules.md) § Coverage, § Offered status, § Gaps and priority, and § Page briefs, for every taxonomy node that fits the practice type.

Done when every in-scope node has an Offered Status and a Coverage value, every gap row has a Priority and a Recommendation, and no node marked "Do not flag" or "NOT US-approved" has a gap.

## Step 4: Keywords per page

Apply [references/rules.md](references/rules.md) § Keywords per page and § Other markets. Keep the client's service-area cities.

Done when every Recommendations row has Relevant Keywords (or the "None in competitor keyword list" text) and a Total National Search Volume, and every excluded keyword is listed with its reason.

## Step 5: Build the workbook

Follow [references/workbook.md](references/workbook.md) for tabs, columns, labels and sort order. Save as `<domain>_service_gap_audit.xlsx`.

Done when the workbook opens with every tab in the spec, in order, and the Recommendations tab's header groups and Why Recommended labels match the spec exactly.

## Step 6: Check, then report

Run every check in [references/workbook.md](references/workbook.md) § QA. Fix and rebuild until all pass.

Then send the workbook and reply in a few sentences: the biggest issue, the top missing pages, what needs client confirmation, and every service or brand on the site that isn't in the taxonomy (so it can be added to `service-taxonomy.xlsx` by pull request).
