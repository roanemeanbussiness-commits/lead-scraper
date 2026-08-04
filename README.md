# 8-Thon Intelligence Lead Scraper

A focused public-web email scraper for blue-collar businesses in Texas, starting with San Antonio.

The first version is seed-based: provide business websites or URLs, and the scraper crawls likely contact pages, extracts public emails, scores Texas/San Antonio relevance, and exports deduplicated CSV leads.

## What It Does

- Crawls public business websites from a seed CSV.
- Prioritizes pages like `contact`, `about`, `team`, `service`, and `locations`.
- Extracts emails from visible text and `mailto:` links.
- Extracts possible owner/founder/CEO names from public website text.
- Filters out common low-value addresses like image assets and placeholders.
- Scores leads for Texas, San Antonio, and blue-collar trade relevance.
- Exports a clean CSV with source URL, domain, email, possible owner, business name, phone, address, trade signals, and confidence.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m lead_scraper --seeds data/sample_seeds.csv --out output/leads.csv
```

## Seed CSV Format

At minimum, include a `url` column:

```csv
url,business_name,phone,address,city,state,category
https://example-plumbing.com,Example Plumbing,210-555-0100,"123 Main St, San Antonio, TX",San Antonio,TX,Plumbing
```

Extra columns are preserved when useful for scoring.

## Discovery Integrations

Google Maps discovery should feed this scraper through seed CSVs. See `docs/integrations.md` for how to use `gosom/google-maps-scraper`, `kaymen99/google-maps-lead-generator`, and `jordolang/Google-Scraper` as discovery/workflow inputs without locking this project to one scraper.

## Notes

This tool is designed for public business contact discovery. Respect robots.txt, website terms, email laws, opt-out requests, and platform rules. Do not use it for credential harvesting, private data collection, or spam.
