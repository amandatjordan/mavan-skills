# config.json

Written by Claude (SKILL.md Step 4) from the page types the person confirmed and the header row of the crawl export. Column names must match the crawl export exactly (not case sensitive). The person is never asked for any of it.

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
    "rating": "Rating 1"
  },
  "page_types": [
    {"name": "Condition", "paths": ["/conditions/"]},
    {"name": "Service", "paths": ["/services/"]},
    {"name": "Blog", "paths": ["/blog/"]}
  ],
  "credential_terms": [],
  "experience_terms": [],
  "content_link_positions": ["Content"],
  "own_domains": []
}
```

## Fields

- **columns.body** is required. Leave any other column out, or set it to `""`, when the site does not have it ("not on this site"): it is shown as n/a and is not counted as missing. `url`, `status` and `indexability` are found automatically in a Screaming Frog or Sitebulb export when left out.
- **page_types** are tried in order and the first match wins. A path matches when the page's URL path contains it. Pages that match none are left out and listed in the preflight warnings. The audit covers concerns/conditions, services and blogs, plus any type the person named.
- **credential_terms** are added to the built-in list: MD, DO, DDS, DMD, NP, PA, PA-C, RN, PhD, FACS, FAAD, board-certified, board certified. Add terms you see on the sample pages (for example FNP or FACOG). Terms of five letters or fewer written in capitals match capitals only, so "md" in ordinary text does not count. Credentials are looked for in the body, author and reviewer text.
- **experience_terms** are extra phrases to count as years of experience. A number of years followed by "experience" or "practice" is always recognised ("18 years of experience").
- **content_link_positions** are the Link Position values that count as citations. Menus and footers are left out. Ignored when the outlinks export has no link position column (preflight warns).
- **own_domains** are extra hosts that count as the client's own site (for example a booking subdomain), so links to them are not citations. Hosts in the crawl are already counted.
