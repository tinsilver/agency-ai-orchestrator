"""
Per-page SEO content gap analysis (--deep mode).

For the domain's keywords ranking at positions 4–30 (reachable quick-wins),
this module:
  1. Picks the top-N highest-volume gap keywords
  2. Fetches live SERP results to identify who ranks #1–3
  3. Parses competitor page content via DataForSEO content_parsing
  4. Scores content gaps: word count, heading structure, topic coverage
  5. Returns per-keyword action briefs

This is an expensive operation (~1 SERP + 3 content_parsing calls per keyword).
The CLI --deep flag enables it; default is off.
"""
from __future__ import annotations

import time
from typing import Optional

from app.services.dataforseo_client import DataForSEOClient, safe_get


MAX_GAP_KEYWORDS     = 5   # max keywords to analyse in deep mode
MAX_SERP_COMPETITORS = 3   # max competitor pages to parse per keyword
MIN_WORD_COUNT_GAP   = 800 # word count threshold for a gap recommendation


def analyse_gaps(
    client:        DataForSEOClient,
    domain:        str,
    keywords_data: dict,
    location_code: int  = 2826,
    cost_tracker         = None,
) -> list[dict]:
    """
    Run per-keyword content gap analysis.

    Args:
        client:        DataForSEOClient instance.
        domain:        Target domain (bare, e.g. 'enricoviola.com').
        keywords_data: Raw ranked_keywords API response.
        location_code: DataForSEO location code.
        cost_tracker:  Optional CostTracker for cost tracking.

    Returns:
        List of gap dicts, one per analysed keyword.
    """
    items    = safe_get(keywords_data, "tasks", 0, "result", 0, "items", default=[])
    gap_kws  = _select_gap_keywords(items)

    if not gap_kws:
        print("   ⚠  No gap keywords found (positions 4–30)")
        return []

    print(f"   → Analysing {len(gap_kws)} gap keywords (SERP + content parsing)…")
    results = []

    for kw_data in gap_kws:
        kw  = kw_data["keyword"]
        pos = kw_data["position"]
        print(f"      '{kw}' (pos {pos}, vol {kw_data['search_volume']:,})…")

        # 1. Fetch SERP
        serp_items = _fetch_serp(client, kw, location_code, cost_tracker)

        # 2. Identify competitor pages (not our domain)
        competitor_urls = _pick_competitor_urls(serp_items, domain)

        # 3. Parse competitor content
        competitor_data = _parse_competitors(client, competitor_urls, cost_tracker)

        # 4. Score gaps
        our_url = _build_our_url(domain, kw_data["url"])
        gap     = _score_gaps(competitor_data)

        results.append({
            "keyword":         kw,
            "position":        pos,
            "search_volume":   kw_data["search_volume"],
            "etv":             kw_data["etv"],
            "target_url":      our_url,
            "competitors_analysed": len(competitor_data),
            "avg_competitor_word_count": gap["avg_word_count"],
            "avg_competitor_h2_count":   gap["avg_h2_count"],
            "gap_actions":               gap["actions"],
        })

        time.sleep(0.5)  # gentle rate limiting

    return results


# ── Helpers ────────────────────────────────────────────────────────────────────

def _select_gap_keywords(items: list) -> list[dict]:
    """Filter and sort keywords by volume, keeping positions 4–30 only."""
    gap = []
    for item in (items if isinstance(items, list) else []):
        pos = safe_get(item, "ranked_serp_element", "serp_item", "rank_absolute", default=0)
        try:
            pos = int(pos)
            if not (4 <= pos <= 30):
                continue
        except (TypeError, ValueError):
            continue

        kw  = safe_get(item, "keyword_data", "keyword", default=None)
        if not kw:
            continue

        sv  = safe_get(item, "keyword_data", "keyword_info", "search_volume", default=0)
        etv = safe_get(item, "ranked_serp_element", "serp_item", "etv", default=0)
        url = safe_get(item, "ranked_serp_element", "serp_item", "relative_url", default="/")

        try:
            sv = int(sv or 0)
        except (TypeError, ValueError):
            sv = 0

        gap.append({"keyword": kw, "position": pos, "search_volume": sv,
                    "etv": etv, "url": url})

    gap.sort(key=lambda x: x["search_volume"], reverse=True)
    return gap[:MAX_GAP_KEYWORDS]


def _fetch_serp(
    client:        DataForSEOClient,
    keyword:       str,
    location_code: int,
    cost_tracker,
) -> list:
    try:
        resp  = client.serp_organic_live(keyword, location_code=location_code)
        if cost_tracker:
            cost_tracker.track_call("serp_organic_live")
        items = safe_get(resp, "tasks", 0, "result", 0, "items", default=[])
        return items if isinstance(items, list) else []
    except Exception as e:
        print(f"      ✗ SERP failed: {e}")
        return []


def _pick_competitor_urls(serp_items: list, domain: str) -> list[str]:
    urls = []
    for item in serp_items:
        item_domain = safe_get(item, "domain", default="")
        item_url    = safe_get(item, "url",    default="")
        if domain not in item_domain and item_url.startswith("http"):
            urls.append(item_url)
        if len(urls) >= MAX_SERP_COMPETITORS:
            break
    return urls


def _parse_competitors(
    client:          DataForSEOClient,
    competitor_urls: list[str],
    cost_tracker,
) -> list[dict]:
    results = []
    for url in competitor_urls:
        try:
            resp   = client.content_parsing(url)
            if cost_tracker:
                cost_tracker.track_call("content_parsing")
            result = safe_get(resp, "tasks", 0, "result", 0, default={})

            word_count = safe_get(result, "content", "plain_text_word_count", default=0)
            htags      = safe_get(result, "content", "meta", "htags", default={}) or {}
            h2_list    = safe_get(htags, "h2", default=[]) or []
            h3_list    = safe_get(htags, "h3", default=[]) or []

            results.append({
                "url":        url,
                "word_count": int(word_count or 0),
                "h2_count":   len(h2_list),
                "h3_count":   len(h3_list),
                "h2_texts":   [str(h) for h in h2_list[:6]],
            })
            time.sleep(0.5)
        except Exception as e:
            print(f"      ✗ Content parsing failed ({url[:60]}…): {e}")
    return results


def _build_our_url(domain: str, relative_url: str) -> str:
    rel = str(relative_url or "/")
    if not rel.startswith("/"):
        rel = "/" + rel
    return f"https://{domain}{rel}"


def _score_gaps(competitor_data: list[dict]) -> dict:
    """Produce actionable content gap insights from competitor averages."""
    if not competitor_data:
        return {
            "avg_word_count": 0,
            "avg_h2_count":   0,
            "actions":        ["Unable to parse competitor content — review manually"],
        }

    avg_wc = sum(c["word_count"] for c in competitor_data) / len(competitor_data)
    avg_h2 = sum(c["h2_count"]   for c in competitor_data) / len(competitor_data)

    actions = []

    if avg_wc >= MIN_WORD_COUNT_GAP:
        target = round(avg_wc * 1.1 / 50) * 50  # round to nearest 50
        actions.append(
            f"Expand page content to ~{target:,} words "
            f"(competitors average {round(avg_wc):,})"
        )

    if avg_h2 >= 4:
        actions.append(
            f"Add more sub-sections — competitors use ~{round(avg_h2)} H2 headings, "
            "improving content depth and featured snippet eligibility"
        )

    if avg_h2 >= 2:
        actions.append(
            "Structure content with clear H2 → H3 hierarchy; "
            "this directly improves AI Overview and People Also Ask eligibility"
        )

    # Surface competitor topic areas
    all_h2 = []
    for c in competitor_data:
        all_h2.extend(c.get("h2_texts", []))
    if all_h2:
        unique_h2 = list(dict.fromkeys(all_h2))[:4]
        actions.append(
            "Consider covering these topics found in top-ranking pages: "
            + "; ".join(f'"{h}"' for h in unique_h2)
        )

    if not actions:
        actions.append("Content length and structure appear competitive — focus on E-E-A-T signals")

    return {
        "avg_word_count": round(avg_wc),
        "avg_h2_count":   round(avg_h2, 1),
        "actions":        actions,
    }
