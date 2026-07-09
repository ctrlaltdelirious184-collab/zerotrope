from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel
import uuid
import os
import httpx
import threading

# Import core Zerotrope logic
from agents.research import ResearchAgent
from agents.intelligence import IntelligenceAgent
from fastapi.middleware.cors import CORSMiddleware
from utils.db_manager import LeadDatabase
from utils.ai_client import AIClient
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

load_dotenv()

app = FastAPI(title="Zerotrope Strategic Bridge")

# Manual CORS handling for Cloudflare Tunnel stability
class CORSMiddlewareManual(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        if request.method == "OPTIONS":
            response = StarletteResponse()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, x-api-key, ngrok-skip-browser-warning"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, x-api-key, ngrok-skip-browser-warning"
        return response

app.add_middleware(CORSMiddlewareManual)

db = LeadDatabase()
ollama_client = AIClient()

# Configuration
API_KEY = os.getenv("ZEROTROPE_API_KEY", "ZEROTROPE_SECURE_9922")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID = "1495146563469836299"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")


class DeliverRequest(BaseModel):
    job_id: str
    name: str
    email: str

class AuditRequest(BaseModel):
    input_text: str


class AuditResponse(BaseModel):
    status: str
    message: str
    narrative_summary: str
    unique_angle: str = ""
    biz_name: str = ""


class AuditJobResponse(BaseModel):
    job_id: str
    status: str


# In-memory job store: job_id -> {result, timestamp}
job_store: dict = {}
import time

def cleanup_job_store():
    """Remove jobs older than 10 minutes to prevent memory leak."""
    cutoff = time.time() - 600
    stale = [jid for jid, v in job_store.items() if isinstance(v, dict) and v.get("_ts", 0) < cutoff]
    for jid in stale:
        del job_store[jid]
    if stale:
        print(f"[JobStore] Cleaned up {len(stale)} stale jobs.")


def send_discord_notification(biz_name, primary_gap, narrative, input_url):
    """Sends a surgical diagnostic alert to the Zerotrope Discord channel."""
    if not DISCORD_TOKEN:
        print("[Discord] Token missing — lead saved to DB but not sent to Discord.")
        return

    message = (
        f"🌪️ **ZEROTROPE DIAGNOSTIC ALERT**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Target:** {biz_name}\n"
        f"**Intel URL:** {input_url}\n"
        f"**Failure Point:** {primary_gap}\n\n"
        f"**The Tease (What they received):**\n> {narrative}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Action Required:** Follow up at architect@zerotrope.co or DM @zerotropeco"
    )

    try:
        httpx.post(
            f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages",
            headers={
                "Authorization": f"Bot {DISCORD_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"content": message},
            timeout=10
        )
        print(f"[Discord] Alert sent for {biz_name}")
    except Exception as e:
        print(f"[Discord Error] {e}")


@app.get("/")
def read_root():
    return {"status": "Zerotrope Strategic Bridge is Online"}


def run_audit_job(job_id: str, input_text: str):
    """Runs the full audit pipeline in a background thread and stores the result."""
    try:
        request = AuditRequest(input_text=input_text)
        # reuse the core logic below
        result = _execute_audit(input_text)
        result["_ts"] = time.time()
        job_store[job_id] = result
    except Exception as e:
        print(f"[Job Error] {e}")
        job_store[job_id] = {
            "status": "error",
            "message": "Diagnostic system timeout.",
            "narrative_summary": "I'm having trouble analyzing this business right now. Please try again.",
            "unique_angle": "",
            "_ts": time.time()
        }


# URL dedup cache: url -> (job_id, timestamp)
url_cache: dict = {}

@app.post("/audit", response_model=AuditJobResponse)
def trigger_audit(request: AuditRequest, x_api_key: str = Header(None)):
    # Security gate
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    cleanup_job_store()

    # Duplicate URL protection — reuse job if same URL submitted within 30 seconds
    url_key = request.input_text.strip().lower()
    if url_key in url_cache:
        existing_job_id, ts = url_cache[url_key]
        if time.time() - ts < 30:
            print(f"[Dedup] Reusing job {existing_job_id} for {url_key}")
            return AuditJobResponse(job_id=existing_job_id, status="pending")

    job_id = str(uuid.uuid4())
    job_store[job_id] = {"_ts": time.time()}  # mark as pending with timestamp
    url_cache[url_key] = (job_id, time.time())
    thread = threading.Thread(target=run_audit_job, args=(job_id, request.input_text), daemon=True)
    thread.start()
    return AuditJobResponse(job_id=job_id, status="pending")


@app.get("/status/{job_id}", response_model=AuditResponse)
def get_audit_status(job_id: str, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job_store[job_id]
    if result is None or (isinstance(result, dict) and "status" not in result):
        return AuditResponse(status="pending", message="Processing...", narrative_summary="", unique_angle="")
    clean = {k: v for k, v in result.items() if not k.startswith("_")}
    return AuditResponse(**clean)


def _execute_audit(input_text: str) -> dict:
    """Core audit logic extracted for background thread use."""
    try:
        # 1. Intelligence gathering — two-pass pipeline
        research_results = ResearchAgent().run(input_text)
        intel_results = IntelligenceAgent().run(research_results)

        # Clean business name — use AI-extracted name first, fallback to title tag, then URL
        raw_title = research_results.get("raw_data", {}).get("title", "")

        from urllib.parse import urlparse
        parsed_url = urlparse(input_text)
        url_domain = parsed_url.netloc.replace("www.", "").split(".")[0].replace("-", " ").title()

        # Service keywords that indicate the title is an SEO descriptor, not a brand name.
        service_keywords = {"clogged", "drain", "broken", "emergency", "repair", "leaking"}
        
        raw_biz_name = (
            intel_results.get("business_name")
            or (raw_title.split("|")[0].strip() if raw_title else "")
            or url_domain
            or input_text
        )
        
        # Heuristic: If name starts with a 'problem' word, it's likely a website title, not the brand.
        if any(raw_biz_name.lower().startswith(kw) for kw in service_keywords) and url_domain:
            raw_biz_name = url_domain

        # Length filter: if name is too long (likely full of keywords), take first 3 words
        if len(raw_biz_name.split()) > 4:
            biz_name = " ".join(raw_biz_name.split()[:3]).strip().title()
        else:
            biz_name = raw_biz_name.strip().title()

        placeholder_phrases = [
            "no brand name", "brand name not", "not provided", "unknown",
            "n/a", "none", "business name", "company name"
        ]
        if not biz_name or len(biz_name.strip()) < 2 or any(p in biz_name.lower() for p in placeholder_phrases):
            biz_name = url_domain or input_text

        primary_gap = intel_results.get("primary_gap", "commodity positioning with no differentiation")
        comp_insight = intel_results.get("competitor_insight", "rivals are using outdated templates")
        usp = intel_results.get("contrarian_usp", "a foundational strategic overhaul")
        
        # Clean terminology
        raw_terminology = intel_results.get("terminology", "client")
        terminology = raw_terminology.split("|")[0].strip().split("/")[0].strip().lower() or "client"
        business_type = intel_results.get("business_type", "business")
        gap_evidence = intel_results.get("gap_evidence", "")
        geo_query = intel_results.get("_geo_query", "")
        geo_appeared = intel_results.get("_geo_appeared", True)
        no_gap_found = intel_results.get("no_gap_found", False)
        unique_angle = f"GAP: {primary_gap} | USP: {usp} | COMP: {comp_insight}"

        # 2. Zerotrope Humanizer
        narrative = ""
        
        # Special check: If we found no on-page gap but they ARE invisible in search
        is_invisible = "GEO INVISIBILITY" in primary_gap.upper() or "AEO" in primary_gap.upper() or intel_results.get("gap_dimension") == "search" or (no_gap_found and geo_query and not geo_appeared)

        if is_invisible:
            humanize_prompt = f"""
[SYSTEM: HOOK GENERATION MODE - INVISIBILITY FOCUS]
You are a high-end strategist who just audited {biz_name}.
Write EXACTLY 3 sentences addressed to the owner.

AUDIT FACTS:
- Business: {biz_name}
- Search Proof: {geo_query} was searched and they were invisible.
- The Cost: Active buyers are finding competitors instead.

Sentence 1: Start on a high note about their site, but pivot to the test. "{biz_name} has a solid digital presence on the surface, but I ran a search for '{geo_query}' and you weren't on the list."
Sentence 2: Explain the cost. "Right now, your competitors are capturing all that high-intent traffic because your site isn't structured for AI search or GEO discovery."
Sentence 3: The Close. "We've put together a custom growth plan for {biz_name} - reach us at architect@zerotrope.co whenever you're ready to see it."

UNIVERSAL RULES:
- Output ONLY the 3 sentences. No AI preamble.
- DO NOT use em-dashes. Use standard hyphens.
- Keep it punchy.
"""
        elif no_gap_found:
            # Derive generic category
            generic_types = {"business", "company", "organization", "brand", "website", ""}
            if business_type and business_type.lower().strip() not in generic_types:
                search_category = business_type.lower().strip()
            else:
                search_category = f"{terminology} service like {biz_name}"

            humanize_prompt = f"""
[SYSTEM: HOOK GENERATION MODE - GENERAL QUALITY]
You are a strategist who audited {biz_name}. Their site is solid.
Write EXACTLY 3 sentences addressed to the owner.

Sentence 1: "{biz_name} has a well-built site - strong messaging, clear CTAs, and visible credibility."
Sentence 2: "The gap isn't on the page, it's upstream: when someone asks ChatGPT to recommend a {search_category}, your name doesn't come up - not because you're less qualified, but because your content isn't structured for AI search yet."
Sentence 3: "We've put together a custom growth plan for {biz_name} - reach us at architect@zerotrope.co whenever you're ready to see it."

UNIVERSAL RULES:
- Output ONLY the 3 sentences. No AI preamble.
"""
        else:
            humanize_prompt = f"""
[SYSTEM: HOOK GENERATION MODE - CONVERSION FOCUS]
You are a strategist who just finished auditing {biz_name}.
You speak like a sharp consultant - not a marketer.
Write a response addressed DIRECTLY to the business owner.

AUDIT FACTS:
- Business: {biz_name}
- Primary Gap: {primary_gap}
- Evidence: {gap_evidence}
- Opportunity: {usp}

YOUR OBJECTIVE:
Point out a real, painful problem on their site accurately - but DO NOT reveal the complete solution.

SCENARIO A - A SPECIFIC GAP WAS FOUND:
Write exactly 3 sentences:
Sentence 1: "{biz_name}, I was looking at your site and noticed your main button just says '{gap_evidence}' instead of stating a specific outcome."
Sentence 2: "Right now, your competitors are capturing those high-value visitors because they clearly position their actual expertise, and you're leaving your best assets buried."
Sentence 3: "We've mapped out a rebuild strategy for {biz_name} - reach us at architect@zerotrope.co whenever you're ready."

UNIVERSAL RULES:
- Output ONLY the 3 sentences. No AI preamble.
- No em-dashes.
"""

        # Generate narrative
        raw_narrative = ollama_client.chat(humanize_prompt)
        
        # Cleanup
        bad_phrases = ["Let me know", "Here are", "I hope this", "Based on the"]
        lines = raw_narrative.split("\n")
        clean_lines = [l.strip() for l in lines if l.strip() and not any(p.lower() in l.lower() for p in bad_phrases)]
        clean_lines = [l for l in clean_lines if len(l.split()) > 3]
        narrative = " ".join(clean_lines).replace('"', '').strip()

        # Enforce 3 sentences
        import re as _re
        sentences = _re.split(r'(?<=[.!?])\s+', narrative)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) > 3:
            narrative = " ".join(sentences[:3])

        # 3. Persistence & alerts
        db.save_lead(str(uuid.uuid4()), input_text, unique_angle)
        send_discord_notification(biz_name, primary_gap, narrative, input_text)

        return {
            "status": "success",
            "message": "Audit Complete",
            "narrative_summary": narrative,
            "unique_angle": unique_angle,
            "biz_name": biz_name
        }

    except Exception as e:
        print(f"[Bridge Error] {e}")
        return {
            "status": "error",
            "message": "Diagnostic system timeout.",
            "narrative_summary": "I'm having trouble analyzing this business right now. Please try again.",
            "unique_angle": ""
        }


def send_resend_email(name: str, email: str, hook: str, biz_name: str):
    """Send branded Hook email via Resend."""
    if not RESEND_API_KEY:
        print("[Email] No RESEND_API_KEY set.")
        return False

    first_name = name.strip().split()[0].title()

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
</head>
<body style="margin:0;padding:0;background:#080808;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#080808;padding:40px 20px;">
    <tr><td align="center">
      <table width="580" cellpadding="0" cellspacing="0" style="background:#0f0f0f;border:1px solid rgba(255,255,255,0.07);border-radius:6px;overflow:hidden;">

        <!-- Header -->
        <tr><td style="background:#0a0a0a;border-bottom:1px solid rgba(200,245,66,0.2);padding:24px 36px;">
          <span style="font-family:'Helvetica Neue',Arial,sans-serif;font-size:20px;font-weight:700;letter-spacing:0.12em;color:#f5f5f0;">ZERO<span style="color:#c8f542;">TROPE</span></span>
        </td></tr>

        <!-- Body -->
        <tr><td style="padding:36px;">
          <p style="color:#c8f542;font-size:11px;letter-spacing:0.2em;text-transform:uppercase;margin:0 0 16px;">Strategic Intelligence Report</p>
          <p style="color:#f5f5f0;font-size:16px;margin:0 0 24px;">Hi {first_name},</p>
          <p style="color:rgba(245,245,240,0.65);font-size:14px;line-height:1.7;margin:0 0 24px;">
            You requested a free Zerotrope audit for <strong style="color:#f5f5f0;">{biz_name}</strong>. We took a look at your site — here's what stood out:
          </p>

          <!-- Hook Block -->
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td style="background:#161616;border-left:3px solid #c8f542;border-radius:0 4px 4px 0;padding:20px 24px;">
              <p style="color:#f5f5f0;font-size:15px;line-height:1.8;margin:0;font-style:italic;">{hook}</p>
            </td></tr>
          </table>

          <p style="color:rgba(245,245,240,0.65);font-size:14px;line-height:1.7;margin:24px 0;">
            This is just the surface. The full growth plan goes deeper — specific actions, prioritized by impact, built around your actual gaps.
          </p>

          <!-- CTA -->
          <table cellpadding="0" cellspacing="0">
            <tr><td style="background:#c8f542;border-radius:2px;padding:12px 28px;">
              <a href="mailto:architect@zerotrope.co?subject=Growth Roadmap - {biz_name}&body=Hi, I received my Zerotrope audit and I'd love to see the full roadmap." style="color:#080808;font-size:13px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;text-decoration:none;">Get the Full Roadmap</a>
            </td></tr>
          </table>

          <p style="color:rgba(245,245,240,0.35);font-size:12px;margin:32px 0 0;">
            Or reply directly to this email — we respond within 24 hours.
          </p>
        </td></tr>

        <!-- Footer -->
        <tr><td style="border-top:1px solid rgba(255,255,255,0.07);padding:20px 36px;">
          <p style="color:rgba(245,245,240,0.25);font-size:11px;margin:0;">
            © 2025 Zerotrope · <a href="https://zerotrope.co" style="color:rgba(200,245,66,0.5);text-decoration:none;">zerotrope.co</a> · You received this because you requested a free audit.
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""

    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": "Zerotrope <architect@zerotrope.co>",
                "to": [email],
                "subject": f"Your Zerotrope Audit — {biz_name}",
                "html": html_body,
                "reply_to": "architect@zerotrope.co"
            },
            timeout=15
        )
        if response.status_code == 200:
            print(f"[Email] Sent to {email}")
            return True
        else:
            print(f"[Email] Failed: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"[Email Error] {e}")
        return False


@app.post("/deliver")
def deliver_audit(request: DeliverRequest, x_api_key: str = Header(None)):
    """Called after prospect fills in name + email. Sends the Hook email and fires Discord alert."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if request.job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")

    result = job_store.get(request.job_id)
    if not result or result.get("status") != "success":
        raise HTTPException(status_code=400, detail="Audit not complete")

    narrative = result.get("narrative_summary", "")
    unique_angle = result.get("unique_angle", "")

    # Extract biz name from job result
    biz_name = result.get("biz_name") or "your business"

    # Send email
    email_sent = send_resend_email(request.name, request.email, narrative, biz_name)

    # Fire enhanced Discord alert with contact info
    if DISCORD_TOKEN:
        email_status = "✅ Yes" if email_sent else "❌ Failed — follow up manually"
        message = (
            "🔥 **NEW LEAD WITH CONTACT INFO**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"**Name:** {request.name}\n"
            f"**Email:** {request.email}\n"
            f"**Business:** {biz_name}\n\n"
            f"**Hook sent:**\n> {narrative[:400]}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"**Email delivered:** {email_status}\n"
            f"**Action:** Reply to {request.email} or DM @zerotropeco"
        )
        try:
            httpx.post(
                f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages",
                headers={"Authorization": f"Bot {DISCORD_TOKEN}", "Content-Type": "application/json"},
                json={"content": message},
                timeout=10
            )
        except Exception as e:
            print(f"[Discord Error] {e}")

    return {"status": "delivered", "email_sent": email_sent}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
