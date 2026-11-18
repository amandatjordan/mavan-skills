# GBP setup: rules

Constants are at the top of `scripts/gbp_setup.py`.

## Categories
- **Per export:** competitors are every business in the export except the client's own (matched by the exact business name). A competitor counts for a category when it appears in any of its five category slots (Primary Category, Category 2-5). Categories are ranked by how many competitors use them; ties go to the category more competitors use as their primary, then alphabetical. The top 3 are kept. A tie at third place is shown ("tied with the next category").
- **Per specialty:** the top 3s of every export with the same specialty label are combined. Competitors are compared only within their own specialty.
- **Recommended:** a category in the top 3 of at least one export **and** matched to at least one roadmap service. Shown with how many exports it was in the top 3 of, competitor use, primary use and its matching services.
- **Not recommended:** a top 3 category with no matching service. Listed so the SEO can add it if the client really offers the service.
- **Suggested primary:** the recommended category most competitors use as their primary (total across the specialty's exports); ties go to the one in more exports' top 3, then higher competitor use. None is suggested when no recommended category is anyone's primary.
- **Client's profile:** when the business name is found in an export, each recommended category shows Has it or Missing, from the five categories in the export.
- **The SEO confirms every category.** The document says so at the top.

## Services and products
- Services: roadmap rows of type Service or Sub-Service, from the Roadmap tab and the "Cut for the 50-page cap" tab (GBP has no 50-page cap). Products: Brand / Device rows. Concerns, blogs, Home, About Us and extra pages are not listed. The roadmap already leaves out anything the client does not offer.
- Each service is matched to at most one category by Claude from the printed candidates, confirmed by the SEO. A service with no match is flagged.

## Services and products sheet
Separate Excel file, one Services tab and one Products tab. Services: title (the roadmap name) and description, 275 characters at most. Products: name 45 characters at most, description 750 characters at most. Character counts are live formulas and turn red over the limit, so the SEO's edits stay checked. The build refuses blank titles or descriptions and any row over a limit, and never truncates. Descriptions use only the roadmap's own information and make no result claims.

## Checklist
Accurate NAP; Photos (facility, team, exterior, interior, results if approved); Services; Products; Hours of operation; Website link; Booking link; Menu / services link; Accessibility; Social accounts; Business description. Booking and menu / services links depend on the categories chosen, so the document tells the SEO to confirm them in the GBP dashboard. The skill does not decide which categories allow them.

## Warnings (never block)
An export with fewer than 3 businesses; a specialty with fewer than 3 exports; a business name not found in any export.

## Limits
The export lists at most 5 categories per business. Competitors from another specialty can appear in an export. Everything is a snapshot of the uploaded files.
