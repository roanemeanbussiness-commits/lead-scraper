# Scraper Improvement Research

## Owner Name Accuracy

Best near-term improvements:

- Crawl more owner-heavy pages: `/about`, `/about-us`, `/team`, `/our-team`, `/staff`, `/leadership`, `/company`, `/contact`, and service/location pages.
- Extract from structured data: JSON-LD `Person`, `founder`, `owner`, and `employee` fields.
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

## Recommended Roadmap

1. Keep Google Places as the main discovery source.
2. Keep website crawling as the truth source for emails and owner names.
3. Use OpenAI strict JSON output for owner/email/custom-opener extraction.
4. Add optional legal-entity enrichment later through OpenCorporates or Texas/city open datasets.
5. Add caching for Google Places results, website pages, MX checks, and OpenAI responses before scaling.
6. Add per-domain crawl rate limits and retry/backoff before running large batches.

