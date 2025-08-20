import asyncio
import subprocess
import sys
import json
import requests
from typing import List, Dict, Any

def fetch_sites_from_api(store_id: int = None, page: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch sites from the API"""
    base_url = "http://49.13.237.126/api/sites"
    
    params = {
        'page': page,
        'limit': limit
    }
    
    if store_id:
        params['store_id'] = store_id
    
    try:
        response = requests.get(base_url, params=params, headers={'accept': 'application/json'})
        response.raise_for_status()
        data = response.json()
        return data.get('data', [])
    except Exception as e:
        print(f"❌ Error fetching sites: {e}")
        return []

def get_all_sites() -> List[str]:
    """Get all unique site domains from the API"""
    all_sites = []
    page = 1
    
    while True:
        print(f"📡 Fetching sites page {page}...")
        sites_data = fetch_sites_from_api(page=page, limit=100)
        
        if not sites_data:
            break
            
        for site in sites_data:
            domain = site.get('store_domain')
            if domain and domain not in all_sites:
                all_sites.append(domain)
                print(f"  ✅ Found site: {domain}")
        
        # Check if there are more pages
        if len(sites_data) < 100:
            break
            
        page += 1
    
    return all_sites

async def run_main_for_site(site: str, index: int, total: int):
    """Run main.py for a specific site"""
    print(f"\n{'='*60}")
    print(f"🌐 Processing site {index}/{total}: {site}")
    print(f"{'='*60}")
    
    try:
        # Run main.py with the site as argument
        process = subprocess.run([
            sys.executable, 'main.py', site
        ], capture_output=True, text=True, encoding='utf-8')
        
        if process.returncode == 0:
            print(f"✅ Successfully processed {site}")
            print("Output:")
            print(process.stdout)
        else:
            print(f"❌ Failed to process {site}")
            print("Error:")
            print(process.stderr)
            
    except Exception as e:
        print(f"❌ Exception processing {site}: {e}")

async def main():
    """Main function to run all sites sequentially"""
    print("🚀 Starting sequential processing of all sites...")
    
    # Get all sites from API
    sites = get_all_sites()
    
    if not sites:
        print("❌ No sites found from API")
        return
    
    print(f"\n📋 Found {len(sites)} unique sites to process:")
    for i, site in enumerate(sites, 1):
        print(f"  {i}. {site}")
    
    # Process each site sequentially
    for i, site in enumerate(sites, 1):
        await run_main_for_site(site, i, len(sites))
        
        # Small delay between sites to avoid overwhelming the system
        if i < len(sites):
            print(f"\n⏳ Waiting 3 seconds before next site...")
            await asyncio.sleep(3)
    
    print(f"\n🎉 Completed processing all {len(sites)} sites!")

if __name__ == "__main__":
    asyncio.run(main())
