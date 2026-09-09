#!/usr/bin/env python3
"""
Mass Domain & URL Prospect Finder
--------------------------------
Scrapes search engines and web directories by niche + location keywords.
Extracts, cleans, deduplicates, and filters out aggregator/directory domains (Yelp, Facebook, etc.)
Outputs clean lists of potential client websites ready for website_auditor.py.
"""

import os
import re
import sys
import time
import json
import random
import argparse
from urllib.parse import urlparse, parse_qs, unquote
import subprocess

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("[!] Installing missing dependencies (requests, beautifulsoup4)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4"])
    import requests
    from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
]

# Domains to ignore during client lead generation (aggregators, social media, government, major tech platforms)
IGNORED_DOMAINS = {
    "google.com", "google.ca", "google.co.uk", "youtube.com", "facebook.com", "instagram.com",
    "linkedin.com", "twitter.com", "x.com", "yelp.com", "yellowpages.com", "tripadvisor.com",
    "wikipedia.org", "amazon.com", "apple.com", "microsoft.com", "pinterest.com", "reddit.com",
    "mapquest.com", "bbb.org", "angi.com", "thumbtack.com", "homeadvisor.com", "houzz.com",
    "glassdoor.com", "indeed.com", "craigslist.org", "zillow.com", "realtor.com", "expedia.com",
    "booking.com", "bing.com", "duckduckgo.com", "yahoo.com", "baidu.com", "w3.org", "gov",
    "zocdoc.com", "webmd.com", "expertise.com", "homeguide.com", "opencare.com", "tebra.com",
    "bestprosintown.com", "healthgrades.com", "vitals.com", "mapquest.com"
}

class DomainScraper:
    def __init__(self, delay=1.5):
        self.delay = delay
        self.session = requests.Session()

    def get_headers(self):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def is_valid_prospect_domain(self, domain, target_locations=None):
        if not domain or "." not in domain:
            return False, "invalid_domain"
        domain_lower = domain.lower()

        # Rule 4: Reject non-US TLDs (.ca, .uk, .au, .de, .fr, .in, etc.) when target locations are US-based
        non_us_tlds = (".ca", ".uk", ".co.uk", ".au", ".de", ".fr", ".in", ".nz", ".nl", ".br", ".mx", ".za")
        if any(domain_lower.endswith(tld) for tld in non_us_tlds):
            return False, "non-US TLD"

        # Check against blacklist
        for ignored in IGNORED_DOMAINS:
            if domain_lower == ignored or domain_lower.endswith("." + ignored):
                return False, f"blacklisted domain ({ignored})"

        # Filter out file downloads, IPs, and invalid extensions
        if re.search(r'\.(pdf|png|jpg|jpeg|gif|css|js|json|xml|zip|gz)$', domain_lower):
            return False, "file/asset URL"

        return True, "valid"

    def extract_domain_from_url(self, raw_url):
        if not raw_url:
            return None
        
        # Clean DuckDuckGo redirect URLs
        if "/l/?" in raw_url or "duckduckgo.com/l/" in raw_url:
            parsed = parse_qs(urlparse(raw_url).query)
            if "uddg" in parsed:
                raw_url = parsed["uddg"][0]

        # Clean Google redirect URLs
        if "/url?" in raw_url:
            parsed = parse_qs(urlparse(raw_url).query)
            if "q" in parsed:
                raw_url = parsed["q"][0]

        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            raw_url = "https://" + raw_url

        try:
            parsed = urlparse(raw_url)
            netloc = parsed.netloc.lower()
            if ":" in netloc:
                netloc = netloc.split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]
            valid, _ = self.is_valid_prospect_domain(netloc)
            return netloc if valid else None
        except Exception:
            return None

    def verify_site_location(self, domain, target_location):
        """
        Secondary verification: fetches homepage of candidate site and checks for
        address, city, state, or area code matching target_location.
        """
        if not target_location:
            return True, "no target location specified"

        # Extract city and state from target_location string (e.g. "Atlanta GA" -> city="Atlanta", state="GA")
        parts = target_location.strip().split()
        state = parts[-1] if len(parts) > 1 and len(parts[-1]) == 2 else "GA"
        city = " ".join(parts[:-1]) if len(parts) > 1 else parts[0]

        # GA area codes map
        ga_area_codes = {"404", "678", "770", "470", "912", "706", "762", "229", "478"}

        url = f"https://{domain}"
        try:
            resp = self.session.get(url, headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                text = resp.text.lower()
                
                # Check city name
                if city.lower() in text:
                    return True, f"city match ({city})"

                # Check state abbreviation with boundary or word
                if f" {state.lower()} " in text or f", {state.lower()}" in text or f" {state.lower()},":
                    # Check area code if GA
                    if state.upper() == "GA":
                        phone_matches = re.findall(r'\(?(\d{3})\)?[-.\s]?\d{3}[-.\s]?\d{4}', resp.text)
                        if any(ac in ga_area_codes for ac in phone_matches):
                            return True, f"GA area code match ({[ac for ac in phone_matches if ac in ga_area_codes][0]})"
                    return True, f"state match ({state})"

                return False, f"location mismatch (missing {city}/{state} on homepage)"
        except Exception as e:
            # If site timeout/blocked, accept conditionally if domain name carries city hint
            if city.lower().replace(" ", "") in domain.lower() or state.lower() in domain.lower():
                return True, "domain name location match (site unreachable)"
            return False, f"location unverified (site unreachable: {e})"

        return True, "unverified"

    def search_duckduckgo(self, query, max_results=30):
        """Scrapes web search results from DuckDuckGo HTML engine without API limits"""
        domains = set()
        url = "https://html.duckduckgo.com/html/"
        headers = self.get_headers()
        data = {"q": query}

        try:
            resp = self.session.post(url, data=data, headers=headers, timeout=10)
            if resp.status_code == 200:
                raw_urls = re.findall(r'href=["\'](https?://[^"\']+)["\']', resp.text)
                for u in raw_urls:
                    if "duckduckgo.com" in u:
                        match = re.search(r'uddg=(https?://[^&]+)', u)
                        if match:
                            u = requests.utils.unquote(match.group(1))
                    dom = self.extract_domain_from_url(u)
                    if dom:
                        domains.add(dom)
                        if len(domains) >= max_results:
                            break
        except Exception as e:
            print(f"[!] DuckDuckGo query error: {e}")

        return domains

    def search_google_lite(self, query, max_results=30):
        """Scrapes web search results from Google Search HTML endpoint"""
        domains = set()
        headers = self.get_headers()
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=50"

        print(f"[*] Querying Google Search for: '{query}'...")
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                raw_urls = re.findall(r'href=["\'](https?://[^"\']+)["\']', resp.text)
                for u in raw_urls:
                    if "/url?q=" in u:
                        match = re.search(r'/url\?q=(https?://[^&]+)', u)
                        if match:
                            u = match.group(1)
                    dom = self.extract_domain_from_url(u)
                    if dom:
                        domains.add(dom)
                        if len(domains) >= max_results:
                            break
        except Exception as e:
            print(f"[!] Google Search query error: {e}")

        return domains

    def search_osm_nominatim(self, niche, location, max_results=30):
        """Mass pulls real business websites from OpenStreetMap (OSM) Places Directory with structured address filtering"""
        domains = set()
        query_str = f"{niche} in {location}"
        url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(query_str)}&format=json&extratags=1&addressdetails=1&limit=50"
        headers = self.get_headers()

        print(f"[*] Querying OpenStreetMap Directory for: '{query_str}'...")
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                places = resp.json()
                for place in places:
                    if isinstance(place, dict):
                        addr = place.get("address") or {}
                        country_code = addr.get("country_code", "").lower()
                        # Structured address check: reject non-us OSM entries when searching US locations
                        if country_code and country_code != "us":
                            print(f"    [REJECTED] {place.get('display_name','')} -> non-US country code ({country_code})")
                            continue

                        extra = place.get("extratags") or {}
                        if isinstance(extra, dict):
                            website = extra.get("website") or extra.get("contact:website") or extra.get("url")
                            if website:
                                dom = self.extract_domain_from_url(website)
                                if dom:
                                    domains.add(dom)
                                    if len(domains) >= max_results:
                                        break
        except Exception as e:
            print(f"[!] OSM query error: {e}")

        return domains

    def mass_harvest(self, niches, locations, limit_per_query=20):
        all_domains = set()
        rejected_log = []

        print(f"\n=======================================================")
        print(f"[+] Starting Mass Prospect Search with Strict Location Verification")
        print(f"=======================================================\n")

        for niche in niches:
            if locations:
                for loc in locations:
                    print(f"\n--- Searching: {niche} in {loc} ---")
                    raw_candidates = set()

                    # 1. TLD check & basic domain validity
                    osm_res = self.search_osm_nominatim(niche, loc, max_results=limit_per_query)
                    google_res = self.search_google_lite(f"{niche} {loc}", max_results=limit_per_query)
                    ddg_res = self.search_duckduckgo(f"{niche} {loc}", max_results=limit_per_query)

                    found = osm_res.union(google_res).union(ddg_res)

                    for dom in found:
                        valid, reason = self.is_valid_prospect_domain(dom)
                        if not valid:
                            rejected_log.append((dom, loc, reason))
                            print(f"    [REJECTED] {dom} -> {reason}")
                            continue

                        # 2. Secondary website content location verification
                        verified, v_reason = self.verify_site_location(dom, loc)
                        if not verified:
                            rejected_log.append((dom, loc, v_reason))
                            print(f"    [REJECTED] {dom} -> {v_reason}")
                            continue

                        all_domains.add(dom)
                        print(f"    [ACCEPTED] {dom} -> {v_reason}")

                    print(f"    -> Current total verified unique domains: {len(all_domains)}")
                    time.sleep(self.delay)
            else:
                print(f"\n--- Searching: {niche} ---")
                res = self.search_duckduckgo(niche, max_results=limit_per_query)
                google_res = self.search_google_lite(niche, max_results=limit_per_query)
                for dom in res.union(google_res):
                    valid, reason = self.is_valid_prospect_domain(dom)
                    if valid:
                        all_domains.add(dom)
                    else:
                        rejected_log.append((dom, "N/A", reason))

        print(f"\n=======================================================")
        print(f"[SUMMARY] Harvest Complete! Verified {len(all_domains)} domain(s). Rejected {len(rejected_log)} candidate(s).")
        print(f"=======================================================\n")

        return sorted(list(all_domains))


GEORGIA_CITIES = [
    "Atlanta GA", "Savannah GA", "Augusta GA", "Macon GA", "Athens GA",
    "Columbus GA", "Roswell GA", "Sandy Springs GA", "Johns Creek GA", "Alpharetta GA",
    "Marietta GA", "Valdosta GA", "Smyrna GA", "Dunwoody GA", "Gainesville GA"
]

def main():
    parser = argparse.ArgumentParser(description="Mass harvest business website domains for client prospecting.")
    parser.add_argument("--niches", "-n", type=str, help="Comma-separated niches (e.g. 'plumber, dentist, lawyer, roofing')")
    parser.add_argument("--locations", "-l", type=str, help="Comma-separated locations (e.g. 'Atlanta GA, Savannah GA' or 'Georgia')")
    parser.add_argument("--state", type=str, choices=["GA", "georgia"], help="Preset targeting all major Georgia cities")
    parser.add_argument("--locations-file", type=str, help="File containing list of custom locations/cities (one per line)")
    parser.add_argument("--query", "-q", type=str, help="Single raw search query (e.g. 'roofing contractor Atlanta GA')")
    parser.add_argument("--output", "-o", type=str, default="harvested_domains.txt", help="Output txt file for harvested domains")
    parser.add_argument("--limit", "--count", type=int, default=20, help="Max results per search query")
    parser.add_argument("--audit", action="store_true", help="Automatically trigger website_auditor.py after harvesting")

    args = parser.parse_args()

    niches = []
    locations = []

    if args.query:
        niches = [args.query]
    else:
        if args.niches:
            niches = [n.strip() for n in args.niches.split(",") if n.strip()]
        else:
            print("[!] No niches specified. Defaulting to high-value local service niches...")
            niches = ["dentist", "plumber", "roofing contractor", "law firm", "chiropractor"]

        # Parse location options
        if args.state and args.state.lower() in ["ga", "georgia"]:
            locations = GEORGIA_CITIES
            print(f"[+] Using Georgia State Preset ({len(GEORGIA_CITIES)} major GA cities loaded)")
        elif args.locations_file and os.path.exists(args.locations_file):
            with open(args.locations_file, "r", encoding="utf-8") as f:
                locations = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            print(f"[+] Loaded {len(locations)} locations from file: {args.locations_file}")
        elif args.locations:
            if args.locations.lower() in ["ga", "georgia"]:
                locations = GEORGIA_CITIES
                print(f"[+] Using Georgia State Preset ({len(GEORGIA_CITIES)} major GA cities loaded)")
            else:
                locations = [l.strip() for l in args.locations.split(",") if l.strip()]
        else:
            print("[!] No locations specified. Defaulting to Georgia major cities...")
            locations = GEORGIA_CITIES

    scraper = DomainScraper(delay=1.5)
    harvested = scraper.mass_harvest(niches, locations, limit_per_query=args.limit)

    print(f"\n=======================================================")
    print(f"[OK] Harvest Complete! Gathered {len(harvested)} unique prospect website domains.")
    print(f"=======================================================\n")

    # Save to file
    with open(args.output, "w", encoding="utf-8") as f:
        for d in harvested:
            f.write(d + "\n")

    print(f"[+] Saved prospect domain list to: {os.path.abspath(args.output)}")

    # Auto-trigger auditor if requested
    if args.audit and harvested:
        print(f"\n[+] Automatically launching website auditor on {len(harvested)} harvested prospects...")
        cmd = [
            sys.executable, "website_auditor.py",
            "--input", args.output,
            "--csv", "prospect_audit.csv",
            "--html", "prospect_audit.html",
            "--json", "prospect_audit.json"
        ]
        subprocess.run(cmd)

if __name__ == "__main__":
    main()
