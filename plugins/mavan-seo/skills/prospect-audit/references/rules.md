# Rules

## Thresholds written into the scripts (confirm with Amanda; change in prep.py)

| Rule | Value | Where |
| --- | --- | --- |
| Thin page | indexable, 200, under 300 content words (same as the service gap audit) | `THIN_WORDS` in prep.py |
| Empty crawl | fail when 20% or more of 200 pages have no title, no H1 and no words, or fewer than 10 pages return 200 | `EMPTY_SHARE_FAIL` in prep.py |
| Unassigned warning | more than 25% of gap keywords in no group | build.py |

## Gap groups (`work/gap_groups.json`)

```json
[
 {"group": "Competitor brand", "kind": "exclude", "terms": ["rival one"]},
 {"group": "Botox and neurotoxin", "practice_type": "medspa", "kind": "service",
  "terms": ["botox", "dysport", "xeomin"], "service_gap_ref": "", "notes": ""}
]
```

- **One group per thing a person would search for**: a service (kind `service`), a problem people search for that points to services (`concern`), a place (`location`), or anything else (`other`). Keep the service names the prospect's own site would use. Name a Botox group for Botox, not "neurotoxin".
- **practice_type** is the prospect's own practice type (for example medspa, surgical, dental), taken from Step 0, not guessed per group.
- **terms** are matched as whole words or phrases against the lowercase keyword, with an optional plural "s" or "es". The first group in the file that matches wins, so put narrow groups before broad ones and `exclude` groups first. Add the competitors' and the prospect's brand names as an `exclude` group.
- Keep each group to one topic. A broad word shared by many services (such as "facial") belongs only to the group for that broad topic.
- **service_gap_ref**: for a `service` group, the result from the service gap audit (for example "Missing" or "Thin page"), copied from its workbook. Leave blank when that audit did not run.
- The workbook never totals volume. It shows the keyword count, the single largest search with its estimated volume, and for each competitor the best position and how many of the group's keywords it ranks for.

## Page check column

Counts live, indexable crawl pages whose URL path, title or H1 contains any of the group's terms.

| Value | Meaning |
| --- | --- |
| Possible missing service page | service group, no matching page in the crawl |
| No matching page in the crawl | other group kinds, no matching page |
| Only thin pages match | every matching page is under the thin line |
| Has a matching page | at least one matching page is not thin |

"Possible" is deliberate: the crawl may have missed the page, or the practice may not offer the service. Confirm with the person before telling a prospect it is missing.

## Ranking URLs not live

A URL with tracked keywords whose crawl status is not 200 (404, redirect or error) or that is not in the crawl at all. "Not in crawl" only means the crawl did not find the URL (an old or orphaned page is not reached by following links). It is not proof the page is gone; say it that way.
