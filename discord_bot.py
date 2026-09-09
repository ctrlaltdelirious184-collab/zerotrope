import os
import shlex
import sys
import csv
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import re
import threading
import subprocess
from pathlib import Path

# Lead Prospector paths
PROSPECTOR_DIR = Path(__file__).parent

# Import agents
from agents.research import ResearchAgent
from agents.intelligence import IntelligenceAgent
from agents.memory import MemoryAgent
from agents.brand import BrandAgent
from agents.audience import AudienceAgent
from agents.strategy import StrategyAgent
from agents.content import ContentAgent
from agents.report import ReportAgent
from agents.website import WebsiteAgent

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Track active tasks per channel so they can be stopped
active_audits = {}

# Trigger pattern
TRIGGER_PATTERN = r"Yo it's time to work again\s+(.+)"

def slugify(text):
    return re.sub(r'[^a-zA-Z0-9]', '-', text.lower()).strip('-')

async def send_long_message(channel, content, title=None):
    """
    Discord has a 2000 char limit. This splits content into chunks.
    """
    if not content: return
    
    # If it's a small message, just send it
    if len(content) <= 1900:
        embed = discord.Embed(title=title, description=content, color=discord.Color.blurple())
        await channel.send(embed=embed)
        return

    # Split into ~1900 char chunks
    chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
    for i, chunk in enumerate(chunks):
        t = f"{title} (Part {i+1})" if title else None
        embed = discord.Embed(title=t, description=chunk, color=discord.Color.blurple())
        await channel.send(embed=embed)

async def run_marketing_pipeline(channel, user_input):
    """
    Orchestrates the agent flow and sends updates to the Discord channel.
    Unified 9-Step Workflow.
    """
    try:
        # Initialize Agents
        research_agent = ResearchAgent()
        intel_agent = IntelligenceAgent()
        brand_agent = BrandAgent()
        audience_agent = AudienceAgent()
        strategy_agent = StrategyAgent()
        content_agent = ContentAgent()
        report_agent = ReportAgent()
        website_agent = WebsiteAgent()
        memory_agent = MemoryAgent()

        await channel.send("🚀 **Marketing Pipeline Initiated!** Building a high-conversion foundation...")

        # 1. Research
        status_msg = await channel.send("🔍 [1/9] Gathering deep research data...")
        research_results = await asyncio.to_thread(research_agent.run, user_input)
        await status_msg.edit(content="✅ [1/9] Research Complete.")

        # Business Name
        biz_name = research_results.get("raw_data", {}).get("title", "Local Business")
        if not biz_name or biz_name == "": biz_name = "New Client"

        # 2. Competitive Intelligence
        status_msg = await channel.send("🌩️ [2/9] Identifying competitor tropes & unique 'Contrarian' angle...")
        intel_results = await asyncio.to_thread(intel_agent.run, research_results)
        await send_long_message(channel, intel_results.get("intel_brief", ""), title="Competitive Intelligence Brief")
        await status_msg.edit(content="✅ [2/9] Unique Market Angle Identified.")

        # 3. Brand Audit
        status_msg = await channel.send(f"🎨 [3/9] Auditing brand identity for **{biz_name}**...")
        brand_results = await asyncio.to_thread(brand_agent.run, research_results, intel_data=intel_results)
        await send_long_message(channel, brand_results.get("audit", ""), title="Brand Audit Results")
        await send_long_message(channel, brand_results.get("visual_critique", ""), title="Visual Analysis")
        await status_msg.edit(content="✅ [3/9] Brand Audit Complete.")

        # 4. Audience
        status_msg = await channel.send("👥 [4/9] Identifying target personas & pain points...")
        audience_results = await asyncio.to_thread(audience_agent.run, research_results, brand_results)
        await send_long_message(channel, audience_results, title="Target Personas")
        await status_msg.edit(content="✅ [4/9] Audience Analysis Complete.")

        # 5. Strategy
        status_msg = await channel.send("📈 [5/9] Drafting growth roadmap & 90-day plan...")
        strategy_results = await asyncio.to_thread(strategy_agent.run, research_results, brand_results, audience_results)
        await send_long_message(channel, strategy_results, title="30/60/90 Day Strategy")
        await status_msg.edit(content="✅ [5/9] Strategy Roadmap Ready.")

        # 6. Content
        status_msg = await channel.send("✍️ [6/9] Generating content assets (AEO & Social Vault)...")
        content_results = await asyncio.to_thread(content_agent.run, strategy_results, audience_results)
        await send_long_message(channel, content_results, title="Content & AEO Vault")
        await status_msg.edit(content="✅ [6/9] Content & AEO Assets Generated.")

        # 7. Website Architect (MANDATORY)
        status_msg = await channel.send("🌐 [7/9] Architecting premium landing page preview...")
        website_path = await asyncio.to_thread(
            website_agent.run, biz_name, brand_results, audience_results, content_results, intel_data=intel_results
        )
        await channel.send("🚀 **Website built!** I've architected a premium landing page based on the 'Unique Angle'.", file=discord.File(website_path))
        await status_msg.edit(content="✅ [7/9] Premium Website Created.")

        # 8. Report
        status_msg = await channel.send("📊 [8/9] Building final premium report...")
        report_path = await asyncio.to_thread(
            report_agent.run, biz_name, research_results, brand_results, audience_results, strategy_results, content_results, intel_data=intel_results, website_path=website_path
        )
        await status_msg.edit(content="✅ [8/9] Final Report Assembled.")

        # 9. Memory Management
        status_msg = await channel.send("🧠 [9/9] Distilling agency lessons for global memory...")
        await asyncio.to_thread(memory_agent.run, biz_name, intel_results, brand_results, strategy_results)
        await status_msg.edit(content="✅ [9/9] Knowledge Base Updated.")

        # Upload final file
        await channel.send("✨ **All work complete!** Here is your premium marketing package:", file=discord.File(report_path))

    except asyncio.CancelledError:
        await channel.send("🛑 **Audit canceled by user.** Cleaning up workspace...")
        raise 
    except Exception as e:
        await channel.send(f"❌ **Error during pipeline execution:** {str(e)}")
    finally:
        # Cleanup task tracking
        if channel.id in active_audits:
            del active_audits[channel_id]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')

@bot.command(name="audit")
async def audit_command(ctx, *, user_input: str):
    """
    Standard command to trigger the marketing pipeline.
    Usage: !audit [URL or Description]
    """
    await initiate_pipeline(ctx.message, user_input)

@bot.command(name="stop", aliases=["cancel"])
async def stop_command(ctx):
    """
    Stops/cancels any active running audit task in the current channel.
    """
    channel_id = ctx.channel.id
    if channel_id in active_audits:
        item = active_audits[channel_id]
        task = item.get("task") if isinstance(item, dict) else item
        if task and not task.done():
            task.cancel()
        del active_audits[channel_id]
        await ctx.send(embed=discord.Embed(
            title="🛑 Audit Cancelled",
            description="Active audit task for this channel has been stopped.",
            color=discord.Color.red()
        ))
    else:
        await ctx.send("❌ There is no active audit running in this channel.")


# ─────────────────────────────────────────────────────────────────────────────
# LEAD PROSPECTOR COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

async def run_subprocess(cmd, cwd, channel_id=None):
    """Runs a shell command asynchronously and returns (stdout, stderr, returncode)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd)
    )

    if channel_id:
        active_audits[channel_id] = {"process": proc, "task": asyncio.current_task()}

    try:
        stdout, stderr = await proc.communicate()
        return stdout.decode(errors="ignore"), stderr.decode(errors="ignore"), proc.returncode
    except asyncio.CancelledError:
        try:
            proc.kill()
        except Exception:
            pass
        raise
    finally:
        if channel_id and channel_id in active_audits:
            active_audits.pop(channel_id, None)


def parse_lead_csv(csv_path, max_rows=10):
    """Read top prospect rows from CSV and return a formatted summary string."""
    rows = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        return "Could not read report file."

    if not rows:
        return "No results found."

    rows.sort(key=lambda r: int(r.get("overall_score", 100)))
    lines = []
    for r in rows[:max_rows]:
        score = r.get("overall_score", "?")
        domain = r.get("input_domain", "?")
        tier = r.get("prospect_tier", "?")
        pitches = r.get("pitch_summary", "").split(" | ")
        # Filter out repetitive pitch strings
        clean_pitch = pitches[0] if pitches else "Site requires design & performance modernization."
        lines.append(f"**{domain}** — Score: `{score}/100` — {tier}\n> {clean_pitch}")

    return "\n\n".join(lines)


@bot.command(name="harvest")
async def harvest_command(ctx, *, args: str = ""):
    """
    Harvest business website domains by niche + location.
    Usage:
      !harvest --state GA --niches "dentist, plumber"
      !harvest --locations "Atlanta GA" --niches "roofing contractor"
      !harvest --query "chiropractor Savannah GA"
    """
    await ctx.send(embed=discord.Embed(
        title="Domain Harvester Started",
        description=f"Searching for business websites...\n```{args or '(default: Georgia niches)'}```",
        color=discord.Color.orange()
    ))

    output_file = PROSPECTOR_DIR / "discord_prospects.txt"
    cmd = [sys.executable, "domain_scraper.py"] + (shlex.split(args) if args else ["--state", "GA"]) + ["--output", str(output_file)]

    status = await ctx.send("Harvesting domains... please wait.")
    stdout, stderr, code = await run_subprocess(cmd, PROSPECTOR_DIR)

    if code != 0:
        await status.edit(content="❌ Harvester encountered an error.")
        await ctx.send(f"```{stderr[:1500]}```")
        return

    # Count results
    try:
        domains = [l.strip() for l in output_file.read_text().splitlines() if l.strip()]
        count = len(domains)
    except Exception:
        count = 0

    await status.delete()
    embed = discord.Embed(
        title=f"Harvest Complete — {count} Domains Found",
        description=f"Saved to `discord_prospects.txt`.\nRun `!scan` to audit these prospects now.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

    if output_file.exists() and output_file.stat().st_size > 0:
        await ctx.send("Prospect domain list:", file=discord.File(str(output_file)))


@bot.command(name="scan")
async def scan_command(ctx, url: str = ""):
    """
    Audit websites and generate a lead quality report.
    Usage:
      !scan                         — Audit the last harvested list
      !scan somedentist.com         — Audit a single URL
    """
    prospects_file = PROSPECTOR_DIR / "discord_prospects.txt"
    csv_out = PROSPECTOR_DIR / "discord_audit.csv"
    html_out = PROSPECTOR_DIR / "discord_audit.html"
    json_out = PROSPECTOR_DIR / "discord_audit.json"

    if url:
        cmd = [
            sys.executable, "website_auditor.py",
            "--url", url,
            "--csv", str(csv_out),
            "--html", str(html_out),
            "--json", str(json_out)
        ]
        target_desc = f"`{url}`"
    elif prospects_file.exists():
        cmd = [
            sys.executable, "website_auditor.py",
            "--input", str(prospects_file),
            "--threads", "10",
            "--csv", str(csv_out),
            "--html", str(html_out),
            "--json", str(json_out)
        ]
        count = len([l for l in prospects_file.read_text().splitlines() if l.strip()])
        target_desc = f"`discord_prospects.txt` ({count} domains)"
    else:
        await ctx.send("❌ No domain list found. Run `!harvest` first.")
        return

    await ctx.send(embed=discord.Embed(
        title="Website Auditor Running",
        description=f"Scanning {target_desc} across Design, Mobile, SEO, Speed & Trust...",
        color=discord.Color.blue()
    ))

    status = await ctx.send("Auditing websites... this may take a moment.")
    stdout, stderr, code = await run_subprocess(cmd, PROSPECTOR_DIR)

    await status.delete()

    if code != 0:
        await ctx.send(embed=discord.Embed(title="❌ Audit Error", description=f"```{stderr[:1500]}```", color=discord.Color.red()))
        return

    # Build summary of top leads
    summary = parse_lead_csv(csv_out, max_rows=8)
    embed = discord.Embed(
        title="Lead Audit Report — Top Prospects",
        description=summary,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Full HTML dashboard attached below. Open it in your browser.")
    await ctx.send(embed=embed)

    if csv_out.exists():
        await ctx.send("Full CSV Report:", file=discord.File(str(csv_out)))
    if html_out.exists():
        await ctx.send("Interactive HTML Dashboard:", file=discord.File(str(html_out)))


@bot.command(name="prospect")
async def prospect_command(ctx, *, args: str = ""):
    """
    Full one-shot pipeline: harvest domains then immediately audit them.
    Usage:
      !prospect --state GA --niches "dentist, plumber"
      !prospect --locations "Atlanta GA" --niches "roofing contractor, law firm"
    """
    output_file = PROSPECTOR_DIR / "discord_prospects.txt"
    csv_out = PROSPECTOR_DIR / "discord_audit.csv"
    html_out = PROSPECTOR_DIR / "discord_audit.html"
    json_out = PROSPECTOR_DIR / "discord_audit.json"

    await ctx.send(embed=discord.Embed(
        title="Full Prospect Pipeline Started",
        description=f"Step 1/2: Harvesting domains...\n```{args or '(default: Georgia niches)'}```",
        color=discord.Color.orange()
    ))

    # Step 1: Harvest
    harvest_cmd = [sys.executable, "domain_scraper.py"] + (shlex.split(args) if args else ["--state", "GA"]) + ["--output", str(output_file)]
    status = await ctx.send("Harvesting...")
    stdout, stderr, code = await run_subprocess(harvest_cmd, PROSPECTOR_DIR, channel_id=ctx.channel.id)

    if code != 0:
        await status.edit(content="❌ Harvest failed.")
        await ctx.send(f"```{stderr[:1500]}```")
        return

    try:
        domains = [l.strip() for l in output_file.read_text().splitlines() if l.strip()]
        count = len(domains)
    except Exception:
        count = 0

    await status.edit(content=f"✅ Step 1/2: Harvested **{count} domains**. Now auditing...")

    # Step 2: Audit
    audit_cmd = [
        sys.executable, "website_auditor.py",
        "--input", str(output_file),
        "--threads", "10",
        "--csv", str(csv_out),
        "--html", str(html_out),
        "--json", str(json_out)
    ]
    stdout, stderr, code = await run_subprocess(audit_cmd, PROSPECTOR_DIR, channel_id=ctx.channel.id)

    if code != 0:
        await ctx.send(embed=discord.Embed(title="❌ Audit Failed", description=f"```{stderr[:1500]}```", color=discord.Color.red()))
        return

    # Summary
    summary = parse_lead_csv(csv_out, max_rows=8)
    embed = discord.Embed(
        title=f"Prospect Pipeline Complete — Top {min(8, count)} Leads",
        description=summary,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Full reports attached below.")
    await ctx.send(embed=embed)

    if csv_out.exists():
        await ctx.send("Full CSV Report:", file=discord.File(str(csv_out)))
    if html_out.exists():
        await ctx.send("Interactive HTML Dashboard:", file=discord.File(str(html_out)))


@bot.command(name="pagespeed", aliases=["speed"])
async def pagespeed_command(ctx, url: str):
    """
    Audit a single website URL using Google's PageSpeed Insights API and get plain-English client talking points.
    Usage: !pagespeed example.com
    """
    if not url:
        await ctx.send("❌ Please provide a URL. Example: `!pagespeed example.com`")
        return

    await ctx.send(embed=discord.Embed(
        title="PageSpeed Insights Audit Started",
        description=f"Auditing `{url}` with Google PageSpeed Insights API...",
        color=discord.Color.blue()
    ))

    cmd = [sys.executable, "pagespeed_auditor.py", url]
    stdout, stderr, code = await run_subprocess(cmd, Path(__file__).parent)

    if code != 0 or not stdout.strip():
        await ctx.send(embed=discord.Embed(title="❌ PageSpeed Audit Failed", description=f"```{stderr[:1500]}```", color=discord.Color.red()))
        return

    await ctx.send(f"```{stdout.strip()}```")


async def _get_or_create_thread(channel, thread_name: str):
    """Finds existing thread by name or creates a new public thread, handling errors gracefully."""
    # Check existing active threads
    if hasattr(channel, "threads"):
        for th in channel.threads:
            if th.name == thread_name:
                return th
    # Check archived threads if supported
    if hasattr(channel, "archived_threads"):
        try:
            async for th in channel.archived_threads():
                if th.name == thread_name:
                    return th
        except Exception:
            pass

    # Create new thread
    try:
        thread = await channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.public_thread if hasattr(discord.ChannelType, "public_thread") else None,
            auto_archive_duration=1440
        )
        return thread
    except Exception as e:
        print(f"[Warning] Failed to create thread '{thread_name}': {e}")
        return None


async def process_stage2_discord_output(ctx, result, mod, is_inline: bool):
    """
    Handles Part 2 (Main Channel Summary) & Part 3 (Dedicated Thread Screenshots & per-page detail).
    """
    domain = result.get("domain", "audit")
    thread_name = f"{domain}-audit"
    use_thread = not is_inline

    target_channel = ctx.channel
    thread = None

    if use_thread:
        thread = await _get_or_create_thread(ctx.channel, thread_name)

    thread_jump_url = thread.jump_url if thread else None

    # Part 2: Main channel text summary
    summary_text = mod.format_deduped_summary(result, thread_jump_url=thread_jump_url)
    
    # Send main channel summary (fallback to channel if thread creation failed)
    if len(summary_text) <= 1900:
        await ctx.send(summary_text)
    else:
        chunks = [summary_text[i:i+1900] for i in range(0, len(summary_text), 1900)]
        for ch in chunks:
            await ctx.send(ch)

    if use_thread and not thread:
        await ctx.send("⚠️ *Thread creation unavailable (permissions/rate limit). Posting results in channel inline.*")

    # Part 3: Thread / Inline Screenshots & Per-page detail
    dest = thread if (use_thread and thread) else ctx.channel

    if thread:
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await thread.send(f"--- **Audit Session: {now_str}** ---")

    pages_crawled = result.get("pages_crawled", [])
    raw_issues = result.get("confirmed_issues", [])
    screenshots = result.get("screenshots", {})

    # Pre-compute which signatures are sitewide (≥80% of pages)
    # so we only show them once in the thread, not on every page.
    total_pages = len(pages_crawled)
    sitewide_threshold = max(2, round(total_pages * 0.8))

    from collections import defaultdict
    sig_pages = defaultdict(set)
    for iss in raw_issues:
        cat = iss.get("category", "")
        elem = iss.get("element", "")
        detail = iss.get("detail", "")
        sig_pages[(cat, elem, detail)].add(iss.get("page", ""))

    sitewide_sigs = {
        sig for sig, pages in sig_pages.items()
        if len(pages) >= sitewide_threshold
    }
    # Track which sitewide sigs have already been announced in the thread
    announced_sitewide = set()

    for pg_url in pages_crawled:
        pg_issues = [i for i in raw_issues if i.get("page") == pg_url]

        # Dedup within this page
        deduped_pg = mod.dedupe_issues(pg_issues, total_pages)

        issue_lines = []
        sitewide_skipped = []
        if not deduped_pg:
            issue_lines.append("• No confirmed defects found on this page.")
        else:
            for item in deduped_pg:
                sig = (item["category"], item["element"], item["detail"])
                if sig in sitewide_sigs:
                    if sig not in announced_sitewide:
                        # First time we see this sitewide issue — show it with a sitewide tag
                        announced_sitewide.add(sig)
                        line = mod.format_finding_plain_english(item, is_summary=False)
                        issue_lines.append(line + "  *(sitewide — shown once)*")
                    else:
                        # Already shown on a previous page — skip silently
                        sitewide_skipped.append(item["category"])
                else:
                    issue_lines.append(mod.format_finding_plain_english(item, is_summary=False))

        if sitewide_skipped:
            cats = ", ".join(sorted(set(sitewide_skipped)))
            issue_lines.append(f"*({len(sitewide_skipped)} sitewide issue(s) [{cats}] suppressed — already reported above)*")

        caption = f"📄 **Page Detail:** `{pg_url}`\n" + "\n".join(issue_lines)


        pg_shots = screenshots.get(pg_url, {})
        files_to_send = []
        for vp_name in ["mobile", "desktop"]:
            fp = pg_shots.get(vp_name)
            if fp and Path(fp).exists():
                files_to_send.append(discord.File(str(fp), filename=f"{vp_name}_{Path(fp).name}"))

        try:
            if files_to_send:
                await dest.send(caption, files=files_to_send)
            else:
                await dest.send(caption)
        except Exception as e:
            await dest.send(f"📄 **Page Detail:** `{pg_url}` (Error uploading image: {e})\n" + "\n".join(issue_lines))


@bot.command(name="confirm")
async def confirm_command(ctx, domain: str = "", *, flags: str = ""):
    """
    Stage 2 Playwright multi-page browser audit on one domain.
    Usage:
      !confirm example.com                     -- multi-page + dedicated thread
      !confirm example.com --inline            -- post images directly in channel
      !confirm example.com --single-page       -- homepage only (fast)
    """
    if not domain:
        await ctx.send("Please provide a domain. Example: `!confirm example.com`")
        return

    all_args = (domain + " " + flags).split()
    target_domain = all_args[0]
    single_page   = "--single-page" in all_args
    is_inline     = "--inline" in all_args

    max_sp = 6
    if "--max-subpages" in all_args:
        try:
            max_sp = int(all_args[all_args.index("--max-subpages") + 1])
        except (ValueError, IndexError):
            pass

    mode_label = "homepage only" if single_page else f"multi-page (up to {max_sp} subpages)"
    status_msg = await ctx.send(embed=discord.Embed(
        title="Stage 2 Browser Audit Starting",
        description=f"Crawling `{target_domain}` | Mode: {mode_label}\nProgress updates will appear below...",
        color=discord.Color.gold()
    ))

    import importlib.util as _ilu
    import concurrent.futures

    loop = asyncio.get_event_loop()
    progress_lines = []

    def _progress(msg):
        progress_lines.append(msg)
        print(f"[confirm] {msg}")

    def _run_audit():
        spec = _ilu.spec_from_file_location("playwright_auditor", Path(__file__).parent / "playwright_auditor.py")
        mod  = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.confirm_audit(
            target_domain,
            output_dir   = str(Path(__file__).parent / "screenshots"),
            max_subpages = max_sp,
            single_page  = single_page,
            progress_cb  = _progress,
        ), mod

    current_task = asyncio.current_task()
    active_audits[ctx.channel.id] = {"task": current_task, "name": f"!confirm {target_domain}"}

    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = loop.run_in_executor(pool, _run_audit)

            while not future.done():
                await asyncio.sleep(4)
                if ctx.channel.id not in active_audits:
                    # Cancelled by !stop / !cancel
                    return
                if not future.done() and progress_lines:
                    recent = "\n".join(progress_lines[-4:])
                    try:
                        await status_msg.edit(embed=discord.Embed(
                            title="Stage 2 In Progress...",
                            description=f"```{recent}```",
                            color=discord.Color.gold()
                        ))
                    except Exception:
                        pass

            result, mod = await future

        await process_stage2_discord_output(ctx, result, mod, is_inline)
    finally:
        active_audits.pop(ctx.channel.id, None)



@bot.command(name="confirmall")
async def confirmall_command(ctx, *, flags: str = ""):
    """
    Run Stage 2 Playwright audit on all needs_confirmation leads from the last scan.
    Usage:
      !confirmall                    -- multi-page + dedicated threads
      !confirmall --inline           -- post images inline in main channel
      !confirmall --single-page      -- fast single page mode
    """
    json_path = Path("prospect_audit.json")
    if not json_path.exists():
        json_path = Path("discord_audit.json")

    if not json_path.exists():
        await ctx.send("No `prospect_audit.json` or `discord_audit.json` found. Run `!scan` or `!prospect` first.")
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        await ctx.send(f"Error reading results: {e}")
        return

    flagged   = [r for r in data if r.get("needs_confirmation")]
    single_pg = "--single-page" in flags
    is_inline = "--inline" in flags

    if not flagged:
        await ctx.send("No domains are flagged for Stage 2 confirmation from the last scan.")
        return

    mode_label = "homepage-only" if single_pg else "multi-page"
    await ctx.send(embed=discord.Embed(
        title="Batch Stage 2 Audit Initiated",
        description=f"Auditing **{len(flagged)}** leads | Mode: {mode_label}\nThis may take a few minutes...",
        color=discord.Color.purple()
    ))

    import importlib.util as _ilu
    import concurrent.futures

    spec = _ilu.spec_from_file_location("playwright_auditor", Path(__file__).parent / "playwright_auditor.py")
    mod  = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)

    loop = asyncio.get_event_loop()

    for idx, item in enumerate(flagged, 1):
        dom = item.get("input_domain") or item.get("url")
        prog_msg = await ctx.send(f"[{idx}/{len(flagged)}] Starting Stage 2 on `{dom}`...")
        progress_lines = []

        def _progress(msg):
            progress_lines.append(msg)

        def _run(d=dom, sp=single_pg, m=mod):
            return m.confirm_audit(
                d,
                output_dir   = str(Path(__file__).parent / "screenshots"),
                max_subpages = 6,
                single_page  = sp,
                progress_cb  = _progress,
            )

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = loop.run_in_executor(pool, _run)

            while not future.done():
                await asyncio.sleep(6)
                if not future.done() and progress_lines:
                    recent = "\n".join(progress_lines[-3:])
                    try:
                        await prog_msg.edit(content=f"[{idx}/{len(flagged)}] `{dom}`\n```{recent}```")
                    except Exception:
                        pass

            result = await future

        await process_stage2_discord_output(ctx, result, mod, is_inline)



@bot.command(name="leads")
async def leads_help(ctx):
    """
    Shows all lead prospector commands.
    """
    embed = discord.Embed(
        title="Lead Prospector Commands",
        color=discord.Color.blurple()
    )
    embed.add_field(name="!prospect", value="Full pipeline: harvest + audit in one shot\n`!prospect --state GA --niches \"dentist, roofer\"`", inline=False)
    embed.add_field(name="!harvest", value="Discover business domains by niche + location\n`!harvest --state GA --niches \"plumber, lawyer\"`", inline=False)
    embed.add_field(name="!scan", value="Stage 1 Fast Filter audit\n`!scan` — audit last harvested list\n`!scan targetdomain.com`", inline=False)
    embed.add_field(name="!confirm", value="Stage 2 Playwright multi-page audit\n`!confirm targetdomain.com` — crawl up to 6 subpages\n`!confirm targetdomain.com --single-page` — homepage only (fast)\n`!confirm targetdomain.com --max-subpages 3`", inline=False)
    embed.add_field(name="!confirmall", value="Batch Stage 2 on all flagged leads\n`!confirmall` | `!confirmall --single-page`", inline=False)
    embed.add_field(name="!pagespeed", value="PageSpeed Insights audit\n`!pagespeed targetbusiness.com`", inline=False)
    embed.add_field(name="!stop / !cancel", value="Cancel any active audit or scan running in this channel", inline=False)
    embed.add_field(name="!restart", value="Restart the Discord bot process immediately", inline=False)
    embed.set_footer(text="Stage 1 = fast pre-filter. Stage 2 = crawled Playwright proof with screenshots.")
    await ctx.send(embed=embed)

@bot.command(name="restart")
async def restart_command(ctx):
    """
    Restarts the Discord bot process.
    """
    await ctx.send("🔄 **Restarting Discord Bot...**")
    vbs_path = Path(__file__).parent / "run_discord_bot.vbs"
    if sys.platform == "win32" and vbs_path.exists():
        subprocess.Popen(["wscript", str(vbs_path)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        sys.exit(0)
    else:
        os.execv(sys.executable, [sys.executable] + sys.argv)


async def initiate_pipeline(message, user_input):
    """
    Helper to handle the logic of creating a channel and starting the pipeline.
    """
    guild = message.guild
    channel_id = message.channel.id
    
    # Check if audit already running here
    if channel_id in active_audits:
        await message.reply("❌ An audit is already running in this channel. Use `!stop` first if you want to restart.")
        return

    channel_name = f"audit-{slugify(user_input[:20])}"
    
    await message.reply(f"Acknowledged. Creating a dedicated workspace for the full 9-step audit...")
    
    try:
        new_channel = await guild.create_text_channel(
            name=channel_name,
            category=message.channel.category,
            topic=f"Marketing Audit for: {user_input}"
        )
        await message.reply(f"Channel created: {new_channel.mention}. Beginning 9-step workflow now.")
        
        # Start and track the task
        task = asyncio.create_task(run_marketing_pipeline(new_channel, user_input))
        active_audits[new_channel.id] = task
        
    except Exception as e:
        await message.reply(f"Failed to create channel: {e}. I'll run it here instead.")
        task = asyncio.create_task(run_marketing_pipeline(message.channel, user_input))
        active_audits[message.channel.id] = task

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Check for the custom "Yo" trigger
    match = re.search(TRIGGER_PATTERN, message.content, re.IGNORECASE)
    if match:
        user_input = match.group(1).strip()
        await initiate_pipeline(message, user_input)

    await bot.process_commands(message)

if __name__ == "__main__":
    if not TOKEN or TOKEN == "your_token_here":
        print("ERROR: Please set your DISCORD_TOKEN in the .env file.")
    else:
        bot.run(TOKEN)
