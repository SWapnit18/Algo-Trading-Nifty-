import httpx
import json

base_url = "https://api.github.com/repos/Amitrawal1/InvestIQ/contents"
headers = {"User-Agent": "InvestIQ-Inspector"}

def inspect_dir(path=""):
    url = f"{base_url}/{path}" if path else base_url
    r = httpx.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return []

print("=== BACKEND DIRECTORY ===")
for item in inspect_dir("backend"):
    print(f"backend/{item['name']} ({item['type']})")
    if item['type'] == 'dir':
        for sub in inspect_dir(f"backend/{item['name']}"):
            print(f"  backend/{item['name']}/{sub['name']} ({sub['type']})")

print("\n=== ML DIRECTORY ===")
for item in inspect_dir("ml"):
    print(f"ml/{item['name']} ({item['type']})")
    if item['type'] == 'dir':
        for sub in inspect_dir(f"ml/{item['name']}"):
            print(f"  ml/{item['name']}/{sub['name']} ({sub['type']})")

print("\n=== FRONTEND DIRECTORY ===")
for item in inspect_dir("frontend"):
    print(f"frontend/{item['name']} ({item['type']})")
    if item['type'] == 'dir' and item['name'] in ['src', 'app']:
        for sub in inspect_dir(f"frontend/{item['name']}"):
            print(f"  frontend/{item['name']}/{sub['name']} ({sub['type']})")

# Fetch README content using utf-8 write to file
r_readme = httpx.get("https://raw.githubusercontent.com/Amitrawal1/InvestIQ/main/README.md", headers=headers)
if r_readme.status_code == 200:
    with open("investiq_readme.md", "w", encoding="utf-8") as f:
        f.write(r_readme.text)
    print("\nSaved investiq_readme.md")
