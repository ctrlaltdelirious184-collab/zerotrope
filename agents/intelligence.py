import json
import os
from utils.ollama_client import OllamaClient

class IntelligenceAgent:
    def __init__(self, memory_file="knowledge/agency_memory.json"):
        self.client = OllamaClient()
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
        if raw_title:
            homepage_text += f"\nPage title: {raw_title}"

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

        # Also extract from text - look for imperative phrases
        cta_keywords = ["join", "book", "get started", "sign up", "register", "download", 
                       "subscribe", "learn more", "contact", "schedule", "apply", "start",
                       "discover", "explore", "try", "buy", "shop", "hire"]
        text_ctas = []
        for line in homepage_text.split("\n"):
            line_clean = line.strip()
            if any(kw in line_clean.lower() for kw in cta_keywords) and len(line_clean) < 100:
                text_ctas.append(line_clean)

        all_ctas = list(found_ctas) + text_ctas[:10]
        
        # Check for actual pricing — requires dollar amounts, not just the word "pricing"
        import re as re2
        all_text = homepage_text + subpage_context
        dollar_amounts = re2.findall(r'\$\d+', all_text)
        pricing_found = len(dollar_amounts) > 0
        pricing_on_homepage = len(re2.findall(r'\$\d+', homepage_text)) > 0
        
        # Check for testimonials
        testimonial_keywords = ["testimonial", "review", "said", "quote", "worked with", "client story", "success story", "★", "⭐", "5 star"]
        testimonials_found = any(kw in (homepage_text + subpage_context).lower() for kw in testimonial_keywords)

        homepage_dollar_amounts = re2.findall(r"\$\d+", homepage_text)
        
        # Build hard facts summary for the AI
        hard_facts = f"""
HARD FACTS (extracted programmatically — these are definitive):
- CTAs found on site: {", ".join(all_ctas[:15]) if all_ctas else "NONE FOUND"}
- Dollar amounts found on HOMEPAGE: {"YES — " + ", ".join(homepage_dollar_amounts[:5]) if pricing_on_homepage else "NO"}
- Dollar amounts found on scraped SUBPAGES: {"YES — " + ", ".join(dollar_amounts[:5]) if pricing_found else "NO"}
- Pricing verdict: {"Pricing exists clearly on homepage" if pricing_on_homepage else "No transparent pricing listed directly on the homepage."}
- Testimonials found: {"YES" if testimonials_found else "NO"}
"""

        full_data = f"HOMEPAGE:\n{homepage_text}\n{subpage_context}\n{hard_facts}"

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
- CRITICAL: Never claim something (like pricing or CTAs) is "missing from the entire site" or "nowhere on any subpages". You can only say it is missing from the HOMEPAGE. Scraping doesn't see Javascript shops, so if you claim pricing is gone site-wide, you will look foolish.
- If CTAs exist in the data, do NOT flag CTAs as missing
- If testimonials exist in the data, do NOT flag testimonials as missing  
- If pricing exists anywhere in the data, do NOT flag pricing as missing
- If something exists on a subpage, it is NOT missing — it may be a prominence issue

For each gap you find, you MUST provide the exact quote or data point that proves it.

Check these dimensions ONLY using the actual data:

1. HOMEPAGE HERO: What does the hero section actually say? Is the main CTA above the fold specific or generic?
2. HOMEPAGE PRICING: Search the data carefully. Is pricing shown clearly on the homepage?
3. TRUST SIGNALS: Are testimonials, reviews, case studies visible? Where exactly?
4. AI/SEARCH VISIBILITY: Is the business described as a named entity with specific expertise, or just generic keywords?
5. MESSAGING: Does the headline copy use generic phrases that could apply to any competitor?

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

After validation, select the SINGLE most glaring, unique, or verifiable gap. 
DO NOT always default to the same type of gap (like generic CTAs) if there are more interesting problems found (e.g. absolutely no pricing, missing trust signals, or copy that applies to any competitor).

Choose the gap that would create the most "sting" for the business owner when pointed out.

Also extract:
- Clean business name (from logo text, H1, or brand mentions — NOT the SEO title tag)
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

        # Fallback business name
        if not intel_data.get("business_name") or len(intel_data["business_name"].strip()) < 2:
            from urllib.parse import urlparse
            source = research_data.get("source", "")
            if source.startswith("http"):
                domain = urlparse(source).netloc.replace("www.", "").split(".")[0]
                intel_data["business_name"] = domain.replace("-", " ").title()
            else:
                intel_data["business_name"] = raw_title.split("|")[0].strip() if raw_title else source

        # Reject placeholder names
        placeholder_phrases = ["no brand", "brand name", "not provided", "unknown", "n/a", "none", "company name"]
        if any(p in intel_data.get("business_name", "").lower() for p in placeholder_phrases):
            from urllib.parse import urlparse
            source = research_data.get("source", "")
            if source.startswith("http"):
                domain = urlparse(source).netloc.replace("www.", "").split(".")[0]
                intel_data["business_name"] = domain.replace("-", " ").title()

        print(f"[Intelligence] Validated business: {intel_data.get('business_name')}")
        print(f"[Intelligence] Final gap: {intel_data.get('primary_gap', '')[:80]}...")
        return intel_data