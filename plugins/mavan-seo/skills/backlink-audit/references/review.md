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
 "lost": {
   "realsite.com": {"priority": "High", "do_this": "Ask them to restore the link on their providers page.", "found": "Listed us as a provider in 2025."},
   "junkdirectory.info": {"include": false}
 },
 "opportunities": {
   "tampabaynews.com": {"type": "Local news / media", "do_this": "Pitch ...", "target": "https://client.com/services/botox/",
                        "found": "Competitor X was quoted in a 2025 article on lip filler trends.", "priority": "High"},
   "randomblog.com": {"include": false}
 }
}
```

Keys are domains (registrable, no www) or normalized URLs (https, no www, trailing slash), as they appear in prep.py's CSVs.

## Lost backlinks

Lost links come from the backlinks export: the rows it marks as lost (Semrush `Lost link`, Ahrefs `Lost`). Nothing is checked live. `work/lost.csv` has one row per lost link with the linking domain and page, the client URL it pointed at, the anchor, the authority, the last-seen date, whether the domain is noise, and whether the domain still links to the client from another page. build.py makes one Recommendations row per linking domain and leaves out noise and junk domains and anything on the Disavow Review tab.

- `include: false` for domains that aren't worth asking: spam directories, link sellers, scrapers prep.py didn't catch.
- `priority`: build.py's default is High for authority 40+, Medium for 20-39, Low otherwise, and Low when the domain still links from another page (often a directory that reshuffled its listing pages). Semrush page scores are low, so set the priority by judgment: a relevant local or industry site that dropped the client is worth more than its score.
- `do_this`: the default says to check why it was lost in the tool and ask for it back if the page moved or the listing changed. Write a specific one for High rows.
- Target URL stays blank: these rows are outreach, not redirects. The client URL the link pointed at is in Client URL Affected.

## Link opportunities

For each kept domain, check the type guess (domain-name keywords only, so it's often wrong) and set the real one. Types: Local directory / citation | Local news / media | Association / chamber / nonprofit | Manufacturer / provider locator | Industry publication / blog | Listicle / "best of" roundup | Sponsorship / event | Podcast / interview | Education / .edu / .gov | Partner / vendor | Other.

- `include: false` for: sites that sell links (prices for "guest posts", "write for us" marketplaces), irrelevant national sites with no way in, competitors' own other sites, anything spammy. Even when every competitor has the link.
- **Relevant** means: local (the client's city or state), specific to the client's field (med-spa, health, beauty), a provider locator, an association, or a generic local-business citation. Generic marketplaces and review platforms with AS 40+ and 1 competitor are Low.
- **Gap list cleanup.** prep.py auto-removes spam TLDs (.shop .store .space .site .online .website .xyz .icu .sbs .cfd and similar) and SEO-tool names. It does NOT remove words like "directory" or "listing": they hide real citations, so review those separately. Classify from the domain name and group similar domains together; don't visit sites. When the name doesn't say what the site is, keep the type guess or Other and say so in `found`.
- **Domain-level gap export (Semrush).** Client URL Affected and Evidence URL are blank on opportunities. That is expected, not a question for the person.
- Add domains linking to only 1 competitor (prep.py drops them below 40 DR/AS) when they're local or industry-relevant: set them in `opportunities` with a type, and build.py adds the row from the gap export. The same works for a domain prep.py dropped as junk (spam TLDs such as .shop .store .xyz, or seo/backlink/checker/serp in the name) if it is real. It can't add a domain that already links to the client, is a competitor, or is on the Disavow Review tab. Domains not in the gap export fail the build.
- `do_this`: one or two short, concrete actions. Defaults exist per type; write a specific one for High rows and for every Other row. Never recommend buying links.
- `target`: the client page the link should point to. Homepage for directories, locators, associations, sponsorships; the matching service page for topical articles and roundups.
- `found`: optional extra sentence, e.g. what the competitor was featured for (from the Evidence URL, which is blank on Semrush audits: Backlink Gap is domain-level, so search the domain or open the competitor's site).
- Priority (prep.py's default): High = 3+ competitors, or a relevant site with DR/AS 40+; Medium = 2 competitors or DR/AS 20-39; Low = the rest. Override with `priority` when your judgment differs.
- build.py caps the tab at 75 opportunities, best first, and reports how many more there were.

## Disavow Review

The tab lists links for a person to look at. It never decides to disavow.

**Suggested Status.** prep.py sets `Review closer` for a strong flag (spam topic, paid post, repeated commercial anchor) or two or more flags, else `Monitor`. `Disavow candidate - matches manual action` is allowed only when config `manual_action` is `unnatural-to`, and only for domains that match the examples Google gave in the manual action; build.py fails the run otherwise.

**Dofollow? column.** Yes = every link from the domain is dofollow, No = none are, Mixed = some of each.

**Check before keeping a row.** Look at the domain, example URL and anchor of every row (open the linking page when the row says Review closer and you can't tell from the URL). Then:

- Drop false positives (`"drop": true`): a real local or industry site, a directory, a news article, a manufacturer page, an association, a review site. A commercial anchor from a relevant local site is normal.
- Move to `noise`: scrapers, stats/"website worth"/whois pages, SEO-tool pages, AI mirror sites, link lists that copy other sites. They're summarized in one row (Links from Domain = the number of domains, AS blank). Noise is decided per domain: a domain is noise if ANY of its linking rows matches. prep.py sends link-seller and PBN networks there (linking page URL, anchor or title matching "link-outreach-services", "/all/356/", "aged domains", "seo domain research", "website stats", "url shared", "domain report", "any seo resource", "dofollow backlinks", "PBN", "guest post", "niche edit", "tiered link building", "directory pages index", "linkly.agency", "backlink"). A client that sells SEO may have real sites caught by that: add the domain under `disavow` (without `drop`) to take it out of noise.
- Regroup: give rows that share a pattern the same `pattern_group` ("Casino anchor network", "Foreign-language spam blogs", "Paid guest posts on general blogs") so the person reviews them together.
- Add (`disavow` entry for a domain prep.py didn't flag): hacked or injected links buried in unrelated content, links on obvious link-selling sites. The domain must be in the backlinks export. A domain added here is never treated as noise.
- Rewrite `why_flagged` in plain words when the automatic reasons are unclear.

Never flag: brand or naked-URL anchors from relevant sites, local directories and citations, local news, associations, manufacturer/provider locators (Allergan, Galderma, Evolus "find a provider" pages), review sites, the client's own social profiles.
