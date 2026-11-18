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

Pages are added in that order until 50 is reached. A group is only reached once every row in the groups above it fits. Over the cap, the rest go to the Not on the roadmap tab with their group. Blogs for a page that was cut are not listed one by one; one row names those pages.

## Order inside a group

1. Where the page came from: **client-listed** ("Yes" on the research Pages tab), then **Implied** parents (a Service added because a listed Brand / Device sits under it), then rows the client **confirmed** Yes on the Confirm with client tab, then **gap-only** services (offered by the client, found only in the gap workbook).
2. **Competitor gap keywords**, highest first (below).
3. **Primary keyword volume**, highest first (national, from the research workbook; never summed).
4. Name, so the order is stable.

## Competitor gap keywords

From the gap workbook's Service opportunities tab: "Keywords with 2+ in top 10 or 1+ in top 3" plus the local version of the same column, for the gap service matched to the page. Two gap services matched to one page are added. A Sub-Service or Brand / Device with no gap service of its own shows its Service's number, marked "inherited", so children of a Service with competitor demand rank ahead of children of one without. A gap-only service shows its own number.

The gap workbook's counts are at the service level, so they say which services competitors win, not which sub-services.

## Gap workbook: who counts

Only gap services the SEO marked **Yes** in "Offered by our client" count. Yes with no research page becomes a gap-only page. No or blank is left off the roadmap and listed with the reason. A "No" gap service matched to a research page the client listed raises a warning (the two workbooks disagree).

## Confirm with client rows

On the research workbook's Confirm with client tab, only rows marked **Yes** with "Would be" = Own page are added. No and blank rows are listed on Not on the roadmap with the reason.

## Blogs

From the bundled `references/blog-taxonomy.xlsx` (Lookup tab, which already applies the Overrides tab). Two posts per Service and Sub-Service: prep / maintenance and choosing a provider. Brand / Device posts exist only where the Overrides tab adds them. A node the taxonomy excludes, or does not contain, gets no blogs and is listed. A Sub-Service that is only a section on its parent page still gets its two posts, linked to the parent page. A blog is only listed when its page (or its parent page, for a section) is on the roadmap.

Titles are never set. The writer chooses each post's title and query. Blogs must not promise results.

## Concerns

Last in the order, so they are the first to be cut. The research workbook already limits concerns to the few the client listed.

## Not covered

Pages that need no content from us (Contact, Privacy Policy, Terms, Sitemap and similar), location and city pages unless the SEO lists them as extras, internal links (they stay in the research workbook), and any volume re-check for the client's market.

## Updating the blog taxonomy

Replace `references/blog-taxonomy.xlsx` and raise the plugin version in the same pull request. The script reads the Lookup, Blog Rules and Overrides tabs by name.
