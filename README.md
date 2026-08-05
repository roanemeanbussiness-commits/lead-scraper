# 8-Thon Intelligence Lead Scraper

A focused public-web lead scraper for blue-collar businesses in Texas, starting with San Antonio.

Use the dashboard to search Google Maps by business type and location, or provide business websites directly. The scraper crawls likely contact pages, extracts public emails, enriches owner/email/opener fields when OpenAI is configured, validates email domains when requested, and exports deduplicated CSV leads.

## What It Does

- Crawls public business websites from a seed CSV.
- Prioritizes pages like `contact`, `about`, `team`, `service`, and `locations`.
- Extracts emails from visible text and `mailto:` links.
- Extracts role-specific owner/founder names from visible text, JSON-LD, and Microdata.
- Records owner role, evidence, source URL, and confidence instead of treating every schema `Person` as an owner.
- Uses OpenAI, when configured, only when deterministic owner evidence is missing.
- Decodes Cloudflare-protected and common `[at]` / `[dot]` email formats.
- Validates public URLs and redirects, respects `robots.txt`, limits response sizes, and retries transient failures.
- Paginates Google Places Text Search up to its 60-result limit and retains stable Place IDs.
- Optionally verifies email domains with MX record checks.
- Filters out common low-value addresses like image assets and placeholders.
- Scores leads for Texas, San Antonio, and blue-collar trade relevance.
- Exports a clean CSV with source URL, domain, email, possible owner, business name, phone, address, trade signals, and confidence.

## API Keys

Set these in your local shell or Fly.io secrets:

```powershell
GOOGLE_MAPS_API_KEY=your_google_maps_key
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
```

`GOOGLE_MAPS_API_KEY` powers Google Places search from the dashboard. `OPENAI_API_KEY` is optional but improves owner-name, direct-email, and custom-opener enrichment.

The app also recognizes legacy Fly secret aliases `GooglePlacesAPI`, `GOOGLE_PLACES_API_KEY`, `OpenAI_api`, and `OPENAI_API`.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m lead_scraper scrape --seeds data/sample_seeds.csv --out output/leads.csv
```

The scraper keeps memory in `data/lead_history.db` by default. SQLite tracks exported emails, domains, and Google Place IDs so future runs do not re-scrape the same usable leads. Legacy CSV history paths remain supported.

## Seed CSV Format

At minimum, include a `url` column:

```csv
url,business_name,phone,address,city,state,category
https://example-plumbing.com,Example Plumbing,210-555-0100,"123 Main St, San Antonio, TX",San Antonio,TX,Plumbing
```

Extra columns are preserved when useful for scoring.

## Discovery Integrations

Google Maps discovery should feed this scraper through seed CSVs. See `docs/integrations.md` for how to use `gosom/google-maps-scraper`, `kaymen99/google-maps-lead-generator`, and `jordolang/Google-Scraper` as discovery/workflow inputs without locking this project to one scraper.

See `docs/research.md` for owner-name extraction improvements and optional free/low-cost APIs that can improve lead quality.

## Output Goal

The raw scraper export uses these columns:

```csv
email,possible_owner,owner_role,owner_evidence,owner_source_url,owner_confidence,custom_opener,place_id,domain,source_url,business_name,phone,address,city,state,category,blue_collar_signals,texas_signals,confidence
```

Use `--dedupe email`, `--dedupe domain`, `--dedupe email_or_domain`, or `--dedupe none` to control how aggressively the agent avoids leads it has already exported.

To prepare a filtered direct-lead CSV, run:

```powershell
python -m lead_scraper export-direct --input output/leads.csv --out output/direct_leads.csv
```

This drops generic inboxes like `info@`, `support@`, and `sales@`, deduplicates emails, and fills `first_name` for downstream tools. Add `--verify-mx` to require each email domain to have MX mail records.

## Fly.io

This repo includes a minimal FastAPI health service for Fly deployments:

```powershell
flyctl deploy -a lead-scraper-rrhtda
```

The dashboard at `/` can start a scrape and return a downloadable CSV.

Search by business type and location, or paste one business website URL per line, then download `scraped_leads.csv`. Use the dashboard's MX option when you want stricter email-domain validation.

Fly mounts the `lead_data` volume at `/data`, where the SQLite history survives deploys and Machine restarts.

## Auto Deploy

GitHub Actions deploys to Fly on every push to `master`.

Add a GitHub Actions repository secret named `FLY_API_TOKEN` with a Fly deploy token. Do not commit Fly tokens to the repo. You can also run the `Fly Deploy` workflow manually from the GitHub Actions tab.

## Notes

This tool is designed for public business contact discovery. Respect robots.txt, website terms, email laws, opt-out requests, and platform rules. Do not use it for credential harvesting, private data collection, or spam.
