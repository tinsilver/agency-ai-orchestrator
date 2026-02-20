"""
SocialMediaFinderService: Find social media accounts linked from websites.
"""
from typing import Dict, Any, Optional
import re
from langfuse import observe
from app.services.web_scraper import WebScraperService


class SocialMediaFinderService:
    """
    Finds social media account links from website HTML.
    Uses regex patterns to extract social media URLs.
    """

    def __init__(self):
        self.web_scraper = WebScraperService()

        # Social media URL patterns
        self.patterns = {
            'facebook': r'(?:https?://)?(?:www\.)?facebook\.com/(?:pages/)?([a-zA-Z0-9\.\-_]+)/?',
            'twitter': r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)/?',
            'instagram': r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9\._]+)/?',
            'linkedin': r'(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/([a-zA-Z0-9\-_]+)/?',
            'youtube': r'(?:https?://)?(?:www\.)?youtube\.com/(?:@|channel/|c/|user/)?([a-zA-Z0-9\-_]+)/?',
            'tiktok': r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9\._]+)/?',
            'pinterest': r'(?:https?://)?(?:www\.)?pinterest\.com/([a-zA-Z0-9_]+)/?',
            'github': r'(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9\-_]+)/?',
        }

    @observe(name="social-media-finder")
    async def find_accounts(self, url: str) -> Dict[str, Any]:
        """
        Find all social media accounts linked from a website.

        Args:
            url: URL to analyze

        Returns:
            Dict with social media accounts or error
        """
        # Scrape the website
        scrape_result = await self.web_scraper.scrape_url(url)

        if scrape_result.get("error"):
            return {"error": f"Failed to fetch page: {scrape_result['error']}"}

        html_content = scrape_result.get("html", "")
        if not html_content:
            return {"error": "No HTML content available"}

        # Extract social media links
        accounts = self._extract_social_media(html_content)

        # Calculate confidence based on how many platforms found
        platforms_found = sum(1 for v in accounts.values() if v is not None)
        confidence = min(platforms_found / 4.0, 1.0)  # Normalize to max of 4 platforms

        return {
            "url": url,
            "accounts": accounts,
            "platforms_found": platforms_found,
            "confidence": round(confidence, 2)
        }

    def _extract_social_media(self, html: str) -> Dict[str, Optional[str]]:
        """
        Extract social media URLs from HTML content.

        Args:
            html: HTML content to search

        Returns:
            Dict mapping platform names to URLs (or None if not found)
        """
        accounts = {}

        for platform, pattern in self.patterns.items():
            matches = re.findall(pattern, html, re.IGNORECASE)

            if matches:
                # Get the first match and construct full URL
                username = matches[0]

                # Construct full URL based on platform
                if platform == 'facebook':
                    full_url = f"https://www.facebook.com/{username}"
                elif platform == 'twitter':
                    full_url = f"https://twitter.com/{username}"
                elif platform == 'instagram':
                    full_url = f"https://www.instagram.com/{username}"
                elif platform == 'linkedin':
                    # Check if it's a company or person
                    if '/company/' in html:
                        full_url = f"https://www.linkedin.com/company/{username}"
                    else:
                        full_url = f"https://www.linkedin.com/in/{username}"
                elif platform == 'youtube':
                    full_url = f"https://www.youtube.com/{username}"
                elif platform == 'tiktok':
                    full_url = f"https://www.tiktok.com/@{username}"
                elif platform == 'pinterest':
                    full_url = f"https://www.pinterest.com/{username}"
                elif platform == 'github':
                    full_url = f"https://github.com/{username}"
                else:
                    full_url = None

                accounts[platform] = full_url
            else:
                accounts[platform] = None

        return accounts

    def format_for_display(self, accounts: Dict[str, Optional[str]]) -> str:
        """
        Format social media accounts for human-readable display.

        Args:
            accounts: Dict of platform -> URL

        Returns:
            Formatted string
        """
        found = [f"{platform.capitalize()}: {url}" for platform, url in accounts.items() if url]

        if not found:
            return "No social media accounts found"

        return "\n".join(found)
