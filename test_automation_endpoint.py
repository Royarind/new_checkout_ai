"""
Quick test to verify the automation endpoint works correctly
"""
import requests
import json
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Test automation endpoint
url = "http://localhost:8000/api/automation/start"

# Minimal test data
test_data = {
    "json_data": {
        "customer": {
            "contact": {
                "firstName": "Test",
                "lastName": "User",
                "email": "test@test.com",
                "phone": "+1234567890"
            },
            "shippingAddress": {
                "addressLine1": "123 Test St",
                "addressLine2": "",
                "city": "Test City",
                "province": "Test State",
                "postalCode": "12345",
                "country": "US"
            }
        },
        "tasks": [
            {
                "url": "https://example.com/product",
                "quantity": 1,
                "selectedVariant": {
                    "color": "Blue"
                }
            }
        ]
    }
}

print("Testing automation endpoint...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(test_data, indent=2)}")

try:
    response = requests.post(url, json=test_data, timeout=10)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("\n[OK] Automation endpoint is working!")
    else:
        print(f"\n[WARN] Unexpected status code: {response.status_code}")
        
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()

