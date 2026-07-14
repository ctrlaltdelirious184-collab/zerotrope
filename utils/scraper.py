import requests
from bs4 import BeautifulSoup
import os
import asyncio
import threading
import time
from playwright.sync_api import sync_playwright

# Global concurrency lock to prevent launching multiple Chromium instances simultaneously
# This prevents RAM exhaustion (Out-Of-Memory) on Render free tier.
browser_lock = threading.Lock()

class Scraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def scrape_static(self, url):
        """
        Scrapes a target website. First attempts a lightweight requests/bs4 scrape (low RAM, fast).
        Falls back to Playwright Chromium ONLY when page is dynamic/empty, utilizing a global lock
        and memory optimization flags.
        """
        # Step 1: Lightweight static scrape first
        try:
            print(f"[Scraper] Attempting fast static scrape for: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                
                # Strip out script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                text = soup.get_text(separator="\n")
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                clean_text = "\n".join(chunk for chunk in chunks if chunk)
                
                # If we successfully parsed >1500 chars, it's a solid content site; return immediately
                if len(clean_text) > 1500:
                    print(f"[Scraper] Fast static parse succeeded ({len(clean_text)} chars). Skipping Playwright.")
                    return {
                        "title": soup.title.string.strip() if soup.title else url,
                        "html": response.text,
                        "text": clean_text
                    }
                else:
                    print(f"[Scraper] Fast static parse yielded too little text ({len(clean_text)} chars). Falling back to Playwright.")
        except Exception as e:
            print(f"[Scraper] Fast static parse failed: {e}. Falling back to Playwright.")

        # Step 2: Fallback to Playwright with global concurrency lock & memory optimizations
        print(f"[Scraper] Acquiring global Chromium lock for: {url}...")
        acquired = browser_lock.acquire(timeout=15)
        if not acquired:
            print(f"[Scraper] Timeout waiting for browser lock on: {url}. Rejecting execution.")
            return None

        try:
            with sync_playwright() as p:
                # Optimized launch flags to minimize memory footprint on Render
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--single-process",
                        "--disable-extensions",
                        "--no-first-run",
                        "--no-default-browser-check"
                    ]
                )
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
                
                raw_html = page.content()
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
        finally:
            browser_lock.release()
            print("[Scraper] Released Chromium lock.")

    def get_screenshot(self, url, output_path):
        """
        Uses Playwright to take a screenshot for vision analysis (with global concurrency lock).
        """
        acquired = browser_lock.acquire(timeout=15)
        if not acquired:
            print(f"[Scraper] Timeout waiting for browser lock to take screenshot of: {url}")
            return False

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--single-process"
                    ]
                )
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
                page.screenshot(path=output_path)
                browser.close()
            return True
        except Exception as e:
            print(f"Screenshot failed: {e}")
            return False
        finally:
            browser_lock.release()

if __name__ == "__main__":
    scraper = Scraper()

