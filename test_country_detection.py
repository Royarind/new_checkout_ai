"""Test country detection"""
from src.checkout_ai.utils.country_detector import detect_country_from_url, get_country_config

# Test URLs
test_urls = [
    ('https://amazon.in/product', 'IN'),
    ('https://amazon.co.uk/item', 'GB'),
    ('https://amazon.com/item', 'US'),
    ('https://flipkart.com/product', 'IN'),
    ('https://myntra.com/item', 'IN'),
    ('https://example.com', 'US'),
    ('https://example.co.uk', 'GB'),
]

print("=" * 60)
print("COUNTRY DETECTION TEST")
print("=" * 60)

for url, expected in test_urls:
    detected = detect_country_from_url(url)
    status = "PASS" if detected == expected else "FAIL"
    print(f"{status} {url:35} -> {detected} (expected: {expected})")

print("\n" + "=" * 60)
print("COUNTRY CONFIG TEST")
print("=" * 60)

for country_code in ['IN', 'US', 'GB', 'CA', 'AU']:
    config = get_country_config(country_code)
    print(f"\n{country_code}: {config['name']}")
    print(f"  Postal: {config['postal_code_label']} ({config['postal_code_example']})")
    print(f"  Currency: {config['currency_symbol']} {config['currency_code']}")
    print(f"  Phone: {config['phone_example']}")
