import asyncio
from app.services.web_scraper import WebScraperService

async def test_scraper():
    print("--- 🕷️ Testing Web Scraper ---")
    
    # Test with a real site (example.com is safe and stable)
    url = "example.com"
    scraper = WebScraperService()
    
    print(f"Scraping {url}...")
    result = await scraper.scrape_url(url)
    
    if result.get("error"):
        print(f"❌ Failed: {result['error']}")
    else:
        print("✅ Success!")
        print(f"Title: {result['title']}")
        print(f"Structure Summary:\n{result['structure_summary']}")
        print(f"Detected Sections: {result['detected_sections']}")
        print(f"Text Preview: {result['full_text'][:200]}...")

if __name__ == "__main__":
    asyncio.run(test_scraper())
