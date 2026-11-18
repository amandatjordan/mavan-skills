# New site keyword research: rules

All thresholds are constants at the top of `scripts/research.py`. Change them there and update this file in the same pull request.

## Vocabulary

Category > Service > Sub-Service > Brand / Device. A **Concern** is a problem people search for and points to Services. A **Modifier** (Cost, Before & After, Recovery / Risks, Comparison, Candidacy, Best / Top) is a flag on a keyword, never a level. These are the taxonomy's own names.

## What goes in the plan

- Every item the person lists that matches a taxonomy row.
- The **parent Service** of any listed Sub-Service or Brand / Device, marked "Implied" (the taxonomy's implication rule: a Brand / Device implies its Service). Sub-Services are not implied by a brand; unlisted ones go to Confirm with client.
- Left out, with the reason on the Not in the plan tab: items whose taxonomy note says not US-approved, not FDA-approved, investigational or discontinued, and typed items with no match.
- **Dental is included.** The taxonomy has no keyword data for dental services yet, so dental rows show no keywords and a note. A dental Sub-Service or Brand / Device with no keywords defaults to a section, because the volume cutoff has nothing to decide with. Check its volume before building a page.

## Page or section

| Level | Rule |
| --- | --- |
| Service | Always its own page |
| Concern | Own page when the client lists it. More than 5 raises a warning |
| Sub-Service | Own page when its highest-volume keyword is 1,000 or more (`PAGE_MIN_VOLUME`). Otherwise a section on its Service page |
| Brand / Device | Same cutoff. Otherwise a section on its parent page: each listed Sub-Service of the brand that has its own page, or the Service page |

The cutoff was set from the taxonomy's own distribution (v5.1): 21 of the 49 Sub-Services and 44 of the 92 Brands / Devices that have keywords have a top keyword of 1,000 or more, so about 45% would get their own page. It is a starting point; the SEO can change it.

A section row keeps its keywords: they are the headings and terms for that section on the parent page. The parent page's row lists its sections in "Mention on this page as a section".

## Volume

- National volume from the taxonomy's All Keywords tab (what competitors rank for). Not local demand, not a forecast.
- **Highest keyword, never a sum.** Many keywords are the same search worded differently, so adding them double counts.
- City-modified keywords (a city name in the search, `Geo Modified` in the taxonomy) are excluded from every figure and shown only as a count. "Near me" keywords stay in.
- A Service row counts only searches that name the service. Searches for its brands (Botox under Neurotoxin) sit on the brand rows, so Service rows also show the highest keyword anywhere under the service, as text, to compare services.
- Concerns are only those that point to a real Service or Sub-Service. Keywords for a concern that was removed from the taxonomy sit in Unmapped.
- Only keywords the taxonomy classes as Service or Concern are used. Generic, Exclude and Unmapped keywords are ignored.

## Internal links

Built from the hierarchy, only between pages with their own page:

| Link | Priority |
| --- | --- |
| Service <-> its Sub-Service page, both directions | High |
| Brand / Device <-> its parent page (Sub-Service if it has one, else Service), both directions | High |
| Concern -> each Service or Sub-Service page the taxonomy says treats it (its Implies Offered list), and each of those back to the Concern page | Medium |
| Sub-Services under one Service <-> each other | Low |

Sections have no link of their own. The suggested anchor is the target page's primary keyword.

## Sections searchers look for

A word check on each keyword. It suggests which sections a page needs and never changes a page decision.

| Modifier | Words |
| --- | --- |
| Cost | cost, price, pricing, how much, cheap, financing |
| Before & After | before and after, before & after |
| Recovery / Risks | recover, side effect, risk, downtime, healing, aftercare, complication |
| Comparison | vs, versus, difference between, compare, alternative |
| Candidacy | candidate, who is / should, am i a, good for, right for, eligible |
| Best / Top | best, top |

## Not covered

Location pages and city terms, competitor analysis, the client's own rankings, and the content roadmap (a later skill that combines this plan with the blog taxonomy).
