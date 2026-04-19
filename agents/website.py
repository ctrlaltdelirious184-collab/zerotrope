from utils.ollama_client import OllamaClient
import os

class WebsiteAgent:
    def __init__(self):
        self.client = OllamaClient()

    def run(self, business_name, brand_data, audience_data, content_data, intel_data=None):
        """
        Generates a CINEMATIC, PRODUCTION-GRADE landing page.
        Enforces 'Rich Aesthetics' and 'Visual Excellence' with a GUARANTEED 2026 Design System.
        """
        print(f"[Website] Architecting premium 'Mantle UI' landing page for {business_name}...")
        
        unique_angle = intel_data.get("intel_brief", "") if intel_data else "A premium, high-quality service."
        
        # We provide a BASE CSS SKELETON to ensure 'Rich Aesthetics' NO MATTER WHAT.
        # This prevents the LLM from reverting to "shapes with black and white".
        css_skeleton = """
        :root {
            --bg: #050510;
            --accent-primary: #00E5FF;
            --accent-secondary: #CC00FF;
            --glass-bg: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.1);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: var(--bg); 
            color: #fff; 
            font-family: 'Inter', sans-serif; 
            overflow-x: hidden;
            background-image: radial-gradient(circle at 50% -20%, #1a1a3a 0%, transparent 50%),
                              radial-gradient(circle at 10% 50%, #0c0c22 0%, transparent 30%);
        }
        .glass-panel {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8);
        }
        .neon-border {
            border: 1px solid transparent;
            background-image: linear-gradient(var(--bg), var(--bg)), linear-gradient(to right, var(--accent-primary), var(--accent-secondary));
            background-origin: border-box;
            background-clip: padding-box, border-box;
        }
        .hero {
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 0 10%;
            position: relative;
        }
        h1 { font-family: 'Outfit', sans-serif; font-size: 5rem; font-weight: 800; line-height: 1.1; margin-bottom: 2rem; background: linear-gradient(to right, #fff, #888); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-glow {
            padding: 1.5rem 3rem;
            background: linear-gradient(to right, var(--accent-primary), var(--accent-secondary));
            border: none;
            border-radius: 50px;
            color: #fff;
            font-weight: bold;
            font-size: 1.1rem;
            cursor: pointer;
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.4);
            transition: 0.3s;
        }
        .btn-glow:hover { transform: scale(1.05); box-shadow: 0 0 40px rgba(204, 0, 255, 0.6); }
        """

        prompt = f"""
        You are a Master Creative Coder. 
        BUILD A CINEMATIC, HIGH-CONVERSION LANDING PAGE FOR: {business_name}.
        
        STRICT COMPONENT LIST:
        1. Sticky Nav: Translucent glass-blur.
        2. Hero: Massive typography showing the 'Unique Angle'. Add a floating 3D effect.
        3. Services: 3 'Glassmorphism' cards with neon-luminous strokes.
        4. Branding Narrative: A section with 'Cinematic Depth' and ambient lighting meshes.
        5. lead Form: A centerpiece modal.
        
        CSS TO USE (MANDATORY):
        {css_skeleton}
        
        CONTENT DATA:
        Business: {business_name}
        Core Strategy: {unique_angle[:1500]}
        Brand Narrative: {brand_data.get('audit', '')[:1000]}
        
        IMAGE MAPPINGS (Use these specific Unsplash URLs for maximum quality):
        - Hero BG: https://images.unsplash.com/photo-1639322537228-f710d846310a?auto=format&fit=crop&q=80 (Futuristic Digital)
        - Services: https://images.unsplash.com/photo-1620712943543-bcc4638ef001?auto=format&fit=crop&q=80 (AI Intelligence)
        
        Output ONLY the code for index.html. Include the CSS above in the <style> tag. No talk.
        """
        
        site_code = self.client.chat(prompt, system="You are the Creative Director at a world-class digital agency. You do not build basic sites. You build masterpieces.")
        
        if "```html" in site_code:
            site_code = site_code.split("```html")[1].split("```")[0].strip()
        elif "```" in site_code:
            site_code = site_code.split("```")[1].split("```")[0].strip()

        site_dir = os.path.join(os.getcwd(), "website_output")
        if not os.path.exists(site_dir):
            os.makedirs(site_dir)
            
        output_path = os.path.join(site_dir, "index.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(site_code)
            
        return output_path
