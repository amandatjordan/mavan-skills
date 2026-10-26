# Review rules and decisions.json

prep.py makes the first pass with pattern lists. These are the judgment calls it can't make. Every decision goes in `work/decisions.json`; build.py reads it. Never edit the workbook by hand.

```json
{
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

## Broken backlinks

Broken URLs are not taken from a tool export. build.py checks every client URL the backlinks point at against status.tsv and lists the ones that answer 404, 410 or 5xx (after redirects), or 403 while the homepage answers 200, in `work/broken_found.csv` with the referring domains and the strongest linking page. A 429, an error, or a 403 when the homepage is blocked too is treated as bot protection: those URLs are named in a warning, not listed. Open the 403 ones in a browser before keeping them.

Every broken URL needs a target (or `"action": "drop"` when the old URL was junk nobody needs, e.g. a test page with one link from a scraper).

- build.py fills the target from the redirect map when one was attached. Keep it unless it's wrong.
- Otherwise pick the closest live page by topic: the same treatment or service, then its hub, then the homepage as a last resort. If two pages are equally close, pick the one with the more specific topic match.
- `action`: `301` (default); `restore` when the page had content for a service the client still offers (say why in `note`); `typo` when the link points at a misspelling or wrong case of a real URL.
- The target must answer 200 without a redirect. build.py checks it against status.tsv.
- If a prune & merge is planned, the target must not be a page that's being merged or removed.

## Link opportunities

For each kept domain, check the type guess (domain-name keywords only, so it's often wrong) and set the real one. Types: Local directory / citation | Local news / media | Association / chamber / nonprofit | Manufacturer / provider locator | Industry publication / blog | Listicle / "best of" roundup | Sponsorship / event | Podcast / interview | Education / .edu / .gov | Partner / vendor | Other.

- `include: false` for: sites that sell links (prices for "guest posts", "write for us" marketplaces), irrelevant national sites with no way in, competitors' own other sites, anything spammy. Even when every competitor has the link.
- Add domains linking to only 1 competitor (prep.py drops them below 40 DR/AS) when they're local or industry-relevant: set them in `opportunities` with a type, and build.py adds the row from the gap export. The same works for a domain prep.py dropped as junk (spam TLDs such as .shop .store .xyz, or seo/backlink/checker/serp in the name) if it is real. It can't add a domain that already links to the client, is a competitor, or is on the Disavow Review tab. Domains not in the gap export fail the build.
- `do_this`: one or two short, concrete actions. Defaults exist per type; write a specific one for High rows and for every Other row. Never recommend buying links.
- `target`: the client page the link should point to. Homepage for directories, locators, associations, sponsorships; the matching service page for topical articles and roundups.
- `found`: optional extra sentence, e.g. what the competitor was featured for (from the Evidence URL, which is blank on Semrush audits: Backlink Gap is domain-level, so search the domain or open the competitor's site).
- Priority (prep.py's default): High = 3+ competitors, or a relevant site with DR/AS 40+; Medium = 2 competitors or DR/AS 20-39; Low = the rest. Override with `priority` when your judgment differs.
- build.py caps the tab at 75 opportunities, best first, and reports how many more there were.

## Disavow Review

The tab lists links for a person to look at. It never decides to disavow.

**Suggested Status.** prep.py sets `Review closer` for a strong flag (spam topic, paid post, repeated commercial anchor) or two or more flags, else `Monitor`. `Disavow candidate - matches manual action` is allowed only when config `manual_action` is `unnatural-to`, and only for domains that match the examples Google gave in the manual action; build.py fails the run otherwise.

**Check before keeping a row.** Look at the domain, example URL and anchor of every row (open the linking page when the row says Review closer and you can't tell from the URL). Then:

- Drop false positives (`"drop": true`): a real local or industry site, a directory, a news article, a manufacturer page, an association, a review site. A commercial anchor from a relevant local site is normal.
- Move to `noise`: scrapers, stats/"website worth"/whois pages, SEO-tool pages, AI mirror sites, link lists that copy other sites. They're summarized in one row. prep.py already sends link-seller and PBN networks there (linking page URL, anchor or title matching things like "link-outreach-services", "Premium Link Building", "Dofollow Backlinks", "PBN", "aged domains", "backlink"). A client that sells SEO may have real sites caught by that: add the domain under `disavow` (without `drop`) to take it out of noise.
- Regroup: give rows that share a pattern the same `pattern_group` ("Casino anchor network", "Foreign-language spam blogs", "Paid guest posts on general blogs") so the person reviews them together.
- Add (`disavow` entry for a domain prep.py didn't flag): hacked or injected links buried in unrelated content, links on obvious link-selling sites. The domain must be in the backlinks export. A domain added here is never treated as noise.
- Rewrite `why_flagged` in plain words when the automatic reasons are unclear.

Never flag: brand or naked-URL anchors from relevant sites, local directories and citations, local news, associations, manufacturer/provider locators (Allergan, Galderma, Evolus "find a provider" pages), review sites, the client's own social profiles.
