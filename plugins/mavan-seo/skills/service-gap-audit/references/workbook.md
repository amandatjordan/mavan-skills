# Service Gap Audit workbook

Arial throughout, header row dark blue with white bold text, frozen header, Excel table (filters) on every data tab, wrapped text in long columns, `#,##0` on volumes and word counts. Yellow fill marks columns a person fills in.

## Tabs, in this order

### 1. Read Me
Two columns (label, text): Inputs (crawler, URL count, crawl date, taxonomy version, GSC yes/no), Fields used, Practice type and service area, Level names, Offered Status definitions, Coverage definitions, Priority definitions, Competitor Volume (ranks gaps against each other; not local demand), Limits of export-only (no body text: a Sub-Service mentioned only in body copy shows as not found), Thresholds, Recommendations tab, Search volume (how keywords are assigned and which are excluded), Yellow columns.

### 2. Recommendations (the deliverable)
Row 1 header groups: **Page** over columns A–D, **Search Volume** over E–F. Row 2 column headers:

| Column | Content |
| --- | --- |
| Service Page Recommended | Service name; Sub-Service or Brand / Device with its parent, e.g. "Lip Filler (Dermal Filler)", "Botox (Neurotoxin)" |
| Current URL | Path of the existing page for this row, blank for a new page |
| Existing Brand / Sub-Service Page(s) | Only for "Only has a brand/product page" and "Only has Sub-Service pages" rows: every page under this Service as "Node: path", separated by "; " (e.g. "SkinPen: /services/skinpen-microneedling-canandaigua-ny"). Blank on every other row |
| Why Recommended | One label from the list below |
| Relevant Keywords | One cell, comma-separated, highest volume first |
| Total National Search Volume | Sum of those keywords |

Rows: every gap at Service or Sub-Service level, plus Brand / Device rows whose gap is Indexability blocker, Empty / thin page or Light page.

**Why Recommended** labels, in this sort order (then by Total National Search Volume, highest first):
1. Existing page, not indexable (use this label and that URL whenever the node has a non-indexable page with >= 300 words, even if a thin indexable duplicate exists)
2. Existing page, thin content
3. Offered (before & after photos), no page
4. Likely offered (mentioned on site), no page
5. Only has a brand/product page
6. Only has Sub-Service pages
7. Only covered in blog posts
8. Existing page, light content
9. Confirm with client (parent Service offered)
10. Confirm with client (no sign it is offered)

### 3. Keyword Map
Service Page Recommended, Current URL, Keyword, National Search Volume. One row per keyword.

### 4. Excluded Keywords
Keyword, National Search Volume, Service Page Recommended, Exclusion Reason, Keep? (Y to add back) in yellow. Only keywords that would have counted for a Recommendations row. Sort Geo Modified rows first.

### 5. Gap List
Priority (P1 red fill, P2 yellow, P3 green, Ask blue), Gap Type, Category, Service, Level, Service / Sub-Service / Brand, Offered Status, Offered Evidence, Coverage, Best Page, Content Words, Indexability, All Pages for Node ("path (Nw, indexability)"; ...), Competitor Volume, Volume Tier (High / Medium / Low / No data), Recommendation (page brief for empty Service hubs), Client Confirmed (yellow, Yes / No / Planned dropdown), Notes (yellow). Sorted by Priority, Gap Type, Competitor Volume.

### 6. Page Inventory
Path, Page Type, Primary Level, Primary Service, Primary Service / Sub-Service / Brand, Content Words, Indexability, H1 Missing, Duplicate Of, Page Issues (not indexable; empty / thin or light with word count; missing H1), Title, H1, H2, H2 (second), Meta Description. Service pages first, then Location, Blog post, Blog index, Utility. Galleries are on their own tab.

### 7. Service Coverage
Every in-scope node: Category, Service, Level, Service / Sub-Service / Brand, Offered Status, Coverage, Best Page, Content Words, Indexability, Competitor Volume, Gap Type, Status Note.

### 8. Gallery Evidence
Slug (trailing number stripped), Gallery Pages (count), Maps To (Service > Sub-Service, or "Package name? Ask client").

## QA

Every check passes before the workbook goes to the person:
- 5 Recommendations rows opened against Page Inventory: label, URL and word count agree.
- No Brand / Device page is named as its parent Service, and every Service page with a brand in its title is labeled with that brand.
- The top 10 Recommendations rows' Relevant Keywords contain no other city and no keyword from a different service. A wrong-service keyword means a match term is too broad: tighten it in your working copy, re-run, and list it for the taxonomy pull request.
- Every Why Recommended value is one of the ten labels.
- Totals in Total National Search Volume equal the sum of that row's Keyword Map rows.
- Every "Only has a brand/product page" and "Only has Sub-Service pages" row names at least one page in Existing Brand / Sub-Service Page(s), and that page's primary node in Page Inventory belongs to the row's Service.
