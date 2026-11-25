# Crawl setup

What Claude gives the person (from `work/extraction_setup.md`) and what the person does in their crawler. Menu names change between versions, so if one is not where this says, search the crawler's own documentation; preflight (SKILL.md Step 4) checks the result either way.

## 1. The extraction rules (Claude finds the selectors in Claude in Chrome)

Each rule reads one element of the page and becomes a column in the crawl export. Claude tests every selector on the confirmed sample pages before giving it to the person.

| Column name | What it should return |
| --- | --- |
| Body | The text of the main article container only, not the whole page (which would include the menu and footer) |
| Author | The visible author name |
| Reviewer | The visible reviewer or "medically reviewed by" line |
| Published, Updated | The visible dates (or the dates in the page's schema) |
| Schema | The `@type` values in the page's JSON-LD |
| Testimonials, Before After, Rating | Empty (or 0) when the page has none; anything else when it does |

For each rule Claude writes an XPath and a CSS selector, because Screaming Frog accepts either and Sitebulb uses CSS selectors. If an item is not on the site, Claude says "not on this site" and the person adds no rule for it.

## 2. Site crawl and outlinks export

- **Screaming Frog (paid licence):** Configuration > Custom > Extraction. Add one rule per column: pick XPath or CSS Path, paste the selector, and choose "Extract Text" (or "Function Value" for a count). Name the rule with the column name above; the export column is that name with a number added (for example "Body 1"). Turn on JavaScript rendering if the content is added by scripts. Turn on external link checking (Configuration > Spider > Crawl > External Links). Crawl, then export the Internal HTML tab and the All Outlinks export (it includes Link Position).
- **Sitebulb (Pro):** content extraction is a Pro feature. In the audit setup, turn on Content Extraction and use Add Rule for each column: paste the CSS selector, set Extract Data using (text, HTML or attribute) and Type of Data. Sitebulb returns only the **first match** by default: for any rule whose selector matches several elements (Body on pages built from sections, Schema), set the rule's **Operation** to return all matched items. Test each rule on a sample page before saving. Sitebulb writes "Not Found" when a rule finds nothing; the audit treats that as empty.
  External links: turn on **External URL HTTP Status** in the audit setup. It is its own setting, separate from the Search Engine Optimization advanced settings, and it is off by default on new projects (Sitebulb 9.4.3 and later). Sitebulb only status-checks external URLs (it does not crawl them), which is what the audit needs. Without it, Link Explorer shows no external links.
  Export the URL data with the extraction columns plus Status Code and Indexability, and the external links export from Link Explorer (source, destination, anchor text, status code, link position).
- **Page type labels (only when there is no IA or Content Prune & Merge workbook):** add a column named Page Type to the site crawl export, the same file that holds the extraction columns, before sending it. Label every service, blog and condition/concern page (and any other type the person named), using one label per page type consistently (for example Service, Blog, Concern). Leave other pages blank; unlabelled pages are not audited. Do not send the labels as a separate file: the audit reads them from the crawl export. In Screaming Frog, Segments can fill the column during the crawl; otherwise add it in a spreadsheet after exporting.

The outlinks export needs the source page, destination, anchor text and status code, and ideally the link position, so menu and footer links are left out of the citation counts.

## 3. Marker rules (testimonials, before/after, rating)

A marker must be empty or 0 when the page lacks the element. In Screaming Frog, "Function Value" with an XPath such as `count(//section[contains(@class,'testimonials')]//article)` returns 0 or a number. For photos, count the images in the results gallery, not just the section. If a count cannot be written, extract the text of the element and check an obvious page that has it and one that lacks it.

## 4. List crawl of the external destinations

The script writes `work/external_urls.txt`: every external destination once. In the crawler, switch to list mode, upload that file and crawl it. In list mode the listed pages are crawled as the pages themselves, so the export has each one's status code, title and H1. Export that tab (address, status code, title, H1).

- Some sites block crawlers and return 403 or similar. Those are listed for a manual check, not counted as dead links.
- Crawl at the crawler's default speed. A long list can take a while.
