# Backlink audit process

Everything the audit needs is in this skill. A written copy of the process may exist elsewhere for people to read; the skill never needs it.

## Goal

Show how the client's backlink profile compares with the competitors they actually lose to, and turn that into a short list of work: links to win (sites that link to competitors but not to the client), links being wasted (backlinks pointing at client URLs that error), and links that look risky. The output is one workbook: Competitor Rollup, Disavow Review, Recommendations.

## Disavow rule

Nothing is disavowed unless Google Search Console shows a manual action for **Unnatural links to your site**. Ahrefs and Semrush risk scores are not a reason to disavow: Google ignores most spammy links on its own, and disavowing good links by mistake can hurt rankings. With no manual action, sketchy links are reviewed and monitored, never disavowed.

The manual actions result always comes from the person: the Search Console API (and so Composio) can't read it. Record it in config.json as:

| Person reports | `manual_action` | What it means |
| --- | --- | --- |
| No issues detected | `none` | Disavow Review is for monitoring only. Status is Monitor or Review closer. |
| Unnatural links to your site | `unnatural-to` | Disavow is allowed, only for domains that match the examples Google gives in the manual action. |
| Unnatural links from your site | `unnatural-from` | About the client's outbound links: fix or nofollow them on the client's site. Never disavow. |
| Any other manual action | `other` | Not a backlink issue. Say so in the report so the strategist picks it up. |
| Not checked / doesn't know | `unknown` | Treat as `none`, and say at the top of the report that it still needs checking in Search Console > Security & Manual Actions > Manual actions. |

## Competitors

3 to 5 sites that compete for the client's main service keywords in the client's market. Leave out directories, aggregators and national brands (Yelp, RealSelf, Healthline, WebMD, chains with hundreds of locations): their link profiles aren't something a local business can copy. If the person gives a competitor that looks like one of these, say so and ask whether to keep it. If they give no competitors, ask; you can suggest candidates from the client's top non-brand queries in Search Console (Composio) by searching them and noting who ranks.

## After delivery: what the person reviews

Put these next steps in the final reply so the person knows what's left for them.

**Disavow Review, no manual action (most audits).** Work by Pattern Group, opening 2-3 linking pages per group, and set Final Decision:
- Keep: a false positive (a real local or industry site with an odd anchor).
- Monitor: junk Google is very likely ignoring. The default for spam the client didn't build.
- Request removal: only for links the client or a past agency placed (paid posts, link swaps). Ask the site to remove the link or add `rel="sponsored"`.
- A large pattern of links the client clearly paid for: raise it with the client and strategist, write it up in Reviewer Notes, still don't disavow, and check Manual Actions again at the next audit.

**Disavow Review, manual action for Unnatural links to your site.**
1. Read the examples Google gives in the manual action; they define what to clean up.
2. Try removal first for links the client or a past agency placed, and log every request (date, contact, response) in Reviewer Notes.
3. Mark Disavow only for domains that match the manual action and couldn't be removed. Disavow at domain level (`domain:example.com`) unless only one page on a good site is the problem.
4. Build the disavow .txt from the Disavow rows. Uploading replaces any existing disavow file, so download the current one first and merge its entries in.
5. Upload it in Search Console's disavow links tool, then file a reconsideration request: what was found, what was removed, what was disavowed.

**Broken backlinks.** Confirm each target is the best topical match, not just the homepage. If the client has a planned redirect map (e.g. from a prune & merge), add these redirects to it so there's one map, and check for chains. For High rows from strong sites, also ask the linking site to update the link: a direct link beats a redirect. A week after the redirects go live, check each one 301s to its target in one hop.

**Link opportunities.** For each High and Medium row: is it relevant (same market or industry, or a local site the client's patients read)? Attainable (directories, locators, associations and chambers are quick; editorial links need a pitch)? Why do competitors have it (open their linking page: a sponsorship, membership, quote or listing tells you what to ask for)? Worth it (skip sites that only sell links, even if competitors are on them)? Change Priority where judgment differs, delete rows that fail, and give each kept row an owner.

**Re-run** quarterly, or after any migration or prune & merge. Compare referring domains with this audit's Rollup and check Manual Actions every time.

## Things to watch out for

- Tool scores aren't Google. Semrush risk scores and low DR/AS are reasons to look closer, never to disavow on their own.
- Don't mix tools. DR (Ahrefs) and AS (Semrush) are different scales.
- Tool data is stale: broken backlink reports lag, so every URL is checked live before it goes in the workbook.
- Uploading a disavow file replaces the old one.
- Never recommend buying links, even when every competitor has them. Paid links are what causes manual actions.
