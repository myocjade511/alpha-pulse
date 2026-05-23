#!/usr/bin/env python3
"""Deploy the latest index.html to Vercel."""
import json, urllib.request, os, sys

VC_TOKEN = os.environ.get("VERCEL_TOKEN", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, 'index.html')

if not os.path.exists(INDEX_PATH):
    print("No index.html found")
    sys.exit(1)

with open(INDEX_PATH) as f:
    html = f.read()

print(f"Deploying index.html ({len(html)} bytes)...")

payload = json.dumps({
    "name": "alpha-pulse",
    "files": [{"file": "index.html", "data": html}],
    "target": "production"
}).encode()

req = urllib.request.Request(
    "https://api.vercel.com/v12/deployments",
    data=payload,
    headers={
        "Authorization": f"Bearer {VC_TOKEN}",
        "Content-Type": "application/json"
    },
    method="POST"
)

resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
url = f"https://{resp.get('url', '?')}"
print(f"Deployed: {url}")
print(f"State: {resp.get('readyState','?')}")

# Save deploy info
info = {
    'last_deploy_url': url,
    'last_deployed_at': __import__('datetime').datetime.utcnow().isoformat(),
    'state': resp.get('readyState','?')
}
with open(os.path.join(BASE_DIR, 'deploy-info.json'), 'w') as f:
    json.dump(info, f, indent=2)
print("Done.")
