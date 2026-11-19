---
name: eeat-ymyl-audit
description: Run Mavan's E-E-A-T & YMYL audit for a client site. Claude in Chrome finds the extraction selectors and checks one page per page type; a Screaming Frog or Sitebulb crawl with those extractions, the external links export and a list-mode crawl of the external destinations do the rest. Checks every concern/condition, service and blog page for author, reviewer, credentials, years of experience, dates, schema, external citations, link health (status, anchor vs destination title and H1), testimonials, before/after photos and rating, queues pages for an accuracy review, and builds a workbook. Use for E-E-A-T audits, YMYL audits, content trust or quality reviews, AI-written or unedited content concerns, bad external linking, or "is this site's medical content credible".
---

# E-E-A-T & YMYL audit (Mavan SOP)

This skill carries the whole process and does not need the written SOP; a copy in a project management tool is documentation for people.

It answers: which pages are missing experience, expertise, authority and trust signals, which external links are dead or do not match the page they are linked from, and which pages a person must read for accuracy. A crawl shows what is on a page and where its links go. **It cannot say whether a claim is true.** That is the Accuracy Review Queue: Claude lists the specific claims, a person verifies them.

**Claude in Chrome is required.** It finds the selectors the crawler needs and checks one page per page type. If it is not available, stop and tell the person to open Chrome with the Claude extension on this computer; do not look for another way.

Do not use Composio, DataForSEO or any other data tool. Use no tool, dependency, fallback or extra step beyond those named here without asking the person first and explaining why it is needed. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Assume nothing about the site (industry, URL structure, platform, column names). Every count and join is done by `scripts/audit.py`; never type or estimate a number.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). The script needs Python 3 with pandas and openpyxl. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## What the person gives you

- The client's **website address**, and which crawler they will use: Screaming Frog (paid licence) or Sitebulb (Pro, for content extraction).
- Three **exports** from the crawler, after you give them the setup (Steps 4 and 5): the site crawl with the extraction columns, the outlinks export, and the list-mode crawl of the external destinations.
- A **yes** on the sample pages and page types you propose (Step 2). They can give their own sample pages instead of letting you choose.

Everything else you work out yourself: the selectors, URL patterns and markers from the site in Claude in Chrome, and the credential terms from the built-in list plus any you see on the sample pages. Do not ask the person for selectors, domain rules, scoring or anything else.

## Step 1: Start

Send one message saying what is about to happen and what you need: the website address and the crawler, and whether they want to name a sample page for each page type or have you choose (you will show them for a yes either way). Say Claude in Chrome is needed. The page types are concerns/conditions, services and blogs, plus any other type the person names. Wait for the answer.

## Step 2: Find the page types and sample pages

Load the `chrome-browser` skill and use Claude in Chrome; open a new tab for the site. **Read only: do not log in, submit a form, click a call, book or buy button, or accept anything.**

Find where each page type lives from the site's menu and list pages, note the URL path they share, and pick one typical page of each type (or use the person's). Show the person the pages and the paths, and ask: "Is each of these a good example of its page type, and are these the right URL paths?" Do not go on until they confirm; if not, pick again or use the page they name.

## Step 3: Find the selectors and check the pages

On each confirmed page, find a selector for each item below (`references/crawl-setup.md` says what each should return). Test it on the page so it returns what you expect. Where an item is not on the site, record "not on this site".

Body text of the article only (not the menu or footer) · author · reviewer · published date · updated date · schema types (JSON-LD `@type`) · testimonials or reviews · before/after or results photos · rating.

Also look at what a visitor sees on each page: whether the author and reviewer are visible and where, whether results photos look like real patient or customer results or stock images, whether review or rating widgets show, trust signals (badges, credentials, certifications, awards), disclaimers, calls to action and where they sit, readability and layout, and any other opportunity to build trust that stands out.

Write two files:

- `work/extraction_setup.md`: one row per item with the column name to use (Body, Author, Reviewer, Published, Updated, Schema, Testimonials, Before After, Rating), an XPath and a CSS selector, how to extract it (text, or function value for counts), and the page it was tested on; plus the URL path of each page type. Section 3 of `references/crawl-setup.md` says how to write the marker rules so they are empty when the page lacks the element.
- `work/chrome.tsv` (tab separated, header `url`, `visitor_sees`, `agrees`, `opportunities`), one row per sample page. Leave `agrees` empty for now. `opportunities` is what you would improve beyond what a crawl captures. No tabs or line breaks in the text.

## Step 4: The person runs the crawl

Give the person `work/extraction_setup.md` and the crawler instructions in `references/crawl-setup.md` (site crawl with the extraction rules and external link checking on; the outlinks export). Wait for the exports. Never read an export into the chat; the script reads them.

When they arrive, read only the header row of the site crawl export and write `work/config.json` from it and from Step 2 (`references/config.md`). Then:

```
python $SKILL/scripts/audit.py preflight --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --out work
```

It prints READY, WARN and STOP items, the start and end of the body text of one page per page type, and writes `work/external_urls.txt`.

- **STOP** items must be fixed before going on. Tell the person exactly what to change (an extraction rule, a crawl setting) and re-run when they send a new export.
- Check the sample body text yourself: if it includes the menu or footer, the body selector is wrong; fix it and ask for a new crawl.
- **WARN** items continue. They are shown at the top of the workbook; tell the person in plain words.

Done when there is no STOP and the body text is the article.

## Step 5: List crawl of the external destinations

Give the person `work/external_urls.txt` and tell them to crawl it in list mode and export address, status code, title and H1 (`references/crawl-setup.md`). Wait for the export. Then:

```
python $SKILL/scripts/audit.py preflight --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --external EXTERNAL.csv --chrome work/chrome.tsv --out work
```

It also prints what the crawl detected on each sample page. Compare it with what you saw in Chrome and set `agrees` in `work/chrome.tsv` to `Yes`, `Partly` or `No`. Where it is `Partly` or `No`, say what differs in `visitor_sees`: that is an extraction rule that needs fixing. If a sample page is "not in the crawl", the URL or the page type path is wrong.

Done when there is no STOP and every sample page has `agrees` filled in.

## Step 6: Accuracy review

```
python $SKILL/scripts/audit.py queue --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --external EXTERNAL.csv --out work
```

It prints the pages and body word count for each page type, and writes `work/queue.tsv` and one text file per page in `work/text/`. Tell the person the counts and ask which page types Claude should read, and whether to stop at a number of pages (default: all of them). If they choose, re-run with `--types Condition,Service` and/or `--max N`, and use the same options in Step 7.

Read the text files one at a time and write `work/claims.tsv` (tab separated, header `url`, `specific_claims`, `claims_to_verify`). Do not paste page text into the chat.

- `specific_claims` is `Yes` when the page makes specific medical or factual claims a reviewer should verify: statistics, timeframes, safety or effectiveness statements, dosages, guarantees, "clinically proven", "studies show". Otherwise `No`.
- `claims_to_verify` lists those claims in the page's own words, short, separated by ` | `. No tabs or line breaks.
- Do not say whether a claim is true, search for sources, or judge the writing. The reviewer does that on the Accuracy Review Queue tab.

Done when every page in `work/queue.tsv` has a row in `claims.tsv`.

## Step 7: Build the workbook

```
python $SKILL/scripts/audit.py build --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --external EXTERNAL.csv --chrome work/chrome.tsv --claims work/claims.tsv --out DOMAIN_eeat_ymyl_audit.xlsx
```

Add the same `--types` and `--max` as in Step 6 if used. Read what it prints: every QA line must say PASS.

Done when every check prints PASS and you have opened 5 rows of Page Review and their External Links rows and agree they are right: dead means the status is 400 or higher, No shared words means none of the anchor's words appear in the destination's title or H1.

## Step 8: Report

Send the workbook and reply in a few sentences:
- Pages audited by page type, and the most common things pages lack (from the Recommendations tab).
- The External Links flags in numbers: dead links, links with no shared words, sites that blocked the crawler.
- How many pages are in the Accuracy Review Queue and that a person must verify each claim against sources.
- The preflight warnings, in plain words.
- The Claude in Chrome findings: where the crawl and the visitor's view disagreed, and the opportunities found.
- That anchor vs destination is a word match, so "No shared words" rows need a person's look before anyone changes a link.
- The next human step: work the Accuracy Review Queue, then fix the flagged links and the missing signals.

Do not paste page text or export rows into the chat.

## Reference files

- `references/crawl-setup.md`: the extraction rules and what each should return, and how to run the crawls in Screaming Frog and Sitebulb.
- `references/config.md`: the config format.
- `references/rules.md`: every check and flag.
- `references/workbook.md`: the tabs and columns.
