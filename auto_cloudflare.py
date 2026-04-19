import subprocess
import time
import re

def auto_start_cloudflare():
    print("Killing lingering tunnels...")
    subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)

    print("Starting fresh Cloudflare Tunnel...")
    # Launch cloudflared and capture stderr (where it prints the URL)
    process = subprocess.Popen(
        ["cloudflared.exe", "tunnel", "--url", "http://localhost:8000"], 
        stderr=subprocess.PIPE, 
        text=True
    )

    url = None
    print("Waiting for Cloudflare to assign a URL...")
    
    # Tail the logs in real-time until we spot the URL
    for line in process.stderr:
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match:
            url = match.group(0)
            break

    if url:
        print(f"\n✅ SECURE URL ACQUIRED: {url}")
        
        # Patch config.js
        with open("config.js", "r", encoding="utf-8") as f:
            config = f.read()
            
        config = re.sub(r"window\.ZEROTROPE_PIPELINE_URL\s*=\s*'.*';", f"window.ZEROTROPE_PIPELINE_URL = '{url}';", config)
        
        with open("config.js", "w", encoding="utf-8") as f:
            f.write(config)
            
        print("✅ config.js updated automatically!")
        print("🚀 Committing and pushing to GitHub to trigger Vercel deployment...")
        
        # Auto-Deploy to GitHub
        subprocess.run(["git", "add", "config.js"])
        subprocess.run(["git", "commit", "-m", f"Auto-sync Cloudflare Webhook"])
        subprocess.run(["git", "push"])
        
        print("\n🎉 ALL DONE! Your Vercel frontend will automatically update in 30 seconds.")
        print("⚠️  LEAVE THIS TERMINAL OPEN. If you close this, the tunnel dies.\n")
        
        # Keep the script alive so the tunnel doesn't close
        process.wait()
    else:
        print("❌ Failed to grab Cloudflare URL. Has Cloudflare crashed?")

if __name__ == "__main__":
    auto_start_cloudflare()
