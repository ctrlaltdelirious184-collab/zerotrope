from utils.ollama_client import OllamaClient
import base64

class BrandAgent:
    def __init__(self):
        self.client = OllamaClient()
        self.vision_client = OllamaClient(model="llama3.2-vision:latest")

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def run(self, research_data, intel_data=None):
        """
        Analyzes the research data to audit the brand.
        """
        print("[Brand] Auditing brand identity & positioning...")
        
        raw_text = research_data.get("raw_data", {}).get("text", "")
        title = research_data.get("raw_data", {}).get("title", "")
        headings = ", ".join(research_data.get("raw_data", {}).get("headings", []))
        intel_brief = intel_data.get("intel_brief", "") if intel_data else "No competitive intelligence provided."
        
        prompt = f"""
        Analyze this business brand based on its website content and the provided competitive intelligence:
        Title: {title}
        Headings: {headings}
        Content: {raw_text}
        
        Competitive Intelligence:
        {intel_brief}
        
        Your goal is to provide a brand audit focused on NARRATIVE.
        Identify:
        1. Current Tone of Voice (e.g., Professional, Playful, Stale)
        2. The 'Unique Angle' to adopt (Based on the Intel Brief)
        3. Messaging Gaps (What aren't they saying that they SHOULD be?)
        4. Brand Strength Score (1-10)
        
        Provide a 'Category of One' recommendation for the brand's positioning.
        """
        
        audit = self.client.chat(prompt, system="You are an expert Brand Strategist who hates generic branding.")
        
        visual_critique = "No screenshot available for visual analysis."
        if "screenshot_path" in research_data:
            print("[Brand] Running visual analysis via Vision model...")
            img_b64 = self.encode_image(research_data["screenshot_path"])
            vision_prompt = "Analyze this website screenshot. Critique the layout, color palette, and professional feel. What is the first impression it gives to a customer?"
            visual_critique = self.vision_client.chat(vision_prompt, images=[img_b64])

        return {
            "audit": audit,
            "visual_critique": visual_critique
        }
