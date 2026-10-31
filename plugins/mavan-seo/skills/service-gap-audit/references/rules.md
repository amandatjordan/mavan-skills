# Service Gap Audit rules

`scripts/build.py` applies everything here except § Page types and § Nodes, which are your judgment in Step 3. Thresholds: **thin** < 300 content words, **light** < 600; volume tiers **High** >= 5,000, **Medium** 2,000 to 4,999, **Low** < 2,000, zero = **No data** (ranks as Low).

## Page types

Decide each page's type from what the page is, using its H1, title and path together. Never decide it from a folder name alone: one site keeps services under `/services/`, another under `/treatments/`, another at the root, and concern pages, galleries and blogs move around the same way.

| Type | The page is | Counts as |
| --- | --- | --- |
| Service | About one treatment, brand, device or area (Botox, Lip Filler, Morpheus8), including a city version of it ("Botox in Tampa") | That node's page |
| Concern | About a problem or grouping that lists treatments (wrinkles, volume loss, "treatments by area", "by age", signature or featured treatment pages, a services menu that is mostly a list) | Proof the treatments it names are offered; never a service's page |
| Gallery | Before & after photos | Proof the treatment in its slug is offered |
| Blog | An article, news post, or a blog / news index | A blog mention (Likely offered) |
| Location | A city or "serving X" landing page | Nothing (not a service page) |
| Utility | Home, about, team, contact, policies, specials, financing, forms, category hubs with no content of their own | Nothing |

A category hub (e.g. "Injectables", "Body") whose H1 names a taxonomy Service is a Service page for that Service; one that only lists links and names no taxonomy node is Utility.

## Nodes

- `node` is the exact name of the most specific taxonomy node the page is about (Brand / Device > Sub-Service > Service), as written on the Taxonomy tab. A page about Botox is `Botox`, not `Neurotoxin`; an empty "Neurotoxins" hub is `Neurotoxin`.
- Every Service page needs a node. Concern, Blog and other pages may leave it blank: the script finds the treatments they name.
- A brand or device that is not in the taxonomy: `NEW: Name > Service`, with an existing taxonomy Service as parent (e.g. `NEW: Emsella Chair > Sexual Wellness`). It counts as that Service's brand page and is listed for the taxonomy pull request.
- Practice-specific program or package names ("Signature Glow Facial") are not brands: give the page the node of the treatment it is (`Facials`), or type it Concern if it bundles several.
- `city`: the service-area city the page is for, when it is a city version of a service page. Used to name thin copies.

## Keyword classification (done by the script on every run)

The script classifies the All Keywords tab with the Taxonomy and Filters tabs each run, so a taxonomy edit applies immediately. All matching is case-insensitive regex.

1. **Exclude** first: Celebrity / person, Competitor brand, Off-topic (Filters tab).
2. **Match nodes**: best Brand / Device, Sub-Service, Service and Concern match. Best = longest matched span; ties go to the earlier taxonomy row. A brand sets its Service; a Sub-Service of the same Service sets the Sub-Service (a keyword can carry both, "botox lip flip"); a brand with a single Sub-Service sets it; otherwise the best Service. Class = Service.
3. No service but a Concern: Class = Concern. Otherwise the Generic pattern: Class = Generic. Otherwise Unmapped.

## Indexability

The crawler's indexable status, plus **Canonical loop**: the page is canonicalized to a URL that redirects. With a canonical column the target's status is checked directly; without one, a canonicalized URL whose other trailing-slash form redirects in the same export is a loop. A canonical loop means Google has no indexable copy of the page.

## Coverage

Evidence from live (200) pages, per Service, Sub-Service and Brand / Device that fits the practice type:
- **Page**: a Service page whose node is this node. A Service row counts only its own page; its brand and Sub-Service pages are listed separately.
- **Section**: the node matches an H2 on a Service page (skipped when the export has no H2 columns; the Read Me says so).
- **Gallery**: the node matches a Gallery page's slug.
- **Concern page**: the node matches a Concern page's path, title, H1 or H2s.
- **Meta mention**: the node matches a Service page's meta description.
- **Blog**: the node matches a Blog page's path, title, H1 or H2s.

**Best page** when a node has several: indexable first, then >= thin, then most content words. A node with a non-indexable page of >= 300 words is "not indexable", even when a thin indexable duplicate exists.

**Coverage**, first that applies: Page exists, not indexable / Empty or thin page / Light page / Page / Only Brand / Sub-Service pages / Section (H2) only / Gallery only / Concern page only / Meta description mention only / Blog only / None.

## Offered status

- **Confirmed**: own page, H2 section, gallery, concern page, or implied. Implied = a Brand / Device or Sub-Service with any evidence implies the Sub-Services and Service in its row (Sub-Service column and Implies Offered).
- **Likely**: only a meta description or blog mention.
- **Unknown (parent offered)**: a Sub-Service with no evidence whose Service is Confirmed.
- **No evidence**.

## Gaps and priority

Never a gap for a node whose Status / Notes says "Do not flag" or "NOT US-approved". Volume = competitor volume for the node: Service = all its keywords; Sub-Service = keywords with that Sub-Service (any brand); Brand = keywords with that brand.

| Gap Type | When | High | Medium | Low / No data |
| --- | --- | --- | --- | --- |
| Indexability blocker | Best page is not indexable | P1 | P1 | P1 |
| Empty / thin page | Best page indexable and < thin | P1 | P1 | P1 |
| Missing page (offered) | Gallery, concern page or meta mention, or Confirmed / Likely with no page | P1 | P2 | P3 |
| No Service page (brand pages only) | Service with only brand / Sub-Service pages | P2 | P3 | P3 |
| Missing page (blog only) | Only blog posts | P2 | P3 | P3 |
| Section, no page | Only an H2 section | P3 | P3 | P3 |
| Light page | Best page indexable, thin <= words < light | P3 | P3 | P3 |
| Confirm Sub-Service, then page | Unknown (parent offered) | P2 | not flagged | not flagged |
| Ask client: not offered? | Service, No evidence, fits practice type, not Beauty Services | Ask | not flagged | not flagged |

**Page brief** for an Empty / thin Service page: build the best page into the main page (with today's word count); merge and 301 each other thin page for the same node; a section per Confirmed or Likely Sub-Service; Sub-Services to confirm; brand pages to compare and link.

## Keywords per page

Each keyword is counted once, on its most specific page: Service page = that Service with no Sub-Service and no Brand; Sub-Service page = that Sub-Service, any brand ("juvederm lip filler" counts for Lip Filler); Brand page = that brand with no Sub-Service. Only Class = Service.

**Other markets**: a keyword with Geo Modified = Y (All Keywords tab) is excluded unless it names one of the client's cities. Suburbs the person did not name are other markets; the Excluded Keywords tab's Keep? column is how a person adds one back. Near Me keywords are kept.

**Search Console**: with the sheet, Client GSC Impressions = impressions summed across the site for queries that exactly match the row's Relevant Keywords.
