# Crawl setup

What the person sets up in their crawler. Menu names change between versions, so if one is not where this says, search the crawler's own documentation; preflight (SKILL.md Step 2) checks the result either way.

## 1. Site crawl with extraction

Goal: one export of every internal HTML page, with a column for each of the items below. Each is an extraction rule that reads one element of the page. The selector (CSS or XPath) is different on every site: open a sample page, inspect the element and copy its selector, then check the result on that sample.

| Column | What to extract |
| --- | --- |
| Body | The text of the main article container only (not the whole page, which would include the menu and footer) |
| Author | The visible author name |
| Reviewer | The visible reviewer or "medically reviewed by" line |
| Published / Updated | The visible dates (or the dates in the page's schema) |
| Schema types | The `@type` values in the page's JSON-LD |
| Testimonials, Before/after, Rating | Something that is empty when the page has none: a selector for the section, or a count of matching elements. A value of 0, no or false counts as none |

- **Screaming Frog (paid licence):** Configuration > Custom > Extraction. Choose XPath or CSS Path, and "Extract Text" for body text and names. Turn on JavaScript rendering if the content is added by scripts. Each rule becomes a column named after the rule, with a number added (for example "Body 1"); put that exact name in the config. Export the Internal HTML tab.
- **Sitebulb (Pro):** content extraction is a Pro feature. In the audit setup, open Content Extraction, add a rule per column with a CSS selector and the type of data to return, and run it on every page. Export the page data with the extraction columns.

Turn on external link checking in the crawler's settings (Screaming Frog: Configuration > Spider > Crawl > External Links) so the outlinks export has external destinations and their status codes.

## 2. Outlinks export

The crawler's export of every link: source page, destination, anchor text and status code. Include the link position column if the crawler has one (Screaming Frog's All Outlinks export has Link Position), so menu and footer links can be left out of the citation counts.

## 3. List crawl of the external destinations

The skill writes `work/external_urls.txt`: every external destination once. In the crawler, switch to list mode, upload that file and crawl it. In list mode the listed pages are crawled as the pages themselves, so the export has each one's status code, title and H1. Export that tab (address, status code, title, H1).

- Some sites block crawlers and return 403 or similar. Those are listed for a manual check, not counted as dead links.
- Crawl politely: keep the crawler's default speed settings. A long list can take a while.
