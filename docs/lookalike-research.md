# Like-for-Like Company Discovery

## What Ocean's Public Product Reveals

Ocean.io describes a workflow where users provide one or more company domains and receive ranked lookalikes from a pre-indexed company database. Its public API material describes context-vector similarity plus filters such as industry, technology, headcount, location, growth, and revenue. Customer examples also show that strong searches commonly use several positive reference companies and add firmographic or digital-presence filters after similarity retrieval.

This creates two separate technical problems:

1. Candidate generation: maintain or query a broad universe of companies.
2. Candidate ranking: decide which candidates are genuinely like the reference companies.

Embeddings solve the second problem, not the first. A vector database cannot discover a company that has never been collected and indexed.

Sources:

- [Ocean.io company search](https://www.ocean.io/)
- [Ocean.io API](https://www.ocean.io/api)
- [Explorium lookalike company API](https://explorium-api.readme.io/reference/lookalike-companies)
- [U.S. Department of Labor website-similarity research brief](https://www.dol.gov/sites/dolgov/files/OASP/evaluation/pdf/Using-Similarity-Scores-to-Identify-Organizations-of-Interest-by-Website-Research-Brief.pdf)

## Implemented Architecture

The 8-Thon implementation follows a two-stage retrieval and reranking design:

1. Crawl two to four positive reference websites and optional negative examples.
2. Convert public website evidence into normalized company fingerprints.
3. Embed the fingerprints with `text-embedding-3-small`.
4. Search the persistent SQLite catalog first.
5. Expand a small candidate pool through several AI-derived Google Places queries when the catalog needs more coverage.
6. Crawl and fingerprint new candidates concurrently, then add them to the catalog.
7. Rank candidates with semantic, structured, and lexical similarity.
8. Penalize candidates close to the negative examples.
9. Use a bounded LLM pass to rerank only the best candidates and produce factual fit reasons.
10. Reuse crawled pages for owner and direct-email enrichment, then export CSV.

The Claude teardown supplied after the first implementation highlighted Ocean's structured filter taxonomy and crawl-on-demand behavior. Version 0.4 incorporates the recommendations that are supportable from the project's current public-web data:

- `precise` and `broad` matching modes
- compound industry and any/all/none keyword filtering through normalized fingerprint fields
- technology include/exclude filters using deterministic page-source signatures
- active-hiring, social-presence, and e-commerce signals
- catalog freshness filters and six-month reference-profile caching
- query-specific Fit / Not fit feedback that adjusts future ranking
- preview-first scored results and estimated API-call transparency
- richer CSV company records, including summary, technology, social, hiring, commerce, founding-year, stated-size, and headquarters fields

Revenue, funding, traffic, employee-growth, and department-growth filters are intentionally not fabricated. They require licensed sources, reliable registries, or repeated historical observations. LinkedIn people data is also not scraped because the project does not have a licensed source. SMTP mailbox probing and email sending remain outside this scraper-only product.

## Interface Research

Ocean's public product screenshots show a compact filter rail, precise-company-match controls, and a scored company table with quick actions. The 8-Thon dashboard adopts that operational pattern while using its own branding, copy, colors, and code. It does not reproduce Ocean trademarks or protected visual assets.

- [Ocean AI Company Search](https://www.ocean.io/features/ai-company-search)
- [Ocean current lookalike workflow](https://www.ocean.io/)
- [Clay preview-based Ocean integration](https://www.clay.com/changelog/ocean-io)

The final base score is deliberately inspectable:

- 62% embedding similarity across the positive examples
- 25% structured overlap in services, customers, business model, industry, and specialties
- 13% lexical overlap
- Up to a 20-point negative-example penalty

For multiple positive examples, the scorer blends median and best-match similarity. The median rewards the shared ICP while the best-match component preserves valid subtypes. The Department of Labor's research similarly found that multiple known sites and subpage content improve website-similarity discovery, while similarity alone still benefits from a second review stage.

## Why SQLite Instead of Chroma or FAISS

The current Fly machine has 512 MB of memory and the Texas catalog will initially contain hundreds or thousands of companies. Exact cosine scoring is fast at that size and avoids a heavy service dependency. Embeddings are stored as compact float32 blobs in the existing durable SQLite volume.

At much larger scale, the catalog interface can move to `sqlite-vec`, PostgreSQL with `pgvector`, or FAISS without changing the fingerprint and scoring contracts.

- [sqlite-vec](https://github.com/asg017/sqlite-vec)
- [FAISS](https://github.com/facebookresearch/faiss)
- [Sentence Transformers retrieve and rerank](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)

## Free Candidate Universes Worth Adding

The strongest free sources are data imports, not owner-email APIs:

- [Overture Maps Places](https://docs.overturemaps.org/guides/places/) provides downloadable POIs with categories, addresses, websites, phones, emails, social links, confidence, and stable GERS IDs. A scheduled Texas bbox import is the best next expansion path.
- [Foursquare Open Source Places](https://docs.foursquare.com/data-products/docs/fsq-places-open-source) provides a large Apache 2.0 POI dataset with websites, phones, addresses, categories, and quality fields. Its current portal access requires an account token.
- [Texas Open Data Portal](https://data.texas.gov/) and local licensing or permit datasets can validate trade type and operating status. These should only provide owner evidence when a field explicitly identifies an owner.

These sources should feed the company catalog in background import jobs. Running a statewide GeoParquet scan inside a dashboard request would be unreliable on the current small Fly machine.

## Quality Measurement

A similarity system should be evaluated with a labeled set, not by whether individual results sound plausible. Recommended metrics are Precision@10, NDCG@10, direct-email yield, owner-evidence yield, candidate crawl success, and user acceptance/rejection rate. Save rejected examples as explicit negatives for the next query instead of globally teaching that a company is always a bad lead.

Useful retrieval references:

- [Reciprocal Rank Fusion for hybrid retrieval](https://arxiv.org/abs/2210.11934)
- [Maximal Marginal Relevance](https://aclanthology.org/anthology-files/pdf/X/X98/X98-1025.pdf)
- [OpenAI text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small)

## Practical Boundary

This implementation reproduces the public workflow and core ranking ideas, but it does not claim to copy Ocean's proprietary model, private data, or tens-of-millions-company index. Its advantage is focus: the catalog can become a high-quality Texas blue-collar universe with transparent scoring, public evidence, and direct integration into owner/email enrichment.
