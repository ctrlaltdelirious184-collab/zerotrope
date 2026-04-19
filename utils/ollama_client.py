import httpx
import json
import sys

OLLAMA_BASE_URL = "http://127.0.0.1:11434/api"

class OllamaClient:
    def __init__(self, model="llama3:latest"):
        self.model = model

    def chat(self, prompt, system=None, images=None, stream=True):
        """
        Calls the Ollama chat API.
        """
        payload = {
            "model": self.model,
            "messages": [],
            "stream": stream
        }

        if system:
            payload["messages"].append({"role": "system", "content": system})
        
        message = {"role": "user", "content": prompt}
        if images:
            message["images"] = images
            
        payload["messages"].append(message)

        try:
            # We use trust_env=False to ensure we bypass any Windows system proxies that cause 503 errors
            with httpx.Client(timeout=300.0, trust_env=False) as client:
                if not stream:
                    response = client.post(f"{OLLAMA_BASE_URL}/chat", json=payload)
                    response.raise_for_status()
                    return response.json().get("message", {}).get("content", "")
                else:
                    full_response = ""
                    with client.stream("POST", f"{OLLAMA_BASE_URL}/chat", json=payload) as r:
                        r.raise_for_status()
                        for line in r.iter_lines():
                            if line:
                                body = json.loads(line)
                                if "message" in body:
                                    content = body["message"].get("content", "")
                                    full_response += content
                                    # We could yield here if we wanted true streaming to terminal
                                if body.get("done", False):
                                    break
                    return full_response
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"

# Example usage for testing
if __name__ == "__main__":
    client = OllamaClient()
    print(client.chat("Hello, tell me a short joke."))
