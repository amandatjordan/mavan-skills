# Rules, checks and tab contents

## Who decides what

| Question | Who decides |
| --- | --- |
| Does this page stay, get merged, or get removed? | Content Prune |
| Which URL does a page that stays end up at? | IA audit (it sets the URL structure) |

Decision order for each old URL: Content Prune's action, then the IA move for a page that stays, then keep at the same URL.

The audits already cross-check each other. The skill is a safety net for what slips through or what the SEO's changes introduce. **Option A:** the skill applies the fix and lists every discrepancy on the Summary tab (what the audits said, what the skill did, where each came from):
- A redirect whose target is itself moving, merged or redirected points to the final URL in one hop. Existing site redirects are repointed the same way. Example: prune merges `/botox-tips/` into `/botox/`, the IA audit moves `/botox/` to `/services/botox/`, so `/botox-tips/` redirects to `/services/botox/`.
- An IA move on a page prune removes or merges is dropped; the prune decision stands.

To change an outcome, the SEO edits the audit workbook and re-runs.

## Removing a URL

404 or 410 is allowed. In the audit workbook the SEO types **Gone** (or **Gone 410**) as the target. On the migration sheet the row shows the code and no target, and the SEO writes the **reason** in the orange cell; pass 2 fails without it.

## Media with backlinks

Only media files with backlinks in the backlink export are handled; all other media is ignored. Nobody can know whether the new site keeps a file at the same URL, so each file gets a row on its own tab and **the SEO decides**: Keep at the same URL, or Redirect with the new URL filled in. Redirects chosen there go to the developer list in pass 2.

## Wildcard rules

A Junk folders rule is counted once as a rule, not once per URL. The developer list gets one row with Regex = 1. A page that stays inside a wildcard rule, or a target that matches one, is a failure.

## Internal links

Every internal link on a page that stays is kept, so the sheet does not list them. Menus, footers and breadcrumbs are rebuilt from the Final menu and nav tab.

New pages: up to 3 existing pages that should link TO the new page are suggested from the Service Gap data (the existing related pages first, then the pages that name the service), each shown at its final URL. Pages that are removed or not on the new site are skipped. The SEO changes or adds pages and fills in the anchor text each one uses.

## Internal link cutoff

Bottom quartile of pages linking in, per page type (a type needs 4 pages). The cutoff used is on the Summary tab, for the staging check.

## Script checks (all must pass before client approval)

1. Every old URL has exactly one decision (keep, merge, redirect or Gone). Old URLs are the live pages in the crawl, the redirects already on the site, and every URL with backlinks or Search Console impressions. A URL nobody decided is left on Pages to redirect for the SEO.
2. No blank redirect target.
3. Every Gone URL has a reason and a 404 or 410 code.
4. No redirect chains or loops, no redirect to itself, no source listed twice, no two pages ending at the same URL.
5. Every redirect target is a page that stays or a new page.
6. No kept page and no target sits inside a wildcard rule.
7. Every media file with backlinks has an SEO decision, and every one set to redirect has a new URL.
8. Every new page has a URL and at least one page linking to it with anchor text (every listed page has anchor text), and those pages are on the new site.
9. Final menu and nav: every URL is a page that stays or a new page (not merged, redirected or Gone), and every child has a parent. The tab must not be empty.

Checks 7 to 9 are OPEN in pass 1 (the SEO has not filled them in yet) and FAIL in pass 2.

## Tabs

| Tab | Contents |
| --- | --- |
| Summary | Counts per decision, the check results, every discrepancy, the internal link cutoff |
| All pages | Every page on the new site: final URL, old URL when it moves, origin (Stays, Moved, New page), page type, title and H1 at migration (Update pages' new ones when filled in, otherwise the crawl's), notes. Merged pages are not listed. **The SEO reviews and updates page type, title and H1** (light orange columns); the edits are read back in pass 2, matched by final URL (new pages by their Service Gap note) |
| Final menu and nav | The SEO fills in: parent label, parent URL, child label, child URL, order. Always parent and child levels |
| Pages to merge | Page that goes away, surviving URL, unique content to copy over. Its redirect is on Pages to redirect and in the dev list |
| Pages to redirect | Old URL, target (or Gone), HTTP code, reason for Gone, which audit decided it. Merge and wildcard redirects are included |
| Media with backlinks | Media URL, backlinks, SEO decision, new URL |
| New pages | Page to create (Service Gap rows set to Create new page), URL (SEO fills in), keywords, up to 3 suggested pages that link to it, with the anchor text (SEO fills in the anchor text) |
| README | SEO only: how to use, files and tabs read, thresholds, what was not checked |

The developer redirect list is not a tab: pass 2 writes it as a separate CSV (Source URL, Target URL, Regex 0 or 1, HTTP Code; headers in row 1), the only copy. It holds every 301 redirect, every Gone row with its 404 or 410 code, one row per wildcard rule with Regex = 1, and media files the SEO set to redirect.

Excel does not allow "/" in a tab name, so the navigation tab is called **Final menu and nav**.
