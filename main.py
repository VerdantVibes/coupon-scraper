from openai import AsyncOpenAI
import json
from typing import List
from pydantic import BaseModel
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class CouponCode(BaseModel):
    code: str

class CouponMappingList(BaseModel):
    coupons: List[CouponCode]

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# First get the response
async def get_response():
    response = await client.responses.create(
        model="gpt-5",
        tools=[{"type": "web_search_preview"}],
        input="find all working coupon on woxer.com"
    )
    with open('response.json', 'w') as f:
        json.dump(response.model_dump(), f, indent=2)
    return response

# Now parse the response to extract coupon codes
async def parse_response(response_text):
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

    list = parsed_response.choices[0].message.parsed

    # Extract just the coupon code strings
    coupon_codes = [coupon.code for coupon in list.coupons]

    # Save the coupon codes list to JSON
    with open('coupon_codes.json', 'w') as f:
        json.dump(coupon_codes, f, indent=2)

    print("Coupon codes saved to coupon_codes.json")
    print(f"Found {len(coupon_codes)} coupon codes")

async def main():
    response = await get_response()
    await parse_response(response.output_text)

asyncio.run(main())