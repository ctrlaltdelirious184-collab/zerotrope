"""
Gemini 2.0 Flash Automated Image Editing Agent
Uses google-genai SDK and gemini-2.0-flash-exp to edit images multimodal-style
with built-in rate-limit handling and logging.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from google import genai
from google.genai import types
from google.genai.errors import APIError
from PIL import Image

# Load environment variables if running directly
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

class GeminiImageAgent:
    def __init__(self, api_key=None, model="gemini-2.5-flash-image"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY must be provided or set as an environment variable."
            )
        self.model = model
        # Initialize Google GenAI client
        self.client = genai.Client(api_key=self.api_key)

    def edit_image(self, input_image_path, instruction, output_folder, max_retries=5, base_delay=3):
        """
        Edits an image using the Gemini multimodal image-to-image capabilities.
        Handles rate limits (429 / 15 RPM) using exponential backoff.
        """
        input_path = Path(input_image_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input image not found: {input_image_path}")

        output_dir = Path(output_folder)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Loading input image: {input_path.name}")
        img = Image.open(input_path).convert("RGB")

        # Configure response modalities for IMAGE and TEXT
        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            temperature=0.4
        )

        prompt = f"""You are an expert AI photo retoucher.
Your task is to edit the provided photo according to this instruction:
"{instruction}"

━━━ CRITICAL RULES ━━━
1. Preserve the identity, facial features, and hair of the person exactly.
2. Only change the specific elements mentioned in the instruction.
3. Match the existing lighting, shadows, composition, and photorealistic style.
"""

        print(f"Sending request to Gemini ({self.model})...")
        response_image_bytes = None
        response_text = ""

        # Exponential backoff retry loop
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[img, prompt],
                    config=config
                )

                # Parse the response parts
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        response_image_bytes = part.inline_data.data
                    elif part.text:
                        response_text += part.text

                if response_image_bytes:
                    break
                else:
                    raise ValueError("API responded successfully, but returned no image data.")

            except (APIError, Exception) as e:
                status_code = getattr(e, "code", None)
                # Check for rate limit status (429 or RESOURCE_EXHAUSTED)
                is_rate_limit = (status_code == 429) or ("429" in str(e)) or ("RESOURCE_EXHAUSTED" in str(e))

                if is_rate_limit and attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    print(f"Rate limit hit (429). Retrying in {sleep_time}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    print(f"Error occurred during API call: {e}")
                    raise e

        if not response_image_bytes:
            raise RuntimeError("Failed to generate edited image after retries.")

        # Generate unique filename for the output image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_instruction = "".join(c for c in instruction if c.isalnum() or c in " _-").strip().replace(" ", "_")[:30]
        output_filename = f"edited_{safe_instruction}_{timestamp}.png"
        output_path = output_dir / output_filename

        # Save output image
        with open(output_path, "wb") as f:
            f.write(response_image_bytes)
        print(f"Success! Edited image saved to: {output_path}")

        # Log the edit
        self._log_edit(output_dir, input_path, output_path, instruction, response_text)

        return output_path, response_text

    def _log_edit(self, output_dir, input_path, output_path, instruction, response_text):
        log_path = output_dir / "edit_log.json"
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "original_image": str(input_path.resolve()),
            "edited_image": str(output_path.resolve()),
            "instruction": instruction,
            "api_response_text": response_text.strip(),
            "model_used": self.model
        }

        # Read existing logs or create new list
        logs = []
        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                pass

        logs.append(log_entry)

        # Write back updated logs
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)
        print("Logged edit entry to edit_log.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini 2.0 Automated Image Editor")
    parser.add_argument("--image", type=str, help="Path to input image")
    parser.add_argument("--instruction", type=str, help="Outfit/Expression edit instruction")
    parser.add_argument("--output", type=str, help="Folder to save edited images")
    parser.add_argument("--run-test", action="store_true", help="Run the default sample test run")

    args = parser.parse_args()

    # Create agent instance
    try:
        agent = GeminiImageAgent()
    except Exception as e:
        print(f"Initialization error: {e}")
        sys.exit(1)

    if args.run_test:
        # Default test parameters
        test_image = r"C:\Users\Evan\Desktop\AI Influencer\chloe_dawson\images\10_chloe dawson\0712d238-eaf7-4304-a3d3-ca030a5404fd.png"
        test_instruction = "Change outfit to a casual streetwear look, keep the face and expression identical"
        test_output = r"C:\Users\Evan\Desktop\AI Influencer\chloe_dawson\images\outfit_edits"

        print("=== Running Simple Test Run ===")
        print(f"Input: {test_image}")
        print(f"Instruction: {test_instruction}")
        print(f"Output Directory: {test_output}")
        print("================================")

        try:
            out_file, caption = agent.edit_image(test_image, test_instruction, test_output)
            print("\nTest completed successfully!")
            print(f"Output File: {out_file}")
            print(f"Notes: {caption}")
        except Exception as e:
            print(f"\nTest run failed: {e}")
            sys.exit(1)
            
    elif args.image and args.instruction and args.output:
        try:
            agent.edit_image(args.image, args.instruction, args.output)
        except Exception as e:
            print(f"Error running edit: {e}")
            sys.exit(1)
    else:
        parser.print_help()
