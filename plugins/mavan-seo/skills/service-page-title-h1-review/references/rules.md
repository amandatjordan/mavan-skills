# Service Page H1 & Title Tag Review rules

`scripts/build.py` applies every rule below. Read this to explain a result or to judge a row, not to redo the work by hand. The taxonomy decides everything it can; nothing here is specific to one site.

## Matching a page to one taxonomy entry

- **Page text** is the page path (lowercased; hyphens, underscores, slashes and dots become spaces), the H1 (lowercased) and the Title Tag (the text before the first `|`, lowercased). Nothing else about the page is used.
- Test the Taxonomy tab's **Match Terms** (case-insensitive regex) of every Brand / Device, Sub-Service and Service row against the path first, then the H1, then the Title Tag. Stop at the first one that matches any of them.
- **Concern** rows are tested only when no Brand / Device, Sub-Service or Service row matches in any of the three.
- The most specific level that matched wins: Brand / Device, then Sub-Service, then Service.
- If several entries match at that level, drop an entry that is broader than another matching entry: (a) its Implies Offered list is a strict subset of the other's (a "family" row against a specific product), or (b) its matched text is only part of the other's longer matched text ("scar" inside "acne scar"). One entry left is the match. More than one left means the page is Not matched and Review Needed, naming them.
- No match leaves the page **Not matched**. A page that is not matched gets no keywords, is marked Review Needed, and nothing is guessed.
- A Service or Sub-Service **has a page** when at least one crawled URL matched to it. A section on another page does not count.
- A Sub-Service whose own name contains a brand ("Masseter / Jaw Botox") is labeled with the brand, as in the Service Gap Audit. The Notes column says which field matched so a person can see it.

## Keyword pool

A keyword sits on one entry only, the taxonomy's own "most specific match". Rows come from the All Keywords tab:

| Page entry | Rows used |
| --- | --- |
| Service | Class = Service, Matched Level = Service, same Service |
| Sub-Service | Class = Service, Matched Level = Sub-Service, same Service and Sub-Service |
| Brand / Device | Class = Service, Matched Level = Brand / Device, same Service and Brand / Device |
| Concern | Class = Concern, same Concern |

No other filters. Exclude, Generic and Unmapped rows have no entry, so they never reach a pool. Geo Modified, Near Me, modifier, informational and Spanish keywords stay eligible; the city and "near me" are already removed in Base Term, and the writer adds the location.

## Implied entries and missing pages

- Read Implies Offered on the page's entry (names separated by `;`). For a Brand / Device or Sub-Service, a name resolves to its Service, or to a Sub-Service of the same Service. For a Concern, a name resolves to any Sub-Service or Service. A name that is not in the taxonomy is skipped and listed in the report.
- Skip an implied entry whose Status / Notes says "Do not flag" or "NOT US-approved".
- If a crawled page has the implied entry, add nothing. If none does, add that entry's own keyword pool to this page's pool and add a row to Recommendations.
- A Concern page borrows keywords the same way but never creates a Recommendations row: the taxonomy says a Concern is not a page gap on its own, and it does not prove the practice offers the service.
- Never add child entries' keywords to a Service or Sub-Service page, and never look for missing pages any other way. Recommendations come only from this check.

## Top 5 keywords

- Group the pool by Base Term, ignoring case, spaces, hyphens and a trailing "s" (so "med spa" and "medspa" are one group).
- Keep the row with the highest volume in each group, show its Base Term and volume, and never add volumes together. A "near me" or city row can supply the volume for its Base Term.
- Sort by volume, highest first, and keep 5. Fewer than 5 means list what exists. None means a blank cell and the note "No keywords found in taxonomy".
- **Update to Include** is one keyword per line: `term - 1,234`.
- Volume is from competitor rankings, often in other markets. It ranks keywords against each other. It is not demand for this client.

## When a person must review a page

A page is **Review Needed = Yes** when any of these is true, and the Why Review column lists each one in plain words. Everything else about how a page was matched goes in Matching Notes, which is information only.

| Flag | When |
| --- | --- |
| Not matched | No taxonomy entry matched, or several tied (see Matching a page). Choose the service and keywords by hand |
| No keywords | The matched entry, and any implied entry with no page, has no keywords in the taxonomy. Choose keywords by hand |
| Keywords not represented | None of the top keywords appears in the current Title Tag or H1. A keyword appears when its words are in the Title Tag or the H1 as an exact phrase, ignoring case, spaces, hyphens, accents and a plural "s" ("Med-Spa" and "medspas" both contain "med spa") |
| No city | The person gave the client's city or service-area cities and none of them appears in the Title Tag or the H1 (whole title, including text after a `\|`). Skipped when no city was given |
| Blank H1 / Blank Title Tag | The export has no H1 or no Title Tag for the page |

A page with some of its top keywords already in the title is not flagged: the writer works the missing ones in.
