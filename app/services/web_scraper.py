import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List
from langfuse import observe
from app.utils import ensure_url_with_protocol

class WebScraperService:
    """Service to fetch and parse website content for AI context."""

    def __init__(self):
        self.headers = {
            "User-Agent": "AgencyAI/1.0 (Testing from theoruby.com)"
        }

    @observe(name="web-scraper")
    async def scrape_url(self, url: str) -> Dict[str, Any]:
        """
        Fetches URL and returns structured content summary.
        Includes title, meta description, and simplified structural outline.
        """
        # Ensure URL has protocol (handles both "example.com" and "https://example.com")
        url = ensure_url_with_protocol(url)

        try:
            async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=15.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                html = response.text

            return self._parse_html(html, url)

        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return {"error": str(e), "url": url}

    def _parse_html(self, html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        # 1. Basic Metadata
        title = soup.title.string.strip() if soup.title else "No Title"
        
        meta = soup.find("meta", attrs={"name": "description"})
        description = meta["content"].strip() if meta else "No description"

        # 2. Extract Structure (Headings & Navigation)
        structure = []
        
        # Navigation
        navs = soup.find_all("nav")
        for i, nav in enumerate(navs):
            links = [a.get_text(strip=True) for a in nav.find_all("a")]
            if links:
                structure.append(f"Navigation Block {i+1}: {', '.join(links[:10])}")

        # Main Content Areas (Headings)
        for tag in soup.find_all(['h1', 'h2', 'h3']):
            text = tag.get_text(strip=True)
            if text:
                level = tag.name.upper()
                structure.append(f"[{level}] {text}")

        # 3. Detect Key Sections (Hero, Footer, etc via class/id heuristics)
        sections = []
        for tag in soup.find_all(['div', 'section', 'header', 'footer']):
            cls_id = str(tag.get('class', [])) + str(tag.get('id', ''))
            cls_id = cls_id.lower()
            
            if 'hero' in cls_id:
                sections.append("Found Hero Section")
            if 'footer' in cls_id:
                sections.append("Found Footer")
            if 'contact' in cls_id:
                sections.append("Found Contact Section")
        
        return {
            "url": url,
            "title": title,
            "description": description,
            "structure_summary": "\n".join(structure[:50]), # Limit length
            "detected_sections": list(set(sections)),
            "full_text": soup.get_text(separator="\n", strip=True)[:5000] # Truncate large pages
        }
