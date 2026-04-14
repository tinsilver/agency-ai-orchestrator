 Plan: DataForSEO Audit Enhancement — Sandbox, New Endpoints, Better  │
│ Reports                                                              │
│                                                                      │
│ Context                                                              │
│                                                                      │
│ The SEO audit tool currently uses 21 API calls across 4 tiers. The   │
│ user has identified ~35 available DataForSEO endpoints and wants us  │
│ to use all appropriate ones for the best possible report.            │
│ Additionally, we need sandbox mode for cost-free testing, and the    │
│ hardcoded business context needs to become configurable.             │
│                                                                      │
│ Two bugs were already fixed this session (type safety for pm/checks  │
│ in PDF and executive summary fallback).                              │
│                                                                      │
│ Endpoint Classification                                              │
│                                                                      │
│ Must-Have (11 new endpoints)                                         │
│                                                                      │
│ Endpoint: duplicate_tags                                             │
│ Tier: 1 (OnPage)                                                     │
│ Why: Actual URLs with duplicate title/meta — currently only          │
│ aggregate                                                            │
│   counts                                                             │
│ ────────────────────────────────────────                             │
│ Endpoint: duplicate_content                                          │
│ Tier: 1 (OnPage)                                                     │
│ Why: Near-duplicate page pairs for canonical recommendations         │
│ ────────────────────────────────────────                             │
│ Endpoint: redirect_chains                                            │
│ Tier: 1 (OnPage)                                                     │
│ Why: Multi-hop redirects wasting crawl budget                        │
│ ────────────────────────────────────────                             │
│ Endpoint: resources                                                  │
│ Tier: 1 (OnPage)                                                     │
│ Why: Broken images/CSS/JS resources                                  │
│ ────────────────────────────────────────                             │
│ Endpoint: domain_technologies                                        │
│ Tier: 2                                                              │
│ Why: CMS, analytics, CDN, framework detection                        │
│ ────────────────────────────────────────                             │
│ Endpoint: historical_rank_overview                                   │
│ Tier: 0                                                              │
│ Why: 6-12 month organic visibility trend                             │
│ ────────────────────────────────────────                             │
│ Endpoint: keywords_for_site                                          │
│ Tier: 0                                                              │
│ Why: Full keyword universe with position brackets                    │
│ ────────────────────────────────────────                             │
│ Endpoint: llm_mentions/search                                        │
│ Tier: 4 (AI, toggleable)                                             │
│ Why: Brand mentions in ChatGPT/Google AI                             │
│ ────────────────────────────────────────                             │
│ Endpoint: llm_mentions/aggregated_metrics                            │
│ Tier: 4 (AI, toggleable)                                             │
│ Why: AI impression counts and trends                                 │
│ ────────────────────────────────────────                             │
│ Endpoint: serp_organic_live (multi-keyword)                          │
│ Tier: 4                                                              │
│ Why: Local pack, AI overview, featured snippets, PAA detection       │
│ ────────────────────────────────────────                             │
│ Endpoint: keyword_overview (bulk)                                    │
│ Tier: 0                                                              │
│ Why: Efficient volume+CPC+difficulty in one call                     │
│                                                                      │
│ Skip (redundant/low-value)                                           │
│                                                                      │
│ raw_html, keywords_for_keywords, google maps, local finder, google   │
│ AI mode, chatgpt responses, gemini responses,                        │
│ ai_keyword_search_volume, domain_intersection,                       │
│ bulk_traffic_estimation, trustpilot, content_analysis/*              │
│                                                                      │
│ Implementation — 5 Phases                                            │
│                                                                      │
│ ---                                                                  │
│ Phase 1: Sandbox Mode + CLI Enhancements                             │
│                                                                      │
│ Files: dataforseo_client.py, dataforseo_audit.py,                    │
│ tools/seo_audit_cli.py                                               │
│                                                                      │
│ 1. dataforseo_client.py: Change BASE_URL from class constant to      │
│ instance attribute self.base_url. Add sandbox: bool = False param to │
│  __init__(). Set self.base_url = "https://sandbox.dataforseo.com/v3" │
│  when sandbox=True.                                                  │
│ 2. dataforseo_audit.py: Accept sandbox param in                      │
│ DataForSEOAuditService.__init__(), pass to client.                   │
│ 3. seo_audit_cli.py: Add --sandbox flag (uses real API with test     │
│ data, no credits spent). Add --business-context flag (string, e.g.   │
│ "dental practice in Manchester"). Add --ai-visibility flag (enables  │
│ Tier 4 AI endpoints). Print mode indicators in banner.               │
│ 4. Pass sandbox, business_context, ai_visibility through CLI →       │
│ service → client/executive_summary.                                  │
│                                                                      │
│ ---                                                                  │
│ Phase 2: OnPage Technical Deep Dive (4 new endpoints, Tier 1)        │
│                                                                      │
│ Files: dataforseo_client.py, dataforseo_audit.py, dataforseo_pdf.py, │
│  cost_tracker.py                                                     │
│                                                                      │
│ New client methods (all use existing task_id):                       │
│ - onpage_duplicate_tags(task_id, limit=50) → POST                    │
│ /on_page/duplicate_tags                                              │
│ - onpage_duplicate_content(task_id, limit=50) → POST                 │
│ /on_page/duplicate_content                                           │
│ - onpage_redirect_chains(task_id, limit=50) → POST                   │
│ /on_page/redirect_chains                                             │
│ - onpage_resources(task_id, limit=100, broken_only=True) → POST      │
│ /on_page/resources with filter ["resource_type","=","broken"]        │
│                                                                      │
│ In collect_data(): Add after existing Tier 1 onpage calls, gated on  │
│ if task_id:. Store as data["duplicate_tags"],                        │
│ data["duplicate_content"], data["redirect_chains"],                  │
│ data["broken_resources"].                                            │
│                                                                      │
│ PDF: Add subsections within _section_onpage():                       │
│ - "Duplicate Title/Meta Tags" — table of URL + duplicate tag value   │
│ - "Duplicate Content" — table of page pairs with similarity %        │
│ - "Redirect Chains" — table showing chain paths                      │
│ - "Broken Resources" — table of broken images/CSS/JS with HTTP       │
│ status                                                               │
│                                                                      │
│ Markdown: Add subsections under "On-Page Health".                    │
│                                                                      │
│ Mock data: Add entries for all 4 new keys.                           │
│                                                                      │
│ ---                                                                  │
│ Phase 3: Domain Intelligence (3 new endpoints, Tiers 0+2)            │
│                                                                      │
│ Files: dataforseo_client.py, dataforseo_audit.py, dataforseo_pdf.py, │
│  cost_tracker.py                                                     │
│                                                                      │
│ New client methods:                                                  │
│ - historical_rank_overview(domain, location_code) → POST             │
│ /dataforseo_labs/google/historical_rank_overview/live                │
│ - keywords_for_site(domain, location_code, limit=100) → POST         │
│ /dataforseo_labs/google/keywords_for_site/live                       │
│ - domain_technologies(domain) → POST                                 │
│ /domain_analytics/technologies/domain_technologies/live              │
│                                                                      │
│ In collect_data():                                                   │
│ - historical_rank_overview in Tier 0 after domain_rank_overview →    │
│ data["historical_rank"]                                              │
│ - keywords_for_site in Tier 0 after ranked_keywords →                │
│ data["keywords_for_site"]                                            │
│ - domain_technologies in Tier 2 → data["technologies"]               │
│                                                                      │
│ PDF:                                                                 │
│ - New _section_technologies() — table of detected tech grouped by    │
│ category (CMS, Analytics, CDN, etc.)                                 │
│ - New "Visibility Trend" subsection in _section_domain_overview() —  │
│ table showing keyword/ETV changes over months                        │
│                                                                      │
│ Markdown: Add "Technology Stack" section and "Visibility Trend"      │
│ subsection.                                                          │
│                                                                      │
│ ---                                                                  │
│ Phase 4: AI Visibility — Tier 4 (behind --ai-visibility flag)        │
│                                                                      │
│ Files: dataforseo_client.py, dataforseo_audit.py,                    │
│ aeo_geo_analysis.py, dataforseo_pdf.py, cost_tracker.py              │
│                                                                      │
│ New client methods:                                                  │
│ - llm_mentions_search(keyword, location_code=2826) → POST            │
│ /ai_optimization/llm_mentions/search/live                            │
│ - llm_mentions_aggregated(keyword, location_code=2826) → POST        │
│ /ai_optimization/llm_mentions/aggregated_metrics/live                │
│ - Reuse existing serp_organic_live() for 3-5 keywords                │
│                                                                      │
│ In collect_data(): New "Tier 4: AI Visibility" section, only when    │
│ ai_visibility=True:                                                  │
│ - Extract brand keyword (domain name) + top 2-4 traffic keywords     │
│ from Tier 0 data                                                     │
│ - Call llm_mentions_search with brand keyword → data["llm_mentions"] │
│ - Call llm_mentions_aggregated with brand keyword →                  │
│ data["llm_mentions_agg"]                                             │
│ - Call serp_organic_live for each keyword (3-5 calls) →              │
│ data["brand_serp"]                                                   │
│                                                                      │
│ aeo_geo_analysis.py: Enhance analyse() to:                           │
│ - Accept llm_mentions, llm_mentions_agg, brand_serp data             │
│ - Extract real mention counts from llm_mentions                      │
│ - Detect AI Overview, featured snippet, PAA, local pack from         │
│ brand_serp items                                                     │
│ - Update readiness score to weight real data over URL-pattern        │
│ heuristics                                                           │
│                                                                      │
│ PDF: Enhance _section_aeo() with real AI mention data, SERP feature  │
│ detection results.                                                   │
│                                                                      │
│ ---                                                                  │
│ Phase 5: Business Context + Executive Summary Enhancement            │
│                                                                      │
│ Files: executive_summary.py, dataforseo_audit.py                     │
│                                                                      │
│ 1. executive_summary.py: Replace hardcoded "hypnosis / complementary │
│  therapy" business context in _build_prompt() with a                 │
│ business_context parameter. Use the provided string if given,        │
│ otherwise use a generic default: "This is a business website seeking │
│  to improve organic search visibility."                              │
│ 2. dataforseo_audit.py: Pass business_context from run_audit()       │
│ through to executive_summary.generate().                             │
│ 3. _fallback_summary(): Also accept and use business_context for     │
│ generic recommendation text.                                         │
│                                                                      │
│ ---                                                                  │
│ Updated Step Count                                                   │
│                                                                      │
│ ┌─────────────────────────┬───────────┬───────────────┐              │
│ │          Phase          │ New Steps │ Running Total │              │
│ ├─────────────────────────┼───────────┼───────────────┤              │
│ │ Current                 │ 17        │ 17            │              │
│ ├─────────────────────────┼───────────┼───────────────┤              │
│ │ Phase 2 (OnPage)        │ +4        │ 21            │              │
│ ├─────────────────────────┼───────────┼───────────────┤              │
│ │ Phase 3 (Domain Intel)  │ +3        │ 24            │              │
│ ├─────────────────────────┼───────────┼───────────────┤              │
│ │ Phase 4 (AI Visibility) │ +3-7      │ 27-31         │              │
│ ├─────────────────────────┼───────────┼───────────────┤              │
│ │ Total                   │ +10-14    │ 27-31         │              │
│ └─────────────────────────┴───────────┴───────────────┘              │
│                                                                      │
│ Estimated Cost Per Audit                                             │
│                                                                      │
│ ┌───────────────────┬─────────┬───────────────────────────────────┐  │
│ │     Component     │ Current │         After Enhancement         │  │
│ ├───────────────────┼─────────┼───────────────────────────────────┤  │
│ │ Tier 0 (base)     │ ~$0.10  │ ~$0.14 (+historical,              │  │
│ │                   │         │ keywords_for_site)                │  │
│ ├───────────────────┼─────────┼───────────────────────────────────┤  │
│ │ Tier 1 (extended) │ ~$0.05  │ ~$0.06 (+4 onpage calls)          │  │
│ ├───────────────────┼─────────┼───────────────────────────────────┤  │
│ │ Tier 2 (advanced) │ ~$0.06  │ ~$0.07 (+technologies)            │  │
│ ├───────────────────┼─────────┼───────────────────────────────────┤  │
│ │ Tier 3 (local)    │ ~$0.04  │ ~$0.04 (unchanged)                │  │
│ ├───────────────────┼─────────┼───────────────────────────────────┤  │
│ │ Tier 4 (AI,       │ —       │ ~$0.05 (llm_mentions + 3-5 SERP)  │  │
│ │ optional)         │         │                                   │  │
│ ├───────────────────┼─────────┼───────────────────────────────────┤  │
│ │ LLM               │ ~$0.01  │ ~$0.01                            │  │
│ ├───────────────────┼─────────┼───────────────────────────────────┤  │
│ │ Total             │ ~$0.26  │ ~$0.32-0.37                       │  │
│ └───────────────────┴─────────┴───────────────────────────────────┘  │
│                                                                      │
│ Verification Plan                                                    │
│                                                                      │
│ 1. Phase 1: Run python3 tools/seo_audit_cli.py enricoviola.com       │
│ --sandbox --format json — verify all endpoints return sandbox data,  │
│ no credits spent                                                     │
│ 2. Phase 2: Run --sandbox --format all — verify new OnPage sections  │
│ render in PDF/MD with sandbox data                                   │
│ 3. Phase 3: Run --sandbox --format all — verify Technology Stack     │
│ section and Visibility Trend appear                                  │
│ 4. Phase 4: Run --sandbox --ai-visibility --format all — verify AI   │
│ Visibility section with real mention data                            │
│ 5. Phase 5: Run --sandbox --business-context "mental therapy clinic in London" --format all — verify LLM prompt uses custom context     │
│ 6. Final: Run live audit with production API key to verify real data │
│  flows end-to-end                                                    │
│                             