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
from utils.ollama_client import OllamaClient
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
ollama_client = OllamaClient()

# Configuration
API_KEY = os.getenv("ZEROTROPE_API_KEY", "ZEROTROPE_SECURE_9922")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID = "1495146563469836299"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3")


class AuditRequest(BaseModel):
    input_text: str


class AuditResponse(BaseModel):
    status: str
    message: str
    narrative_summary: str
    unique_angle: str = ""


class AuditJobResponse(BaseModel):
    job_id: str
    status: str


# In-memory job store: job_id -> result dict
job_store: dict = {}


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
        job_store[job_id] = result
    except Exception as e:
        print(f"[Job Error] {e}")
        job_store[job_id] = {
            "status": "error",
            "message": "Diagnostic system timeout.",
            "narrative_summary": "I'm having trouble analyzing this business right now. Please try again.",
            "unique_angle": ""
        }


@app.post("/audit", response_model=AuditJobResponse)
def trigger_audit(request: AuditRequest, x_api_key: str = Header(None)):
    # Security gate
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    job_id = str(uuid.uuid4())
    job_store[job_id] = None  # mark as pending
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
    if result is None:
        return AuditResponse(status="pending", message="Processing...", narrative_summary="", unique_angle="")
    return AuditResponse(**result)


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

        biz_name = (
            intel_results.get("business_name")
            or (raw_title.split("|")[0].strip() if raw_title else "")
            or url_domain
            or input_text
        )
        placeholder_phrases = [
            "no brand name", "brand name not", "not provided", "unknown",
            "n/a", "none", "business name", "company name"
        ]
        if not biz_name or len(biz_name.strip()) < 2 or any(p in biz_name.lower() for p in placeholder_phrases):
            biz_name = url_domain or input_text

        primary_gap = intel_results.get("primary_gap", "commodity positioning with no differentiation")
        comp_insight = intel_results.get("competitor_insight", "rivals are using outdated templates")
        usp = intel_results.get("contrarian_usp", "a foundational strategic overhaul")
        terminology = intel_results.get("terminology", "client")
        owner_name = intel_results.get("owner_name", "")
        gap_evidence = intel_results.get("gap_evidence", "")
        no_gap_found = intel_results.get("no_gap_found", False)
        unique_angle = f"GAP: {primary_gap} | USP: {usp} | COMP: {comp_insight}"

        # 2. Zerotrope Humanizer
        if no_gap_found:
            narrative = (
                f"{biz_name} has a well-built site — the CTAs are specific, the credentials are visible, "
                f"and the messaging is clear enough to convert visitors who find you. "
                f"The gap is upstream: when a potential {terminology} asks ChatGPT or Perplexity "
                f"for a recommendation in your space, you don't appear — not because you're less qualified, "
                f"but because your content isn't structured for AI discovery yet, and your competitors are already moving on it. "
                f"The full 9-Step Growth Roadmap for {biz_name} is ready whenever you are."
            )
        else:
            humanize_prompt = f"""
[SYSTEM: HOOK GENERATION MODE]
You are a high-end, straight-talking strategist who just finished auditing {biz_name}.
You speak like a sharp consultant — not a polite assistant, and definitely not a marketer.
Write a response addressed DIRECTLY to the business owner.

AUDIT FACTS:
- Business Name: {biz_name}
- Primary Gap Found: {primary_gap}
- Gap Evidence: {gap_evidence}
- Their Opportunity: {usp}

YOUR OBJECTIVE:
Point out a real, painful problem on their site accurately—but DO NOT reveal the complete solution.
The goal is to create tension and curiosity (a "hook"). If you tell them how to fix it, they won't need us.

CRITICAL: NEVER start your sentences with phrases like "The specific finding is...", "I found that...", or "For instance...". Just state the observation aggressively.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCENARIO A — A REAL, SPECIFIC GAP WAS FOUND:
Write exactly 3 sentences:

Sentence 1 (The Observation):
- Speak directly to the business: "[Business Name], I was looking at your site and noticed..." (or similar natural opening).
- You MUST use the exact quote from the 'Gap Evidence' provided to prove you actually looked at their site.
- NEVER use consultant phrases like "The specific finding is..." or "You have a generic CTA...".
- Your sentence MUST be structurally similar to this formula: "I was looking at the site and noticed your main button just says '[INSERT EXACT QUOTE FROM GAP EVIDENCE]' instead of stating a specific outcome."

Sentence 2 (The Cost & The Hook):
- Tell them what the vagueness is costing them right now (e.g. lost prospects, lost search visibility).
- Contrast their site against what top competitors do. DO NOT just repeat marketing buzzwords.
- Your sentence MUST be structurally similar to this formula: "Right now, your competitors are capturing those high-value visitors because they clearly position their actual expertise, and you're leaving your best assets buried."

Sentence 3 (The Close):
- Tell them we already mapped out the solution.
- "The full 9-Step Growth Roadmap for {biz_name} is mapped out and ready whenever you are."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCENARIO B — THE SITE IS GENUINELY SOLID:
Write exactly 3 sentences acknowledging their solid site, then pivoting to AI search visibility (AEO).

Sentence 1: "{biz_name} is actually built quite well—the messaging is clear enough to convert anyone who finds it."
Sentence 2: "But the gap is upstream: AI search engines like ChatGPT are currently recommending competitors because your site isn't structured for AEO discovery."
Sentence 3: "The full 9-Step Growth Roadmap for {biz_name} is mapped out and ready whenever you are."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UNIVERSAL RULES:
- Output ONLY the 3 sentences. No AI preamble.
- DO NOT tell them how to fix the problem. You want them to want the report.
- Keep sentences punchy. No em-dashes. No "we".
- Never invent evidence. Only use the Audit Facts provided.
"""
            raw_narrative = ollama_client.chat(humanize_prompt)
            narrative = raw_narrative.split(":")[-1].strip() if ":" in raw_narrative[:100] else raw_narrative

            bad_phrases = [
                "Let me know if this meets", "Here are the 3-sentence", "Here is the",
                "I hope this", "Please let me know", "Feel free to", "Note:",
                "This response", "As requested", "Based on the",
                "I've got to give you credit", "I have to give you credit",
                "Credit where credit is due", "To be fair", "I must say", "It's worth noting",
            ]
            lines = narrative.split("\n")
            clean_lines = [l.strip() for l in lines if l.strip() and not any(p.lower() in l.lower() for p in bad_phrases)]
            narrative = " ".join(clean_lines).replace('"', '').strip()

        # 3. Persistence & alerts
        db.save_lead(str(uuid.uuid4()), input_text, unique_angle)
        send_discord_notification(biz_name, primary_gap, narrative, input_text)

        return {
            "status": "success",
            "message": "Audit Complete",
            "narrative_summary": narrative,
            "unique_angle": unique_angle
        }

    except Exception as e:
        print(f"[Bridge Error] {e}")
        return {
            "status": "error",
            "message": "Diagnostic system timeout.",
            "narrative_summary": "I'm having trouble analyzing this business right now. Please try again.",
            "unique_angle": ""
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)