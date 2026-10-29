# Audit rules

Rules version: 2026-10-26 (matches the Content Prune & Merge SOP as edited that day). If the person pastes a newer SOP and its rules differ, follow the pasted SOP and list the differences in the report.

The sheet's formulas read some of these values as exact text. Anything shown in `code` below is matched by a formula or a dropdown: copy it character for character.

## Audit tab columns

One row per live (200) page, in this order. Column A (Area) is a formula; rows are written from column B.

URL | Page Type | Page Type Reason | HTTP Status Code | Internal Linking URLs | Internal Outgoing Links | Title | H1 | URLs with Duplicate H1s | URLs with Duplicate Titles | URLs with Similar Content | Conversions | New Users (GA4) | Sessions | Views (GA4) | No. Keywords | Clicks | Impressions | Referring Domains | Suggested Next Step | Suggested Target | Next Steps | Target URL | Reasoning | Notes

- Conversions = GA4 key events. No. Keywords = number of non-brand queries.
- Duplicate H1s / Titles = how many *other* live pages share the exact text. Similar Content = the crawler's near-duplicate count, blank if the export has none.
- Referring Domains = from the bulk backlink export when one was given (matched on the normalized URL), otherwise blank for a person.
- Leave blank for a person: Next Steps, Target URL, Reasoning.
- Sort by Page Type (order below), then Impressions high to low.

## Page Type

Values (a dropdown, in this sort order): `Home` | `Service` | `Concern / Condition` | `Service Area / Location` | `Hub / Category Page` | `Blog Post` | `Blog Category / Tag` | `Gallery` | `Author / Archive` | `Not for SEO (contact, legal, etc.)` | `Other`

Apply in order; write the rule used in Page Type Reason.

1. `/` = Home.
2. **The confirmed folder map decides first** (SKILL.md Step 2): a page inside a mapped folder gets that folder's type. Reason: "Folder map: /folder/". A folder's own listing page, or a page that lists a group of services or products (often ~10 words), = Hub / Category Page. These patterns hold on any site: `/tag/`, `/category/` and `/blog/page/N/` = Blog Category / Tag; `/author/` or date archives (`/2024/05/`) = Author / Archive; gallery folders = Gallery. Any folder the map does not cover: the closest type, naming the folder in the reason.
3. **Site signals for root-level pages** (from the classified links, before any slug guess). Many sites, WordPress especially, keep posts and service pages at the root, so these beat the slug rules:
   - Linked from Body links on the blog listing or its pagination = Blog Post. Reason: "Listed on the blog listing".
   - Linked from Body links on a hub page for the client's concerns or conditions = Concern / Condition. Reason: "Listed on the [hub name] hub".
4. **Slug rules for the remaining root-level pages:**
   - Contact, privacy, terms, HIPAA, thank-you, sitemap, login, cart, checkout, account, financing, shop, packages, memberships, booking, events, policies, and any other page that exists for users rather than search = Not for SEO (contact, legal, etc.). About, team, reviews = Other.
   - Pages named for an area the client serves (`/areas-we-serve/`, `/{city}/`, `/{city}-{business type}/`) = Service Area / Location. A service-plus-city slug follows the city-in-slug bullet below.
   - Blog Post if ANY: slug starts with a question word (what, how, why, can, is, are, does, do, should, when, which, where, who); slug has 6+ words; slug or H1 uses blog wording (vs, versus, benefits, guide, tips, cost, explained, what to expect, reasons, aftercare, before and after, myths); the H1 is a question. Reason starts "Root-level, slug reads like a post".
   - A long-slug page that is NOT listed on the blog is a page, not a post: Service, reason "Root-level, long slug but not on the blog - check".
   - A city in the slug always wins: a slug containing a city or area name (the client's main city, the cities on the folder map's location pages, or any place name the person confirmed) is Service Area / Location even when it also names a service (`/botox-denver/`). Reason `Root-level, city in slug`.
   - Otherwise a short slug naming a service with no city in it = Service, reason `Root-level, no folder match`.
   - Anything else = Other, reason `No rule matched - check`.
5. If the IA audit All Pages tab is attached, use its type for any URL it covers instead, mapped to the values above, reason "From IA audit".

**Reason wording drives the sheet:** the Area formula tags any reason containing `Root-level` or `No rule matched` as *Check page type*. Use those words only for slug-rule guesses (rule 4), never for folder-map or site-signal types.

## Suggested Next Step and Suggested Target

Values (same as the Next Steps dropdown): `Keep` | `Update` | `Repurpose` | `Merge then Redirect` | `Remove then Redirect` | `Needs Discussion`. Apply in order; the first match wins.

1. Not for SEO pages = Keep.
2. Two or more pages about the same treatment or topic that share 30%+ of their non-brand query impressions (measured on the smaller page, within a topic group): the keeper = Keep; every other page in the group = Merge then Redirect, Suggested Target = the keeper. Keeper order: Service, then Concern, then Blog Post; the main city before other cities; then most impressions.
3. The same service with a separate page per city or area, where the extra page has 0 clicks = Needs Discussion (a policy decision, not a merge).
4. Blog Post with 0 clicks and under 50 impressions = Remove then Redirect, Suggested Target = the matching service page by treatment, otherwise the blog listing page.
5. Blog Post getting impressions for commercial searches (treatment + city, "near me", cost) with no matching service page = Repurpose.
6. Service page named after a brand or product while its queries are for the treatment or problem = Update.
7. Everything else = Keep.

Also:
- Suggested Target is always a full URL of a live page whose own suggestion is Keep, Update, Repurpose or Needs Discussion. Follow the chain until it lands on one.
- Thin stubs (under ~15 words) that duplicate a real page's intent merge into that page even below the 30% bar; say "judgment" in Notes.
- Every call beyond the seven rules (a "near me" post with under 30% overlap, a blog matching a concern page, a location page that overlaps the homepage) is marked "judgment" in Notes so the reviewer can find it.

## Notes

Start with `Suggested because: ` and one short sentence, then flags joined with `; `. Flag wording the Area formula reads (copy exactly, filling the brackets):

- `Competes with [URL] for "[top shared query]" ([N]% shared)`: same treatment or topic, 30%+ shared non-brand impressions on the smaller page.
- `Blog outranks service page [URL]`: a blog on a treatment gets more clicks than that treatment's service page.
- `0 clicks, under 50 impressions`
- `[City]-style city copy of [URL]`: the same service has a page per city (the formula looks for `city copy of`; keep those words exactly).
- `Already redirected to by [N] old URL(s)`: from the redirects export.
- `In main menu`: linked from a Nav-class link (menu by CSS/link path, not the crawler's location label). The sheet only counts it toward the Menu cleanup Area on Merge/Remove rows, and `Already redirected to by` toward Old redirects likewise; on a Keep row they are plain information.

Other flags (plain words, not read by formulas): "Only linked from blog pagination", "Canonical points to [URL] which 404s - fix the canonical", "Uppercase duplicate of [URL]", "If the URL changes, update anything redirecting to it" (every Repurpose row), "No GSC or GA4 data in the window".

Consistency: a Keep row that carries a Competes flag says "kept by default (rule 7), but it overlaps with the page flagged below - review whether both should stay". A keeper says how many pages are suggested to merge or redirect into it. Notes never contradict the suggestion.

## Junk folders

A folder is a junk candidate when (a) it matches a known auto-generated pattern: `/tag/`, `/category/`, `/author/`, date archives (`/2024/05/`), `/page/N/` pagination outside the blog listing, `/attachment/`, a folder name containing "category" or "archive", or the platform's equivalent (for example Shopify `/blogs/{blog}/tagged/`); OR (b) 80%+ of its live pages have ALL of: 0 clicks and under 10 impressions, under 150 content words or titles/H1s identical apart from one word, and no Body links from pages outside the folder. One-page-per-photo gallery folders count when they meet (b).

- Include archive URLs found only in the XML sitemap (they are often missing from a link crawl).
- Junk pages get no Audit row; each folder gets one wildcard on Existing Redirects (see redirects-qa.md). A page inside a junk folder with 5+ clicks, conversions or backlinks gets its own Audit row.
- Wildcard target: the blog listing for blog archives, the main gallery page for gallery entries, the team or about page for author archives. Never a target the pattern itself matches.
- Leave `/blog/page/N/` alone when it is the only internal path to older posts or canonicalizes to the listing.
- For each folder report: rule matched, page count, clicks, impressions, 5 example URLs, wildcard target. The person confirms which folders are junk before the sheet is written (SKILL.md Step 5).

## Review triage

For the report (nothing is written to the sheet): split the Audit rows into two piles so the reviewer spends time where judgment is needed.

- **Skim list:** Suggested Next Step is Keep, the page is Not for SEO or has meaningful clicks (set the bar per client, for example the top quarter of pages by clicks), and Notes has no Competes, Blog outranks service page or city copy flag. The reviewer checks the row looks right and copies the suggestion into Next Steps.
- **Review queue:** everything else, in particular every Merge, Remove, Repurpose, Update and Needs Discussion suggestion, any flagged row, any Keep with no clicks that is not Not for SEO, and any row whose Page Type Reason contains `Root-level` or `No rule matched`.

Every row still needs a Next Steps value, skim list included. Report both counts.

## Recommendations tab

6 to 12 rows, one fix per row, highest priority first. Columns written from B5: Priority | Area | Problem | Do this. The #, Pages and Where to find columns fill themselves.

- Priority: exactly one of `High` | `Medium` | `Low` | `Pass` | `Info`. High = losing traffic now or will break something (pages competing for the same searches, redirect chains, junk folders at scale). Medium = clear gain, not urgent. Low = nice to have. Pass = checked, no problem (include so the reviewer knows it was checked). Info = context only.
- Area: exactly one of `Junk folders` | `Merge pages` | `Remove pages` | `Repurpose pages` | `Update pages` | `Needs discussion` | `Blog beats service` | `City copies` | `Menu cleanup` | `Old redirects` | `Check page type`. Each label once at most, and only if at least one Audit row will carry it (Junk folders: only if a wildcard row exists). The formula derives Area from Suggested Next Step and the Notes flags above, so check the label against what the rows actually say.
- Problem: one sentence with the key number and one example URL, in plain words.
- Do this: one or two short instructions, naming the exact target URL when there is one.
- Point links at service, concern or location pages; recommend links to blog posts nowhere.
- Leave page counts and locations to the sheet.
