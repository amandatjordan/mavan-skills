# Service Page H1 & Title Tag Review rules

`scripts/build.py` applies every rule below. Read this to explain a result or to judge a row, not to redo the work by hand. The AI decides what a page is about and which candidate keywords fit; the script does the lookups and the math. Nothing here is specific to one site.

## What a page is about (decided by the AI, not the taxonomy)

- The AI reads `work/pages.tsv` (path, H1, title, plus the taxonomy's guess) and writes the page's **topic**: the H1 and last path segment first, the title to confirm, earlier path segments as context only, the city ignored. A broad word shared with other pages is the topic only on the page for that broad category.
- The taxonomy's guess is made by matching the Taxonomy tab's Match Terms (path, then H1, then title; most specific level wins). It is only a guess and a label. When the AI marks it `none`, the page has no taxonomy entry: no implied entries are borrowed and it creates no Recommendations.
- A Service or Sub-Service **has a page** when at least one crawled page keeps that entry as its taxonomy entry. A section on another page does not count.

## Candidate keywords

- For each topic term, the script takes every row of the All Keywords tab (all classes except Exclude) whose Base Term has all of the term's words, with plurals folded. For a term of several words it also takes rows with the term's rarest word, but only when that word is in the list at all, so "facial sanding" cannot fall back on "facial".
- Up to 12 topic candidates (full matches first, highest volume first), then up to 3 more from implied entries with no page.
- The AI strikes candidates that are about something else. The script never strikes anything itself.
- A topic term with fewer than 3 keyword groups containing all its words is named in Why Review and written to the missing-keywords file.

## Implied entries and missing pages

- Read Implies Offered on the page's taxonomy entry (names separated by `;`). For a Brand / Device or Sub-Service, a name resolves to its Service, or to a Sub-Service of the same Service. For a Concern, a name resolves to any Sub-Service or Service. A name that is not in the taxonomy is skipped and listed in the report.
- Skip an implied entry whose Status / Notes says "Do not flag" or "NOT US-approved".
- If a crawled page has the implied entry, add nothing. If none does, offer that entry's top 3 keywords as extra candidates (the AI may strike them) and add a row to Recommendations.
- A Concern page offers keywords the same way but never creates a Recommendations row: a Concern is not a page gap on its own and does not prove the practice offers the service.
- Never look for missing pages any other way. Recommendations come only from this check.

## Top 5 keywords

- Group the kept candidates by Base Term, ignoring case, spaces, hyphens and a trailing "s" (so "med spa" and "medspa" are one group).
- Keep the row with the highest volume in each group, show its Base Term and volume, and never add volumes together. A "near me" or city row can supply the volume for its Base Term.
- Sort by volume, highest first, and keep 5. Fewer than 5 means list what exists. None means a blank cell and a Review flag.
- **Update to Include** is one keyword per line: `term - 1,234`.
- Volume is from competitor rankings, often in other markets. It ranks keywords against each other. It is not demand for this client.

## When a person must review a page

A page is **Review Needed = Yes** when any of these is true, and the Why Review column lists each one in plain words. Everything else about how a page was matched goes in Matching Notes, which is information only.

| Flag | When |
| --- | --- |
| Few or no keywords | A topic term has fewer than 3 keyword groups in the list. The term is named, e.g. "facial sanding" (none) |
| No keywords | Nothing is left after the strikes. Choose keywords by hand |
| Keywords not represented | None of the top keywords appears in the current Title Tag or H1. A keyword appears when its words are in the Title Tag or the H1 as an exact phrase, ignoring case, spaces, hyphens, accents and a plural "s" ("Med-Spa" and "medspas" both contain "med spa") |
| No city | The person gave the client's city or service-area cities and none of them appears in the Title Tag or the H1 (whole title, including text after a `\|`). Skipped when no city was given |
| Blank H1 / Blank Title Tag | The export has no H1 or no Title Tag for the page |

A page with some of its top keywords already in the title is not flagged: the writer works the missing ones in.
