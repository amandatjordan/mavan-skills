---
name: seo-audit-client-report
description: Turn a finished SEO audit (workbooks, exports, redirect maps) into a short client report: an at-a-glance table, the biggest themes with why they matter and examples, and the next steps we will take. Use for any client report, findings summary or "what we found" doc.
---

# SEO audit client report

Turn the deliverables of a finished SEO audit into a short report a business owner can read in a few minutes. It has exactly four parts: a title and byline, **At a glance**, **Biggest opportunities**, **Next Steps**. It shows we understand this client's site, using the client's own data. It never reads like a generic explanation of SEO, and it never promises a result.

This works for any audit type: content refresh and merge, service gap, technical, information architecture, internal linking, backlinks, titles and H1s, local SEO and Google Business Profile, redirects, and so on.

References: [references/example-report.md](references/example-report.md) is a finished report to match for structure, length and tone (not content). [references/blank-template.md](references/blank-template.md) is the blank version to fill in.

## Inputs

- **The audit deliverables:** every workbook tab, export or paste the audit produced (page lists with actions, redirect maps, gap lists, backlink lists, and so on). The actions the audit chose are the source for Next Steps. Its priority order, if it has one, is the source for theme order.
- **Client facts:** business name, what they sell, who their customers are (patients, clients, guests), target towns. Take these from the files or the person's chat.

If the files contain no actions at all, ask for them. Do not invent actions from raw data.

## Workflow

1. **Read every deliverable end to end.** Note each action type, how many items it covers, the metrics in the data, and any priority order.
2. **Group the findings into 3 to 6 overarching themes.** A theme is one kind of problem (for example, pages competing for the same searches), not one page. Name each theme in plain words that describe the actual finding. Order themes by the deliverable's own priority. If it has none, order by how much visibility is involved and say so in chat.
3. **Count what each theme affects.** Use the deliverable's own counts. If you have to add numbers together yourself (for example, 38 posts plus 294 archive pages), only add figures that appear in the deliverable, and list every sum you made in chat afterward.
4. **Pick examples.** For each theme, choose the highest-priority pages or items, with their data. Prefer the client's own traffic and visibility figures for the affected pages.
5. **Raise gaps in chat before writing** if something important is missing: no actions, unclear metric columns, an unknown date range the report needs. If the person is not around, take the most reasonable reading and say which one you took.
6. **Build the report as a doc** when Claude Docs is available (otherwise in the format the person asks for): create the doc first with the title, byline and one pending block per section, open it, then fill one section per call.
7. **Run the quality check** below.
8. **Hand off** with one short line, then tell the person in chat what you assumed, which numbers you summed yourself, and what you left out.

## Report structure (use exactly this)

### Title and byline
`[Client name]: [Audit type] Findings & Recommendations`, then the date and author. Describe the audit type in client-friendly words, not internal ones (write "Content Refresh & Merge", not "Content Prune").

### At a glance
This is a summary, so keep it short:
- One or two sentences saying what we reviewed and why, in the client's terms (for example: "We reviewed your website to identify opportunities to improve visibility in Google and bring more potential patients to your most important service pages."), then "We found the following opportunities to improve your performance:".
- Then **one summary table** with two columns: **Issue** and **Pages affected** (use "Items affected" or a better unit when the issue is not about pages, such as redirect rules or links). Plain-language issue names, one row per theme, 8 rows at most, counts taken from the deliverable.
- Nothing else. No paragraph of headline numbers, no bullets, no explanation of why the issues matter (that belongs in Biggest opportunities), and no "About the numbers" section.

### Biggest opportunities
One sentence of intro. Then one block per theme, in the same order as the table, each with exactly this shape:

```
### N. [Theme in plain words]
[Why it matters: 2 to 3 plain sentences.]
- [Example with data]
- [Example with data]
```

- **Why it matters** says what is happening on the site today and what that costs this business, in terms a business owner cares about (people reaching the right page, bookings, being found). Name the client's own kind of customer or service. Describe the current situation. Do not predict what fixing it will do.
- **Examples** are 1 to 3 bullets of the client's own data: the theme's total from the deliverable, then the highest-priority page or item, named, with its numbers. Break a long count into nested bullets if that reads better. Never list every affected page; the detail lives in the deliverable.
- Use the real metric names the deliverable uses (impressions, clicks, rankings, sessions, conversions). Say where a number covers one page and where it covers a group.

### Next Steps
The actual actions we will take, taken from the actions in the deliverable. Start with: "These are the actions we will be taking to resolve these issues:". Then one bullet per action group, in theme order, each with a bold lead-in and one sentence on what we will do, including the count from the deliverable (for example: "**Combine competing pages:** merge the useful content from 18 pages into the stronger page for each topic, and redirect the old addresses to it.").

- Every step must exist in the deliverable. Do not add steps that are not in it.
- State actions, not outcomes. No timelines, no "this will improve".
- Where the audit marks something for discussion or a policy decision, write it as an action we take ("Review the 11 location pages that repeat another page and handle each one"), not a question for the client.

## Rules

**Never promise a result.** No guaranteed or expected rankings, traffic, leads or revenue. No "will rank", "will increase", "you can expect", targets, forecasts or timelines. Describe what the data shows and what we will do, then stop.

**Stick to the data in the deliverables.** Every number must come from the audit files. Don't estimate, extrapolate or round into something the data doesn't say. Don't combine unrelated datasets into one figure. Never show national search volume numbers; they read as a promise of local traffic.

**Only claim what the data shows.** Don't give a cause the data can't support (for example, don't say people skip a page "because it is short"). General statements in Why it matters must not contradict the specific data. If a related page already ranks for a topic, don't say the site "can't rank" without a new page.

**Don't make the client do SEO strategy.** The client hired us to make the SEO calls. Don't ask them to choose which pages to keep, merge or redirect. Only ask for things only they can supply (for example, confirming they offer a service the site doesn't mention yet, or giving access), and put those in a short "What we need from you" section after Next Steps. Leave that section out when there is nothing to ask.

**Write for a business owner with no SEO background.** Plain words. Keep paragraphs to 3 sentences or fewer. Be specific: name the pages, services and searches. Don't pad with generic SEO education.

**Keep internal language out.** No tool names, workbook or tab names, internal labels (page types, Keep / Prune / Needs Discussion, P1 / P2, "thin content", rule numbers), keyword lists or scripts.

## Quality check

Before handing over, confirm each of these and revise until they all pass:

1. The title uses client-friendly audit wording, and the sections are exactly: At a glance, Biggest opportunities, Next Steps.
2. At a glance is a short intro plus one table (Issue, count) and nothing more.
3. Every table row matches a theme, in the same order, and every count traces to the deliverable.
4. Each theme has a plain-language why it matters and 1 to 3 examples with real data.
5. Next Steps lists only actions that exist in the deliverable, with counts, and no timelines or outcomes.
6. No promised, expected or predicted results anywhere.
7. No question asks the client to make an SEO decision.
8. No internal labels, tool names, tab names or national search volume.
9. Nothing is repeated across sections beyond the table-to-theme link.
10. Every number you added up yourself is listed in your chat note.
