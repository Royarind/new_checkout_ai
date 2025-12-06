"""
Additional API endpoints for Wallet and Orders
Add this to backend/main.py after existing endpoints
"""

# =========== WALLET ENDPOINTS ===========

@app.get("/api/wallet/payment-methods")
async def get_payment_methods(user_id: int = 1):  # TODO: Get from JWT token
    """Get all payment methods for user"""
    from checkout_ai.users import ProfileService
    methods = ProfileService.get_payment_methods(user_id)
    return methods

@app.post("/api/wallet/add-card")
async def add_card(
    user_id: int = 1,  # TODO: From JWT
    label: str = "",
    card_number: str = "",
    card_holder_name: str = "",
    expiry_month: int = 0,
    expiry_year: int = 0,
    cvv: str = "",
    card_brand: str = "visa"
):
    """Add credit/debit card to wallet"""
    from checkout_ai.users import ProfileService
    
    card_id = ProfileService.add_card(
        user_id=user_id,
        label=label,
        card_number=card_number,
        card_holder_name=card_holder_name,
        expiry_month=expiry_month,
        expiry_year=expiry_year,
        cvv=cvv,
        card_brand=card_brand
    )
    
    return {"success": True, "card_id": card_id}

@app.post("/api/wallet/add-upi")
async def add_upi(user_id: int = 1, label: str = "", upi_id: str = ""):
    """Add UPI ID to wallet"""
    from checkout_ai.users import ProfileService
    
    payment_id = ProfileService.add_upi(
        user_id=user_id,
        label=label,
        upi_id=upi_id
    )
    
    return {"success": True, "payment_id": payment_id}

@app.delete("/api/wallet/payment-methods/{payment_id}")
async def delete_payment_method(payment_id: int, user_id: int = 1):
    """Delete a payment method"""
    from checkout_ai.users import ProfileService
    
    success = ProfileService.delete_payment_method(payment_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    return {"success": True}

# =========== ORDER ENDPOINTS ===========

@app.get("/api/orders")
async def get_orders(user_id: int = 1):
    """Get order history for user"""
    from checkout_ai.db import db
    
    orders = db.execute_query("""
        SELECT id, order_number, site_domain, site_name, order_url,
               total_amount, currency, status, category, ordered_at
        FROM orders
        WHERE user_id = ?
        ORDER BY ordered_at DESC
    """, (user_id,))
    
    return orders

@app.get("/api/orders/{order_id}")
async def get_order_details(order_id: int, user_id: int = 1):
    """Get detailed order information"""
    from checkout_ai.db import db
    
    order = db.fetch_one("""
        SELECT * FROM orders WHERE id = ? AND user_id = ?
    """, (order_id, user_id))
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get order items
    items = db.execute_query("""
        SELECT * FROM order_items WHERE order_id = ?
    """, (order_id,))
    
    return {**order, "items": items}

# =========== ANALYTICS ENDPOINTS ===========

@app.get("/api/analytics/spending")
async def get_spending_analytics(user_id: int = 1):
    """Get spending analytics by category"""
    from checkout_ai.db import db
    
    # Category breakdown
    category_spending = db.execute_query("""
        SELECT category, COUNT(*) as count, SUM(total_amount) as total
        FROM orders
        WHERE user_id = ? AND status = 'completed' AND category IS NOT NULL
        GROUP BY category
        ORDER BY total DESC
    """, (user_id,))
    
    # Monthly trend
    monthly_spending = db.execute_query("""
        SELECT 
            strftime('%Y-%m', ordered_at) as month,
            COUNT(*) as order_count,
            SUM(total_amount) as total
        FROM orders
        WHERE user_id = ? AND status = 'completed'
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
    """, (user_id,))
    
    return {
        "by_category": category_spending,
        "by_month": monthly_spending
    }
