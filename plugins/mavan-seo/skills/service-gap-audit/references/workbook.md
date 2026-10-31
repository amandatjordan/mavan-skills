# Service Gap Audit workbook

`scripts/build.py build` writes this workbook; this file is the spec it follows and what to check it against. Arial throughout, dark blue header row with white bold text, frozen header, Excel table (filters) on every data tab, `#,##0` on volumes and word counts. Yellow marks columns a person fills in.

## Tabs, in this order

### 1. Read Me
Inputs (crawl file, URL counts, taxonomy version, Search Console used or not and why), Fields used (and missing columns, e.g. no H2s), Practice type and service-area cities, Level names, Page types, Offered Status, Priority, Competitor Volume, Limits, Thresholds, Search volume, Not in taxonomy (NEW nodes with their pages), Yellow columns.

### 2. Recommendations (the deliverable)
Row 1 header groups: **Page** over A–D, **Search Volume** over E onward. Row 2 headers:

| Column | Content |
| --- | --- |
| Service Page Recommended | Service name; Sub-Service or Brand / Device with its parent, e.g. "Lip Filler (Dermal Filler)", "Botox (Neurotoxin)" |
| Current URL | The row's own existing page, blank for a new page |
| Existing Brand / Sub-Service Page(s) | Only on "Only has a brand/product page" and "Only has Sub-Service pages" rows: "Node: path; Node: path" |
| Why Recommended | One label below |
| Relevant Keywords | One cell, comma-separated, highest volume first, or "None in competitor keyword list (check GSC / keyword tool)" |
| Total National Search Volume | Sum of those keywords |
| Client GSC Impressions | Only when a Search Console sheet was used |

Rows: every gap at Service or Sub-Service level, plus Brand / Device rows whose gap is Indexability blocker, Empty / thin page or Light page. **Why Recommended**, in this sort order (then by Total National Search Volume, highest first):

1. Existing page, not indexable
2. Existing page, thin content
3. Offered (before & after photos), no page
4. Offered (named on a concern page), no page
5. Likely offered (mentioned on site), no page
6. Only has a brand/product page
7. Only has Sub-Service pages
8. Only covered in blog posts
9. Existing page, light content
10. Confirm with client (parent Service offered)
11. Confirm with client (no sign it is offered)

### 3. Keyword Map
Service Page Recommended, Current URL, Keyword, National Search Volume. One row per keyword.

### 4. Excluded Keywords
Keyword, National Search Volume, Service Page Recommended, Exclusion Reason ("Other market (Geo Modified: place)"), Keep? (Y to add back) in yellow.

### 5. Gap List
Priority (P1 red, P2 yellow, P3 green, Ask blue), Gap Type, Category, Service, Level, Service / Sub-Service / Brand, Offered Status, Offered Evidence, Coverage, Best Page, Content Words, Indexability, All Pages for Node, Competitor Volume, Volume Tier, Recommendation (page brief for empty Service pages), Client Confirmed (yellow, Yes / No / Planned), Notes (yellow).

### 6. Page Inventory
Every live page except galleries: Path, Page Type, Primary Level, Primary Service, Primary Service / Sub-Service / Brand, City, Content Words, Indexability, H1 Missing, Duplicate Of, Page Issues (not indexable; thin or light with word count; missing H1; thin copy of another page for the same node), Title, H1, H2, H2 (second), Meta Description.

### 7. Service Coverage
Every in-scope node: Category, Service, Level, Service / Sub-Service / Brand, Offered Status, Coverage, Best Page, Content Words, Indexability, Competitor Volume, Gap Type, Status Note.

### 8. Gallery Evidence
Slug (trailing number stripped), Gallery Pages, Maps To (Service > node, or "Package name? Ask client").

## Checks the script runs (all must PASS)

- Every Why Recommended value is one of the labels.
- Total National Search Volume equals the row's Keyword Map rows.
- Brand-only rows name their existing page(s), all under the row's Service.
- No gap on a node marked Do not flag / NOT US-approved.
- Every Service page has a node.
- Brand / Device and Sub-Service rows are named with their parent.

Your own checks are SKILL.md Step 5.
