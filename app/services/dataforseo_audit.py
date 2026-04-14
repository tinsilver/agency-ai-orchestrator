"""
DataForSEO SEO Audit Service — full-stack, three-tier.

Orchestrates a comprehensive domain SEO audit across three tiers:
  Tier 0 (base):  Domain rank, keywords, competitors, backlinks, on-page, page speed
  Tier 1 (extended): Keyword gap, anchor text, WHOIS, internal links, non-indexable pages
  Tier 2 (advanced): Backlink history, keyword difficulty, search intent, related keywords
  Tier 3 (local):    Google Business Profile, Google Reviews
  Deep (optional):   Per-page SERP content gap analysis (--deep flag)
  AEO/GEO:          Answer engine and generative engine optimisation signals (derived)
  Executive Summary: LLM-generated (Claude Haiku)

Outputs: JSON (full data), Markdown (AI-context summary), PDF (branded client report).

Usage:
    from app.services.dataforseo_audit import DataForSEOAuditService
    service = DataForSEOAuditService()
    result  = await service.run_audit("enricoviola.com", formats=["all"], deep=True)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from langfuse import observe

from app.services.cost_tracker import CostTracker
from app.services.dataforseo_client import (
    DataForSEOClient,
    first_result,
    now_utc,
    safe_get,
)


OutputFormat = Literal["json", "md", "pdf", "all"]

_TOTAL_STEPS = 25  # API steps in collect_data (before deep / AEO / LLM)


def _sanitise_domain(raw: str) -> str:
    raw = raw.strip().lower()
    raw = re.sub(r"^https?://", "", raw)
    raw = re.sub(r"^www\.", "", raw)
    return raw.rstrip("/")


def _log(response: dict, label: str):
    try:
        task = response["tasks"][0]
        code = task.get("status_code")
        msg  = task.get("status_message", "")
        sym  = "✓" if code in (20000, 20100) else "⚠"
        print(f"   {sym}  {label}: {code} {msg}")
    except Exception:
        pass


def _derive_onpage_issues(onpage_summary: dict) -> dict:
    """
    Extract on-page issues from the onpage_summary page_metrics.checks dict.
    Returns data in a structure compatible with the report renderers.
    """
    checks = safe_get(
        onpage_summary, "tasks", 0, "result", 0, "page_metrics", "checks",
        default={}
    )
    if not isinstance(checks, dict):
        return {}

    # Map check keys to human-readable issue descriptions
    _ISSUE_MAP = {
        "no_description":       "Pages missing meta description",
        "is_broken":            "Broken pages (4xx/5xx)",
        "is_4xx_code":          "Pages returning 4xx status",
        "is_5xx_code":          "Pages returning 5xx status",
        "broken_links":         "Pages with broken outgoing links",
        "duplicate_title_tag":  "Duplicate title tags",
        "duplicate_meta_tags":  "Pages with duplicate meta tags",
        "no_h1_tag":            "Pages without an H1 heading",
        "no_title":             "Pages without a title tag",
        "no_image_alt":         "Images missing alt attribute",
        "no_image_title":       "Images missing title attribute",
        "low_content_rate":     "Pages with low content rate",
        "no_favicon":           "Missing favicon",
        "is_redirect":          "Redirect pages",
        "https_to_http_links":  "HTTPS pages linking to HTTP",
        "has_render_blocking_resources": "Pages with render-blocking resources",
        "no_encoding_meta_tag": "Missing encoding meta tag",
        "large_page_size":      "Pages exceeding recommended size",
        "title_too_long":       "Title tag too long",
        "title_too_short":      "Title tag too short",
        "irrelevant_description": "Irrelevant meta description",
        "canonical_to_broken":  "Canonical pointing to broken URL",
        "canonical_to_redirect": "Canonical pointing to redirect",
        "has_links_to_redirects": "Pages linking to redirects",
    }

    issues = []
    for key, label in _ISSUE_MAP.items():
        count = checks.get(key, 0)
        if count and count > 0:
            issues.append({
                "issue_type":        key,
                "issue_description": label,
                "pages_count":       count,
            })

    # Sort by count descending
    issues.sort(key=lambda x: x["pages_count"], reverse=True)

    # Return in the standard tasks/result wrapper format
    return {"tasks": [{"status_code": 20000, "result": issues}]}


# ── Mock data (enricoviola.com hypnosis therapist) ─────────────────────────────

def _mock_data(domain: str) -> dict:
    return {
        "domain":       domain,
        "collected_at": now_utc().isoformat(),
        # Tier 0
        "overview": {"tasks": [{"status_code": 20000, "result": [{"items": [{"metrics": {
            "organic": {"count": 312,  "etv": 640,   "pos_1": 8, "pos_2_3": 21, "pos_4_10": 74},
            "paid":    {"count": 0,    "etv": 0},
        }}]}]}]},
        "keywords": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"keyword_data": {"keyword": "hypnotherapy london",
                              "keyword_info": {"search_volume": 1600}},
             "ranked_serp_element": {"serp_item": {"rank_absolute": 8, "etv": 90, "relative_url": "/"}}},
            {"keyword_data": {"keyword": "hypnosis near me",
                              "keyword_info": {"search_volume": 2400}},
             "ranked_serp_element": {"serp_item": {"rank_absolute": 14, "etv": 38, "relative_url": "/"}}},
            {"keyword_data": {"keyword": "clinical hypnotherapy",
                              "keyword_info": {"search_volume": 880}},
             "ranked_serp_element": {"serp_item": {"rank_absolute": 6, "etv": 62, "relative_url": "/services"}}},
            {"keyword_data": {"keyword": "hypnotherapy for anxiety",
                              "keyword_info": {"search_volume": 1300}},
             "ranked_serp_element": {"serp_item": {"rank_absolute": 19, "etv": 22, "relative_url": "/anxiety"}}},
        ]}]}]},
        "historical_rank": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"year": 2025, "month": 1,  "metrics": {"organic": {"count": 280, "etv": 580, "pos_1": 6,  "pos_2_3": 18, "pos_4_10": 65}}},
            {"year": 2025, "month": 4,  "metrics": {"organic": {"count": 295, "etv": 610, "pos_1": 7,  "pos_2_3": 19, "pos_4_10": 70}}},
            {"year": 2025, "month": 7,  "metrics": {"organic": {"count": 305, "etv": 625, "pos_1": 8,  "pos_2_3": 20, "pos_4_10": 72}}},
            {"year": 2025, "month": 10, "metrics": {"organic": {"count": 312, "etv": 640, "pos_1": 8,  "pos_2_3": 21, "pos_4_10": 74}}},
        ]}]}]},
        "keywords_for_site": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"keyword": "hypnotherapy london", "keyword_info": {"search_volume": 1600, "cpc": 2.40, "competition": 0.68}},
            {"keyword": "hypnosis near me",    "keyword_info": {"search_volume": 2400, "cpc": 1.80, "competition": 0.55}},
            {"keyword": "clinical hypnotherapy", "keyword_info": {"search_volume": 880, "cpc": 1.95, "competition": 0.62}},
            {"keyword": "hypnotherapy for anxiety", "keyword_info": {"search_volume": 1300, "cpc": 2.10, "competition": 0.59}},
            {"keyword": "stop smoking hypnotherapy", "keyword_info": {"search_volume": 1900, "cpc": 3.20, "competition": 0.72}},
        ]}]}]},
        "competitors": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"domain": "londonhypnotherapy.co.uk", "domain_rank": 312,
             "avg_position": 5.2, "metrics": {"organic": {"count": 1840, "etv": 8200}}},
            {"domain": "hypnotherapydirectory.org.uk", "domain_rank": 498,
             "avg_position": 3.8, "metrics": {"organic": {"count": 12400, "etv": 41000}}},
            {"domain": "thehypnotherapist.co.uk", "domain_rank": 280,
             "avg_position": 7.1, "metrics": {"organic": {"count": 720, "etv": 3100}}},
        ]}]}]},
        "backlinks": {"tasks": [{"status_code": 20000, "result": [{
            "backlinks": 184, "referring_domains": 38,
            "referring_ips": 29, "broken_backlinks": 3,
        }]}]},
        "referring_domains": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"domain": "hypnotherapydirectory.org.uk", "rank": 498, "backlinks": 1, "dofollow": True,  "first_seen": "2021-03-12"},
            {"domain": "nchhypnotherapy.co.uk",        "rank": 340, "backlinks": 1, "dofollow": True,  "first_seen": "2020-09-04"},
            {"domain": "yell.com",                     "rank": 612, "backlinks": 1, "dofollow": False, "first_seen": "2022-01-18"},
        ]}]}]},
        "onpage_summary": {"tasks": [{"status_code": 20000, "result": [{"crawl_progress": "finished", "page_metrics": {
            "onpage_score": 68.5, "pages_crawled": 24,
            "broken_links": 5, "broken_resources": 3,
            "links_internal": 120, "links_external": 45,
            "duplicate_title": 3, "duplicate_description": 2, "duplicate_content": 1,
            "non_indexable": 2, "redirect_loop": 0,
            "checks": {
                "no_description": 8, "is_broken": 2, "broken_links": 5,
                "duplicate_title_tag": 3, "no_h1_tag": 2, "no_image_alt": 12,
                "low_content_rate": 6, "is_redirect": 1, "no_favicon": 0,
                "has_render_blocking_resources": 14, "https_to_http_links": 0,
                "no_encoding_meta_tag": 1, "is_4xx_code": 2, "is_5xx_code": 0,
                "title_too_long": 1, "title_too_short": 0,
            },
        }}]}]},
        "onpage_issues": {"tasks": [{"status_code": 20000, "result": [
            {"issue_type": "has_render_blocking_resources", "issue_description": "Pages with render-blocking resources", "pages_count": 14},
            {"issue_type": "no_image_alt",   "issue_description": "Images missing alt attribute",    "pages_count": 12},
            {"issue_type": "no_description", "issue_description": "Pages missing meta description",  "pages_count": 8},
            {"issue_type": "low_content_rate","issue_description": "Pages with low content rate",    "pages_count": 6},
            {"issue_type": "broken_links",   "issue_description": "Pages with broken outgoing links","pages_count": 5},
            {"issue_type": "duplicate_title_tag", "issue_description": "Duplicate title tags",       "pages_count": 3},
            {"issue_type": "is_broken",      "issue_description": "Broken pages (4xx/5xx)",          "pages_count": 2},
            {"issue_type": "is_4xx_code",    "issue_description": "Pages returning 4xx status",      "pages_count": 2},
            {"issue_type": "no_h1_tag",      "issue_description": "Pages without an H1 heading",     "pages_count": 2},
            {"issue_type": "no_encoding_meta_tag", "issue_description": "Missing charset encoding meta tag", "pages_count": 1},
            {"issue_type": "title_too_long", "issue_description": "Title tag too long (>60 chars)",  "pages_count": 1},
        ]}]},
        "onpage_pages": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"url": f"https://{domain}/",
             "onpage_score": 72.0, "resource_errors_count": 1,
             "meta": {"title": "Enrico Viola Hypnotherapy", "description": None,
                      "content": {"plain_text_word_count": 650}},
             "checks": {"has_micromarkup": False, "no_description": True, "no_h1_tag": False,
                        "no_image_alt": False, "has_render_blocking_resources": True, "low_content_rate": False}},
            {"url": f"https://{domain}/services",
             "onpage_score": 81.0, "resource_errors_count": 0,
             "meta": {"title": "Hypnotherapy Services", "description": "Hypnotherapy services",
                      "content": {"plain_text_word_count": 420}},
             "checks": {"has_micromarkup": False, "no_description": False, "no_h1_tag": False,
                        "no_image_alt": True, "has_render_blocking_resources": True, "low_content_rate": True}},
            {"url": f"https://{domain}/about",
             "onpage_score": 88.5, "resource_errors_count": 0,
             "meta": {"title": "About Enrico", "description": "About the practice",
                      "content": {"plain_text_word_count": 890}},
             "checks": {"has_micromarkup": False, "no_description": False, "no_h1_tag": False,
                        "no_image_alt": False, "has_render_blocking_resources": True, "low_content_rate": False}},
            {"url": f"https://{domain}/contact",
             "onpage_score": 65.0, "resource_errors_count": 0,
             "meta": {"title": "Contact Us", "description": None,
                      "content": {"plain_text_word_count": 180}},
             "checks": {"has_micromarkup": False, "no_description": True, "no_h1_tag": False,
                        "no_image_alt": False, "has_render_blocking_resources": False, "low_content_rate": True}},
            {"url": f"https://{domain}/anxiety",
             "onpage_score": 58.0, "resource_errors_count": 2,
             "meta": {"title": "Hypnotherapy for Anxiety", "description": None,
                      "content": {"plain_text_word_count": 310}},
             "checks": {"has_micromarkup": False, "no_description": True, "no_h1_tag": True,
                        "no_image_alt": True, "has_render_blocking_resources": True, "low_content_rate": False}},
        ]}]}]},
        "page_speed": {"tasks": [{"status_code": 20000, "result": [{"items": [{
            "url": f"https://{domain}/",
            "onpage_score": 72.5,
            "page_timing": {
                "time_to_interactive": 2800,
                "dom_complete":        3100,
                "largest_contentful_paint": 2200,
                "first_input_delay":   80,
                "connection_time":     42,
                "waiting_time":        580,
                "download_time":       15,
                "duration_time":       3100,
            },
        }]}]}]},
        "lighthouse": {"tasks": [{"status_code": 20000, "result": [{"items": [{
            "url": f"https://{domain}/",
            "categories": {
                "performance":    {"id": "performance",    "title": "Performance",    "score": 0.64},
                "accessibility":  {"id": "accessibility",  "title": "Accessibility",  "score": 0.87},
                "best-practices": {"id": "best-practices", "title": "Best Practices", "score": 0.79},
                "seo":            {"id": "seo",            "title": "SEO",            "score": 0.91},
            },
            "audits": {
                "largest-contentful-paint": {"score": 0.65, "displayValue": "2.2 s"},
                "total-blocking-time":      {"score": 0.72, "displayValue": "150 ms"},
                "cumulative-layout-shift":  {"score": 0.90, "displayValue": "0.05"},
                "speed-index":              {"score": 0.70, "displayValue": "3.2 s"},
                "first-contentful-paint":   {"score": 0.75, "displayValue": "1.8 s"},
                "interactive":              {"score": 0.68, "displayValue": "2.8 s"},
            },
        }]}]}]},
        # Tier 1
        "keyword_gap": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"keyword_data": {"keyword": "hypnotherapy for depression", "keyword_info": {"search_volume": 720}},  "first_domain_serp_element": {"rank_absolute": 4},  "second_domain_serp_element": None},
            {"keyword_data": {"keyword": "past life regression london",  "keyword_info": {"search_volume": 480}},  "first_domain_serp_element": {"rank_absolute": 3},  "second_domain_serp_element": None},
            {"keyword_data": {"keyword": "stop smoking hypnosis",        "keyword_info": {"search_volume": 1900}}, "first_domain_serp_element": {"rank_absolute": 6},  "second_domain_serp_element": None},
        ]}]}]},
        "anchor_text": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"anchor": "enrico viola hypnotherapy", "rank": 320, "backlinks": 12, "referring_domains": 8},
            {"anchor": "hypnotherapist london",     "rank": 280, "backlinks": 6,  "referring_domains": 4},
            {"anchor": "click here",                "rank": 100, "backlinks": 4,  "referring_domains": 4},
        ]}]}]},
        "whois": {"tasks": [{"status_code": 20000, "result": [{"items": [{
            "domain": domain, "created_datetime": "2018-04-12 00:00:00 +00:00",
            "expiration_datetime": "2027-04-12 00:00:00 +00:00", "registrar": "GoDaddy",
        }]}]}]},
        "onpage_links": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"url_from": f"https://{domain}/",         "url_to": f"https://{domain}/services", "type": "anchor", "dofollow": True},
            {"url_from": f"https://{domain}/",         "url_to": f"https://{domain}/about",    "type": "anchor", "dofollow": True},
            {"url_from": f"https://{domain}/services", "url_to": f"https://{domain}/contact",  "type": "anchor", "dofollow": True},
        ]}]}]},
        "onpage_non_indexable": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"url": f"https://{domain}/tag/hypnosis", "reason": "noindex meta tag"},
            {"url": f"https://{domain}/page/2",       "reason": "noindex meta tag"},
        ]}]}]},
        "duplicate_tags": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"url": f"https://{domain}/services",  "accumulator": "title", "title": "Hypnotherapy Services"},
            {"url": f"https://{domain}/treatments", "accumulator": "title", "title": "Hypnotherapy Services"},
            {"url": f"https://{domain}/about",     "accumulator": "description", "description": "About the practice"},
            {"url": f"https://{domain}/team",      "accumulator": "description", "description": "About the practice"},
        ]}]}]},
        "duplicate_content": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"url": f"https://{domain}/services", "page_from_url": f"https://{domain}/treatments", "similarity": 0.87},
        ]}]}]},
        "redirect_chains": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"url": f"https://{domain}/old-page", "redirect_url": f"https://{domain}/temp-redirect",
             "is_redirect_chain": True, "chain_size": 3},
        ]}]}]},
        "broken_resources": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"url": f"https://{domain}/images/hero.jpg", "resource_type": "image", "status_code": 404,
             "page_url": f"https://{domain}/"},
            {"url": f"https://{domain}/css/old-style.css", "resource_type": "stylesheet", "status_code": 404,
             "page_url": f"https://{domain}/about"},
        ]}]}]},
        # Tier 2
        "backlinks_history": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"date": "2024-01-01", "backlinks": 120, "referring_domains": 28},
            {"date": "2024-04-01", "backlinks": 148, "referring_domains": 32},
            {"date": "2024-07-01", "backlinks": 162, "referring_domains": 35},
            {"date": "2024-10-01", "backlinks": 175, "referring_domains": 37},
            {"date": "2025-01-01", "backlinks": 184, "referring_domains": 38},
        ]}]}]},
        "keyword_difficulty": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"keyword": "hypnotherapy london",     "keyword_difficulty": 68},
            {"keyword": "hypnosis near me",        "keyword_difficulty": 52},
            {"keyword": "clinical hypnotherapy",   "keyword_difficulty": 61},
            {"keyword": "hypnotherapy for anxiety","keyword_difficulty": 57},
        ]}]}]},
        "search_intent": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"keyword": "hypnotherapy london",      "search_intent": "commercial"},
            {"keyword": "hypnosis near me",         "search_intent": "commercial"},
            {"keyword": "clinical hypnotherapy",    "search_intent": "informational"},
            {"keyword": "hypnotherapy for anxiety", "search_intent": "commercial"},
        ]}]}]},
        "related_keywords": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"keyword": "cognitive hypnotherapy",    "keyword_data": {"keyword_info": {"search_volume": 320}}},
            {"keyword": "nlp hypnotherapy",          "keyword_data": {"keyword_info": {"search_volume": 260}}},
            {"keyword": "solution focused hypnotherapy", "keyword_data": {"keyword_info": {"search_volume": 590}}},
        ]}]}]},
        "technologies": {"tasks": [{"status_code": 20000, "result": [{"items": [{
            "technologies": [
                {"name": "WordPress", "category": "CMS"},
                {"name": "Google Analytics", "category": "Analytics"},
                {"name": "Cloudflare", "category": "CDN"},
                {"name": "Yoast SEO", "category": "SEO"},
                {"name": "WooCommerce", "category": "Ecommerce"},
                {"name": "jQuery", "category": "JavaScript libraries"},
                {"name": "PHP", "category": "Programming languages"},
                {"name": "MySQL", "category": "Databases"},
            ],
        }]}]}]},
        # Tier 3
        "gbp_search": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {
                "title":   "Enrico Viola Clinical Hypnotherapy",
                "address": "123 Harley Street, London W1G 9QD",
                "phone":   "+44 20 7946 0000",
                "category": "Hypnotherapist",
                "rating":  {"value": 4.8, "votes_count": 14},
                "url":     f"https://{domain}",
            }
        ]}]}]},
        "google_reviews": {"tasks": [{"status_code": 20000, "result": [{"items": [
            {"rating": {"value": 5}, "review_text": "Incredible results after just 3 sessions."},
            {"rating": {"value": 5}, "review_text": "Enrico is warm, professional and highly skilled."},
            {"rating": {"value": 4}, "review_text": "Helped enormously with my sleep anxiety."},
        ]}]}]},
        # Tier 4: AI Visibility (empty in mock unless --ai-visibility)
        "llm_mentions": {},
        "llm_mentions_agg": {},
        "brand_serp": [],
        # Deep (empty in mock — too expensive to fake plausibly)
        "gap_analysis": [],
        # AEO/GEO (populated by aeo_geo_analysis.analyse())
        "aeo_geo": {},
        # Executive summary (populated by executive_summary.generate())
        "executive_summary": {},
        # Cost
        "cost": {
            "api_calls_total": 0,
            "api_cost_usd":    0.0,
            "llm_cost_usd":    0.0,
            "total_cost_usd":  0.0,
        },
    }


# ── Markdown generator ─────────────────────────────────────────────────────────

def _to_markdown(data: dict, agency: str) -> str:
    domain     = data.get("domain", "unknown")
    ts         = data.get("collected_at", now_utc().isoformat())
    # domain_rank_overview: metrics are at result[0].items[0]
    ov_result  = first_result(data.get("overview", {})) or {}
    ov_items   = safe_get(ov_result, "items", default=[]) or []
    ov         = ov_items[0] if ov_items else {}
    bl         = first_result(data.get("backlinks", {})) or {}
    ps_result  = first_result(data.get("page_speed", {})) or {}
    ps_items   = safe_get(ps_result, "items", default=[]) or []
    ps_item    = ps_items[0] if ps_items else {}
    timing     = safe_get(ps_item, "page_timing", default={}) or {}
    pm         = safe_get(first_result(data.get("onpage_summary", {})), "page_metrics") or {}
    checks     = safe_get(pm, "checks", default={}) or {}
    issues     = safe_get(data.get("onpage_issues", {}), "tasks", 0, "result", default=[])
    kw_items   = safe_get(data.get("keywords",     {}), "tasks", 0, "result", 0, "items", default=[])
    comp_items = safe_get(data.get("competitors",  {}), "tasks", 0, "result", 0, "items", default=[])
    aeo        = data.get("aeo_geo", {})
    exe        = data.get("executive_summary", {})
    cost       = data.get("cost", {})

    def _s(v):
        if v in (None, "N/A"): return "N/A"
        try:
            f = float(v)
            return str(int(f * 100)) if f <= 1.0 else str(int(f))
        except (TypeError, ValueError): return str(v)

    lines = [
        f"# SEO Audit Report: {domain}",
        f"**Agency:** {agency}  |  **Date:** {ts[:10]}  |  **Source:** DataForSEO API v3",
        "",
        "---",
        "",
    ]

    # Executive summary (LLM)
    if exe.get("state_summary"):
        lines += [
            "## Executive Summary",
            "",
            exe["state_summary"],
            "",
        ]
        if exe.get("aeo_summary"):
            lines += [f"**AI/AEO:** {exe['aeo_summary']}", ""]

    # Domain overview
    lines += [
        "## 1. Domain Overview",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Organic Keywords | {safe_get(ov, 'metrics', 'organic', 'count')} |",
        f"| Est. Monthly Traffic (ETV) | {safe_get(ov, 'metrics', 'organic', 'etv')} |",
        f"| Ranking #1 Keywords | {safe_get(ov, 'metrics', 'organic', 'pos_1')} |",
        f"| Ranking #4-10 Keywords | {safe_get(ov, 'metrics', 'organic', 'pos_4_10')} |",
        f"| Total Backlinks | {safe_get(bl, 'backlinks')} |",
        f"| Referring Domains | {safe_get(bl, 'referring_domains')} |",
        "",
        "",
    ]

    # Visibility trend
    hr_items = safe_get(data.get("historical_rank", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(hr_items, list) and hr_items:
        lines += [
            "### Visibility Trend",
            "",
            "| Period | Keywords | Est. Traffic | #1 Rankings |",
            "|--------|----------|-------------|-------------|",
        ]
        for h in hr_items:
            period = f"{safe_get(h, 'year', default='')}-{str(safe_get(h, 'month', default='')).zfill(2)}"
            kw_count = safe_get(h, "metrics", "organic", "count", default="—")
            etv_val = safe_get(h, "metrics", "organic", "etv", default="—")
            pos1 = safe_get(h, "metrics", "organic", "pos_1", default="—")
            lines.append(f"| {period} | {kw_count} | {etv_val} | {pos1} |")
        lines.append("")

    # Technology stack
    tech_items = safe_get(data.get("technologies", {}), "tasks", 0, "result", 0, "items", default=[])
    tech_item = tech_items[0] if isinstance(tech_items, list) and tech_items else {}
    techs = safe_get(tech_item, "technologies", default=[]) or []
    if isinstance(techs, list) and techs:
        lines += [
            "### Technology Stack",
            "",
            "| Category | Technologies |",
            "|----------|-------------|",
        ]
        by_cat: dict = {}
        for t in techs:
            cat = safe_get(t, "category", default="Other")
            name = safe_get(t, "name", default="Unknown")
            by_cat.setdefault(str(cat), []).append(str(name))
        for cat, names in sorted(by_cat.items()):
            lines.append(f"| {cat} | {', '.join(names)} |")
        lines.append("")

    lines += [
        "## 2. Page Speed",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| OnPage Score | {_s(safe_get(ps_item, 'onpage_score'))} / 100 |",
        f"| Time to Interactive | {safe_get(timing, 'time_to_interactive', default='N/A')} ms |",
        f"| DOM Complete | {safe_get(timing, 'dom_complete', default='N/A')} ms |",
        f"| Largest Contentful Paint | {safe_get(timing, 'largest_contentful_paint', default='N/A')} ms |",
        f"| Server Wait (TTFB) | {safe_get(timing, 'waiting_time', default='N/A')} ms |",
        "",
        "## 3. On-Page Health",
        "",
        "| Check | Count |",
        "|-------|-------|",
        f"| OnPage Score | {safe_get(pm, 'onpage_score', default='N/A')} |",
        f"| Broken Links | {safe_get(pm, 'broken_links', default=checks.get('broken_links', 'N/A'))} |",
        f"| Broken Pages | {checks.get('is_broken', 'N/A')} |",
        f"| Duplicate Titles | {checks.get('duplicate_title_tag', safe_get(pm, 'duplicate_title', default='N/A'))} |",
        f"| Missing Meta Description | {checks.get('no_description', 'N/A')} |",
        f"| No Image Alt | {checks.get('no_image_alt', 'N/A')} |",
        f"| Low Content Rate | {checks.get('low_content_rate', 'N/A')} |",
        f"| Internal Links | {safe_get(pm, 'links_internal', default='N/A')} |",
        f"| External Links | {safe_get(pm, 'links_external', default='N/A')} |",
        "",
    ]

    if isinstance(issues, list) and issues:
        lines += ["### Issues", ""]
        lines += ["| Issue | Pages |", "|-------|-------|"]
        for i in issues[:10]:
            lines.append(f"| {safe_get(i, 'issue_description')} | {safe_get(i, 'pages_count')} |")
        lines.append("")

    # Duplicate tags
    dt_items = safe_get(data.get("duplicate_tags", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(dt_items, list) and dt_items:
        lines += ["### Duplicate Title / Meta Tags", ""]
        lines += ["| URL | Tag Type | Value |", "|-----|----------|-------|"]
        for d in dt_items[:10]:
            url = safe_get(d, "url", default="—")
            tag_type = safe_get(d, "accumulator", default="—")
            tag_val = safe_get(d, "title", default=safe_get(d, "description", default="—"))
            lines.append(f"| {url} | {tag_type} | {tag_val} |")
        lines.append("")

    # Duplicate content
    dc_items = safe_get(data.get("duplicate_content", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(dc_items, list) and dc_items:
        lines += ["### Duplicate Content", ""]
        lines += ["| Page A | Page B | Similarity |", "|--------|--------|------------|"]
        for d in dc_items[:10]:
            url1 = safe_get(d, "url", default="—")
            url2 = safe_get(d, "page_from_url", default="—")
            sim = safe_get(d, "similarity", default="—")
            try:
                sim_str = f"{float(sim) * 100:.0f}%"
            except (TypeError, ValueError):
                sim_str = str(sim)
            lines.append(f"| {url1} | {url2} | {sim_str} |")
        lines.append("")

    # Redirect chains
    rc_items = safe_get(data.get("redirect_chains", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(rc_items, list) and rc_items:
        lines += ["### Redirect Chains", ""]
        lines += ["| Origin | Target | Hops |", "|--------|--------|------|"]
        for r in rc_items[:10]:
            url_from = safe_get(r, "url", default="—")
            url_to = safe_get(r, "redirect_url", default="—")
            hops = safe_get(r, "chain_size", default="—")
            lines.append(f"| {url_from} | {url_to} | {hops} |")
        lines.append("")

    # Broken resources
    br_items = safe_get(data.get("broken_resources", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(br_items, list) and br_items:
        lines += ["### Broken Resources", ""]
        lines += ["| Resource URL | Type | Status | Found On |", "|-------------|------|--------|----------|"]
        for b in br_items[:10]:
            res_url = safe_get(b, "url", default="—")
            res_type = safe_get(b, "resource_type", default="—")
            status = safe_get(b, "status_code", default="—")
            page = safe_get(b, "page_url", default="—")
            lines.append(f"| {res_url} | {res_type} | {status} | {page} |")
        lines.append("")

    # Keywords
    lines += ["## 4. Top Keywords", ""]
    if isinstance(kw_items, list) and kw_items:
        lines += ["| Keyword | Pos | Volume | Traffic |", "|---------|-----|--------|---------|"]
        for item in kw_items[:15]:
            kw  = safe_get(item, "keyword_data", "keyword", default="—")
            pos = safe_get(item, "ranked_serp_element", "serp_item", "rank_absolute", default="—")
            vol = safe_get(item, "keyword_data", "keyword_info", "search_volume", default="—")
            etv = safe_get(item, "ranked_serp_element", "serp_item", "etv", default="—")
            lines.append(f"| {kw} | {pos} | {vol} | {etv} |")
        lines.append("")

    # AEO/GEO
    if aeo:
        aeo_score = safe_get(aeo, "ai_overview", "readiness_score", default="N/A")
        aeo_label = safe_get(aeo, "ai_overview", "score_label",     default="")
        gbp_found = safe_get(aeo, "local", "gbp_found", default=False)
        has_faq   = safe_get(aeo, "schema", "has_faq_page", default=False)
        lines += [
            "## 5. AEO / AI Overview Readiness",
            "",
            f"**Readiness Score:** {aeo_score}/100 ({aeo_label})",
            "",
            "| Signal | Status |",
            "|--------|--------|",
            f"| Google Business Profile | {'✓ Found' if gbp_found else '✗ Not found'} |",
            f"| FAQPage schema | {'✓ Present' if has_faq else '✗ Missing'} |",
            f"| LocalBusiness schema | {'✓ Present' if safe_get(aeo, 'schema', 'has_local_business') else '✗ Missing'} |",
            f"| About/Practitioner page | {'✓ Present' if safe_get(aeo, 'eeat', 'has_about_page') else '✗ Missing'} |",
            f"| In local pack | {'✓ Yes' if safe_get(aeo, 'local', 'in_local_pack') else '✗ No'} |",
            "",
        ]

    # Opportunities (LLM)
    if exe.get("opportunities"):
        lines += ["## 6. Top Opportunities", ""]
        lines += ["| # | Opportunity | Impact | Effort |", "|---|-------------|--------|--------|"]
        for opp in exe["opportunities"][:5]:
            lines.append(
                f"| {opp.get('rank', '')} "
                f"| {opp.get('title', '')} "
                f"| {opp.get('expected_impact', '')} "
                f"| {opp.get('effort', '')} |"
            )
        lines.append("")

    # Cost summary
    if cost:
        lines += [
            "## 7. Audit Cost Summary",
            "",
            f"| Item | Value |",
            f"|------|-------|",
            f"| API calls | {cost.get('api_calls_total', 0)} |",
            f"| API cost (est.) | ${cost.get('api_cost_usd', 0):.4f} |",
            f"| LLM tokens (in/out) | {cost.get('llm_input_tokens', 0):,} / {cost.get('llm_output_tokens', 0):,} |",
            f"| LLM cost (est.) | ${cost.get('llm_cost_usd', 0):.4f} |",
            f"| **Total cost (est.)** | **${cost.get('total_cost_usd', 0):.4f}** |",
            "",
        ]

    lines += [
        "---",
        f"*Generated by {agency} using DataForSEO API v3*",
    ]

    return "\n".join(lines)


# ── Main service ───────────────────────────────────────────────────────────────

class DataForSEOAuditService:
    """
    Full-stack three-tier SEO audit service powered by DataForSEO API v3.

    Tier 0 (base, always):
      Domain rank, keywords, competitors, backlinks, on-page crawl, page speed
    Tier 1 (extended, always):
      Keyword gap, anchor text, WHOIS, internal links, non-indexable pages
    Tier 2 (advanced, always):
      Backlink history, keyword difficulty, search intent, related keywords
    Tier 3 (local, always):
      Google Business Profile, Google Reviews
    Deep (--deep flag):
      Per-page SERP content gap analysis
    AEO/GEO (always, derived — no extra API calls):
      Schema coverage, E-E-A-T, local signals, AI Overview readiness score
    Executive Summary (always):
      LLM-generated via Claude Haiku (falls back to static if unavailable)
    """

    def __init__(
        self,
        api_key: str | None = None,
        sandbox: bool = False,
        use_standard: bool = False,
        business_context: str | None = None,
        ai_visibility: bool = False,
    ):
        self.client = DataForSEOClient(api_key, sandbox=sandbox, use_standard=use_standard)
        self.agency = os.environ.get("SEO_AGENCY_NAME", "Theo Ruby SEO Agency")
        self.sandbox = sandbox
        self.business_context = business_context
        self.ai_visibility = ai_visibility

    # ── Data collection ────────────────────────────────────────────────────────

    @observe(name="dataforseo-collect-data")
    def collect_data(
        self,
        domain:         str,
        location_code:  int  = 2826,
        deep:           bool = False,
        ai_visibility:  bool | None = None,
        business_context: str | None = None,
    ) -> dict:
        """
        Run all DataForSEO API calls (Tiers 0–3) for a domain,
        then run AEO/GEO analysis and generate an LLM executive summary.

        Args:
            domain:        Bare domain (protocol/www stripped automatically).
            location_code: DataForSEO location code (2840=US, 2826=UK, etc.).
            deep:          If True, also run per-page SERP gap analysis.

        Returns:
            dict with all raw API responses plus derived analysis.
        """
        # Resolve flags from method args or instance defaults
        if ai_visibility is None:
            ai_visibility = self.ai_visibility
        if business_context is None:
            business_context = self.business_context

        domain  = _sanitise_domain(domain)
        data: dict = {"domain": domain, "collected_at": now_utc().isoformat()}
        tracker    = CostTracker()
        task_id    = None  # OnPage task id reused across tier 0 and tier 1

        step = 0

        def s():
            nonlocal step
            step += 1
            return f"[{step}/{_TOTAL_STEPS}]"

        # ── TIER 0: Base audit ─────────────────────────────────────────────────

        if self.sandbox:
            mode_label = "SANDBOX"
        elif self.client.use_standard:
            mode_label = "STANDARD (task-based, cheaper)"
        else:
            mode_label = "LIVE"
        print(f"\n{'='*50}")
        print(f"  DataForSEO full audit: {domain}")
        print(f"  Mode: {mode_label}")
        if ai_visibility:
            print(f"  AI Visibility: ON")
        if business_context:
            print(f"  Business: {business_context[:60]}")
        print(f"{'='*50}\n")

        print(f"{s()} Domain rank overview…")
        try:
            data["overview"] = self.client.domain_rank_overview(domain, location_code)
            tracker.track_call("domain_rank_overview")
            _log(data["overview"], "Domain Rank Overview")
        except Exception as e:
            print(f"   ✗  {e}"); data["overview"] = {}

        print(f"{s()} Top organic keywords…")
        try:
            data["keywords"] = self.client.ranked_keywords(domain, location_code, limit=50)
            tracker.track_call("ranked_keywords")
            _log(data["keywords"], "Ranked Keywords")
        except Exception as e:
            print(f"   ✗  {e}"); data["keywords"] = {}

        print(f"{s()} Historical rank overview…")
        try:
            data["historical_rank"] = self.client.historical_rank_overview(domain, location_code)
            tracker.track_call("historical_rank_overview")
            _log(data["historical_rank"], "Historical Rank")
        except Exception as e:
            print(f"   ✗  {e}"); data["historical_rank"] = {}

        print(f"{s()} Keywords for site…")
        try:
            data["keywords_for_site"] = self.client.keywords_for_site(domain, location_code)
            tracker.track_call("keywords_for_site")
            _log(data["keywords_for_site"], "Keywords for Site")
        except Exception as e:
            print(f"   ✗  {e}"); data["keywords_for_site"] = {}

        print(f"{s()} Competitor analysis…")
        try:
            data["competitors"] = self.client.competitors_domain(domain, location_code)
            tracker.track_call("competitors_domain")
            _log(data["competitors"], "Competitors")
        except Exception as e:
            print(f"   ✗  {e}"); data["competitors"] = {}

        print(f"{s()} Backlink profile…")
        try:
            data["backlinks"]         = self.client.backlinks_summary(domain)
            data["referring_domains"] = self.client.referring_domains(domain)
            tracker.track_call("backlinks_summary")
            tracker.track_call("referring_domains")
            _log(data["backlinks"],         "Backlink Summary")
            _log(data["referring_domains"], "Referring Domains")
        except Exception as e:
            print(f"   ✗  {e}")
            data.setdefault("backlinks", {}); data.setdefault("referring_domains", {})

        print(f"{s()} On-Page crawl (task-based, polling)…")
        try:
            task_id = self.client.onpage_task_post(domain)
            tracker.track_call("onpage_task_post")
            if task_id:
                print(f"   ✓  Task: {task_id}")
                data["onpage_summary"] = self.client.onpage_wait_and_fetch(task_id)
                tracker.track_call("onpage_summary")
                _log(data["onpage_summary"], "OnPage Summary")
            else:
                data["onpage_summary"] = {}
        except Exception as e:
            print(f"   ✗  OnPage task: {e}")
            data.setdefault("onpage_summary", {})

        # Derive issues from onpage_summary.page_metrics.checks (always available)
        data["onpage_issues"] = _derive_onpage_issues(data.get("onpage_summary", {}))

        if task_id:
            try:
                data["onpage_pages"] = self.client.onpage_pages(task_id)
                tracker.track_call("onpage_pages")
            except Exception as e:
                print(f"   ✗  OnPage pages: {e}")
                data["onpage_pages"] = {}
        else:
            data["onpage_pages"] = {}

        print(f"{s()} Page speed (Instant Pages)…")
        try:
            data["page_speed"] = self.client.page_speed(f"https://{domain}")
            tracker.track_call("page_speed")
            _log(data["page_speed"], "Page Speed")
        except Exception as e:
            print(f"   ✗  {e}"); data["page_speed"] = {}

        print(f"{s()} Lighthouse audit (Performance / Accessibility / Best Practices / SEO)…")
        try:
            data["lighthouse"] = self.client.onpage_lighthouse(f"https://{domain}")
            tracker.track_call("onpage_lighthouse")
            _log(data["lighthouse"], "Lighthouse")
        except Exception as e:
            print(f"   ✗  {e}"); data["lighthouse"] = {}

        # ── TIER 1: Extended ───────────────────────────────────────────────────

        print(f"\n── Tier 1: Extended ──")
        print(f"{s()} Keyword gap analysis…")
        try:
            comp_items = safe_get(data.get("competitors", {}), "tasks", 0, "result", 0, "items", default=[])
            top_comps  = [safe_get(c, "domain") for c in (comp_items[:2] if comp_items else [])]
            targets    = [domain] + [c for c in top_comps if c and c != "N/A"]
            if len(targets) >= 2:
                data["keyword_gap"] = self.client.keyword_gap(targets, location_code)
                tracker.track_call("keyword_gap")
                _log(data["keyword_gap"], "Keyword Gap")
            else:
                data["keyword_gap"] = {}
        except Exception as e:
            print(f"   ✗  {e}"); data["keyword_gap"] = {}

        print(f"{s()} Anchor text distribution…")
        try:
            data["anchor_text"] = self.client.anchor_text(domain)
            tracker.track_call("anchor_text")
            _log(data["anchor_text"], "Anchor Text")
        except Exception as e:
            print(f"   ✗  {e}"); data["anchor_text"] = {}

        print(f"{s()} WHOIS data…")
        try:
            data["whois"] = self.client.domain_whois(domain)
            tracker.track_call("domain_whois")
            _log(data["whois"], "WHOIS")
        except Exception as e:
            print(f"   ✗  {e}"); data["whois"] = {}

        print(f"{s()} Internal link map…")
        if task_id:
            try:
                data["onpage_links"] = self.client.onpage_links(task_id)
                tracker.track_call("onpage_links")
                _log(data["onpage_links"], "OnPage Links")
            except Exception as e:
                print(f"   ✗  {e}"); data["onpage_links"] = {}
        else:
            data["onpage_links"] = {}
            print("   ⚠  Skipped (no OnPage task)")

        print(f"{s()} Non-indexable pages…")
        if task_id:
            try:
                data["onpage_non_indexable"] = self.client.onpage_non_indexable(task_id)
                tracker.track_call("onpage_non_indexable")
                _log(data["onpage_non_indexable"], "Non-Indexable")
            except Exception as e:
                print(f"   ✗  {e}"); data["onpage_non_indexable"] = {}
        else:
            data["onpage_non_indexable"] = {}

        print(f"{s()} Duplicate tags…")
        if task_id:
            try:
                data["duplicate_tags"] = self.client.onpage_duplicate_tags(task_id)
                tracker.track_call("onpage_duplicate_tags")
                _log(data["duplicate_tags"], "Duplicate Tags")
            except Exception as e:
                print(f"   ✗  {e}"); data["duplicate_tags"] = {}
        else:
            data["duplicate_tags"] = {}

        print(f"{s()} Duplicate content…")
        if task_id:
            try:
                homepage_url = f"https://{domain}"
                data["duplicate_content"] = self.client.onpage_duplicate_content(
                    task_id, url=homepage_url
                )
                tracker.track_call("onpage_duplicate_content")
                _log(data["duplicate_content"], "Duplicate Content")
            except Exception as e:
                print(f"   ✗  {e}"); data["duplicate_content"] = {}
        else:
            data["duplicate_content"] = {}

        print(f"{s()} Redirect chains…")
        if task_id:
            try:
                data["redirect_chains"] = self.client.onpage_redirect_chains(task_id)
                tracker.track_call("onpage_redirect_chains")
                _log(data["redirect_chains"], "Redirect Chains")
            except Exception as e:
                print(f"   ✗  {e}"); data["redirect_chains"] = {}
        else:
            data["redirect_chains"] = {}

        print(f"{s()} Broken resources…")
        if task_id:
            try:
                data["broken_resources"] = self.client.onpage_resources(task_id, broken_only=True)
                tracker.track_call("onpage_resources")
                _log(data["broken_resources"], "Broken Resources")
            except Exception as e:
                print(f"   ✗  {e}"); data["broken_resources"] = {}
        else:
            data["broken_resources"] = {}

        # ── TIER 2: Advanced ───────────────────────────────────────────────────

        print(f"\n── Tier 2: Advanced ──")
        print(f"{s()} Backlink history…")
        try:
            data["backlinks_history"] = self.client.backlinks_history(domain)
            tracker.track_call("backlinks_history")
            _log(data["backlinks_history"], "Backlink History")
        except Exception as e:
            print(f"   ✗  {e}"); data["backlinks_history"] = {}

        print(f"{s()} Bulk keyword difficulty…")
        try:
            kw_items = safe_get(data.get("keywords", {}), "tasks", 0, "result", 0, "items", default=[])
            top_kws  = [safe_get(i, "keyword_data", "keyword") for i in (kw_items[:20] if kw_items else [])]
            top_kws  = [k for k in top_kws if k and k != "N/A"]
            if top_kws:
                data["keyword_difficulty"] = self.client.bulk_keyword_difficulty(top_kws, location_code)
                tracker.track_call("bulk_keyword_difficulty")
                _log(data["keyword_difficulty"], "Keyword Difficulty")
            else:
                data["keyword_difficulty"] = {}
        except Exception as e:
            print(f"   ✗  {e}"); data["keyword_difficulty"] = {}

        print(f"{s()} Search intent classification…")
        try:
            kw_items = safe_get(data.get("keywords", {}), "tasks", 0, "result", 0, "items", default=[])
            top_kws  = [safe_get(i, "keyword_data", "keyword") for i in (kw_items[:20] if kw_items else [])]
            top_kws  = [k for k in top_kws if k and k != "N/A"]
            if top_kws:
                data["search_intent"] = self.client.search_intent(top_kws, location_code)
                tracker.track_call("search_intent")
                _log(data["search_intent"], "Search Intent")
            else:
                data["search_intent"] = {}
        except Exception as e:
            print(f"   ✗  {e}"); data["search_intent"] = {}

        print(f"{s()} Domain technologies…")
        try:
            data["technologies"] = self.client.domain_technologies(domain)
            tracker.track_call("domain_technologies")
            _log(data["technologies"], "Domain Technologies")
        except Exception as e:
            print(f"   ✗  {e}"); data["technologies"] = {}

        print(f"{s()} Related keywords…")
        try:
            kw_items = safe_get(data.get("keywords", {}), "tasks", 0, "result", 0, "items", default=[])
            top_kw   = safe_get(kw_items, 0, "keyword_data", "keyword") if kw_items else None
            if top_kw and top_kw != "N/A":
                data["related_keywords"] = self.client.related_keywords(top_kw, location_code)
                tracker.track_call("related_keywords")
                _log(data["related_keywords"], "Related Keywords")
            else:
                data["related_keywords"] = {}
        except Exception as e:
            print(f"   ✗  {e}"); data["related_keywords"] = {}

        # ── TIER 3: Local SEO ──────────────────────────────────────────────────

        print(f"\n── Tier 3: Local SEO ──")
        print(f"{s()} Google Business Profile…")
        try:
            data["gbp_search"] = self.client.google_business_info(domain, location_code)
            tracker.track_call("google_business_info")
            _log(data["gbp_search"], "GBP Info")
        except Exception as e:
            print(f"   ✗  {e}"); data["gbp_search"] = {}

        print(f"{s()} Google Reviews…")
        try:
            rev_task_id = self.client.google_reviews_task_post(domain, location_code)
            tracker.track_call("google_reviews_task_post")
            if rev_task_id:
                print(f"   ✓  Reviews task: {rev_task_id}")
                data["google_reviews"] = self.client.google_reviews_wait_and_fetch(rev_task_id)
                tracker.track_call("google_reviews_task_get")
                _log(data["google_reviews"], "Google Reviews")
            else:
                data["google_reviews"] = {}
        except Exception as e:
            print(f"   ✗  {e}"); data["google_reviews"] = {}

        # ── TIER 4: AI Visibility (optional) ────────────────────────────────────

        if ai_visibility:
            print(f"\n── Tier 4: AI Visibility ──")

            # Extract brand keyword (domain name without TLD) + top traffic keywords
            brand_kw = domain.split(".")[0]
            kw_items_t4 = safe_get(data.get("keywords", {}), "tasks", 0, "result", 0, "items", default=[])
            top_traffic_kws = []
            for item in (kw_items_t4[:4] if isinstance(kw_items_t4, list) else []):
                kw = safe_get(item, "keyword_data", "keyword")
                if kw and kw != "N/A":
                    top_traffic_kws.append(kw)

            print(f"   LLM mentions search ({brand_kw})…")
            try:
                data["llm_mentions"] = self.client.llm_mentions_search(brand_kw, location_code)
                tracker.track_call("llm_mentions_search")
                _log(data["llm_mentions"], "LLM Mentions Search")
            except Exception as e:
                print(f"   ✗  {e}"); data["llm_mentions"] = {}

            print(f"   LLM mentions aggregated ({brand_kw})…")
            try:
                data["llm_mentions_agg"] = self.client.llm_mentions_aggregated(brand_kw, location_code)
                tracker.track_call("llm_mentions_aggregated")
                _log(data["llm_mentions_agg"], "LLM Mentions Aggregated")
            except Exception as e:
                print(f"   ✗  {e}"); data["llm_mentions_agg"] = {}

            # Brand SERP for top keywords (3-5 calls)
            serp_keywords = [brand_kw] + top_traffic_kws[:3]
            brand_serp_results = []
            for skw in serp_keywords:
                print(f"   SERP features ({skw})…")
                try:
                    serp_resp = self.client.serp_organic_live(skw, location_code)
                    tracker.track_call("serp_organic_live")
                    _log(serp_resp, f"SERP: {skw}")
                    brand_serp_results.append({"keyword": skw, "serp": serp_resp})
                except Exception as e:
                    print(f"   ✗  {e}")
                    brand_serp_results.append({"keyword": skw, "serp": {}})
            data["brand_serp"] = brand_serp_results
        else:
            data["llm_mentions"] = {}
            data["llm_mentions_agg"] = {}
            data["brand_serp"] = []

        # ── DEEP: Per-page gap analysis (optional) ─────────────────────────────

        if deep:
            print(f"\n── Deep: Per-page gap analysis ──")
            try:
                from app.services.gap_analysis import analyse_gaps
                data["gap_analysis"] = analyse_gaps(
                    client        = self.client,
                    domain        = domain,
                    keywords_data = data.get("keywords", {}),
                    location_code = location_code,
                    cost_tracker  = tracker,
                )
                print(f"   ✓  {len(data['gap_analysis'])} keyword gaps analysed")
            except Exception as e:
                print(f"   ✗  Gap analysis failed: {e}")
                data["gap_analysis"] = []
        else:
            data["gap_analysis"] = []

        # ── AEO/GEO Analysis (derived, no extra API calls) ─────────────────────

        print(f"\n── AEO / GEO Analysis ──")
        try:
            from app.services.aeo_geo_analysis import analyse as aeo_analyse
            data["aeo_geo"] = aeo_analyse(
                data,
                llm_mentions=data.get("llm_mentions"),
                llm_mentions_agg=data.get("llm_mentions_agg"),
                brand_serp=data.get("brand_serp"),
            )
            score = safe_get(data["aeo_geo"], "ai_overview", "readiness_score", default="?")
            label = safe_get(data["aeo_geo"], "ai_overview", "score_label",     default="")
            print(f"   ✓  AEO readiness: {score}/100 ({label})")
        except Exception as e:
            print(f"   ✗  AEO analysis failed: {e}")
            data["aeo_geo"] = {}

        # ── Executive Summary (LLM) ────────────────────────────────────────────

        print(f"\n── Executive Summary (LLM) ──")
        try:
            from app.services.executive_summary import generate as gen_summary
            data["executive_summary"] = gen_summary(
                data             = data,
                aeo              = data.get("aeo_geo"),
                cost_tracker     = tracker,
                business_context = business_context,
            )
            src = data["executive_summary"].get("_source", "?")
            print(f"   ✓  Summary generated ({src})")
        except Exception as e:
            print(f"   ✗  Executive summary failed: {e}")
            data["executive_summary"] = {}

        # ── Cost summary ───────────────────────────────────────────────────────

        data["cost"] = tracker.summary()
        total = data["cost"]["total_cost_usd"]
        print(f"\n── Estimated audit cost: ${total:.4f} ──\n")

        return data

    # ── Output formatters ──────────────────────────────────────────────────────

    def to_json(self, data: dict, indent: int = 2) -> str:
        return json.dumps(data, indent=indent, default=str)

    def to_markdown(self, data: dict) -> str:
        return _to_markdown(data, self.agency)

    def to_pdf(self, data: dict, output_path: str) -> str:
        from app.services.dataforseo_pdf import build_pdf
        return build_pdf(data, output_path, agency=self.agency)

    # ── Primary entry point ────────────────────────────────────────────────────

    @observe(name="dataforseo-audit")
    async def run_audit(
        self,
        domain:           str,
        output_dir:       str | Path             = "reports",
        formats:          list[OutputFormat] | None = None,
        location_code:    int                   = 2826,
        mock:             bool                  = False,
        deep:             bool                  = False,
        ai_visibility:    bool | None           = None,
        business_context: str | None            = None,
    ) -> dict:
        """
        Run a complete three-tier SEO audit and write output files.

        Args:
            domain:        Domain to audit (e.g. 'enricoviola.com').
            output_dir:    Directory to write output files into (created if missing).
            formats:       Output formats: ['json'], ['md'], ['pdf'], or ['all'].
                           Defaults to ['json', 'md'].
            location_code: DataForSEO location code (default 2840 = US).
            mock:          If True, use synthetic data instead of live API calls.
            deep:          If True, also run per-page SERP content gap analysis.

        Returns:
            dict with keys: 'data', and optionally 'json_path', 'md_path', 'pdf_path'.
        """
        formats = formats or ["json", "md"]
        if "all" in formats:
            formats = ["json", "md", "pdf"]

        domain  = _sanitise_domain(domain)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        date_str  = datetime.now(timezone.utc).strftime("%Y%m%d")
        base_name = f"{domain.replace('.', '_')}_{date_str}"

        if mock:
            print(f"\n[MOCK] Generating synthetic audit data for {domain}…")
            data = _mock_data(domain)
            # Run derived analysis on mock data too
            try:
                from app.services.aeo_geo_analysis import analyse as aeo_analyse
                data["aeo_geo"] = aeo_analyse(
                    data,
                    llm_mentions=data.get("llm_mentions"),
                    llm_mentions_agg=data.get("llm_mentions_agg"),
                    brand_serp=data.get("brand_serp"),
                )
            except Exception:
                pass
            try:
                from app.services.executive_summary import generate as gen_summary
                data["executive_summary"] = gen_summary(
                    data=data, aeo=data.get("aeo_geo"),
                    business_context=business_context,
                )
            except Exception:
                pass
        else:
            data = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collect_data(
                    domain, location_code, deep=deep,
                    ai_visibility=ai_visibility,
                    business_context=business_context,
                ),
            )

        result: dict = {"data": data}

        if "json" in formats:
            json_path = out_dir / f"{base_name}.json"
            json_path.write_text(self.to_json(data), encoding="utf-8")
            result["json_path"] = str(json_path)
            print(f"\n✅  JSON → {json_path}")

        if "md" in formats:
            md_path = out_dir / f"{base_name}.md"
            md_path.write_text(self.to_markdown(data), encoding="utf-8")
            result["md_path"] = str(md_path)
            print(f"✅  Markdown → {md_path}")

        if "pdf" in formats:
            pdf_path = out_dir / f"{base_name}.pdf"
            await asyncio.get_event_loop().run_in_executor(
                None, self.to_pdf, data, str(pdf_path)
            )
            result["pdf_path"] = str(pdf_path)
            print(f"✅  PDF → {pdf_path}")

        return result
