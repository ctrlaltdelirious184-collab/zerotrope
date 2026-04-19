import os
import re
from jinja2 import Environment, FileSystemLoader

class ReportAgent:
    def __init__(self, template_dir="templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def run(self, business_name, research_data, brand_data, audience_data, strategy_data, content_data, intel_data=None, website_path=None):
        """
        Renders the final HTML report.
        """
        print("[Report] Assembling final HTML package...")
        
        # Sanitize business name for filename
        clean_name = re.sub(r'[^a-zA-Z0-9]', '_', business_name.lower()).strip('_')
        # Shrink underscores
        clean_name = re.sub(r'__+', '_', clean_name)
        
        template = self.env.get_template("report.html.jinja")
        
        html_content = template.render(
            business_name=business_name,
            intel_brief=intel_data.get("intel_brief", "") if intel_data else "",
            brand_audit=brand_data.get("audit", ""),
            visual_critique=brand_data.get("visual_critique", ""),
            audience_data=audience_data,
            strategy_data=strategy_data,
            content_data=content_data,
            website_path=website_path
        )
        
        # Save output
        output_filename = f"report_{clean_name}.html"
        output_path = os.path.abspath(os.path.join(os.getcwd(), output_filename))
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return output_path
