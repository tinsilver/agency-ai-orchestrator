# DataForSEO SEO Audit — CLI Guide

Runs a full premium SEO audit for any domain using the DataForSEO API v3.
Outputs structured **JSON**, **Markdown**, and/or a branded **PDF** report.

---

## Quick Start

```bash
# Activate the virtualenv first
source .venv/bin/activate

# Full audit with JSON + Markdown output (default)
python tools/seo_audit_cli.py enricoviola.com

# All three formats
python tools/seo_audit_cli.py enricoviola.com --format all

# PDF only
python tools/seo_audit_cli.py enricoviola.com --format pdf

# Mock mode (no API calls, useful for testing)
python tools/seo_audit_cli.py enricoviola.com --mock --format all

# Deep mode — adds per-page SERP content gap analysis (paid)
python tools/seo_audit_cli.py enricoviola.com --format all --deep

# Deep mode with mock data (no API calls)
python tools/seo_audit_cli.py enricoviola.com --mock --deep --format all
```

---

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `domain` | *(required)* | Domain to audit. Protocol and `www.` are stripped automatically. |
| `--format` / `-f` | `json md` | Output formats: `json`, `md`, `pdf`, or `all`. |
| `--output-dir` / `-o` | `reports/` | Directory to write files into. Created if it doesn't exist. |
| `--location` / `-l` | `us` | Target market for keyword/SERP data (see table below). |
| `--mock` | *(off)* | Use synthetic data. Skips API calls — no quota consumed. |
| `--deep` | *(off)* | Per-page SERP content gap analysis (positions 4–30). Expensive — see below. |

---

## Location Codes

| Shortcode | Country | DataForSEO Code |
|-----------|---------|-----------------|
| `us` | United States (default) | 2840 |
| `uk` | United Kingdom | 2826 |
| `au` | Australia | 2036 |
| `ca` | Canada | 2124 |
| `de` | Germany | 2276 |
| `fr` | France | 2250 |
| `it` | Italy | 2380 |
| `es` | Spain | 2724 |
| `nl` | Netherlands | 2528 |

Or pass a raw [DataForSEO location code](https://docs.dataforseo.com/v3/appendix/locations/) integer directly:

```bash
python tools/seo_audit_cli.py enricoviola.com --location 2380   # Italy
```

---

## Examples

```bash
# UK audit, PDF only, custom output directory
python tools/seo_audit_cli.py example.co.uk --location uk --format pdf --output-dir ~/Desktop/audits

# Multiple formats explicitly
python tools/seo_audit_cli.py mybrand.com --format json md pdf

# UK market audit with deep mode
python tools/seo_audit_cli.py enricoviola.com --location uk --format all --deep

# Quick test without spending API credits
python tools/seo_audit_cli.py anydomain.com --mock --format all
```

---

## Output Files

All files are saved to `reports/` (or `--output-dir`) with the naming pattern:

```
{domain}_{YYYYMMDD}.json
{domain}_{YYYYMMDD}.md
{domain}_{YYYYMMDD}.pdf
```

Example output for `enricoviola.com` run on 2026-02-24:

```
reports/
├── enricoviola_com_20260224.json   ← full structured data for AI agents
├── enricoviola_com_20260224.md     ← concise summary for AI context / prompts
└── enricoviola_com_20260224.pdf    ← branded client report (Theo Ruby SEO Agency)
```

### JSON
Full raw API responses from all DataForSEO endpoints plus `aeo_geo`, `executive_summary`, and `cost` keys. Use this to feed data into AI agent pipelines or for custom downstream processing.

### Markdown
Concise human-readable summary with tables for metrics, keywords, competitors, on-page issues, AEO signals, opportunities, and recommendations. Ideal for injecting into AI agent context windows.

### PDF
Branded A4 client report with cover page, TOC, and up to 12 sections:

| # | Section | Notes |
|---|---------|-------|
| 1 | Executive Summary | LLM-generated (Claude Haiku): current state, top 5 opportunities, dev time estimate, workstream plan |
| 2 | Domain Overview & Authority | WHOIS, domain rank, backlink counts |
| 3 | Organic Keyword Rankings | Top keywords with KD, intent, and keyword gap table |
| 4 | Competitive Landscape | Top 10 organic competitors |
| 5 | Backlink Profile | Summary + anchor text distribution |
| 6 | On-Page & Technical SEO | Issue counts, broken pages, non-indexable pages |
| 7 | Page Speed & Core Web Vitals | Lighthouse scores |
| 8 | Local SEO | Google Business Profile details and reviews |
| 9 | AEO & AI Overview Readiness | Schema coverage, E-E-A-T signals, readiness score, recommendations |
| 10 | Per-Page Content Gaps | *(only with `--deep`)* — per-keyword word count and content gap actions |
| 11 | Priority Recommendations | Ranked action list with workstream column (Developer / VA / Consultancy) |
| 12 | Cost Appendix | API call counts by endpoint + LLM token usage with estimated USD costs |

---

## What the Audit Covers

### Standard (always collected)

| Data Type | Endpoint | Notes |
|-----------|----------|-------|
| Domain rank overview | `dataforseo_labs/google/domain_rank_overview/live` | Organic/paid keyword counts, ETV |
| Ranked keywords | `dataforseo_labs/google/ranked_keywords/live` | Top 50 by estimated traffic |
| Competitors | `dataforseo_labs/google/competitors_domain/live` | Top 10 organic competitors |
| Backlink summary | `backlinks/summary/live` | Total links, referring domains, broken |
| Referring domains | `backlinks/referring_domains/live` | Top 30 by domain rank |
| On-page crawl | `on_page/task_post` → poll → `on_page/summary` | Crawls up to 100 pages |
| On-page issues | `on_page/pages/issues_by_type` | Broken links, missing tags, duplicates |
| Page speed | `on_page/instant_pages` | Lighthouse scores + Core Web Vitals |
| SERP organic | `serp/google/organic/live/regular` | Used for competitor SERP + local pack detection |
| Keyword gap | `dataforseo_labs/google/keyword_gap/live` | Keywords competitors rank for that you don't |
| Anchor text | `backlinks/anchors/live` | Top 30 anchor text phrases |
| WHOIS | `domain_analytics/whois/overview/live` | Expiry date, registrar |
| Internal links | `on_page/links` | Internal link structure |
| Non-indexable pages | `on_page/non_indexable` | Pages blocked from Google indexing |
| Backlink history | `backlinks/history/live` | Link acquisition trend |
| Keyword difficulty | `dataforseo_labs/google/bulk_keyword_difficulty/live` | Top-10 keyword difficulty scores |
| Search intent | `dataforseo_labs/google/search_intent/live` | Informational / commercial / transactional |
| Related keywords | `dataforseo_labs/google/related_keywords/live` | Expansion opportunities |
| Google Business Profile | `business_data/google/my_business_search/live` | GBP name, address, rating |
| Google Reviews | `business_data/google/reviews/live` | Recent reviews for sentiment analysis |

### Deep mode (`--deep`)

| Data Type | Per keyword | Notes |
|-----------|-------------|-------|
| SERP results | 1 call/keyword | Identifies top 3 ranking competitor pages |
| Content parsing | Up to 3 calls/keyword | Word count, H2/H3 structure of competitor pages |

**Cost:** ~4 API calls per gap keyword × up to 5 keywords = up to 20 additional calls.

---

## Report Tiers

The audit is structured internally in tiers of increasing cost:

| Tier | Data | API Credit Cost (approx.) |
|------|------|--------------------------|
| 0 — Core | Domain overview, keywords, competitors, backlinks | ~$0.08 |
| 1 — Technical | Keyword gap, anchors, WHOIS, internal links, non-indexable | ~$0.03 |
| 2 — Intelligence | Backlink history, keyword difficulty, search intent, related keywords | ~$0.05 |
| 3 — Local | Google Business Profile, Google Reviews | ~$0.02 |
| Deep | Per-keyword SERP + content parsing (opt-in) | ~$0.04–$0.20 |
| LLM | Executive summary via Claude Haiku | ~$0.001 |

Exact costs vary by domain size and are printed in the **Cost Appendix** section of the PDF.

---

## AEO / GEO Analysis

The **AEO & AI Overview Readiness** section is always included and covers:

- **Schema coverage** — LocalBusiness, FAQPage, Person, Article, Review schema detected
- **E-E-A-T signals** — About page, Contact page, Privacy page, referring domains
- **Local SEO** — GBP status, local pack presence, review count and rating
- **AI Overview readiness score** — 0–100 composite score
- **Recommendations** — Prioritised actions split by workstream (Developer / VA / Consultancy)

No additional API calls are required — all signals are derived from data already collected.

---

## Executive Summary (LLM-generated)

When `ANTHROPIC_API_KEY` is set, the first section of the PDF is generated by **Claude Haiku** and covers:

- Current state with specific metrics
- Top 5 prioritised opportunities (impact × effort ratings)
- Developer time estimate with task breakdown
- Workstream plan: what to give to a developer, a VA, and a consultancy
- AEO readiness narrative

If the LLM call fails or the API key is absent, a static fallback summary is used instead. The `_source` field in the JSON output indicates whether the summary is `"llm"` or `"fallback"`.

---

## Using from a Python Workflow Agent

```python
from app.services.dataforseo_audit import DataForSEOAuditService

service = DataForSEOAuditService()

# Standard audit
result = await service.run_audit(
    domain="enricoviola.com",
    formats=["json", "md", "pdf"],
    location_code=2380,           # Italy
    output_dir="reports/",
)

# Deep audit with per-page gap analysis
result = await service.run_audit(
    domain="enricoviola.com",
    formats=["pdf"],
    location_code=2380,
    output_dir="reports/",
    deep=True,
)

# Access raw data
data = result["data"]
aeo  = data["aeo_geo"]          # AEO/GEO readiness dict
exec = data["executive_summary"] # LLM summary dict
cost = data["cost"]              # API + LLM cost summary
```

---

## Environment Variables

Set in `.env`:

```env
DATAFORSEO_API_KEY=dGhlb0B0aGVvcnVieS5jb206...==   # base64(login:password)
ANTHROPIC_API_KEY=sk-ant-...                          # for LLM executive summary
SEO_AGENCY_NAME=Theo Ruby SEO Agency
```

---

## When to use each service

| Service | File | Cost | Speed | Best for |
|---------|------|------|-------|----------|
| `SEOAuditService` | `app/services/seo_audit.py` | Free | Instant | Quick per-URL checks in enrichment workflow |
| `DataForSEOAuditService` | `app/services/dataforseo_audit.py` | Paid (API credits) | 2–8 min | Full client domain audits with PDF delivery |

The BeautifulSoup-based `SEOAuditService` remains active in the enrichment pipeline for lightweight, no-cost page-level checks. Use `DataForSEOAuditService` when you need comprehensive data for a client report.
