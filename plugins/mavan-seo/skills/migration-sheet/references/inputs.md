# Inputs: which export, which tool, what is read

All inputs are uploaded files. Nothing is fetched.

| Input | Where it comes from | What is read |
| --- | --- | --- |
| URL export (old site) | Sitebulb: URL Explorer > Internal > HTML. Screaming Frog: Internal > HTML. Crawl with the XML sitemap as a source so unlinked pages are included | URL (or Address), HTTP status code, Title, H1, Redirect URL when present. Every URL, not only 200s |
| Internal links export | Sitebulb: Links > Internal Links (Linking URL, Target URL, Anchor Text, Location, CSS Path). Screaming Frog: Bulk Export > Links > All Inlinks (Source, Destination, Anchor, Link Position, Link Path, Type) | Source page, target page, the CSS path or link path (used to class Nav / Footer / Breadcrumb / Body) |
| Redirects export (optional) | Sitebulb Redirects report. Screaming Frog Reports > Redirects > All Redirects | Redirects already on the old site; each carries over unless an audit decided that URL |
| Backlink export | Ahrefs or Semrush backlinks export for the client domain | Target URL column only (UTF-8 or UTF-16, comma, tab or semicolon). URLs with backlinks, including media files, are counted from it |
| Search Console sheet | Mavan's Search Console template, tab "Claude Use This" (Page, Query, Clicks, Impressions) | Page and Impressions: old URLs that get impressions but are not live |
| Content Prune & Merge workbook | The SEO's working copy (has Kept pages and Check page type), .xlsx | See below |
| IA audit workbook | The SEO's working copy (has README and Check page type), .xlsx | See below |
| Service Gap workbook | Med spa and plastic surgery sites only, .xlsx | Recommendations: rows whose Next Steps is "Create new page" |

Not required: the crawl's images and documents lists. They are accepted but nothing is read from them; media comes from the backlink export.

## Audit workbook tabs read (matched by exact name; headers in row 2 under a banner row, the dev tab headers in row 1)

**Content Prune & Merge:** Kept pages (page type; the Disagree? column must be empty), Check page type (a Correct page type still "SEO fill in" blocks), Needs discussion (the answer in column B must be recorded), Merge pages and Redirect after merge (source, surviving page, unique content), Remove pages and Redirects needing a target (source, target; type Gone for no redirect), Per location service pages (Merge or Keep), Junk folders (wildcard rules), All redirects - Handoff to Dev (wildcard rows with Regex = 1 only), Update pages (new title and H1 when filled in).

**IA audit:** Moves (old URL, new URL), Check page type (page types), Fix links (a new URL still "SEO fill in" blocks), Menu cleanup (Keep or Remove must be filled; reference only, the SEO sets the navigation), README.

**Service Gap:** Recommendations (Service Page Recommended, Current URL, Next Steps, Relevant Keywords).

A tab an audit left out (it had no rows) is skipped. The implementer copies (without Kept pages and Check page type, or without README and Check page type) are refused: they cannot show what the SEO approved.
