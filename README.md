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
python -m lead_scraper scrape --seeds data/sample_seeds.csv --out output/leads.csv
```

The scraper keeps memory in `data/lead_history.csv` by default. Future runs skip previously exported emails so the agent does not keep re-scraping the same usable leads.

## Seed CSV Format

At minimum, include a `url` column:

```csv
url,business_name,phone,address,city,state,category
https://example-plumbing.com,Example Plumbing,210-555-0100,"123 Main St, San Antonio, TX",San Antonio,TX,Plumbing
```

Extra columns are preserved when useful for scoring.

## Discovery Integrations

Google Maps discovery should feed this scraper through seed CSVs. See `docs/integrations.md` for how to use `gosom/google-maps-scraper`, `kaymen99/google-maps-lead-generator`, and `jordolang/Google-Scraper` as discovery/workflow inputs without locking this project to one scraper.

## Output Goal

Each run exports CSV columns for the email campaign agent:

```csv
email,possible_owner,domain,source_url,business_name,phone,address,city,state,category,blue_collar_signals,texas_signals,confidence
```

Use `--dedupe email`, `--dedupe domain`, `--dedupe email_or_domain`, or `--dedupe none` to control how aggressively the agent avoids leads it has already exported.

To prepare a filtered CSV for the email campaign agent, run:

```powershell
python -m lead_scraper export-direct --input output/leads.csv --out output/direct_leads.csv
```

This drops generic inboxes like `info@`, `support@`, and `sales@`, deduplicates emails, and fills `first_name` for campaign template tags.

## Fly.io

This repo includes a minimal FastAPI health service for Fly deployments:

```powershell
flyctl deploy -a lead-scraper-rrhtda
```

The scraper itself still runs as a CLI job. The web process exists so Fly has a stable container entrypoint and health check target.

## Notes

This tool is designed for public business contact discovery. Respect robots.txt, website terms, email laws, opt-out requests, and platform rules. Do not use it for credential harvesting, private data collection, or spam.
