# Audit rules

Rules version: 2026-11-01. It changes the Content Prune & Merge SOP as edited on 2026-10-26 in three places: city copies are Needs Discussion before any overlap check (rule 2), concern pages that overlap a service page merge into it (rule 3), and cities come from the list the person confirms. Update the SOP to match. If the person pastes a newer SOP and its rules differ, follow the pasted SOP and list the differences in the report.

The sheet's formulas read some of these values as exact text. Anything shown in `code` below is matched by a formula or a dropdown: copy it character for character.

## Audit tab columns

One row per live (200) page, in this order. Column A (Area) is a formula; rows are written from column B.

URL | Page Type | Page Type Reason | HTTP Status Code | Internal Linking URLs | Internal Outgoing Links | Title | H1 | URLs with Duplicate H1s | URLs with Duplicate Titles | URLs with Similar Content | Conversions | New Users (GA4) | Sessions | Views (GA4) | No. Keywords | Clicks | Impressions | Referring Domains | Suggested Next Step | Suggested Target | Next Steps | Target URL | Reasoning | Notes

- Conversions = GA4 key events. No. Keywords = number of non-brand queries.
- Duplicate H1s / Titles = how many *other* live pages share the exact text. Similar Content = the crawler's near-duplicate count, blank if the export has none.
- Referring Domains: always leave blank. The column stays in the sheet but is not filled or mentioned.
- Leave blank for a person: Next Steps, Target URL, Reasoning.
- Sort by Page Type (order below), then Impressions high to low.

## Page Type

Values (a dropdown, in this sort order): `Home` | `Service` | `Concern / Condition` | `Service Area / Location` | `Hub / Category Page` | `Blog Post` | `Blog Category / Tag` | `Gallery` | `Author / Archive` | `Not for SEO (contact, legal, etc.)` | `Other`

Apply in order; write the rule used in Page Type Reason.

1. `/` = Home.
2. **The confirmed folder map decides first** (SKILL.md Step 2): a page inside a mapped folder gets that folder's type. Reason: "Folder map: /folder/". A folder's own listing page, or a page that lists a group of services or products (often ~10 words), = Hub / Category Page. A folder of resources or information for existing patients or customers (patient resources, forms, financing) = Not for SEO, not Service. A page inside a Service folder stays Service even when its slug names a city (`/services/botox-tampa/`); the city-in-slug rule below is for root-level pages and folders that are not mapped as Service. Cities come only from `work/cities.json` (SKILL.md Step 2): "separate" cities are location signals, "ignore" cities (usually the main city, when most URLs carry it) never are. These patterns hold on any site: `/tag/`, `/category/` and `/blog/page/N/` = Blog Category / Tag; `/author/` or date archives (`/2024/05/`) = Author / Archive; gallery folders = Gallery. Any folder the map does not cover: the closest type, naming the folder in the reason.
3. **Site signals for root-level pages** (from the classified links, before any slug guess). Many sites, WordPress especially, keep posts and service pages at the root, so these beat the slug rules:
   - Linked from Body links on the blog listing or its pagination = Blog Post. Reason: "Listed on the blog listing".
   - Linked from Body links on a hub page for the client's concerns or conditions = Concern / Condition. Reason: "Listed on the [hub name] hub".
4. **Slug rules for the remaining root-level pages:**
   - Contact, privacy, terms, HIPAA, thank-you, sitemap, login, cart, checkout, account, financing, shop, packages, memberships, booking, events, policies, patient resources, patient information, forms, and any other page that exists for users rather than search = Not for SEO (contact, legal, etc.). About, team, reviews, press = Other. When the slug is one of these words, the type is certain, not a guess: reason `Slug: legal, contact or user page` or `Slug: about, team or reviews page`, never with the words `Root-level`, so the row is not sent to Check page type.
   - Pages named for an area the client serves (`/areas-we-serve/`, `/{city}/`, `/{city}-{business type}/`, where the city is a "separate" city in `work/cities.json`) = Service Area / Location. A service-plus-city slug follows the city-in-slug bullet below.
   - Blog Post if ANY: slug starts with a question word (what, how, why, can, is, are, does, do, should, when, which, where, who); slug has 6+ words; slug or H1 uses blog wording (vs, versus, benefits, guide, tips, cost, explained, what to expect, reasons, aftercare, before and after, myths); the H1 is a question. Reason starts "Root-level, slug reads like a post".
   - A long-slug page that is NOT listed on the blog is a page, not a post: Service, reason "Root-level, long slug but not on the blog - check".
   - A separate-market city in the slug wins: a slug containing a "separate" city from `work/cities.json` is Service Area / Location even when it also names a service (`/botox-denver/`). Reason `Root-level, city in slug`. An "ignore" city in the slug (often the main city, as in `/botox-brandon-fl/`) says nothing: decide the page by the other bullets.
   - Otherwise a short slug naming a service with no city in it = Service, reason `Root-level, no folder match`.
   - Anything else = Other, reason `No rule matched - check`.
5. If the IA audit All Pages tab is attached, use its type for any URL it covers instead, mapped to the values above, reason "From IA audit".

**Reason wording drives the sheet:** the Area formula tags any reason containing `Root-level` or `No rule matched` as *Check page type*, meaning "nothing on the site said what kind of page this is, so the type is a guess from the URL wording; confirm it". Use those words only for real guesses under rule 4, never for folder-map or site-signal types, or for the certain slug words above.

## Suggested Next Step and Suggested Target

Values (same as the Next Steps dropdown): `Keep` | `Update` | `Repurpose` | `Merge then Redirect` | `Remove then Redirect` | `Needs Discussion`. Apply in order; the first match wins.

1. Not for SEO pages = Keep.
2. **City copies** = Needs Discussion (a policy decision, not a merge), whatever their overlap or clicks. A city copy is a page whose slug is identical to another live page's slug once a "separate" city from `work/cities.json` (and a trailing state code such as `-fl`) is removed, or a pair the person matched by hand in Step 2 (`copy_pairs`). The copy for the non-main city is the one flagged; the main-city page goes on through the rules. Never decide a copy by fuzzy matching.
3. **Overlap** (references/data.md defines the share): pages that share 30%+ of their impressions:
   - Within a topic group: the keeper = Keep; every other page = Merge then Redirect, Suggested Target = the keeper. Keeper order: Service, then Concern, then Blog Post; the main city before other cities; then most impressions. A page merges only into a keeper it overlaps itself, never through a chain of other pages.
   - A concern page and a service page (any topic group): service pages come first, so the concern page = Merge then Redirect into that service page, with the Notes flag `Concern merges into service page [URL]`. If the concern page overlaps several service pages at 30%+, it merges into the one with the highest share.
4. Blog Post with 0 clicks and under 50 impressions = Remove then Redirect, Suggested Target = the service page in the post's confirmed topic group with the most impressions, otherwise the blog listing page.
5. Blog Post getting impressions for commercial searches (treatment + city, "near me", cost) with no service page in its topic group = Repurpose.
6. Service page named after a brand or product while its queries are for the treatment or problem = Update.
7. Everything else = Keep.

Also:
- Suggested Target is always a full URL of a live page whose own suggestion is Keep, Update, Repurpose or Needs Discussion. Follow the chain until it lands on one. When a merge target turns out to be a city copy (rule 2), point the merge at the copy's main-city page instead and mark it "judgment" in Notes.
- Thin stubs (under ~15 words) that duplicate a real page's intent merge into that page even below the 30% bar; say "judgment" in Notes.
- Every call beyond the seven rules (a "near me" post with under 30% overlap, a blog matching a concern page, a location page that overlaps the homepage) is marked "judgment" in Notes so the reviewer can find it.

## Notes

Start with `Suggested because: ` and one short sentence, then flags joined with `; `. Flag wording the Area formula reads (copy exactly, filling the brackets):

- `Competes with [URL] for "[top shared query]" ([N]% shared)`: same topic group, or a concern and a service page, with 30%+ shared impressions on the smaller page (references/data.md, Overlap).
- `Blog outranks service page [URL]`: a blog on a treatment gets more clicks than that treatment's service page.
- `0 clicks, under 50 impressions`
- `[City]-style city copy of [URL]`: on every rule-2 row, naming the main-city page (the formula looks for `city copy of`; keep those words exactly).
- `Concern merges into service page [URL]`: on every concern page merged into a service page under rule 3 (plain information; the row's Area is Merge pages from its suggestion).
- `Already redirected to by [N] old URL(s)`: from the redirects export.
- `In main menu`: linked from a Nav-class link (menu by CSS/link path, not the crawler's location label). The sheet only counts it toward the Menu cleanup Area on Merge/Remove rows, and `Already redirected to by` toward Old redirects likewise; on a Keep row they are plain information.

Other flags (plain words, not read by formulas): "Only linked from blog pagination", "Canonical points to [URL] which 404s - fix the canonical", "Canonical points to [URL] which redirects back to this page - fix the canonical" (take both from `work/canonical_issues.csv`; the redirect-back case is common after a duplicate slug such as `/page-results/` canonicalizing to `/page-results-2/`), "Uppercase duplicate of [URL]", "If the URL changes, update anything redirecting to it" (every Repurpose row), "No GSC or GA4 data in the window".

Consistency: a Keep row that carries a Competes flag says "kept by default (rule 7), but it overlaps with the page flagged below - review whether both should stay". A keeper says how many pages are suggested to merge or redirect into it. Notes never contradict the suggestion.

## Junk folders

A folder is a junk candidate when (a) it matches a known auto-generated pattern: `/tag/`, `/category/`, `/author/`, date archives (`/2024/05/`), `/page/N/` pagination outside the blog listing, `/attachment/`, a folder name containing "category" or "archive", or the platform's equivalent (for example Shopify `/blogs/{blog}/tagged/`); OR (b) 80%+ of its live pages have ALL of: 0 clicks and under 10 impressions, under 150 content words or titles/H1s identical apart from one word, and no Body links from pages outside the folder. One-page-per-photo gallery folders count when they meet (b).

- Include archive URLs that are in `work/not_in_crawl.tsv` or in the crawl's sitemap data (they are often missing from a link crawl). Make no live requests to find more.
- Junk pages get no Audit row; each folder gets one wildcard on Existing Redirects (see redirects-qa.md). A page inside a junk folder with 5+ clicks or any conversions gets its own Audit row.
- Wildcard target: the blog listing for blog archives, the main gallery page for gallery entries, the team or about page for author archives. Never a target the pattern itself matches.
- Leave `/blog/page/N/` alone when it is the only internal path to older posts or canonicalizes to the listing.
- Pagination query URLs (`?e-page-1a2b=2`, `?page=3`, `?paged=2`) canonicalize to the listing: they get no audit row and no redirect.
- For each folder report: rule matched, page count, total impressions, 5 example URLs, suggested wildcard target. Targets: the blog listing for tag, category and author folders, the gallery page for gallery folders, the testimonials page for testimonial categories. The person picks which folders ARE junk before the sheet is written (SKILL.md Step 5); anything not picked stays in the audit as normal pages.

## Review triage

For the report (nothing is written to the sheet): split the Audit rows into two piles so the reviewer spends time where judgment is needed.

- **Skim list:** Suggested Next Step is Keep, the page is Not for SEO or has meaningful clicks (the top quarter of pages by clicks; when that bar is 0 clicks, as on low-traffic sites, use 1 click or more and say so in the report), and Notes has no Competes, Blog outranks service page or city copy flag. The reviewer checks the row looks right and copies the suggestion into Next Steps.
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
- Write every count from the data, in code, with correct plurals ("1 click", "2 clicks", "1 page", "3 pages"). Name the exact pages instead of vague phrases ("check the 1 in 4"). Never hardcode a number into text.
- Never write a Recommendations row about canonical problems; they are noted only on the affected page.
- The links export may not include blog listing or pagination pages, so root-level posts can then be typed only from the slug rules. Keep the Check page type row and say how many pages are affected. The reviewer may not know the label, so its Problem says in plain words what it means, for example: "For 64 pages nothing on the site (menu, blog listing or folder) says what kind of page it is, so the type is a guess from the URL wording; 56 are guessed as blog posts and 8 as location pages, for example [URL]." Its Do this says to correct any wrong Page Type before filling in Next Steps, because the suggestion depends on it.
- The same goes for any other label a reviewer may not know (city copy, keeper, competes): say what it means in the Problem sentence.
