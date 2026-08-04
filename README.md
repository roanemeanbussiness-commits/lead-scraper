# 8-Thon Intelligence Lead Scraper

A focused public-web email scraper for blue-collar businesses in Texas, starting with San Antonio.

The first version is seed-based: provide business websites or URLs, and the scraper crawls likely contact pages, extracts public emails, scores Texas/San Antonio relevance, and exports deduplicated CSV leads.

## What It Does

- Crawls public business websites from a seed CSV.
- Prioritizes pages like `contact`, `about`, `team`, `service`, and `locations`.
- Extracts emails from visible text and `mailto:` links.
- Filters out common low-value addresses like image assets and placeholders.
- Scores leads for Texas, San Antonio, and blue-collar trade relevance.
- Exports a clean CSV with source URL, domain, email, business name, trade signals, and confidence.

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
url,business_name,city,state,category
https://example-plumbing.com,Example Plumbing,San Antonio,TX,Plumbing
```

Extra columns are preserved when useful for scoring.

## Notes

This tool is designed for public business contact discovery. Respect robots.txt, website terms, email laws, opt-out requests, and platform rules. Do not use it for credential harvesting, private data collection, or spam.

