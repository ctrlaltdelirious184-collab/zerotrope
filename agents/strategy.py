from utils.ollama_client import OllamaClient

class StrategyAgent:
    def __init__(self):
        self.client = OllamaClient()

    def run(self, research_data, brand_data, audience_data):
        """
        Creates a marketing strategy roadmap.
        """
        print("[Strategy] Drafting growth roadmap...")
        
        prompt = f"""
        Create a comprehensive 30/60/90-day marketing strategy for this business.
        
        Brand Context: {brand_data.get('audit', '')[:1000]}
        Target Audience Profiles: {audience_data[:1000]}
        
        Include:
        1. Primary Recommended Channels (e.g. SEO, Meta Ads, TikTok, Local Mailers) with rationale.
        2. 30-Day Goal: Quick Wins & Foundation.
        3. 60-Day Goal: Scaling & Content.
        4. 90-Day Goal: Automation & Optimization.
        5. Estimated Budget Allocation (Low/Medium/High priorities).
        
        Make it actionable and specific to the niche.
        """
        
        return self.client.chat(prompt, system="You are a high-level Chief Marketing Officer (CMO).")
