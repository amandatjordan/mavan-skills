---
name: eeat-ymyl-audit
description: Run Mavan's E-E-A-T & YMYL audit for a client site from a Screaming Frog or Sitebulb crawl (with custom extraction), the external links export and a list-mode crawl of the external destinations. Checks every concern/condition, service and blog page for author, reviewer, credentials, dates, schema, citations, link health, anchor vs destination match, testimonials, results photos and rating, queues the pages for an accuracy review, and builds a workbook. Optionally checks one page per page type in Claude in Chrome. Use for E-E-A-T audits, YMYL audits, content trust or quality reviews, AI-written or unedited content concerns, bad external linking, or "is this site's medical content credible".
---

# E-E-A-T & YMYL audit (Mavan SOP)

This skill carries the whole process and does not need the written SOP; a copy in a project management tool is documentation for people.

It answers: which pages show weak experience, expertise, authority and trust signals, which external links are broken or do not support the page, and which pages a person must read for accuracy. A crawl can show what is on a page and where its links go. **It cannot say whether a claim is true.** That is the Accuracy Review Queue, which a person works through; Claude only lists the specific claims to verify.

Work only from the exports the person provides, plus the page text Claude reads for the accuracy review. **Do not use Composio for any part of this skill. Do not use DataForSEO or any other data tool. Never visit the live site, except in the optional Claude in Chrome check in Step 5, and only if the person chose it.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person first and explaining why it is needed. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Assume nothing about the site (industry, URL structure, column names, platform). Every count, share and join is done by `scripts/audit.py`; never type or estimate a number.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). The script needs Python 3 with pandas and openpyxl. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## What you need (this is the preflight list)

1. **Which crawler** the person used: Screaming Frog (paid licence) or Sitebulb (Pro, for content extraction). `references/crawl-setup.md` says how to set up the crawl, the extraction and the list crawl in each.
2. **Site crawl export**: all internal HTML pages, with the extraction columns (body text, author, reviewer, published date, updated date, schema types, and the testimonial, before/after and rating markers).
3. **Outlinks export** (external links): source, destination, anchor text, status code, and link position if the crawler has it.
4. **List-mode crawl export of the external destinations**: address, status code, title, H1. The skill makes the URL list for the person to crawl (Step 3), so this comes after Step 2.
5. **Main-content selector**, tested on one sample page (preflight shows the start and end of the body text of one page per type so the person can see it is the article, not the menu or footer).
6. **Author, reviewer and date selectors** (or "not on this site").
7. **Credential terms** and years-of-experience wording. Offer the starting list in `references/config.md`; the person adds the client's field.
8. **Authoritative-domain rules.** Offer the starting list in `references/config.md`; the person adds professional bodies and journals for the client's field, and any weak-source domains (forums, social, user-generated) if they want those flagged.
9. **Page-type URL patterns**: which URL paths are conditions, services, blogs, provider bios, other.
10. **YMYL tier for each page type**: High, Medium or Low. Low pages are listed but not scored.
11. **Markers** for testimonials/reviews, before/after photos and an on-page rating (selector, section name or terms), or "not on this site".
12. **Optional: Claude in Chrome page check.** Ask the person if they want it, and tell them plainly that it is optional and **needs Claude in Chrome** (Chrome with the Claude extension, on the computer being used). It checks one representative page of each page type for other opportunities.
13. **Only if 12 is yes:** does the person want to **provide** the page for each page type, or have Claude **choose later**? If Claude chooses, Claude shows the pages and asks the person to confirm each is a good representative of its type (Step 5).

Ask for whatever the request does not give in **one** message (Step 1), with no menus beyond the choices above.

## Step 1: Ask for everything once

Send one message listing only the items above the request did not already give. Offer the starting lists for items 7 and 8. Say that item 12 is optional and needs Claude in Chrome. Do not ask about scoring, cut-offs, or anything not listed: the defaults are in `references/rules.md`. Wait for the answer.

Done when every item is given or the person says it does not apply, and the person has said yes or no to the Claude in Chrome check.

## Step 2: Write the config and run preflight part 1

Write `work/config.json` from the answers (`references/config.md` has the format and the starting lists). Use the exact column names from the crawl export. Then:

```
python $SKILL/scripts/audit.py preflight --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --out work
```

It prints READY, WARN and STOP items, the start and end of the body text of one page per page type, and writes `work/external_urls.txt`. Never read the exports into the chat; the script reads them.

- **STOP** items must be fixed before going on. Tell the person exactly what to change (a selector, a crawl setting, a missing column) and re-run when they send a new export.
- Show the person the sample body text and ask them to confirm each page type's text is the article only (if the menu or footer is in it, the selector is wrong).
- **WARN** items continue. List them in plain words and say they will be shown at the top of the workbook.

Done when there is no STOP and the person has confirmed the body text.

## Step 3: List crawl of the external destinations

Give the person `work/external_urls.txt` and tell them to crawl it in list mode (`references/crawl-setup.md`) and export the Internal HTML tab or equivalent with address, status code, title and H1. Wait for the export. Then:

```
python $SKILL/scripts/audit.py preflight --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --external EXTERNAL.csv --out work
```

Done when there is no STOP and every WARN has been told to the person.

## Step 4: Accuracy review scope and claims

```
python $SKILL/scripts/audit.py queue --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --external EXTERNAL.csv --out work
```

It prints the page count and body word count for two scopes: **failed** (High-YMYL pages that failed at least one structural check; the default) and **all-high** (every High-YMYL page). Tell the person both counts and ask which they want, and whether Claude should read all of the pages in the queue. If they pick all-high, re-run with `--scope all-high`; use the same scope in Step 6. It writes `work/queue.tsv` and one text file per page in `work/text/`.

Read the text files one at a time, in order, and write `work/claims.tsv` (tab separated, header `url`, `specific_claims`, `claims_to_verify`). Do not paste page text into the chat.

- `specific_claims` is `Yes` when the page makes specific medical or factual claims a reviewer should verify: statistics, timeframes, safety or effectiveness statements, dosages, guarantees, "clinically proven", "studies show". Otherwise `No`.
- `claims_to_verify` lists those claims in the page's own words, short, separated by ` | `. No tabs or line breaks.
- Do not say whether a claim is true, search for sources, or judge the writing. The reviewer does that on the Accuracy Review Queue tab. The text file shows how many external citations the page has, so the reviewer knows which pages have no sources at all.

Done when every page in `work/queue.tsv` has a row in `claims.tsv`, or the person chose to read fewer (the rest show "Not read").

## Step 5: Chrome check, only if the person said yes in Step 1

Skip this step otherwise.

1. If the person gave a page for each page type, use those. If Claude chooses, run
   ```
   python $SKILL/scripts/audit.py reps --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --external EXTERNAL.csv
   ```
   It proposes the page whose body length is closest to its type's median (a typical page, not the best or the worst). Show the pages and ask: "Is each of these a good example of its page type?" If not, the person names another page or says which to pick again. Do not open any page until they confirm.
2. Load the `chrome-browser` skill with the Skill tool and use Claude in Chrome. If Claude in Chrome is not available, say so and ask whether to skip this step.
3. Open each confirmed page in a new tab. **Read only: do not log in, submit a form, click a call, book or buy button, or accept anything.** Look at what a visitor sees: whether the author and reviewer are visible and where, whether results photos look like real patient or customer results or stock images, whether review or rating widgets show, trust signals (badges, credentials, certifications, awards), disclaimers, calls to action and where they sit, readability and layout, and any other opportunity to build trust that stands out.
4. Write `work/chrome.tsv` (tab separated, header `url`, `visitor_sees`, `agrees`, `opportunities`), one row per page. `agrees` is `Yes`, `Partly` or `No`: whether what a visitor sees matches what the crawl detected for that page (the workbook fills in what the crawl detected from the Page Review row). Where it is `Partly` or `No`, say what differs in `visitor_sees`, because that points to an extraction marker that needs fixing. No tabs or line breaks in the text.

Done when every confirmed page has a row.

## Step 6: Build the workbook

```
python $SKILL/scripts/audit.py build --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --external EXTERNAL.csv --claims work/claims.tsv --chrome work/chrome.tsv --out DOMAIN_eeat_ymyl_audit.xlsx
```

Leave out `--chrome` when Step 5 was skipped, and `--claims` if no pages were read. Add `--scope all-high` if that scope was chosen. Read what it prints: every QA line must say PASS.

Done when every check prints PASS and you have opened 5 rows of Page Review (include a High priority row) and its External Links rows and agree the flags are right: dead means the status is 400 or higher, No shared words means the anchor's words do not appear in the destination's title or H1.

## Step 7: Report

Send the workbook and reply in a few sentences:
- Pages audited and scored, and the Priority split.
- The three most common issues from the Recommendations tab, and the External Links flags in numbers.
- How many pages are in the Accuracy Review Queue, how many Claude read, and that a person must verify each claim against sources.
- The preflight warnings, in plain words.
- If the Chrome check ran: the pages checked, where it disagreed with the crawl, and the opportunities it found.
- That Priority uses the default cut-offs (4 or more failed checks is High, 2 to 3 is Medium; set in the config) and that anchor vs destination is a word match, so "No shared words" rows need a person's look before anyone changes a link.
- The next human step: work the Accuracy Review Queue, then fix the flagged links and the missing signals, High priority first.

Do not paste page text or export rows into the chat.

## Reference files

- `references/config.md`: the config format, the starting credential and authoritative-domain lists.
- `references/crawl-setup.md`: how to set up the crawl, extraction, outlinks export and list crawl in Screaming Frog and Sitebulb.
- `references/rules.md`: every check, flag and default.
- `references/workbook.md`: the tabs and columns.
