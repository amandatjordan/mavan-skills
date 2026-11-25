# Rules

Everything below is done by `scripts/audit.py`. There is no scoring, tiering or priority: the workbook reports facts.

## Which pages are audited

A crawled page is audited when it returned 200, is indexable (when the export says so) and its page type label (from the IA or Content Prune & Merge workbook, or the crawl's label column) belongs to a page type in the config. Everything else is left out and counted in the preflight warnings (did not return 200, not indexable, no page type).

An extraction (author, reviewer, dates, schema, testimonials, before/after, rating) that is empty on every page of a page type is a **CHECK**, not a finding: the queue and the workbook stop until Claude has checked the selector in Claude in Chrome and either fixed it (new crawl) or recorded it as `Confirmed absent` in `work/checks.tsv` with the pages checked.

## Which external links count

A link counts as a citation when its destination is on a host that is not the client's own, it comes from an audited page, it is a hyperlink (not an image or script), and, when the export has a link position column, its position is one of `content_link_positions`. A page linking to the same destination twice counts once. Links in menus and footers (social profiles and so on) are left out.

## What the page lacks

Listed on each page, and counted by page type on the Recommendations tab:

- No author shown: the author column is empty (skipped when the site has none).
- No medical / expert reviewer: the reviewer column is empty (skipped when the site has none).
- No credentials found: none of the credential terms appear in the body, author or reviewer text.
- No published date: the published column is empty (skipped when the site has none).
- No schema: the schema column is empty (skipped when the site has none).
- No external citations: the page has no counted external link.

Testimonials, before/after photos, rating and years of experience are reported per page and counted by page type, never listed as "lacks".

## External link status and flags

The status is the destination's status code from the external URLs export (the outlinks export's status when that has none).

| Flag | When |
| --- | --- |
| Dead link | Status 400 or higher, except 401, 403, 405, 429 and 999 |
| No response | Status 0 or blank |
| No shared words | The anchor has meaningful words and none appear in the destination's title or H1, or in its URL when there is no title or H1 |
| Check manually | Status 401, 403, 405, 429 or 999: the site blocked the crawler or refused its request method. Shown, never counted as flagged |

**Flagged external links** counts Dead link, No response and No shared words. Redirects and links to a homepage show their status and URL; they are not flagged.

## Anchor vs destination

Plain word overlap, no judgement. The anchor's words are lower-cased, a trailing "s" is dropped, and stop words and generic words are removed. If nothing is left the anchor is **Generic anchor** and is not compared. Otherwise it is compared with the words of the destination's title and H1 when the export has them. When it has neither (Sitebulb only status-checks external URLs), it is compared with the words in the destination's host and path, leaving out the query string, numbers and URL noise (http, www, com, org, gov, html, php, index and similar); the External Links tab says which was used. **Match** (every anchor word appears), **Partial** (some do), **No match** (none do, flagged No shared words). Words with digits (ids) are dropped. When the path has no words left (pubmed.ncbi.nlm.nih.gov/18462427, a homepage with a tracking query), the link is **Not checked**: the URL names the source, not the topic. A URL comparison is rougher than a title, so "No shared words" rows need a person's look.

## Schema types

When the schema extraction holds the JSON-LD itself (Sitebulb extracts the script tags), the Page Review shows only the `@type` names, in order, once each, leaving out nested ListItem, Question, Answer, EntryPoint and SearchAction. A sitewide Organization block on every page means "No schema" is rarely hit; read the types to see which pages have page-level schema.

Generic words ignored: click, here, read, more, link, article, source, sources, page, website, site, learn, see, visit, via, official, research, study, studies, shows, show, according, report, info, information. Stop words ignored: a, an, and, or, the, of, in, on, for, to, with, by, at, as, is, are, be, from, vs, near, me, your, you, our, we, it, its, this, that, these, those, into.

This cannot say whether the destination supports the sentence it is linked from. It finds links that obviously do not match. "No shared words" rows need a person's look before a link is changed.

## Accuracy Review Queue

The audited pages, in crawl order, optionally limited to some page types (`--types`) and a number of pages (`--max`), both the person's choice. Claude reads each queued page's body text and writes the specific claims to verify; it never judges whether they are true. A page not read shows "Not read".

## Chrome Page Check

One row per page Claude checked in Claude in Chrome, one page per page type, confirmed by the person. The crawl-detected column is filled by the script from the page's crawl data; the visitor and opportunities columns are Claude's observations (read only). The "agrees" column says whether what a visitor sees matches what the crawl detected: a Partly or No means an extraction rule needs fixing.
