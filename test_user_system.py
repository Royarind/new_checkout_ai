"""
Test script to verify SQLite user system
"""

import sys
from pathlib import Path

# Add src to path - fix the path resolution
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

from checkout_ai.db import create_database
from checkout_ai.auth import AuthService
from checkout_ai.users import ProfileService

def test_user_system():
    print("\n" + "="*60)
    print("TESTING SQLITE USER SYSTEM")
    print("="*60 + "\n")
    
    # 1. Create database
    print("1. Creating database...")
    db_path = create_database()
    print(f"   Database: {db_path}\n")
    
    # 2. Register a user
    print("2. Registering user...")
    try:
        user_id = AuthService.register_user(
            email="test@example.com",
            password="Test123!",
            full_name="Test User",
            country="IN"  # India
        )
        print(f"   User ID: {user_id}\n")
    except ValueError as e:
        print(f"   User already exists, logging in instead...\n")
    
    # 3. Authenticate user
    print("3. Authenticating user...")
    auth_result = AuthService.authenticate_user(
        email="test@example.com",
        password="Test123!"
    )
    print(f"   Token: {auth_result['access_token'][:50]}...")
    print(f"   User: {auth_result['user']}\n")
    
    user_id = auth_result['user']['id']
    
    # 4. Add shipping address
    print("4. Adding shipping address...")
    address_id = ProfileService.add_shipping_address(
        user_id=user_id,
        label="Home",
        recipient_name="Test User",
        address_line1="123 Test Street",
        city="Mumbai",
        state_province="Maharashtra",
        postal_code="400001",
        country="IN",
        phone="+91-9876543210",
        is_default=True
    )
    print(f"   Address ID: {address_id}\n")
    
    # 5. Add payment method (UPI for India)
    print("5. Adding UPI payment method...")
    payment_id = ProfileService.add_upi(
        user_id=user_id,
        label="My PhonePe",
        upi_id="testuser@phonepe",
        is_default=True
    )
    print(f"   Payment ID: {payment_id}\n")
    
    # 6. Add credit card
    print("6. Adding credit card (plain text - no encryption)...")
    card_id = ProfileService.add_card(
        user_id=user_id,
        label="Personal Visa",
        card_number="4111111111111111",  # Test card number
        card_holder_name="TEST USER",
        expiry_month=12,
        expiry_year=2025,
        cvv="123",
        card_brand="visa"
    )
    print(f"   Card ID: {card_id}\n")
    
    # 7. Add site credentials
    print("7. Adding site credentials...")
    cred_id = ProfileService.add_site_credentials(
        user_id=user_id,
        site_domain="amazon.in",
        site_name="Amazon India",
        email="test@example.com",
        password="AmazonPassword123",
        notes="Primary shopping account"
    )
    print(f"   Credential ID: {cred_id}\n")
    
    # 8. Retrieve all data
    print("8. Retrieving user data...")
    
    addresses = ProfileService.get_shipping_addresses(user_id)
    print(f"   Addresses: {len(addresses)}")
    for addr in addresses:
        print(f"     - {addr['label']}: {addr['city']}, {addr['country']}")
    
    payment_methods = ProfileService.get_payment_methods(user_id)
    print(f"   Payment Methods: {len(payment_methods)}")
    for pm in payment_methods:
        if pm['payment_type'] == 'card':
            print(f"     - {pm['label']}: Card ending in {pm['card_number'][-4:]}")
        elif pm['payment_type'] == 'upi':
            print(f"     - {pm['label']}: {pm['upi_id']}")
    
    site_creds = ProfileService.get_site_credentials(user_id)
    print(f"   Site Credentials: {len(site_creds)}")
    for cred in site_creds:
        print(f"     - {cred['site_name']}: {cred['email']}")
    
    print("\n" + "="*60)
    print("[OK] ALL TESTS PASSED!")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_user_system()
