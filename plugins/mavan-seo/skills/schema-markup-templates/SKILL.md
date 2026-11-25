---
name: schema-markup-templates
description: For a site whose content is written, turns the new site content roadmap and one real page of each page type into a tested JSON-LD schema template per page type, for a WordPress schema plugin to fill. Adds a recommended schema type to every roadmap page, writes each template from a real page's content (FAQs, reviews, breadcrumbs and whatever else the page has), gives you a filled copy to test in the schema.org validator, and once the SEO confirms each passed, builds one document with every template. Use for schema markup, structured data, JSON-LD templates, "what schema does each page need", or after the new site content is written.
---

# Schema markup templates (Mavan)

One question for a site whose content exists: what **schema template** does each **page type** need? The answer is the roadmap with a recommended schema type per page, then one template per page type, then one document holding them all. A WordPress schema plugin fills each template's placeholders from the page.

**What is being built is a template, not a finished page's markup.** The job is to get the structure right: which schema objects each page type carries, how they connect and which values become placeholders. A real page is read to find that structure, so the exact data in it (URLs, dates, long answers) matters little. Do not hold back a block because the paste lacks a detail for it, and do not ask the person for details a template does not need.

Work only from the roadmap workbook, the pages the person pastes and what they type in. **Never visit a live site, and use no Composio tool, DataForSEO, Semrush, Ahrefs export or other connector.** Use no tool, dependency, fallback or extra step beyond those named here without asking the person and explaining why. If a step is unreliable, expensive or needs workarounds, stop and tell the person. This skill cannot check markup against schema.org (it has no way to reach it): **the schema.org validator, run by the person, is the only proof a template is valid.** Never say a template is valid before the person reports a pass. Every time a template or filled copy is sent, say plainly that it is a schema template, that it has not been checked against schema.org, and ask the person to test it in the validator and paste any error or warning messages back into this chat. What each rule means is in [references/rules.md](references/rules.md); a worked template is in `references/example-treatment.json` and `example-treatment.map.json`.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads; `${CLAUDE_SKILL_DIR}` in Claude Code). The script needs Python 3 with openpyxl. Work in a folder named after the client with a `work/` subfolder (it holds the plan, the templates and each template's status, so a later session can carry on), and keep a task list with one item per step.

## Step 1: Ask for the inputs

Ask in **one** message, before doing anything else.

| Input | Required? | Notes |
| --- | --- | --- |
| **New site content roadmap** workbook | Required | The .xlsx from `new-site-content-roadmap` (only its Roadmap tab is used) |
| **Business type** | Required | `medspa`, `surgical`, `dental`, or the schema.org type the Home page should use (for example `MedicalClinic`) |
| Client name | Optional | Names the files |

Done when the roadmap and the business type are given.

## Step 2: Preflight

```
python $SKILL/scripts/schema.py preflight --roadmap ROADMAP.xlsx --business-type TYPE --out work
```

On NOT READY, send **one** message listing each FAIL and what is needed, then stop. Done when it says READY.

## Step 3: Type every page, plan the templates

```
python $SKILL/scripts/schema.py build --roadmap ROADMAP.xlsx --business-type TYPE --client "CLIENT" --out "CLIENT_schema_types.xlsx" --work work
```

This writes the Roadmap tab with two new columns (Primary schema type, Why this schema type) and a Read Me, and `work/plan.md`: the templates to write. Send the workbook now, then tell the person which templates are planned and which types are yellow (extra pages the SEO confirms once the real page is read). Done when the build prints PASS.

## Step 4: Ask for one real page per template

A template is written from a real page, because only the page shows which schema objects it needs. Ask for **one finished page for each template in `work/plan.md`**, in one message: its content copied from the browser, including the FAQs, reviews or testimonials, breadcrumb labels, author and dates, prices, videos and anything else visible. The URL, meta description and breadcrumb URLs are welcome but optional: the template only needs them as placeholders. For the treatment template, ask for the most complete Service, Sub-Service or Brand / Device page (the one with the most sections). For Home, also ask for the business details a plugin would fill from the site's settings and the page may not show: legal name, logo URL, phone, address, opening hours, map coordinates, service area and social media profile links. A detail the person says the business does not have is left out.

Do not write a template from a page type's name alone. If a page type has no finished page yet, say that template has to wait for it. Start on the pages already received; do not wait for every page.

## Step 5: Write each template and its filled test copy

For each page, read it and list the schema objects it actually contains (rules.md says which objects to look for and how each is built). Put every such object into the template as a block with placeholders, even when the paste does not carry every value the block needs (a video with no URL, an FAQ whose answers were collapsed, reviews with no dates). The template shows structure; the values come later. Then:

1. Write `work/templates/<slug>.json`: the JSON-LD with `{{placeholder}}` for everything that changes from page to page. Types and structure are written out; only values are placeholders.
2. Write `work/templates/<slug>.map.json`: what each placeholder maps to, plus short notes (blocks to include only if present, blocks to repeat).
3. Run `python $SKILL/scripts/schema.py check --work work --slug <slug> --page-url URL`. Fix and rerun until it prints PASS.
4. Write `work/<slug>.values.json`: each placeholder's value, copied exactly from the real page (and, for Home, the business details the person gave). A value the paste does not carry (page URL, meta description, breadcrumb URLs, thumbnail, upload or publish dates) is filled with a clearly fake test value on `example.com` (for example `https://example.com/services/breast-augmentation/`) and the person is told which values are fake; the validator checks structure, so fake values test the template as well as real ones. Do not stop to ask for them. Run `python $SKILL/scripts/schema.py fill --work work --slug <slug> --values work/<slug>.values.json`. Fix and rerun until it prints PASS.

Never invent a review, a rating, a question, an answer or other page text: that always comes from the page. A property the page does not support is left out of the template, not left blank. Show two of any repeating item in the template (the map file says to repeat it); the filled copy follows the template, so it shows two as well.

Send each `work/test/<slug>.filled.json`. Tell the person that these are schema templates, filled with sample values so they can be tested, not final markup for the site; that they need to paste each into the schema.org validator (validator.schema.org, "Code Snippet" tab) and check that it validates correctly; and that they should reply per template with Pass or paste the exact errors and warnings into this chat. Say which values are fake test values. Done when every planned template has a filled copy sent.

## Step 6: Handle the validator results

- **Pass, and the SEO confirms:** `python $SKILL/scripts/schema.py mark --work work --slug <slug> --status passed`.
- **Errors or warnings:** fix the template (and the values file if needed), rerun `check` and `fill`, send the new filled copy and ask for another result. Mark `failed` with the message as a `--note` while it is open. Treat a warning as something to fix or explain to the SEO; do not mark a template passed with a warning the person has not accepted.
- If the validator says a type or property does not exist or does not belong on a type, trust the validator over this skill and change the template.

Done when every template is marked passed. If the person returns in a later session, read `work/status.json` and carry on from there. A template that is sent but not yet tested stays `draft`; do not describe it as finished.

## Step 7: Build the document

```
python $SKILL/scripts/schema.py doc --work work --client "CLIENT" --out "CLIENT_schema_templates.md"
```

It refuses until every template has passed. Then create one document from that file with the document tool the session offers (a Docs artifact in Claude); if there is none, send the .md. Reply in a few sentences: how many templates, which page types each covers, that each passed the validator on a real page (name them), and any yellow type the SEO confirmed. Remind the person that these are templates for the plugin to fill, and that if the plugin's output shows errors on a live page, they should paste the validator messages here. Do not recap the steps.
