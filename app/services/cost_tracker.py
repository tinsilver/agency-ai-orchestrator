"""
Cost tracker for DataForSEO API calls and LLM token usage.

Provides per-endpoint call counting and estimated cost reporting
for inclusion in the audit report cost appendix.

Costs are estimates based on typical DataForSEO mid-tier pricing.
Actual costs depend on your plan, data volume, and current pricing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CostTracker:
    """
    Tracks DataForSEO API usage and LLM token consumption.

    Usage::
        tracker = CostTracker()
        data["overview"] = client.domain_rank_overview(domain)
        tracker.track_call("domain_rank_overview")
        ...
        data["cost"] = tracker.summary()
    """

    # Estimated USD cost per API call (rough mid-tier pricing)
    ENDPOINT_COSTS: dict = field(default_factory=lambda: {
        # DataForSEO Labs (live)
        "domain_rank_overview":      0.020,
        "ranked_keywords":           0.025,
        "competitors_domain":        0.020,
        "keyword_ideas":             0.020,
        "historical_rank_overview":  0.020,
        "keywords_for_site":         0.025,
        "keyword_gap":               0.025,
        "bulk_keyword_difficulty":   0.010,
        "search_intent":             0.015,
        "related_keywords":          0.020,
        # Backlinks
        "backlinks_summary":         0.010,
        "referring_domains":         0.010,
        "anchor_text":               0.010,
        "backlinks_history":         0.015,
        # OnPage (task-based)
        "onpage_task_post":          0.010,
        "onpage_summary":            0.002,
        "onpage_issues":             0.002,
        "onpage_pages":              0.002,
        "onpage_links":              0.002,
        "onpage_non_indexable":      0.002,
        "onpage_duplicate_tags":     0.002,
        "onpage_duplicate_content":  0.002,
        "onpage_redirect_chains":    0.002,
        "onpage_resources":          0.002,
        # Page Speed
        "page_speed":                0.010,
        # Content
        "content_parsing":           0.010,
        # SERP
        "serp_organic_live":         0.020,
        # AI Optimisation
        "llm_mentions_search":       0.010,
        "llm_mentions_aggregated":   0.010,
        # Business Data
        "google_business_search":    0.020,
        "google_reviews":            0.020,
        # Domain Analytics
        "domain_whois":              0.010,
        "domain_technologies":       0.010,
        # Account (free)
        "get_user_data":             0.000,
    })

    # Claude Sonnet 4.6 pricing per token
    # Input: ~$3.00/M tokens   Output: ~$15.00/M tokens
    LLM_INPUT_COST_PER_TOKEN:  float = 0.000003
    LLM_OUTPUT_COST_PER_TOKEN: float = 0.000015

    calls:             list  = field(default_factory=list)
    llm_input_tokens:  int   = 0
    llm_output_tokens: int   = 0
    llm_model:         str   = "claude-sonnet-4-6"

    def track_call(self, endpoint: str, count: int = 1) -> None:
        """Record one (or more) API calls and their estimated cost."""
        cost = self.ENDPOINT_COSTS.get(endpoint, 0.015) * count
        self.calls.append({"endpoint": endpoint, "count": count, "cost": cost})

    def track_llm(
        self,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None,
    ) -> None:
        """Record LLM token usage."""
        self.llm_input_tokens  += input_tokens
        self.llm_output_tokens += output_tokens
        if model:
            self.llm_model = model

    @property
    def api_cost(self) -> float:
        return sum(c["cost"] for c in self.calls)

    @property
    def llm_cost(self) -> float:
        return (
            self.llm_input_tokens  * self.LLM_INPUT_COST_PER_TOKEN
            + self.llm_output_tokens * self.LLM_OUTPUT_COST_PER_TOKEN
        )

    @property
    def total_cost(self) -> float:
        return self.api_cost + self.llm_cost

    def summary(self) -> dict:
        """Return a structured cost summary dict for report inclusion."""
        endpoint_totals: dict = {}
        for c in self.calls:
            e = c["endpoint"]
            if e not in endpoint_totals:
                endpoint_totals[e] = {"calls": 0, "cost_usd": 0.0}
            endpoint_totals[e]["calls"]    += c["count"]
            endpoint_totals[e]["cost_usd"] += c["cost"]

        for e in endpoint_totals:
            endpoint_totals[e]["cost_usd"] = round(endpoint_totals[e]["cost_usd"], 4)

        return {
            "api_calls_by_endpoint": endpoint_totals,
            "api_calls_total":       sum(c["count"] for c in self.calls),
            "api_cost_usd":          round(self.api_cost,  4),
            "llm_model":             self.llm_model,
            "llm_input_tokens":      self.llm_input_tokens,
            "llm_output_tokens":     self.llm_output_tokens,
            "llm_cost_usd":          round(self.llm_cost,  4),
            "total_cost_usd":        round(self.total_cost, 4),
        }
