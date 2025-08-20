import subprocess
import json
import os
import asyncio
from typing import Tuple

async def validate_single_coupon(code: str, domain: str) -> Tuple[bool, str]:
    """
    Validate a single coupon code and return (is_valid, error_message)
    
    Args:
        code (str): The coupon code to validate
        domain (str): The domain to validate against (e.g., 'woxer.com')
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    try:
        # Set environment variables for better encoding handling
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['NODE_OPTIONS'] = '--max-old-space-size=4096'
        
        # Run the validator directly
        process = subprocess.Popen([
            'node', 'validator.js',
            f'--coupon={code}',
            f'--domain={domain}'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
           env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
        try:
            stdout, stderr = process.communicate()
            returncode = process.returncode
            
            # Decode output safely
            stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ""
            stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
            

        except Exception as e:
            return False, f"Process error: {str(e)}"
        
        # Check if validation was successful
        if returncode == 0:
            # Parse the result.json file to check if coupon is valid
            try:
                # Check if output directory exists
                if not os.path.exists('./output'):
                    return False, "Output directory does not exist"
                    
                if not os.path.exists('./output/result.json'):
                    return False, f"result.json file does not exist. stdout: {stdout_text[:100]}... stderr: {stderr_text[:100]}..."
                    
                with open('./output/result.json', 'r', encoding='utf-8') as f:
                    validation_result = json.load(f)
                
                is_valid = validation_result.get('couponIsValid', False)
                return is_valid, "Success"
                    
            except FileNotFoundError:
                return False, "Could not read validation result"
            except json.JSONDecodeError:
                return False, "Invalid JSON in validation result"
        else:
            return False, f"Validation failed: {stderr_text}"
            
    except Exception as e:
        return False, f"Error validating: {str(e)}"

async def main():
    """Example usage of the validate_single_coupon function"""
    
    # Example 1: Test a single coupon
    code = "WIFE15"
    domain = "woxer.com"
    
    print(f"Testing coupon: {code} on domain: {domain}")
    is_valid, error_msg = await validate_single_coupon(code, domain)
    
    if is_valid:
        print(f"✅ {code} is VALID!")
    else:
        print(f"❌ {code} is INVALID: {error_msg}")
    
    # Example 2: Test multiple coupons
    test_coupons = ["MEL", "FACEBOOK20", "INVALID_CODE"]
    domain = "woxer.com"
    
    print(f"\nTesting multiple coupons on {domain}:")
    for coupon in test_coupons:
        is_valid, error_msg = await validate_single_coupon(coupon, domain)
        status = "✅ VALID" if is_valid else "❌ INVALID"
        print(f"{coupon}: {status}")
        if not is_valid and error_msg != "Success":
            print(f"  Error: {error_msg}")

if __name__ == "__main__":
    asyncio.run(main())
