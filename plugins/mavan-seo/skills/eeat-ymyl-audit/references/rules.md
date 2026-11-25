# Rules

Everything below is done by `scripts/audit.py`. There is no scoring, tiering or priority: the workbook reports facts.

## Which pages are audited

A crawled page is audited when it returned 200, is indexable (when the export says so) and its page type label (from the IA or Content Prune & Merge workbook, or the crawl's label column) belongs to a page type in the config. Everything else is left out and counted in the preflight warnings (did not return 200, not indexable, no page type).

## Which external links count

A link counts as a citation when its destination is on a host that is not the client's own, it comes from an audited page, it is a hyperlink (not an image or script), and, when the export has a link position column, its position is one of `content_link_positions`. A page linking to the same destination twice counts once. Links in menus and footers (social profiles and so on) are left out.

## Requirements by page type

Each page type has a role: condition (concerns / conditions), service or blog. The role comes from `role` in the config, or from the page type's name. Every audited page is checked against the requirements for its role; the rest are "Not required".

| Requirement | Applies to | Passes when | Priority | Next steps | Handoff |
| --- | --- | --- | --- | --- | --- |
| Reviewer who is a medical professional | All | The reviewer extraction has a credential term (MD, DO, NP, APRN, PA-C, RN, board-certified and the config's terms). No reviewer rule (not on the site) is Missing | High | SEO: get the reviewer's name and credentials from the client. Dev: add a reviewed-by line to the templates | Dev |
| External link to a credible medical source | All | At least one content link goes to a credible source (below) | High | SEO: choose the source and anchor (External Links Needed). Dev: add the links | Dev |
| Credentials or years of experience mentioned | All | A credential term in the body, author or reviewer, or "N years of experience / practice" in the body | Medium | SEO: confirm them. Content: add them to the copy | Content |
| Author shown | Blog | The author extraction is not empty | Medium | SEO: confirm the author. Dev: add an author byline with a bio link | Dev |
| Published date shown | Blog | The published extraction is not empty | Low | Dev: show the date on the blog template | Dev |
| MedicalCondition schema | Condition | The schema types include MedicalCondition | Medium | Dev: add it to the condition template | Dev |
| MedicalProcedure schema | Service | The schema types include MedicalProcedure | Medium | Dev: add it to the service template | Dev |
| FAQPage schema on pages with FAQs | Any page whose FAQ extraction is not empty | The schema types include FAQPage | Low | Dev: output FAQPage schema from the FAQ section | Dev |
| Reviews or testimonials | Service, condition | The testimonials marker is not empty | Medium | SEO: pick reviews. Content: add them | Content |
| Before/after photos | Service | The before/after marker is not empty | Medium | SEO: collect consented photos. Content: add them | Content |
| Google rating shown | Service | The rating marker is not empty | Medium | Dev: add the rating to the service template | Dev |

Also on the Recommendations tab: claims needing verification (High, Content) and external links with an issue (High when any is dead or has no response, otherwise Medium; Dev).

Updated date is extracted and shown when the site has it, but it is not a requirement.

## Credible external sources

A content link counts as a credible source when its host ends in .gov, .edu or .org (or .gov.uk, .nhs.uk, .ac.uk, .gc.ca), or is a medical journal, database or reputable medical site in the built-in list (NEJM, JAMA, The Lancet, BMJ, Nature, ScienceDirect, Springer, Wiley, LWW, Oxford Academic, Cochrane, Frontiers, MDPI, Karger, Taylor & Francis, SAGE, Cell, JAAD, WebMD, Medical News Today, Healthline, Verywell Health, Merck Manuals, UpToDate, Drugs.com), or a host in the config's `credible_domains`. Shop, booking, financing, social and press links are not credible sources; they still appear on External Link Issues when they have an error.

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

## Claims Needing Verification

Claims are read on a sample: `--sample-per-type 5` picks 5 pages of each type at random (seeded by page type, so the same pages on every run) from pages with at least 200 words of body text, or from all pages of the type when fewer than 5 have that many. Claude lists each claim in the page's own words; each claim is one row.

**Follow-up review:** for blog and condition page types only, when the sampled pages' claims on pages that cite no credible source add up to 2 or more, and pages of that type were left out of the sample, the Recommendations tab adds a Low priority issue (Content): if the other changes do not bring improvements, the rest of that page type needs a closer review for claims. Claude never judges whether a claim is true: the SEO adds a source, marks it Accurate claim or Bad claim, and writes the updated claim for Content. A page not read shows "Not read".

## Sample page checks

Before the crawl, Claude gives the person what it believes each sample page has or is missing for every requirement; the person checks the live pages and every disagreement is fixed in the extraction rules first. After the crawl, preflight prints what the crawl detected on each sample page; the person checks it against the live pages again, and `agrees` in `work/chrome.tsv` records their answer. The build stops unless every sample page is Yes.

## Empty extractions (CHECK)

An extraction that feeds a requirement of a page type and is empty on every page of that type is a CHECK: the queue and the build stop until Claude has looked for the element in Claude in Chrome on the sample page, the page the selector was tested on and a few more pages of that type, and either fixed the rule or recorded `Confirmed absent` with the pages checked in `work/checks.tsv`.
