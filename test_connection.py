from utils.ai_client import AIClient
import sys

def test():
    try:
        client = AIClient()
        print(f"Connecting to AI client (provider: {client.provider})...")
        response = client.chat("Say 'AI is online' if you see this.")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error connecting to AI: {str(e)}")

if __name__ == "__main__":
    test()
