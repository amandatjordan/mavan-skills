---
name: eeat-ymyl-audit
description: Run Mavan's E-E-A-T & YMYL audit for a client site. Page types come from the client's IA or Content Prune & Merge workbook or a Page Type column in the crawl export; Claude in Chrome finds the extraction selectors on one sample page per type, and the person confirms what Claude found on those pages before the crawl and again before the workbook. A Screaming Frog or Sitebulb crawl checks every concern/condition, service and blog page against Mavan's requirements (medical reviewer, credible external source, credentials, blog author and date, MedicalCondition / MedicalProcedure / FAQPage schema, reviews, before/after photos, Google rating) and every external link's health; Claude reads 5 random pages of each type for medical claims and flags content for a closer review when the sample shows unsourced claims. Builds a workbook with a prioritised Recommendations rollup with SEO / Dev / Content next steps and handoffs, All Pages, External Links Needed, External Link Issues and Claims Needing Verification. Use for E-E-A-T audits, YMYL audits, content trust or quality reviews, AI-written or unedited content concerns, bad external linking, or "is this site's medical content credible".
---

# E-E-A-T & YMYL audit (Mavan SOP)

This skill carries the whole process and does not need the written SOP; a copy in a project management tool is documentation for people.

It answers: which pages miss Mavan's E-E-A-T requirements for their page type (`references/rules.md`), which pages have no credible external source, which external links have errors, and which medical claims must be verified. The deliverable is work for an SEO to hand off: every issue has a priority, next steps for SEO, Dev or Content, and a completion handoff to Dev or Content. A crawl shows what is on a page and where its links go. **It cannot say whether a claim is true.** Claude lists the claims; the SEO verifies them on the Claims Needing Verification tab.

**The person checks the sample pages twice:** before the crawl (what Claude believes each sample page has or is missing) and after it (what the crawl detected), both on the live pages. Nothing is built until they agree. This finds wrong selectors before they become a whole wrong audit.

**Claude in Chrome is required.** It finds the selectors the crawler needs and checks one sample page per page type. It is never used to work out which pages belong to which page type: that comes from the person's IA or Content Prune & Merge workbook, or from labels the person adds in the crawl (Step 2). If it is not available, stop and tell the person to open Chrome with the Claude extension on this computer; do not look for another way.

Do not use Composio, DataForSEO or any other data tool. Use no tool, dependency, fallback or extra step beyond those named here without asking the person first and explaining why it is needed. If a step is unreliable, expensive or needs workarounds, stop and tell the person. Assume nothing about the site (industry, URL structure, platform, column names). Every count and join is done by `scripts/audit.py`; never type or estimate a number.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). The script needs Python 3 with pandas and openpyxl. Work in a folder named after the client with a `work/` subfolder, and keep a task list with one item per step.

## What the person gives you

- The client's **website address**, and which crawler they will use: Screaming Frog (paid licence) or Sitebulb (Pro, for content extraction).
- **Page types:** a completed IA audit or Content Prune & Merge workbook for the client, if there is one. If not, the person adds a Page Type column to the site crawl export (the one with the extraction columns) and labels each page's type: service, blog, condition/concern and any other they want.
- Three **exports** from their own crawler, after you give them the setup (Steps 4 and 5): the site crawl with the extraction columns, the external links export, and the external URLs with their status codes.
- **Two confirmations** that what Claude says is on the sample pages matches the live pages (Steps 3 and 5).
- **One sample page per page type** (Step 2), or a yes on the ones you pick from the page type list.

Everything else you work out yourself: the selectors and markers from the sample pages in Claude in Chrome, and the credential terms from the built-in list plus any you see on the sample pages. Do not ask the person for selectors, domain rules, scoring or anything else.

## Step 1: Start

Send one message saying what is about to happen and what you need: the website address, the crawler, one sample page per page type, and whether there is a completed IA audit or Content Prune & Merge workbook for this client. Say Claude in Chrome is needed. The page types are concerns/conditions, services and blogs, plus any other type the person names. Wait for the answer.

## Step 2: Page types and sample pages

Do not use Claude in Chrome, the site's menu or its URL structure to decide page types.

- **IA or Content Prune & Merge workbook:** ask the person to attach it. Read only the header row of the tab that lists each URL with its page type, note the sheet, URL column and page type column, and the labels it uses. Set `page_type_source` to that file (`references/config.md`). Map each label for conditions/concerns, services and blogs (and any type the person named) to a page type, and show the person the labels and which page type each goes to; labels not mapped are left out. Have the script count the pages: they are printed by preflight in Step 4.
- **No workbook:** the person adds a Page Type column to the site crawl export, the same file as the extraction columns, and labels every page of each type in it (Step 4, `references/crawl-setup.md` section 2). Do not ask for a separate file of labels. Set `page_type_source` to `{"column": "Page Type"}` once the export arrives.

If the person did not give a sample page per page type, pick one from the workbook's list (or ask for one when there is no workbook). Ask: "Is each of these a good example of its page type?" Do not go on until they confirm.

## Step 3: Find the selectors and check the pages

Load the `chrome-browser` skill and use Claude in Chrome; open a new tab. Open only the confirmed sample pages. **Read only: do not log in, submit a form, click a call, book or buy button, or accept anything.**

On each confirmed page, find a selector for each item below (`references/crawl-setup.md` says what each should return). Test it on the page so it returns what you expect. Where an item is not on the site, record "not on this site".

A selector found on a page outside the audit (a testimonials page, a gallery page) is not tested yet. Sites often show the same thing differently inside service, concern and blog templates (review cards, a before/after slider, star icons). Before writing the rule, look for that element on pages of the audited types in Claude in Chrome (fetch a few pages of each type and look for the classes, star characters, `data-` attributes or image pairs), and make the selector match every form you find. Record the audited page it matched on.

Body text of the article only (not the menu or footer) · author · reviewer · published date · updated date · schema (the JSON-LD; the script keeps the `@type` names) · FAQ (the first question of an FAQ section: FAQs are in the body text, but the body cannot say whether a page has an FAQ section) · testimonials or reviews · before/after or results photos · Google rating.

Also look at what a visitor sees on each page: whether the author and reviewer are visible and where, whether results photos look like real patient or customer results or stock images, whether review or rating widgets show, trust signals (badges, credentials, certifications, awards), disclaimers, calls to action and where they sit, readability and layout, and any other opportunity to build trust that stands out.

Write two files:

- `work/extraction_setup.md`: one row per item with the column name to use (Body, Author, Reviewer, Published, Updated, Schema, Testimonials, Before After, Rating), an XPath and a CSS selector, how to extract it (text, or function value for counts; for Sitebulb, the exact Extract Data using, Type of Data and Operation settings, with Operation set to all matched items wherever the selector matches more than one element), and the page it was tested on; plus every crawl setting the person must change (external link checking, export columns), spelled out with where it is. Look up anything you are unsure of in the crawler's documentation before handing it over; never tell the person to go and find a setting. When there is no workbook, add the page type step: before sending the site crawl export, add a Page Type column to that same export (next to the extraction columns) and label every service, blog and condition/concern page (and any other type named).
- `work/chrome.tsv` (tab separated, header `url`, `visitor_sees`, `agrees`, `opportunities`), one row per sample page. Leave `agrees` empty for now. `opportunities` is what you would improve beyond what a crawl captures. No tabs or line breaks in the text.

Then add a **sample page check** to `work/extraction_setup.md`: a table with one column per sample page and one row per requirement in `references/rules.md` (plus FAQ section and page schema types), each cell Present (with where and what, for example "June 4, 2026, under the title"), Missing, or Not required for that page type. Give it to the person with the setup and ask them to open each sample page and say where they disagree. Fix every rule they disagree with before they crawl. Done when the person agrees with every cell.

## Step 4: The person runs the crawl

Give the person `work/extraction_setup.md` and the crawler instructions in `references/crawl-setup.md` (site crawl with the extraction rules and external link checking on, plus page type labels when there is no workbook; the outlinks export). Wait for the exports. Never read an export into the chat; the script reads them.

When they arrive, read only the header row of the site crawl export and write `work/config.json` from it and from Step 2 (`references/config.md`): `page_type_source` is the workbook or the crawl's label column. Then:

```
python $SKILL/scripts/audit.py preflight --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --out work
```

It prints READY, WARN and STOP items, how many pages matched each page type and which labels were left out, how many booking, Google, address and phone links were left out of the link checks (never citations, `references/rules.md`), the start and end of the body text of one page per page type, and writes `work/external_urls.txt`.

- **STOP** items must be fixed before going on. Tell the person exactly what to change (an extraction rule, a crawl setting) and re-run when they send a new export.
- Check the sample body text yourself: if it includes the menu or footer, the body selector is wrong; fix it and ask for a new crawl.
- **CHECK** items: an extraction is empty on every page of a page type. Treat each as a selector problem until proven otherwise; never report it as a finding first. In Claude in Chrome, reopen the sample page of that type and the page the selector was tested on, then look at a few other pages of that type for the element in any form. If you find it, fix the selector, give the person the corrected rule and ask for a new crawl. If it truly is not there, add a row to `work/checks.tsv` (tab separated, header `column`, `page_type`, `result`, `pages_checked`) with result `Confirmed absent` and the pages you checked, and pass `--checks work/checks.tsv` to every later command. The queue and the workbook stop while any CHECK is open.
- **WARN** items continue. They are shown at the top of the workbook; tell the person in plain words.

Done when there is no STOP, no CHECK, and the body text is the article.

## Step 5: Status codes of the external destinations

Use the person's own crawler; never ask them to use a different one. Tell them how to export every external URL with its HTTP status code from it (`references/crawl-setup.md` section 4): in Sitebulb, the external URLs list from the same audit; in Screaming Frog, a list-mode crawl of `work/external_urls.txt`, which also gives each destination's title and H1. Crawlers that only status-check external URLs (Sitebulb) give no title or H1; the script then compares the anchor with the words in the destination's URL. Wait for the export. Then:

```
python $SKILL/scripts/audit.py preflight --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --external EXTERNAL.csv --checks work/checks.tsv --chrome work/chrome.tsv --out work
```

It also prints what the crawl detected on each sample page, check by check. Show the person that list next to the Step 3 sample page check and ask them to confirm it on the live pages **before anything else is built**. Where they disagree, fix the extraction rule and ask for a new crawl. Set `agrees` in `work/chrome.tsv` to the person's answer (`Yes`, `Partly` or `No`); the build stops unless every sample page is `Yes`. If a sample page is "not in the crawl", the URL or its page type label is wrong.

Done when there is no STOP, no CHECK, and the person has confirmed every sample page (`agrees` is `Yes`).

## Step 6: Accuracy review

```
python $SKILL/scripts/audit.py queue --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --external EXTERNAL.csv --checks work/checks.tsv --sample-per-type 5 --out work
```

It prints the pages and body word count for each page type, and writes `work/queue.tsv` and one text file per page in `work/text/`. **Claims are read on a sample: 5 pages of each page type**, picked at random from pages with at least 200 words of body text (hub and list pages make no claims), the same pages on every run. Issues are usually template-wide, so a sample shows whether claims are a problem without reading every page. Use the same `--sample-per-type 5` in Step 7. Read every page only if the person asks (leave the option out); if that is more than you can read in this conversation, ask whether to split the reading across subagents.

When the sampled blog or condition pages make 2 or more claims on pages that cite no credible source, the workbook adds a Low priority follow-up: if the other changes do not bring improvements, the rest of that page type needs a closer review for claims.

Read the text files and write `work/claims.tsv` (tab separated, header `url`, `specific_claims`, `claims_to_verify`). Do not paste page text into the chat.

- `specific_claims` is `Yes` when the page makes specific medical or factual claims: statistics, timeframes, how long results last, session counts, downtime, safety or effectiveness statements, FDA approval or clearance, dosages, guarantees, "clinically proven", "studies show", what a treatment cures or treats. Otherwise `No`.
- `claims_to_verify` lists each claim in the page's own words, short, separated by ` | `; each becomes one row on the Claims Needing Verification tab. No tabs or line breaks.
- Leave out pricing and cost, the provider's credentials and years of experience: they are not claims to verify (`references/rules.md`).
- Do not say whether a claim is true, search for sources, or judge the writing. The SEO does that on the Claims Needing Verification tab.

Done when every page in `work/queue.tsv` has a row in `claims.tsv`.

## Step 7: Build the workbook

```
python $SKILL/scripts/audit.py build --config work/config.json --crawl CRAWL.csv --outlinks OUTLINKS.csv --external EXTERNAL.csv --checks work/checks.tsv --chrome work/chrome.tsv --claims work/claims.tsv --out DOMAIN_eeat_ymyl_audit.xlsx
```

Add the same `--sample-per-type` (and `--types`, `--max-per-type`, `--max` if used) as in Step 6. Read what it prints: every QA line must say PASS.

Done when every check prints PASS and you have opened the workbook and checked: the Recommendations rollup reads as real findings (X of Y pages, by page type) with a next step and handoff on each; 5 rows of All Pages match the crawl; External Links Needed lists only pages with no credible source; no booking, Google, address or phone link appears on either link tab; External Link Issues rows have a real error (dead means 400 or higher; No shared words means none of the anchor's words appear in the destination's title or H1, or its URL when the crawler gave no title or H1); each claim is its own row.

## Step 8: Report

Send the workbook and reply in a few sentences:
- Pages audited by page type, and the top High priority issues from the Recommendations tab, as written there.
- How many pages need a credible external source, how many external links have an issue, and how many claims need verifying.
- What goes to Dev and what goes to Content.
- The crawl notes, in plain words.
- That anchor vs destination is a word match, so "No shared words" rows need a person's look before anyone changes a link.
- The next step for the SEO: work the manual checks (sources and anchors, link decisions, claims), then hand off.

Do not paste page text or export rows into the chat.

## Reference files

- `references/crawl-setup.md`: the extraction rules and what each should return, and how to run the crawls in Screaming Frog and Sitebulb.
- `references/config.md`: the config format.
- `references/rules.md`: every check and flag.
- `references/workbook.md`: the tabs and columns.
- `references/rules.md` also holds the requirements by page type, the credible source rule, and each issue's priority, next step and handoff.
