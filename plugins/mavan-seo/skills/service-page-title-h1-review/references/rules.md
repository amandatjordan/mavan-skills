# Service Page H1 & Title Tag Review rules

`scripts/build.py` applies the mechanical rules below. Read this to explain a result or to judge a row. The AI decides what each page is about and which keywords it should target; the script does the lookups and the math. Nothing here is specific to one site or industry.

## Topic and target keywords (decided by the AI)

- Inputs are the page path, H1 and Title Tag only (the text before the first `|`). The H1 and last path segment name the page, the title confirms, earlier path segments are context only, the city is ignored.
- The topic is the service as a searcher would name it. Up to 8 keywords per page, most important first: the main term, other names for it, close variants. Duplicates (ignoring case, spaces, hyphens and a trailing "s") are dropped.
- A broad word shared with other pages is a keyword only on the page for that broad topic. Hub pages target the category term.
- The AI never types a number. Without Search Console the list keeps the AI's order and shows no numbers.

## Ranking with Search Console

- Search Console rows are page + query with clicks and impressions, summed per page and query.
- A keyword's number is the sum of impressions of that page's queries that contain all the keyword's words (plurals folded, "near", "me", "for" and similar words ignored). It is **not search volume**, and queries that contain a keyword's words overlap, so the numbers are not additive across keywords.
- Keywords are ranked by that number, highest first; keywords with 0 and pages with no Search Console data keep the AI's order. The top 5 are kept.
- A page's GSC Clicks and Impressions are the sums of its saved query rows, so they leave out the queries Search Console hides.

## When a person must review a page

A page is **Review Needed = Yes** when any of these is true, and Why Review lists each in plain words.

| Flag | When |
| --- | --- |
| No keywords | The AI gave no keywords for the page. Choose them by hand |
| Keywords not represented | None of the top keywords appears in the current Title Tag or H1. A keyword appears when its words are in the Title Tag or the H1 as an exact phrase, ignoring case, spaces, hyphens, accents and a plural "s" |
| No location | The person gave the client's city or service-area cities and none appears in the Title Tag, or none appears in the H1. Checked separately: "No location in Title Tag" and "No location in H1". Skipped when no city was given |
| Blank H1 / Blank Title Tag | The export has no H1 or no Title Tag for the page |

A page with some of its top keywords already in the title is not flagged: the writer works the missing ones in.
