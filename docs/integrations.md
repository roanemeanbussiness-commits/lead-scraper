# Discovery Integration Plan

This project keeps discovery and enrichment separate.

Discovery tools find candidate businesses from Google Maps or search. The local `lead_scraper` package enriches their website URLs into owner/email-ready leads.

## Recommended Upstream Roles

| Project | Best Role | Notes |
| --- | --- | --- |
| `gosom/google-maps-scraper` | High-volume Google Maps discovery | Strong fit for extracting name, address, phone, website, rating, review count, coordinates, and sometimes email data. |
| `kaymen99/google-maps-lead-generator` | API-backed discovery and AI enrichment pattern | Uses Serper Maps API plus web enrichment ideas. Useful when we want predictable API-based discovery instead of browser automation. |
| `jordolang/Google-Scraper` | Outreach workflow inspiration | Useful for output structure, tests, docs, and personalized outreach templates after lead data is verified. |

## Normal Agent Workflow

1. Discovery sub-agent runs a Maps/search query such as `roofer in San Antonio, TX`.
2. Discovery output is normalized to this seed CSV shape:

```csv
url,business_name,phone,address,city,state,category
https://example-roofing.com,Example Roofing,210-555-0100,"123 Main St, San Antonio, TX",San Antonio,TX,Roofing
```

3. Website enrichment crawls the website plus high-value subpages.
4. Extraction returns public emails and likely owner names.
5. Output generator exports:

```csv
email,possible_owner,domain,source_url,business_name,phone,address,city,state,category,blue_collar_signals,texas_signals,confidence
```

## Integration Boundary

Do not vendor upstream projects directly unless their license, dependency footprint, and runtime behavior have been reviewed. Prefer calling them as optional discovery adapters that produce seed CSV files for this package.

