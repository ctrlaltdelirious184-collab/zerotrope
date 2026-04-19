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
    open("config.js", "w", encoding="utf-8").write(config)
    print("SUCCESS: config.js has been perfectly updated!")
except Exception as e:
    print(f"FAILED: {e}")
