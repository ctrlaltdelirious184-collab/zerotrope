from utils.scraper import Scraper
import os
from urllib.parse import urljoin, urlparse

class ResearchAgent:
    def __init__(self):
        self.scraper = Scraper()

    def _extract_links_from_homepage(self, base_url, scraped_data):
        """
        Extracts all internal links from the homepage HTML to find actual page URLs.
        Works for any CMS including Wix, Squarespace, Webflow with custom slugs.
        """
        import re
        from urllib.parse import urljoin, urlparse

        links = set()
        base_domain = urlparse(base_url).netloc

        # Try to get raw HTML if available
        html = scraped_data.get("html", "") or scraped_data.get("text", "")

        # Extract href links
        href_pattern = re.compile(r'href=["\'"]([^"\'"]+)["\'"]')
        for match in href_pattern.findall(html):
            href = match.strip()
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            # Only keep internal links
            if parsed.netloc == base_domain and parsed.path and parsed.path != "/":
                links.add(full_url.split("?")[0].split("#")[0])

        return list(links)[:20]  # Cap at 20 to avoid crawling the entire site

    def _find_key_pages(self, base_url, scraped_data):
        """
        Crawls actual links found on the homepage first, then falls back to common slugs.
        Works for any CMS including Wix, Squarespace, Webflow with custom page slugs.
        """
        found_pages = {}

        # Step 1 — Extract real links from homepage
        real_links = self._extract_links_from_homepage(base_url, scraped_data)
        print(f"[Research] Found {len(real_links)} internal links on homepage")

        for url in real_links:
            try:
                scraped = self.scraper.scrape_static(url)
                if scraped and scraped.get("text") and len(scraped.get("text", "")) > 200:
                    slug = url.replace(base_url.rstrip("/"), "").strip("/") or url
                    found_pages[slug] = scraped.get("text", "")[:1500]
                    print(f"[Research] Crawled: {slug}")
            except Exception:
                pass

        # Step 2 — Also try common slugs as fallback for sites with minimal homepage links
        key_slugs = [
            "about", "about-us", "services", "our-services",
            "testimonials", "reviews", "success-stories",
            "gallery", "before-after", "results", "portfolio",
            "pricing", "cost", "fees", "rates", "packages",
            "shop", "store", "products", "courses", "programs",
            "speaking", "coaching", "contact", "contact-us", "faq",
        ]

        base = base_url.rstrip("/")
        for slug in key_slugs:
            url = f"{base}/{slug}"
            if url in real_links:
                continue  # Already crawled
            try:
                scraped = self.scraper.scrape_static(url)
                if scraped and scraped.get("text") and len(scraped.get("text", "")) > 200:
                    found_pages[slug] = scraped.get("text", "")[:1500]
                    print(f"[Research] Found fallback subpage: /{slug}")
            except Exception:
                pass

        return found_pages

    def run(self, input_data):
        """
        Input: URL or text description
        Output: Dictionary of researched facts including key subpages
        """
        results = {
            "source": input_data,
            "type": "text",
            "raw_data": {},
            "subpages": {}
        }

        if input_data.startswith("http"):
            results["type"] = "url"
            print(f"[Research] Scraping homepage: {input_data}...")
            scraped = self.scraper.scrape_static(input_data)
            if scraped:
                results["raw_data"] = scraped

            # Crawl key subpages
            print(f"[Research] Scanning subpages...")
            subpages = self._find_key_pages(input_data, scraped if scraped else {})
            results["subpages"] = subpages
            print(f"[Research] Found {len(subpages)} subpages: {list(subpages.keys())}")

            # Take screenshot for vision agent
            screenshot_path = os.path.join(os.getcwd(), "temp_homepage.png")
            if self.scraper.get_screenshot(input_data, screenshot_path):
                results["screenshot_path"] = screenshot_path
        else:
            print("[Research] Processing text description...")
            results["raw_data"] = {"text": input_data}

        return results