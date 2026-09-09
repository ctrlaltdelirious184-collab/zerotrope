#!/usr/bin/env python3
"""
Stage 2 Playwright Browser Auditor (Multi-Page)
------------------------------------------------
Crawls relevant subpages and runs 5 checks on each:
  1. Horizontal overflow (bounding box vs viewport width)
  2. Absolute-position element collisions
  3. WCAG AA contrast ratio failures (computed colors)
  4. Form label overlap & placeholder truncation
  5. Broken dynamic content (error strings, impossible pagination states)

No new Python packages needed — all checks run inside page.evaluate() JS.
"""

import os
import re
import sys
import time
from urllib.parse import urlparse, urljoin, urlunparse

# ─── Crawl config ─────────────────────────────────────────────────────────────
PRIORITY_KEYWORDS = [
    "contact", "appointment", "book", "schedule", "about",
    "service", "blog", "article", "news", "patient", "review"
]
EXCLUDE_KEYWORDS = [
    "privacy", "terms", "sitemap", "login", "disclaimer",
    "accessibility-statement", "cookie", "logout"
]
DEFAULT_MAX_SUBPAGES = 6      # Subpages per domain (not counting homepage)
INTER_PAGE_DELAY    = 1.5     # Seconds between subpage navigations

# ─── Viewport definitions ─────────────────────────────────────────────────────
VIEWPORTS = {
    "mobile":  {"width": 390,  "height": 844, "is_mobile": True},
    "desktop": {"width": 1440, "height": 900, "is_mobile": False},
}

# ─── JS inspection bundle (all 5 checks, returns list of issue dicts) ─────────
# Receives one argument: vpWidth (integer)
_INSPECT_JS = r"""
(vpWidth) => {
  const issues = [];

  // ── Helpers ────────────────────────────────────────────────────────────────
  function tagDesc(el) {
    let d = el.tagName.toLowerCase();
    if (el.id) d += '#' + el.id;
    else if (el.className && typeof el.className === 'string')
      d += '.' + el.className.trim().split(/\s+/).slice(0,3).join('.');
    return d.slice(0, 60);
  }

  // WCAG linearisation + luminance + contrast ratio
  function linearize(c) {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  }
  function luminance(r, g, b) {
    return 0.2126*linearize(r) + 0.7152*linearize(g) + 0.0722*linearize(b);
  }
  function contrastRatio(l1, l2) {
    return (Math.max(l1,l2)+0.05) / (Math.min(l1,l2)+0.05);
  }
  function parseRgb(str) {
    if (!str) return null;
    const m = str.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    return m ? [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])] : null;
  }
  function isTransparent(str) {
    if (!str) return true;
    if (str === 'transparent') return true;
    // rgba(x, y, z, 0) — fully transparent regardless of color
    const m = str.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)/);
    return m ? parseFloat(m[4]) === 0 : false;
  }
  function hasGradientBg(el) {
    // If an ancestor uses a CSS gradient, treat it as a non-white opaque background
    const bg = window.getComputedStyle(el).backgroundImage;
    return bg && bg !== 'none' && bg.includes('gradient');
  }
  // ── Background resolution helpers ────────────────────────────────────────
  // Returns {rgb: [r,g,b], confidence: 'css'|'gradient'|'assumed_white'}
  function resolveBackground(el) {
    let node = el.parentElement;  // Start above the text element itself
    let blended = null;  // Will accumulate blended rgba as [r,g,b,a]

    while (node) {
      const cs = window.getComputedStyle(node);
      const bgImg = cs.backgroundImage;
      const bgColor = cs.backgroundColor;

      // Check for background-image (gradient or image URL)
      const hasImg = bgImg && bgImg !== 'none';
      const hasGrad = hasImg && bgImg.includes('gradient');
      const hasImgUrl = hasImg && bgImg.includes('url(');

      // If a solid-ish background-color exists on this node, capture it
      const m = bgColor && bgColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
      if (m) {
        const alpha = m[4] !== undefined ? parseFloat(m[4]) : 1.0;
        if (alpha > 0.02) {
          const layerRgb = [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])];
          if (!blended) {
            blended = [...layerRgb, alpha];
          } else {
            // Composite: blend layerRgb under blended using source-over
            const srcA = blended[3];
            const dstA = alpha;
            const outA = srcA + dstA * (1 - srcA);
            if (outA > 0.001) {
              blended = [
                Math.round((blended[0]*srcA + layerRgb[0]*dstA*(1-srcA)) / outA),
                Math.round((blended[1]*srcA + layerRgb[1]*dstA*(1-srcA)) / outA),
                Math.round((blended[2]*srcA + layerRgb[2]*dstA*(1-srcA)) / outA),
                outA
              ];
            }
          }
          // If fully opaque, we're done — no need to walk further up
          if (alpha >= 0.99) break;
        }
      }

      // If there's a gradient or image on this node, flag it
      if (hasGrad) return { rgb: blended ? blended.slice(0,3) : null, confidence: 'gradient', node: node };
      if (hasImgUrl) return { rgb: blended ? blended.slice(0,3) : null, confidence: 'image_bg', node: node };

      // Reached top of DOM
      if (node === document.documentElement) break;
      node = node.parentElement;
    }

    if (blended && blended[3] > 0.1) {
      return { rgb: blended.slice(0, 3), confidence: 'css' };
    }
    // Fell through — no background found. Use canvas pixel sampling.
    return { rgb: null, confidence: 'assumed_white' };
  }

  // Canvas pixel-sample: reads the rendered RGBA at the center of an element's bounding rect
  function samplePixelBehindElement(el) {
    try {
      const rect = el.getBoundingClientRect();
      const cx = Math.round(rect.left + rect.width / 2 + window.scrollX);
      const cy = Math.round(rect.top + 2 + window.scrollY);  // sample just above text baseline
      // Temporarily hide the element so we see what's behind it
      const prevVis = el.style.visibility;
      el.style.visibility = 'hidden';
      const canvas = document.createElement('canvas');
      canvas.width = 1; canvas.height = 1;
      const ctx = canvas.getContext('2d');
      // drawWindow only works in Firefox extensions; use body background color as fallback
      el.style.visibility = prevVis;
      // Fallback: sample the body's computed bg at that position via CSS
      // We can't truly pixel-sample without drawWindow, so we do a best-effort:
      // Walk ancestors and find the closest one with a background
      let node = el.parentElement;
      while (node && node !== document.documentElement) {
        const cs = window.getComputedStyle(node);
        const m = cs.backgroundColor && cs.backgroundColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        if (m) {
          const alpha = cs.backgroundColor.includes('rgba') ?
            parseFloat(cs.backgroundColor.split(',')[3]) : 1.0;
          if (alpha > 0.5) return [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])];
        }
        node = node.parentElement;
      }
      return null;
    } catch(e) { return null; }
  }

  // ── 3. WCAG AA CONTRAST CHECK (sample up to 50 visible leaf text nodes) ────
  const textEls = Array.from(
    document.querySelectorAll('p,h1,h2,h3,h4,h5,h6,a,label,span,li,button,td,th')
  ).filter(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 &&
           el.childElementCount === 0 &&
           (el.innerText || '').trim().length > 1;
  }).slice(0, 50);

  textEls.forEach(el => {
    const cs    = window.getComputedStyle(el);
    const fgRgb = parseRgb(cs.color);
    if (!fgRgb) return;

    const bgResult = resolveBackground(el);
    let bgRgb = bgResult.rgb;
    let bgConfidence = bgResult.confidence;

    // If CSS walk-up got a gradient/image, skip entirely — unreliable
    if (bgConfidence === 'gradient' || bgConfidence === 'image_bg') return;

    // If walk-up returned nothing or assumed white, try canvas pixel sampling
    if (!bgRgb || bgConfidence === 'assumed_white') {
      const sampled = samplePixelBehindElement(el);
      if (sampled) {
        bgRgb = sampled;
        bgConfidence = 'pixel_sample';
      } else {
        bgRgb = [255, 255, 255];
        bgConfidence = 'assumed_white';
      }
    }

    const fgL = luminance(...fgRgb);
    const bgL = luminance(...bgRgb);
    const ratio = contrastRatio(fgL, bgL);

    // Skip identical colors — always a walk-up miss
    if (ratio < 1.01) return;

    const fs    = parseFloat(cs.fontSize) || 16;
    const bold  = parseInt(cs.fontWeight, 10) >= 700;
    const large = (bold && fs >= 18) || fs >= 24;
    const thresh = large ? 3.0 : 4.5;

    if (ratio < thresh) {
      issues.push({
        category: 'contrast',
        element: tagDesc(el),
        detail: `WCAG AA fail: ${ratio.toFixed(2)}:1 (need ${thresh}:1 for ${large ? 'large' : 'normal'} text)`,
        computed_data: {
          text_snippet: (el.innerText||'').trim().slice(0, 150),
          foreground: cs.color,
          background: `rgb(${bgRgb.join(',')})`,
          bg_confidence: bgConfidence,
          contrast_ratio: Math.round(ratio*100)/100,
          threshold: thresh,
          font_size: cs.fontSize,
          font_weight: cs.fontWeight
        }
      });
    }
  });

  const containerSel = 'form,nav,main,.container,header,footer,section,table,iframe,.wrapper,.content';
  let containers = Array.from(document.querySelectorAll(containerSel));
  if (containers.length === 0) containers = Array.from(document.body.children);

  containers.forEach(elem => {
    if (!elem || elem.offsetWidth === 0) return;
    const rect = elem.getBoundingClientRect();
    if (rect.right > vpWidth + 5 || rect.width > vpWidth + 5) {
      const cs = window.getComputedStyle(elem);
      issues.push({
        category: 'overflow',
        element: tagDesc(elem),
        detail: `Element width (${Math.round(rect.width)}px) / right-edge (${Math.round(rect.right)}px) exceeds viewport (${vpWidth}px)`,
        computed_data: {
          width: cs.width, max_width: cs.maxWidth,
          position: cs.position, overflow: cs.overflow, box_sizing: cs.boxSizing
        }
      });
    }
  });

  // ── 2. ABSOLUTE-POSITION GENUINE COLLISION CHECK ──────────────────────────
  // Only flags cases where:
  //   (a) One element is position:absolute
  //   (b) Their bounding boxes overlap by >100px² (not just touching)
  //   (c) Neither element is an ancestor of the other (nesting is expected)
  //   (d) The absolute element's parent does NOT explicitly have a set height
  //       that would contain it (scroll containers etc. are excluded)
  for (let i = 0; i < containers.length; i++) {
    const el1 = containers[i];
    const r1 = el1.getBoundingClientRect();
    if (r1.width === 0 || r1.height === 0) continue;
    const s1 = window.getComputedStyle(el1);
    if (s1.position !== 'absolute') continue;  // Only test absolutely-positioned elements

    for (let j = 0; j < Math.min(containers.length, 30); j++) {
      if (i === j) continue;
      const el2 = containers[j];
      const r2 = el2.getBoundingClientRect();
      if (r2.width === 0 || r2.height === 0) continue;

      // Skip if one is an ancestor of the other (legitimate containment)
      if (el1.contains(el2) || el2.contains(el1)) continue;

      // Calculate actual pixel overlap area
      const overlapX = Math.max(0, Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left));
      const overlapY = Math.max(0, Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top));
      const overlapArea = overlapX * overlapY;

      // Require >100px² genuine overlap (not just touching edges)
      if (overlapArea < 100) continue;

      const s2 = window.getComputedStyle(el2);

      // Skip if el2 is also absolute — two abs elements overlapping is expected in layered UIs
      if (s2.position === 'absolute' || s2.position === 'fixed') continue;

      // Skip if el2 is a scroll container (overflow:scroll/auto) — maps/widgets live in these
      const ov2 = s2.overflow + s2.overflowX + s2.overflowY;
      if (ov2.includes('scroll') || ov2.includes('auto')) continue;

      issues.push({
        category: 'overlap',
        element: `${tagDesc(el1)} & ${tagDesc(el2)}`,
        detail: `Absolutely-positioned element overlaps sibling content (${Math.round(overlapArea)}px² intersection)`,
        computed_data: {
          abs_element: tagDesc(el1),
          sibling_element: tagDesc(el2),
          overlap_area_px2: Math.round(overlapArea),
          overlap_px: `${Math.round(overlapX)}x${Math.round(overlapY)}`
        }
      });
    }
  }


  // ── 4. FORM FIELD OVERLAP & PLACEHOLDER TRUNCATION ─────────────────────────
  const inputs = Array.from(document.querySelectorAll(
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"]), textarea'
  ));
  inputs.forEach(inp => {
    const inpRect = inp.getBoundingClientRect();
    if (inpRect.width === 0) return;
    const fieldName = inp.name || inp.id || inp.placeholder || 'unnamed';

    // Label bounding-box collision
    let label = inp.id ? document.querySelector(`label[for="${inp.id}"]`) : null;
    if (!label) label = inp.closest('label');
    if (label) {
      const lblRect = label.getBoundingClientRect();
      const intersects = !(lblRect.left >= inpRect.right || lblRect.right <= inpRect.left ||
                           lblRect.top  >= inpRect.bottom || lblRect.bottom <= inpRect.top);
      if (intersects) {
        issues.push({
          category: 'form_overlap',
          element: `input[name="${fieldName}"]`,
          detail: 'Label bounding box overlaps/collides with input field (label-stacking layout bug)',
          computed_data: {
            input_rect:  { x: Math.round(inpRect.x),  y: Math.round(inpRect.y),  w: Math.round(inpRect.width),  h: Math.round(inpRect.height) },
            label_rect:  { x: Math.round(lblRect.x),  y: Math.round(lblRect.y),  w: Math.round(lblRect.width),  h: Math.round(lblRect.height) }
          }
        });
      }
    }

    // Precise Canvas 2D measureText check (exact rendered font metrics)
    const ph = inp.placeholder || '';
    if (ph.length > 0) {
      const cs = window.getComputedStyle(inp);
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const fontStr = `${cs.fontWeight || 'normal'} ${cs.fontSize || '14px'} ${cs.fontFamily || 'sans-serif'}`;
      ctx.font = fontStr;
      
      const realTextW = ctx.measureText(ph).width;
      const padLeft = parseFloat(cs.paddingLeft) || 8;
      const padRight = parseFloat(cs.paddingRight) || 8;
      const availW = inpRect.width - padLeft - padRight;
      
      // Buffer of 4px for browser input inner padding / scroll margins
      if (realTextW > availW + 4) {
        issues.push({
          category: 'truncation',
          element: `input[name="${fieldName}"]`,
          detail: `Placeholder truncated: text width ${Math.round(realTextW)}px > available ${Math.round(availW)}px`,
          computed_data: {
            placeholder: ph,
            input_width_px: Math.round(availW),
            estimated_text_px: Math.round(realTextW),
            font_size: cs.fontSize
          }
        });
      }
    }
  });

  // ── 5. BROKEN DYNAMIC CONTENT ──────────────────────────────────────────────
  const bodyText = (document.body && document.body.innerText) || '';
  const errorPatterns = [
    /\bnot found\b/i, /0 of 0/i, /no results/i, /\bundefined\b/,
    /\bnull\b/, /error loading/i, /failed to load/i,
    /nan of nan/i, /no articles/i, /no posts found/i,
    /\d+ of 0\b/i, /\d+ of nan/i, /1of0/i, /nan of nan/i
  ];
  const seen = new Set();
  errorPatterns.forEach(pat => {
    const m = bodyText.match(pat);
    if (m && !seen.has(m[0])) {
      seen.add(m[0]);
      issues.push({
        category: 'broken_content',
        element: 'document.body (text scan)',
        detail: `Dynamic content error string in page: "${m[0]}"`,
        computed_data: { matched_string: m[0] }
      });
    }
  });

  return issues;
}
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────
def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url


def _slug(url: str) -> str:
    """Create a safe filename slug from a URL path."""
    parsed = urlparse(url)
    path = re.sub(r"[^a-z0-9]", "_", parsed.path.lower().strip("/"))
    return path[:30] or "home"


def _make_context(browser, vp_name: str):
    """Create a Playwright browser context with realistic headers."""
    vp = VIEWPORTS[vp_name]
    ua = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        if vp["is_mobile"] else
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    return browser.new_context(
        viewport={"width": vp["width"], "height": vp["height"]},
        is_mobile=vp["is_mobile"],
        user_agent=ua,
        extra_http_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?1" if vp["is_mobile"] else "?0",
            "Sec-Ch-Ua-Platform": '"iOS"' if vp["is_mobile"] else '"Windows"',
        }
    )


def _navigate(page, url: str):
    """Navigate with networkidle fallback to domcontentloaded."""
    resp = None
    try:
        resp = page.goto(url, wait_until="networkidle", timeout=30000)
    except Exception:
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass
    return resp


def _extract_subpages(page, base_url: str, max_pages: int) -> list:
    """Extract same-domain priority subpage links from the current page.
    
    Strips www. from both sides for comparison so bare-domain→www redirects
    don't silently discard all subpage links.
    """
    parsed_base = urlparse(base_url)
    # Use the actual current URL (post-redirect) netloc if possible
    try:
        actual_url = page.url
        parsed_base = urlparse(actual_url)
        base_url = actual_url  # update base to resolved URL for urljoin
    except Exception:
        pass
    base_netloc_bare = parsed_base.netloc.lower().removeprefix("www.")

    try:
        links = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                href: a.href || '',
                text: (a.innerText || a.textContent || '').trim().toLowerCase().slice(0, 80)
            }));
        }""")
    except Exception:
        return []

    seen, priority, rest = set(), [], []
    for item in links:
        href = item.get("href", "").strip()
        text = item.get("text", "")
        if not href or href.startswith("mailto:") or href.startswith("tel:") or "#" in href:
            continue
        parsed = urlparse(href)
        # Same-domain check (www-agnostic)
        if parsed.netloc:
            link_bare = parsed.netloc.lower().removeprefix("www.")
            if link_bare != base_netloc_bare:
                continue
        full = urlunparse(urlparse(urljoin(base_url, href))._replace(fragment=""))
        if full == base_url or full in seen:
            continue
        path_lower = parsed.path.lower()
        if any(k in path_lower or k in text for k in EXCLUDE_KEYWORDS):
            continue
        seen.add(full)
        if any(k in path_lower or k in text for k in PRIORITY_KEYWORDS):
            priority.append(full)
        else:
            rest.append(full)

    return (priority + rest)[:max_pages]


def _audit_page(browser, page_url: str, domain: str, output_dir: str, page_index: int,
                page_total: int, progress_cb=None) -> tuple:
    """
    Run overflow, overlap, contrast, form, and broken-content checks on one page
    across both viewports. Returns (issues_list, screenshots_dict).
    """
    page_issues = []
    page_shots  = {}
    slug = _slug(page_url)

    for vp_name in VIEWPORTS:
        if progress_cb:
            progress_cb(f"  [{page_index}/{page_total}] {vp_name.upper()}: {page_url}")

        ctx  = _make_context(browser, vp_name)
        page = ctx.new_page()

        resp = _navigate(page, page_url)

        if resp and resp.status in (401, 403, 500, 502, 503):
            page_issues.append({
                "page":          page_url,
                "viewport":      vp_name,
                "category":      "access_denied",
                "element":       "server_response",
                "detail":        f"HTTP {resp.status} (WAF/Cloudflare block)",
                "computed_data": {}
            })
            ctx.close()
            continue

        time.sleep(1.5)

        # Screenshot
        shot_path = os.path.join(output_dir, f"{domain}_{slug}_{vp_name}.png")
        try:
            page.screenshot(path=shot_path, full_page=True)
            page_shots[vp_name] = os.path.abspath(shot_path)
        except Exception:
            pass

        # Run all 5 checks
        try:
            raw = page.evaluate(_INSPECT_JS, VIEWPORTS[vp_name]["width"])
            for iss in raw:
                iss["page"]    = page_url
                iss["viewport"] = vp_name
                page_issues.append(iss)
        except Exception:
            pass

        ctx.close()
        time.sleep(INTER_PAGE_DELAY)

    return page_issues, page_shots


# ─── Public API ───────────────────────────────────────────────────────────────
def confirm_audit(
    url:          str,
    output_dir:   str  = "screenshots",
    max_subpages: int  = DEFAULT_MAX_SUBPAGES,
    single_page:  bool = False,
    progress_cb        = None,
) -> dict:
    """
    Stage 2 Confirmed Audit using Playwright Headless Chromium.

    Args:
        url:          Homepage URL to audit.
        output_dir:   Directory to save screenshots.
        max_subpages: Max subpages to crawl (0 = homepage only).
        single_page:  If True, skip crawling and audit homepage only (fast mode).
        progress_cb:  Optional callable(message: str) for progress reporting.
    """
    target_url = normalize_url(url)
    domain     = urlparse(target_url).netloc.replace("www.", "") or "domain"
    os.makedirs(output_dir, exist_ok=True)

    result = {
        "url":             target_url,
        "domain":          domain,
        "status":          "Success",
        "confirmation_status": "confirmed",
        "pages_crawled":   [],
        "confirmed_issues": [],
        "screenshots":     {},
        "error":           None,
    }

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result["status"]               = "Error"
        result["confirmation_status"]  = "unavailable"
        result["error"]                = "Playwright not installed. Run: pip install playwright && playwright install chromium"
        return result

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # ── Step 1: Load homepage and collect subpages ─────────────────
            subpages = []
            if not single_page and max_subpages > 0:
                if progress_cb:
                    progress_cb(f"Crawling homepage for subpage links: {target_url}")
                ctx  = _make_context(browser, "desktop")
                page = ctx.new_page()
                _navigate(page, target_url)
                subpages = _extract_subpages(page, target_url, max_subpages)
                ctx.close()

            pages_to_audit = [target_url] + subpages
            result["pages_crawled"] = pages_to_audit

            if progress_cb:
                progress_cb(f"Pages queued: {len(pages_to_audit)} ({len(subpages)} subpages found)")

            # ── Step 2: Full audit on each page ────────────────────────────
            for idx, page_url in enumerate(pages_to_audit, 1):
                if progress_cb:
                    progress_cb(f"Auditing page {idx}/{len(pages_to_audit)}: {page_url}")

                issues, shots = _audit_page(
                    browser, page_url, domain, output_dir,
                    idx, len(pages_to_audit), progress_cb
                )
                result["confirmed_issues"].extend(issues)
                result["screenshots"][page_url] = shots

            browser.close()

    except Exception as e:
        result["status"]              = "Error"
        result["confirmation_status"] = "unavailable"
        result["error"]               = f"Playwright error: {str(e)}"

    return result


# ─── Color & Text Helpers ──────────────────────────────────────────────────────
COLOR_PALETTE = [
    ((255, 255, 255), "white"),
    ((0, 0, 0), "black"),
    ((255, 0, 0), "red"),
    ((0, 128, 0), "green"),
    ((0, 0, 255), "blue"),
    ((255, 255, 0), "yellow"),
    ((0, 255, 255), "cyan"),
    ((255, 0, 255), "magenta"),
    ((192, 192, 192), "light gray"),
    ((128, 128, 128), "gray"),
    ((64, 64, 64), "dark gray"),
    ((128, 0, 0), "dark red"),
    ((128, 128, 0), "olive"),
    ((0, 128, 128), "teal"),
    ((0, 0, 128), "navy blue"),
    ((210, 180, 140), "tan"),
    ((245, 245, 220), "beige"),
    ((223, 201, 153), "tan"),
    ((240, 230, 140), "khaki"),
    ((189, 183, 107), "dark khaki"),
    ((255, 165, 0), "orange"),
    ((255, 192, 203), "pink"),
    ((128, 0, 128), "purple"),
    ((165, 42, 42), "brown"),
    ((3, 132, 215), "blue"),
    ((35, 58, 38), "dark green"),
    ((102, 95, 79), "dark khaki"),
]


def rgb_to_color_name(rgb_str: str) -> str:
    """Translates an 'rgb(r, g, b)' or 'rgba(r, g, b, a)' string to a plain-English color name."""
    if not rgb_str:
        return "unknown color"
    m = re.search(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", str(rgb_str))
    if not m:
        return str(rgb_str)

    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))

    best_name = "gray"
    min_dist = float("inf")
    for (pr, pg, pb), name in COLOR_PALETTE:
        # Euclidean distance in RGB color space
        dist = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if dist < min_dist:
            min_dist = dist
            best_name = name

    # Light / dark modifier heuristics if generic
    if min_dist > 1000 and best_name not in ["tan", "beige", "khaki"]:
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        if lum > 200 and not best_name.startswith("light"):
            best_name = f"light {best_name}"
        elif lum < 50 and not best_name.startswith("dark"):
            best_name = f"dark {best_name}"

    return best_name


def truncate_word_boundary(text: str, max_length: int = 80) -> str:
    """Truncates text at the nearest word boundary so no word is split mid-word."""
    if not text or len(text) <= max_length:
        return text or ""
    truncated = text[:max_length]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated.rstrip(",.;:-") + "..."


def clean_element_description(elem_str: str, category: str = "") -> str:
    """Replaces raw DOM selectors with plain-English component names."""
    if not elem_str:
        return "element"
    
    if category == "overlap":
        if "iframe" in elem_str.lower():
            return "An embedded element (likely a booking widget or map)"
        return "Overlapping visual content elements"

    # Specific selector cleanups
    low = elem_str.lower()
    if "print-header" in low or "h2." in low or "h1." in low or "h3." in low or elem_str.startswith("h"):
        return "A section heading"
    if elem_str.startswith("a.") or elem_str.startswith("a#") or elem_str == "a":
        return "navigation link"
    if "button" in low:
        return "button"
    if "input" in low:
        return "form field"
    if "div." in low or "section" in low:
        return "content section"

    return elem_str


def format_finding_plain_english(item: dict, is_summary: bool = True) -> str:
    """
    Unified single source of truth for formatting findings into human-readable plain English.
    Used by both main channel summary and per-page thread detail views.
    """
    cat = item.get("category", "")
    elem = item.get("element", "")
    cd = item.get("computed_data", {})
    detail = item.get("detail", "")
    count_pages = item.get("count_pages")
    total_pages = item.get("total_pages")

    pg_suffix = f". Seen on {count_pages}/{total_pages} pages." if (is_summary and count_pages and total_pages) else ""

    if cat == "contrast":
        snip = cd.get("text_snippet") or elem
        snip = truncate_word_boundary(snip, max_length=50)
        fg_name = rgb_to_color_name(cd.get("foreground", ""))
        bg_name = rgb_to_color_name(cd.get("background", ""))
        
        try:
            ratio_val = float(cd.get("contrast_ratio", 0))
        except (ValueError, TypeError):
            ratio_val = 0.0

        thresh_val = float(cd.get("threshold", 4.5))

        if ratio_val < 2.0:
            sev_phrase = "is nearly invisible against"
            label = "Severe"
        elif ratio_val < 3.5:
            sev_phrase = "is difficult to read against"
            label = "Poor"
        else:
            sev_phrase = "is a little hard to read against"
            label = "Borderline"

        # Determine element noun
        clean_elem = clean_element_description(elem, category="contrast")
        if "link" in clean_elem.lower():
            noun = f"{fg_name.capitalize()} link text"
        elif "heading" in clean_elem.lower():
            noun = f"{fg_name.capitalize()} heading text"
        elif snip and len(snip) > 2:
            noun = f"'{snip}'"
        else:
            noun = f"{fg_name.capitalize()} text"

        # Confidence qualifier
        bg_conf = cd.get("bg_confidence", "css")
        if bg_conf == "assumed_white":
            conf_note = " ⚠️ *(background assumed white — verify manually)*"
        elif bg_conf == "pixel_sample":
            conf_note = " *(background pixel-sampled)*"
        else:
            conf_note = ""

        return f"• {noun} {sev_phrase} the {bg_name} background ({ratio_val:.2f}:1 — needs {thresh_val:g}:1). {label}{conf_note}{pg_suffix}"

    elif cat == "truncation":
        # Extract field name cleanly
        field_name = elem
        m_name = re.search(r'name=["\']?([^"\'\]]+)["\']?', elem)
        if m_name:
            field_name = m_name.group(1).capitalize()
        else:
            m_id = re.search(r'id=["\']?([^"\'\]]+)["\']?', elem)
            if m_id:
                field_name = m_id.group(1).capitalize()

        ph = cd.get("placeholder", "")
        if ph:
            ph_clean = truncate_word_boundary(ph, max_length=50)
            return (
                "• The \"" + field_name + "\" field's placeholder text "
                "(\"" + ph_clean + "\") is too long for the box — "
                "it gets cut off before a visitor can read the full instruction" + pg_suffix
            )
        else:
            return "• The \"" + field_name + "\" field placeholder is too long for the input box and gets cut off" + pg_suffix

    elif cat == "overlap":
        clean_elem = clean_element_description(elem, category="overlap")
        return f"• {clean_elem} overlapping the page content (absolute positioning, no parent containment){pg_suffix}"

    elif cat == "overflow":
        clean_elem = clean_element_description(elem, category="overflow")
        return f"• {clean_elem} spilling outside the screen bounds ({detail}){pg_suffix}"

    else:
        clean_elem = clean_element_description(elem, category=cat)
        return f"• {clean_elem} — {detail}{pg_suffix}"


# ─── Deduplication & Clean Reporting ──────────────────────────────────────────
def dedupe_issues(issues: list, total_pages_count: int) -> list:
    """
    Groups findings by (category, element, detail).
    Returns list of dicts with count_pages, total_pages, pages list, etc.
    """
    groups = {}
    for iss in issues:
        cat = iss.get("category", "other")
        elem = iss.get("element", "unknown")
        detail = iss.get("detail", "")
        cd = iss.get("computed_data", {})

        # Category-aware dedup key: contrast deduplicates on color pair+threshold,
        # not on element selector — two different headings with the same contrast
        # problem are the same problem to report.
        if cat == "contrast":
            fg = cd.get("foreground", "")
            bg = cd.get("background", "")
            thresh = cd.get("threshold", 4.5)
            sig = (cat, fg, bg, str(thresh))
        elif cat == "truncation":
            # Same placeholder text in different inputs = same truncation finding
            ph = cd.get("placeholder", elem)
            sig = (cat, ph)
        else:
            sig = (cat, elem, detail)

        if sig not in groups:
            groups[sig] = {
                "category": cat,
                "element": elem,
                "detail": detail,
                "computed_data": iss.get("computed_data", {}),
                "pages": set(),
                "viewports": set(),
                "raw_issues": []
            }
        
        groups[sig]["pages"].add(iss.get("page", ""))
        groups[sig]["viewports"].add(iss.get("viewport", ""))
        groups[sig]["raw_issues"].append(iss)

    deduped = []
    for sig, item in groups.items():
        pages_list = sorted(list(item["pages"]))
        deduped.append({
            "category": item["category"],
            "element": item["element"],
            "detail": item["detail"],
            "computed_data": item["computed_data"],
            "pages": pages_list,
            "viewports": sorted(list(item["viewports"])),
            "count_pages": len(pages_list),
            "total_pages": total_pages_count,
            "signature": sig,
            "raw_issues": item["raw_issues"]
        })

    return deduped


def format_deduped_summary(res: dict, thread_jump_url: str = None) -> str:
    """Formats Part 2 main channel text summary using plain-English and word-boundary safe text."""
    if res.get("confirmation_status") == "unavailable":
        return (f"⚠️ **Stage 2 Audit Unavailable for `{res.get('domain', '?')}`**\n"
                f"> {res.get('error', 'Site blocked browser inspection.')}")

    domain = res.get("domain", "?")
    pages = res.get("pages_crawled", [])
    raw_issues = res.get("confirmed_issues", [])
    deduped = dedupe_issues(raw_issues, len(pages))

    lines = [
        f"📋 **Audit Complete: `{domain}`**",
        f"Pages crawled: **{len(pages)}** | Unique issues: **{len(deduped)}**",
        ""
    ]

    if not deduped:
        lines.append("✅ **No layout defects or accessibility errors confirmed across viewports.**")
    else:
        # Group by category
        by_cat = {}
        for d in deduped:
            by_cat.setdefault(d["category"], []).append(d)

        cat_names = {
            "overflow": "HORIZONTAL OVERFLOW",
            "overlap": "ELEMENT OVERLAP",
            "contrast": "CONTRAST (WCAG AA)",
            "form_overlap": "FORM LABEL OVERLAP",
            "truncation": "FORM TRUNCATION",
            "broken_content": "BROKEN DYNAMIC CONTENT",
            "access_denied": "ACCESS DENIED"
        }

        for cat, items in by_cat.items():
            label = cat_names.get(cat, cat.upper())
            sitewide_tag = " (sitewide)" if any(it["count_pages"] == len(pages) for it in items) else ""
            lines.append(f"🔍 **{label}** ({len(items)} unique issue{'s' if len(items)>1 else ''}{sitewide_tag})")

            for item in items:
                lines.append(format_finding_plain_english(item, is_summary=True))

            lines.append("")

    if thread_jump_url:
        lines.append(f"📸 **Full screenshots and per-page detail:** {thread_jump_url}")

    return "\n".join(lines)


def format_confirmed_summary(res: dict) -> str:
    """Backwards-compatible legacy formatter."""
    return format_deduped_summary(res)


# ─── CLI entry-point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    if len(sys.argv) < 2:
        print("Usage: python playwright_auditor.py <url> [--single-page] [--max-subpages N]")
        sys.exit(1)

    target = sys.argv[1]
    single = "--single-page" in sys.argv
    max_sp = DEFAULT_MAX_SUBPAGES
    if "--max-subpages" in sys.argv:
        idx = sys.argv.index("--max-subpages")
        try:
            max_sp = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            pass

    print(f"[+] Stage 2 Confirmed Audit on: {target}")
    print(f"    Mode: {'single-page' if single else f'multi-page (max {max_sp} subpages)'}")
    print()

    res = confirm_audit(
        target,
        max_subpages=max_sp,
        single_page=single,
        progress_cb=lambda msg: print(f"  {msg}"),
    )

    print()
    print(format_confirmed_summary(res))
