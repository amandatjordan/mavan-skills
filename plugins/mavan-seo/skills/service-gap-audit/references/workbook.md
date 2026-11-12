# Service Gap Audit workbook

`scripts/build.py build` writes this workbook; this file is the spec it follows and what to check it against. Arial throughout, dark blue header row with white bold text, frozen header, Excel table (filters) on every data tab, `#,##0` on volumes and word counts. Yellow marks columns a person fills in.

## Tabs, in this order

### 1. Read Me
Inputs (crawl file, URL counts, taxonomy version, Search Console used or not and why), Fields used (and missing columns, e.g. no H2s), Practice type and service-area cities, Level names, Page types, Offered Status, Priority, Competitor Volume, Limits, Thresholds, Search volume, Not in taxonomy (NEW nodes with their pages), Yellow columns.

### 2. Recommendations (the deliverable)
Row 1 header groups: **Page** over A–F, **Search Volume** over G onward. Row 2 headers:

| Column | Content |
| --- | --- |
| Service Page Recommended | Service name; Sub-Service or Brand / Device with its parent, e.g. "Lip Filler (Dermal Filler)", "Botox (Neurotoxin)" |
| Current URL | The row's own existing page, blank for a new page |
| Next Steps | Yellow, blank, dropdown for the SEO to fill in: Create new page, Update page, Fix indexability, Add section to existing page, Merge / redirect, Ignore |
| Existing Brand / Sub-Service Page(s) | Only on "Only has a brand/product page" and "Only has Sub-Service pages" rows: "Node: path; Node: path" |
| Why Recommended | One label below |
| Relevant Pages | Existing pages the service is named on, as paths, "; " separated: concern pages, H2 sections, before & after galleries, meta descriptions and blog posts. Blank when nothing names it. Never the row's own Current URL |
| Relevant Keywords | One cell, comma-separated, highest volume first, at most 20 (the Keyword Map has the full list), or "None in competitor keyword list (check GSC / keyword tool)" |
| Total National Search Volume | Sum of those keywords |
| Client GSC Impressions | Only when a Search Console sheet was used |

Rows: every gap at Service or Sub-Service level, plus Brand / Device rows whose gap is Indexability blocker. An existing page appears only when it is not indexable; a service with no sign on the site never appears. **Why Recommended**, in this sort order (then by Total National Search Volume, highest first):

1. Existing page, not indexable
2. Offered (before & after photos), no page
3. Offered (named on a concern page), no page
4. Likely offered (mentioned on site), no page
5. Only has a brand/product page
6. Only has Sub-Service pages
7. Only covered in blog posts
8. Confirm with client (parent Service offered)

### 3. Keyword Map
Service Page Recommended, Current URL, Keyword, National Search Volume. One row per keyword.

### 4. Excluded Keywords
Keyword, National Search Volume, Service Page Recommended, Exclusion Reason ("Other market (Geo Modified: place)"), Keep? (Y to add back) in yellow.

### 5. Gap List
Priority (P1 red, P2 yellow, P3 green), Gap Type, Category, Service, Level, Service / Sub-Service / Brand, Offered Status, Offered Evidence, Coverage, Best Page, Content Words, Indexability, All Pages for Node, Competitor Volume, Volume Tier, Recommendation, Client Confirmed (yellow, Yes / No / Planned), Notes (yellow).

### 6. Page Inventory
Every live page except galleries: Path, Page Type, Primary Level, Primary Service, Primary Service / Sub-Service / Brand, City, Content Words, Indexability, H1 Missing, Duplicate Of, Page Issues (not indexable; thin or light with word count; missing H1; thin copy of another page for the same node), Title, H1, H2, H2 (second), Meta Description.

### 7. Service Coverage
Every in-scope node: Category, Service, Level, Service / Sub-Service / Brand, Offered Status, Coverage, Best Page, Content Words, Indexability, Competitor Volume, Gap Type, Status Note.

### 8. Gallery Evidence
Slug (trailing number stripped), Gallery Pages, Maps To (Service > node, or "Package name? Ask client").

## Checks the script runs (all must PASS)

- Every Why Recommended value is one of the labels.
- Existing pages appear only when not indexable.
- No row recommends a service with no sign on the site.
- Total National Search Volume equals the row's Keyword Map rows.
- Brand-only rows name their existing page(s), all under the row's Service.
- No gap on a node marked Do not flag / NOT US-approved.
- Every Service page has a node.
- Brand / Device and Sub-Service rows are named with their parent.

Your own checks are SKILL.md Step 5.
