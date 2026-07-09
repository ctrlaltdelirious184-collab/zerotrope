import os
from utils.ollama_client import OllamaClient
from utils.gemini_client import GeminiClient

class AIClient:
    def __init__(self, model=None):
        self.provider = os.getenv("AI_PROVIDER", "").lower().strip()

        # Auto-detect: if GEMINI_API_KEY is set and provider not forced to ollama, use Gemini
        if not self.provider:
            if os.getenv("GEMINI_API_KEY"):
                self.provider = "gemini"
            else:
                self.provider = "ollama"

        if self.provider == "gemini":
            self.client = GeminiClient(model=model)
        else:
            ollama_model = model or os.getenv("OLLAMA_MODEL", "gemma3")
            self.client = OllamaClient(model=ollama_model)

    def chat(self, prompt, system=None, images=None, stream=False, temperature=0.2):
        """
        Delegates the chat call to the configured provider.
        If Gemini fails completely (quota + all fallbacks exhausted), attempts Ollama as emergency fallback.
        """
        if self.provider == "gemini":
            try:
                return self.client.chat(prompt, system=system, images=images, temperature=temperature)
            except RuntimeError as e:
                # Gemini exhausted all retries and fallbacks — try local Ollama as emergency backup
                print(f"[AIClient] Gemini unavailable: {e}")
                print("[AIClient] Attempting emergency fallback to local Ollama...")
                try:
                    ollama = OllamaClient(model=os.getenv("OLLAMA_MODEL", "gemma3"))
                    return ollama.chat(prompt, system=system, images=images, stream=stream)
                except Exception as ollama_err:
                    print(f"[AIClient] Ollama also unavailable: {ollama_err}")
                    raise RuntimeError(
                        "All AI providers unavailable. Gemini quota exhausted and Ollama is offline."
                    )
        else:
            return self.client.chat(prompt, system=system, images=images, stream=stream)


if __name__ == "__main__":
    client = AIClient()
    print(f"Factory initialized with provider: {client.provider}")
    print(client.chat("Hello, which provider are you using?"))
