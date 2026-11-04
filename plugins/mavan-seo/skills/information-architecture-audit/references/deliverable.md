# The deliverable (built by `scripts/make_xlsx.py`)

One standalone .xlsx. Claude does not write any wording in it: tab names, banners, headers, fixes, owners and order are fixed in the script. The only per-row text is the Why column, which the script fills from the analysis. House style (colors, fonts, widths, banner row) matches the other Mavan deliverables; the constants are copied into the script on purpose.

Tabs, in this order. A tab with no rows is left out, with its Recommendations row and README row:

| Tab | Color | Who | What it holds |
| --- | --- | --- | --- |
| Recommendations | orange | both | One row per issue: Issue, Priority, Fix, Number of Pages Affected, Tab(s) for SEO to Review, Tab(s) to hand off, Handoff to, Order |
| Check page type | grey | SEO only | Pages whose type is a guess from the URL wording, with the SEO's correct type |
| Moves | green | Dev | Blog posts and service pages outside their folder, with the new URL. Pages the prune removes or merges are not moved |
| All redirects - Handoff to Dev | blue | Dev | Header row 1 only (no banner): Source URL, Target URL, Regex (0 = no, 1 = yes), HTTP Code. The redirects for the Moves that are ready |
| Fix links | green | Dev | One row per page that links to a URL that no longer exists, redirects or is moving. The new URL is the final live URL |
| Menu cleanup | green | Dev | A recommended removal list. The SEO types Keep or Remove in each row; the implementer gets the Remove rows |
| Internal linking opportunities | green | Content | One Link from page per row. The SEO checks the anchor text exists on the page and writes the text to add if not |
| README | grey | SEO only | How to use, what was checked, settings, data used, what was not checked |

Row 1 is a yellow banner on every tab except Recommendations and the dev tab. The SEO deletes the banner, the Why columns, the grey tabs and the README before handoff.

## Rules the script applies (so they hold on every site)
- Owners are fixed: Dev does moves, redirects, link and menu edits; Content writes anything new; the SEO only checks and decides.
- The prune audit owns junk archives, posts to remove, duplicates, merges and their redirects. This deliverable never lists them. With no prune workbook, the README says those need the prune audit.
- A page type from the prune workbook is used as is. Only pages the prune did not type (or only guessed) are typed by this audit's rules, and the guessed ones go on Check page type.
- Where the script cannot choose (a move whose new URL already exists, a broken link, a topic no page owns) the cell says `SEO fill in` and is orange.
- Fix links skips nothing: every linking page gets a row. A menu or footer link found on 10+ pages is one row (`Main menu` / `Footer`).
- The Recommendations count for Fix links and Internal linking opportunities is distinct pages to edit.

## When the analysis finds an issue this script has no wording for
Add one object to `work/decisions.json` under `extra_recommendations` and say so in the chat. The script writes it as an extra Recommendations row (order cell orange, for the SEO to set) and a README row. Keys: `issue`, `priority` (High or Medium), `fix`, `pages` (a number from the analysis), `review`, `hand_off`, `handoff_to`, `order`, `rule`. Do not use this to reword an issue the script already covers.
