import os
from utils.ollama_client import OllamaClient
from utils.gemini_client import GeminiClient

class AIClient:
    def __init__(self, model=None):
        self.provider = "gemini"
        self.client = GeminiClient(model=model)

    def chat(self, prompt, system=None, images=None, stream=False, temperature=0.2):
        """
        Delegates the chat call to the configured Gemini provider.
        """
        return self.client.chat(prompt, system=system, images=images, temperature=temperature)


if __name__ == "__main__":
    client = AIClient()
    print(f"Factory initialized with provider: {client.provider}")
    print(client.chat("Hello, which provider are you using?"))
