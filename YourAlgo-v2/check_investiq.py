import os
import glob
import pandas as pd
import httpx
import json

print("=== CHECKING GITHUB REPO Amitrawal1/InvestIQ ===")
try:
    r = httpx.get("https://api.github.com/repos/Amitrawal1/InvestIQ/contents", headers={"User-Agent": "InvestIQ-Reader"}, timeout=10.0)
    print("GitHub API Status:", r.status_code)
    if r.status_code == 200:
        contents = r.json()
        print("Files/Directories:")
        for item in contents:
            print(f" - {item.get('name')} ({item.get('type')}) - {item.get('download_url')}")
    else:
        print("GitHub Error:", r.text[:300])
except Exception as e:
    print("GitHub Fetch Error:", e)

# Also check README if available
try:
    r_readme = httpx.get("https://raw.githubusercontent.com/Amitrawal1/InvestIQ/main/README.md", headers={"User-Agent": "InvestIQ-Reader"}, timeout=10.0)
    if r_readme.status_code == 200:
        print("\n=== README.md Content ===")
        print(r_readme.text[:1500])
    else:
        # try master branch
        r_readme = httpx.get("https://raw.githubusercontent.com/Amitrawal1/InvestIQ/master/README.md", headers={"User-Agent": "InvestIQ-Reader"}, timeout=10.0)
        if r_readme.status_code == 200:
            print("\n=== README.md (master) Content ===")
            print(r_readme.text[:1500])
except Exception as e:
    print("README Error:", e)

print("\n=== ANALYZING NSE DATA FOLDER ===")
nse_dir = r"c:\Users\patel\Desktop\Algo Trading\NSE data"
csv_files = glob.glob(os.path.join(nse_dir, "*.csv"))
print(f"Total CSV files found: {len(csv_files)}")

for cf in sorted(csv_files):
    size_kb = os.path.getsize(cf) / 1024
    base = os.path.basename(cf)
    print(f"\n--- File: {base} ({size_kb:.1f} KB) ---")
    try:
        df = pd.read_csv(cf, nrows=3)
        print("Columns:", list(df.columns))
        print("Sample row:")
        print(df.head(1).to_dict(orient="records"))
    except Exception as e:
        print("Read error:", e)
