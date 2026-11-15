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

## Retained internal links

For each page that stays and each merged page, the retained links are its **body** links (menus, footers and breadcrumbs are rebuilt by the template and the Final menu and nav tab). Each target is mapped to its final URL, so a link to a merged or moved page points to where that page ends up. A link that would point to the page itself is dropped; a link to a Gone page is dropped.

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
8. Every new page has a URL and the internal links it must include.
9. Final menu and nav: every URL is a page that stays or a new page (not merged, redirected or Gone), and every child has a parent. The tab must not be empty.

Checks 7 to 9 are OPEN in pass 1 (the SEO has not filled them in yet) and FAIL in pass 2.

## Tabs

| Tab | Contents |
| --- | --- |
| Summary | Counts per decision, the check results, every discrepancy, the internal link cutoff |
| Pages to keep | Final URL, old URL when it moves, page type, title and H1 at migration (Update pages' new ones when filled in, otherwise the crawl's), internal links to retain, backlinks, pages linking in |
| Final menu and nav | The SEO fills in: parent label, parent URL, child label, child URL, order. Always parent and child levels |
| Pages to merge | Page that goes away, surviving URL, unique content to copy, body links to carry over |
| Pages to redirect | Old URL, target (or Gone), HTTP code, reason for Gone, backlinks, which audit decided it. Merge and wildcard redirects are included |
| Media with backlinks | Media URL, backlinks, SEO decision, new URL |
| New pages | Page to create (Service Gap rows set to Create new page), URL and internal links to include (SEO fills in), keywords |
| Redirects - Handoff to Dev (pass 2) | Source URL, Target URL, Regex (0 or 1), HTTP Code. Headers in row 1 so it downloads as a CSV |
| README | SEO only: how to use, files and tabs read, thresholds, what was not checked |

Excel does not allow "/" in a tab name, so the navigation tab is called **Final menu and nav**.
