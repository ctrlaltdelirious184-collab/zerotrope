import json
import os
from utils.ollama_client import OllamaClient

class MemoryAgent:
    def __init__(self, memory_file="knowledge/agency_memory.json"):
        self.client = OllamaClient()
        self.memory_file = memory_file

    def run(self, business_name, intel_data, brand_data, strategy_data):
        """
        Distills the most successful strategic 'wins' from a project run and saves them to memory.
        """
        print(f"[Memory] Distilling key lessons from {business_name}...")
        
        prompt = f"""
        You are the 'Agency Archivist'. You are analyzing a completed marketing project.
        
        Business: {business_name}
        Unique Angle Found: {intel_data.get('intel_brief', '')[:500]}
        Core Narrative: {brand_data.get('audit', '')[:500]}
        Strategy Highlights: {strategy_data[:500]}
        
        Goal: Distill exactly ONE high-impact 'Lesson Learned' or 'Strategic Template' from this run. 
        What worked? Why was this angle unique? 
        
        Format your response as a valid JSON object:
        {{
            "niche": "The industry name",
            "angle": "One sentence summary of the unique hook",
            "takeaway": "What should we remember for next time we see this niche?",
            "timestamp": "Current date"
        }}
        
        Output ONLY the JSON. No conversational filler.
        """
        
        response = self.client.chat(prompt, system="You are a data-driven Agency Strategist.")
        
        # Clean response
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            new_memory = json.loads(response)
            
            # Load existing memory
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r") as f:
                    try:
                        memories = json.load(f)
                    except json.JSONDecodeError:
                        memories = []
            else:
                memories = []
                
            memories.append(new_memory)
            
            # Save back (keep only last 20 for token efficiency)
            with open(self.memory_file, "w") as f:
                json.dump(memories[-20:], f, indent=2)
                
            return new_memory
        except Exception as e:
            print(f"[Memory] Failed to save memory: {e}")
            return None
