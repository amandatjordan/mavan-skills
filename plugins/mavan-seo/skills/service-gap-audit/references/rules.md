# Service Gap Audit rules

Thresholds are first-test defaults (agelesscdga.com, Oct 2026): **thin** < 300 content words, **light** < 600, Sub-Service confirm at competitor volume >= 5,000, "is it offered?" at >= 5,000. Write them in the Read Me.

## Keyword classification

Only needed when the person attached a keyword list other than the bundled All Keywords tab. All matching is case-insensitive regex against the lowercased keyword, using the Taxonomy tab's Match Terms and the Filters tab's patterns.

1. **Exclude** first: Celebrity / person, Competitor brand, Off-topic (Filters tab). Class = Exclude.
2. **Match nodes.** Find the best Brand / Device, Sub-Service, Service and Concern match. Best = longest matched span; ties go to the earlier taxonomy row.
   - Brand matched: Service = the brand's Service, Brand = it.
   - Sub-Service matched and it belongs to the same Service (or no brand matched): Sub-Service = it. A keyword can carry both ("botox lip flip" = Neurotoxin > Lip Flip, Brand Botox).
   - Brand has a single Sub-Service in its row and none matched: use it.
   - Otherwise Service = best Service match.
   - Any of the above: Class = Service. Matched Level = the most specific one filled.
3. No service but a Concern: Class = Concern.
4. Otherwise Generic pattern: Class = Generic. Otherwise Unmapped.
5. Flags: Geo Modified (Known city / state / ZIP), Near Me, Spanish, Informational, and each Modifier.

## Pages

**Page type** from the path:
- Gallery: before & after URLs (`/before-after`, `/gallery`, `/photos` with a treatment slug).
- Blog post: under `/blog/` (Blog index for `/blog/` and `/blog/page/N/`).
- Location: a city or "near X" landing page with no service in its path.
- Service: under `/services/` (or the site's equivalent), plus service or concern hubs outside it whose path, title or H1 names a taxonomy node.
- Utility: everything else (contact, about, privacy, team, specials, thank-you).

**Indexability.** Use the crawler's indexable status. Flag **Canonical loop** when the page is canonicalized to another URL and that canonical target redirects. With a canonical column, check the target's status directly. Without one, infer it: the URL without a trailing slash is "Canonicalized" and the trailing-slash version is a 3xx in the same export. A canonical loop means Google has no indexable copy of the page.

**Primary node** of each Service page: match path (dashes and slashes as spaces) + title (text before the first `|`) + H1 against the taxonomy, ignoring Concerns. Most specific level wins (Brand / Device > Sub-Service > Service), then longest match. Service pages that match nothing are missing from the taxonomy: list them.

**Duplicates**: two or more Service pages with the same primary node. Report each one's content words, indexability and H1.

## Coverage

For each Service, Sub-Service and Brand / Device, collect evidence from live (200) pages:
- **Page**: a Service page whose primary node is this node (same Service). A Service row counts only the Service's own page. Its brand and sub-service pages are listed separately as "Brand / Sub-Service pages".
- **Section**: the node matches an H2 (either exported H2) on a Service page.
- **Meta mention**: the node matches a Service page's meta description.
- **Blog**: the node matches a blog post's path, title, H1 or H2.
- **Gallery**: the node matches a gallery URL slug.

**Best page** when a node has several: prefer indexable, then >= thin threshold, then a `/services/` URL, then most content words.

**Coverage** (first that applies): Page exists, not indexable / Empty or thin page / Light page / Page / Only Brand / Sub-Service pages / Section (H2) only / Meta description mention only / Blog only / Gallery only / None.

Skip nodes whose Practice Type doesn't fit the client (Surgical for a medspa-only client, Medspa for a surgical-only client).

## Offered status

- **Confirmed**: own page, an H2 section, a gallery, or implied. Implied = a Brand / Device with any evidence implies the Sub-Services and Service in its Implies Offered; a Sub-Service with any evidence implies its Service.
- **Likely**: only a meta description mention.
- **Unknown (parent offered)**: a Sub-Service with no evidence whose Service is Confirmed.
- **No evidence**.

## Gaps and priority

Never create a gap for a node whose Status / Notes says "Do not flag" or "NOT US-approved".

| Gap Type | When | Priority |
| --- | --- | --- |
| Indexability blocker | Best page is not indexable | P1 |
| Empty / thin page | Best page indexable and < thin | P1 |
| Missing page (offered) | Confirmed or Likely, coverage is meta / gallery / none | P1 if Confirmed and volume >= 5,000, else P2 |
| No Service page (brand pages only) | Service with only brand / sub-service pages (keep the list of those pages for the Recommendations tab) | P2 if volume >= 5,000, else P3 |
| Missing page (blog only) | Only blog posts | P2 if volume >= 5,000, else P3 |
| Section, no page | Only an H2 section | P3 |
| Light page | Best page indexable, thin <= words < light | P3 |
| Confirm Sub-Service, then page | Unknown (parent offered), volume >= 5,000 | P2 |
| Ask client: not offered? | Service, No evidence, volume >= 5,000, fits practice type, not Beauty Services | Ask |

Volume here = competitor volume for the node: Service = all its keywords; Sub-Service = keywords with that Sub-Service (any brand); Brand = keywords with that brand.

## Page briefs

For each **Empty / thin page** Service row, the Recommendation is a brief, built from the data:
1. If the node also has a non-indexable page with >= thin words, the real content already exists there: say so with its word count, "fix that first", then say the empty `/services/` hub should become the overview that compares the brands and links to it (or 301 it).
2. Otherwise: build the `/services/` hub into the main page, with today's word count.
3. Each other thin duplicate: give its path, word count and H1, and recommend a Concern page for that H1 that links to the main page, or a 301.
4. Sections for each Confirmed or Likely Sub-Service, each linking to its own page once built.
5. Sub-Services to confirm with the client.
6. Brand pages to compare and link.
7. Modifier sections with competitor volume >= 1,000 for that Service, with the volume.

Other gap types get one-line recommendations (see the example workbook's Gap List).

## Keywords per page

Each keyword is counted on its most specific page, never twice:
- **Service** page: keywords with that Service, no Sub-Service, no Brand.
- **Sub-Service** page: keywords with that Sub-Service, any Brand ("juvederm lip filler" counts for Lip Filler).
- **Brand / Device** page: keywords with that Brand and no Sub-Service.

Only Class = Service keywords. Exclude other markets (below). Total National Search Volume = sum of what's left. No keywords left: "None in competitor keyword list (check GSC / keyword tool)" and 0.

If a GSC queries export is attached, add "Client GSC Impressions": the sum of impressions for queries that exactly match the page's Relevant Keywords.

## Other markets

The competitor list is full of other cities ("botox miami"). Keep the client's service-area cities; exclude a keyword when either rule fires:

Place detection is precomputed in the bundled All Keywords tab: **Geo Modified = Y** marks a keyword that names a US city, state, ZIP or other place (matched against a gazetteer, with ambiguous single words such as "spring" or "temple" left unflagged; Geo Check shows "Place found" or "Review"). Exclude Geo Modified = Y keywords unless the place is one of the client's service-area cities. Near Me keywords are kept. Only when the person attached a different keyword list, flag places yourself: match a US city / state / country gazetteer, treat a 5-digit number as a ZIP, and leave ordinary words alone.

Record each excluded keyword with its reason: "Other market (Geo Modified)". Neighborhoods made of ordinary words ("river north") get through; the QA step catches the ones that matter.
