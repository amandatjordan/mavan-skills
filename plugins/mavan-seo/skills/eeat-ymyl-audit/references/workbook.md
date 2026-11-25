# E-E-A-T & YMYL audit workbook

`scripts/audit.py build` builds it. Arial throughout, header row dark blue with white bold text, frozen header, an Excel table (filters) on each data tab, wrapped text. Yellow marks the columns a person fills in. Values, not formulas: every number is computed by the script. Five tabs, in this order.

## 1. Recommendations

Preflight warnings (or "None"), then the counts: pages audited, external links checked, pages in the accuracy review queue. Then:

- **What pages lack, by page type:** pages, and how many have no author, no reviewer, no credentials found, no published date, no schema, no external citations, flagged links, no testimonials, no before/after photos, no rating. n/a means the site does not have that element.
- **External links by flag.**

## 2. Page Review

One row per audited page, in crawl order.

| Column | Content |
| --- | --- |
| URL, Page type | From the config's page types |
| Author shown, Reviewer shown | Yes or No; n/a when the site has none |
| Credentials found | The credential terms found, or None |
| Years of experience | The matches, or None |
| Published, Last updated, Schema types | The value, or None; n/a when the site has none |
| External citations | Counted external links |
| Flagged external links | Links flagged Dead link, No response or No shared words |
| Testimonials or reviews, Before/after photos | Yes or No; Not set up when there is no marker |
| Rating shown on page | The rating text, or No; Not set up |
| Specific claims found | Yes or No from Claude's reading; Not read |
| What the page lacks | The missing items in words |

## 3. External Links

One row per audited page and destination: source page, anchor text, destination URL, status, destination title, destination H1 (empty when the crawler only status-checks external URLs), what the anchor was compared with (Title and H1, or URL), anchor vs destination, flag, and a yellow Reviewer note column.

## 4. Accuracy Review Queue

One row per queued page: URL, page type, what the page lacks, external citations, specific claims found, claims to verify, cited sources (destination URLs), and yellow Reviewer, Result and Notes columns. Result is for the reviewer: for example Accurate, Inaccurate, Needs expert, Remove claim.

## 5. Chrome Page Check

One row per sample page: page type, URL, what the crawl detected, what a visitor sees, agrees with the crawl (Yes / Partly / No), other opportunities.

## QA

`audit.py build` prints PASS or FAIL for each and exits non-zero on a FAIL:
- Every audited page appears once in Page Review.
- External Links has one row per source page and destination.
- The pages' citation counts add up to the External Links rows.
- Flagged counts match the External Links flags.
- The accuracy queue has one row per queued page.
- Every page type has a Claude in Chrome check.
