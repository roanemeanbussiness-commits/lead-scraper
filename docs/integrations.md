# Ocean.io Integration

Ocean.io is the live application's only search and enrichment provider.

| Capability | Endpoint | Behavior |
| --- | --- | --- |
| Company search | `POST /v3/search/companies` | Native filters, lookalike domains, up to 10,000 results per request |
| People search | `POST /v3/search/people` | Seniority, department, job-title, company-domain, and people-per-company filters |
| Email reveal | `POST /v2/reveal/emails` | Asynchronous callback, batches of up to 500 person IDs |
| Credit balance | `GET /v2/credits/balance` | Standard, email, phone, preview, and daily request balances |

## Security Boundary

The browser never receives the Ocean API token. FastAPI sends it only in the server-side `x-api-token` header. Email callback URLs contain a random one-time token and reveal data is written to the persistent SQLite store.

## Legacy Modules

The public-web crawler, Google Places adapter, and OpenAI enrichment modules remain in the repository for CLI compatibility and rollback. The dashboard and `/api/jobs/ocean` route do not call them.
