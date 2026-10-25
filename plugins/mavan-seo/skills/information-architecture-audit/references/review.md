# Reviewing the analysis

analyze.py applies the audit's rules mechanically. Review is where you catch what rules get wrong. Every correction goes in `work/decisions.json`, so a re-run from the exports reproduces it. Re-run `analyze.py` after each round and work down `work/review/next_steps.md` until it asks for nothing.

## decisions.json keys read by analyze.py

All optional.

```json
{
 "page_types":     {"/path/": "Service"},
 "folder_types":   {"procedures": "Service", "journal": "Blog"},
 "blog_folder":    "/blog/",
 "service_folder": "/services/",
 "topics":         {"/path/": "microneedling"},
 "synonyms":       {"abdominoplasty": ["tummy tuck"], "blepharoplasty": ["eyelid surgery"]},
 "extra_topics":   ["microneedling"],
 "pair_verdicts":  {"/page-a/ | /page-b/": "duplicate"},
 "keepers":        {"facelift": "/facelift/"},
 "service_pages":  {"facelift": "/facelift/"},
 "noowner_owner":  {"sagging jowls springfield il": "Make /jowls/ the owner and link to it from the facelift and neck pages"},
 "extra_areas":    {"/path/": "Hubs & packages"}
}
```

- `page_types` values must be one of the template's types: Home, Pagination, Query-string URL, Archive, Gallery item, Company / Info, Utility / Policy, Service hub, Service, Concern hub, Concern, Blog hub, Blog, Location hub, Location / Area, Service-like (no folder), Unclassified, or "Name (folder)". The Area formula needs "Blog", "Service", "Service-like (no folder)" and "Location / Area" spelled exactly.
- `pair_verdicts` keys are the `override_key` column of `review/dup_candidates.csv`, copied exactly. Values: `duplicate`, `not`, `city`.
- `keepers` and `service_pages` are keyed by topic, as it appears in `review/topics.csv`.

## Page types (`review/page_types.csv`, `review/unclassified.csv`)

- Open 5 rows per type and read the "why" column. Blogs at the root are the usual problem: a short blog slug can land in Service-like, and a long service slug can land in Blog. Fix single pages with `page_types`.
- A folder typed "Name (folder)" may really be a service, concern or blog folder under another name (e.g. /procedures/, /journal/); set `folder_types`.
- Label Unclassified pages if the answer is clear from the title and H1; otherwise leave them and list them in the chat summary for a person.

## Topics (`review/topics.csv`)

The topic decides duplicates, the blog's matching service page and the retarget suggestions. Topics come from service page slugs; a content page gets the longest one found in its slug, H1 or title.
- Add `synonyms` when one treatment has two names (labiaplasty / labia reduction, tummy tuck / abdominoplasty). The canonical name is the key; synonyms override slug-derived topics.
- Use `topics` for a single page that matched the wrong treatment, and `extra_topics` for a treatment with no service page that blogs keep mentioning.

## Duplicate pairs (`review/dup_candidates.csv`)

A pair is a duplicate only if both pages are about the same treatment. Look at:
- **check**: one topic is the other plus words. A product line is a duplicate (Restylane / Restylane Silk; gynecomastia / gynecomastia surgery). A different treatment in the same area is not (breast / breast lift; liposuction / neck liposuction). Decide every one.
- **duplicate**: confirm the two pages really share the treatment, not just a city or a generic search.
- **not** with high overlap: usually a missing synonym. Fix the synonym rather than the pair.
- **city**: the same treatment in different cities. These stay city variants for a policy decision; never merge them automatically.

The keeper rule is: service page first, then concern, then blog; main city first; then most impressions. Override with `keepers` only for a clear reason, such as the rule picking an orphaned page with no traffic, and say why in the chat summary.

## Searches with no owner (`analysis/no_owner.csv`)

Generic searches that reach 3+ treatments with no page holding half the impressions. The suggestion names an existing page when its topic is in the search, otherwise a hub. Rewrite a suggestion with `noowner_owner` when you know a better owner.

## Orphan risk

next_steps.md lists pages that lose all their body links if the suggested removals and merges happen. Mention them in the chat summary and the Read Me (`readme.missing` or `readme.side_observations`) so whoever does the removals relinks them.
