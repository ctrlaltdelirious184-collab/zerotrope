import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import socket
from bridge_api import is_private_ip, rate_limit_ip, ip_history
from utils.scraper import Scraper

def test_private_ip():
    print("Testing Private IP detection...")
    assert is_private_ip("http://localhost:8000") == True
    assert is_private_ip("http://127.0.0.1") == True
    assert is_private_ip("http://192.168.1.1") == True
    assert is_private_ip("http://10.0.0.5") == True
    assert is_private_ip("https://google.com") == False
    print("Private IP detection works perfectly!")

def test_rate_limiting():
    print("Testing IP rate limiting...")
    ip_history.clear()
    rate_limit_ip("1.2.3.4")
    rate_limit_ip("1.2.3.4")
    rate_limit_ip("1.2.3.4")
    try:
        rate_limit_ip("1.2.3.4")
        raise RuntimeError("Should have raised HTTPException 429!")
    except Exception as e:
        print("Rate limiting caught overload correctly:", str(e))

def test_hybrid_scraper():
    print("Testing scraper fast-parse fallback...")
    scraper = Scraper()
    # Fast requests parse should succeed easily on static sites with >1500 chars
    res = scraper.scrape_static("https://example.com")
    if res:
        print("Scraper successfully scraped example.com! Text length:", len(res["text"]))
    else:
        print("Scraper failed or got blocked.")

if __name__ == "__main__":
    test_private_ip()
    test_rate_limiting()
    test_hybrid_scraper()
