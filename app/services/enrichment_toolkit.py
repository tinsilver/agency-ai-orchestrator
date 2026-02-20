"""
EnrichmentToolkit: Orchestrates all dynamic enrichment tools with budget enforcement.
"""
from typing import Dict, Any, Optional
from langfuse import observe


class EnrichmentToolkit:
    """
    Unified service providing all dynamic enrichment tools.
    Enforces per-tool usage budgets to prevent excessive API calls.
    """

    def __init__(self):
        # Tool budgets (max calls per request)
        self.tool_budgets = {
            "web_fetch": 5,
            "web_search": 3,
            "image_analysis": 3,
            "pdf_extract": 2,
            "form_detector": 3,
            "social_media_finder": 2,
            "seo_audit": 1,
            "google_maps_scraper": 1,
            "google_reviews_scraper": 1
        }

        # Initialize tool services (lazy loading)
        self._web_scraper = None
        self._web_search = None
        self._form_detector = None
        self._social_media_finder = None
        self._image_analyzer = None
        self._pdf_extractor = None
        self._seo_auditor = None
        self._maps_scraper = None
        self._reviews_scraper = None

    def _check_budget(self, tool_name: str, usage_stats: dict) -> bool:
        """
        Check if tool has budget remaining.

        Args:
            tool_name: Name of the tool
            usage_stats: Current usage statistics dict

        Returns:
            True if tool can be called, False if budget exceeded
        """
        if tool_name not in usage_stats:
            return True

        current_calls = usage_stats[tool_name].get("calls", 0)
        max_calls = self.tool_budgets.get(tool_name, 1)
        return current_calls < max_calls

    def _increment_usage(self, tool_name: str, usage_stats: dict):
        """
        Track tool usage by incrementing call count.

        Args:
            tool_name: Name of the tool
            usage_stats: Usage statistics dict to update (mutated in place)
        """
        if tool_name not in usage_stats:
            usage_stats[tool_name] = {
                "calls": 0,
                "max_calls": self.tool_budgets.get(tool_name, 1)
            }
        usage_stats[tool_name]["calls"] += 1

    def get_available_tools(self, usage_stats: dict) -> list[Dict[str, Any]]:
        """
        Get list of available tools with remaining budget.

        Args:
            usage_stats: Current usage statistics

        Returns:
            List of available tools with metadata
        """
        available = []
        for tool_name, max_calls in self.tool_budgets.items():
            if tool_name in usage_stats:
                current_calls = usage_stats[tool_name].get("calls", 0)
                remaining = max_calls - current_calls
            else:
                remaining = max_calls

            if remaining > 0:
                available.append({
                    "name": tool_name,
                    "max_calls": max_calls,
                    "remaining_calls": remaining
                })

        return available

    @observe(name="web-fetch-tool")
    async def web_fetch(self, url: str, usage_stats: dict) -> Dict[str, Any]:
        """
        Fetch and parse webpage content.

        Args:
            url: URL to fetch
            usage_stats: Current usage statistics

        Returns:
            Dict with webpage data or error
        """
        if not self._check_budget("web_fetch", usage_stats):
            return {"error": "Tool budget exceeded for web_fetch"}

        try:
            # Lazy load web scraper
            if self._web_scraper is None:
                from app.services.web_scraper import WebScraperService
                self._web_scraper = WebScraperService()

            result = await self._web_scraper.scrape_url(url)
            self._increment_usage("web_fetch", usage_stats)
            return result

        except Exception as e:
            return {"error": f"web_fetch failed: {str(e)}"}

    @observe(name="web-search-tool")
    async def web_search(self, query: str, usage_stats: dict) -> Dict[str, Any]:
        """
        Search the web for information.

        Args:
            query: Search query
            usage_stats: Current usage statistics

        Returns:
            Dict with search results or error
        """
        if not self._check_budget("web_search", usage_stats):
            return {"error": "Tool budget exceeded for web_search"}

        try:
            # Lazy load web search service
            if self._web_search is None:
                from app.services.web_search import WebSearchService
                self._web_search = WebSearchService()

            result = await self._web_search.search(query)
            self._increment_usage("web_search", usage_stats)
            return result

        except Exception as e:
            return {"error": f"web_search failed: {str(e)}"}

    @observe(name="form-detector-tool")
    async def form_detector(self, url: str, usage_stats: dict) -> Dict[str, Any]:
        """
        Detect forms on a webpage.

        Args:
            url: URL to analyze
            usage_stats: Current usage statistics

        Returns:
            Dict with form information or error
        """
        if not self._check_budget("form_detector", usage_stats):
            return {"error": "Tool budget exceeded for form_detector"}

        try:
            # Lazy load form detector service
            if self._form_detector is None:
                from app.services.form_detector import FormDetectorService
                self._form_detector = FormDetectorService()

            result = await self._form_detector.detect_forms(url)
            self._increment_usage("form_detector", usage_stats)
            return result

        except Exception as e:
            return {"error": f"form_detector failed: {str(e)}"}

    @observe(name="social-media-finder-tool")
    async def social_media_finder(self, url: str, usage_stats: dict) -> Dict[str, Any]:
        """
        Find social media accounts linked from a website.

        Args:
            url: URL to analyze
            usage_stats: Current usage statistics

        Returns:
            Dict with social media links or error
        """
        if not self._check_budget("social_media_finder", usage_stats):
            return {"error": "Tool budget exceeded for social_media_finder"}

        try:
            # Lazy load social media finder service
            if self._social_media_finder is None:
                from app.services.social_media_finder import SocialMediaFinderService
                self._social_media_finder = SocialMediaFinderService()

            result = await self._social_media_finder.find_accounts(url)
            self._increment_usage("social_media_finder", usage_stats)
            return result

        except Exception as e:
            return {"error": f"social_media_finder failed: {str(e)}"}

    @observe(name="image-analysis-tool")
    async def image_analysis(self, image_path: str, usage_stats: dict) -> Dict[str, Any]:
        """
        Analyze image properties and content using Claude vision.

        Args:
            image_path: Path or URL to image
            usage_stats: Current usage statistics

        Returns:
            Dict with image analysis or error
        """
        if not self._check_budget("image_analysis", usage_stats):
            return {"error": "Tool budget exceeded for image_analysis"}

        try:
            # Lazy load image analyzer service
            if self._image_analyzer is None:
                from app.services.image_analysis import ImageAnalysisService
                self._image_analyzer = ImageAnalysisService()

            result = await self._image_analyzer.analyze(image_path)
            self._increment_usage("image_analysis", usage_stats)
            return result

        except Exception as e:
            return {"error": f"image_analysis failed: {str(e)}"}

    @observe(name="pdf-extract-tool")
    async def pdf_extract(self, file_path: str, usage_stats: dict) -> Dict[str, Any]:
        """
        Extract text and metadata from PDF files.

        Args:
            file_path: Path to PDF file
            usage_stats: Current usage statistics

        Returns:
            Dict with extracted content or error
        """
        if not self._check_budget("pdf_extract", usage_stats):
            return {"error": "Tool budget exceeded for pdf_extract"}

        try:
            # Lazy load PDF extractor service
            if self._pdf_extractor is None:
                from app.services.pdf_extractor import PDFExtractorService
                self._pdf_extractor = PDFExtractorService()

            result = await self._pdf_extractor.extract(file_path)
            self._increment_usage("pdf_extract", usage_stats)
            return result

        except Exception as e:
            return {"error": f"pdf_extract failed: {str(e)}"}

    @observe(name="seo-audit-tool")
    async def seo_audit(self, url: str, usage_stats: dict) -> Dict[str, Any]:
        """
        Perform SEO audit of a webpage.

        Args:
            url: URL to audit
            usage_stats: Current usage statistics

        Returns:
            Dict with SEO audit results or error
        """
        if not self._check_budget("seo_audit", usage_stats):
            return {"error": "Tool budget exceeded for seo_audit"}

        try:
            # Lazy load SEO auditor service
            if self._seo_auditor is None:
                from app.services.seo_audit import SEOAuditService
                self._seo_auditor = SEOAuditService()

            result = await self._seo_auditor.audit(url)
            self._increment_usage("seo_audit", usage_stats)
            return result

        except Exception as e:
            return {"error": f"seo_audit failed: {str(e)}"}

    @observe(name="google-maps-scraper-tool")
    async def google_maps_scraper(self, business_name: str, usage_stats: dict) -> Dict[str, Any]:
        """
        Scrape Google Maps for business information.

        Args:
            business_name: Name of business to find
            usage_stats: Current usage statistics

        Returns:
            Dict with business info or error
        """
        if not self._check_budget("google_maps_scraper", usage_stats):
            return {"error": "Tool budget exceeded for google_maps_scraper"}

        try:
            # Lazy load Google Maps scraper service
            if self._maps_scraper is None:
                from app.services.google_maps_scraper import GoogleMapsScraperService
                self._maps_scraper = GoogleMapsScraperService()

            result = await self._maps_scraper.scrape(business_name)
            self._increment_usage("google_maps_scraper", usage_stats)
            return result

        except Exception as e:
            return {"error": f"google_maps_scraper failed: {str(e)}"}

    @observe(name="google-reviews-scraper-tool")
    async def google_reviews_scraper(self, business_name: str, usage_stats: dict) -> Dict[str, Any]:
        """
        Scrape Google reviews for a business.

        Args:
            business_name: Name of business to find reviews for
            usage_stats: Current usage statistics

        Returns:
            Dict with reviews or error
        """
        if not self._check_budget("google_reviews_scraper", usage_stats):
            return {"error": "Tool budget exceeded for google_reviews_scraper"}

        try:
            # Lazy load Google reviews scraper service
            if self._reviews_scraper is None:
                from app.services.google_reviews_scraper import GoogleReviewsScraperService
                self._reviews_scraper = GoogleReviewsScraperService()

            result = await self._reviews_scraper.scrape(business_name)
            self._increment_usage("google_reviews_scraper", usage_stats)
            return result

        except Exception as e:
            return {"error": f"google_reviews_scraper failed: {str(e)}"}

    async def call_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        usage_stats: dict
    ) -> Dict[str, Any]:
        """
        Dynamically call a tool by name.

        Args:
            tool_name: Name of the tool to call
            params: Parameters for the tool
            usage_stats: Current usage statistics

        Returns:
            Tool result dict

        Raises:
            ValueError: If tool_name is not recognized
        """
        tool_methods = {
            "web_fetch": self.web_fetch,
            "web_search": self.web_search,
            "form_detector": self.form_detector,
            "social_media_finder": self.social_media_finder,
            "image_analysis": self.image_analysis,
            "pdf_extract": self.pdf_extract,
            "seo_audit": self.seo_audit,
            "google_maps_scraper": self.google_maps_scraper,
            "google_reviews_scraper": self.google_reviews_scraper,
        }

        if tool_name not in tool_methods:
            return {"error": f"Unknown tool: {tool_name}"}

        method = tool_methods[tool_name]

        # Extract the primary parameter based on tool type
        if tool_name in ["web_fetch", "form_detector", "social_media_finder", "seo_audit"]:
            primary_param = params.get("url", "")
        elif tool_name == "web_search":
            primary_param = params.get("query", "")
        elif tool_name in ["image_analysis", "pdf_extract"]:
            primary_param = params.get("path", params.get("file_path", ""))
        elif tool_name in ["google_maps_scraper", "google_reviews_scraper"]:
            primary_param = params.get("business_name", "")
        else:
            primary_param = ""

        return await method(primary_param, usage_stats)
