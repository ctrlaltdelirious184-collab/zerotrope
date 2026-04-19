import requests
from bs4 import BeautifulSoup
import os
import asyncio
from playwright.sync_api import sync_playwright

class Scraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def scrape_static(self, url):
        """
        Scrapes dynamic Javascript HTML using Playwright.
        (Kept the method name 'scrape_static' for backwards compatibility in other files)
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                # Wait for the DOM, then wait 3 seconds for async JS to finish, rather than waiting for networking to fully close
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
                
                # Get the full raw HTML for programmatic extraction (CTAs)
                raw_html = page.content()
                
                # Get clean, rendered text directly from the browser to avoid hidden/script data
                rendered_text = page.evaluate("document.body.innerText")
                
                title = page.title()
                
                data = {
                    "title": title,
                    "html": raw_html,
                    "text": rendered_text
                }
                browser.close()
            return data
        except Exception as e:
            print(f"Playwright scrape failed for {url}: {e}")
            return None

    def get_screenshot(self, url, output_path):
        """
        Uses Playwright to take a screenshot for vision analysis.
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
                page.screenshot(path=output_path)
                browser.close()
            return True
        except Exception as e:
            print(f"Screenshot failed: {e}")
            return False

# Example test
if __name__ == "__main__":
    scraper = Scraper()
    # print(scraper.scrape_static("https://example.com"))
