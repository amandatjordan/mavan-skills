# New site keyword research: rules

All thresholds are constants at the top of `scripts/research.py`. Change them there and update this file in the same pull request.

## Vocabulary

Category > Service > Sub-Service > Brand / Device. A **Concern** is a problem people search for and points to Services. A **Modifier** (Cost, Before & After, Recovery / Risks, Comparison, Candidacy, Best / Top) is a flag on a keyword, never a level. These are the taxonomy's own names.

## What goes in the plan

- Every item the person lists that matches a taxonomy row.
- The **parent Service** of any listed Sub-Service or Brand / Device, marked "Implied" (the taxonomy's implication rule: a Brand / Device implies its Service). Sub-Services are not implied by a brand; unlisted ones are suggested rows with Client offers it? left blank.
- Left out, with the reason on the Not in the plan tab: items whose taxonomy note says not US-approved, not FDA-approved, investigational or discontinued, and typed items with no match.
- **Dental is included, with no minimum volume.** Every listed dental Service, Sub-Service, Brand / Device and Concern gets its own page, and every unlisted dental Sub-Service and Brand is a suggested row with Client offers it? left blank. The taxonomy has keyword data for dental concerns only, so other dental rows show no keywords and a note to research volume separately.

## Page or section

| Level | Rule |
| --- | --- |
| Service | Always its own page |
| Concern | Own page when the client lists it. More than 5 raises a warning |
| Sub-Service | Own page when its highest-volume keyword is 1,000 or more (`PAGE_MIN_VOLUME`). Otherwise a section on its Service page. **Dental: always its own page, no minimum** |
| Brand / Device | Same cutoff (dental: always its own page). Otherwise a section on its parent page: each listed Sub-Service of the brand that has its own page, or the Service page |

The cutoff was set from the taxonomy's own distribution (v5.1): 21 of the 49 Sub-Services and 44 of the 92 Brands / Devices that have keywords have a top keyword of 1,000 or more, so about 45% would get their own page. It is a starting point; the SEO can change it.

A section row keeps its keywords: they are the headings and terms for that section on the parent page. The parent page's row lists its sections in "Mention on this page as a section".

## Suggested pages and Client offers it?

Unlisted Sub-Services and Brands / Devices under the plan's Services join the Pages tab as suggested rows when their highest keyword is 1,000 or more (`CONFIRM_MIN_VOLUME`; every unlisted dental one, no minimum). The **Client offers it? (Yes / No)** column is Yes for listed items and parents of listed items, blank for suggested rows. A No means no page. A suggested page is never named as the parent of a section; sections sit on a confirmed page. Taxonomy names are shown without the "(family)" tag.

## Volume

- National volume from the taxonomy's All Keywords tab (what competitors rank for). Not local demand, not a forecast.
- **Highest keyword, never a sum.** Many keywords are the same search worded differently, so adding them double counts.
- City-modified keywords (a city name in the search, `Geo Modified` in the taxonomy) are excluded from every figure and shown only as a count. "Near me" keywords stay in.
- A Service row counts only searches that name the service. Searches for its brands (Botox under Neurotoxin) sit on the brand rows, so Service rows also show the highest keyword anywhere under the service, as text, to compare services.
- Concerns are only those that point to a real Service or Sub-Service. Keywords for a concern that was removed from the taxonomy sit in Unmapped.
- The 77 keywords added for 24 concerns in taxonomy v5.3 come from a Google Ads check (Nov 2026), so their Keyword Difficulty and CPC are blank and their volumes are from a different source than the competitor-ranking keywords. Check the Volume Notes column for intent problems (for example Diastasis Recti is mostly exercise searches).
- Only keywords the taxonomy classes as Service or Concern are used. Generic, Exclude and Unmapped keywords are ignored.

## Internal links

Built from the hierarchy, only between pages with their own page:

| Link | Priority |
| --- | --- |
| Service <-> its Sub-Service page, both directions | High |
| Brand / Device <-> its parent page (Sub-Service if it has one, else Service), both directions | High |
| Concern -> each Service or Sub-Service page the taxonomy says treats it (its Implies Offered list), and each of those back to the Concern page | Medium |
| Sub-Services under one Service <-> each other | Low |

Sections have no link of their own. The links are a column on the Pages tab ("Internal links out"), not a separate tab. A link to a suggested page the client has not confirmed is tagged "only if the client offers it". Anchor text is not suggested: the Pages tab has a blank column for the SEO to fill in.

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
