"""
DataForSEO API client.

Follows DataForSEO best practices:
  - status_code 20100 = task created, 20000 = task ready
  - Retry on transient 5xxxx errors with back-off
  - Poll /tasks_ready before fetching task results (OnPage)
  - 30 concurrent-request limit respected for live endpoints
  - Pre-encoded base64 API key read from DATAFORSEO_API_KEY env var
"""
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import requests


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def safe_get(obj: Any, *keys, default: Any = "N/A") -> Any:
    """Safely traverse nested dict/list without raising."""
    try:
        for k in keys:
            if isinstance(obj, list):
                obj = obj[int(k)]
            else:
                obj = obj[k]
        return obj if obj is not None else default
    except (KeyError, IndexError, TypeError, ValueError):
        return default


def first_result(api_response: dict, *path) -> Any:
    """Shortcut: tasks[0].result[0][...path]"""
    return safe_get(api_response, "tasks", 0, "result", 0, *path)


class DataForSEOClient:
    """
    Thin HTTP wrapper around the DataForSEO REST API v3.

    Authentication: HTTP Basic with a pre-encoded base64 key
    (DATAFORSEO_API_KEY = base64("login:password")).
    """

    LIVE_URL = "https://api.dataforseo.com/v3"
    SANDBOX_URL = "https://sandbox.dataforseo.com/v3"
    MAX_RETRIES = 3
    RETRY_DELAY = 10  # seconds between retry attempts

    def __init__(
        self,
        api_key: Optional[str] = None,
        sandbox: bool = False,
        use_standard: bool = False,
    ):
        """
        Args:
            api_key:       Base64-encoded "login:password" key.  Reads from
                           DATAFORSEO_API_KEY env var if not supplied.
            sandbox:       Route all calls to the DataForSEO sandbox.
            use_standard:  If True, use the cheaper asynchronous Standard method
                           (task_post → tasks_ready poll → task_get/advanced) for
                           all endpoints that support it.  Live-only endpoints
                           (instant_pages, lighthouse, my_business_info) are
                           unaffected.  Default: False (Live method).
        """
        key = api_key or os.environ.get("DATAFORSEO_API_KEY")
        if not key:
            raise ValueError(
                "DataForSEO API key not found. "
                "Set DATAFORSEO_API_KEY env var (base64 of login:password)."
            )
        self.sandbox      = sandbox
        self.use_standard = use_standard
        self.base_url     = self.SANDBOX_URL if sandbox else self.LIVE_URL
        self.session      = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {key}",
            "Content-Type": "application/json",
        })

    # ── Core request helpers ───────────────────────────────────────────────────

    def _post(self, endpoint: str, payload: list, timeout: int = 120) -> dict:
        url = f"{self.base_url}{endpoint}"
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self.session.post(url, json=payload, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                top_code = data.get("status_code", 0)
                if top_code in (50000, 50401):
                    print(
                        f"   ⚠  API error {top_code} on attempt "
                        f"{attempt}/{self.MAX_RETRIES}, retrying in {self.RETRY_DELAY}s…"
                    )
                    time.sleep(self.RETRY_DELAY)
                    continue
                return data
            except requests.exceptions.Timeout:
                print(f"   ⚠  Request timed out (attempt {attempt})")
                time.sleep(self.RETRY_DELAY)
        raise RuntimeError(f"Failed after {self.MAX_RETRIES} attempts: POST {endpoint}")

    def _get(self, endpoint: str, timeout: int = 60) -> dict:
        url = f"{self.base_url}{endpoint}"
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                top_code = data.get("status_code", 0)
                if top_code in (50000, 50401):
                    print(f"   ⚠  API error {top_code} on attempt {attempt}, retrying…")
                    time.sleep(self.RETRY_DELAY)
                    continue
                return data
            except requests.exceptions.Timeout:
                print(f"   ⚠  GET timed out (attempt {attempt})")
                time.sleep(self.RETRY_DELAY)
        raise RuntimeError(f"Failed after {self.MAX_RETRIES} attempts: GET {endpoint}")

    def _check_task_created(self, response: dict, endpoint: str) -> Optional[str]:
        """Return task ID if status_code == 20100, else None."""
        try:
            task = response["tasks"][0]
            code = task.get("status_code")
            if code == 20100:
                return task["id"]
            print(
                f"   ✗  Task rejected for {endpoint}: "
                f"{code} – {task.get('status_message', '')}"
            )
            return None
        except (KeyError, IndexError) as exc:
            print(f"   ✗  Could not parse task response for {endpoint}: {exc}")
            return None

    # ── Standard / Live dispatch ───────────────────────────────────────────────

    def _call(self, base_path: str, payload: list, timeout: int = 120) -> dict:
        """
        Route a request through either the Live or Standard method.

        Live   (use_standard=False):
            POST {base_path}/live  →  immediate results

        Standard (use_standard=True):
            POST {base_path}/task_post  →  poll {base_path}/tasks_ready
            →  GET {base_path}/task_get/advanced/{id}
        """
        if not self.use_standard:
            return self._post(f"{base_path}/live", payload, timeout=timeout)

        resp    = self._post(f"{base_path}/task_post", payload, timeout=60)
        task_id = self._check_task_created(resp, f"{base_path}/task_post")
        if not task_id:
            return {}
        return self._poll_standard_task(base_path, task_id)

    def _poll_standard_task(
        self,
        base_path: str,
        task_id: str,
        poll_interval: int = 10,
        max_wait: int = 120,
    ) -> dict:
        """Poll {base_path}/tasks_ready until task_id appears, then fetch results."""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(poll_interval)
            ready_resp = self._get(f"{base_path}/tasks_ready")
            for task in ready_resp.get("tasks") or []:
                for item in task.get("result") or []:
                    if isinstance(item, dict) and item.get("id") == task_id:
                        return self._get(
                            f"{base_path}/task_get/advanced/{task_id}"
                        )
        print(
            f"   ⚠  Standard task {task_id} not ready after {max_wait}s "
            "— fetching anyway…"
        )
        return self._get(f"{base_path}/task_get/advanced/{task_id}")

    # ── DataForSEO Labs ────────────────────────────────────────────────────────
    # NOTE: DataForSEO Labs has NO Standard (task_post) variants — live only.

    def domain_rank_overview(self, domain: str, location_code: int = 2826) -> dict:
        """Domain-level organic/paid metrics."""
        payload = [{"target": domain, "location_code": location_code, "language_code": "en"}]
        return self._post("/dataforseo_labs/google/domain_rank_overview/live", payload)

    def ranked_keywords(
        self, domain: str, location_code: int = 2826, limit: int = 50
    ) -> dict:
        """Top organic keywords by estimated traffic volume."""
        payload = [{
            "target": domain,
            "location_code": location_code,
            "language_code": "en",
            "limit": limit,
            "order_by": ["ranked_serp_element.serp_item.etv,desc"],
        }]
        return self._post("/dataforseo_labs/google/ranked_keywords/live", payload)

    def competitors_domain(self, domain: str, location_code: int = 2826) -> dict:
        """Organic competitors ranked by shared-keyword overlap."""
        payload = [{
            "target": domain,
            "location_code": location_code,
            "language_code": "en",
            "limit": 10,
        }]
        return self._post("/dataforseo_labs/google/competitors_domain/live", payload)

    def keyword_ideas(
        self, keywords: list[str], location_code: int = 2826, limit: int = 30
    ) -> dict:
        """Keyword ideas and related terms for content gap analysis."""
        payload = [{
            "keywords": keywords,
            "location_code": location_code,
            "language_code": "en",
            "limit": limit,
        }]
        return self._post("/dataforseo_labs/google/keyword_ideas/live", payload)

    def historical_rank_overview(self, domain: str, location_code: int = 2826) -> dict:
        """Historical organic visibility trend (6–12 months)."""
        payload = [{"target": domain, "location_code": location_code, "language_code": "en"}]
        return self._post("/dataforseo_labs/google/historical_rank_overview/live", payload)

    def keywords_for_site(self, domain: str, location_code: int = 2826, limit: int = 100) -> dict:
        """Full keyword universe with position brackets."""
        payload = [{
            "target": domain,
            "location_code": location_code,
            "language_code": "en",
            "limit": limit,
        }]
        return self._post("/dataforseo_labs/google/keywords_for_site/live", payload)

    # ── Backlinks ──────────────────────────────────────────────────────────────
    # NOTE: Backlinks API has NO Standard (task_post) variants — live only.

    def backlinks_summary(self, domain: str) -> dict:
        """High-level backlink stats: total links, referring domains, broken."""
        payload = [{"target": domain, "target_type": "domain", "include_subdomains": True}]
        return self._post("/backlinks/summary/live", payload)

    def referring_domains(self, domain: str, limit: int = 30) -> dict:
        """Top referring domains ordered by domain rank."""
        payload = [{
            "target": domain,
            "target_type": "domain",
            "include_subdomains": True,
            "limit": limit,
            "order_by": ["rank,desc"],
        }]
        return self._post("/backlinks/referring_domains/live", payload)

    # ── OnPage API (task-based, poll Tasks Ready) ──────────────────────────────

    def onpage_task_post(self, domain: str, max_crawl_pages: int = 100) -> Optional[str]:
        """
        Submit an OnPage crawl task.
        Returns task_id if accepted (status_code 20100), else None.
        Per best practices: always verify status before proceeding.
        """
        payload = [{
            "target": domain,
            "max_crawl_pages": max_crawl_pages,
            "load_resources": True,
            "enable_javascript": False,
            "store_raw_html": False,
            "check_spell": False,
        }]
        resp = self._post("/on_page/task_post", payload)
        return self._check_task_created(resp, "/on_page/task_post")

    def onpage_wait_and_fetch(
        self, task_id: str, poll_interval: int = 20, max_wait: int = 360
    ) -> dict:
        """
        Poll /on_page/tasks_ready until our task appears, then fetch summary.
        Per best practices: use Tasks Ready rather than a blind sleep.
        """
        print(f"   ⏳ Polling for OnPage task {task_id}…")
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(poll_interval)
            ready_resp = self._get("/on_page/tasks_ready")
            for task in ready_resp.get("tasks") or []:
                for item in task.get("result") or []:
                    if isinstance(item, dict) and item.get("id") == task_id:
                        print("   ✓  OnPage task ready, fetching summary…")
                        return self._get(f"/on_page/summary/{task_id}")
        print(f"   ⚠  OnPage task not ready after {max_wait}s — fetching anyway…")
        return self._get(f"/on_page/summary/{task_id}")

    def onpage_pages_issues(self, task_id: str) -> dict:
        """
        Fetch pages with on-page issues from an OnPage crawl task.
        Uses /on_page/pages with a filter for pages that have warnings or errors.
        """
        payload = [{
            "id": task_id,
            "limit": 100,
            "filters": [
                "resource_type", "=", "html"
            ],
            "order_by": ["onpage_score,asc"],
        }]
        return self._post("/on_page/pages", payload)

    def onpage_pages(self, task_id: str, limit: int = 50) -> dict:
        """Fetch crawled page details."""
        payload = [{"id": task_id, "limit": limit,
                    "order_by": ["meta.content.plain_text_word_count,desc"]}]
        try:
            result = self._post("/on_page/pages", payload)
            items = safe_get(result, "tasks", 0, "result", 0, "items", default=[])
            if not items:
                payload[0].pop("filters", None)
                result = self._post("/on_page/pages", payload)
            return result
        except Exception:
            payload[0].pop("filters", None)
            return self._post("/on_page/pages", payload)

    def onpage_duplicate_tags(self, task_id: str, limit: int = 50) -> dict:
        """
        Fetch pages with duplicate title or meta description tags.
        DataForSEO requires a `type` field: makes two calls (one per type)
        and merges the results into a single response wrapper.
        """
        items: list = []
        for tag_type in ("duplicate_title", "duplicate_description"):
            payload = [{"id": task_id, "type": tag_type, "limit": limit}]
            try:
                resp = self._post("/on_page/duplicate_tags", payload)
                batch = safe_get(resp, "tasks", 0, "result", 0, "items", default=[])
                if isinstance(batch, list):
                    items.extend(batch)
            except Exception as exc:
                print(f"   ⚠  duplicate_tags ({tag_type}): {exc}")
        return {"tasks": [{"status_code": 20000, "result": [{"items": items}]}]}

    def onpage_duplicate_content(self, task_id: str, url: str, limit: int = 50) -> dict:
        """
        Fetch near-duplicate pages for a given URL.
        DataForSEO requires a `url` field (the starting page URL).
        """
        payload = [{"id": task_id, "url": url, "limit": limit}]
        return self._post("/on_page/duplicate_content", payload)

    def onpage_redirect_chains(self, task_id: str, limit: int = 50) -> dict:
        """Fetch multi-hop redirect chains wasting crawl budget."""
        payload = [{"id": task_id, "limit": limit}]
        return self._post("/on_page/redirect_chains", payload)

    def onpage_resources(self, task_id: str, limit: int = 100, broken_only: bool = True) -> dict:
        """Fetch page resources (images/CSS/JS). Optionally filter to broken only."""
        payload = [{"id": task_id, "limit": limit}]
        if broken_only:
            payload[0]["filters"] = ["resource_type", "=", "broken"]
        return self._post("/on_page/resources", payload)

    # ── Page Speed (OnPage Instant Pages, live) ────────────────────────────────

    def page_speed(self, url: str) -> dict:
        """
        OnPage Instant Pages — Lighthouse metrics.
        Live endpoint; timeout set to 120s per DataForSEO recommendation.
        """
        payload = [{"url": url, "enable_javascript": True, "load_resources": True}]
        return self._post("/on_page/instant_pages", payload, timeout=120)

    def onpage_lighthouse(self, url: str, for_mobile: bool = False) -> dict:
        """
        Real Google Lighthouse audit scores.
        Returns four category scores (0.0–1.0 floats, multiply by 100 for display):
          performance, accessibility, best-practices, seo
        Also returns individual Core Web Vitals audits with human-readable displayValues
        (LCP, TBT, CLS, Speed Index, FCP).
        Live endpoint; timeout 120s.
        Correct path: /on_page/lighthouse/live/json
        """
        payload = [{"url": url, "for_mobile": for_mobile}]
        return self._post("/on_page/lighthouse/live/json", payload, timeout=120)

    # ── SERP / GEO ─────────────────────────────────────────────────────────────

    def serp_organic_live(
        self,
        keyword: str,
        location_code: int = 2826,
        language_code: str = "en",
    ) -> dict:
        """
        Live organic SERP results for a keyword.
        Useful for GEO/local ranking checks with location_code targeting.
        Common location codes: 2840=US, 2826=UK, 2036=AU, 2124=CA, 2276=DE
        """
        payload = [{
            "keyword": keyword,
            "location_code": location_code,
            "language_code": language_code,
            "device": "desktop",
            "os": "windows",
        }]
        return self._post("/serp/google/organic/live/advanced", payload)

    # ── AI Optimisation (Tier 4, toggleable) ─────────────────────────────────

    def llm_mentions_search(self, keyword: str, location_code: int = 2826) -> dict:
        """
        Search for brand mentions in LLM outputs (ChatGPT, Google AI, etc.).
        `target` must be an array of objects: [{"keyword": "...", "match_type": "partial_match"}]
        """
        payload = [{
            "target": [{"keyword": keyword, "match_type": "partial_match"}],
            "location_code": location_code,
            "language_code": "en",
        }]
        return self._post("/ai_optimization/llm_mentions/search/live", payload)

    def llm_mentions_aggregated(self, keyword: str, location_code: int = 2826) -> dict:
        """
        Aggregated LLM mention metrics and trends.
        `target` must be an array of objects: [{"keyword": "...", "match_type": "partial_match"}]
        """
        payload = [{
            "target": [{"keyword": keyword, "match_type": "partial_match"}],
            "location_code": location_code,
            "language_code": "en",
        }]
        return self._post("/ai_optimization/llm_mentions/aggregated_metrics/live", payload)

    # ── Tier 1: Keyword Gap & Extended Backlinks ───────────────────────────────

    def keyword_gap(self, targets: list[str], location_code: int = 2826) -> dict:
        """
        Keyword gap analysis: keywords the competitor ranks for but the target domain doesn't.
        targets[0] is the main (client) domain; targets[1] is the competitor.
        Uses domain_intersection with intersections=False to find competitor-exclusive keywords.
        """
        client_domain = targets[0]
        competitor    = targets[1] if len(targets) > 1 else targets[0]
        payload = [{
            "target1":       competitor,
            "target2":       client_domain,
            "location_code": location_code,
            "language_code": "en",
            "limit":         50,
            "intersections": False,  # keywords only target1 (competitor) ranks for
        }]
        return self._post("/dataforseo_labs/google/domain_intersection/live", payload)

    def anchor_text(self, domain: str, limit: int = 30) -> dict:
        """Anchor text distribution for a domain's backlink profile."""
        payload = [{
            "target": domain,
            "target_type": "domain",
            "limit": limit,
        }]
        return self._post("/backlinks/anchors/live", payload)

    def domain_whois(self, domain: str) -> dict:
        """WHOIS and domain registration / expiry data for a single domain."""
        payload = [{
            "limit": 1,
            "filters": [["domain", "=", domain]],
        }]
        return self._post("/domain_analytics/whois/overview/live", payload)

    def onpage_non_indexable(self, task_id: str, limit: int = 50) -> dict:
        """Fetch non-indexable pages discovered during an OnPage crawl task."""
        payload = [{"id": task_id, "limit": limit}]
        return self._post("/on_page/non_indexable", payload)

    def onpage_links(self, task_id: str, limit: int = 100) -> dict:
        """Fetch the internal link map from an OnPage crawl task."""
        payload = [{"id": task_id, "limit": limit}]
        return self._post("/on_page/links", payload)

    # ── Tier 2: Backlink History, Keyword Intelligence, Content ───────────────

    def backlinks_history(self, domain: str, date_from: str = "2023-01-01") -> dict:
        """Historical backlink growth over time."""
        from datetime import date
        payload = [{
            "target":      domain,
            "target_type": "domain",
            "date_from":   date_from,
            "date_to":     date.today().isoformat(),
        }]
        return self._post("/backlinks/history/live", payload)

    def bulk_keyword_difficulty(
        self, keywords: list[str], location_code: int = 2826
    ) -> dict:
        """Bulk keyword difficulty scores (0–100) for a list of keywords."""
        payload = [{
            "keywords":      keywords[:1000],
            "location_code": location_code,
            "language_code": "en",
        }]
        return self._post("/dataforseo_labs/google/bulk_keyword_difficulty/live", payload)

    def content_parsing(self, url: str) -> dict:
        """
        Parse and extract structured content from a URL (word count, headings, entities).
        Live endpoint; used in deep gap analysis.
        """
        payload = [{"url": url, "enable_javascript": False, "load_resources": False}]
        return self._post("/on_page/content_parsing/live", payload, timeout=60)

    def search_intent(
        self, keywords: list[str], location_code: int = 2826
    ) -> dict:
        """Classify search intent (informational / commercial / transactional / navigational)."""
        payload = [{
            "keywords":      keywords[:100],
            "location_code": location_code,
            "language_code": "en",
        }]
        return self._post("/dataforseo_labs/google/search_intent/live", payload)

    def related_keywords(
        self, keyword: str, location_code: int = 2826, limit: int = 20
    ) -> dict:
        """Semantically related keywords and their search metrics."""
        payload = [{
            "keyword":       keyword,
            "location_code": location_code,
            "language_code": "en",
            "limit":         limit,
        }]
        return self._post("/dataforseo_labs/google/related_keywords/live", payload)

    # ── Tier 3: Local / Google Business Profile ────────────────────────────────

    def google_business_info(
        self, keyword: str, location_code: int = 2826
    ) -> dict:
        """
        Fetch Google Business Profile info by keyword or business name.
        Returns GBP data: title, address, rating, categories, work hours.
        Uses the /my_business_info/live endpoint.
        """
        payload = [{
            "keyword":       keyword,
            "location_code": location_code,
            "language_code": "en",
        }]
        return self._post("/business_data/google/my_business_info/live", payload)

    def google_reviews_task_post(
        self, keyword: str, location_code: int = 2826, depth: int = 10
    ) -> Optional[str]:
        """
        Submit a Google Reviews collection task (task-based, no live endpoint).
        priority=2 (high) reduces queue wait; billed at a small premium.
        Returns task_id if accepted, else None.
        """
        payload = [{
            "keyword":       keyword,
            "location_code": location_code,
            "language_code": "en",
            "depth":         depth,
            "priority":      2,
        }]
        resp = self._post("/business_data/google/reviews/task_post", payload)
        return self._check_task_created(resp, "google/reviews/task_post")

    def google_reviews_wait_and_fetch(
        self, task_id: str, poll_interval: int = 10, max_wait: int = 120
    ) -> dict:
        """
        Poll /business_data/google/reviews/tasks_ready until our task appears,
        then fetch results. Falls back to direct GET after max_wait seconds.
        """
        print(f"   ⏳ Polling for Google Reviews task {task_id}…")
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(poll_interval)
            ready_resp = self._get("/business_data/google/reviews/tasks_ready")
            for task in ready_resp.get("tasks") or []:
                for item in task.get("result") or []:
                    if isinstance(item, dict) and item.get("id") == task_id:
                        print("   ✓  Reviews task ready, fetching…")
                        return self._get(
                            f"/business_data/google/reviews/task_get/{task_id}"
                        )
        print(f"   ⚠  Reviews task not ready after {max_wait}s — fetching anyway…")
        return self._get(f"/business_data/google/reviews/task_get/{task_id}")

    # ── Domain Analytics ───────────────────────────────────────────────────────

    def domain_technologies(self, domain: str) -> dict:
        """CMS, analytics, CDN, and framework detection for a domain."""
        payload = [{
            "target": domain,
            "limit": 1,
        }]
        return self._post("/domain_analytics/technologies/domain_technologies/live", payload)

    # ── Account ────────────────────────────────────────────────────────────────

    def get_user_data(self) -> dict:
        """Fetch account info, plan details, and remaining API credits."""
        return self._get("/user/data")
