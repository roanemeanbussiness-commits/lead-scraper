# Legacy Scraper Improvement Research

This document records the earlier Google/OpenAI research path. The live dashboard now uses Ocean.io directly; see `docs/ocean-api-notes.md`.

## Owner Name Accuracy

Best near-term improvements:

- Crawl more owner-heavy pages: `/about`, `/about-us`, `/team`, `/our-team`, `/staff`, `/leadership`, `/company`, `/contact`, and service/location pages.
- Extract from structured data, but accept only explicit `founder` and `owner` relationships. Generic `Person`, `employee`, and `alumni` records are not owner evidence.
- Use multiple owner phrase patterns: `owned and operated by Jane Doe`, `founded by Jane Doe`, `Jane Doe, Owner`, and `meet the owner Jane Doe`.
- Use OpenAI structured outputs for the final pass over the crawled website text, but only accept owner names when the text supports them.
- Store source URL and confidence signals so questionable owner names can be reviewed instead of blindly trusted.

## Free Or Low-Cost APIs To Consider

| API | Use | Cost/Limit Notes | Fit |
| --- | --- | --- | --- |
| Google Places Text Search | Discover business name, phone, address, website, category. | Paid Google API, but already configured for this app. | Core discovery source. |
| OpenAI Structured Outputs | Extract owner, direct email, and custom opener from messy website text. | Paid API usage. | Core intelligence layer. |
| DNS MX via `dnspython` | Check whether an email domain has mail servers. | Free local DNS lookup. | Already added as optional validation. |
| RDAP | Domain registration/org metadata. | Public protocol; data availability varies by TLD/registrar/privacy. | Useful for domain-level provenance, weak for owner names due privacy redaction. |
| OpenCorporates | Legal entity search and officers where available. | API key required; open-data/free access has limits and license requirements. | Good optional legal-entity enrichment. |
| Socrata open-data APIs | Local/state datasets such as permits, licenses, and business records where cities publish them. | App tokens are free and improve throttling. Dataset availability varies. | Useful for city-specific lead sources. |
| Yelp Fusion / Places APIs | Alternate local-business discovery and categories. | Trial/free limits vary. | Secondary discovery source when Google is sparse. |
| Hunter API | Domain email discovery and email verification. | Free/test access exists; email finder/verifier consume credits. | Optional high-quality email enrichment, not required for pure scraping. |

## Google API Expansion Review

The useful Google additions are narrower than they first appear:

- [Places Aggregate API](https://developers.google.com/maps/documentation/places-aggregate/overview) is the strongest next Maps integration. It can count matching places inside circles, regions, or polygons and return Place IDs when a filtered area contains 100 or fewer matches. The scraper can use those counts to divide Texas into smaller search areas, then retrieve details through Places API. This is the recommended route for reliable 1,000-company geographic harvesting.
- [Geocoding API](https://developers.google.com/maps/documentation/geocoding/overview) can convert cities, counties, ZIP codes, and addresses into coordinates and viewports. It does not provide leads itself, but it can create the geographic tiles used by Places Aggregate and Text Search.
- [Gemini Google Search grounding](https://ai.google.dev/gemini-api/docs/google-search) can optionally search the public web for company leadership and contact evidence that is absent from a company site. It requires a separate Gemini API key and carries model/search quotas and possible usage charges, so it should be an opt-in enrichment provider with citations, caching, and strict evidence checks.
- Google Business Profile API is not a discovery option. Google's [Business Profile API policies](https://developers.google.com/my-business/content/policies) restrict it to listings the user owns or is authorized to manage and explicitly prohibit lead-generation use.

The current version implements the no-new-secret improvement first: trade-aware multi-query Places harvesting, custom 1-1,000 company/email targets, and best-effort over-collection for email goals. Places Aggregate plus Geocoding should be the next Google adapter after their APIs are enabled in the Google Cloud project.

## Recommended Roadmap

1. Keep Google Places as the main discovery source.
2. Keep website crawling as the truth source for emails and owner names.
3. Use OpenAI strict JSON output for owner/email/custom-opener extraction.
4. Add optional legal-entity enrichment later through OpenCorporates or Texas/city open datasets.
5. Add caching for Google Places results, website pages, MX checks, and OpenAI responses before scaling.
6. Add per-domain crawl rate limits and retry/backoff before running large batches.

## Implemented Open-Source Improvements

- [`scrapinghub/extruct`](https://github.com/scrapinghub/extruct) parses JSON-LD and Microdata instead of relying on one custom JSON parser.
- [`adbar/trafilatura`](https://github.com/adbar/trafilatura) produces cleaner visible page text for owner matching and the optional AI review.
- Reliability patterns from [`apify/crawlee-python`](https://github.com/apify/crawlee-python) informed bounded responses, retries, prioritized queues, and persistent state. The full browser runtime was not added because the current Fly Machine has 512 MB of memory and most local-service sites do not require browser rendering.
- Stable Google Place IDs and SQLite provide deterministic deduplication now. [`dedupeio/dedupe`](https://github.com/dedupeio/dedupe) is deferred until the scraper has labeled duplicate/non-duplicate examples; adding a trained entity-resolution engine before then would reduce accuracy.
- [`gosom/google-maps-scraper`](https://github.com/gosom/google-maps-scraper) remains an optional discovery sidecar. The app keeps the official Places API as its default to avoid shipping a second Go/browser stack and to keep data-source behavior predictable.

## Next Data Sources

The strongest next additions are Texas TDLR license records and San Antonio permit data through their public Socrata APIs. They should be integrated as separate discovery adapters with dataset-specific tests, then joined by normalized business name, phone, address, domain, and Place ID. They should not be treated as proof of an owner unless the source explicitly identifies an owner or responsible party.
