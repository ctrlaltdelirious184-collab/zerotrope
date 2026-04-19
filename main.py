import sys
import argparse
import os
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

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

console = Console()

def main():
    parser = argparse.ArgumentParser(description="AI Marketing Pipeline")
    parser.add_argument("--input", required=True, help="Business URL or description")
    args = parser.parse_args()

    console.print(Panel.fit("[bold purple]Antigravity[/] AI Marketing Pipeline", subtitle="Autonomous Branding & Strategy"))

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

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # 1. Research
        task_research = progress.add_task("Gathering raw business data...", total=None)
        research_results = research_agent.run(args.input)
        progress.update(task_research, description="[green]Research Complete[/]")

        # Name extraction
        biz_name = research_results.get("raw_data", {}).get("title", "Local Business")
        if not biz_name or biz_name == "":
            biz_name = "Custom Project"

        # 2. Competitive Intelligence
        task_intel = progress.add_task("Analyzing unique market angle...", total=None)
        intel_results = intel_agent.run(research_results)
        progress.update(task_intel, description="[green]Market Angle Identified[/]")

        # 3. Brand Audit
        task_brand = progress.add_task("Auditing brand and narrative...", total=None)
        brand_results = brand_agent.run(research_results, intel_data=intel_results)
        progress.update(task_brand, description="[green]Brand Narrative Defined[/]")

        # 4. Audience Analysis
        task_audience = progress.add_task("Identifying target personas...", total=None)
        audience_results = audience_agent.run(research_results, brand_results)
        progress.update(task_audience, description="[green]Audience Personas Created[/]")

        # 5. Strategy Development
        task_strategy = progress.add_task("Drafting marketing roadmap...", total=None)
        strategy_results = strategy_agent.run(research_results, brand_results, audience_results)
        progress.update(task_strategy, description="[green]Strategy Roadmap Ready[/]")

        # 6. Content & AEO
        task_content = progress.add_task("Generating AEO Optimized copy...", total=None)
        content_results = content_agent.run(strategy_results, audience_results)
        progress.update(task_content, description="[green]Content & AEO Vault Ready[/]")

        # 7. Web Builder (MANDATORY in 9-step flow)
        task_web = progress.add_task("Architecting premium landing page...", total=None)
        website_path = website_agent.run(biz_name, brand_results, audience_results, content_results, intel_data=intel_results)
        progress.update(task_web, description="[green]Website Built From Scratch[/]")

        # 8. Final Report
        task_report = progress.add_task("Assembling final HTML report...", total=None)
        report_path = report_agent.run(
            biz_name, 
            research_results, 
            brand_results, 
            audience_results, 
            strategy_results, 
            content_results,
            intel_data=intel_results,
            website_path=website_path
        )
        progress.update(task_report, description="[green]Report Finalized[/]")

        # 9. Memory Management
        task_memory = progress.add_task("Distilling agency knowledge...", total=None)
        memory_agent.run(biz_name, intel_results, brand_results, strategy_results)
        progress.update(task_memory, description="[green]Knowledge Base Updated[/]")

    console.print(f"\n[bold green]Success![/] Your marketing audit is ready:")
    console.print(f"Location: [link=file://{report_path}]{report_path}[/]")

if __name__ == "__main__":
    main()
