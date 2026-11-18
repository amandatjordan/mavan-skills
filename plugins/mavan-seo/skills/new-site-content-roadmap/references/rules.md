# New site content roadmap: rules

All thresholds are constants at the top of `scripts/roadmap.py`. Change them there and update this file in the same pull request.

## The 50-page cap

`MAX_PAGES = 50`. Home, About Us, extra pages, Service, Sub-Service, Brand / Device and Concern pages and blog posts **all** count. One row is one page or one blog post.

## What is added, in this order

1. **Home** and **About Us**: always. They are not in the keyword sheets.
2. **Extra pages** the SEO named in the preflight (packages, providers, locations, events, financing, treatments by area or age and so on). They are never cut automatically, and the SEO sets each one's priority (High, Medium or Low) in the yellow column. The SEO makes the final decision and can change the priority of any page.
3. **Service** pages, then **Sub-Service**, then **Brand / Device** pages (own-page rows only; "Section on ..." rows are not pages).
4. **Blog** posts, for each Service and Sub-Service page that made the roadmap.
5. **Concern** pages.

Pages are added in that order until 50 is reached. A group is only reached once every row in the groups above it fits. Over the cap, the rest go to the "Cut for the 50-page cap" tab. It starts with an instruction row (the SEO moves rows between it and the Roadmap to make the final list) and has the Roadmap's columns, with the reason last, so a row can be moved as it is. Sections are not listed there: they are in "Sections to cover" on the parent page. Things the client does not offer are not listed anywhere. Blogs for a page that was cut are not listed one by one; one row names those pages.

## Order inside a group

1. Where the page came from: **client-listed** ("Yes" in "Client offers it?" on the research Pages tab; rows left blank or marked No are not used), then **Implied** parents (a Service added because a listed Brand / Device sits under it), then **Suggested** rows (the taxonomy suggested them, the client did not list them, and the SEO confirmed Yes), then **gap-only** services (offered by the client, found only in the gap workbook).
2. **Competitor gap keywords**, highest first (below).
3. **Primary keyword volume**, highest first (national, from the research workbook; never summed).
4. Name, so the order is stable.

## Competitor gap keywords

From the gap workbook's Service opportunities tab: "Keywords with 2+ in top 10 or 1+ in top 3" plus the local version of the same column, for the gap service matched to the page. Two gap services matched to one page are added. A Sub-Service or Brand / Device with no gap service of its own shows its Service's number, marked "inherited", so children of a Service with competitor demand rank ahead of children of one without. A gap-only service shows its own number.

The gap workbook's counts are at the service level, so they say which services competitors win, not which sub-services.

## Gap workbook: who counts

Only gap services the SEO marked **Yes** in "Offered by our client" count. Yes with no research page becomes a gap-only page. No or blank is left off the roadmap and not listed anywhere. A "No" gap service matched to a research page the client listed raises a warning (the two workbooks disagree).

## Primary keywords are for the SEO to check

The primary keyword is the research workbook's highest-volume search for the page. It can be a poor target (for example "face with wrinkles" for Wrinkles / Fine Lines is someone looking at pictures, not looking for a treatment). The Roadmap highlights the column (yellow) for the SEO to replace the keyword or add keywords in the same cell. The script never judges a keyword.

## Must appear on page

The research workbook's "Anchor text for links to this page" for each page is copied to the "Must appear on page" column, so content knows which words other pages will use to link to it and must include them. A Sub-Service or Brand / Device that is only a section on a parent page adds its anchor text to the parent page's cell (links to that topic land on the parent). Blank where the research sheet has none. Home, About Us, extra pages, gap-only pages and blogs have none. Preflight warns when own pages have no anchor text.

## Internal links

Every Service, Sub-Service and Brand / Device page on the Roadmap must receive at least one internal link from another page. The Internal links tab is built in this order:

1. The links on the research Pages tab ("Internal links out (priority)"), kept only when both pages are on the Roadmap. Links to sections, pages the client does not offer and pages that were cut are dropped.
2. Any Service, Sub-Service or Brand / Device page still without a link pointing at it gets one, marked "Added so every page gets a link", from its parent page. If the parent is not on the Roadmap (it is a section, was cut or is not offered), from its Service. If that is not on the Roadmap either, from Home. Services and gap-only pages (no parent) get a link from Home.
3. Each blog links to its page (listed, but a blog link does not count as the link a page must receive).

Every link that is needed has its own row. The anchor text of the research sheet's links is the linked page's first phrase from "Must appear on page" (blank where the research sheet has none). Every other phrase in that cell (the ones a section adds) gets a row of its own: a link to the page with that phrase as the anchor text, from Home or, if Home already links to the page, from the first page on the roadmap that does not, marked "Added so every phrase has a link". A page nothing links to (for example a Concern) gets a row for its first phrase too. The SEO can change the From page of an added row. Concern pages are linked where the research sheet links to them, but are not required to receive a link. If the SEO moves pages between the Roadmap and Cut tabs, the links to and from them have to be updated by hand.

## Blogs

From the bundled `references/blog-taxonomy.xlsx` (Lookup tab, which already applies the Overrides tab). Two posts per Service and Sub-Service: prep / maintenance and choosing a provider. Brand / Device posts exist only where the Overrides tab adds them. A node the taxonomy excludes, or does not contain, gets no blogs and is named in the Read Me warnings. A Sub-Service that is only a section on its parent page still gets its two posts, linked to the parent page. A blog is only listed when its page (or its parent page, for a section) is on the roadmap.

Titles are never set. The writer chooses each post's title and query. Blogs must not promise results.

## Concerns

Last in the order, so they are the first to be cut. The research workbook already limits concerns to the few the client listed.

## Not covered

Pages that need no content from us (Contact, Privacy Policy, Terms, Sitemap and similar), location and city pages unless the SEO lists them as extras, internal links (they stay in the research workbook), and any volume re-check for the client's market.

## Updating the blog taxonomy

Replace `references/blog-taxonomy.xlsx` and raise the plugin version in the same pull request. The script reads the Lookup, Blog Rules and Overrides tabs by name.
