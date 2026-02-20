"""
SEOAuditService: Perform basic SEO audit of web pages.
"""
from typing import Dict, Any, List
from langfuse import observe
from bs4 import BeautifulSoup
from app.services.web_scraper import WebScraperService


class SEOAuditService:
    """
    Performs basic SEO audit of web pages.
    Checks meta tags, headings, images, and common SEO issues.
    """

    def __init__(self):
        self.web_scraper = WebScraperService()

    @observe(name="seo-audit")
    async def audit(self, url: str) -> Dict[str, Any]:
        """
        Perform SEO audit on a webpage.

        Args:
            url: URL to audit

        Returns:
            Dict with SEO audit results or error
        """
        # Scrape the page
        scrape_result = await self.web_scraper.scrape_url(url)

        if scrape_result.get("error"):
            return {"error": f"Failed to fetch page: {scrape_result['error']}"}

        html_content = scrape_result.get("html", "")
        if not html_content:
            return {"error": "No HTML content available"}

        # Parse and audit
        soup = BeautifulSoup(html_content, 'html.parser')

        audit_results = {
            "url": url,
            "meta_tags": self._audit_meta_tags(soup),
            "headings": self._audit_headings(soup),
            "images": self._audit_images(soup),
            "links": self._audit_links(soup, url),
            "issues": [],
            "score": 0
        }

        # Calculate issues
        audit_results["issues"] = self._identify_issues(audit_results)

        # Calculate overall score (0-100)
        audit_results["score"] = self._calculate_score(audit_results)

        return audit_results

    def _audit_meta_tags(self, soup) -> Dict[str, Any]:
        """Audit meta tags."""
        title = soup.find('title')
        meta_description = soup.find('meta', attrs={'name': 'description'})
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        og_description = soup.find('meta', attrs={'property': 'og:description'})
        og_image = soup.find('meta', attrs={'property': 'og:image'})

        return {
            'title': title.string if title else None,
            'title_length': len(title.string) if title and title.string else 0,
            'description': meta_description.get('content') if meta_description else None,
            'description_length': len(meta_description.get('content', '')) if meta_description else 0,
            'keywords': meta_keywords.get('content') if meta_keywords else None,
            'has_title': title is not None,
            'has_description': meta_description is not None,
            'has_og_tags': og_title is not None or og_description is not None or og_image is not None
        }

    def _audit_headings(self, soup) -> Dict[str, Any]:
        """Audit heading structure."""
        h1_tags = soup.find_all('h1')
        h2_tags = soup.find_all('h2')
        h3_tags = soup.find_all('h3')

        return {
            'h1_count': len(h1_tags),
            'h1_text': [h1.get_text(strip=True) for h1 in h1_tags],
            'h2_count': len(h2_tags),
            'h3_count': len(h3_tags),
            'has_h1': len(h1_tags) > 0
        }

    def _audit_images(self, soup) -> Dict[str, Any]:
        """Audit images for alt text."""
        images = soup.find_all('img')
        images_without_alt = [img for img in images if not img.get('alt')]

        return {
            'total': len(images),
            'without_alt': len(images_without_alt),
            'alt_percentage': round((len(images) - len(images_without_alt)) / len(images) * 100, 1) if images else 100
        }

    def _audit_links(self, soup, base_url: str) -> Dict[str, Any]:
        """Audit internal and external links."""
        links = soup.find_all('a', href=True)
        internal_links = [
            link['href'] for link in links
            if link['href'].startswith('/') or base_url in link['href']
        ]
        external_links = [
            link['href'] for link in links
            if link['href'].startswith('http') and base_url not in link['href']
        ]

        return {
            'total': len(links),
            'internal': len(internal_links),
            'external': len(external_links)
        }

    def _identify_issues(self, audit_results: Dict[str, Any]) -> List[str]:
        """Identify SEO issues."""
        issues = []

        # Meta tags issues
        meta = audit_results['meta_tags']
        if not meta['has_title']:
            issues.append("Missing page title")
        elif meta['title_length'] < 30 or meta['title_length'] > 60:
            issues.append(f"Title length ({meta['title_length']} chars) not optimal (30-60 chars)")

        if not meta['has_description']:
            issues.append("Missing meta description")
        elif meta['description_length'] < 120 or meta['description_length'] > 160:
            issues.append(f"Description length ({meta['description_length']} chars) not optimal (120-160 chars)")

        if not meta['has_og_tags']:
            issues.append("Missing Open Graph tags (important for social sharing)")

        # Headings issues
        headings = audit_results['headings']
        if headings['h1_count'] == 0:
            issues.append("No H1 heading found")
        elif headings['h1_count'] > 1:
            issues.append(f"Multiple H1 headings found ({headings['h1_count']}) - should have only one")

        # Images issues
        images = audit_results['images']
        if images['total'] > 0 and images['alt_percentage'] < 90:
            issues.append(f"{images['without_alt']} images missing alt text")

        return issues

    def _calculate_score(self, audit_results: Dict[str, Any]) -> int:
        """Calculate overall SEO score (0-100)."""
        score = 100

        # Deduct points for each issue
        score -= len(audit_results['issues']) * 10

        # Bonus for good practices
        if audit_results['meta_tags']['has_og_tags']:
            score += 5
        if audit_results['images']['alt_percentage'] == 100:
            score += 5

        return max(0, min(100, score))  # Clamp between 0-100
