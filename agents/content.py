from utils.ollama_client import OllamaClient

class ContentAgent:
    def __init__(self):
        self.client = OllamaClient()

    def run(self, strategy_data, audience_data):
        """
        Generates ready-to-use marketing assets.
        """
        print("[Content] Generating copy and creative assets...")
        
        prompt = f"""
        Generate high-converting marketing copy AND AEO (Answer Engine Optimization) assets:
        
        Strategy Summary: {strategy_data[:1000]}
        Audience: {audience_data[:1000]}
        
        Please provide:
        1. 3 Powerful Taglines.
        2. 1 Short 'Elevator Pitch' (Focus on the Unique Angle identified).
        3. 2 Meta Ad Headline & Description sets.
        4. 3 Social Media Post Ideas with 'Stopping Power'.
        
        --- AEO & AI SEARCH OPTIMIZATION ---
        5. 3 'Answer Snippets': Direct answers to common customer questions about this service, formatted for AI scrapers (Question -> Concise Direct Answer -> Supporting Detail).
        6. Essential Semantic Entities: 10 key terms/entities to include in the website code to anchor this in the Knowledge Graph.
        7. Recommended Schema Markup types (e.g., FAQPage, Service, LocalBusiness) with specific field suggestions.
        
        Tone: Aggressive differentiation, high authority.
        """
        
        return self.client.chat(prompt, system="You are a world-class Direct Response Copywriter.")
