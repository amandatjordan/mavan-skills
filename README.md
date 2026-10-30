# Mavan skills

Claude skills for Mavan's SEO processes, packaged as one plugin (`mavan-seo`) so Claude can sync them to the whole team from this repository.

| Skill | What it does | Matching SOP |
| --- | --- | --- |
| `information-architecture-audit` | Classifies every page, finds duplicate intent, path and link problems, and fills the IA Audit template | Information Architecture Audit Process |
| `internal-linking-audit` | From a crawl export and Search Console, lists which pages should link to each priority page (page to edit + page to link to) and builds the implementation sheet | Internal Linking Audit Process |
| `content-prune-merge` | Runs the Content Prune & Merge audit and fills the Prune & Merge template | Content Prune & Merge |
| `service-gap-audit` | Finds missing, thin and non-indexable service pages for medspa and plastic surgery sites from a crawl export and the bundled service taxonomy, and builds the gap audit workbook | Service Gap Audit |
| `backlink-audit` | Compares the client's backlinks with competitors, lists sketchy links for review (disavow only with a GSC manual action), and lists lost backlinks to win back and link opportunities, from Ahrefs or Semrush exports | Backlink Gap |
| `service-page-title-h1-review` | From a crawl export of the service pages, works out what each page is about and its target keywords from the path, H1 and title, adds each page's top non-branded Search Console queries when Composio is connected, and flags the pages a person must review (keywords missing from the title and H1, no location in the Title Tag or H1, blanks, pages that look like they are not service pages) | Service Page H1 & Title Tag Review |

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
| Internal linking audit | [internal-linking-audit.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/internal-linking-audit.zip) |
| Content prune & merge | [content-prune-merge.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/content-prune-merge.zip) |
| Service gap audit | [service-gap-audit.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/service-gap-audit.zip) |
| Backlink audit | [backlink-audit.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/backlink-audit.zip) |
| Service page H1 & Title Tag review | [service-page-title-h1-review.zip](https://github.com/amandatjordan/mavan-skills/releases/latest/download/service-page-title-h1-review.zip) |

Then in Claude: **Customize > Skills**, **+** > **Create skill** > **Upload a skill**, and choose the ZIP. Uploaded skills do not update themselves: download the ZIP again when a new version is released ([all releases](https://github.com/amandatjordan/mavan-skills/releases)).

The whole plugin is also attached to each release as `mavan-seo.plugin`, for uploading under Customize > Plugins.

## Add or change a skill

1. Add or edit the folder under `plugins/mavan-seo/skills/`. The folder name must match the `name` in its SKILL.md.
2. Raise `version` in `plugins/mavan-seo/.claude-plugin/plugin.json`.
3. Open a pull request. Once it merges to `main`, the team gets it on the next sync, and the **Release skill downloads** workflow publishes a new release with fresh ZIPs. Raise the version on every change, or the release keeps the old version number.

To update the service taxonomy, edit `plugins/mavan-seo/skills/service-gap-audit/references/service-taxonomy.xlsx` (add the brand, device or service with its match terms on the Taxonomy tab) and open a pull request like any other change.

Keep executables in a skill's `scripts/` folder; organization sync rejects a plugin with a top-level `bin/` directory.

## Sync to the team (once, by an Owner)

The repository must be **private** for organization sync. Then, in claude.ai: **Organization settings > Plugins & skills > Add > Sync from GitHub**, pick this repository, leave **Sync automatically** on, choose the default access, and select **Create**. After it syncs, remove any copies of these skills that were uploaded by hand, so each skill exists once.
