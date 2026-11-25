# Schema markup templates: rules

Constants are at the top of `scripts/schema.py`. Change them there and update this file in the same pull request.

## What this skill can and cannot prove

The skill writes JSON-LD from its knowledge of schema.org and from the real page. It does not check the markup against schema.org. The person tests each filled template in the schema.org validator and the SEO confirms the result; only then is a template passed. If the validator disagrees with this file, the validator wins and this file is fixed.

`check` is a local lint, not a validation: the template is valid JSON, has `@context`, uses only described placeholders, has no empty values, and contains the group's primary type. `fill` checks that every placeholder got a value.

## Page type to primary schema type

| Roadmap page type | Primary type | Template |
| --- | --- | --- |
| Home | the business type (`medspa` is MedicalClinic, `surgical` is PlasticSurgery, `dental` is Dentist, or the type the person names) | home |
| About Us | AboutPage | about-us |
| Service, Sub-Service, Brand / Device | MedicalProcedure | treatment (one template for all three; a Sub-Service or Brand / Device has one more breadcrumb level) |
| Concern | MedicalCondition | concern |
| Blog | BlogPosting | blog |
| Extra: Package | Service, with an Offer when the page shows a price | extra-package |
| Extra: Provider | Person (Physician describes a practice, not a person) | extra-provider |
| Extra: Location | the business type, with the location's own address | extra-location |
| Extra: Event | Event | extra-event |
| Any other Extra or page type | WebPage until the real page is read | extra-<label> |

Treatment pages are MedicalProcedure and concern pages are MedicalCondition (Amanda's decision). Extra types are yellow in the workbook: the SEO confirms them once the real page is read, and if the real page shows another type fits, change the group's type in `work/plan.json` and tell the SEO.

## How a template is built

- A `@graph` of nodes, each with an `@id` where another node refers to it. Nodes point to each other by `{"@id": ...}`.
- **Page node:** WebPage (or the primary type's page, such as AboutPage). The primary entity is its `mainEntity`. Use `publisher` or `about` to connect the page to the business: `provider` is not a property of MedicalProcedure, so the business is not put inside the procedure.
- **Business node:** the full business block (name, url, logo, description, telephone, address, hours, geo, area served, hasMap, `sameAs`) lives on the Home template only. Every other template refers to it by the same `@id` (`{{business_id}}`).
- **Objects come from the real page.** The page decides which blocks the template has, not which values the paste happens to carry. Look for, and include as a block with placeholders, every object the page has (a video the paste names but gives no URL for still gets a VideoObject block):
  - BreadcrumbList when the page shows breadcrumbs or sits under a parent;
  - FAQPage with a Question and acceptedAnswer for each question and answer the page shows;
  - reviews or testimonials: Review items (author, date, text, rating) and an AggregateRating only when the page shows a rating and a count. They sit on the business node, not on a Product;
  - for a blog post: author (Person), datePublished, dateModified, headline, image;
  - an Offer when the page shows a price;
  - images, videos or other media the page carries (ImageObject, VideoObject);
  - anything else that the page clearly contains and schema.org has a type for.
- **Placeholders:** `{{lowercase_with_underscores}}`, one per value that changes between pages. Descriptive names (`page_title`, `faq_1_question`, `review_1_text`). Show two of any repeating item and note that the block repeats. Types, property names and structure are never placeholders.
- **Leave a property out rather than empty.** An empty GeoCoordinates or a blank value is removed, not kept.
- **Optional blocks** are marked in the map file's notes ("include only if the page has it").
- **Copy values exactly** from the page for the filled test copy. Never write a review, rating, answer or page text the page does not show. A value that is a technical detail the paste cannot carry (page URL, breadcrumb URLs, thumbnail, upload or publish date, meta description) is a clearly fake `example.com` test value, and the person is told which ones; the validator checks structure, not truth.

## What the person is told

Everything this skill sends is a schema template, not final site markup. Each time a template or filled copy goes out, the person is told that it has not been checked against schema.org, that they should test it in the validator and that they should paste any error or warning messages into the chat.

## Test and status

`work/status.json` holds each template's status: not started, draft (passed `check`), failed or passed. `mark ... passed` is run only after the person reports a clean validator result and the SEO confirms. `doc` refuses while any template is not passed, so a template that never passed cannot reach the document.

Reviews and ratings of a business that appear on its own site are valid schema.org markup, but Google does not show review stars for them. Say so in the reviews note; do not leave them out for that reason.
