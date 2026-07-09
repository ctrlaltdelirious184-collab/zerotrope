import os
import time

from google import genai
from google.genai import types

# Fallback model chain — tried in order when primary model fails due to quota or overload
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

class GeminiClient:
    def __init__(self, model=None, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        # Allow override via env var, otherwise use the first fallback model
        self.model = os.getenv("GEMINI_MODEL", model or FALLBACK_MODELS[0])
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set in environment variables.")
        self.client = genai.Client(api_key=self.api_key)

    def chat(self, prompt, system=None, images=None, temperature=0.2,
             max_retries=3, base_delay=5):
        """
        Calls the Gemini API to get a text response.
        Implements exponential backoff for 503 (overload) and rate-limit (429) errors.
        Tries fallback models if the primary model is exhausted.
        """
        config_params = {}
        if system:
            config_params["system_instruction"] = system
        if temperature is not None:
            config_params["temperature"] = temperature
        config = types.GenerateContentConfig(**config_params) if config_params else None

        contents = []
        if images:
            import base64
            import io
            from PIL import Image
            processed_images = []
            img_list = images if isinstance(images, list) else [images]
            for img in img_list:
                if isinstance(img, str):
                    try:
                        decoded = base64.b64decode(img)
                        pil_img = Image.open(io.BytesIO(decoded))
                        processed_images.append(pil_img)
                    except Exception:
                        processed_images.append(img)
                else:
                    processed_images.append(img)
            contents.extend(processed_images)
        contents.append(prompt)

        # Build model list — always try the configured model first, then fallbacks
        models_to_try = [self.model]
        for m in FALLBACK_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = None
        for model in models_to_try:
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config
                    )
                    if model != self.model:
                        print(f"[Gemini] Used fallback model: {model}")
                    return response.text or ""

                except Exception as e:
                    err_str = str(e)
                    last_error = err_str
                    is_overload = "503" in err_str or "UNAVAILABLE" in err_str
                    is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str

                    if is_overload and attempt < max_retries - 1:
                        # 503 overload — retry same model with backoff
                        sleep_time = base_delay * (2 ** attempt)
                        print(f"[Gemini] 503 overload on {model}, retrying in {sleep_time}s (attempt {attempt+1}/{max_retries})...")
                        time.sleep(sleep_time)
                        continue
                    elif is_rate_limit:
                        # 429 quota exhausted — move on to next fallback model immediately
                        print(f"[Gemini] Quota exhausted on {model}, trying next fallback...")
                        break
                    else:
                        # Unknown error — don't retry
                        break

        # All models exhausted — raise so bridge_api fallback handler can catch it
        raise RuntimeError(f"Gemini API unavailable after all retries. Last error: {last_error}")


if __name__ == "__main__":
    try:
        client = GeminiClient()
        print("Testing Gemini Client...")
        print(client.chat("Say 'Gemini is online' if you receive this."))
    except Exception as e:
        print(f"Failed to test Gemini client: {e}")
