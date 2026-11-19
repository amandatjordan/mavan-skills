# Rules

Everything below is done by `scripts/audit.py`. There is no scoring, tiering or priority: the workbook reports facts.

## Which pages are audited

A crawled page is audited when it returned 200, is indexable (when the export says so) and its URL path matches a page type in the config. Everything else is left out and counted in the preflight warnings (did not return 200, not indexable, no page type).

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

The status is the list crawl's status code for the destination (the outlinks export's status when the list crawl has none).

| Flag | When |
| --- | --- |
| Dead link | Status 400 or higher, except 401, 403, 429 and 999 |
| No response | Status 0 or blank |
| No shared words | The anchor has meaningful words and none appear in the destination's title or H1 |
| Check manually | Status 401, 403, 429 or 999: the site blocked the crawler. Shown, never counted as flagged |

**Flagged external links** counts Dead link, No response and No shared words. Redirects and links to a homepage show their status and URL; they are not flagged.

## Anchor vs destination

Plain word overlap, no judgement. The anchor's words are lower-cased, a trailing "s" is dropped, and stop words and generic words are removed. If nothing is left the anchor is **Generic anchor** and is not compared. Otherwise it is compared with the words of the destination's title and H1: **Match** (every anchor word appears), **Partial** (some do), **No match** (none do, flagged No shared words), or **Not checked** (the destination has no title or H1, for example it was not crawled).

Generic words ignored: click, here, read, more, link, article, source, sources, page, website, site, learn, see, visit, via, official, research, study, studies, shows, show, according, report, info, information. Stop words ignored: a, an, and, or, the, of, in, on, for, to, with, by, at, as, is, are, be, from, vs, near, me, your, you, our, we, it, its, this, that, these, those, into.

This cannot say whether the destination supports the sentence it is linked from. It finds links that obviously do not match. "No shared words" rows need a person's look before a link is changed.

## Accuracy Review Queue

The audited pages, in crawl order, optionally limited to some page types (`--types`) and a number of pages (`--max`), both the person's choice. Claude reads each queued page's body text and writes the specific claims to verify; it never judges whether they are true. A page not read shows "Not read".

## Chrome Page Check

One row per page Claude checked in Claude in Chrome, one page per page type, confirmed by the person. The crawl-detected column is filled by the script from the page's crawl data; the visitor and opportunities columns are Claude's observations (read only). The "agrees" column says whether what a visitor sees matches what the crawl detected: a Partly or No means an extraction rule needs fixing.
