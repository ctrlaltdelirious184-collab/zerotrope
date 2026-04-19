import subprocess
import time
import urllib.request
import json
import re

print("Killing old ngrok processes...")
subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"], capture_output=True)

print("Starting fresh Ngrok...")
subprocess.Popen(["ngrok.exe", "http", "8000"])

print("Waiting for tunnel to open...")
time.sleep(3)

try:
    resp = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels")
    data = json.loads(resp.read().decode('utf-8'))
    url = data['tunnels'][0]['public_url']
    print(f"FOUND SECURE URL: {url}")
    
    config = open("config.js", "r", encoding="utf-8").read()
    config = re.sub(r"window\.ZEROTROPE_PIPELINE_URL\s*=\s*'.*';", f"window.ZEROTROPE_PIPELINE_URL = '{url}';", config)
    
    # Auto-Deploy to GitHub
    print("🚀 Committing and pushing to GitHub to trigger Vercel deployment...")
    subprocess.run(["git", "add", "config.js"])
    subprocess.run(["git", "commit", "-m", f"Auto-sync Ngrok Webhook"])
    subprocess.run(["git", "push"])
    
    print("\n🎉 SUCCESS: config.js has been perfectly updated and pushed to Vercel!")
    print("⚠️  LEAVE THIS TERMINAL OPEN. If you close this, the Ngrok tunnel dies.\n")
except Exception as e:
    print(f"FAILED: {e}")
