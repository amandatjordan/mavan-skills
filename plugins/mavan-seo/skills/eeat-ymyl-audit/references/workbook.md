# E-E-A-T & YMYL audit workbook

`scripts/audit.py build` builds it. Arial throughout, header row dark blue with white bold text, frozen header, an Excel table (filters) on each data tab, wrapped text. **Yellow marks the columns the SEO fills in**; columns with fixed choices have a dropdown. Values, not formulas: every number is computed by the script. Six tabs, in this order. It is built only after the person has confirmed the sample pages and every CHECK is closed.

## 1. Recommendations

What the SEO works from. No raw counts table: every line is a finding.

- **Issues found, by priority:** one row per requirement and page type that has pages missing it, plus one row for the claims and one for external link issues. Columns: Priority (High / Medium / Low), Issue (a rollup sentence such as "52 of 56 service pages have no external link to a medical journal, .gov, .edu, .org or reputable medical site." or "Across the board, blog posts do not show an author (34 of 34)."), Pages / items, Where to look (the tab), Next steps (SEO / Dev / Content), Completion handoff (Dev or Content), and a yellow Status dropdown (Not started / In progress / Done). Sorted High first. Priorities, next steps and handoffs come from `rules.md`.
- **Manual checks for the SEO:** the work only a person can do, with the tab and the number of items: choose a source and anchor per page (External Links Needed), decide each link with an issue (External Link Issues), verify each claim (Claims Needing Verification), confirm the reviewer and credentials with the client.
- **Ownership:** the issues grouped by handoff, Dev and Content.
- **Crawl notes:** the preflight warnings, and each empty extraction that was confirmed absent in Claude in Chrome.

## 2. All Pages

Reference sheet: one row per audited page, in crawl order. URL, page type, then one column per requirement in `rules.md` (Yes / Missing / Not required for this page type / Not checked when the crawl has no column for it), then FAQ section, schema types, credentials found, years of experience, external links, credible external links, external links with an issue.

## 3. External Links Needed (Dev handoff)

One row per page with no credible external source: URL, page type, the external links on the page now (none of them credible), the claims found on the page (to help choose a source), yellow **Source to link to**, yellow **Anchor text on the page** (existing text on the page to link from), yellow Notes, Completion handoff (Dev).

## 4. External Link Issues (Dev handoff)

One row per external link with any issue (Dead link, No response, Check manually, No shared words): source page, anchor text, destination URL, status, issue, what the anchor was compared with (Title and H1, or URL), whether the destination is a credible source, yellow **Action** dropdown (Keep / Replace / Remove), yellow **Replacement URL**, yellow **New anchor text**, yellow Notes, Completion handoff (Dev).

## 5. Claims Needing Verification (Content handoff)

One row per claim, in the page's own words: URL, page type, claim, the credible sources the page cites now, yellow **Source to cite** (the SEO adds a real source for the claim), yellow **Claim status** dropdown (Accurate claim / Bad claim), yellow **Claim update** (the corrected wording to use on the site), Completion handoff (Content). A page Claude did not read has one row with "Not read".

## 6. Sample Page Check

One row per sample page: page type, URL, what the crawl detected (each requirement), what a visitor sees, whether the person agrees with the crawl (always Yes: the build stops otherwise), other opportunities.

## QA

`audit.py build` prints PASS or FAIL for each and exits non-zero on a FAIL:
- Every audited page appears once in All Pages.
- External Links Needed lists exactly the pages whose credible source check is Missing.
- External Link Issues lists every flagged link once.
- Claims Needing Verification has one row per claim.
- The Recommendations counts add up to the Missing cells in All Pages.
- Every page type has a sample page the person checked and agreed with.
