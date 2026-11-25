# Mavan skills

Claude skills for Mavan's SEO processes, packaged as one plugin (`mavan-seo`) so Claude can sync them to the whole team from this repository.

| Skill | What it does | Matching SOP |
| --- | --- | --- |
| `information-architecture-audit` | Checks the inputs first (preflight), types every page, and builds a standalone workbook: Recommendations plus tabs for page types to check, moves and their redirects, links to fix, menu cleanup and internal linking opportunities. Search Console comes from a Google Sheet (GA4 optional, through Composio); when the client has a content prune workbook, its page types are adopted | Information Architecture Audit Process |
| `migration-sheet` | Step 1C of the Site Migration SOP. Merges the Content Prune & Merge, IA audit and (when it applies) Service Gap workbooks with the old-site crawl, a backlink export and the Search Console sheet into one migration workbook: pages to keep, merge and redirect, media with backlinks, new pages, the final navigation the SEO fills in, and the developer redirect list. Blocks on unresolved audit cells, fixes redirect chains and lists every discrepancy, never makes a live request | Site Migration SOP |
| `site-diagnosis` | One entry point for an existing site that is losing traffic. Compares two periods of Search Console page + query data (overall change, pages and searches that gained or lost, pages behind the biggest losing searches, pages competing for the same search, losing URLs that no longer return 200 when a crawl is attached), then runs the information architecture audit and the service gap audit as the evidence calls for and recommends Content Prune & Merge or the backlink audit. Reports what changed, not why | Site diagnosis |
| `internal-linking-audit` | From a crawl export and Search Console, lists which pages should link to each priority page (page to edit + page to link to) and builds the implementation sheet | Internal Linking Audit Process |
| `content-prune-merge` | Runs the Content Prune & Merge audit and delivers a workbook with a Recommendations tab, one tab per issue and a dev redirect CSV tab | Content Prune & Merge |
| `service-gap-audit` | Finds missing and non-indexable service pages for any practice that offers med spa, plastic surgery or dental services (practice type `medspa`, `surgical`, `dental` or a combination; a practice whose main business the taxonomy does not cover, such as LASIK, has its own services left out) from a crawl export and the bundled service taxonomy, and builds the gap audit workbook. Dental has no keyword volume in the taxonomy, so dental services are ranked at the High priority tier | Service Gap Audit |
| `backlink-audit` | Compares the client's backlinks with competitors, lists sketchy links for review (disavow only with a GSC manual action), and lists lost backlinks to win back and link opportunities, from Ahrefs or Semrush exports | Backlink Gap |
| `prospect-audit` | For a potential client with no Search Console or GA4: from a crawl plus Semrush or Ahrefs exports, builds the competitor keyword gap, a thin content flag and the list of ranking URLs that are not live, then runs the service gap, information architecture, title and H1 and backlink audits and drafts the prospect report. Keyword numbers are the tool's estimates | Prospect audit |
| `prospect-diagnosis` | For a potential client with no Search Console: answers which is the biggest underlying issue, authority / trust, content or site architecture, from a crawl, Semrush or Ahrefs ranking and keyword gap exports, and overview figures typed from the tool (referring domains and backlink gap exports optional; no internal links or page-level backlinks export needed). Scores fixed signals and builds a workbook with the verdict and its evidence. Optional Pleper Search Export files (3 local searches: rating, reviews, categories and local ranking for the prospect and every other business listed) add a separate GBP findings tab that never changes the verdict; anything the exports lack is not scored. Always ends by building the Site Health Report with `prospect-sales-report` | Prospect audit |
| `new-site-keyword-gap` | For a business with no website yet: from a competitor keyword gap export (Semrush Keyword Gap or Ahrefs Content Gap) and each competitor's Organic Positions, removes searches that contain a competitor's name, groups the rest by service (with a separate Local group for city and "near me" searches), flags searches where 2 or more competitors rank in the top 10 or one ranks top 3, and shows the best-ranking competitor, position and page for every keyword. Builds one workbook. Volumes are the tool's estimates and are never added together | New site keyword research |
| `new-site-keyword-research` | For a brand-new site: from the services, products or devices and (optionally) top 5 concerns the client cares most about, uses the bundled service taxonomy to list the pages to build and the keywords each should target. Says which Sub-Services and Brands / Devices earn their own page and which are a section on a parent page (and what to mention on each page), suggests which pages should link to each other, and adds unlisted services worth confirming with the client as rows with a Client offers it? column. Everything is on one Pages tab. Needs no export or connector. Volumes are national, from the taxonomy, and are never added together | New site keyword research (taxonomy) |
| `new-site-content-roadmap` | For a brand-new site: from the new-site keyword research workbook, the new-site keyword gap workbook (or one per set of competitors when the client has services that do not overlap) and the bundled blog taxonomy, lists the pages and blog posts to write content for, 50 at most, always starting with Home and About Us. Preflight asks for both workbooks and for any extra pages that need content (packages, providers, locations, events, financing, treatments by area or age); the SEO sets each one's High / Medium / Low priority. Order: Home, About Us, extras, Service, Sub-Service, Brand / Device, Blog, Concern; inside a group, client-listed first, then competitor gap, then volume. Primary keywords are highlighted for the SEO to check and replace. An Internal links tab lists every link between the pages and makes sure every Service, Sub-Service and Brand / Device page receives one. Pages that need no content from us are left to the information architecture work. Needs no connector | New site content roadmap |
| `new-site-ia` | For a brand-new site: from the new site content roadmap and a CSV of the other pages the site needs (Contact, Privacy Policy, booking, membership; URL optional), lists every page with its parent, recommended URL path and whether it is in the main nav, plus the roadmap's planned internal links with URLs added. Service, Sub-Service and Brand / Device pages sit under `/services/`, no URL is more than three segments, a `/blog` index is added, Home and the blog index are always in the main nav and blog posts never are; the SEO can change the other main nav cells. Never changes a link: gaps in the roadmap's links are reported as warnings. Needs no connector | New site IA |
| `schema-markup-templates` | For a site whose content is written: from the new site content roadmap and one real page of each page type, adds a recommended schema type to every roadmap page (treatment pages MedicalProcedure, concern pages MedicalCondition, blogs BlogPosting, the business type on Home) and writes one JSON-LD template per page type for a WordPress schema plugin to fill, with generic placeholders and every object the real page has (breadcrumbs, FAQs, reviews and so on). Gives a filled copy to test in the schema.org validator, and once the SEO confirms each passed, builds one document with every template. It cannot reach schema.org: the validator run by the person is the only validation. Needs no connector | Schema markup templates |
| `gbp-setup` | For a business building or fixing its Google Business Profile: from the new site content roadmap and Pleper Search Export files (one per priority local search, each labelled with its specialty, so a client with several specialties gets several sets), takes the top 3 categories of each export, matches the roadmap's services to them and recommends categories per specialty with a suggested primary. Flags services with no matching category and competitor categories with no matching service. Builds a Word document with the categories, the services, the products and a checklist of everything else the profile needs, plus a separate Excel sheet with a title and description for every service (275 characters at most) and product (name 45, description 750), with the limits enforced. Every recommendation is a draft the SEO confirms. Needs no connector | GBP setup |
| `client-diagnosis` | For an existing client: the prospect diagnosis plus Search Console. From a crawl, Semrush or Ahrefs exports and at least 6 months of Search Console data (with a Date column) it compares the latest 6 months with the 6 before (or two equal halves when there is less than a year), lists the keywords whose clicks fell, scores structure and content signals with real clicks and impressions (skipping any signal a capped export makes unreliable), applies a person-reported manual action to Authority & Trust, and builds a workbook with the verdict and its evidence. Optional Pleper Search Export files (3 local searches) add a separate GBP findings tab that never changes the verdict; anything the exports lack is not scored. Always ends by building the Site Health Report with `prospect-sales-report` (no onboarding column) | Client audit |
| `eeat-ymyl-audit` | For a client whose medical content may be unedited, AI-written or badly linked. Page types come from the client's IA or Content Prune & Merge workbook or a Page Type column in the crawl export. Claude in Chrome finds the extraction selectors on one sample page per type, and the person confirms on the live pages what Claude found, before the crawl and again before anything is built. A Screaming Frog or Sitebulb crawl checks every concern/condition, service and blog page against Mavan's requirements (medical reviewer, credible external source, credentials, blog author and date, MedicalCondition / MedicalProcedure / FAQPage schema, reviews, before/after photos, Google rating) and every external link; an extraction empty on a whole page type stops the build until it is checked in Chrome. Claude reads 5 random pages of each type for medical claims and flags blog or condition content for a closer review when the sample shows unsourced claims. The workbook: Recommendations (rollup findings with priority, SEO / Dev / Content next steps and a Dev or Content handoff), All Pages, External Links Needed, External Link Issues and Claims Needing Verification | E-E-A-T & YMYL audit |
| `prospect-sales-report` | From a prospect diagnosis, builds the one-page client-facing report sales goes over on the call: Site Health Score (overall and per metric), one verdict (site architecture, then content, then authority & trust), each metric's findings, and the 3-month roadmap for that track and the chosen tier, as a shareable web page. Google Maps findings are included when the diagnosis has GBP data | Prospect audit |
| `seo-audit-client-report` | Turns any finished audit's deliverables into a short client report: an at-a-glance table, the biggest themes (why each matters, with examples) and the next steps we will take. Never promises a result | Client report |
| `service-page-title-h1-review` | From a crawl export of the service pages, works out what each page is about and its target keywords from the path, H1 and title, adds each page's top non-branded Search Console queries from a Google Sheet of GSC data you provide, and flags the pages a person must review (keywords missing from the title and H1, no location in the Title Tag or H1, blanks, pages that look like they are not service pages) | Service Page H1 & Title Tag Review |

## Layout

```
.claude-plugin/marketplace.json          lists the plugin
plugins/mavan-seo/.claude-plugin/plugin.json
plugins/mavan-seo/skills/<skill-name>/   SKILL.md plus any references/ and scripts/
```

## Install

Anyone with a Claude account can use these skills; how depends on your plan. Every plan needs **code execution** turned on, because the skills run Python: Settings > Capabilities on Free, Pro and Max, or Organization settings on Team and Enterprise (an owner turns it on).

### Pro, Max, Team and Enterprise: add the marketplace (gets updates)

1. In Claude, open **Customize > Plugins** and select **Add marketplace**.
2. Enter `amandatjordan/mavan-skills`.
3. Install **mavan-seo**. When a new version is released, click **Update** on the marketplace.

On Team and Enterprise, an organization owner may need to allow outside marketplaces first.

In the Claude Code terminal:

```
claude plugin marketplace add amandatjordan/mavan-skills
claude plugin install mavan-seo@mavan-skills
```

### Free (or anyone who prefers a file): upload a skill ZIP

Free plans can use skills but not plugins. Download the ZIP for the skill you want:

| Skill | Download |
| --- | --- |
| Information architecture audit | [information-architecture-audit.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/information-architecture-audit.zip) |
| Migration sheet | [migration-sheet.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/migration-sheet.zip) |
| Site diagnosis | [site-diagnosis.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/site-diagnosis.zip) |
| Internal linking audit | [internal-linking-audit.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/internal-linking-audit.zip) |
| Content prune & merge | [content-prune-merge.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/content-prune-merge.zip) |
| Service gap audit | [service-gap-audit.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/service-gap-audit.zip) |
| Backlink audit | [backlink-audit.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/backlink-audit.zip) |
| Prospect audit | [prospect-audit.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/prospect-audit.zip) |
| Prospect diagnosis | [prospect-diagnosis.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/prospect-diagnosis.zip) |
| New-site keyword gap | [new-site-keyword-gap.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/new-site-keyword-gap.zip) |
| New site keyword research | [new-site-keyword-research.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/new-site-keyword-research.zip) |
| New site content roadmap | [new-site-content-roadmap.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/new-site-content-roadmap.zip) |
| New site IA | [new-site-ia.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/new-site-ia.zip) |
| Schema markup templates | [schema-markup-templates.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/schema-markup-templates.zip) |
| GBP setup | [gbp-setup.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/gbp-setup.zip) |
| Client diagnosis | [client-diagnosis.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/client-diagnosis.zip) |
| Prospect sales report | [prospect-sales-report.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/prospect-sales-report.zip) |
| SEO audit client report | [seo-audit-client-report.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/seo-audit-client-report.zip) |
| Service page H1 & Title Tag review | [service-page-title-h1-review.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/service-page-title-h1-review.zip) |
| E-E-A-T & YMYL audit | [eeat-ymyl-audit.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/eeat-ymyl-audit.zip) |

Then in Claude: **Customize > Skills**, **+** > **Create skill** > **Upload a skill**, and choose the ZIP. Uploaded skills do not update themselves: download the ZIP again when a new version is released ([all releases](https://github.com/amandatjordan/mavan-skills/releases)).

The whole plugin is also attached to each release as `mavan-seo.plugin`, for uploading under Customize > Plugins.

## Add or change a skill

1. Add or edit the folder under `plugins/mavan-seo/skills/`. The folder name must match the `name` in its SKILL.md.
2. Raise `version` in `plugins/mavan-seo/.claude-plugin/plugin.json`.
3. Open a pull request. Once it merges to `main`, the team gets it on the next sync, and the **Release skill downloads** workflow publishes a new release with fresh ZIPs. Raise the version on every change, or the release keeps the old version number.

To update the service taxonomy, edit `plugins/mavan-seo/skills/service-gap-audit/references/service-taxonomy.xlsx` (add the brand, device or service with its match terms on the Taxonomy tab) and open a pull request like any other change. `new-site-keyword-research` bundles its own copy at `plugins/mavan-seo/skills/new-site-keyword-research/references/service-taxonomy.xlsx` (each skill ships as its own ZIP), so copy the updated file there in the same pull request. `new-site-content-roadmap` bundles the blog taxonomy at `plugins/mavan-seo/skills/new-site-content-roadmap/references/blog-taxonomy.xlsx`; replace that file and raise the version when the blog taxonomy changes.

Keep executables in a skill's `scripts/` folder; organization sync rejects a plugin with a top-level `bin/` directory.

## Sync to the team (once, by an Owner)

The repository must be **private** for organization sync. Then, in claude.ai: **Organization settings > Plugins & skills > Add > Sync from GitHub**, pick this repository, leave **Sync automatically** on, choose the default access, and select **Create**. After it syncs, remove any copies of these skills that were uploaded by hand, so each skill exists once.
