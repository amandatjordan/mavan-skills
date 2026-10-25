# Review rules and decisions.json

prep.py makes the first pass with pattern lists. These are the judgment calls it can't make. Every decision goes in `work/decisions.json`; build.py reads it. Never edit the workbook by hand.

```json
{
 "takeaways": ["Competitor X has 3.4x the client's referring domains; ...", "..."],
 "noise": ["somescraper.net"],
 "disavow": {
   "spamsite.xyz": {"pattern_group": "Casino anchor network", "why_flagged": "...", "status": "Review closer"},
   "realsite.com": {"drop": true},
   "notflagged.com": {"pattern_group": "Added on review", "why_flagged": "Hidden link in footer of a hacked page", "status": "Review closer"}
 },
 "broken": {
   "https://client.com/old-botox-page/": {"target": "https://client.com/services/botox/", "action": "301", "note": ""},
   "https://client.com/sevices/": {"target": "https://client.com/services/", "action": "typo"},
   "https://client.com/2019/promo/": {"action": "drop"}
 },
 "opportunities": {
   "tampabaynews.com": {"type": "Local news / media", "do_this": "Pitch ...", "target": "https://client.com/services/botox/",
                        "found": "Competitor X was quoted in a 2025 article on lip filler trends.", "priority": "High"},
   "randomblog.com": {"include": false}
 }
}
```

Keys are domains (registrable, no www) or normalized URLs (https, no www, trailing slash), as they appear in prep.py's CSVs.

## Disavow Review

The tab lists links for a person to look at. It never decides to disavow.

**Suggested Status.** prep.py sets `Review closer` for a strong flag (spam topic, paid post, repeated commercial anchor) or two or more flags, else `Monitor`. `Disavow candidate - matches manual action` is allowed only when config `manual_action` is `unnatural-to`, and only for domains that match the examples Google gave in the manual action; build.py fails the run otherwise.

**Check before keeping a row.** Look at the domain, example URL and anchor of every row (open the linking page when the row says Review closer and you can't tell from the URL). Then:

- Drop false positives (`"drop": true`): a real local or industry site, a directory, a news article, a manufacturer page, an association, a review site. A commercial anchor from a relevant local site is normal.
- Move to `noise`: scrapers, stats/"website worth"/whois pages, SEO-tool pages, AI mirror sites, link lists that copy other sites. They're summarized in one row.
- Regroup: give rows that share a pattern the same `pattern_group` ("Casino anchor network", "Foreign-language spam blogs", "Paid guest posts on general blogs") so the person reviews them together.
- Add (`disavow` entry for a domain prep.py didn't flag): hacked or injected links buried in unrelated content, links on obvious link-selling sites. The domain must be in the backlinks export.
- Rewrite `why_flagged` in plain words when the automatic reasons are unclear.

Never flag: brand or naked-URL anchors from relevant sites, local directories and citations, local news, associations, manufacturer/provider locators (Allergan, Galderma, Evolus "find a provider" pages), review sites, the client's own social profiles.

## Broken backlinks

Every broken URL needs a target (or `"action": "drop"` when the old URL was junk nobody needs, e.g. a test page with one link from a scraper).

- prep.py fills the target from the redirect map when one was attached. Keep it unless it's wrong.
- Otherwise pick the closest live page by topic: the same treatment or service, then its hub, then the homepage as a last resort. Use GSC clicks by page (references/composio.md) to choose between two equally close pages.
- `action`: `301` (default); `restore` when the page had content for a service the client still offers (say why in `note`); `typo` when the link points at a misspelling or wrong case of a real URL.
- The target must answer 200 without a redirect. build.py checks it against status.tsv.
- If a prune & merge is planned, the target must not be a page that's being merged or removed.

## Link opportunities

For each kept domain, check the type guess (domain-name keywords only, so it's often wrong) and set the real one. Types: Local directory / citation | Local news / media | Association / chamber / nonprofit | Manufacturer / provider locator | Industry publication / blog | Listicle / "best of" roundup | Sponsorship / event | Podcast / interview | Education / .edu / .gov | Partner / vendor | Other.

- `include: false` for: sites that sell links (prices for "guest posts", "write for us" marketplaces), irrelevant national sites with no way in, competitors' own other sites, anything spammy. Even when every competitor has the link.
- Add domains linking to only 1 competitor (prep.py drops them below 40 DR/AS) when they're local or industry-relevant: set them in `opportunities` with a type. They need to be in the gap export.
- `do_this`: one or two short, concrete actions. Defaults exist per type; write a specific one for High rows and for every Other row. Never recommend buying links.
- `target`: the client page the link should point to. Homepage for directories, locators, associations, sponsorships; the matching service page for topical articles and roundups.
- `found`: optional extra sentence, e.g. what the competitor was featured for (from the Evidence URL).
- Priority (prep.py's default): High = 3+ competitors, or a relevant site with DR/AS 40+; Medium = 2 competitors or DR/AS 20-39; Low = the rest. Override with `priority` when your judgment differs.
- build.py caps the tab at 75 opportunities, best first, and reports how many more there were.

## Takeaways (Competitor Rollup)

3 to 5 plain sentences, each with a number from rollup.csv or the other CSVs, e.g. "Competitor X has 3.4x the client's referring domains", "41 domains link to 2+ competitors but not the client; 12 are local directories the client can claim this week", "9 broken URLs have 63 referring domains between them".
