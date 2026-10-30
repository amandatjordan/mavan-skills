# Service Page H1 & Title Tag Review rules

`scripts/build.py` applies the mechanical rules below. Read this to explain a result or to judge a row. The AI decides what each page is about and which keywords it should target; the script does the lookups and the math. Nothing here is specific to one site or industry.

## Topic and target keywords (decided by the AI)

- Inputs are the page path, H1 and Title Tag only (the text before the first `|`). The H1 and last path segment name the page, the title confirms, earlier path segments are context only, the city is ignored.
- The topic is the service as a searcher would name it. Up to 8 keywords per page, most important first: the main term, other names for it, close variants. Duplicates (ignoring case, spaces, hyphens and a trailing "s") are dropped.
- A broad word shared with other pages is a keyword only on the page for that broad topic. Hub pages target the category term.
- The AI never types a number. Suggested Keywords are the first 5, in the AI's order, with no numbers.

## Top GSC Queries (Search Console only)

- Search Console rows are page + query with impressions and clicks, summed per page and query. Brand terms are excluded in the request and again by the script.
- Per page the script keeps up to 10 queries with at least 5 impressions each, most impressions first (ties: more clicks), shown as `query (impressions/clicks)` separated by `;`. Pages with none show "No GSC data for this page (or fewer than 5 impressions per query)".
- The queries are for a person to read when working out what belongs in the Title Tag and H1. Claude does not rank, filter or judge them; it only reports pages whose queries are mostly other cities or services.
- Suggested Keywords are not ranked by Search Console data.

## When a person must review a page

A page is **Review Needed = Yes** when any of these is true, and Why Review lists each in plain words.

| Flag | When |
| --- | --- |
| No keywords | The AI gave no keywords for the page. Choose them by hand |
| Keywords not represented | None of the top keywords appears in the current Title Tag or H1. A keyword appears when its words are in the Title Tag or the H1 as an exact phrase, ignoring case, spaces, hyphens, accents and a plural "s" |
| No location | The person gave the client's city or service-area cities and none appears in the Title Tag, or none appears in the H1. Checked separately: "No location in Title Tag" and "No location in H1". Skipped when no city was given |
| Blank H1 / Blank Title Tag | The export has no H1 or no Title Tag for the page |
| Likely not a service page | The path contains a tag, category, author, blog, news or feed segment, a `/page/N` or a `/YYYY/MM/` date. The page is kept and flagged |

A page with some of its top keywords already in the title is not flagged: the writer works the missing ones in.
