# Rules

Everything below is done by `scripts/audit.py`. Nothing here is assumed about a site: every list and cut-off is in the person's config.

## Which pages are audited

A crawled page is audited when it returned 200, is indexable (when the export says so) and its URL path matches a page type in the config. Everything else is left out and counted in the preflight warnings (did not return 200, not indexable, no page type). Pages in a Low-YMYL type are audited and listed but not scored.

## Which external links count

A link counts as a citation when its destination is on a host that is not the client's own, it comes from an audited page, it is a hyperlink (not an image or script), and, when the export has a link position column, its position is one of `content_link_positions`. A page linking to the same destination twice counts once. Links in menus and footers (social profiles and so on) are left out.

## Checks per page (scored pages only)

A page fails a check when:

- **No author shown:** the author column is empty (skipped when the site has none).
- **No medical / expert reviewer:** the reviewer column is empty (skipped when the site has none).
- **No credentials found:** none of the credential terms appear in the body, author or reviewer text.
- **No published date:** the published column is empty (skipped when the site has none).
- **No external citations:** the page has no counted external link.
- **Flagged external links:** at least one of its links has a flag in the list below.
- **No schema:** the schema column is empty (skipped when the site has none).

Trust signals (testimonials, before/after photos, rating, years of experience) are reported but never count as a failed check.

## Priority

Checks failed: High at 4 or more, Medium at 2 or 3, Low below that. These defaults come from the example Mavan reviewed; they are set in the config (`priority_cutoffs`) and change only if the person asks. Low-YMYL pages show "Not scored".

## External link status and flags

The status is the list crawl's status code for the destination (the outlinks export's status when the list crawl has none).

| Flag | When |
| --- | --- |
| Dead link | Status 400 or higher, except 401, 403, 429 and 999 |
| No response | Status 0 or blank |
| Redirect | Status 300 to 399 |
| Goes to homepage | The destination is the site's root with no query |
| No shared words | The anchor has meaningful words and none appear in the destination's title or H1 |
| Weak source | The host is in `weak_domains` |
| Check manually | Status 401, 403, 429 or 999: the site blocked the crawler. Shown, never counted as flagged |

**Flagged external links** counts every flag except Check manually.

## Anchor vs destination

Plain word overlap, no judgement. The anchor's words are lower-cased, a trailing "s" is dropped, and stop words and generic words are removed. If nothing is left the anchor is **Generic anchor** and is not compared. Otherwise it is compared with the words of the destination's title and H1: **Match** (every anchor word appears), **Partial** (some do), **No match** (none do, flagged No shared words), or **Not checked** (the destination has no title or H1, for example it was not crawled).

Generic words ignored: click, here, read, more, link, article, source, sources, page, website, site, learn, see, visit, via, official, research, study, studies, shows, show, according, report, info, information (plus the config's `generic_anchor_words`). Stop words ignored: a, an, and, or, the, of, in, on, for, to, with, by, at, as, is, are, be, from, vs, near, me, your, you, our, we, it, its, this, that, these, those, into.

This cannot say whether the destination supports the sentence it is linked from. It finds links that obviously do not match. "No shared words" rows need a person's look before a link is changed.

## Domain type

Authoritative (matches the config's rules), Weak source (matches `weak_domains`) or Other. Authoritative share = authoritative citations divided by all citations on the page.

## Accuracy Review Queue

High-YMYL pages. Scope **failed** (default): pages that failed at least one check. Scope **all-high**: every High-YMYL page. Ordered by checks failed, most first. Claude reads each queued page's body text and writes the specific claims to verify; it never judges whether they are true. A page not read shows "Not read".

## Chrome Page Check

Added only when the person chose it. One page per page type. When Claude chooses, the proposed page is the one whose body word count is closest to its type's median, and the person confirms it. The crawl-detected column is filled by the script from the page's row; the visitor and opportunities columns are Claude's observations from Claude in Chrome, read only.
