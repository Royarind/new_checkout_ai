"""
Demo: Complete Checkout Flow with Payment Automation
Shows: Wallet → Payment → Order Confirmation → History
"""

import sys
from pathlib import Path
import asyncio
from playwright.async_api import async_playwright

# Add src to path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

from checkout_ai.db import db
from checkout_ai.auth import AuthService
from checkout_ai.users import ProfileService
from checkout_ai.payments import PaymentAutomationService

async def demo_payment_automation():
    """
    Simulated payment automation flow
    Note: This is a demo - replace with actual site navigation
    """
    
    print("\n" + "="*60)
    print("PAYMENT AUTOMATION DEMO")
    print("="*60 + "\n")
    
    # 1. Get test user
    print("1. Authenticating user...")
    auth = AuthService.authenticate_user("test@example.com", "Test123!")
    user_id = auth['user']['id']
    print(f"   User ID: {user_id}\n")
    
    # 2. Show saved payment methods
    print("2. Available payment methods:")
    payments = ProfileService.get_payment_methods(user_id)
    for pm in payments:
        if pm['payment_type'] == 'card':
            print(f"   [{pm['id']}] {pm['label']}: Card ending in {pm['card_number'][-4:]}")
        elif pm['payment_type'] == 'upi':
            print(f"   [{pm['id']}] {pm['label']}: {pm['upi_id']}")
    print()
    
    # 3. Simulate checkout flow
    print("3. Simulating checkout flow...")
    print("   (In real usage, this would navigate to payment page)")
    print()
    
    # For demo purposes, we'll just show the order capture structure
    print("4. Order confirmation capture:")
    print("   - Extract order number from confirmation page")
    print("   - Save to purchase history")
    print("   - Update payment method last_used_at")
    print()
    
    # 5. Show how to save an order
    print("5. Saving demo order to history...")
    
    demo_order_data = {
        'success': True,
        'order_number': 'AMZ-12345-XYZ',
        'order_url': 'https://amazon.com/order/confirmation/12345',
        'confirmed': True
    }
    
    demo_checkout_json = {
        'tasks': [{
            'url': 'https://amazon.com/product/abc',
            'quantity': 1
        }],
        'currency': 'USD'
    }
    
    order_id = await PaymentAutomationService.save_order_to_history(
        user_id=user_id,
        order_data=demo_order_data,
        checkout_json=demo_checkout_json
    )
    
    print(f"   Order saved with ID: {order_id}\n")
    
    # 6. View order history
    print("6. Order history:")
    orders = db.execute_query("""
        SELECT order_number, site_domain, status, ordered_at
        FROM orders
        WHERE user_id = ?
        ORDER BY ordered_at DESC
    """, (user_id,))
    
    for order in orders:
        print(f"   - {order['order_number']}: {order['site_domain']} ({order['status']})")
    
    print("\n" + "="*60)
    print("[OK] PAYMENT AUTOMATION DEMO COMPLETE")
    print("="*60 + "\n")
    
    print("INTEGRATION POINTS:")
    print("- fill_payment_from_wallet() - Auto-fill payment from saved methods")
    print("- submit_payment() - Click place order button")
    print("- capture_order_confirmation() - Extract order #")
    print("- save_order_to_history() - Save to database")
    print()

if __name__ == "__main__":
    asyncio.run(demo_payment_automation())
