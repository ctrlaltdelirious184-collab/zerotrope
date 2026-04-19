import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import re
import threading

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
    Stops the active audit in the current channel.
    """
    channel_id = ctx.channel.id
    if channel_id in active_audits:
        task = active_audits[channel_id]
        task.cancel()
        await ctx.send("⌛ Cancellation signal sent. Stopping agents...")
    else:
        await ctx.send("❌ There is no active audit running in this channel.")

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
