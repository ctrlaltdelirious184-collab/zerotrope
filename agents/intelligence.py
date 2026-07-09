import json
import os
from utils.ai_client import AIClient

class IntelligenceAgent:
    def __init__(self, memory_file="knowledge/agency_memory.json"):
        self.client = AIClient()
        self.memory_file = memory_file

    def run(self, research_data):
        print("[Intelligence] Pass 1 — Gap Discovery...")

        # Load memory
        agency_memory = "No previous memory."
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r") as f:
                    memories = json.load(f)
                    if memories:
                        agency_memory = json.dumps(memories[-3:], indent=2)
            except Exception:
                pass

        raw_data = research_data.get("raw_data", {})
        homepage_text = raw_data.get("text", "")[:4000]
        raw_title = raw_data.get("title", "")
        # Clean the title tag — strip SEO suffixes after | or –
        import re as _re
        clean_title = _re.split(r'[|\-–—]', raw_title)[0].strip() if raw_title else ""
        # Also reject single generic words like "Online", "Home", "Welcome"
        generic_words = {"online", "home", "welcome", "index", "homepage", "website", "site"}
        if clean_title.lower() in generic_words:
            clean_title = ""
        if clean_title:
            homepage_text += f"\nPage title (cleaned): {clean_title}"
        elif raw_title:
            homepage_text += f"\nRaw page title: {raw_title}"

        subpages = research_data.get("subpages", {})
        subpage_context = ""
        if subpages:
            subpage_context = "\n\nCONFIRMED SUBPAGES (these pages exist and were scraped):\n"
            for slug, text in subpages.items():
                subpage_context += f"\n--- PAGE: /{slug} ---\n{text[:800]}\n"
        else:
            subpage_context = "\n\nNo subpages found. Analysis is homepage only."

        # ─────────────────────────────────────────
        # PRE-PASS — PYTHON EXTRACTION (hard facts, not AI guesses)
        # ─────────────────────────────────────────
        import re

        # Extract CTAs programmatically from raw HTML if available
        raw_html = raw_data.get("html", "") or homepage_text
        
        # Find all link/button text patterns
        cta_patterns = [
            r'(?:href|onclick)[^>]*>[\s]*([^<]{3,60})[\s]*<',
            r'(?:btn|button|cta)[^>]*>[\s]*([^<]{3,60})[\s]*<',
        ]
        found_ctas = set()
        for pattern in cta_patterns:
            for match in re.findall(pattern, raw_html, re.IGNORECASE):
                clean = match.strip()
                if clean and len(clean) > 2 and len(clean) < 80:
                    found_ctas.add(clean)

        # Filter out accessibility/navigation non-CTAs
        accessibility_noise = [
            "skip to", "skip to main", "skip to content", "skip navigation",
            "back to top", "close menu", "open menu", "toggle menu",
            "search", "menu", "home", "next", "previous", "more"
        ]

        # Also extract from text - look for imperative phrases
        cta_keywords = ["join", "book", "get started", "sign up", "register", "download",
                       "subscribe", "learn more", "contact", "schedule", "apply", "start",
                       "discover", "explore", "try", "buy", "shop", "hire", "work with",
                       "connect", "let's", "free", "get your", "claim"]
        text_ctas = []
        for line in homepage_text.split("\n"):
            line_clean = line.strip()
            if not line_clean:
                continue
            # Skip accessibility elements
            if any(noise in line_clean.lower() for noise in accessibility_noise):
                continue
            if any(kw in line_clean.lower() for kw in cta_keywords) and len(line_clean) < 100:
                text_ctas.append(line_clean)

        # Filter found_ctas too
        filtered_ctas = [c for c in found_ctas if not any(noise in c.lower() for noise in accessibility_noise)]
        all_ctas = list(filtered_ctas) + text_ctas[:10]
        
        # Check for actual pricing — requires dollar amounts, not just the word "pricing"
        import re as re2
        all_text = homepage_text + subpage_context
        dollar_amounts = re2.findall(r'\$\d+', all_text)
        pricing_found = len(dollar_amounts) > 0
        pricing_on_homepage = len(re2.findall(r'\$\d+', homepage_text)) > 0
        
        # Detect ordering/menu CTAs — these prove pricing exists behind JS (Square, Toast, etc.)
        ordering_keywords = ["order now", "order online", "order here", "view menu", "see menu",
                            "online ordering", "doordash", "ubereats", "grubhub", "toast", "square",
                            "book now", "book online", "schedule", "reserve", "make a reservation",
                            "buy now", "add to cart", "shop now"]
        has_ordering_cta = any(kw in all_text.lower() for kw in ordering_keywords)
        
        # Check for testimonials
        testimonial_keywords = ["testimonial", "review", "said", "quote", "worked with", "client story", "success story", "★", "⭐", "5 star"]
        testimonials_found = any(kw in (homepage_text + subpage_context).lower() for kw in testimonial_keywords)

        homepage_dollar_amounts = re2.findall(r"\$\d+", homepage_text)
        
        # Build hard facts summary for the AI
        # Check for external redirects used as CTAs (bit.ly, tinyurl etc)
        external_redirects = re2.findall(r'bit[.]ly/\S+|tinyurl[.]com/\S+|goo[.]gl/\S+|ow[.]ly/\S+', homepage_text)
        
        # Determine pricing verdict with business-type awareness
        if pricing_on_homepage:
            pricing_verdict = "NOT a gap — pricing visible on homepage"
        elif pricing_found:
            pricing_verdict = "NOT a gap — pricing exists on subpages, which is completely normal"
        elif has_ordering_cta:
            pricing_verdict = "NOT a gap — ordering/booking CTAs found, pricing lives inside the ordering system (this is standard for restaurants, salons, etc.)"
        else:
            pricing_verdict = "POTENTIAL GAP — no pricing found anywhere, but ONLY flag this for businesses that sell fixed-price products/services (SaaS, ecommerce). Do NOT flag for restaurants, salons, coaches, speakers, or service businesses."

        # ─────────────────────────────────────────
        # GEO VISIBILITY CHECK — only if business has a local presence
        # ─────────────────────────────────────────
        geo_fact = ""
        try:
            # Extract city/state from the scraped text
            city_state_pattern = re2.search(
                r'\b([A-Z][a-zA-Z\s]+),\s*([A-Z]{2})\b',
                all_text
            )
            zip_pattern = re2.search(r'\b\d{5}(?:-\d{4})?\b', all_text)
            location_found = city_state_pattern is not None or zip_pattern is not None

            if location_found and city_state_pattern:
                city = city_state_pattern.group(1).strip()
                state = city_state_pattern.group(2).strip()
                location_str = f"{city}, {state}"
            elif location_found and zip_pattern:
                location_str = zip_pattern.group(0)
            else:
                location_str = None

            if location_str:
                # We have a location — run the GEO search
                source_url = research_data.get("source", "")
                source_domain = ""
                if source_url.startswith("http"):
                    from urllib.parse import urlparse as _urlparse
                    source_domain = _urlparse(source_url).netloc.replace("www.", "")

                # We'll pass location + domain to the AI for it to derive business type,
                # then do the search ourselves
                print(f"[Intelligence] GEO check — location detected: {location_str}")

                from ddgs import DDGS
                # We don't know the business type yet (that comes from AI Pass 1),
                # so search by domain/brand as a proxy
                domain_keyword = source_domain.split(".")[0].replace("-", " ") if source_domain else ""
                search_query = f"{domain_keyword} {location_str}"
                broader_query = f"best restaurant {location_str}" if "taste" in domain_keyword.lower() or "food" in domain_keyword.lower() or "eat" in domain_keyword.lower() else f"best {domain_keyword.split()[0] if domain_keyword else 'business'} {location_str}"

                with DDGS() as ddgs:
                    results = list(ddgs.text(broader_query, max_results=8))

                # Check if business domain appears in any result
                appeared = any(
                    source_domain in (r.get("href", "") + r.get("title", "")).lower()
                    for r in results
                ) if source_domain else False

                top_results_preview = "; ".join(
                    [f"\"{r.get('title', '')}\"" for r in results[:5]]
                )

                if appeared:
                    geo_fact = f"\n- GEO VISIBILITY SEARCH: Ran '{broader_query}' — business DOES appear in top results. Visibility is NOT a gap."
                else:
                    geo_fact = (
                        f"\n- GEO VISIBILITY SEARCH: Ran '{broader_query}' — business is NOT found in top results."
                        f"\n- Top results were: {top_results_preview}"
                        f"\n- GEO VERDICT: CONFIRMED GAP — this business is invisible to AI-driven 'near me' searches. "
                        f"This is high-priority evidence. Use this as the primary gap if no stronger gap exists."
                    )
                print(f"[Intelligence] GEO check complete — appeared: {appeared}")
            else:
                geo_fact = "\n- GEO VISIBILITY SEARCH: Skipped — no physical location detected (likely national/remote business)."
                print("[Intelligence] GEO check skipped — no location found.")
        except Exception as geo_err:
            geo_fact = f"\n- GEO VISIBILITY SEARCH: Could not complete ({geo_err})."
            print(f"[Intelligence] GEO check error: {geo_err}")

        hard_facts = f"""
HARD FACTS (extracted programmatically — these are definitive):
- CTAs found on site: {", ".join(all_ctas[:15]) if all_ctas else "NONE FOUND"}
- Dollar amounts found on HOMEPAGE: {"YES — " + ", ".join(homepage_dollar_amounts[:5]) if pricing_on_homepage else "NO"}
- Dollar amounts found on scraped SUBPAGES: {"YES — " + ", ".join(dollar_amounts[:5]) if pricing_found else "NO"}
- Ordering/booking CTAs detected: {"YES — " + ", ".join([kw for kw in ordering_keywords if kw in all_text.lower()][:5]) if has_ordering_cta else "NO"}
- PRICING GAP VERDICT: {pricing_verdict}
- RULE: Never flag pricing as a gap if ordering CTAs (Order Now, Book Now, etc.) exist — pricing is inside the ordering system and our scraper cannot see JavaScript-rendered content.
- RULE: Never flag pricing for restaurants, salons, coaches, or personal brands. These businesses price through ordering systems or after consultation.
- Testimonials found: {"YES" if testimonials_found else "NO"}
- External redirect links (bit.ly/tinyurl) used as CTAs: {"YES — " + ", ".join(external_redirects[:3]) + " — this is a trust/conversion red flag" if external_redirects else "NO"}{geo_fact}
"""


        # ─────────────────────────────────────────
        # PYTHON NAME EXTRACTION — runs before AI, overrides LLC names
        # ─────────────────────────────────────────
        import re as re3
        from urllib.parse import urlparse as _urlparse

        # Extract domain-based fallback name
        source_url = research_data.get("source", "")
        domain_name = ""
        if source_url.startswith("http"):
            domain_name = _urlparse(source_url).netloc.replace("www.", "").split(".")[0].replace("-", " ").title()

        # Try to get name from title tag (cleaned)
        title_name = clean_title if clean_title and clean_title.lower() not in {"online", "home", "welcome", "index"} else ""

        # Extract from H1 tags in homepage text
        h1_matches = re3.findall(r'[#]+[ ]+(.+)', homepage_text)
        h1_name = ""
        for h1 in h1_matches[:3]:
            h1_clean = h1.strip()
            # Skip generic h1s
            if len(h1_clean) < 60 and not any(skip in h1_clean.lower() for skip in ["crown", "celebrate", "welcome", "we are", "we help", "about"]):
                h1_name = h1_clean
                break

        # Check for LLC/Inc/Corp in title — if found, prefer domain name
        llc_pattern = re3.compile(r'(llc|inc|corp|ltd|co\.)', re3.IGNORECASE)
        if llc_pattern.search(title_name):
            title_name = ""

        # Best python-extracted name
        python_name = title_name or h1_name or domain_name or ""

        # Inject into context so AI knows the correct name
        name_hint = f"\n\nPYTHON-EXTRACTED BUSINESS NAME (use this, do not use LLC names from footer): {python_name}" if python_name else ""

        full_data = f"HOMEPAGE:\n{homepage_text}\n{subpage_context}\n{hard_facts}{name_hint}"

        # ─────────────────────────────────────────
        # PASS 1 — EVIDENCE-BASED GAP DISCOVERY
        # ─────────────────────────────────────────
        pass1_prompt = f"""
You are a website analyst. Your ONLY job is to find gaps that are DIRECTLY PROVABLE from the website data below.

WEBSITE DATA (this is everything you are allowed to base findings on):
{full_data}

NOTE: The HARD FACTS section above was extracted programmatically and is definitive. If CTAs are listed there, do NOT flag CTAs as missing or generic. If pricing is marked YES, do NOT flag pricing as missing.

STRICT RULES FOR PASS 1:
- You may ONLY report a gap if you can quote or directly reference specific text/content from the data above that proves it
- NEVER invent or assume anything not shown in the data
- NEVER report a gap based on what you expect to see — only what the data actually shows
- NEVER flag "Skip to Main Content", "Skip Navigation", or any accessibility/screen-reader element as a CTA
- Accessibility links are present on every website and are NOT real CTAs — ignore them completely
- CRITICAL: Never claim something (like pricing or CTAs) is "missing from the entire site" or "nowhere on any subpages". You can only say it is missing from the HOMEPAGE. Scraping doesn't see Javascript shops, so if you claim pricing is gone site-wide, you will look foolish.
- If CTAs exist in the data, do NOT flag CTAs as missing
- If testimonials exist in the data, do NOT flag testimonials as missing  
- If pricing exists anywhere in the data, do NOT flag pricing as missing
- If something exists on a subpage, it is NOT missing — it may be a prominence issue

For each gap you find, you MUST provide the exact quote or data point that proves it.

Check these dimensions ONLY using the actual data:

1. TITLE/IDENTITY: Does the page title tag actually match what the business does? If the title says something generic or unrelated to the business (e.g. a bakery whose title tag says "Home | My Website"), this is a CRITICAL search/identity gap. The title tag is what Google and AI search engines use to understand the business.
2. HOMEPAGE HERO: What does the hero section actually say? Is the main CTA above the fold specific or generic?
3. PRICING ACCESSIBILITY: Is pricing shown anywhere? If ordering CTAs exist (Order Now, Book Now, etc.), pricing is behind the ordering system and is NOT a gap. Only flag pricing if completely absent AND the business sells fixed-price products (SaaS, ecommerce). NEVER flag for restaurants, salons, coaches, or service businesses.
4. TRUST SIGNALS: Are testimonials, reviews, case studies visible? Where exactly?
5. AI/SEARCH VISIBILITY: Is the business described as a named entity with specific expertise, or just generic keywords?
6. MESSAGING: Does the headline copy use generic phrases that could apply to any competitor?
7. EXTERNAL REDIRECTS: Does the site use bit.ly or similar redirect links as CTAs instead of proper landing pages? (check HARD FACTS)

Output a JSON array. Each item MUST have direct evidence from the data:
[
  {{
    "gap": "One specific, concrete gap description",
    "direct_quote": "The EXACT text from the website data that proves this gap — must be a real quote",
    "where_found": "homepage hero / homepage body / subpage /slug / not found anywhere",
    "confidence": "high | medium",
    "dimension": "hero | pricing | trust | search | messaging"
  }}
]

If you cannot find direct evidence for a gap, DO NOT include it.
Output ONLY the JSON array. No preamble. No explanation.
"""

        print("[Intelligence] Running Pass 1...")
        raw_pass1 = self.client.chat(pass1_prompt, system="You are a factual website analyst. Output ONLY valid JSON. Never invent findings.")

        try:
            # Clean common JSON issues
            raw_pass1 = raw_pass1.strip()
            if raw_pass1.startswith("```"):
                raw_pass1 = raw_pass1.split("```")[1]
                if raw_pass1.startswith("json"):
                    raw_pass1 = raw_pass1[4:]
            gaps = json.loads(raw_pass1.strip())
        except Exception:
            gaps = []

        print(f"[Intelligence] Pass 1 found {len(gaps)} candidate gaps.")

        # ─────────────────────────────────────────
        # PASS 2 — STRICT EVIDENCE VALIDATION
        # ─────────────────────────────────────────
        print("[Intelligence] Pass 2 — Validating gaps against raw data...")

        pass2_prompt = f"""
You are a fact-checker validating gap findings against raw website data.

RAW WEBSITE DATA (ground truth — this is all that exists):
{full_data}

CRITICAL: The HARD FACTS section above is programmatically extracted and overrides any AI interpretation. If specific CTAs are listed, the CTA gap MUST be discarded.

GAPS TO VALIDATE:
{json.dumps(gaps, indent=2)}

YOUR JOB: For each gap, verify it against the ground truth data above.

DISCARD a gap if ANY of these are true:
1. The "direct_quote" is not actually found verbatim (or near-verbatim) in the raw data above
2. The gap claims something is MISSING but it actually EXISTS anywhere in the raw data
3. The gap claims a CTA is generic/missing but specific CTAs exist in the data
4. The gap claims no testimonials but testimonials appear anywhere in the data
5. The gap claims no pricing but pricing appears on any subpage in the data
6. The confidence is "low"
7. The gap is vague and cannot be immediately verified by reading the site

KEEP a gap only if:
- The direct quote actually appears in the raw data above
- The gap is specific enough that the business owner could verify it in 10 seconds
- It represents a REAL conversion or visibility problem

After validation, RANK surviving gaps by business impact and select the highest-ranked one:
1. EXTERNAL REDIRECTS — using bit.ly, tinyurl, or external links as primary CTAs (CRITICAL trust gap)
2. GEO INVISIBILITY — confirmed by real search: business not found when searching '[type] in [city]'. This is the highest-impact gap for local businesses because it means active buyers can't find them.
3. PRICING INVISIBILITY — no dollar amounts ANYWHERE, and business type requires upfront pricing.
4. TRUST DEFICIT — no testimonials or named results visible on homepage
5. MESSAGING GENERICNESS — tagline/copy applies to any competitor
6. HERO VAGUENESS — headline vague (LOWEST priority — only if nothing else found)

CRITICAL RULES FOR SELECTION:
- Taglines like "CROWN, CELEBRATE, COLLABORATE AND CONNECT" are MESSAGING issues, not CTA gaps
- A CTA gap only counts if there is NO action button anywhere above the fold
- If booking links or contact forms exist anywhere, do NOT flag missing CTA
- DO NOT default to hero/CTA gaps when pricing or trust gaps exist

Also extract:
- Clean business name: use the logo text, H1, or prominent brand name shown on the site. 
  NEVER use LLC/Inc/Corp company legal names from copyright footers.
  NEVER use generic words like "Online", "Home", "Welcome".
  If the site is a personal brand, use the person's name (e.g. "Jerusher Wiggins") not their LLC name.
  Priority: Logo text > H1 headline > Prominent brand name > Domain name
- What type of business this is (so we use correct terminology: client/customer/student/patient etc.)
- The founder/owner name if mentioned

Output ONLY this JSON:
{{
    "business_name": "Clean brand name only",
    "business_type": "Brief description e.g. business coach, orthodontist, restaurant",
    "terminology": "client | customer | patient | student | guest | audience member",
    "owner_name": "First name of founder/owner if found, else empty string",
    "primary_gap": "The single most defensible gap, written as a plain factual observation. If something exists but is buried, say so explicitly.",
    "gap_evidence": "The exact quote from the site data that proves this gap",
    "gap_location": "Where on the site this gap was found",
    "gap_dimension": "hero | pricing | trust | search | messaging",
    "no_gap_found": false,
    "contrarian_usp": "The specific positioning angle this business could own based on what IS strong about their site",
    "tropes": ["generic phrase 1 actually found on site", "generic phrase 2", "generic phrase 3"],
    "skepticism": "What this type of business owner's clients are actually afraid of",
    "competitor_insight": "A specific observation about rivals in this niche — for report only"
}}

If NO defensible gap passes validation, set "no_gap_found": true and "primary_gap": "No significant gap found."
Output ONLY the JSON. No preamble.
"""

        print("[Intelligence] Running Pass 2...")
        raw_pass2 = self.client.chat(pass2_prompt, system="You are a strict fact-checker. Output ONLY valid JSON. Discard any finding not directly supported by the raw data.")

        try:
            raw_pass2 = raw_pass2.strip()
            if raw_pass2.startswith("```"):
                raw_pass2 = raw_pass2.split("```")[1]
                if raw_pass2.startswith("json"):
                    raw_pass2 = raw_pass2[4:]
            intel_data = json.loads(raw_pass2.strip())
        except Exception:
            intel_data = {
                "business_name": raw_title.split("|")[0].strip() if raw_title else "",
                "business_type": "business",
                "terminology": "client",
                "owner_name": "",
                "primary_gap": "No significant gap could be verified from the available data.",
                "gap_evidence": "",
                "gap_location": "",
                "gap_dimension": "",
                "no_gap_found": True,
                "contrarian_usp": "A data-driven, transparent approach",
                "tropes": [],
                "skepticism": "Worried about results and ROI",
                "competitor_insight": "Most rivals use generic messaging"
            }

        # Reject LLC/Inc/Corp names from footer — override with python-extracted name
        llc_check = re3.compile(r'(?i)(llc|inc|corp|ltd|co[.])')
        current_name = intel_data.get("business_name", "")

        placeholder_phrases = ["no brand", "brand name", "not provided", "unknown", "n/a", "none", "company name"]
        name_is_bad = (
            not current_name
            or len(current_name.strip()) < 2
            or llc_check.search(current_name)
            or any(p in current_name.lower() for p in placeholder_phrases)
        )

        if name_is_bad:
            intel_data["business_name"] = python_name or current_name.split("|")[0].strip() or "this business"

        # Inject GEO metadata for bridge_api to use in narrative
        intel_data["_geo_fact"] = geo_fact
        # Extract the search query from geo_fact for use in the narrative
        geo_query_match = re2.search(r"Ran '([^']+)'", geo_fact)
        intel_data["_geo_query"] = geo_query_match.group(1) if geo_query_match else ""
        intel_data["_geo_appeared"] = "DOES appear" in geo_fact

        print(f"[Intelligence] Validated business: {intel_data.get('business_name')}")
        print(f"[Intelligence] Final gap: {intel_data.get('primary_gap', '')[:80]}...")
        return intel_data