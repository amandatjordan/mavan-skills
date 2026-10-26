# Existing redirects and QA

Do all matching in code, on normalized URLs (lowercase, https, non-www, trailing slash, no query or fragment). Only use target URLs that are live pages in the crawl.

A **chain** is A -> B -> C: every redirect goes straight to its final page. A **loop** is A -> B -> A, including a wildcard whose target matches its own pattern. A specific rule listed below a wildcard that also matches it never fires.

Valid final destinations: live pages whose suggestion (or, once a person has decided, Next Steps) is Keep, Update, Repurpose or Needs Discussion.

## Existing Redirects rows

Columns: Source URL | Target URL | Notes (full URLs). They appear at the bottom of the Redirects tab marked Now.

1. **Existing 3XX** from the redirects export: follow each to its final destination through other hops in the export.
   - Lands on a kept page in one hop: leave it off the tab (nothing to change). Lands on one after several hops: add it pointing straight at the final page, Notes `Chain removed (was A -> B -> C)`.
   - Lands on a page being merged or removed: repoint to that page's Suggested Target, following on until a kept page. Notes `Existing redirect - repointed (was X)`.
   - Lands on a 404 or missing page: suggest the closest kept page by topic, same treatment first. Notes start `SUGGESTED - check target`.
2. **404s with demand**: every non-live URL with GSC impressions, GA4 sessions or internal links that returns 404 today. Suggest a target the same way, Notes `SUGGESTED - check target. Currently 404s; [the demand, e.g. 860 impressions for "[treatment] [city]"]`. Confirm the 404 with a live request when web access allows; otherwise say "per crawl".
3. **Junk folder wildcards**: one row per folder, Source `https://domain/folder/*`. Notes: "Junk folder wildcard - [what it is, how many]. Disable these archives in the SEO plugin so they do not regenerate".

## QA (run once on the final set, before writing anything to the sheet)

Do every check in code and list only what fails. Rerun only if the redirects change.

Breaking issues first:

- Every Merge/Remove row has a full Suggested Target URL (not a description) that is a live page with a valid-destination suggestion.
- No target is also a source (on the Audit tab or Existing Redirects), and no target matches a wildcard.
- No self-redirects; no wildcard targets matching their own pattern; no specific rule a wildcard would catch first.
- No source appears twice with different targets. An existing no-slash redirect next to its slash version on the Audit tab is the same rule, not a conflict.
- Every existing 3XX that pointed at a page being merged or removed now points at the final page.

Gaps:

- Every live 200 URL in the crawl has an Audit row, or sits in a junk folder covered by a wildcard. Group misses by folder with counts.
- Every archive-type URL (tag, category, author, date, gallery entries, sitemap-only archives) is covered by a wildcard.
- Every Repurpose row says "If the URL changes, update anything redirecting to it", and every redirect pointing at it is listed in the report.

Consistency (report, do not change):

- Two or more pages suggested Keep/Update/Repurpose that target the same treatment or keyword (compare titles, H1s, slugs, top queries).
- Notes that contradict the suggestion.
- The same page type handled with different logic without a stated reason (e.g. one brand folded into a category page while another keeps its own page).
- Every Recommendations Area label is spelled exactly as in rules.md and at least one Audit row will carry it.

## Internal links to update

From the classified links: every page that links to a redirected or 404 URL, as Linking page | Old URL | Final URL, grouped by linking page. Call out Nav and Footer links separately (one template edit fixes them sitewide) and links to case-duplicate URLs. Put this in the report or a separate file; it has no tab in the template.
