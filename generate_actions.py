import requests
import json
import os
from typing import List, Dict, Any

def fetch_sites_from_api(store_id: int = None, page: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch sites from the API
    
    Args:
        store_id (int, optional): Specific store ID to fetch
        page (int): Page number
        limit (int): Number of items per page
    
    Returns:
        List[Dict]: List of site configurations
    """
    url = "http://49.13.237.126/api/sites"
    params = {
        'page': page,
        'limit': limit
    }
    
    if store_id:
        params['store_id'] = store_id
    
    headers = {
        'accept': 'application/json'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        return data.get('data', [])
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching sites: {e}")
        return []

def convert_api_config_to_actions_format(api_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert API configuration format to actions.json format
    
    Args:
        api_config (Dict): Configuration from API
    
    Returns:
        Dict: Configuration in actions.json format
    """
    config = api_config.get('config', {})
    
    # Convert actions format
    actions = []
    for action in config.get('actions', []):
        actions.append({
            "name": action.get('name', ''),
            "selectors": action.get('selectors', []),
            "type": action.get('type', 'click'),
            "waitAfter": action.get('waitAfter', 5000),
            "event": action.get('event', '')
        })
    
    # Handle validation configuration
    code_validation = config.get('codeValidation', {})
    promo_code = {
        "elementAlert": code_validation.get('element', ''),
        "validText": code_validation.get('validText', '')
    }
    
    return {
        "baseUrl": config.get('baseUrl', ''),
        "productUrl": config.get('productUrl', ''),
        "actions": actions,
        "waitTime": config.get('waitTime', 5000),
        "promoCode": promo_code
    }

def generate_actions_json():
    """
    Generate actions.json file from API data
    """
    print("🔄 Fetching sites from API...")
    
    # Fetch all sites (without store_id to get all sites)
    all_sites = []
    page = 1
    
    while True:
        sites = fetch_sites_from_api(page=page, limit=100)
        if not sites:
            break
            
        all_sites.extend(sites)
        page += 1
        
        # Safety check to prevent infinite loop
        if page > 50:
            break
    
    print(f"📊 Found {len(all_sites)} sites")
    
    if not all_sites:
        print("❌ No sites found")
        return
    
    # Convert to actions.json format
    actions_data = {
        "defaultWaitTime": 1000,
        "sites": {}
    }
    
    for site in all_sites:
        store_domain = site.get('store_domain')
        if store_domain:
            print(f"🔄 Processing site: {store_domain}")
            actions_data["sites"][store_domain] = convert_api_config_to_actions_format(site)
    
    # Save to actions.json
    try:
        with open('actions.json', 'w', encoding='utf-8') as f:
            json.dump(actions_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Successfully generated actions.json with {len(actions_data['sites'])} sites")
        
        # Print summary
        print("\n📋 Sites added:")
        for domain in actions_data['sites'].keys():
            print(f"  - {domain}")
            
    except Exception as e:
        print(f"❌ Error saving actions.json: {e}")

def fetch_specific_store(store_id: int):
    """
    Fetch and add a specific store to actions.json
    
    Args:
        store_id (int): Store ID to fetch
    """
    print(f"🔄 Fetching store ID: {store_id}")
    
    sites = fetch_sites_from_api(store_id=store_id)
    
    if not sites:
        print(f"❌ No site found for store ID: {store_id}")
        return
    
    site = sites[0]  # Should be only one site for specific store_id
    store_domain = site.get('store_domain')
    
    if not store_domain:
        print("❌ No store domain found")
        return
    
    print(f"🔄 Processing site: {store_domain}")
    
    # Load existing actions.json if it exists
    actions_data = {
        "defaultWaitTime": 1000,
        "sites": {}
    }
    
    if os.path.exists('actions.json'):
        try:
            with open('actions.json', 'r', encoding='utf-8') as f:
                actions_data = json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading existing actions.json: {e}")
    
    # Add the new site
    actions_data["sites"][store_domain] = convert_api_config_to_actions_format(site)
    
    # Save updated actions.json
    try:
        with open('actions.json', 'w', encoding='utf-8') as f:
            json.dump(actions_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Successfully added {store_domain} to actions.json")
        
    except Exception as e:
        print(f"❌ Error saving actions.json: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # If store_id is provided as argument
        try:
            store_id = int(sys.argv[1])
            fetch_specific_store(store_id)
        except ValueError:
            print("❌ Invalid store ID. Please provide a number.")
    else:
        # Generate actions.json with all sites
        generate_actions_json()
