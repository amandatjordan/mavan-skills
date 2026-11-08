# Rules

Every threshold below is a constant at the top of `scripts/diagnose.py` or `scripts/gsc.py`. They are starting values: confirm with Amanda before changing, change them in the script, and update this file in the same pull request.

## Scoring

- Each signal adds points when its value passes its threshold (most are worth 1, a few 2).
- A signal whose input is missing is **Not scored** and does not count toward the points possible.
- A lens's score = points / points possible from its scored signals. **High** 50%+, **Medium** 25-49%, **Low** under 25%.
- The lens with the highest score leads. Any lens within **10 points** of it is a **co-lead**. A lens with fewer than 2 scored signals is **Not enough data** and cannot lead.

## Page groups (crawl)

- **Live** = status 200. **Indexable** = the crawler's indexable status (every live page when the export has no indexability column).
- **Archive and listing pages** = indexable pages whose path matches a generic CMS listing pattern: `/tag(s)/`, `/category/`, `/categories/`, `/author(s)/`, `/archive(s)/`, `/page/N`, `?page=N` (or `paged`, `p`), a date archive ending at the year or month (`/2024/` or `/2024/05/`), feeds. Add a site's own pattern in `config.json` `archive_patterns` only after checking examples in the crawl.
- **Other indexable pages** = indexable pages that are not archives. Thin, repeated-title and no-keyword signals use only these, so archive pages are not counted twice.
- When several crawl rows normalise to the same URL (trailing slash, case, `www`), the live 200 row wins.

## Signals

| Lens | ID | Signal | Threshold | Points |
| --- | --- | --- | --- | --- |
| Architecture | A1 | Archive pages as a share of indexable pages | 25% / 50% | 1 / 2 |
| Architecture | A2 | Other indexable pages whose title or H1 is shared by 5+ pages | 20% | 1 |
| Architecture | A3 | Other indexable pages with no tracked keywords (only when there are 200+ such pages) | 80% | 1 |
| Architecture | A4 | Redirecting URLs (3xx) the crawler reached, as a share of crawled HTML URLs | 20% | 1 |
| Architecture | A5 | Indexable pages deeper than 3 clicks (needs a crawl depth column) | 20% | 1 |
| Architecture | A6 | Ranking URLs on the crawled host that are not a live 200 page (404, redirect, or not found by the crawl) | 10% | 1 |
| Architecture | A7 | Indexable non-archive crawl pages with no GSC impressions in period B (replaces A3 when scored) | 80% | 1 |
| Architecture | A8 | Archive pages' share of non-brand GSC impressions in period B | 30% | 1 |
| Architecture | A9 | Non-brand searches (20+ impressions in B) where 2+ URLs each have 10+ impressions, as a share of those searches | 30% | 1 |
| Content | C1 | Keywords in the gap export ranked by the top competitor vs the prospect | 2x / 3x | 1 / 2 |
| Content | C2 | Top-10 rankings on non-branded service keywords: prospect below the median competitor | below | 1 |
| Content | C3 | Of the gap keywords a competitor ranks top 20 for (prospect absent), the share that are buying searches | 30% | 1 |
| Content | C4 | Other indexable pages under 300 content words | 15% | 1 |
| Content | C5 | Non-brand GSC clicks, period B vs period A (impressions when period A has under 10 clicks and impressions are comparable) | down 20% | 1 |
| Content | C6 | Non-brand service searches (all non-brand when there are no service terms) at average position 8-20 with 20+ impressions in B | 6 or more | 1 |
| Authority | U1 | Median competitor authority score minus the prospect's | 5 / 10 | 1 / 2 |
| Authority | U2 | Prospect referring domains under half the median competitor | under 50% | 1 |
| Authority | U3 | Domains scoring 30+ that link to competitors and not the prospect outnumber the prospect's own 30+ domains (needs both optional exports) | more | 1 |
| Authority | U4 | Unusual link growth: prospect 12-month referring domain growth 2x the median competitor, and/or 50%+ of its referring domains first seen in the last 90 days. Each check that has data must hold | holds | 1 |
| Authority | U5 | Manual action reported in Search Console (person-reported). **Yes makes Authority & Trust High regardless of score** (its issue score becomes 100%). Unknown is Not scored | any | 1 |

Notes:

- **Buying searches** (C3): from the export's intent column when it has one (Commercial or Transactional), otherwise from buying words in the keyword (near me, cost, price, best, clinic, doctor, surgeon, consultation, financing, before and after, reviews). Searches containing a brand term or a competitor's domain name are left out of every content signal.
- **Service keywords** (C2 and the service table): non-branded keywords in the gap export that match a `service_terms` entry or one of its synonyms (whole word or phrase, optional plural). A keyword goes to the service whose matching term is longest, so "breast lift with augmentation" counts once. Without `service_terms`, C2 uses non-branded buying searches instead. The service table shows, per service: keywords tracked, the prospect's top-10 count and best position, the competitor with the most top-10 rankings and its best position, and the keywords where a competitor is top 10 and the prospect is not top 20.
- **Ranking URLs on another host** (a store subdomain, say) are listed as "Other host (not crawled)" and are not counted in A6.
- **A4** counts every 3xx the crawler reached, so it includes http-to-https and trailing-slash redirects: internal links that point at redirects.
- **U4 is a trust risk**, not proof of spam. Spam waves often hit every site in a market; compare growth with the competitors before calling it out, and never recommend a disavow without a Search Console manual action.
- **Authority overview figures** are typed by the person. They are used as given and labelled as typed from the tool.

## Search Console (GSC)

- **Periods**: B = the 6 months ending on the newest date in the file, A = the 6 months before it; change = B minus A. The data must start within 14 days of the start of A or the preflight fails.
- **Brand**: whole-word match on `brand_terms`; brand searches are left out of every "non-brand" figure.
- **Pages** are matched to the crawl with the same URL normalisation (https, no www, no query string, trailing slash), so tracking parameters such as `?utm_source=gbp` fold into the page.
- **Capped exports**: if zero-click rows are under half as common in one period as in the other (the export kept only clicked rows there), impressions are not comparable. A7, A8, A9, C6 are Not scored, C5 uses clicks only, keyword drops use clicks only. A3 (the keyword-tool proxy) stays scored when A7 cannot be.
- **Keyword drops**: non-brand searches whose clicks fell from A to B, biggest loss first, shown with both periods' clicks, impressions and average position. Keywords with under `--click-floor` clicks (default 3) in both periods are labelled low numbers. When impressions are comparable, a keyword whose clicks did not fall but whose impressions fell by 50% or more from at least `--impr-floor` (default 50) counts too, labelled "Impressions (clicks too low)".
- **Average position** is impression-weighted.
- **Numbers**: GSC figures are real clicks and impressions. Semrush or Ahrefs volumes are estimates and are never added together or added to GSC figures.

## What this does not check

Internal links between pages (no link export), the live site, GA4, why traffic changed (migrations, updates, seasonality), page speed or Core Web Vitals, and Google Business Profile.
