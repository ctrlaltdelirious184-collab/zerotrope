#!/usr/bin/env python3
"""
PageSpeed Insights Website Auditor Module
----------------------------------------
Calls Google's PageSpeed Insights API (mobile & desktop strategy) to audit URLs
and maps technical metrics into plain-English, non-technical explanations for business owners.
"""

import os
import sys
import json
import argparse
from urllib.parse import urlparse

import time as _time

# Rate throttle state for free-tier PageSpeed API (max ~1 req/sec)
_pagespeed_last_call = 0.0
_PAGESPEED_FREE_DELAY = 2.0  # seconds between calls without API key

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# -----------------------------------------------------------------------------
# PLAIN-ENGLISH ISSUE TRANSLATION CONFIG / THRESHOLDS
# -----------------------------------------------------------------------------
# Thresholds:
#   - Scores: 0 to 100 (flagged if value < threshold)
#   - LCP (Largest Contentful Paint): in seconds (flagged if value > threshold)
#   - CLS (Cumulative Layout Shift): score (flagged if value > threshold)
#   - TBT (Total Blocking Time): in ms (flagged if value > threshold)
#   - Booleans: flagged if value is True or False as specified

ISSUE_TRANSLATIONS = {
    # Overall Scores (0-100)
    "performance_score": {
        "threshold": 50,
        "comparator": "lt",
        "message": "Your site takes too long to load — most visitors leave before it even finishes loading on their phone."
    },
    "seo_score": {
        "threshold": 70,
        "comparator": "lt",
        "message": "Your site is missing basic elements Google looks for, which likely means you're getting buried under competitors in search results."
    },
    "accessibility_score": {
        "threshold": 70,
        "comparator": "lt",
        "message": "Some visitors, like those using screen readers or mobile accessibility features, may not be able to use your site properly."
    },
    "best_practices_score": {
        "threshold": 70,
        "comparator": "lt",
        "message": "Your site isn't following modern web security and code standards, making it vulnerable or glitchy in modern browsers."
    },

    # Core Web Vitals
    "lcp_seconds": {
        "threshold": 2.5,
        "comparator": "gt",
        "message": "The main content of your page takes several seconds to appear, which frustrates visitors and can hurt your Google ranking."
    },
    "cls": {
        "threshold": 0.1,
        "comparator": "gt",
        "message": "Your page elements shift around unexpectedly while loading, causing visitors to accidentally click the wrong links or buttons."
    },
    "tbt_ms": {
        "threshold": 300,
        "comparator": "gt",
        "message": "Your website freezes or becomes unresponsive for a noticeable delay when visitors try to click or scroll."
    },

    # Mobile Usability & Security
    "mobile_font_size": {
        "threshold": True,
        "comparator": "eq",
        "message": "Text on your mobile site is too small, forcing visitors to zoom in just to read your services."
    },
    "mobile_tap_targets": {
        "threshold": True,
        "comparator": "eq",
        "message": "Buttons and links on mobile are placed too close together, making it easy for customers to tap the wrong thing."
    },
    "mobile_viewport": {
        "threshold": True,
        "comparator": "eq",
        "message": "Your site lacks a proper mobile viewport, so it appears shrunk down or awkwardly zoomed on mobile screens."
    },
    "is_https": {
        "threshold": False,
        "comparator": "eq",
        "message": "Browsers may show visitors a 'Not Secure' warning before they even see your site because SSL/HTTPS is missing."
    }
}


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url


def audit_site(url: str, api_key: str = None, run_both_strategies: bool = True) -> dict:
    """
    Audits a given URL using Google's PageSpeed Insights API.
    By default queries both 'mobile' and 'desktop' strategies and averages the scores.
    Supports free tier (no API key) or PAGESPEED_API_KEY environment variable.
    """
    global _pagespeed_last_call

    target_url = normalize_url(url)
    api_key = api_key or os.getenv("PAGESPEED_API_KEY") or None
    if api_key == "":
        api_key = None

    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    strategies = ["mobile", "desktop"] if run_both_strategies else ["mobile"]

    raw_responses = {}
    error_msg = None

    for strat in strategies:
        # Throttle free-tier requests to avoid 429s during batch scans
        if not api_key:
            elapsed = _time.time() - _pagespeed_last_call
            if elapsed < _PAGESPEED_FREE_DELAY:
                _time.sleep(_PAGESPEED_FREE_DELAY - elapsed)
        _pagespeed_last_call = _time.time()

        params = {
            "url": target_url,
            "strategy": strat,
            "category": ["performance", "seo", "accessibility", "best-practices"]
        }
        if api_key:
            params["key"] = api_key

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.get(endpoint, params=params, timeout=45)
                if resp.status_code == 200:
                    raw_responses[strat] = resp.json()
                    break
                elif resp.status_code == 429:
                    if attempt < max_retries - 1:
                        wait = (attempt + 1) * 5
                        _time.sleep(wait)
                        continue
                    error_msg = "Google PageSpeed API rate limit reached after retries. Add PAGESPEED_API_KEY to .env for higher quota."
                else:
                    try:
                        err_json = resp.json()
                        err_msg_text = err_json.get("error", {}).get("message", f"HTTP {resp.status_code}")
                    except Exception:
                        err_msg_text = f"HTTP {resp.status_code}"
                    error_msg = f"PageSpeed API error ({strat}): {err_msg_text}"
                    break
            except requests.exceptions.Timeout:
                error_msg = f"Request timed out analyzing site ({strat})."
                break
            except requests.exceptions.RequestException as e:
                error_msg = f"Network error during audit: {str(e)}"
                break

    if not raw_responses:
        return {
            "url": target_url,
            "status": "Error",
            "error": error_msg or "Failed to fetch PageSpeed data.",
            "scores": {},
            "metrics": {},
            "issues": [],
            "raw": {}
        }

    # Helper function to parse 0-100 score from a strategy response
    def extract_scores_from_res(res_data):
        if not res_data:
            return {}
        cats = res_data.get("lighthouseResult", {}).get("categories", {})
        res_scores = {}
        for c in ["performance", "seo", "accessibility", "best-practices"]:
            val = cats.get(c, {}).get("score")
            res_scores[c] = round(val * 100) if val is not None else None
        return res_scores

    mobile_scores = extract_scores_from_res(raw_responses.get("mobile"))
    desktop_scores = extract_scores_from_res(raw_responses.get("desktop"))

    # Compute averaged score across both strategies
    scores = {}
    for c in ["performance", "seo", "accessibility", "best_practices"]:
        cat_key = "best-practices" if c == "best_practices" else c
        m_score = mobile_scores.get(cat_key)
        d_score = desktop_scores.get(cat_key)

        if m_score is not None and d_score is not None:
            scores[c] = int(round((m_score + d_score) / 2.0))
        elif m_score is not None:
            scores[c] = m_score
        elif d_score is not None:
            scores[c] = d_score
        else:
            scores[c] = None

    scores["mobile"] = mobile_scores
    scores["desktop"] = desktop_scores

    # Primary data extraction for metrics and issues (prefer Mobile, fallback Desktop)
    primary = raw_responses.get("mobile") or raw_responses.get("desktop")
    lighthouse = primary.get("lighthouseResult", {})
    audits = lighthouse.get("audits", {})

    # Extract Core Web Vitals & Metrics
    lcp_val = audits.get("largest-contentful-paint", {}).get("numericValue")  # in ms
    lcp_sec = round(lcp_val / 1000.0, 2) if lcp_val is not None else None

    cls_val = audits.get("cumulative-layout-shift", {}).get("numericValue")
    cls_score = round(cls_val, 3) if cls_val is not None else None

    tbt_val = audits.get("total-blocking-time", {}).get("numericValue")
    tbt_ms = round(tbt_val) if tbt_val is not None else None

    # Usability & Security flags
    font_size_score = audits.get("font-size", {}).get("score")
    font_size_issue = (font_size_score is not None and font_size_score < 0.9)

    tap_targets_score = audits.get("tap-targets", {}).get("score")
    tap_targets_issue = (tap_targets_score is not None and tap_targets_score < 0.9)

    viewport_score = audits.get("viewport", {}).get("score")
    viewport_issue = (viewport_score is not None and viewport_score < 1.0)

    is_https = target_url.startswith("https://")
    is_https_audit = audits.get("is-on-https", {}).get("score")
    if is_https_audit is not None:
        is_https = (is_https_audit == 1)

    extracted_metrics = {
        "performance_score": scores.get("performance"),
        "seo_score": scores.get("seo"),
        "accessibility_score": scores.get("accessibility"),
        "best_practices_score": scores.get("best_practices"),
        "lcp_seconds": lcp_sec,
        "cls": cls_score,
        "tbt_ms": tbt_ms,
        "mobile_font_size": font_size_issue,
        "mobile_tap_targets": tap_targets_issue,
        "mobile_viewport": viewport_issue,
        "is_https": is_https
    }

    # Translate failures to Plain-English issues based on thresholds
    issues = []
    for metric_key, config in ISSUE_TRANSLATIONS.items():
        val = extracted_metrics.get(metric_key)
        if val is None:
            continue

        comp = config["comparator"]
        thresh = config["threshold"]
        flagged = False

        if comp == "lt" and isinstance(val, (int, float)) and val < thresh:
            flagged = True
        elif comp == "gt" and isinstance(val, (int, float)) and val > thresh:
            flagged = True
        elif comp == "eq" and val == thresh:
            flagged = True

        if flagged:
            issues.append(config["message"])

    return {
        "url": target_url,
        "status": "Success",
        "error": None,
        "scores": scores,
        "metrics": extracted_metrics,
        "issues": issues,
        "raw": raw_responses
    }


def format_audit_summary(result: dict) -> str:
    """Formats audit result into a clean, human-readable sales summary for emails/Discord."""
    if result.get("status") != "Success":
        return f"[!] PageSpeed Audit Error for `{result.get('url')}`\n> {result.get('error')}"

    url = result.get("url")
    scores = result.get("scores", {})
    issues = result.get("issues", [])
    metrics = result.get("metrics", {})

    lines = []
    lines.append(f"=== Website Audit Summary for `{url}` ===")
    lines.append("")
    lines.append("Scores:")
    lines.append(f"  - Performance: {scores.get('performance', 'N/A')}/100")
    lines.append(f"  - SEO: {scores.get('seo', 'N/A')}/100")
    lines.append(f"  - Accessibility: {scores.get('accessibility', 'N/A')}/100")
    lines.append(f"  - Best Practices: {scores.get('best_practices', 'N/A')}/100")
    lines.append("")

    if metrics.get("lcp_seconds") is not None or metrics.get("tbt_ms") is not None or metrics.get("cls") is not None:
        lines.append("Core Web Vitals:")
        if metrics.get("lcp_seconds") is not None:
            lines.append(f"  - Main Content Load Time (LCP): {metrics['lcp_seconds']}s")
        if metrics.get("tbt_ms") is not None:
            lines.append(f"  - Interactivity Delay (TBT): {metrics['tbt_ms']}ms")
        if metrics.get("cls") is not None:
            lines.append(f"  - Visual Layout Shift (CLS): {metrics['cls']}")
        lines.append("")

    if issues:
        lines.append(f"Key Client-Facing Talking Points ({len(issues)} issues found):")
        for idx, issue in enumerate(issues, 1):
            lines.append(f"  {idx}. {issue}")
    else:
        lines.append("No major client-facing issues detected - site meets performance & usability benchmarks.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Audit website with Google PageSpeed Insights & translate to plain-English issues.")
    parser.add_argument("url", type=str, help="Website URL to audit (e.g. example.com)")
    parser.add_argument("--key", type=str, help="Optional Google PageSpeed API Key (overrides PAGESPEED_API_KEY env var)")
    parser.add_argument("--json", action="store_true", help="Output result as JSON instead of formatted text")

    args = parser.parse_args()

    res = audit_site(args.url, api_key=args.key)

    if args.json:
        # Exclude huge raw response if printing simple JSON unless desired
        print(json.dumps(res, indent=2))
    else:
        print(format_audit_summary(res))


if __name__ == "__main__":
    main()
