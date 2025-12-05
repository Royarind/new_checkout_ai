#!/usr/bin/env python3
"""Test script to verify JSON data parsing"""

import json

# Sample JSON payload
test_payload = {
    "customer": {
        "contact": {
            "email": "test@example.com",
            "firstName": "John",
            "lastName": "Doe",
            "phone": "1234567890"
        },
        "shippingAddress": {
            "addressLine1": "123 Main St",
            "addressLine2": "Apt 4B",
            "city": "New York",
            "province": "NY",
            "postalCode": "10001",
            "country": "United States"
        }
    }
}

print("=== Testing Data Parsing ===\n")

# Test contact data extraction
contact_data = test_payload.get('customer', {}).get('contact', {})
print("CONTACT DATA:")
print(f"  Email: {contact_data.get('email')}")
print(f"  First Name: {contact_data.get('firstName')}")
print(f"  Last Name: {contact_data.get('lastName')}")
print(f"  Phone: {contact_data.get('phone')}")

# Test address data extraction
address_data = test_payload.get('customer', {}).get('shippingAddress', {})
print("\nADDRESS DATA:")
print(f"  Address Line 1: {address_data.get('addressLine1') or address_data.get('address1') or address_data.get('address')}")
print(f"  Address Line 2: {address_data.get('addressLine2') or address_data.get('address2')}")
print(f"  City: {address_data.get('city')}")
print(f"  State: {address_data.get('province') or address_data.get('state')}")
print(f"  Postal: {address_data.get('postalCode') or address_data.get('zipCode') or address_data.get('zip')}")
print(f"  Country: {address_data.get('country')}")
print(f"  Phone: {address_data.get('phone') or address_data.get('phoneNumber')}")

print("\n=== All data parsed successfully ===")
