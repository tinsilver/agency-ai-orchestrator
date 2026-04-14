"""
AEO (Answer Engine Optimisation) and GEO (Generative Engine Optimisation) analysis.

Analyses a domain's readiness for:
  - Google AI Overviews and featured snippets
  - Local Pack & Google Maps visibility
  - E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness)
  - Schema markup coverage
  - Conversational / voice search optimisation

All signals are derived from data already collected by DataForSEOAuditService
(no additional API calls required).
"""
from __future__ import annotations

import re
from typing import Any

from app.services.dataforseo_client import first_result, safe_get


# ── Internal helpers ───────────────────────────────────────────────────────────

def _has_page_matching(pages: list, pattern: str) -> bool:
    """Return True if any crawled page URL matches the regex pattern."""
    for page in (pages if isinstance(pages, list) else []):
        url = safe_get(page, "url", default="")
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def _average_ratings(review_items: list) -> float | None:
    ratings = []
    for r in review_items:
        raw = safe_get(r, "rating", "value", default=None)
        if raw is None:
            raw = safe_get(r, "rating", default=None)
        if raw is not None:
            try:
                ratings.append(float(raw))
            except (TypeError, ValueError):
                pass
    return round(sum(ratings) / len(ratings), 1) if ratings else None


def _check_local_pack(serp_items: list) -> bool:
    """Return True if a local pack element was present in SERP results."""
    for item in (serp_items if isinstance(serp_items, list) else []):
        if safe_get(item, "type", default="") in ("local_pack", "maps_pack", "google_maps"):
            return True
    return False


def _detect_schema_types(pages: list, issues: list) -> set:
    """
    Infer schema types present on the site from page URLs, checks, and issues.
    DataForSEO OnPage API surfaces `has_micromarkup` in checks when structured
    data is detected. We also infer from URL patterns.
    """
    types: set = set()

    for page in (pages if isinstance(pages, list) else []):
        url    = safe_get(page, "url", default="").lower()
        checks = safe_get(page, "checks", default={}) or {}

        if safe_get(checks, "has_micromarkup"):
            # Micromarkup detected — common on local business sites
            types.add("StructuredData")

        # Infer schema type from URL patterns
        if re.search(r"/(faq|frequently.asked)", url):
            types.add("FAQPage")
        if re.search(r"/(about|meet|team|practitioner|therapist|bio|author)", url):
            types.add("Person")
        if re.search(r"/(blog|article|post|news|insight)", url):
            types.add("Article")
        if re.search(r"/(review|testimonial|feedback)", url):
            types.add("Review")
        if re.search(r"/(service|treatment|therapy|session|appointment)", url):
            types.add("Service")

        # Check title/meta for schema hints
        title = safe_get(page, "meta", "title", default="").lower()
        if any(t in title for t in ("hypnotherapy", "hypnosis", "therapy", "clinic", "practice")):
            types.add("MedicalBusiness")

    # Issues sometimes reference structured data
    for issue in (issues if isinstance(issues, list) else []):
        desc = safe_get(issue, "issue_description", default="").lower()
        if "structured data" in desc or "schema" in desc or "markup" in desc:
            types.add("StructuredData")

    # If we have Service or MedicalBusiness, infer LocalBusiness parent
    if "MedicalBusiness" in types or "Service" in types:
        types.add("LocalBusiness")

    return types


def _score_ai_overview(
    has_faq:        bool,
    has_local_biz:  bool,
    has_person:     bool,
    has_about_page: bool,
    gbp_found:      bool,
    referring_domains: Any,
) -> int:
    """Score AI Overview / answer engine readiness 0–100."""
    score = 0
    if has_faq:        score += 25
    if has_local_biz:  score += 20
    if has_person:     score += 15
    if has_about_page: score += 15
    if gbp_found:      score += 15
    try:
        rd = int(referring_domains or 0)
        if rd >= 50:   score += 10
        elif rd >= 20: score += 5
    except (TypeError, ValueError):
        pass
    return min(score, 100)


def _score_label(score: int) -> str:
    if score >= 70: return "Good"
    if score >= 40: return "Moderate"
    return "Needs Improvement"


def _build_recommendations(
    has_local_biz:  bool,
    has_faq:        bool,
    has_about_page: bool,
    has_contact_pg: bool,
    has_person:     bool,
    has_review:     bool,
    gbp_found:      bool,
    gbp_rating:     Any,
    gbp_reviews:    Any,
    in_local_pack:  bool,
) -> list[dict]:
    recs = []

    if not has_local_biz:
        recs.append({
            "priority":   "High",
            "area":       "Schema",
            "action":     "Add LocalBusiness (or MedicalBusiness) JSON-LD schema to the homepage",
            "benefit":    "Required for local AI Overviews and Google Business Profile knowledge panel eligibility",
            "workstream": "Developer",
        })

    if not has_faq:
        recs.append({
            "priority":   "High",
            "area":       "AEO",
            "action":     "Create a FAQ page and add FAQPage JSON-LD schema with 6–8 common client questions",
            "benefit":    "FAQPage schema frequently surfaces in Google AI Overviews and People Also Ask boxes",
            "workstream": "VA / Content",
        })

    if not has_about_page:
        recs.append({
            "priority":   "High",
            "area":       "E-E-A-T",
            "action":     "Create a detailed About/Practitioner page with credentials, training, and a professional photo",
            "benefit":    "Core E-E-A-T signal for health/wellness YMYL content; Google AI systems weight practitioner pages heavily",
            "workstream": "VA / Content",
        })

    if not has_person:
        recs.append({
            "priority":   "Medium",
            "area":       "Schema",
            "action":     "Add Person schema for the lead practitioner including sameAs links to LinkedIn/professional profiles",
            "benefit":    "Establishes Knowledge Panel eligibility and signals genuine expertise to AI recommendation systems",
            "workstream": "Developer",
        })

    if not gbp_found:
        recs.append({
            "priority":   "High",
            "area":       "Local SEO",
            "action":     "Create or claim and fully optimise a Google Business Profile",
            "benefit":    "Essential for local pack and Google Maps visibility — directly drives in-person appointment bookings",
            "workstream": "Consultancy / VA",
        })
    elif not in_local_pack:
        recs.append({
            "priority":   "High",
            "area":       "Local SEO",
            "action":     "Optimise GBP primary category, add service descriptions, and post weekly updates",
            "benefit":    "Improves local pack ranking; critical for local therapist visibility",
            "workstream": "Consultancy / VA",
        })

    try:
        reviews_n = int(gbp_reviews or 0)
        if reviews_n < 20:
            recs.append({
                "priority":   "High",
                "area":       "Local SEO",
                "action":     f"Systematically request Google reviews from satisfied clients (currently ~{reviews_n})",
                "benefit":    "Review count and rating are direct local pack ranking factors; also influence AI-generated recommendations",
                "workstream": "Consultancy / VA",
            })
    except (TypeError, ValueError):
        pass

    if not has_review:
        recs.append({
            "priority":   "Medium",
            "area":       "Schema",
            "action":     "Implement AggregateRating schema to display star ratings in organic search results",
            "benefit":    "Rich snippet star ratings improve click-through rate from organic listings",
            "workstream": "Developer",
        })

    if not has_contact_pg:
        recs.append({
            "priority":   "Medium",
            "area":       "E-E-A-T",
            "action":     "Ensure the Contact page includes consistent NAP (Name, Address, Phone) in text format",
            "benefit":    "NAP consistency is a local ranking factor and a trust signal for AI systems",
            "workstream": "VA / Content",
        })

    # Universal AEO best practices
    recs.append({
        "priority":   "Medium",
        "area":       "AEO",
        "action":     "Write concise, direct answers to the 10 most common pre-booking questions clients ask",
        "benefit":    "Positions content for People Also Ask features and direct AI Overview citations",
        "workstream": "VA / Content",
    })
    recs.append({
        "priority":   "Low",
        "area":       "GEO",
        "action":     "Register on Bing Places, Apple Maps, Yelp, and therapy directories (Psychology Today, TherapyTribe)",
        "benefit":    "Citation consistency is a key signal for AI systems recommending local health services",
        "workstream": "VA",
    })

    return recs


# ── Public entry point ─────────────────────────────────────────────────────────

def _extract_serp_features(brand_serp: list) -> dict:
    """Extract SERP feature presence from brand SERP results."""
    features = {
        "ai_overview_detected": False,
        "featured_snippet_detected": False,
        "people_also_ask_detected": False,
        "local_pack_detected": False,
        "knowledge_panel_detected": False,
        "keywords_checked": [],
    }
    for entry in (brand_serp if isinstance(brand_serp, list) else []):
        kw = entry.get("keyword", "")
        serp = entry.get("serp", {})
        items = safe_get(serp, "tasks", 0, "result", 0, "items", default=[])
        features["keywords_checked"].append(kw)
        for item in (items if isinstance(items, list) else []):
            item_type = safe_get(item, "type", default="")
            if item_type in ("ai_overview", "ai_mode"):
                features["ai_overview_detected"] = True
            if item_type == "featured_snippet":
                features["featured_snippet_detected"] = True
            if item_type in ("people_also_ask", "related_searches"):
                features["people_also_ask_detected"] = True
            if item_type in ("local_pack", "maps_pack", "google_maps"):
                features["local_pack_detected"] = True
            if item_type in ("knowledge_panel", "knowledge_graph"):
                features["knowledge_panel_detected"] = True
    return features


def _extract_llm_mentions(llm_mentions: dict, llm_mentions_agg: dict) -> dict:
    """Extract real mention counts from LLM mentions data."""
    result = {
        "mentions_found": False,
        "mention_count": 0,
        "platforms": [],
        "aggregated_impressions": 0,
    }
    # Search results
    items = safe_get(llm_mentions, "tasks", 0, "result", 0, "items", default=[])
    if isinstance(items, list) and items:
        result["mentions_found"] = True
        result["mention_count"] = len(items)
        platforms = set()
        for item in items:
            platform = safe_get(item, "platform", default=None)
            if platform:
                platforms.add(str(platform))
        result["platforms"] = sorted(platforms)

    # Aggregated metrics
    agg_items = safe_get(llm_mentions_agg, "tasks", 0, "result", 0, "items", default=[])
    if isinstance(agg_items, list) and agg_items:
        total_impressions = 0
        for agg in agg_items:
            impressions = safe_get(agg, "impressions_count", default=0)
            try:
                total_impressions += int(impressions or 0)
            except (TypeError, ValueError):
                pass
        result["aggregated_impressions"] = total_impressions

    return result


def analyse(
    data: dict,
    llm_mentions: dict | None = None,
    llm_mentions_agg: dict | None = None,
    brand_serp: list | None = None,
) -> dict:
    """
    Derive AEO/GEO readiness signals from already-collected audit data.
    Optionally incorporates real AI visibility data from Tier 4 endpoints.

    Returns a structured dict with schema coverage, E-E-A-T signals,
    local SEO signals, AI overview readiness score, and recommendations.
    """
    pages        = safe_get(data.get("onpage_pages",    {}), "tasks", 0, "result", 0, "items", default=[])
    issues       = safe_get(data.get("onpage_issues",   {}), "tasks", 0, "result", default=[])
    gbp_items    = safe_get(data.get("gbp_search",      {}), "tasks", 0, "result", 0, "items", default=[])
    review_items = safe_get(data.get("google_reviews",  {}), "tasks", 0, "result", 0, "items", default=[])
    serp_items   = safe_get(data.get("serp_organic",    {}), "tasks", 0, "result", 0, "items", default=[])

    # Schema
    schema_types  = _detect_schema_types(
        pages  if isinstance(pages,  list) else [],
        issues if isinstance(issues, list) else [],
    )
    has_local_biz = bool({"LocalBusiness", "MedicalBusiness"} & schema_types)
    has_faq       = "FAQPage" in schema_types
    has_article   = bool({"Article", "BlogPosting"} & schema_types)
    has_review    = bool({"Review", "AggregateRating"} & schema_types)
    has_person    = "Person" in schema_types

    # E-E-A-T
    has_about_page  = _has_page_matching(pages, r"/(about|meet|team|practitioner|therapist|bio|author)")
    has_contact_pg  = _has_page_matching(pages, r"/(contact|reach|get-in-touch|find-us)")
    has_privacy_pg  = _has_page_matching(pages, r"/(privacy|terms|legal|gdpr|cookie)")
    ref_domains     = safe_get(first_result(data.get("backlinks", {})), "referring_domains", default=0)

    # Local SEO
    gbp_listing  = (gbp_items[0] if gbp_items and isinstance(gbp_items, list) else {}) or {}
    gbp_found    = bool(gbp_listing)
    gbp_name     = safe_get(gbp_listing, "title",  default="N/A")
    gbp_address  = safe_get(gbp_listing, "address", default="N/A")
    gbp_rating   = safe_get(gbp_listing, "rating", "value", default=None)
    gbp_review_n = safe_get(gbp_listing, "rating", "votes_count", default=0)

    reviews      = review_items if isinstance(review_items, list) else []
    avg_rating   = _average_ratings(reviews)
    review_count = len(reviews)

    in_local_pack = _check_local_pack(serp_items)

    # Extract real AI visibility data if available
    ai_mentions = _extract_llm_mentions(llm_mentions or {}, llm_mentions_agg or {})
    serp_features = _extract_serp_features(brand_serp or [])

    # Use real local pack detection from brand SERP if available
    if serp_features.get("local_pack_detected"):
        in_local_pack = True

    # AI Overview readiness — weight real data when available
    ai_score = _score_ai_overview(
        has_faq=has_faq,
        has_local_biz=has_local_biz,
        has_person=has_person,
        has_about_page=has_about_page,
        gbp_found=gbp_found,
        referring_domains=ref_domains,
    )
    # Bonus points for real AI visibility signals
    if ai_mentions.get("mentions_found"):
        ai_score = min(ai_score + 10, 100)
    if serp_features.get("featured_snippet_detected"):
        ai_score = min(ai_score + 5, 100)

    return {
        "schema": {
            "types_detected":     sorted(schema_types),
            "has_local_business": has_local_biz,
            "has_faq_page":       has_faq,
            "has_article":        has_article,
            "has_review_schema":  has_review,
            "has_person":         has_person,
        },
        "eeat": {
            "has_about_page":   has_about_page,
            "has_contact_page": has_contact_pg,
            "has_privacy_page": has_privacy_pg,
            "referring_domains": ref_domains,
        },
        "local": {
            "gbp_found":    gbp_found,
            "gbp_name":     gbp_name,
            "gbp_address":  gbp_address,
            "gbp_rating":   gbp_rating,
            "gbp_reviews":  gbp_review_n,
            "in_local_pack": in_local_pack,
            "review_count": review_count,
            "avg_rating":   avg_rating,
        },
        "ai_overview": {
            "readiness_score": ai_score,
            "score_label":     _score_label(ai_score),
        },
        "ai_visibility": {
            "llm_mentions": ai_mentions,
            "serp_features": serp_features,
        },
        "recommendations": _build_recommendations(
            has_local_biz=has_local_biz,
            has_faq=has_faq,
            has_about_page=has_about_page,
            has_contact_pg=has_contact_pg,
            has_person=has_person,
            has_review=has_review,
            gbp_found=gbp_found,
            gbp_rating=gbp_rating,
            gbp_reviews=gbp_review_n,
            in_local_pack=in_local_pack,
        ),
    }
