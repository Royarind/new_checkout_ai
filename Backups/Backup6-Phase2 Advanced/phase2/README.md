# Phase 2: Checkout Flow

Phase 2 handles the checkout process after products are added to cart in Phase 1.

## Architecture

### Files

1. **checkout_dom_finder.py** - Fresh DOM finder for checkout elements
   - `find_and_click_button()` - Find and click buttons by keyword matching
   - `find_input_by_label()` - Find form inputs by label text
   - `fill_input_field()` - Fill text input fields
   - `find_and_select_dropdown()` - Handle native SELECT and custom dropdowns

2. **checkout_flow.py** - Main checkout orchestration
   - `proceed_to_checkout()` - Click checkout button
   - `handle_guest_checkout()` - Select guest checkout (US) or login (India)
   - `fill_contact_info()` - Fill email, firstName, lastName, phone
   - `fill_shipping_address()` - Fill address including state dropdown
   - `run_checkout_flow()` - Main entry point

### Keywords

All keywords are defined in `/shared/checkout_keywords.py`:
- Checkout buttons: 'checkout', 'proceed to checkout', etc.
- Guest checkout: 'guest', 'continue as guest', etc.
- Form field labels: email, first name, address, state, zip, etc.

## Integration with Phase 1

Phase 2 receives the same `page` object from Phase 1, maintaining:
- Browser session
- Cookies
- Cart state
- No new browser launch

## Usage

### Via Main Orchestrator

```python
from main_orchestrator import run_full_flow

json_input = {
    "customer": {
        "contact": {
            "email": "user@example.com",
            "firstName": "John",
            "lastName": "Doe",
            "phone": "+1234567890"
        },
        "shippingAddress": {
            "addressLine1": "123 Main St",
            "addressLine2": "Apt 4",
            "city": "New York",
            "province": "New York",
            "postalCode": "10001",
            "country": "US"
        }
    },
    "tasks": [...]
}

result = await run_full_flow(json_input)
```

### Standalone Phase 2

```python
from phase2.checkout_flow import run_checkout_flow

# Assuming you have a page object from Phase 1
result = await run_checkout_flow(page, customer_data)
```

## Flow

1. **Checkout Button** - Click "Checkout" / "Proceed to Checkout"
2. **Guest Checkout** - Click "Guest Checkout" (US only)
3. **Contact Info** - Fill email, firstName, lastName, phone
4. **Continue** - Click continue if multi-step checkout
5. **Shipping Address** - Fill address, city, state (dropdown), zip
6. **Continue** - Proceed to payment (Phase 3)

## Logging

All logs use consistent format:
- **CHECKOUT DOM:** - DOM finder operations
- **CHECKOUT FLOW:** - Flow orchestration
- Format: `[HH:MM:SS]` timestamp on all logs
- No emojis, consistent with Phase 1

## Error Handling

- Retries: 3 attempts for buttons, 1 attempt for form fields
- Optional fields: addressLine2 won't cause failure if not found
- Detailed error messages with step information
- Returns: `{'success': bool, 'error': str, 'step': str, 'details': list}`

## State Dropdown

Handles both:
- **Native SELECT** - Uses `page.select_option()`
- **Custom dropdowns** - Clicks to open, then clicks option
- Matches by full name ("Texas") or abbreviation ("TX")

## Country-Based Logic

- **US**: Clicks guest checkout button
- **India**: Skips guest checkout (login required)
- Determined by: `customer.shippingAddress.country`
