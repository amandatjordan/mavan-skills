# Existing redirects and QA

Do all matching in code, on normalized URLs (lowercase, https, non-www, trailing slash, no query or fragment). Only use target URLs that are live pages in the crawl.

A **chain** is A -> B -> C: every redirect goes straight to its final page. A **loop** is A -> B -> A, including a wildcard whose target matches its own pattern. A specific rule listed below a wildcard that also matches it never fires.

Valid final destinations: live pages whose suggestion (or, once a person has decided, Next Steps) is Keep, Update, Repurpose or Needs Discussion. Never suggest a page that is not live in the crawl. A folder-level target (such as a services folder page) matches only slugs that name a service, never other kinds of page.

**Finding a target for a URL that is not a live page.** Exact matches only, in this order:
1. A live page with the same last path segment under another folder (`/treatments/body/hair-restoration-brandon-fl/` -> `/services/hair-restoration-brandon-fl/`). When several match, prefer the one in the folder mapped as Service. If that page is being merged or removed, follow its Suggested Target. Notes start `SUGGESTED - check target`.
2. No exact match: leave Target URL blank and start Notes with `NEEDS TARGET - no live page with the same slug`. Never pick a target by word similarity: a guessed target looks finished and gets copied. The reviewer chooses, and the report gives the count of blank targets.

## Existing Redirects rows

Columns: Source URL | Target URL | Notes (full URLs). They appear at the bottom of the Redirects tab marked Now.

1. **Existing 3XX** from `work/redirects.csv`, which already holds each redirect's `final` page, `hops` and full `chain`. Skip rows with `normalization_only` True (they only add a slash or change case).
   - Lands on a kept page in one hop: leave it off the tab (nothing to change). Lands on one after several hops: add it pointing straight at the final page, Notes `Chain removed (was A -> B -> C)`.
   - Lands on a page being merged or removed: repoint to that page's Suggested Target, following on until a kept page. Notes `Existing redirect - repointed (was X)`.
   - Lands on a 404 or a URL that is not a live page (`final_status` is not 200): find a target as above.
2. **URLs with demand that are not live pages**: every URL in `work/not_in_crawl.tsv`, plus every non-200 URL in the crawl, that has GSC impressions, GA4 sessions or internal links and is not already covered by a redirect. Find a target as above; Notes add `Not a live page per the crawl; [the demand, e.g. 860 impressions for "[treatment] [city]", or "linked from 10 pages"]`. The crawl's status codes are the truth: never confirm with a live request.
3. **Junk folder wildcards**: one row per folder, Source `https://domain/folder/*`. Notes: "Junk folder wildcard - [what it is], [N] pages, [M] impressions. Disable these archives in the SEO plugin so they do not regenerate". Build the string in code from the data (page count and impressions of that folder), write each number once, and never type a count by hand.

## QA (run once on the final set, before writing anything to the sheet)

Do every check in code and list only what fails. Rerun only if the redirects change.

Breaking issues first:

- Every Merge/Remove row has a full Suggested Target URL (not a description) that is a live page with a valid-destination suggestion.
- An Existing Redirects row has a blank Target URL only when its Notes start `NEEDS TARGET`; every other target is a live page with a valid-destination suggestion.
- No target is also a source (on the Audit tab or Existing Redirects), and no target matches a wildcard.
- No self-redirects; no wildcard targets matching their own pattern; no specific rule a wildcard would catch first.
- No source appears twice with different targets. An existing no-slash redirect next to its slash version on the Audit tab is the same rule, not a conflict.
- Every existing 3XX that pointed at a page being merged or removed now points at the final page.

Gaps:

- Every live 200 URL in the crawl has an Audit row, or sits in a junk folder covered by a wildcard. Group misses by folder with counts.
- Every archive-type URL (tag, category, author, date, gallery entries) is covered by a wildcard.
- Every Repurpose row says "If the URL changes, update anything redirecting to it", and every redirect pointing at it is listed in the report.

Consistency (report, do not change):

- Two or more pages suggested Keep/Update/Repurpose that target the same treatment or keyword (compare titles, H1s, slugs, top queries).
- Notes that contradict the suggestion.
- The same page type handled with different logic without a stated reason (e.g. one brand folded into a category page while another keeps its own page).
- Every Recommendations Area label is spelled exactly as in rules.md and at least one Audit row will carry it.

## Internal links to update

From the classified links: every page that links to a redirected or 404 URL, as Linking page | Old URL | Final URL, grouped by linking page. Call out Nav and Footer links separately (one template edit fixes them sitewide) and links to case-duplicate URLs. Put this in the report or a separate file; it has no tab in the template.
