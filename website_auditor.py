#!/usr/bin/env python3
"""
Website Quality & Design Lead Prospecting Auditor
------------------------------------------------
Scans target websites across Design/UX, Mobile, Performance, SEO, Security, and Modern Tech Stack.
Calculates lead prospect scores and generates custom email/outreach pitch points for web design agency outreach.
"""

import os
import re
import sys
import json
import csv
import time
import math
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("[!] Missing required packages. Installing requests and beautifulsoup4...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "urllib3"])
    import requests
    from bs4 import BeautifulSoup

# Disable SSL warnings for testing uncertified legacy sites
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 QualityAuditor/1.0"

class WebsiteAuditor:
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        })

    def normalize_url(self, target):
        target = target.strip()
        if not target.startswith("http://") and not target.startswith("https://"):
            target = "https://" + target
        return target

    def audit_site(self, target_input):
        raw_url = self.normalize_url(target_input)
        parsed_orig = urlparse(raw_url)
        domain = parsed_orig.netloc or parsed_orig.path

        res = {
            "input_domain": domain,
            "url": raw_url,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Success",
            "error_msg": "",
            "http_code": 0,
            "response_time_sec": 0.0,
            "final_url": raw_url,
            "is_https": raw_url.startswith("https://"),
            
            # Scores (0 - 100)
            "overall_score": 0,
            "design_score": 0,
            "mobile_score": 0,
            "performance_score": 0,
            "seo_score": 0,
            "trust_score": 0,
            
            "prospect_tier": "Low Potential",  # High/Medium/Low prospect lead
            "pitch_points": [],
            "positive_highlights": [],
            
            # Audit Details
            "metrics": {}
        }

        start_time = time.time()
        try:
            # First attempt HTTPS, fallback to HTTP if needed
            try:
                response = self.session.get(raw_url, timeout=self.timeout, allow_redirects=True, verify=False)
            except requests.exceptions.SSLError:
                res["is_https"] = False
                http_url = raw_url.replace("https://", "http://")
                response = self.session.get(http_url, timeout=self.timeout, allow_redirects=True, verify=False)
            except requests.exceptions.RequestException:
                if raw_url.startswith("https://"):
                    http_url = raw_url.replace("https://", "http://")
                    response = self.session.get(http_url, timeout=self.timeout, allow_redirects=True, verify=False)
                else:
                    raise

            res["response_time_sec"] = round(time.time() - start_time, 2)
            res["http_code"] = response.status_code
            res["final_url"] = response.url
            res["is_https"] = response.url.startswith("https://")

            # Fallback to urllib if requests gets blocked by WAF/Cloudflare (403 Forbidden)
            if response.status_code == 403:
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        raw_url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
                    )
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        html_text = resp.read().decode("utf-8", errors="ignore")
                        res["http_code"] = resp.getcode()
                        res["status"] = "Success"
                        res["error_msg"] = ""
                        # Create synthetic response object with text for soup parsing
                        class SyntheticResponse:
                            def __init__(self, text, url, status_code, headers):
                                self.text = text
                                self.url = url
                                self.status_code = status_code
                                self.headers = headers
                        response = SyntheticResponse(html_text, raw_url, 200, {"Content-Type": "text/html"})
                except Exception as ex:
                    pass

            if response.status_code >= 400:
                res["status"] = "HTTP Error"
                res["error_msg"] = f"Server returned HTTP status {response.status_code}"
                self._score_failed_site(res)
                return res

            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                res["status"] = "Non-HTML Content"
                res["error_msg"] = f"Endpoint returned non-HTML content type: {content_type}"
                self._score_failed_site(res)
                return res

            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")

            # Run detailed audits
            self._audit_design_and_ux(soup, html_content, response, res)
            self._audit_mobile(soup, html_content, res)
            self._audit_performance(soup, html_content, res)
            self._audit_seo(soup, res)
            self._audit_trust_and_security(soup, html_content, response, res)

            # Calculate composite scores and generate sales pitch points
            self._calculate_scores_and_pitch(res)

            # ----------------------------------------------------------------
            # PAGESPEED INSIGHTS INTEGRATION
            # Override heuristic Performance & SEO scores with real API data
            # ----------------------------------------------------------------
            try:
                import importlib.util, sys as _sys
                _ps_path = os.path.join(os.path.dirname(__file__), "pagespeed_auditor.py")
                if os.path.exists(_ps_path):
                    _spec = importlib.util.spec_from_file_location("pagespeed_auditor", _ps_path)
                    _ps_mod = importlib.util.module_from_spec(_spec)
                    _spec.loader.exec_module(_ps_mod)
                    ps = _ps_mod.audit_site(raw_url)
                    if ps.get("status") == "Success":
                        ps_scores = ps.get("scores", {})
                        ps_metrics = ps.get("metrics", {})
                        ps_issues = ps.get("issues", [])

                        # Override scores with real PageSpeed values
                        if ps_scores.get("performance") is not None:
                            res["performance_score"] = ps_scores["performance"]
                        if ps_scores.get("seo") is not None:
                            res["seo_score"] = ps_scores["seo"]
                        if ps_scores.get("accessibility") is not None:
                            res["accessibility_score"] = ps_scores["accessibility"]
                        if ps_scores.get("best_practices") is not None:
                            res["best_practices_score"] = ps_scores["best_practices"]

                        # Store Core Web Vitals in metrics
                        res["metrics"]["pagespeed"] = {
                            "lcp_seconds": ps_metrics.get("lcp_seconds"),
                            "cls": ps_metrics.get("cls"),
                            "tbt_ms": ps_metrics.get("tbt_ms"),
                            "mobile_font_size_issue": ps_metrics.get("mobile_font_size"),
                            "mobile_tap_target_issue": ps_metrics.get("mobile_tap_targets"),
                        }

                        # Add PageSpeed plain-English issues to pitch (avoid duplicates)
                        existing_pitch_text = " ".join(res["pitch_points"]).lower()
                        for issue in ps_issues:
                            if issue.lower()[:30] not in existing_pitch_text:
                                res["pitch_points"].append(f"[PageSpeed] {issue}")

                        # Recalculate overall score with real data
                        # Weights: Design 30%, Mobile 20%, Performance 20%, SEO 15%, Trust 15%
                        overall = (
                            res["design_score"] * 0.30 +
                            res["mobile_score"] * 0.20 +
                            res["performance_score"] * 0.20 +
                            res["seo_score"] * 0.15 +
                            res["trust_score"] * 0.15
                        )
                        res["overall_score"] = int(round(overall))

                        # Re-evaluate lead tier based on updated score
                        mob = res["metrics"].get("mobile", {})
                        if res["overall_score"] < 50 or not mob.get("has_viewport_tag", True) or not res.get("is_https"):
                            res["prospect_tier"] = "HIGH POTENTIAL LEAD (Major Flaws / Redesign Needed)"
                        elif res["overall_score"] < 75:
                            res["prospect_tier"] = "MEDIUM POTENTIAL LEAD (Modernization Opportunity)"
                        else:
                            res["prospect_tier"] = "LOW POTENTIAL (Site is already modern)"

                        res["pagespeed_used"] = True

            except Exception as _ps_err:
                res["pagespeed_used"] = False
                res["pagespeed_error"] = str(_ps_err)

            # Stage 1 Pipeline Flag: Mark leads worth pitching for Stage 2 Playwright verification
            res["needs_confirmation"] = "HIGH POTENTIAL" in res.get("prospect_tier", "") or "MEDIUM POTENTIAL" in res.get("prospect_tier", "")

        except Exception as e:
            res["status"] = "Error"
            res["error_msg"] = str(e)
            res["response_time_sec"] = round(time.time() - start_time, 2)
            self._score_failed_site(res)

        return res

    def _audit_design_and_ux(self, soup, html, response, res):
        metrics = res["metrics"]
        
        # 1. Layout techniques (Modern Flex/Grid vs Legacy Tables/Floats)
        style_tags = soup.find_all("style")
        inline_css = " ".join([s.get_text() for s in style_tags])
        
        # Check inline styles attribute count
        elements_with_inline_styles = len(soup.find_all(style=True))
        table_layouts = len(soup.find_all("table"))
        
        uses_flex_or_grid = bool(re.search(r'display\s*:\s*(flex|grid|inline-flex|inline-grid)', inline_css, re.I))
        uses_legacy_floats = bool(re.search(r'float\s*:\s*(left|right)', inline_css, re.I)) or ("align=" in html.lower())

        # 2. Typography & Fonts
        google_fonts = any("fonts.googleapis.com" in (link.get("href") or "") for link in soup.find_all("link", rel=re.compile(r'stylesheet', re.I)))
        custom_fonts_in_css = "@font-face" in inline_css or "font-family" in inline_css

        # 3. Favicon & Branding Assets
        favicons = soup.find_all("link", rel=re.compile(r'icon', re.I))
        has_favicon = len(favicons) > 0
        has_apple_touch_icon = any("apple-touch-icon" in (link.get("rel", []) or "") for link in soup.find_all("link"))

        # 4. Images Quality & Modern Formats
        images = soup.find_all("img")
        total_images = len(images)
        images_missing_alt = len([img for img in images if not img.get("alt")])
        images_with_srcset = len([img for img in images if img.get("srcset")])
        
        legacy_image_formats = len([img for img in images if (img.get("src") or "").lower().endswith((".bmp", ".gif"))])
        modern_image_formats = len([img for img in images if (img.get("src") or "").lower().endswith((".webp", ".svg", ".avif"))])

        # 5. UI Interactivity & Micro-animations
        has_css_hover = ":hover" in inline_css or "transition" in inline_css or "animation" in inline_css
        
        # 6. Call To Action (CTA) buttons
        buttons = soup.find_all(["button", "a"])
        cta_keywords = ["get quote", "contact us", "book now", "schedule", "call now", "buy now", "sign up", "free consultation", "estimate"]
        found_ctas = 0
        # 7. Layout Overlap & Visual Break Detection (Absolute positioning, negative margins, uncontained forms)
        all_styles = inline_css
        for elem in soup.find_all(style=True):
            all_styles += " " + elem.get("style", "")

        has_high_absolute_positioning = len(re.findall(r'position\s*:\s*absolute', all_styles, re.I)) > 5
        has_negative_margins = bool(re.search(r'margin(?:-(?:top|bottom|left|right))?\s*:\s*-[0-9]+', all_styles, re.I))
        has_fixed_height_wrappers = bool(re.search(r'height\s*:\s*[0-9]{3,4}px', all_styles, re.I))
        has_fixed_width_containers = bool(re.search(r'width\s*:\s*(?:9[0-9]{2}|1[0-9]{3})px', all_styles, re.I)) and "@media" not in html
        
        # Check for uncontained form input elements (inputs placed outside form tags or overflowing footer containers)
        inputs_outside_form = len([inp for inp in soup.find_all(["input", "textarea"]) if not inp.find_parent("form")])
        inputs_in_footer = len([inp for inp in soup.find_all(["input", "textarea"]) if inp.find_parent(re.compile(r'footer|bottom', re.I)) or "footer" in str(inp.get("class", [])).lower()])
        
        has_layout_overlap_risk = has_high_absolute_positioning or has_negative_margins or has_fixed_width_containers or (inputs_outside_form > 0 and inputs_in_footer > 0)

        # 8. Color Contrast & Low-Legibility Detection (e.g., dark text on dark background)
        has_poor_contrast = False
        all_text = soup.get_text()
        
        # Check for explicit dark-on-dark contrast issues (e.g. dark olive green #3a3f27, #4a4d38 with dark background)
        dark_text_elements = len(soup.find_all(style=re.compile(r'color\s*:\s*#(?:3a3f27|4a4d38|50523d)|background(?:-color)?\s*:\s*#(?:[0-2][0-9a-f]){3}.*color\s*:\s*#(?:[0-3][0-9a-f]){3}', re.I)))
        has_dark_inline_style = "color:#3a3f27" in html.lower() or "color:#4a4d38" in html.lower() or "color: #3a3f27" in html.lower()
        
        if dark_text_elements > 0 or has_dark_inline_style:
            has_poor_contrast = True

        # 9. Empty Articles & Broken Pagination Widget Detection (e.g. '1of0', '0 of 0', '1 0')
        empty_pagination = bool(re.search(r'1\s*of\s*0|0\s*of\s*0|1\s+0', all_text, re.I)) or ("1of0" in html.replace(" ", "").lower()) or ("1 0" in all_text)
        has_empty_article_widget = empty_pagination or ("articles" in html.lower() and ("1" in html and "0" in html))

        # Save Design Metrics
        metrics["design"] = {
            "inline_style_elements_count": elements_with_inline_styles,
            "table_layout_count": table_layouts,
            "uses_flex_or_grid": uses_flex_or_grid,
            "uses_legacy_floats": uses_legacy_floats,
            "google_fonts_used": google_fonts,
            "has_custom_typography": google_fonts or custom_fonts_in_css,
            "has_favicon": has_favicon,
            "has_apple_touch_icon": has_apple_touch_icon,
            "total_images": total_images,
            "images_missing_alt": images_missing_alt,
            "responsive_images_srcset": images_with_srcset,
            "legacy_image_formats": legacy_image_formats,
            "modern_image_formats": modern_image_formats,
            "has_css_micro_animations": has_css_hover,
            "cta_button_count": found_ctas,
            "has_high_absolute_positioning": has_high_absolute_positioning,
            "has_negative_margins": has_negative_margins,
            "has_fixed_width_containers": has_fixed_width_containers,
            "inputs_outside_form": inputs_outside_form,
            "has_layout_overlap_risk": has_layout_overlap_risk,
            "has_poor_contrast": has_poor_contrast,
            "has_empty_article_widget": has_empty_article_widget
        }

    def _audit_mobile(self, soup, html, res):
        metrics = res["metrics"]
        
        # Viewport Meta Tag
        viewport_tag = soup.find("meta", attrs={"name": re.compile(r'viewport', re.I)})
        has_viewport = bool(viewport_tag)
        viewport_content = viewport_tag.get("content", "") if viewport_tag else ""
        has_width_device = "width=device-width" in viewport_content.lower()

        # Responsive Frameworks (Bootstrap, Tailwind, Bulma, Foundation, etc.)
        css_links = [link.get("href", "").lower() for link in soup.find_all("link", rel=re.compile(r'stylesheet', re.I))]
        frameworks = []
        if any("bootstrap" in href for href in css_links): frameworks.append("Bootstrap")
        if any("tailwind" in href for href in css_links): frameworks.append("Tailwind CSS")
        if any("bulma" in href for href in css_links): frameworks.append("Bulma")
        if any("foundation" in href for href in css_links): frameworks.append("Foundation")
        if any("elementor" in href for href in css_links): frameworks.append("Elementor (WordPress)")
        if any("divi" in href for href in css_links): frameworks.append("Divi (WordPress)")

        # Media Queries check
        has_media_queries = "@media" in html or any("media=" in str(link) for link in css_links)

        metrics["mobile"] = {
            "has_viewport_tag": has_viewport,
            "is_viewport_correct": has_width_device,
            "detected_frameworks": frameworks,
            "has_media_queries": has_media_queries
        }

    def _audit_performance(self, soup, html, res):
        metrics = res["metrics"]
        
        # DOM Node Count & Depth
        total_dom_nodes = len(soup.find_all())
        
        # External Assets Count
        external_css = len(soup.find_all("link", rel=re.compile(r'stylesheet', re.I)))
        external_js = len(soup.find_all("script", src=True))
        
        # Check for legacy scripts (e.g. jQuery < 3, Flash, old libraries)
        script_sources = " ".join([s.get("src", "").lower() for s in soup.find_all("script", src=True)])
        uses_legacy_jquery = bool(re.search(r'jquery[.-](1\.|2\.)', script_sources))
        uses_flash = "embed" in html.lower() or "flash" in html.lower()

        html_size_kb = round(len(html.encode('utf-8')) / 1024.0, 1)

        metrics["performance"] = {
            "page_load_time_sec": res["response_time_sec"],
            "html_size_kb": html_size_kb,
            "total_dom_nodes": total_dom_nodes,
            "external_css_count": external_css,
            "external_js_count": external_js,
            "uses_legacy_jquery": uses_legacy_jquery,
            "uses_flash": uses_flash
        }

    def _audit_seo(self, soup, res):
        metrics = res["metrics"]
        
        # Title
        title_tag = soup.find("title")
        title_text = title_tag.get_text().strip() if title_tag else ""
        has_title = bool(title_text)
        title_length = len(title_text)

        # Meta Description
        meta_desc = soup.find("meta", attrs={"name": re.compile(r'description', re.I)})
        desc_text = meta_desc.get("content", "").strip() if meta_desc else ""
        has_meta_desc = bool(desc_text)
        desc_length = len(desc_text)

        # Headings
        h1_tags = soup.find_all("h1")
        h1_count = len(h1_tags)
        h2_count = len(soup.find_all("h2"))

        # Open Graph (OG Tags)
        og_title = soup.find("meta", property="og:title")
        og_image = soup.find("meta", property="og:image")
        og_desc = soup.find("meta", property="og:description")
        has_og_tags = bool(og_title or og_image or og_desc)

        metrics["seo"] = {
            "has_title": has_title,
            "title_text": title_text,
            "title_length": title_length,
            "has_meta_description": has_meta_desc,
            "meta_description_length": desc_length,
            "h1_count": h1_count,
            "h2_count": h2_count,
            "has_open_graph_tags": has_og_tags,
            "has_og_image": bool(og_image)
        }

    def _audit_trust_and_security(self, soup, html, response, res):
        metrics = res["metrics"]
        
        # Copyright year detection
        current_year = datetime.now().year
        copyright_matches = re.findall(r'(?:copyright|\u00a9|\&copy;)\s*(?:20\d\d\s*[-–—]\s*)?(20\d\d)', html, re.I)
        latest_copyright_year = None
        if copyright_matches:
            try:
                years = [int(y) for y in copyright_matches if 2000 <= int(y) <= current_year]
                if years:
                    latest_copyright_year = max(years)
            except ValueError:
                pass

        is_outdated_copyright = latest_copyright_year is not None and (current_year - latest_copyright_year >= 2)

        # Trust pages: Privacy Policy, Terms, Contact
        links = soup.find_all("a", href=True)
        link_texts_and_hrefs = " ".join([a.get_text().lower() + " " + a.get("href", "").lower() for a in links])
        
        has_privacy_policy = "privacy" in link_texts_and_hrefs
        has_terms = "terms" in link_texts_and_hrefs or "condition" in link_texts_and_hrefs
        has_contact_page = "contact" in link_texts_and_hrefs
        
        # Phone / Email presence
        has_phone = bool(re.search(r'(\+?\d{1,2}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', html))
        has_mailto = "mailto:" in html.lower()

        metrics["trust"] = {
            "is_https": res["is_https"],
            "detected_copyright_year": latest_copyright_year,
            "is_outdated_copyright": is_outdated_copyright,
            "has_privacy_policy": has_privacy_policy,
            "has_terms_page": has_terms,
            "has_contact_page": has_contact_page,
            "has_phone_number": has_phone,
            "has_email_link": has_mailto
        }

    def _score_failed_site(self, res):
        res["overall_score"] = 0
        res["design_score"] = 0
        res["mobile_score"] = 0
        res["performance_score"] = 0
        res["seo_score"] = 0
        res["trust_score"] = 0
        res["prospect_tier"] = "URGENT LEAD (Site Broken / Unreachable)"
        res["pitch_points"] = [
            f"Website is currently unreachable or returning server error ({res['http_code'] or res['error_msg']}).",
            "Business is losing 100% of online visitors and potential customers."
        ]

    def _calculate_scores_and_pitch(self, res):
        m = res["metrics"]
        pitch = []
        highlights = []

        # -----------------------------
        # 1. DESIGN SCORE (Max 100)
        # -----------------------------
        d = m["design"]
        d_score = 100
        
        # Stage 1 Heuristic Pre-Filter Flags (Layout risks marked for Stage 2 Playwright confirmation)
        if d.get("has_fixed_width_containers"):
            d_score -= 20
            pitch.append("[Stage 1 Pre-Filter] POTENTIAL OVERFLOW: Fixed pixel width containers (>900px) detected without media queries. Run !confirm for browser proof.")
        if d.get("has_poor_contrast"):
            d_score -= 20
            pitch.append("VISUAL CONTRAST ISSUE: Low contrast text styles detected against element backgrounds.")
        if d.get("has_empty_article_widget"):
            d_score -= 25
            pitch.append("BROKEN CONTENT WIDGET: Empty article/blog widget detected displaying broken pagination ('1of0' / zero articles available).")
        if d.get("has_high_absolute_positioning"):
            d_score -= 15
            pitch.append("[Stage 1 Pre-Filter] POTENTIAL OVERLAP RISK: Uncontained absolute CSS positioning detected. Run !confirm to verify bounding box collisions.")
        elif d.get("inputs_outside_form", 0) > 0:
            d_score -= 15
            pitch.append("[Stage 1 Pre-Filter] UNCONTAINED INPUTS: Interactive form fields positioned outside form containers. Run !confirm for viewport verification.")
        
        # Mention layout structure only if paired with an actual detected layout defect
        if d["uses_legacy_floats"] and (d.get("has_fixed_width_containers") or d.get("has_high_absolute_positioning")):
            d_score -= 10
            pitch.append("CONTRIBUTING PATTERN: Layout relies on legacy float positioning alongside fixed dimensions, compounding mobile layout shift issues.")
        if d["inline_style_elements_count"] > 25:
            d_score -= 15
            pitch.append("Excessive inline styles detected; makes visual modifications and re-branding inefficient.")
        if not d["has_custom_typography"]:
            d_score -= 15
            pitch.append("Lacks modern web typography (using default browser fonts), reducing brand prestige.")
        else:
            highlights.append("Uses custom web typography.")
            
        if not d["has_favicon"]:
            d_score -= 15
            pitch.append("Missing browser favicon icon — looks unpolished and unprofessional in browser tabs.")
        if d["legacy_image_formats"] > 0:
            d_score -= 10
            pitch.append("Uses legacy image formats (GIF/BMP) instead of crisp vector SVG or high-compression WebP.")
        if d["modern_image_formats"] > 0:
            highlights.append("Uses modern WebP/SVG image formats.")
        if d["images_missing_alt"] > 3:
            d_score -= 10
            pitch.append(f"{d['images_missing_alt']} images are missing ALT descriptive tags (hurts image search ranking and accessibility).")
        if not d["has_css_micro_animations"]:
            d_score -= 10
            pitch.append("Lacks interactive micro-animations or modern hover state feedback for visitors.")
        if d["cta_button_count"] == 0:
            d_score -= 20
            pitch.append("No clear Call-To-Action (CTA) buttons found above or below the fold to convert visitors into phone calls/leads.")
        else:
            highlights.append(f"Found {d['cta_button_count']} Call-To-Action conversion triggers.")

        res["design_score"] = max(0, min(100, d_score))

        # -----------------------------
        # 2. MOBILE SCORE (Max 100)
        # -----------------------------
        mob = m["mobile"]
        mob_score = 100
        if not mob["has_viewport_tag"]:
            mob_score -= 50
            pitch.append("CRITICAL: Missing mobile viewport meta tag. Site will render extremely tiny and zoomed-out on smartphones.")
        elif not mob["is_viewport_correct"]:
            mob_score -= 25
            pitch.append("Mobile viewport configuration is suboptimal for mobile screen responsiveness.")
        
        if not mob["has_media_queries"] and not mob["detected_frameworks"]:
            mob_score -= 35
            pitch.append("Lacks responsive CSS media queries — layout fails to adapt smoothly to modern tablet/mobile screens.")
        elif mob["detected_frameworks"]:
            highlights.append(f"Built with responsive framework: {', '.join(mob['detected_frameworks'])}.")

        res["mobile_score"] = max(0, min(100, mob_score))

        # -----------------------------
        # 3. PERFORMANCE SCORE (Max 100)
        # -----------------------------
        perf = m["performance"]
        p_score = 100
        
        if perf["page_load_time_sec"] > 4.0:
            p_score -= 40
            pitch.append(f"Slow server response time ({perf['page_load_time_sec']}s). Google penalizes sites taking over 3 seconds to load.")
        elif perf["page_load_time_sec"] > 2.0:
            p_score -= 20
            pitch.append(f"Page response time is slightly slow ({perf['page_load_time_sec']}s). Optimizing assets can boost conversion rates.")
        else:
            highlights.append(f"Fast initial response speed ({perf['page_load_time_sec']}s).")

        if perf["external_css_count"] + perf["external_js_count"] > 20:
            p_score -= 15
            pitch.append(f"High HTTP request bottleneck ({perf['external_css_count']} CSS files, {perf['external_js_count']} JS scripts).")
        if perf["uses_legacy_jquery"]:
            p_score -= 15
            pitch.append("Uses an outdated, legacy version of jQuery (v1.x/v2.x) which has known performance and security vulnerabilities.")
        if perf["uses_flash"]:
            p_score -= 50
            pitch.append("URGENT: Flash/Embed technology detected, which is completely unsupported on modern web browsers.")

        res["performance_score"] = max(0, min(100, p_score))

        # -----------------------------
        # 4. SEO SCORE (Max 100)
        # -----------------------------
        seo = m["seo"]
        s_score = 100
        
        if not seo["has_title"]:
            s_score -= 30
            pitch.append("Missing HTML `<title>` tag — critical missing ranking signal for Google Search.")
        elif seo["title_length"] < 15 or seo["title_length"] > 70:
            s_score -= 15
            pitch.append(f"Page title length ({seo['title_length']} chars) is outside optimal SEO range (30-60 characters).")
            
        if not seo["has_meta_description"]:
            s_score -= 25
            pitch.append("Missing meta description; search engines will show random scraped page snippets.")
        if seo["h1_count"] == 0:
            s_score -= 20
            pitch.append("Missing `<h1>` header tag to define the page's primary business topic for SEO.")
        elif seo["h1_count"] > 2:
            s_score -= 10
            pitch.append(f"Multiple `<h1>` tags ({seo['h1_count']}) diluting page keyword context.")
        if not seo["has_open_graph_tags"]:
            s_score -= 15
            pitch.append("Lacks Open Graph (OG) tags — when shared on social media (Facebook, LinkedIn, iMessage), links will show no thumbnail image or preview text.")

        res["seo_score"] = max(0, min(100, s_score))

        # -----------------------------
        # 5. TRUST & SECURITY SCORE (Max 100)
        # -----------------------------
        tr = m["trust"]
        t_score = 100
        
        if not tr["is_https"]:
            t_score -= 40
            pitch.append("CRITICAL: Not using HTTPS SSL security. Browsers display an alarming 'Not Secure' warning to visitors.")
        if tr["is_outdated_copyright"]:
            t_score -= 25
            pitch.append(f"Footer copyright displays outdated year ({tr['detected_copyright_year']}), giving visitors the impression the business is inactive.")
        if not tr["has_privacy_policy"]:
            t_score -= 10
            pitch.append("Missing Privacy Policy page (required for compliance & ad campaigns).")
        if not tr["has_contact_page"] and not tr["has_phone_number"]:
            t_score -= 15
            pitch.append("Hard for visitors to reach out — no clear phone number or contact page detected in audit.")

        res["trust_score"] = max(0, min(100, t_score))

        # -----------------------------
        # COMPOSITE OVERALL SCORE & LEAD TIER
        # -----------------------------
        # Weights: Design 35%, Mobile 20%, Performance 15%, SEO 15%, Trust 15%
        overall = (
            res["design_score"] * 0.35 +
            res["mobile_score"] * 0.20 +
            res["performance_score"] * 0.15 +
            res["seo_score"] * 0.15 +
            res["trust_score"] * 0.15
        )
        res["overall_score"] = int(round(overall))
        res["pitch_points"] = pitch
        res["positive_highlights"] = highlights

        # Lead Rating Assignment
        if res["overall_score"] < 50 or not mob["has_viewport_tag"] or not tr["is_https"]:
            res["prospect_tier"] = "HIGH POTENTIAL LEAD (Major Flaws / Redesign Needed)"
        elif res["overall_score"] < 75:
            res["prospect_tier"] = "MEDIUM POTENTIAL LEAD (Modernization Opportunity)"
        else:
            res["prospect_tier"] = "LOW POTENTIAL (Site is already modern)"


def export_csv(results, filepath):
    fieldnames = [
        "input_domain", "prospect_tier", "overall_score",
        "design_score", "mobile_score", "performance_score", "seo_score", "trust_score",
        "accessibility_score", "best_practices_score",
        "lcp_seconds", "cls", "tbt_ms", "pagespeed_used",
        "url", "response_time_sec", "is_https", "pitch_points_count", "pitch_summary"
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            ps = r.get("metrics", {}).get("pagespeed", {})
            writer.writerow({
                "input_domain": r["input_domain"],
                "prospect_tier": r["prospect_tier"],
                "overall_score": r["overall_score"],
                "design_score": r["design_score"],
                "mobile_score": r["mobile_score"],
                "performance_score": r["performance_score"],
                "seo_score": r["seo_score"],
                "trust_score": r["trust_score"],
                "accessibility_score": r.get("accessibility_score", ""),
                "best_practices_score": r.get("best_practices_score", ""),
                "lcp_seconds": ps.get("lcp_seconds", ""),
                "cls": ps.get("cls", ""),
                "tbt_ms": ps.get("tbt_ms", ""),
                "pagespeed_used": r.get("pagespeed_used", False),
                "url": r["url"],
                "response_time_sec": r["response_time_sec"],
                "is_https": r["is_https"],
                "pitch_points_count": len(r["pitch_points"]),
                "pitch_summary": " | ".join(r["pitch_points"][:4])
            })
    print(f"[+] CSV Report exported to: {os.path.abspath(filepath)}")


def export_json(results, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"[+] JSON Report exported to: {os.path.abspath(filepath)}")


def export_html_dashboard(results, filepath):
    high_leads = sum(1 for r in results if "HIGH POTENTIAL" in r["prospect_tier"] or "URGENT" in r["prospect_tier"])
    med_leads = sum(1 for r in results if "MEDIUM POTENTIAL" in r["prospect_tier"])
    low_leads = sum(1 for r in results if "LOW POTENTIAL" in r["prospect_tier"])

    rows_html = ""
    for idx, r in enumerate(results):
        tier_class = "badge-danger" if "HIGH" in r["prospect_tier"] or "URGENT" in r["prospect_tier"] else ("badge-warning" if "MEDIUM" in r["prospect_tier"] else "badge-success")
        
        pitch_bullets = "".join([f"<li>{p}</li>" for p in r["pitch_points"]]) or "<li>No critical flaws detected. Site meets modern standards.</li>"
        highlights_bullets = "".join([f"<li>{h}</li>" for h in r["positive_highlights"]]) or "<li>Standard setup</li>"

        rows_html += f"""
        <tr class="audit-row">
            <td>
                <strong>{r['input_domain']}</strong><br/>
                <small><a href="{r['url']}" target="_blank">{r['url']}</a></small>
                {('<br/><small style="color:#38bdf8;font-size:11px;">&#9889; Scored with PageSpeed API</small>') if r.get('pagespeed_used') else '<br/><small style="color:#64748b;font-size:11px;">&#128269; Scored with HTML analysis</small>'}
            </td>
            <td><span class="badge {tier_class}">{r['prospect_tier']}</span></td>
            <td><div class="score-pill score-{get_score_color_class(r['overall_score'])}">{r['overall_score']} / 100</div></td>
            <td>
                <div class="subscore-grid">
                    <span>&#127912; Design: <strong>{r['design_score']}</strong></span>
                    <span>&#128241; Mobile: <strong>{r['mobile_score']}</strong></span>
                    <span>&#9889; Speed: <strong style="color:{'#fca5a5' if r['performance_score'] < 50 else '#fde047' if r['performance_score'] < 90 else '#86efac'}">{r['performance_score']}</strong></span>
                    <span>&#128269; SEO: <strong style="color:{'#fca5a5' if r['seo_score'] < 50 else '#fde047' if r['seo_score'] < 90 else '#86efac'}">{r['seo_score']}</strong></span>
                    <span>&#128274; Trust: <strong>{r['trust_score']}</strong></span>
                    {f"<span>&#9745; Access: <strong>{r.get('accessibility_score', 'N/A')}</strong></span>" if r.get('pagespeed_used') else ''}
                </div>
                {f'''<div style="margin-top:6px;font-size:11px;color:#94a3b8;border-top:1px solid #334155;padding-top:4px;">
                    <strong style="color:#38bdf8;">Core Web Vitals</strong><br/>
                    LCP: <strong>{r['metrics'].get('pagespeed', {}).get('lcp_seconds', 'N/A')}s</strong> &nbsp;
                    CLS: <strong>{r['metrics'].get('pagespeed', {}).get('cls', 'N/A')}</strong> &nbsp;
                    TBT: <strong>{r['metrics'].get('pagespeed', {}).get('tbt_ms', 'N/A')}ms</strong>
                </div>''' if r.get('pagespeed_used') and r.get('metrics', {}).get('pagespeed') else ''}
            </td>
            <td>
                <details>
                    <summary><strong>View {len(r['pitch_points'])} Sales Pitch Points</strong></summary>
                    <ul class="pitch-list">
                        {pitch_bullets}
                    </ul>
                </details>
            </td>
        </tr>
        """


    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Website Audit & Lead Prospecting Dashboard</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #22c55e;
            --accent-yellow: #eab308;
            --accent-red: #ef4444;
            --border-color: #334155;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 24px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        h1 {{ margin: 0; font-size: 24px; color: var(--accent-blue); }}
        .stats-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 16px;
            border-radius: 8px;
            text-align: center;
        }}
        .card h3 {{ margin: 0 0 8px 0; font-size: 14px; color: var(--text-muted); text-transform: uppercase; }}
        .card .number {{ font-size: 28px; font-weight: bold; }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card-bg);
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}
        th, td {{
            padding: 14px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
            vertical-align: top;
        }}
        th {{
            background-color: #0f172a;
            color: var(--text-muted);
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        a {{ color: var(--accent-blue); text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-danger {{ background: rgba(239, 68, 68, 0.2); color: var(--accent-red); border: 1px solid var(--accent-red); }}
        .badge-warning {{ background: rgba(234, 179, 8, 0.2); color: var(--accent-yellow); border: 1px solid var(--accent-yellow); }}
        .badge-success {{ background: rgba(34, 197, 94, 0.2); color: var(--accent-green); border: 1px solid var(--accent-green); }}

        .score-pill {{
            font-weight: bold;
            font-size: 16px;
            padding: 6px 12px;
            border-radius: 6px;
            text-align: center;
            display: inline-block;
        }}
        .score-red {{ background: #450a0a; color: #fca5a5; border: 1px solid #ef4444; }}
        .score-yellow {{ background: #422006; color: #fde047; border: 1px solid #eab308; }}
        .score-green {{ background: #052e16; color: #86efac; border: 1px solid #22c55e; }}

        .subscore-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 4px;
            font-size: 12px;
            color: var(--text-muted);
        }}
        .subscore-grid strong {{ color: var(--text-main); }}

        summary {{ cursor: pointer; color: var(--accent-blue); font-size: 13px; }}
        .pitch-list {{
            margin: 8px 0 0 0;
            padding-left: 18px;
            font-size: 13px;
            color: #cbd5e1;
        }}
        .pitch-list li {{ margin-bottom: 6px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🌐 Website Quality & Lead Prospecting Dashboard</h1>
        <span>Generated: {datetime.now().strftime("%B %d, %Y - %H:%M")}</span>
    </div>

    <div class="stats-cards">
        <div class="card">
            <h3>Total Audited Sites</h3>
            <div class="number" style="color: var(--accent-blue);">{len(results)}</div>
        </div>
        <div class="card">
            <h3>High Potential Leads 🔥</h3>
            <div class="number" style="color: var(--accent-red);">{high_leads}</div>
        </div>
        <div class="card">
            <h3>Medium Opportunities ⚡</h3>
            <div class="number" style="color: var(--accent-yellow);">{med_leads}</div>
        </div>
        <div class="card">
            <h3>Low Priority / Modern</h3>
            <div class="number" style="color: var(--accent-green);">{low_leads}</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Domain / Target</th>
                <th>Prospect Rating</th>
                <th>Overall Audit Score</th>
                <th>Sub-Category Scores</th>
                <th>Actionable Pitch Talking Points</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"[+] HTML Dashboard exported to: {os.path.abspath(filepath)}")


def get_score_color_class(score):
    if score < 50: return "red"
    if score < 75: return "yellow"
    return "green"


def main():
    parser = argparse.ArgumentParser(description="Audit websites on Design, Mobile, Speed, SEO, and Security to generate client outreach leads.")
    parser.add_argument("--url", "-u", type=str, help="Single URL or domain to audit")
    parser.add_argument("--input", "-i", type=str, help="File containing list of URLs/domains (one per line)")
    parser.add_argument("--csv", type=str, default="audit_report.csv", help="CSV output filename")
    parser.add_argument("--json", type=str, default="audit_report.json", help="JSON output filename")
    parser.add_argument("--html", type=str, default="audit_report.html", help="HTML dashboard output filename")
    parser.add_argument("--threads", "-t", type=int, default=5, help="Number of concurrent audit threads")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP request timeout in seconds")

    args = parser.parse_args()

    targets = []
    if args.url:
        targets.append(args.url)
    elif args.input:
        if not os.path.exists(args.input):
            print(f"[!] Error: Input file '{args.input}' not found.")
            sys.exit(1)
        with open(args.input, "r", encoding="utf-8") as f:
            targets = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        print("[!] No target specified. Defaulting to sample domains list...")
        targets = ["example.com", "wikipedia.org", "python.org"]

    print(f"\n=======================================================")
    print(f"[+] Starting Website Quality & Design Lead Prospecting Audit")
    print(f"Targets: {len(targets)} domains | Threads: {args.threads} | Timeout: {args.timeout}s")
    print(f"=======================================================\n")

    auditor = WebsiteAuditor(timeout=args.timeout)
    results = []

    start_audit_time = time.time()
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_to_url = {executor.submit(auditor.audit_site, target): target for target in targets}
        for future in as_completed(future_to_url):
            domain = future_to_url[future]
            try:
                res = future.result()
                results.append(res)
                print(f"[{res['status']}] {res['input_domain']:<25} | Score: {res['overall_score']:>3}/100 | Tier: {res['prospect_tier']}")
            except Exception as exc:
                print(f"[ERROR] {domain}: {exc}")

    total_duration = round(time.time() - start_audit_time, 2)
    print(f"\n[OK] Audit completed in {total_duration} seconds.\n")

    # Sort results by overall score ascending (lowest score = highest potential lead first)
    results.sort(key=lambda x: x["overall_score"])

    # Export reports
    export_csv(results, args.csv)
    export_json(results, args.json)
    export_html_dashboard(results, args.html)

    print("\n[Outreach Strategy Tip]")
    print("Filter for 'HIGH POTENTIAL LEAD' sites in the HTML Dashboard or CSV.")
    print("Copy the generated sales pitch points straight into your email or LinkedIn message!")

if __name__ == "__main__":
    main()
