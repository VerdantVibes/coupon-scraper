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

async def validate_coupons(coupon_codes: List[str], target_site: str):
    """Validate coupons using validator.js script"""
    valid_coupons = []
    
    print(f"Starting validation for {len(coupon_codes)} coupons on {target_site}")
    
    for i, coupon in enumerate(coupon_codes, 1):
        print(f"Validating coupon {i}/{len(coupon_codes)}: {coupon}")
        
        try:
            # Run validator.js script for each coupon
            result = subprocess.run([
                'node', 'validator.js',
                f'--coupon={coupon}',
                f'--domain={target_site}'
            ], capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            # Check if validation was successful
            if result.returncode == 0:
                # Parse the result.json file to check if coupon is valid
                try:
                    with open('./output/result.json', 'r') as f:
                        validation_result = json.load(f)
                    
                    is_valid = validation_result.get('couponIsValid', False)
                    
                    # Save to database
                    if is_valid:
                        await save_to_database(target_site, coupon, True)
                    
                    if is_valid:
                        valid_coupons.append({
                            'code': coupon,
                            'site': target_site,
                            'validated_at': validation_result.get('timestamp', ''),
                            'logs': validation_result.get('logs', [])
                        })
                        print(f"✅ {coupon} is VALID!")
                    else:
                        print(f"❌ {coupon} is INVALID")
                        
                except FileNotFoundError:
                    print(f"⚠️ Could not read validation result for {coupon}")
                except json.JSONDecodeError:
                    print(f"⚠️ Invalid JSON in validation result for {coupon}")
            else:
                print(f"⚠️ Validation failed for {coupon}: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print(f"⏰ Validation timeout for {coupon}")
        except Exception as e:
            print(f"❌ Error validating {coupon}: {str(e)}")
    
    # Save valid coupons to JSON file
    with open('valid_coupons.json', 'w') as f:
        json.dump(valid_coupons, f, indent=2)
    
    print(f"\nValidation complete! Found {len(valid_coupons)} valid coupons out of {len(coupon_codes)}")
    print("Valid coupons saved to valid_coupons.json")
    
    return valid_coupons

async def main():
    target_site = "woxer.com"
    
    # Get coupon codes
    response = await get_response(target_site)
    coupon_codes = await parse_response(response.output_text)
    
    # Validate coupons
    valid_coupons = await validate_coupons(coupon_codes, target_site)
    
    # Print summary
    print(f"\n=== SUMMARY ===")
    print(f"Total coupons found: {len(coupon_codes)}")
    print(f"Valid coupons: {len(valid_coupons)}")
    print(f"Success rate: {(len(valid_coupons)/len(coupon_codes)*100):.1f}%" if coupon_codes else "0%")

asyncio.run(main())