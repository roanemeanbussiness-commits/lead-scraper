# 8-Thon Intelligence Ocean Lead Scraper

A focused company and decision-maker search application powered by the Ocean.io API. The live dashboard uses Ocean.io for company discovery, lookalike matching, people search, and email reveal. Google Places and OpenAI are no longer part of the dashboard search path.

## Workflow

1. Search Ocean companies with reference domains or native company filters.
2. Restrict Ocean people search to the returned company domains.
3. Select owners and senior decision-makers by seniority, department, and job-title keywords.
4. Request verified email reveals and receive results through a secured per-request webhook.
5. Suppress recently exported companies and people using persistent SQLite history.
6. Merge company and person data and export a campaign-ready CSV.

## Dashboard

The dashboard supports:

- Lookalike searches from one or more reference domains.
- Filter searches using city, state, country, industry, keywords, company size, revenue, founding year, ecommerce status, and website technologies.
- Decision-maker filters for seniorities, departments, job titles, and people per company.
- Company or verified-email targets from 1 to 1,000.
- Ocean standard-credit and email-credit estimates before each search.
- Live credit balances from Ocean's credit endpoint.
- Separate Companies and People tables.
- Background search progress and downloadable CSV results.
- A configurable 1-to-120-month deduplication window.

## Configuration

The only provider credential required by the live application is an Ocean.io API token:

```powershell
OCEAN_API_TOKEN=your_ocean_api_token
```

The existing Fly secret name `Oceanio` is also supported. Other accepted aliases are `OCEANIO`, `OCEAN_IO_API_KEY`, and `OCEAN_API_KEY`.

Runtime settings:

```powershell
OCEAN_WEBHOOK_BASE_URL=https://lead-scraper-rrhtda.fly.dev
OCEAN_STORE_PATH=/data/ocean_leads.db
OCEAN_REVEAL_WAIT_SECONDS=120
JOB_OUTPUT_PATH=/data/jobs
```

Ocean email reveal is asynchronous. Every reveal batch receives a random callback token, and callback results are stored on the Fly volume before being joined to the CSV.

## Credit Behavior

Ocean company search and people search each cost 0.2 standard credits per returned result. Email reveal costs one email credit for each found address; `notFound` results are not charged. The dashboard estimates the maximum before running and shows the live account balance.

For an email target, the app requests a larger company pool because Ocean documents an approximate 79% email find rate in its decision-maker workflow. Targets remain best effort because market size, filters, available contacts, and credit balances determine the final yield.

## CSV Output

Exports include:

```csv
business_name,owner_name,first_name,owner_role,verified_email,email_status,phone,website,domain,location,industry,company_size,technologies,linkedin_url,linkedin_profile_url,website_traffic,ocean_company_id,ocean_person_id,source
```

Company-target exports include companies even when no contact email was found. Email-target exports include only rows with an email address.

## Local Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn lead_scraper.web:app --host 127.0.0.1 --port 8080
```

Run tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Fly.io

GitHub Actions deploys every push to `master` to `lead-scraper-rrhtda`. The `lead_data` Fly volume stores jobs, email callbacks, and export history across deployments.

```powershell
flyctl deploy -a lead-scraper-rrhtda
```

Do not commit Ocean or Fly tokens. Store `Oceanio` as a Fly application secret and `FLY_API_TOKEN` as a GitHub Actions repository secret.

## Responsible Use

Use business and professional contact data lawfully. Honor opt-out requests, applicable email rules, Ocean.io's terms, and the rules of downstream outreach systems.
