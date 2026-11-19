# config.json

Written by Claude from the person's answers (SKILL.md Step 2). Column names must match the crawl export exactly (not case sensitive). Nothing here is assumed about a site: every value comes from the person.

```json
{
  "crawler": "screaming-frog",
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
    {"name": "Condition", "paths": ["/conditions/"], "tier": "High"},
    {"name": "Service", "paths": ["/services/"], "tier": "High"},
    {"name": "Blog", "paths": ["/blog/"], "tier": "High"},
    {"name": "Provider", "paths": ["/providers/"], "tier": "Medium"},
    {"name": "Company", "paths": ["/about", "/contact"], "tier": "Low"}
  ],
  "credential_terms": ["MD", "DDS", "board-certified"],
  "experience_terms": [],
  "authoritative": {"tlds": [".gov", ".edu"], "domains": ["who.int"]},
  "weak_domains": [],
  "content_link_positions": ["Content"],
  "generic_anchor_words": [],
  "own_domains": [],
  "priority_cutoffs": {"high": 4, "medium": 2}
}
```

## Fields

- **columns.body** is required. Leave any other column out, or set it to `""`, when the site does not have it ("not on this site"): that check is shown as n/a and does not count as failed. `url`, `status` and `indexability` are found automatically in a Screaming Frog or Sitebulb export when left out.
- **page_types** are tried in order and the first match wins. A path matches when the page's URL path contains it. `tier` is `High`, `Medium` or `Low`. Low pages are audited and listed but not scored.
- **credential_terms** are matched as whole words, anywhere in the body, author and reviewer text. Terms of five letters or fewer written in capitals (MD, DDS, RN) match capitals only, so "md" in ordinary text does not count.
- **experience_terms** are extra phrases to count as years of experience. A number of years followed by "experience" or "practice" is always recognised ("18 years of experience").
- **authoritative**: a link is Authoritative when its host ends with one of the `tlds` or is, or is a subdomain of, one of the `domains`.
- **weak_domains**: optional. Links to these hosts (forums, social, user-generated content) are flagged Weak source. Leave empty to flag none.
- **content_link_positions**: which Link Position values count as citations. Menus and footers are left out. Ignored when the outlinks export has no link position column (preflight warns).
- **generic_anchor_words**: extra anchor words to ignore when matching an anchor to its destination (the built-in list is in rules.md).
- **own_domains**: extra hosts that count as the client's own site (for example a booking subdomain), so links to them are not citations. Hosts in the crawl are already counted.
- **priority_cutoffs**: failed checks needed for High and Medium. Defaults 4 and 2. Change them only if the person asks.

## Starting lists to offer the person

These are offered, not assumed. The person edits them for the client's field.

- Credentials: MD, DO, DDS, DMD, NP, PA, RN, PhD, board-certified, board certified, fellowship-trained, licensed.
- Authoritative TLDs: .gov, .edu, .mil, .gov.uk, .nhs.uk, .ac.uk.
- Authoritative domains: who.int, nature.com, thelancet.com, jamanetwork.com, nejm.org, bmj.com, cochranelibrary.com. Ask for professional associations, journals and regulators for the client's field (for example a plastic surgery, dental, dermatology or medical weight loss body), and for a weak-domain list if they want forums and social sites flagged.
