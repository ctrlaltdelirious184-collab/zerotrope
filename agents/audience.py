from utils.ollama_client import OllamaClient

class AudienceAgent:
    def __init__(self):
        self.client = OllamaClient()

    def run(self, research_data, brand_data):
        """
        Generates target personas based on the business data.
        """
        print("[Audience] Identifying target personas...")
        
        business_info = research_data.get("raw_data", {}).get("text", "")
        brand_audit = brand_data.get("audit", "")
        
        prompt = f"""
        Based on this business information and brand audit, identify 2-3 distinct target personas.
        
        Business Context: {business_info}
        Brand Audit: {brand_audit}
        
        For each persona, include:
        - Name & Catchy Label (e.g., 'Busy Mom Brenda')
        - Demographics (Age, Income, Occupation)
        - Core Pain Points (What problem does this business solve for them?)
        - Digital Habits (Where do they spend time online?)
        - Buying Motivation (Why would they choose this company?)
        
        Format as clear, distinct profiles.
        """
        
        return self.client.chat(prompt, system="You are a brilliant Consumer Psychologist and Marketing Researcher.")
