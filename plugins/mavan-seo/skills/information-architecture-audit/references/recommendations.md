# Recommendations, Read Me notes and tab notes

These go in `work/decisions.json` alongside the review keys. Take every number from `work/analysis/summary.json` or the analysis CSVs; never round or estimate.

## recommendations

A TL;DR for the strategist: one row per fix, short and direct. fill.py sorts them High, Medium, Low, Pass, Info.

```json
"recommendations": [
 {"priority": "High", "area": "Duplicate pages", "covers": ["duplicates"],
  "problem": "14 groups of pages compete for the same treatment searches, e.g. /facelift/ and /non-surgical-facelift-aftercare-.../.",
  "do": "Merge the 18 competitors into their keeper pages and 301 them.",
  "where": "All Pages > Area = Duplicate pages; Duplicate Intent tab"},
 {"priority": "Medium", "area": "No owner page", "pages": 29, "covers": ["no_owner"], "problem": "...", "do": "...", "where": "..."}
]
```

- **priority**: exactly High, Medium, Low, Pass or Info, so the template's colours apply.
- **problem**: one sentence with the key number and one example URL. **do**: one or two short imperative sentences. No background, no hedging.
- **area**: a 2-3 word label. When the area is tagged on All Pages, the Pages column is a formula that counts it. The formula tags Duplicate pages, Blog URLs, Prune candidates, Menu cleanup, City pages and Deep service URLs by itself; analyze.py also tags Service paths (service pages outside the service folder) and Junk pages (archives and gallery entries). Tag any other area on its rows with `extra_areas` in decisions.json. For an area with no rows on All Pages (searches with no owner, links to redirects, the traffic baseline), give `"pages"` with the number instead.
- An area name must not sit inside another area name ("Service URLs" inside "Deep service URLs"): the Pages formula matches parts of names, so it would count both. fill.py stops on this.
- **where**: the tab and filter that shows the pages.
- **covers**: which required topics the row answers. Every topic needs a row, even when the answer is Pass: `junk_pages`, `blogs_outside_path`, `services_outside_path`, `duplicates`, `no_owner`, `menu_zero_clicks`, `prune`, `redirect_links`, `overlapping_browse`, `city_pages`, `service_depth`, `traffic_baseline` (Info).
- Blogs outside the blog path: name the blog folder the site uses, or "no blog folder exists", and recommend one consistent folder with 301s, done in the same release as other URL changes so links are only updated once.
- Linking from blogs to service pages is fine. Never recommend adding links to blog posts; that isn't a goal of this audit, and fill.py stops on it.

## readme

```json
"readme": {"window_reason": "...", "other_cities": "...", "ga4_missing": "...", "missing": "...", "side_observations": "..."}
```

All optional; fill.py writes the rest of the Read Me from the data. Set `window_reason` when the window isn't the last 3 full months (a migration), naming the migration month. `other_cities` says where the cities came from. `missing` adds to the notes analyze.py collects. `side_observations` is for anything worth knowing that's outside the audit's scope.

## tab notes and section text

```json
"tab_notes": {"Retarget Links": "None found for this site, so there is nothing to do here."},
"path_summary": "74 blogs sit at the root instead of /blog/; 107 service pages sit outside /services/.",
"link_flow_note": "Most body links come from blogs and point at other blogs, not service pages."
```

`tab_notes` adds one short site-specific sentence to a tab's yellow how-to line. `path_summary` and `link_flow_note` replace the generated summary lines on Path Consistency and Link Flow.
