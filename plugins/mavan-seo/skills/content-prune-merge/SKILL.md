---
name: "content-prune-merge"
description: "Run Mavan's Content Prune & Merge audit for a client site from crawler exports plus GSC/GA4, and fill a client copy of the Prune & Merge template sheet. Use for prune, merge, or cannibalization audits."
---

# Content Prune & Merge

The Notion SOP is the **source of truth** for the template link, decision rules, column definitions, Recommendations rules and prompts: [Content Prune & Merge Process](https://app.notion.com/p/Content-Prune-Merge-Process-3f518945155e80c78bfbcd3c3135a612). This skill is the execution layer: how to run the SOP with Claude's tools, and the gotchas learned on real runs. When the SOP and this skill disagree, the SOP wins; say so in the final report.

## Inputs

- Domain and brand terms (client name, doctor's name, common misspellings).
- The three crawler exports from SOP Step 2: live pages, redirects/errors, all internal links. Sitebulb names them `*_internalfiltered*.csv`, `*_internal_redirected_urls.csv`, `*_links*.csv`. The links file is large (20MB+): load it with pandas, never read it into context.
- Whether to use an existing Site Architecture (IA) audit. Use it only when the user says so; otherwise build page types from scratch.

## Steps

1. **Load the SOP fresh.** Fetch the Notion page at the start of every run, even if an older copy is in context, and note its last-edited time. Take from it: the template link, tab names, paste cells, the Step 4 prompt (columns, Page Type values, suggestion rules, exact Notes wording, Recommendations rules and Area labels), the Step 6 QA prompt and the Step 7 redirect prompt. Done when you can list the current outputs the Step 4 prompt asks for.
2. **Inspect the template.** Open the template sheet named in the SOP with `get_spreadsheet` (tab names, header rows, formulas in row 2, dropdowns). Done when you know which columns are formula-filled and where pasted data starts on every tab.
3. **Profile the crawl** (Python in the working directory, `python3 -I`). Normalize every URL: https, non-www, trailing slash, no query or fragment. Lowercase for joining, but keep the original case to detect case duplicates (e.g. `/Facelift/` returning 200 beside `/facelift/`). Drop `?utm_` variants. Count live pages by folder. Done when every live 200 URL has a normalized path.
4. **Pull GSC and GA4 through Composio** (see Data pull). Done when you hold, per normalized page: clicks, impressions, non-brand query count, top non-brand query, sessions, new users, views, key events, plus the overlap list.
5. **Find what the crawl missed.** From the Composio workbench (it can fetch the live site; the container usually cannot), fetch `robots.txt` and the Yoast/WordPress sitemap index, list sitemap URLs not in the live crawl, and request each one. Also check the status of every non-live URL with GSC impressions or GA4 sessions. Done when every sitemap orphan and every non-live URL with demand has a status code.
6. **Build the Audit rows** in a script (`build.py`) so reruns are one command. Apply the SOP rules in order with the Page typing signals below. Write judgment overrides as an explicit dict with a reason string, and mark them "judgment" in Notes. Done when every live page has a Page Type, Suggested Next Step and Notes, and no Merge/Remove target is itself being merged or removed.
7. **Build the Recommendations rows** per the SOP (6-12 rows, Priority | Area | Problem | Do this), using only Area labels that at least one Audit row will carry. Done when every Area used maps to rows the sheet will count.
8. **Build the Existing Redirects rows** (`redirects.py`): repoint existing 3XX whose target is now being merged or removed, add `SUGGESTED - check target` rows for 404s with demand, and one wildcard row per junk folder. Done when the QA checks all pass.
9. **Fill a client copy of the template** (see Sheet), read it back and compare. Done when the read-back matches the source rows cell for cell and the Area column and Pages counts show values.
10. **Report** in chat: the analysis window, counts per suggestion, findings that change the plan (missed archives, demand gaps, technical bugs, Needs Discussion items), judgment calls, any SOP/skill disagreement, and data you could not get.

## Data pull (Composio)

- `COMPOSIO_SEARCH_TOOLS` for Search Console and GA4, then `GOOGLE_SEARCH_CONSOLE_SEARCH_ANALYTICS_QUERY` and `GOOGLE_ANALYTICS_BATCH_RUN_REPORTS`. Use the site property exactly as listed (it may be `https://domain/` rather than `sc-domain:`). Find the GA4 property via `GOOGLE_ANALYTICS_LIST_ACCOUNT_SUMMARIES` by display name.
- Pull in the workbench with `row_limit: 25000`, paginating with `start_row`: dimensions `page` (12 mo), `date,page` (16 mo, for the migration check), `page,query` (12 mo). GA4: `landingPage` with `sessions, newUsers, screenPageViews, keyEvents`; also key events by `eventName` so you know what counts as a conversion.
- **Migration check:** monthly impressions on live vs non-live URLs. A small, fading non-live share means no migration: say so and use the plain 12-month window.
- **Overlap:** shared non-brand impressions as a share of the smaller page's total. Global pairwise overlap is noise on local sites (generic "... city mi" queries hit dozens of pages), so compute it within treatment groups (slug regex per treatment) and between concern and service pages, with a floor of 20 impressions. Keep each page's strongest competitor for Notes.
- **Getting data out:** the container cannot download workbench files (the Composio file host is blocked by the proxy). Aggregate fully in the workbench, print compact tab-separated rows, write them to a local file, and verify with row counts, column sums and an md5 of a text column computed on both sides.
- GA4 landing pages include non-site paths (booking-widget UUID folders, `/to/` short links, `(not set)`): confirm they 404, then exclude them.

## Page typing signals

WordPress sites put posts and service pages at the root, so slug rules alone misfire. Use the links export first:

- Linked from `/blog/` or `/blog/page/N/` content = **Blog Post**.
- Linked from the `/conditions/` (or `/concerns/`) hub content = **Concern / Condition**.
- `/services/{category}/` pages with ~10 words = **Hub / Category Page**, not Service.
- Sitebulb `Location`: `Header` = main menu; `Content` and `Navigation` = in-body links; footer links are sitewide.
- A root page with a long slug that is not on the blog listing is a page, not a post: type it Service and say "check" in the reason.
- **Page Type Reason wording drives the sheet:** the Area formula tags any reason containing "Root-level" or "No rule matched" as *Check page type*. Use those words only when the type is a slug-rule guess. Signal-based types get reasons like "Listed on /blog/ pagination (WordPress post)" or "Listed on the /conditions/ hub".

## Sheet

- **Copy the whole template file** named in the SOP with the Google Drive connector (`copy_file`), titled `{Client} Content Pruning and Merging`. Keep every tab name: the formulas depend on them.
- **Audit:** column A (Area) is a formula; write rows starting at **B2**, in chunks of about 60 rows with `update_values` (larger calls risk size limits), sorted by Page Type then Impressions descending. Leave Next Steps, Target URL, Reasoning and Referring Domains blank.
- **Recommendations:** write columns B-E starting at **B5**; #, Pages and Where to find fill themselves.
- **Existing Redirects:** Source | Target | Notes from A2.
- **Notes wording drives the sheet too:** the Area formula looks for "Blog outranks service", "city copy of", "In main menu" and "Already redirected to by". Write those flags with the SOP's exact wording.
- Read back with `get_values`; large results save to a file, so compare that file to your source JSON in Python.

## Notes column rules

- Start with `Suggested because: ...`, then the SOP flags joined with `; `.
- A Keep row carrying a "Competes with" flag says "kept by default (rule 7), but it overlaps with the page flagged below - review whether both should stay", so the note never contradicts the decision.
- A keeper says how many pages are suggested to merge into it.
- Flag broken canonicals (canonical pointing at a 404), case-duplicate URLs, and menu links pointing at pages suggested to redirect.

## QA

Run in code before writing the sheet:

- Every Merge/Remove row has a full target URL that is a live page marked Keep, Update, Repurpose or Needs Discussion.
- No target is also a source, and no wildcard pattern matches any target.
- Every existing 3XX that pointed at a page being removed now points at the final page.
- Every junk folder found in the sitemap (category, tag, author, date archives) has a wildcard, and every wildcard note says to disable those archives in the SEO plugin.
- Every Recommendations Area label is spelled exactly as in the SOP list.

The duplicate-source check will list existing no-slash redirects next to their slash versions on the Audit tab; those are one rule apiece, not conflicts.