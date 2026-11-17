# Rules: new-site keyword gap

The thresholds are constants at the top of `scripts/gap.py`. Change them there and here together.

## Opportunity rules (per non-branded keyword)

| Rule | Definition | Constant | Why |
| --- | --- | --- | --- |
| 2+ competitors in top 10 | At least 2 competitors in the top 10 | `MULTI_MIN = 2`, `TOP_N = 10` | Two or more competitors earning page-one positions is evidence that the search is worth a page |
| 1+ competitor in top 3 | Any one competitor at position 3 or better | `TOP_BEST = 3` | One strong ranking shows the search can be won and is valuable, even when the other competitors miss it |
| Best competitor | Always shown: the competitor with the lowest position, that position, and its page | none | Every keyword says who to study, with no cutoff. Ties list every tied competitor |

A keyword is an **opportunity** when it meets either rule. Rules are counted per keyword; services are counted from those keywords.

## Groups

- **Branded removed:** a keyword containing a name the SEO gave for a competitor, or the competitor's domain name (`rival-one.com` adds "rival one", "rivalone" and "rival-one"), as a whole word or phrase with an optional plural. Removed before every flag and count.
- **Local:** a keyword containing a confirmed city, or "near me", "nearby" or "close to me". It is in the Local group only, with the services it also matches shown in the Services column.
- **Service:** a keyword containing a confirmed service term, as a whole word or phrase with an optional plural. A keyword that matches more than one service is counted under each, so service rows can overlap. Summary counts each keyword once.
- **Unassigned:** everything else. Reviewed by the person, never dropped. The most common words in it are listed in the Summary and printed by the build, to help find missing service terms.
- **Leftover brand words** (preflight only): a word of 4 or more letters from a competitor's names that still appears in 3 or more non-branded keywords (`LEFTOVER_MIN = 3`). Listed for the SEO to judge; nothing is removed automatically.
- **Service rows and Local:** a service's row counts its non-local keywords and rule counts. The Local columns beside them count that service's local keywords (same service terms) and how many meet either rule. Local keywords stay out of the service rule counts.

## Data limits

- Volume is the tool's estimate for the keyword. It is not a traffic forecast and is never added together.
- Positions are a snapshot of the keywords the tool tracks, mostly the top 100.
- Positions come from the gap export. The page for a keyword comes from that competitor's own ranking export; a keyword missing there has no page shown.
- A row with no competitor position (every position column empty) is counted in the Summary and left out of the tabs.
- Page "looks like" (home page, blog or article, other page) is a guess from the URL path: blog-style folders and the home page are recognised, everything else is "Other page".
- Preflight does not judge whether a competitor is in the right market or specialty. Competitors may overlap on only some services.

## Service opportunities columns

- **Offered by our client:** left blank, with a Yes or No dropdown, for the SEO to fill in. Nothing in the workbook reads it.
- **Best-performing competitor page:** among all the keywords for the service (non-local and local), the competitor page with the most keywords in the top 10. Home pages are skipped because they are not a page to model, query strings (such as tracking parameters) are removed from every URL, and the same page with and without "www" counts once. "Looks like" next to it shows whether the page is a blog or article. Ties go to the page with more keywords at any position, then the better best position. When no competitor page other than a home page is in the top 10 for the service, the cell says so. It counts keywords; it is not traffic. Pages come from each competitor's ranking export, so a keyword missing there cannot add to a page.
