# Ocean.io API Notes

Implementation verified against the Ocean.io API documentation on August 5, 2026.

- Company and people searches are synchronous and support up to 10,000 results per request.
- Both search endpoints cost 0.2 standard credits per returned result.
- `searchAfter` is available for result sets larger than one response.
- `peoplePerCompany: 1` returns at most one highest-matched person per target company.
- Email reveal is asynchronous, accepts 500 person IDs per request, and costs one email credit for each found address.
- Reveal webhooks return an `emails` array with `personId`, `address`, and `status` fields.
- Email statuses include `verified`, `guessed`, `catchAll`, and `notFound`.
- Self-serve rate limits are 60 requests per minute and 1,000 per day.
- The client honors `Retry-After` on HTTP 429 and retries transient server errors with bounded exponential backoff.

Documentation:

- <https://app.ocean.io/docs/searchCompaniesV3>
- <https://app.ocean.io/docs/searchPeopleV3>
- <https://app.ocean.io/docs/revealEmails>
- <https://app.ocean.io/docs/getCreditBalance>
- <https://app.ocean.io/docs/getting-started/rate-limiting>
