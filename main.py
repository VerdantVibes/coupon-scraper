from openai import AsyncOpenAI
import json
from typing import List
from pydantic import BaseModel
import asyncio
import os
from dotenv import load_dotenv
import subprocess
import sys
import aiohttp
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

class CouponCode(BaseModel):
    code: str

class CouponMappingList(BaseModel):
    coupons: List[CouponCode]

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def save_to_database(site: str, code: str, valid: bool):
    """Save coupon validation result to database via API"""
    api_url = "http://66.220.29.193:7998/api/v1/records"
    
    payload = {
        "site": site,
        "code": code,
        "valid": valid,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    print(f"✅ Saved to DB: {code} ({'valid' if valid else 'invalid'})")
                    return True
                else:
                    print(f"❌ Failed to save to DB: {code} - Status: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Error saving to DB: {code} - {str(e)}")
        return False

# First get the response
async def get_response(site: str):
    print(f"Getting response for {site}")
    response = await client.responses.create(
        model="gpt-5",
        tools=[{"type": "web_search_preview"}],
        input=f"find all working coupon on {site}"
    )
    with open('response.json', 'w') as f:
        json.dump(response.model_dump(), f, indent=2)
        print(f"Response saved to response.json")
    return response

# Now parse the response to extract coupon codes
async def parse_response(response_text):
    print(f"Parsing response")
    parsed_response = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        response_format=CouponMappingList,
        messages=[
            {
                "role": "system",
                "content": "Extract all coupon codes from the text. Only return the coupon codes, nothing else."
            },
            {
                "role": "user",
                "content": f"Extract all coupon codes from this text:\n\n{response_text}"
            }
        ]
    )
    with open('parsed_response.json', 'w') as f:
        json.dump(parsed_response.model_dump(), f, indent=2)
    print(f"Parsed response saved to parsed_response.json")
    list = parsed_response.choices[0].message.parsed

    # Extract just the coupon code strings
    coupon_codes = [coupon.code for coupon in list.coupons]

    # Save the coupon codes list to JSON
    with open('coupon_codes.json', 'w') as f:
        json.dump(coupon_codes, f, indent=2)

    print("Coupon codes saved to coupon_codes.json")
    print(f"Found {len(coupon_codes)} coupon codes")
    
    return coupon_codes

async def validate_single_coupon_parallel(coupon: str, target_site: str, index: int, total: int):
    """Validate a single coupon in parallel"""
    print(f"Validating coupon {index}/{total}: {coupon}")
    
    try:
        # Set environment variables for better encoding handling
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['NODE_OPTIONS'] = '--max-old-space-size=4096'
        
        # Run the validator directly
        process = subprocess.Popen([
            'node', 'validator.js',
            f'--coupon={coupon}',
            f'--domain={target_site}'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
           env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
        # Initialize variables
        returncode = 1
        stdout_text = ""
        stderr_text = ""
        
        try:
            stdout, stderr = process.communicate()
            returncode = process.returncode
            
            # Decode output safely
            stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ""
            stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
            
        except Exception as e:
            stderr_text = f"Process error: {str(e)}"
            returncode = 1
        
        # Check if validation was successful
        if returncode == 0:
            # Parse the result.json file to check if coupon is valid
            try:
                # Find the output directory for this process
                output_dir = None
                for item in os.listdir('.'):
                    if item.startswith('./output-') or item.startswith('output-'):
                        output_dir = item
                        break
                
                if not output_dir or not os.path.exists(output_dir):
                    print(f"⚠️ Output directory does not exist for {coupon}")
                    return None
                    
                result_file = os.path.join(output_dir, 'result.json')
                if not os.path.exists(result_file):
                    print(f"⚠️ result.json file does not exist for {coupon}")
                    return None
                    
                with open(result_file, 'r') as f:
                    validation_result = json.load(f)
                
                is_valid = validation_result.get('couponIsValid', False)
                
                # Save to database
                if is_valid:
                    await save_to_database(target_site, coupon, True)
                
                if is_valid:
                    result = {
                        'code': coupon,
                        'site': target_site,
                        'validated_at': validation_result.get('timestamp', ''),
                        'logs': validation_result.get('logs', [])
                    }
                    print(f"✅ {coupon} is VALID!")
                    return result
                else:
                    print(f"❌ {coupon} is INVALID")
                    return None
                    
            except FileNotFoundError:
                print(f"⚠️ Could not read validation result for {coupon}")
                return None
            except json.JSONDecodeError:
                print(f"⚠️ Invalid JSON in validation result for {coupon}")
                return None
        else:
            print(f"⚠️ Validation failed for {coupon}: {stderr_text}")
            return None
            
    except Exception as e:
        print(f"❌ Error validating {coupon}: {str(e)}")
        return None

async def validate_coupons(coupon_codes: List[str], target_site: str, max_concurrent: int = 3):
    """Validate coupons using parallel validator.js processes"""
    valid_coupons = []
    
    # If coupon_codes is empty, try to load from existing JSON file
    if not coupon_codes:
        try:
            with open('coupon_codes.json', 'r') as f:
                coupon_codes = json.load(f)
            print(f"Loaded {len(coupon_codes)} coupon codes from existing coupon_codes.json file")
        except FileNotFoundError:
            print("❌ No coupon codes provided and no existing coupon_codes.json file found")
            return valid_coupons
        except json.JSONDecodeError:
            print("❌ Error reading coupon_codes.json file")
            return valid_coupons
    
    print(f"Starting parallel validation for {len(coupon_codes)} coupons on {target_site}")
    print(f"Running {max_concurrent} validations simultaneously")
    
    # Process coupons in batches to control concurrency
    for i in range(0, len(coupon_codes), max_concurrent):
        batch = coupon_codes[i:i + max_concurrent]
        batch_tasks = []
        
        for j, coupon in enumerate(batch):
            task = validate_single_coupon_parallel(coupon, target_site, i + j + 1, len(coupon_codes))
            batch_tasks.append(task)
        
        # Run batch in parallel
        print(f"\n🔄 Running batch {i//max_concurrent + 1} ({len(batch)} coupons)...")
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Process results
        for result in batch_results:
            if isinstance(result, Exception):
                print(f"❌ Exception in validation: {result}")
            elif result is not None:
                valid_coupons.append(result)
        
        # Small delay between batches to avoid overwhelming the system
        if i + max_concurrent < len(coupon_codes):
            print("⏳ Waiting 2 seconds before next batch...")
            await asyncio.sleep(2)
    
    # Save valid coupons to JSON file with simplified structure
    simplified_coupons = []
    for coupon in valid_coupons:
        simplified_coupons.append({
            "code": coupon['code'],
            "site": coupon['site']
        })
    
    with open('valid_coupons.json', 'w') as f:
        json.dump(simplified_coupons, f, indent=2)
    
    print(f"\nValidation complete! Found {len(valid_coupons)} valid coupons out of {len(coupon_codes)}")
    print("Valid coupons saved to valid_coupons.json")
    
    return valid_coupons

async def main():
    import sys
    
    # Get target site from command line argument
    if len(sys.argv) > 1:
        target_site = sys.argv[1]
        # Remove protocol if present (e.g., "https://www.woxer.com" -> "woxer.com")
        if target_site.startswith(('http://', 'https://')):
            from urllib.parse import urlparse
            parsed_url = urlparse(target_site)
            target_site = parsed_url.netloc
    else:
        target_site = "woxer.com"  # Default site
        print("Usage: python main.py <domain>")
        print("Example: python main.py woxer.com")
        print("Example: python main.py https://www.woxer.com")
        print(f"Using default site: {target_site}")
    
    print(f"Target site: {target_site}")
    
    # Check if the site exists in actions.json
    try:
        with open('actions.json', 'r') as f:
            actions_data = json.load(f)
        
        if target_site not in actions_data.get('sites', {}):
            print(f"❌ Site '{target_site}' not found in actions.json")
            print("Available sites:")
            for site in actions_data.get('sites', {}).keys():
                print(f"  - {site}")
            print("\nTo add this site, run: python generate_actions.py")
            return
        else:
            print(f"✅ Site '{target_site}' found in actions.json")
            
    except FileNotFoundError:
        print("❌ actions.json file not found")
        print("Please run: python generate_actions.py")
        return
    except json.JSONDecodeError:
        print("❌ Invalid actions.json file")
        return
    
    # Get coupon codes
    response = await get_response(target_site)
    coupon_codes = await parse_response(response.output_text)
    
    # Validate coupons in parallel (3 at a time)
    valid_coupons = await validate_coupons(coupon_codes, target_site, max_concurrent=3)
    
    # Print summary
    print(f"\n=== SUMMARY ===")
    print(f"Total coupons found: {len(coupon_codes)}")
    print(f"Valid coupons: {len(valid_coupons)}")
    print(f"Success rate: {(len(valid_coupons)/len(coupon_codes)*100):.1f}%" if coupon_codes else "0%")

asyncio.run(main())