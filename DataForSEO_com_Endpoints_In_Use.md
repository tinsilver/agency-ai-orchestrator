# DataForSEO.com APIs in use

## Full SEO Audit
🔍 1. On-Page API
The core technical audit — crawls the site directly.

EndpointURLWhat it gives you
Task POSTPOST /v3/on_page/task_postInitiates the site crawl
SummaryPOST /v3/on_page/summaryTop-level audit: broken links, crawl errors, on-page issues score
PagesPOST /v3/on_page/pagesPer-page audit: title/meta tags, word count, H-tag structure, canonical, indexability
ResourcesPOST /v3/on_page/resourcesImages, scripts, stylesheets — identifies unoptimised assets, render-blocking 
JSLinksPOST /v3/on_page/linksAll internal and external links, dofollow/nofollow breakdownDuplicate 
TagsPOST /v3/on_page/duplicate_tagsPages with duplicate title/description tags
Duplicate ContentPOST /v3/on_page/duplicate_contentIdentifies near-duplicate page content
Redirect ChainsPOST /v3/on_page/redirect_chainsMulti-hop redirect issues
Non-Indexable PagesPOST /v3/on_page/non_indexablePages blocked by robots.txt, noindex, etc.
Instant Pages (live)POST /v3/on_page/instant_pagesQuick per-URL scan of homepage + key pages
Raw HTMLPOST /v3/on_page/raw_htmlSchema markup inspection, structured data

📈 2. DataForSEO Labs API
Keyword rankings, competitive landscape, traffic estimates.

EndpointURLWhat it gives you
Domain Rank OverviewPOST /v3/dataforseo_labs/google/domain_rank_overview/live Overall organic/paid ranking distribution
Ranked KeywordsPOST /v3/dataforseo_labs/google/ranked_keywords/liveFull list of keywords enricoviola.com ranks for in the UK
Competitors DomainPOST /v3/dataforseo_labs/google/competitors_domain/liveWho the actual SERP competitors are
Domain IntersectionPOST /v3/dataforseo_labs/google/domain_intersection/liveKeywords shared with competitors (gap analysis)
Keywords For SitePOST /v3/dataforseo_labs/google/keywords_for_site/liveKeyword opportunities relevant to the domain's topic
Keyword OverviewPOST /v3/dataforseo_labs/google/keyword_overview/liveSearch volume + CPC + difficulty for target terms (e.g. "hypnotherapist London")
Search IntentPOST /v3/dataforseo_labs/google/search_intent/liveClassifies target keywords by intent (informational vs. commercial)
Bulk Traffic EstimationPOST /v3/dataforseo_labs/google/bulk_traffic_estimation/liveEstimated monthly organic traffic
Historical Rank OverviewPOST /v3/dataforseo_labs/google/historical_rank_overview/liveRanking trajectory over time — shows if the site has grown or declined

🔗 3. Backlinks API (Premium)
Link profile health and authority.

EndpointURLWhat it gives you
SummaryPOST /v3/backlinks/summary/liveTotal backlinks, referring domains, domain rank, spam score
BacklinksPOST /v3/backlinks/backlinks/liveFull list of inbound links with anchor text, dofollow status, source rank
Referring DomainsPOST /v3/backlinks/referring_domains/liveBreakdown by linking domain with authority metrics
AnchorsPOST /v3/backlinks/anchors/liveAnchor text distribution — reveals over-optimisation risk
Domain PagesPOST /v3/backlinks/domain_pages/liveWhich pages attract the most backlinks
HistoryPOST /v3/backlinks/history/liveLink acquisition/loss over time

🗺️ 4. SERP API
Critical for a local London business.

EndpointURLWhat it gives you
Google OrganicPOST /v3/serp/google/organic/live/advancedSERP snapshot for "hypnotherapist London" and related terms — checks actual ranking position
Google MapsPOST /v3/serp/google/maps/live/advancedLocal pack visibility — is the business appearing in the map pack?
Google Local FinderPOST /v3/serp/google/local_finder/live/advancedExtended local results beyond the top 3 map pack
Google AI ModePOST /v3/serp/google/ai_mode/live/advancedHow Google's AI Overview presents results for target queries

🔑 5. Keyword Data API
Raw search volume data from Google Ads.

EndpointURLWhat it gives you
Google Ads Search VolumePOST /v3/keywords_data/google_ads/search_volume/liveExact monthly search volumes for target keyword list
Google Ads Keywords For KeywordsPOST /v3/keywords_data/google_ads/keywords_for_keywords/liveExpands seed keywords to find related opportunities

🏢 6. Business Data API
Reputation and social signals.

EndpointURLWhat it gives you
Google My Business InfoPOST /v3/business_data/google/my_business_info/task_postGMB profile completeness, categories, attributes
Google ReviewsPOST /v3/business_data/google/reviews/task_postReview count, average rating, recent review content
Trustpilot Search (if applicable)POST /v3/business_data/trustpilot/search/task_postExternal review profile

📊 7. Domain Analytics API
Technical and domain intelligence.

EndpointURLWhat it gives you
Whois OverviewPOST /v3/domain_analytics/whois/overview/liveDomain age, registrar, expiry — age is a ranking factor
Technologies SummaryPOST /v3/domain_analytics/technologies/domain_technologies/liveCMS, plugins, server stack detection

📣 8. Content Analysis API
Brand mentions and web presence.

EndpointURLWhat it gives you
SearchPOST /v3/content_analysis/search/liveFinds mentions of "Enrico Viola" / "enricoviola.com" across indexed web pages
SummaryPOST /v3/content_analysis/summary/liveAggregated mention metrics — sentiment, citation frequency

🤖 9. AI Optimization API (Premium/GEO)
Cutting-edge — how the site appears to AI platforms.

EndpointURLWhat it gives you
LLM Mentions SearchPOST /v3/ai_optimization/llm_mentions/search/liveIs enricoviola.com cited in AI responses for queries like "best hypnotherapist London"?
LLM Mentions Aggregated MetricsPOST /v3/ai_optimization/llm_mentions/aggregated_metrics/liveConsolidated AI visibility metrics by platform (ChatGPT vs Google AI)
ChatGPT LLM ResponsesPOST /v3/ai_optimization/chat_gpt/llm_responses/liveAsk ChatGPT "who is the best hypnotherapist in London?" — see if/how the client is mentioned
Gemini LLM ResponsesPOST /v3/ai_optimization/gemini/llm_responses/liveSame query run against Gemini
AI Keyword Search VolumePOST /v3/ai_optimization/ai_keyword_data/search_volume/liveHow often are hypnotherapy queries being asked in AI tools specifically

