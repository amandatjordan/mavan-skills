# E-E-A-T & YMYL audit workbook

`scripts/audit.py build` builds it. Arial throughout, header row dark blue with white bold text, frozen header, an Excel table (filters) on each data tab, wrapped text. Yellow marks the columns a person fills in. Values, not formulas: every number is computed by the script.

## 1. Recommendations

Preflight warnings (or "None"), then the counts: pages audited, pages scored, external links checked, pages in the accuracy review queue. Then:

- **Issues, most common first** (scored pages): issue, pages affected, % of scored pages, three example pages (the ones with the most failed checks), recommended action (fixed text per issue, in `rules.md` order).
- **By page type:** pages, and how many are High, Medium and Low priority.
- **Trust signals present** across all audited pages: testimonials, before/after photos, rating, credentials, years of experience.
- **External links by flag.**

## 2. Page Review

One row per audited page, in crawl order.

| Column | Content |
| --- | --- |
| URL, Page type, YMYL tier | From the config's page types |
| Author shown, Reviewer shown | Yes or No; n/a when the site has none |
| Credentials found | The credential terms found, or None |
| Years of experience | The matches, or None |
| Published, Last updated, Schema types | The value, or None; n/a when the site has none |
| External citations, Authoritative citations, Authoritative share | Counted links; "No citations" when there are none |
| Flagged external links | Links with a flag other than Check manually |
| Testimonials or reviews, Before/after photos | Yes or No; Not set up when the config has no marker |
| Rating shown on page | The rating text, or No; Not set up |
| Specific claims found | Yes or No from Claude's reading; Not read; n/a on pages that are not High-YMYL |
| Checks failed, Priority, Failed checks | Count, High / Medium / Low (shaded), and the failed checks in words. Low-YMYL pages show Not scored |

## 3. External Links

One row per audited page and destination: source page, anchor text, destination URL, status, destination title, destination H1, domain type, anchor vs destination, flag, and a yellow Reviewer note column.

## 4. Accuracy Review Queue

One row per queued page: URL, page type, why it is in the queue (its failed checks), external citations, specific claims found, claims to verify, cited sources (destination URLs), and yellow Reviewer, Result and Notes columns. Result is for the reviewer: for example Accurate, Inaccurate, Needs expert, Remove claim.

## 5. Chrome Page Check (only when run)

Page type, URL, what the crawl detected, what a visitor sees, agrees with the crawl (Yes / Partly / No), other opportunities.

## QA

`audit.py build` prints PASS or FAIL for each and exits non-zero on a FAIL:
- Every audited page appears once in Page Review.
- External Links has one row per source page and destination.
- The pages' citation counts add up to the External Links rows.
- Low-YMYL pages are not scored, and every scored page has a priority.
- Every queued page is a High-YMYL audited page.
- Flagged counts match the External Links flags.
