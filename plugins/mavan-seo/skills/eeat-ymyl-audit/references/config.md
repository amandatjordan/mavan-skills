# config.json

Written by Claude (SKILL.md Step 4) from the page type source (Step 2) and the header row of the crawl export. Column names must match the crawl export exactly (not case sensitive). The person is never asked for any of it.

```json
{
  "columns": {
    "url": "Address",
    "status": "Status Code",
    "indexability": "Indexability",
    "body": "Body 1",
    "author": "Author 1",
    "reviewer": "Reviewer 1",
    "published": "Published 1",
    "updated": "Updated 1",
    "schema": "Schema 1",
    "testimonials": "Testimonials 1",
    "before_after": "Before After 1",
    "rating": "Rating 1",
    "faq": "FAQ 1"
  },
  "page_type_source": {"file": "work/ia_audit.xlsx", "sheet": "All Pages", "url_column": "URL", "type_column": "Page Type"},
  "page_types": [
    {"name": "Condition", "labels": ["Concern", "Condition"], "role": "condition"},
    {"name": "Service", "labels": ["Service"], "role": "service"},
    {"name": "Blog", "labels": ["Blog", "Blog Post"], "role": "blog"}
  ],
  "credible_domains": [],
  "body_markers": {},
  "credential_terms": [],
  "experience_terms": [],
  "content_link_positions": ["Content"],
  "own_domains": [],
  "non_citation_hosts": []
}
```

## Fields

- **columns.body** is required. When the crawler writes one column per match (Sitebulb's "all matched items" gives Body 1, Body 2, ...), name the base with ` *` (`"Body *"`, `"Schema *"`): the script joins the numbered columns in order. Leave any other column out, or set it to `""`, when the site does not have it ("not on this site"): it is shown as n/a and is not counted as missing. `url`, `status` and `indexability` are found automatically in a Screaming Frog or Sitebulb export when left out.
- **page_type_source** says where each page's type comes from. Either the person's IA audit or Content Prune & Merge workbook (`file`, optional `sheet`, `url_column`, `type_column`; xlsx or csv), or the Page Type column the person added to the site crawl export with the extraction columns (`{"column": "Page Type"}`). Use only the person's workbook or labels, never page types worked out from the site. URLs are compared without the scheme, `www.` or a trailing slash.
- **page_types** give each audited type a `name` and the `labels` from the source that belong to it (the name itself always counts as a label; matching ignores case). A page whose label belongs to no page type is left out, and preflight lists those labels with counts. `paths` (URL path substrings, first match wins) are a fallback only for pages the source does not label; leave them out unless the person asks for them. Pages that match nothing are left out and listed in the preflight warnings. The audit covers concerns/conditions, services and blogs, plus any type the person named.
- **credential_terms** are added to the built-in list: MD, DO, DDS, DMD, NP, PA, PA-C, RN, PhD, FACS, FAAD, board-certified, board certified. Add terms you see on the sample pages (for example FNP or FACOG). Terms of five letters or fewer written in capitals match capitals only, so "md" in ordinary text does not count. Credentials are looked for in the body, author and reviewer text.
- **experience_terms** are extra phrases to count as years of experience. A number of years followed by "experience" or "practice" is always recognised ("18 years of experience").
- **content_link_positions** are the Link Position values that count as citations. Menus and footers are left out. Ignored when the outlinks export has no link position column (preflight warns).
- **non_citation_hosts** are extra hosts whose links are never citations and are left out of every link check, on top of booking platforms, Google, and address or phone anchors (`rules.md`). Add a host only after checking in Claude in Chrome that its links are booking, map or contact links (for example a booking platform not in the built-in list).
- **own_domains** are extra hosts that count as the client's own site (for example a booking subdomain), so links to them are not citations. Hosts in the crawl are already counted.
- **role** on a page type says which requirements apply (`rules.md`): `condition`, `service` or `blog`. Left out, it comes from the name (concern / condition, service, blog / post / article); any other type gets only the requirements for every page.
- **columns.faq** is the FAQ extraction (the first FAQ question). It decides which pages need FAQPage schema.
- **credible_domains** are extra hosts that count as credible medical sources, on top of .gov, .edu, .org and the built-in journals and medical sites (`rules.md`).
- **body_markers** are regular expressions looked for in the body text for `faq`, `testimonials`, `before_after` or `rating` when the crawl has no marker column or it is empty (for example `{"faq": "\\b(FAQs?|Frequently Asked Questions)\\b", "rating": "★"}`). Use one only after checking in Claude in Chrome that the pattern matches the element on the sample pages and nothing else.
