# Audit rules

Rules version: 2026-11-01. It changes the Content Prune & Merge SOP as edited on 2026-10-26 in three places: city copies are decided before any overlap check, merging into the main-city page under 2 clicks (rule 2), concern pages that overlap a service page merge into it (rule 3), and cities come from the list the person confirms. Update the SOP to match. If the person pastes a newer SOP and its rules differ, follow the pasted SOP and list the differences in the report.

`scripts/build.py` applies these rules and `scripts/make_xlsx.py` reads some of the values as exact text to place rows on the workbook's tabs. Anything shown in `code` below is matched by the scripts: change it in the scripts too.

## Audit columns

`work/audit.tsv` (an internal work file, not a tab) has one row per live (200) page, in this order. The workbook's tabs are built from it.

URL | Page Type | Page Type Reason | HTTP Status Code | Internal Linking URLs | Internal Outgoing Links | Title | H1 | URLs with Duplicate H1s | URLs with Duplicate Titles | URLs with Similar Content | Conversions | New Users (GA4) | Sessions | Views (GA4) | No. Keywords | Clicks | Impressions | Referring Domains | Suggested Next Step | Suggested Target | Next Steps | Target URL | Reasoning | Notes

- Conversions = GA4 key events. No. Keywords = number of non-brand queries.
- Duplicate H1s / Titles = how many *other* live pages share the exact text. Similar Content = the crawler's near-duplicate count, blank if the export has none.
- Referring Domains: always blank.
- Next Steps, Target URL and Reasoning stay blank: the SEO decides on the workbook tabs.
- Sort by Page Type (order below), then Impressions high to low.

## Page Type

Values (in this sort order): `Home` | `Service` | `Concern / Condition` | `Service Area / Location` | `Hub / Category Page` | `Blog Post` | `Blog Category / Tag` | `Gallery` | `Author / Archive` | `Not for SEO (contact, legal, etc.)` | `Other`

Apply in order; write the rule used in Page Type Reason.

1. `/` = Home.
2. **The confirmed folder map decides first** (SKILL.md Step 2): a page inside a mapped folder gets that folder's type. Reason: "Folder map: /folder/". A folder's own listing page, or a page that lists a group of services or products (often ~10 words), = Hub / Category Page. A folder of resources or information for existing patients or customers (patient resources, forms, financing) = Not for SEO, not Service. A page inside a Service folder stays Service even when its slug names a city (`/services/botox-riverton/`); the city-in-slug rule below is for root-level pages and folders that are not mapped as Service. Cities come only from `work/cities.json` (SKILL.md Step 2): "separate" cities are location signals, "ignore" cities (usually the main city, when most URLs carry it) never are. These patterns hold on any site: `/tag/`, `/category/` and `/blog/page/N/` = Blog Category / Tag; `/author/` or date archives (`/2024/05/`) = Author / Archive; gallery folders = Gallery. Any folder the map does not cover: the closest type, naming the folder in the reason.
3. **Site signals for root-level pages** (from the classified links, before any slug guess). Many sites, WordPress especially, keep posts and service pages at the root, so these beat the slug rules:
   - Linked from Body links on the blog listing or its pagination = Blog Post. Reason: "Listed on the blog listing".
   - Linked from Body links on a hub page for the client's concerns or conditions = Concern / Condition. Reason: "Listed on the [hub name] hub".
4. **Slug rules for the remaining root-level pages:**
   - Contact, privacy, terms, HIPAA, thank-you, sitemap, login, cart, checkout, account, financing, shop, packages, memberships, booking, events, policies, patient resources, patient information, forms, and any other page that exists for users rather than search = Not for SEO (contact, legal, etc.). About, team, reviews, press = Other. When the slug is one of these words, the type is certain, not a guess: reason `Slug: legal, contact or user page` or `Slug: about, team or reviews page`, never with the words `Root-level`, so the row is not sent to Check page type.
   - Pages named for an area the client serves (`/areas-we-serve/`, `/{city}/`, `/{city}-{business type}/`, where the city is a "separate" city in `work/cities.json`) = Service Area / Location. A service-plus-city slug follows the city-in-slug bullet below.
   - Blog Post if ANY: slug starts with a question word (what, how, why, can, is, are, does, do, should, when, which, where, who); slug has 6+ words; slug or H1 uses blog wording (vs, versus, benefits, guide, tips, cost, explained, what to expect, reasons, aftercare, before and after, myths); the H1 is a question. Reason starts "Root-level, slug reads like a post".
   - A long-slug page that is NOT listed on the blog is a page, not a post: Service, reason "Root-level, long slug but not on the blog - check". This only holds when the links export covers every blog listing page: when the listing pages by query string (`?page=2`, `?e-page-1a2b=2`), its later pages cannot be checked, so a long slug stays a Blog Post.
   - A separate-market city in the slug wins: a slug containing a "separate" city from `work/cities.json` is Service Area / Location even when it also names a service (`/botox-denver/`). Reason `Root-level, city in slug`. An "ignore" city in the slug (often the main city, as in `/botox-springfield-il/`) says nothing: decide the page by the other bullets.
   - Otherwise a short slug naming a service with no city in it = Service, reason `Root-level, no folder match`.
   - Anything else = Other, reason `No rule matched - check`.
5. If the IA audit All Pages tab is attached, use its type for any URL it covers instead, mapped to the values above, reason "From IA audit".

**Reason wording drives the Check page type tab:** make_xlsx.py puts any row whose reason contains `Root-level` or `No rule matched` on the *Check page type* tab, meaning "nothing on the site said what kind of page this is, so the type is a guess from the URL wording; confirm it". Use those words only for real guesses under rule 4, never for folder-map or site-signal types, or for the certain slug words above.

## Suggested Next Step and Suggested Target

Values: `Keep` | `Update` | `Repurpose` | `Merge then Redirect` | `Remove then Redirect` | `Needs Discussion`. Apply in order; the first match wins.

1. Not for SEO pages = Keep.
2. **City copies.** A city copy is a page whose slug is identical to another live page's slug once a "separate" city from `work/cities.json` (and a trailing state code such as `-fl`) is removed, or a pair the person matched by hand in Step 2 (`copy_pairs`). Never decide a copy by fuzzy matching. The copy for the non-main city is decided here, whatever its overlap; the main-city page goes on through the rules.
   - Under 2 clicks (0 or 1) = Merge then Redirect, Suggested Target = the main-city page.
   - 2 clicks or more = Keep: it earns its own traffic.
   - Both carry the city copy flag. Every copy goes on the Per location service pages tab, merged or kept.
   - When the client has only two cities (the main city and one separate city), the Notes also recommend making the main-city page target both cities, for example a title and H1 that name both. With more cities, one page per city can make sense, so leave that out.
3. **Overlap** (references/data.md defines the share): pages that share 30%+ of their impressions:
   - Within a topic group: the keeper = Keep; every other page = Merge then Redirect, Suggested Target = the keeper. Keeper order: Service, then Concern, then Blog Post; the main city before other cities; then most impressions. A page merges only into a keeper it overlaps itself, never through a chain of other pages.
   - A concern page and a service page (any topic group): service pages come first, so the concern page = Merge then Redirect into that service page, with the Notes flag `Concern merges into service page [URL]`. If the concern page overlaps several service pages at 30%+, it merges into the one with the highest share.
4. Blog Post with 0 clicks and under 50 impressions = Remove then Redirect, Suggested Target = the service page in the post's confirmed topic group with the most impressions, otherwise the blog listing page.
5. Blog Post getting impressions for commercial searches with no service page in its topic group = Repurpose. Find the candidates in code first: Blog Posts with no service page in their topic group whose queries contain a city from `work/cities.json` (main or separate), "near me", or a price word (cost, price, prices, how much). Then judge only those candidates: a query is commercial when it is someone looking to buy or book, not to learn. Never start from a list of treatment names: the site's own services come from its confirmed folder map, not from an assumed list.
6. Service page named after a brand or product while its queries are for the treatment or problem = Update.
7. Everything else = Keep.

Also:
- Suggested Target is always a full URL of a live page whose own suggestion is Keep, Update, Repurpose or Needs Discussion. Follow the chain until it lands on one.
- No rule sets Needs Discussion. Use it only for a business decision the reviewer cannot make alone (for example a service the client may no longer offer), and mark it "judgment" in Notes.
- Thin stubs (under ~15 words) that duplicate a real page's intent merge into that page even below the 30% bar; say "judgment" in Notes.
- Every call beyond the seven rules (a "near me" post with under 30% overlap, a blog matching a concern page, a location page that overlaps the homepage) is marked "judgment" in Notes so the reviewer can find it.

## Notes

Start with `Suggested because: ` and the fixed sentence for the rule that decided the row, filled in code, then flags joined with `; `. Write your own sentence only on rows marked "judgment".

| Rule | Sentence after `Suggested because: ` |
| --- | --- |
| 1 | `Not a page for search, so it stays.` |
| 2, under 2 clicks | `City copy of [URL] with [N] click(s), so it merges into the main-city page.` |
| 2, 2+ clicks | `City copy of [URL], but it earns [N] clicks of its own.` |
| 3, keeper | `Strongest page in its topic group; [N] page(s) merge into it.` |
| 3, merged | `Shares [N]% of its impressions with [URL], the page kept for this topic.` |
| 3, concern into service | `Concern page sharing [N]% of its impressions with service page [URL].` |
| 4 | `Blog post with 0 clicks and [N] impression(s).` |
| 5 | `Blog post showing for buying searches such as "[query]", with no service page on the topic.` |
| 6 | `Named for a brand or product, but searchers use "[query]".` |
| 7 | `No rule called for a change.` |

Flag wording the scripts read (copy exactly, filling the brackets):

- `Competes with [URL] for "[top shared query]" ([N]% shared)`: same topic group, or a concern and a service page, with 30%+ shared impressions on the smaller page (references/data.md, Overlap).
- `Blog outranks service page [URL]`: a blog on a treatment gets more clicks than that treatment's service page.
- `0 clicks, under 50 impressions`
- `[City]-style city copy of [URL]`: on every rule-2 row, merged or kept, naming the main-city page (keep the words `city copy of` exactly).
- `Concern merges into service page [URL]`: on every concern page merged into a service page under rule 3 (plain information).
- `Already redirected to by [N] old URL(s)`: from the redirects export.
- `In main menu`: linked from a Nav-class link (menu by CSS/link path, not the crawler's location label). It puts a Merge or Remove row on the Menu cleanup tab; on a Keep row it is plain information.

Other flags (plain words, not read by the scripts): "Only linked from blog pagination", "Canonical points to [URL] which 404s - fix the canonical", "Canonical points to [URL] which redirects back to this page - fix the canonical" (take both from `work/canonical_issues.csv`; the redirect-back case is common after a duplicate slug such as `/page-results/` canonicalizing to `/page-results-2/`), "Uppercase duplicate of [URL]", "If the URL changes, update anything redirecting to it" (every Repurpose row), "No GSC or GA4 data in the window".

Consistency: a Keep row that carries a Competes flag says "kept by default (rule 7), but it overlaps with the page flagged below - review whether both should stay". A keeper says how many pages are suggested to merge or redirect into it. Notes never contradict the suggestion.

## Junk folders

A folder is a junk candidate when (a) it matches a known auto-generated pattern: `/tag/`, `/category/`, `/author/`, date archives (`/2024/05/`), `/page/N/` pagination outside the blog listing, `/attachment/`, a folder name containing "category" or "archive", or the platform's equivalent (for example Shopify `/blogs/{blog}/tagged/`); OR (b) 80%+ of its live pages have ALL of: 0 clicks and under 10 impressions, under 150 content words or titles/H1s identical apart from one word, and no Body links from pages outside the folder. One-page-per-photo gallery folders count when they meet (b).

- Include archive URLs that are in `work/not_in_crawl.tsv` or in the crawl's sitemap data (they are often missing from a link crawl). Make no live requests to find more.
- Junk pages get no audit row; each folder gets one wildcard redirect (see redirects-qa.md). A page inside a junk folder with 5+ clicks or any conversions gets its own audit row.
- Wildcard target: the blog listing for blog archives, the main gallery page for gallery entries, the team or about page for author archives. Never a target the pattern itself matches.
- Leave `/blog/page/N/` alone when it is the only internal path to older posts or canonicalizes to the listing.
- Pagination query URLs (`?e-page-1a2b=2`, `?page=3`, `?paged=2`) canonicalize to the listing: they get no audit row and no redirect.
- For each folder report: rule matched, page count, total impressions, 5 example URLs, suggested wildcard target. Targets: the blog listing for tag, category and author folders, the gallery page for gallery folders, the testimonials page for testimonial categories. The person picks which folders ARE junk (SKILL.md Step 4); anything not picked stays in the audit as normal pages.

## Workbook README

`scripts/make_xlsx.py` reads this table into the workbook's README tab, so the README always matches these rules. Change a rule above and its row here together. Rows show only for tabs the run produced. Keep the Tab names exactly as they are: they are the workbook's tab names.

| Tab | Rule Claude applied | What you need to QA | Handoff to |
| --- | --- | --- | --- |
| Junk folders | Auto-generated archive folders (for example gallery photo pages, tag and category archives) full of thin pages that earn no clicks. | Confirm each folder is really auto-generated and none of its pages earn real traffic. Confirm the redirect target. The redirects are in the dev handoff. | Dev |
| Remove pages | Blog post with 0 clicks and under 50 impressions in the window. | Confirm the post has nothing worth keeping (backlinks, conversions). Confirm the redirect goes to the closest page on the same topic. The redirects are in the dev handoff. | Dev |
| All redirects - Handoff to Dev (old redirect rows) | Existing redirect whose target is not a live page, or that goes through a chain of redirects. | Check each target URL is live and is the right page. This tab has no separate QA copy, so edit it directly. | Dev |
| Redirects needing a target | Old URL with searches or links, but no live page with the same slug, so no target was guessed. | Pick a live page for each one and add the row to the dev handoff. | Dev (after SEO fills in) |
| Merge pages | Page shares 30% or more of its searches with a stronger page on the same topic, or a concern page shares 30% or more with a service page. | Confirm the page we keep is the right one. Fill in the unique content to copy over. | Content, then Dev |
| Per location service pages | Page that copies another page for a different location (same URL once the location is removed). Under 2 clicks: merge into the main page. 2 clicks or more: keep. | Confirm each pair is really a copy and the Merge or Keep call. Fill in the unique content on Merge rows. | Content, then Dev |
| Redirect after merge | A redirect for every merged page. | Confirm each target matches the merge tabs. Send only after the merges are live. | Dev |
| Menu cleanup | Menu item that points to a page being merged or removed, or a menu link that points to a URL that redirects. | Confirm the replacement page. Do this after the merges are live. | Dev |
| Update pages | Service page named after a brand or device, but most of its searches are for the treatment or problem. | Write the new title, H1 and first sentence. Keep the brand name only as a supporting term. | Content |
| Repurpose pages | Blog post getting buying searches (a location, cost or "near me" in the search) with no service page on the topic. | Decide what each post becomes and write it in the tab. | Content (after SEO decides) |
| Blog beats service | Blog post that gets more clicks than the service page on the same topic. | Decide what each one needs and write it in the tab. | Content (after SEO decides) |
| Needs discussion | A business decision the audit cannot make (for example a service the client may no longer offer). | Ask the client and record the answer. | Nobody (SEO only) |
| Check page type | Page type is a guess from the URL because nothing on the site (menu, blog listing, folder) says what kind of page it is. | Correct the page type. A different type can change the recommendation. | Nobody (SEO only) |
| Kept pages | No rule applied, or the page is for visitors, not search. | Check the reason. If you disagree, type the change you want. | Nobody (SEO only) |
