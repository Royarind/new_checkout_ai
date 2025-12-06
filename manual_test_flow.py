
import asyncio
import os
import sys
import logging

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main_orchestrator import run_full_flow
from dotenv import load_dotenv

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env
load_dotenv()

# ==========================================
# TEST CONFIGURATION - EDIT THIS SECTION
# ==========================================
TEST_CONFIG = {
    "customer": {
        "contact": {
            "firstName": "Roy",
            "lastName": "Arindam",
            "email": "aroy23@gmail.com",
            "phone": "555-0123"
        },
        "shippingAddress": {
            "addressLine1": "8600 Eversham Rd",
            "city": "Henrico",
            "province": "VA",
            "postalCode": "23294",
            "country": "United States"
        }
    },
    "tasks": [
        {
            # Example Product
            "url": "https://www.tommiecopper.com/full-back-support-shirt-mens-short-sleeve/",
            "quantity": 1,
            "selectedVariant": {
                "color": "Slate Grey",
                "size": "L"
            }
        }
    ]
}
# ==========================================

async def main():
    print("\n" + "="*50)
    print("STARTING MANUAL BACKEND TEST")
    print("="*50 + "\n")
    
    try:
        # Run the actual flow
        result = await run_full_flow(TEST_CONFIG)
        
        print("\n" + "="*50)
        if result.get('success'):
            print("✅ TEST PASSED")
            print(f"Final Message: {result.get('message', 'No message')}")
        else:
            print("❌ TEST FAILED")
            print(f"Error: {result.get('error')}")
            
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"\n❌ FATAL SCRIPT ERROR: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
