# Mavan skills

Claude skills for Mavan's SEO processes, packaged as one plugin (`mavan-seo`) so Claude can sync them to the whole team from this repository.

| Skill | What it does | SOP |
| --- | --- | --- |
| `information-architecture-audit` | Classifies every page, finds duplicate intent, path and link problems, and fills the IA Audit template | Notion: Information Architecture Audit Process |
| `internal-linking-audit` | Finds internal linking opportunities for priority pages and builds the implementation sheet | Notion: Internal Linking Audit |
| `content-prune-merge` | Runs the Content Prune & Merge audit and fills the Prune & Merge template | Notion: Content Prune & Merge |
| `service-gap-audit` | Finds missing, thin and non-indexable service pages for medspa and plastic surgery sites from a crawl export and the bundled service taxonomy, and builds the gap audit workbook | Notion: Service Gap Audit |

## Layout

```
.claude-plugin/marketplace.json          lists the plugin
plugins/mavan-seo/.claude-plugin/plugin.json
plugins/mavan-seo/skills/<skill-name>/   SKILL.md plus any references/ and scripts/
```

## Install in Claude Code

Members who use the Claude Code terminal without org sync can install the plugin directly:

```
/plugin install mavan-seo --marketplace amandatjordan/mavan-skills
```

## Add or change a skill

1. Add or edit the folder under `plugins/mavan-seo/skills/`. The folder name must match the `name` in its SKILL.md.
2. Raise `version` in `plugins/mavan-seo/.claude-plugin/plugin.json`.
3. Open a pull request. Once it merges to `main`, the team gets it on the next sync.

To update the service taxonomy, edit `plugins/mavan-seo/skills/service-gap-audit/references/service-taxonomy.xlsx` (add the brand, device or service with its match terms on the Taxonomy tab) and open a pull request like any other change.

Keep executables in a skill's `scripts/` folder; organization sync rejects a plugin with a top-level `bin/` directory.

## Sync to the team (once, by an Owner)

The repository must be **private** for organization sync. Then, in claude.ai: **Organization settings > Plugins & skills > Add > Sync from GitHub**, pick this repository, leave **Sync automatically** on, choose the default access, and select **Create**. After it syncs, remove any copies of these skills that were uploaded by hand, so each skill exists once.
