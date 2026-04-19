from utils.ollama_client import OllamaClient
import sys

def test():
    try:
        client = OllamaClient() # Uses llama3:latest by default
        print("Connecting to Ollama...")
        response = client.chat("Say 'Ollama is online' if you see this.")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error connecting to Ollama: {str(e)}")

if __name__ == "__main__":
    test()
