# Payment Automation Integration Guide

## Current Status
✅ **JWT Integration Complete** - All endpoints use authentication  
✅ **Payment Service Ready** - `PaymentAutomationService` exists  
⏳ **Integration Pending** - Need to wire payment service to orchestrator

---

## Payment Service (Already Built)
Location: `src/checkout_ai/payments/automation_service.py`

**Key Functions:**
```python
# 1. Auto-fill payment from wallet
await PaymentAutomationService.fill_payment_from_wallet(page, user_id, payment_method_id)

# 2. Submit order
result = await PaymentAutomationService.submit_payment(page)

# 3. Capture confirmation
order = await PaymentAutomationService.capture_order_confirmation(page)

# 4. Save to database
await PaymentAutomationService.save_order_to_history(user_id, order, checkout_json)
```

---

## Integration Steps (For Manual Completion)

### Step 1: Add Payment Phase to Orchestrator
**File:** `main_orchestrator.py`

**After checkout flow completes** (around line 450-500), add:

```python
# === PAYMENT PHASE ===
logger.info("ORCHESTRATOR: Starting payment phase")

try:
    from checkout_ai.payments import PaymentAutomationService
    
    # Get user_id from json_input
    user_id = json_input.get('user_id', 1)  # TODO: Pass from backend
    
    # Auto-fill payment
    payment_result = await PaymentAutomationService.fill_payment_from_wallet(
        page=page,
        user_id=user_id,
        payment_method_id=None  # Use default
    )
    
    if not payment_result['success']:
        logger.error(f"Payment fill failed: {payment_result.get('error')}")
        return {
            'success': False,
            'phase': 'payment',
            'error': payment_result.get('error')
        }
    
    logger.info(f"Payment filled using: {payment_result.get('method_used')}")
    
    # Submit order
    order_result = await PaymentAutomationService.submit_payment(page)
    
    if not order_result['success']:
        logger.error(f"Order submission failed: {order_result.get('error')}")
        return {
            'success': False,
            'phase': 'order_submission',
            'error': order_result.get('error')
        }
    
    logger.info(f"Order placed: {order_result.get('order_number')}")
    
    # Save to database
    order_id = await PaymentAutomationService.save_order_to_history(
        user_id=user_id,
        order_data=order_result,
        checkout_json=json_input
    )
    
    logger.info(f"Order saved to database: ID {order_id}")
    
    return {
        'success': True,
        'phase': 'completed',
        'order_number': order_result.get('order_number'),
        'order_id': order_id,
        'final_url': page.url
    }
    
except Exception as e:
    logger.error(f"Payment phase error: {e}")
    return {
        'success': False,
        'phase': 'payment',
        'error': str(e)
    }
```

### Step 2: Update Backend Automation Endpoint
**File:** `backend/main.py` - `/api/automation/start` endpoint

Add `user_id` to json_data before passing to orchestrator:

```python
@app.post("/api/automation/start")
async def start_automation(
    request: AutomationRequest, 
    authorization: str = Header(None)
):
    try:
        # Get user_id from JWT
        user_id = await get_current_user_id(authorization)
        
        # Add user_id to json_data
        json_data = request.json_data
        json_data['user_id'] = user_id  # ADD THIS LINE
        
        # Rest of existing code...
```

### Step 3: Wait for Payment in Frontend
**File:** `frontend/src/App.tsx` - `handleConfirmStart` function

Update the automation flow to handle payment phase:

```typescript
const handleConfirmStart = async () => {
    setShowConfirmModal(false);
    setAutomationRunning(true);
    setCurrentPhase('variant_selection');
    
    try {
        const response = await apiCall('/api/automation/start', {
            method: 'POST',
            body: JSON.stringify({ json_data: jsonData })
        });
        
        const result = await response.json();
        
        if (result.status === 'completed' && result.order_number) {
            setAutomationStatus(
                `✅ Order placed! Order #${result.order_number}`
            );
            setCurrentPhase('order_confirmation');
        } else if (result.payment_ready) {
            setAutomationStatus(
                '✅ Payment page ready! Complete payment in browser.'
            );
            setCurrentPhase('payment_fill');
        } else {
            setAutomationStatus(`❌ Failed: ${result.error}`);
        }
    } catch (error) {
        setAutomationStatus(`❌ Error: ${error}`);
    } finally {
        setAutomationRunning(false);
    }
};
```

---

## Why Manual Integration?

The `main_orchestrator.py` is **666 lines** with complex flow control. Safe integration requires:
1. Understanding exact insertion point
2. Error handling for different checkout flows (guest vs login)
3. Testing on real sites
4. Handling 3DS/OTP interruptions

**Recommended**: Test on a simple site first (e.g., test Shopify store) before production use.

---

## Testing the Integration

### 1. Add a Payment Method
```
Visit: /wallet
Add test card: 4111 1111 1111 1111
```

### 2. Run Checkout
```
Product URL → Variants → Cart → Checkout → Payment (auto-fill) → Order!
```

### 3. Check Order History
```
Visit: /orders
Should show completed order
```

---

## Current Limitations

1. **No user_id in orchestrator** - Needs to be passed from backend
2. **No 3DS handling** - Will fail on cards requiring authentication
3. **No OTP detection** - SMS/email verification not handled
4. **Price extraction incomplete** - Total amount may be 0.00

Fix these after basic integration works!
