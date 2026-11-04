# Reviewing the analysis

analyze.py applies the audit's rules mechanically. Review is where you catch what rules get wrong. Every correction goes in `work/decisions.json`, so a re-run from the exports reproduces it. Re-run `analyze.py` after each round and work down `work/review/next_steps.md` until it asks for nothing.

## decisions.json keys read by analyze.py

All optional, except that `mapping_confirmed` and `folder_types` come from the folder mapping the person confirms in Step 3 (analyze.py stops without them).

```json
{
 "mapping_confirmed": true,
 "folder_types":   {"procedures": "Service", "journal": "Blog", "resources": "Mixed"},
 "blog_folder":    "/journal/",
 "service_folder": "/procedures/",
 "page_types":     {"/path/": "Service"},
 "topics":         {"/path/": "microneedling"},
 "synonyms":       {"abdominoplasty": ["tummy tuck"], "blepharoplasty": ["eyelid surgery"]},
 "extra_topics":   ["microneedling"],
 "service_pages":  {"facelift": "/facelift/"}
}
```

- `page_types` is matched on the path without its query string, so an override on `/folder/` also changes every `/folder/?page=2` style URL. To type a listing page and leave its query-string variants alone, map the folder in `folder_types` (its listing page becomes a hub) instead of overriding the path.
- `page_types` values must be one of these types: Home, Pagination, Query-string URL, Archive, Gallery item, Company / Info, Utility / Policy, Service hub, Service, Concern hub, Concern, Blog hub, Blog, Location hub, Location / Area, Service-like (no folder), Unclassified, or "Name (folder)". Spell "Blog", "Service", "Service-like (no folder)" and "Location / Area" exactly: the Moves and Menu rules use them.
- `folder_types` values: Service, Concern, Blog, Location / Area, Company / Info, Gallery item, Archive, Utility / Policy, Mixed, or any other name (it becomes "Name (folder)"). Use `"parent/child"` as a key to type a second-level folder on its own; map the parent as Mixed.
- `service_pages` is keyed by topic, as it appears in `review/topics.csv`.

## Page types (`review/page_types.csv`, `review/unclassified.csv`)

Ask about the uncertain ones with AskUserQuestion (see SKILL.md, "How to ask the person questions"): group root-level pages by the rule that typed them, and offer a rule as an option rather than one question per page.

- Open 5 rows per type and read the "why" column. Blogs at the root are the usual problem: a short blog slug can land in Service-like, and a long service slug can land in Blog. Fix single pages with `page_types`.
- A folder typed "Name (folder)" is one the person gave its own name, or one missing from the confirmed mapping (next_steps.md lists those). If the person later says what it holds, update `folder_types` and re-run; do not guess.
- Label Unclassified pages if the answer is clear from the title and H1; otherwise leave them and list them in the chat summary for a person.

## Topics (`review/topics.csv`)

The topic decides which page owns a search (Internal linking opportunities). Topics come from service page slugs; a content page gets the longest one found in its slug, H1 or title.
- Add `synonyms` when one treatment has two names (labiaplasty / labia reduction, tummy tuck / abdominoplasty). The canonical name is the key; synonyms override slug-derived topics.
- Use `topics` for a single page that matched the wrong treatment, and `extra_topics` for a treatment with no service page that blogs keep mentioning.

## Orphan risk

next_steps.md lists pages that lose all their body links if the suggested removals and merges happen. Mention them in the chat summary so whoever does the removals relinks them.
