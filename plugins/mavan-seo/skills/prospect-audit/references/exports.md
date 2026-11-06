# Keyword exports and how prep.py reads them

**These column names come from the tools' documentation and memory, not from real prospect files.** The first real run should check the printed mapping. If a field maps wrong or is missing, use `--map`; if the tool cannot be detected, use `--tool`.

## Ranking keywords (the prospect)

| Field | Semrush: Organic Research > Positions | Ahrefs: Site Explorer > Organic keywords |
| --- | --- | --- |
| keyword | Keyword | Keyword |
| position | Position | Current position |
| url | URL | Current URL |
| volume (estimate) | Search Volume | Volume |
| traffic (estimate, optional) | Traffic | Organic traffic |

Semrush also has `Traffic (%)` and `Traffic Cost`; the script renames `(%)` columns so they do not collide with `Traffic`.

## Keyword gap (prospect plus competitors)

| Field | Semrush: Keyword Gap | Ahrefs: Content Gap |
| --- | --- | --- |
| keyword | Keyword | Keyword |
| volume (estimate) | Search Volume | Volume |
| difficulty (optional) | Keyword Difficulty | KD |
| positions | one column per domain, named by the domain | one column per domain, named like `domain.com: Position` |

Per-domain columns are found by their name: a column whose name (without a trailing "position" or "rank") is a domain. Columns with `url`, `traffic`, `volume` or `difficulty` in the name are skipped. The prospect and every competitor in `config.json` must have one, or the script stops and lists the domain columns it found.

A keyword is a **gap** when at least one competitor has a position and the prospect has none (blank, 0 or "n/a").

## Detecting the tool

Semrush signals: Search Volume, Keyword Difficulty, Traffic Cost, Competitive Density, Traffic (%). Ahrefs signals: Volume, KD, Current position, Current URL, Organic traffic. The tool with more matching columns wins; a tie stops the run and asks which tool made the file. The tool name is printed and written to `work/tool.txt`, and the workbook Read Me names it.

## Limits

- Exports are capped by plan. A round row count (1,000, 10,000, 100,000 and so on) is flagged as possibly capped.
- Both tools list one URL per keyword in these exports, so competing pages are not checked.
- Ahrefs and Semrush volumes and positions are on different scales. If the two files came from different tools, the run says so; avoid mixing them.
