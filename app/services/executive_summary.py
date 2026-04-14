"""
LLM-generated executive summary for SEO audit reports.

Uses Claude Haiku via LangChain to produce a structured executive summary
covering: present state, opportunity scale, developer time estimate,
workstream groupings (VA / developer / consultancy), and AEO readiness.

Falls back to a static summary if the LLM call fails or is unavailable.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from langfuse import observe

from app.services.dataforseo_client import first_result, safe_get


_SYSTEM_PROMPT = """\
You are a senior SEO consultant writing the executive summary section of a \
client-facing SEO audit report. Your audience is a business owner, not a \
developer — be clear, specific, and action-oriented.

Write in professional British English. Use specific numbers from the data \
wherever possible. Do not use jargon without explanation.

Return ONLY a valid JSON object in the exact structure specified. \
No preamble, no markdown fences, no commentary outside the JSON.\
"""


def _build_prompt(data: dict, aeo: Optional[dict], business_context: Optional[str] = None) -> str:
    domain   = data.get("domain", "unknown")
    # domain_rank_overview: metrics at result[0].items[0]
    ov_result = first_result(data.get("overview", {})) or {}
    ov_items  = safe_get(ov_result, "items", default=[]) or []
    ov        = ov_items[0] if ov_items else {}
    bl        = first_result(data.get("backlinks",     {})) or {}
    pm        = safe_get(data.get("onpage_summary", {}),
                         "tasks", 0, "result", 0, "page_metrics") or {}
    if not isinstance(pm, dict):
        pm = {}
    checks    = safe_get(pm, "checks", default={}) or {}
    if not isinstance(checks, dict):
        checks = {}
    # page_speed: data at result[0].items[0]
    ps_result = first_result(data.get("page_speed", {})) or {}
    ps_items  = safe_get(ps_result, "items", default=[]) or []
    ps_item   = ps_items[0] if ps_items else {}
    kw_items  = safe_get(data.get("keywords",       {}),
                         "tasks", 0, "result", 0, "items", default=[])
    comp      = safe_get(data.get("competitors",    {}),
                         "tasks", 0, "result", 0, "items", default=[])

    # Numeric helpers
    def _int(v, default=0):
        try: return int(v or default)
        except (TypeError, ValueError): return default

    def _pct(v):
        if v in (None, "N/A"): return "not measured"
        try:
            f = float(v)
            return f"{int(f * 100) if f <= 1.0 else int(f)}/100"
        except (TypeError, ValueError): return "not measured"

    organic_kws  = _int(safe_get(ov, "metrics", "organic", "count"))
    etv          = _int(safe_get(ov, "metrics", "organic", "etv"))
    pos_1        = _int(safe_get(ov, "metrics", "organic", "pos_1"))
    pos_4_10     = _int(safe_get(ov, "metrics", "organic", "pos_4_10"))
    backlinks    = _int(safe_get(bl, "backlinks"))
    ref_domains  = _int(safe_get(bl, "referring_domains"))
    broken_pages  = _int(checks.get("is_broken", 0) or safe_get(pm, "broken_links", default=0))
    missing_desc  = _int(checks.get("no_description", 0))
    pages_crawled = _int(safe_get(pm, "pages_crawled", default=0))
    onpage_score  = safe_get(ps_item, "onpage_score", default=None)
    perf_score    = f"{int(float(onpage_score))}/100" if onpage_score else "not measured"

    top_comp     = safe_get(comp, 0, "domain", default="unknown") if comp else "unknown"
    top_comp_etv = _int(safe_get(comp, 0, "metrics", "organic", "etv")) if comp else 0
    top_kw       = safe_get(kw_items, 0, "keyword_data", "keyword", default="unknown") if kw_items else "unknown"

    gbp_found    = safe_get(aeo, "local", "gbp_found",    default=False) if aeo else False
    has_faq      = safe_get(aeo, "schema", "has_faq_page", default=False) if aeo else False
    in_local_pack = safe_get(aeo, "local", "in_local_pack", default=False) if aeo else False
    aeo_score    = safe_get(aeo, "ai_overview", "readiness_score", default="N/A") if aeo else "N/A"
    gbp_rating   = safe_get(aeo, "local", "gbp_rating",   default="N/A") if aeo else "N/A"
    gbp_reviews  = safe_get(aeo, "local", "gbp_reviews",  default=0)     if aeo else 0

    return f"""\
Analyse this SEO audit data for {domain} and return a JSON object with \
EXACTLY these keys:

{{
  "state_summary": "<2-3 sentences on current SEO position with specific numbers>",
  "opportunities": [
    {{"rank": 1, "title": "...", "description": "...", "expected_impact": "high|medium|low", "effort": "low|medium|high"}},
    {{"rank": 2, "title": "...", "description": "...", "expected_impact": "high|medium|low", "effort": "low|medium|high"}},
    {{"rank": 3, "title": "...", "description": "...", "expected_impact": "high|medium|low", "effort": "low|medium|high"}},
    {{"rank": 4, "title": "...", "description": "...", "expected_impact": "high|medium|low", "effort": "low|medium|high"}},
    {{"rank": 5, "title": "...", "description": "...", "expected_impact": "high|medium|low", "effort": "low|medium|high"}}
  ],
  "dev_time_estimate": {{
    "total_hours": <integer>,
    "notes": "<brief note on assumptions>",
    "breakdown": [
      {{"task": "...", "hours": <int>, "workstream": "developer|va|consultancy"}}
    ]
  }},
  "workstreams": {{
    "developer":   ["<task>", "<task>"],
    "va_content":  ["<task>", "<task>"],
    "consultancy": ["<task>", "<task>"]
  }},
  "aeo_summary": "<2-3 sentences on AI Overview / local search readiness and top priority actions>"
}}

AUDIT DATA:
Domain: {domain}
Organic keywords: {organic_kws:,} (pos #1: {pos_1}, pos #4-10: {pos_4_10})
Est. monthly traffic: {etv:,}
Pages crawled: {pages_crawled}
Broken pages: {broken_pages}
Missing meta descriptions: {missing_desc}
Lighthouse performance: {perf_score}
Backlinks: {backlinks:,} from {ref_domains:,} referring domains
Top competitor: {top_comp} (est. traffic: {top_comp_etv:,})
Top ranking keyword: {top_kw}
Google Business Profile found: {gbp_found}
GBP rating: {gbp_rating} ({gbp_reviews} reviews)
FAQPage schema present: {has_faq}
Appearing in local pack: {in_local_pack}
AEO readiness score: {aeo_score}/100

BUSINESS CONTEXT:
{business_context or "This is a business website seeking to improve organic search visibility. Local search and Google Maps visibility may be important for bookings and leads. E-E-A-T signals are valuable for building authority."}

Provide 5 prioritised opportunities with realistic impact and effort ratings.
The developer time estimate should be for a competent freelance developer working alone.
Workstream split: developer (technical/code), va_content (content/admin), consultancy (strategy/outreach).
Return ONLY the JSON.\
"""


@observe(name="executive-summary-llm")
def generate(
    data:             dict,
    aeo:              Optional[dict] = None,
    cost_tracker                   = None,
    business_context: Optional[str] = None,
) -> dict:
    """
    Generate an LLM-powered executive summary using Claude Haiku.

    Returns a structured dict with state_summary, opportunities,
    dev_time_estimate, workstreams, and aeo_summary.
    Falls back to a static summary if the LLM call fails.
    """
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage
        from langfuse.langchain import CallbackHandler

        llm = ChatAnthropic(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            temperature=0.2,
        )
        handler  = CallbackHandler()
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=_build_prompt(data, aeo, business_context)),
        ]

        resp    = llm.invoke(messages, config={"callbacks": [handler]})
        content = resp.content.strip()

        # Track LLM cost
        usage = getattr(resp, "usage_metadata", None)
        if cost_tracker and usage:
            cost_tracker.track_llm(
                input_tokens  = getattr(usage, "input_tokens",  0),
                output_tokens = getattr(usage, "output_tokens", 0),
                model         = "claude-sonnet-4-6",
            )

        # Strip accidental markdown fencing
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$",           "", content)

        summary           = json.loads(content)
        summary["_source"] = "llm"
        return summary

    except Exception as exc:
        print(f"   ⚠  Executive summary LLM call failed: {exc}")
        return _fallback_summary(data, aeo, business_context)


def _fallback_summary(data: dict, aeo: Optional[dict] = None, business_context: Optional[str] = None) -> dict:
    """Static fallback summary when LLM is unavailable."""
    domain  = data.get("domain", "unknown")
    ov_result = first_result(data.get("overview", {})) or {}
    ov_items  = safe_get(ov_result, "items", default=[]) or []
    ov        = ov_items[0] if ov_items else {}
    bl        = first_result(data.get("backlinks", {})) or {}
    pm        = safe_get(data.get("onpage_summary", {}),
                         "tasks", 0, "result", 0, "page_metrics") or {}
    if not isinstance(pm, dict):
        pm = {}
    checks    = safe_get(pm, "checks", default={}) or {}
    if not isinstance(checks, dict):
        checks = {}

    def _i(v):
        try: return int(v or 0)
        except: return 0

    organic  = _i(safe_get(ov, "metrics", "organic", "count"))
    etv      = _i(safe_get(ov, "metrics", "organic", "etv"))
    rd       = _i(safe_get(bl, "referring_domains"))
    broken   = _i(checks.get("is_broken", 0) or pm.get("broken_links", 0))
    missing  = _i(checks.get("no_description", 0))
    gbp      = safe_get(aeo, "local", "gbp_found", default=False) if aeo else False
    aeo_sc   = safe_get(aeo, "ai_overview", "readiness_score", default=0) if aeo else 0

    return {
        "_source": "fallback",
        "state_summary": (
            f"{domain} currently ranks for approximately {organic:,} organic keywords "
            f"with an estimated {etv:,} monthly visits. "
            f"The site has {rd} referring domains and {broken} broken pages requiring attention."
        ),
        "opportunities": [
            {"rank": 1, "title": "Fix technical errors",
             "description": f"Repair {broken} broken pages and add meta descriptions to {missing} pages",
             "expected_impact": "high", "effort": "low"},
            {"rank": 2, "title": "Google Business Profile",
             "description": "Set up/optimise GBP to appear in local pack for therapy searches",
             "expected_impact": "high", "effort": "low"},
            {"rank": 3, "title": "Add schema markup",
             "description": "Implement LocalBusiness, FAQPage, and Person JSON-LD schema",
             "expected_impact": "high", "effort": "low"},
            {"rank": 4, "title": "Improve page speed",
             "description": "Optimise Lighthouse performance score to above 80",
             "expected_impact": "medium", "effort": "medium"},
            {"rank": 5, "title": "Content gap optimisation",
             "description": "Expand content for keywords ranking positions 4–20",
             "expected_impact": "medium", "effort": "medium"},
        ],
        "dev_time_estimate": {
            "total_hours": 45,
            "notes": "Estimate for a competent freelance developer working solo",
            "breakdown": [
                {"task": "Technical SEO fixes (broken links, redirects)", "hours": 6,  "workstream": "developer"},
                {"task": "Schema markup implementation",                  "hours": 8,  "workstream": "developer"},
                {"task": "Page speed optimisation",                       "hours": 12, "workstream": "developer"},
                {"task": "GBP setup and optimisation",                    "hours": 3,  "workstream": "va"},
                {"task": "Meta descriptions and page titles",             "hours": 6,  "workstream": "va"},
                {"task": "FAQ page content creation",                     "hours": 6,  "workstream": "va"},
                {"task": "Local citation building",                       "hours": 4,  "workstream": "consultancy"},
            ],
        },
        "workstreams": {
            "developer":   ["Schema markup", "Page speed", "Technical fixes", "Broken link repair"],
            "va_content":  ["GBP management", "Meta descriptions", "FAQ content", "Blog posts"],
            "consultancy": ["Link building strategy", "Review acquisition", "Local citations", "AI Overview strategy"],
        },
        "aeo_summary": (
            f"With an AEO readiness score of {aeo_sc}/100, the site has significant room to improve "
            "its visibility in Google AI Overviews and local search. "
            "Immediate priorities: claim the Google Business Profile, add FAQPage schema, "
            "and build a detailed About page to establish E-E-A-T credibility."
        ),
    }
