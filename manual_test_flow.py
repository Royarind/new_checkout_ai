
import asyncio
import os
import sys
import logging
import json
import argparse

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
# DEFAULT TEST CONFIGURATION (if no JSON provided)
# ==========================================
DEFAULT_TEST_CONFIG = {
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
        },
        "wallet": {
            "preferredPaymentMethod": "credit_card",
            "cardNumber": "4111111111111111",
            "cardExpiry": "12/25",
            "cardCVV": "123"
        }
    },
    "tasks": [
        {
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

def load_json_config(args):
    """Load JSON configuration from file or command-line argument"""
    
    # Priority 1: JSON file
    if args.json_file:
        logger.info(f"Loading JSON from file: {args.json_file}")
        try:
            with open(args.json_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info("✅ JSON file loaded successfully")
            return config
        except FileNotFoundError:
            logger.error(f"❌ File not found: {args.json_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in file: {e}")
            sys.exit(1)
    
    # Priority 2: JSON string
    elif args.json:
        logger.info("Loading JSON from command-line argument")
        try:
            config = json.loads(args.json)
            logger.info("✅ JSON string parsed successfully")
            return config
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON string: {e}")
            sys.exit(1)
    
    # Priority 3: Default config
    else:
        logger.info("No JSON provided, using DEFAULT_TEST_CONFIG")
        return DEFAULT_TEST_CONFIG

async def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Manual test flow for checkout automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default config
  python manual_test_flow.py

  # Load from JSON file
  python manual_test_flow.py --json-file test_config.json

  # Provide JSON directly
  python manual_test_flow.py --json '{"customer": {...}, "tasks": [...]}'

  # Pretty print config without running
  python manual_test_flow.py --dry-run
        """
    )
    
    parser.add_argument(
        '--json-file',
        type=str,
        help='Path to JSON file containing complete test configuration'
    )
    
    parser.add_argument(
        '--json',
        type=str,
        help='Complete JSON configuration as a string'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print configuration and exit without running automation'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    test_config = load_json_config(args)
    
    print("\n" + "="*50)
    print("MANUAL TEST FLOW - JSON INPUT")
    print("="*50)
    print("\n📋 Configuration:")
    print(json.dumps(test_config, indent=2))
    print("\n" + "="*50 + "\n")
    
    # Dry-run mode
    if args.dry_run:
        print("🔍 DRY-RUN MODE: Configuration validated, exiting without running automation.")
        return
    
    try:
        # Run the actual flow
        print("🚀 Starting automation...\n")
        result = await run_full_flow(test_config)
        
        print("\n" + "="*50)
        if result.get('success'):
            print("✅ TEST PASSED")
            print(f"Final Message: {result.get('message', 'No message')}")
            if result.get('final_url'):
                print(f"Final URL: {result.get('final_url')}")
        else:
            print("❌ TEST FAILED")
            print(f"Error: {result.get('error')}")
            if result.get('phase'):
                print(f"Failed at phase: {result.get('phase')}")
            
        print("="*50 + "\n")
        
    except Exception as e:
        logger.exception(f"❌ FATAL SCRIPT ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
