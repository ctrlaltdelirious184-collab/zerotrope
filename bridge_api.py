from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel
import uuid
import os
import httpx

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


@app.post("/audit", response_model=AuditResponse)
def trigger_audit(request: AuditRequest, background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    # Security gate
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        # 1. Intelligence gathering — two-pass pipeline
        research_results = ResearchAgent().run(request.input_text)
        intel_results = IntelligenceAgent().run(research_results)

        # Clean business name — use AI-extracted name first, fallback to title tag, then URL
        raw_title = research_results.get("raw_data", {}).get("title", "")
        
        # Extract clean name from URL as last resort
        from urllib.parse import urlparse
        parsed_url = urlparse(request.input_text)
        url_domain = parsed_url.netloc.replace("www.", "").split(".")[0].replace("-", " ").title()

        biz_name = (
            intel_results.get("business_name")
            or (raw_title.split("|")[0].strip() if raw_title else "")
            or url_domain
            or request.input_text
        )
        # Final sanity check — reject placeholder text Gemma sometimes outputs
        placeholder_phrases = [
            "no brand name", "brand name not", "not provided", "unknown", 
            "n/a", "none", "business name", "company name"
        ]
        if not biz_name or len(biz_name.strip()) < 2 or any(p in biz_name.lower() for p in placeholder_phrases):
            biz_name = url_domain or request.input_text

        primary_gap = intel_results.get("primary_gap", "commodity positioning with no differentiation")
        comp_insight = intel_results.get("competitor_insight", "rivals are using outdated templates")
        usp = intel_results.get("contrarian_usp", "a foundational strategic overhaul")
        terminology = intel_results.get("terminology", "client")
        owner_name = intel_results.get("owner_name", "")
        business_type = intel_results.get("business_type", "business")
        gap_evidence = intel_results.get("gap_evidence", "")
        no_gap_found = intel_results.get("no_gap_found", False)
        unique_angle = f"GAP: {primary_gap} | USP: {usp} | COMP: {comp_insight}"

        # 2. Zerotrope Humanizer — generates the prospect-facing Hook
        # Handle honest no-gap scenario
        if no_gap_found:
            owner_line = f"Dr. {owner_name}" if owner_name else biz_name
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
- Gap Evidence: {intel_results.get("gap_evidence", "")}
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

        # Ollama call via OllamaClient wrapper
            raw_narrative = ollama_client.chat(humanize_prompt)

            # Strip AI preambles and self-referential lines
            narrative = raw_narrative.split(":")[-1].strip() if ":" in raw_narrative[:100] else raw_narrative

        # Remove lines where the model talks to itself
            bad_phrases = [
            "Let me know if this meets",
            "Here are the 3-sentence",
            "Here is the",
            "I hope this",
            "Please let me know",
            "Feel free to",
            "Note:",
            "This response",
            "As requested",
            "Based on the",
            "I've got to give you credit",
            "I have to give you credit",
            "Credit where credit is due",
            "To be fair",
            "I must say",
            "It's worth noting",
        ]
            lines = narrative.split("\n")
            clean_lines = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if any(phrase.lower() in stripped.lower() for phrase in bad_phrases):
                    continue
                clean_lines.append(stripped)
            narrative = " ".join(clean_lines).replace('"', '').strip()

        # 3. Persistence & alerts
        db.save_lead(str(uuid.uuid4()), request.input_text, unique_angle)
        background_tasks.add_task(send_discord_notification, biz_name, primary_gap, narrative, request.input_text)

        return AuditResponse(
            status="success",
            message="Audit Complete",
            narrative_summary=narrative,
            unique_angle=unique_angle
        )

    except Exception as e:
        print(f"[Bridge Error] {e}")
        return AuditResponse(
            status="error",
            message="Diagnostic system timeout.",
            narrative_summary="I'm having trouble analyzing this business right now. Please try again."
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)