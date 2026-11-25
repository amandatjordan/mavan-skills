# New site IA: rules

Constants are at the top of `scripts/ia.py`. Change them there and update this file in the same pull request.

## Pages

**Page names** are each page's own name: the last part of the roadmap's name, so "Neurotoxin > Botox" is "Botox". The Parent column and the Internal links tab use the same names. Blog titles are kept whole. When two roadmap pages share an own name (Neurotoxin > Botox and Laser > Botox), both keep their full roadmap names and a warning asks the SEO to rename them. A CSV page whose name matches a roadmap page's own name is skipped.

One row per roadmap page (blogs included), one per CSV page, and a `/blog` index when any blog is on the roadmap. Pages the roadmap cut for the 50-page cap are not here. Sections are not pages and never appear. A CSV page with the same name as a roadmap page is skipped with a warning.

Order: roadmap order (without blogs), CSV pages, the blog index, then the blogs.

## URL paths

- Lowercase, hyphens, accents removed, text in brackets dropped (flagged in Notes), `+` becomes "plus", `&` becomes "and", no trailing slash. Words are not stripped. The slug is the last segment of the page name.
- **Service, Sub-Service and Brand / Device** pages sit under `/services/` so performance across all services can be tracked with one path filter.
- A Sub-Service or Brand / Device sits **one level under its top-level Service** (`/services/{service}/{child}`), at most 3 segments. A Brand whose parent is a Sub-Service still sits under the top-level Service; the Parent column keeps the real parent and Notes says so.
- `/services/` is **not** added as a page. Add it only if the client wants a hub page with content, and link the Service pages straight from the nav so the hub does not add click depth.
- Home is `/`. About Us, extra pages and Concern pages sit at the root.
- Blog posts: `/blog/prepare-for-{page}` and `/blog/choosing-a-provider-for-{page}`. These are placeholders, because the roadmap never sets titles.
- **CSV pages:** a URL the client gave is used as given (a leading slash is added if missing, a full URL is cut to its path). With none, the slug of the page name is recommended.
- Yellow URL cells are ours (Recommended). A duplicate URL raises a warning.

## Main nav

- **Always Yes:** Home, the blog index. **Always No:** individual blog posts. These cells are not yellow.
- Yes: About Us, Service pages, roadmap extra pages (packages, providers, locations and so on) and CSV pages, except legal / utility pages (name contains privacy, terms, cookie, accessibility, sitemap, disclaimer, hipaa, notice, thank or 404), which are No.
- No: Sub-Service, Brand / Device and Concern pages (reached from their parent page).
- Every other cell is yellow: a recommendation the SEO can change.  There is no limit on how many pages are in the main nav.

## Internal links

The roadmap's Internal links tab, copied as it is with the From and To URLs added. The IA skill adds, removes and changes nothing. It warns about:

- a Service, Sub-Service, Brand / Device or Concern page nothing links to;
- a "Must appear on page" term that is not the anchor of any link to that page (the term is anchor text, so a link is missing);
- a link with no anchor text;
- a link that names a page that is not on the Pages tab.

All of these are fixed in the roadmap.

## SEO QA

The Read Me's first row after the client name tells the SEO to QA both tabs before the workbook goes anywhere: the Pages tab (names, types, parents, URLs, main nav, notes) and the Internal links tab (From and To pages, URLs, anchor text) plus every warning. The script's checks do not replace this. Links not planned anywhere: service pages to the booking page, the blog index to each post, menu and footer links.
