import subprocess
import time
import re
import os

def auto_start_cloudflare():
    print("Killing lingering tunnels...")
    subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)

    print("Starting fresh Cloudflare Tunnel...")
    process = subprocess.Popen(
        ["cloudflared.exe", "tunnel", "--url", "http://localhost:8000"],
        stderr=subprocess.PIPE,
        text=True
    )

    url = None
    print("Waiting for Cloudflare to assign a URL...")

    for line in process.stderr:
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match:
            url = match.group(0)
            break

    if url:
        print(f"\n✅ TUNNEL URL: {url}")

        # Check if we have a permanent custom domain (api.zerotrope.co)
        # If so, no need to update config.js — just report the tunnel is live
        config_js_path = "config.js"
        if os.path.exists(config_js_path):
            with open(config_js_path, "r", encoding="utf-8") as f:
                config_content = f.read()

            # Only update if not using permanent domain
            if "api.zerotrope.co" not in config_content:
                config_content = re.sub(
                    r"window\.ZEROTROPE_PIPELINE_URL = \'https://[^\']+\';",
                    f"window.ZEROTROPE_PIPELINE_URL = \'{url}\';",
                    config_content
                )
                with open(config_js_path, "w", encoding="utf-8") as f:
                    f.write(config_content)
                print("✅ config.js updated with new tunnel URL.")

                # Auto-push to GitHub
                subprocess.run(["git", "add", "config.js"])
                subprocess.run(["git", "commit", "-m", f"Auto-sync Cloudflare URL: {url}"])
                subprocess.run(["git", "push"])
                print("🚀 Pushed to GitHub — Vercel will update in ~30 seconds.")
            else:
                print("✅ Permanent domain active (api.zerotrope.co) — no config update needed.")
        else:
            print("⚠️  config.js not found in current directory.")

        print("\n⚠️  LEAVE THIS TERMINAL OPEN. Closing it kills the tunnel.\n")
        process.wait()
    else:
        print("❌ Failed to grab Cloudflare URL. Did cloudflared crash?")

if __name__ == "__main__":
    auto_start_cloudflare()