# Dillard's Checkout Button Fix

## Problem
Dillard's has **two checkout buttons**:
1. **Side Modal Button**: Text says "Checkout" but actually acts as "View Cart"
2. **Cart Page Button**: Text says "PROCEED TO CHECKOUT" (the correct one)

The agent was clicking the first button instead of the second.

## Solution
Created a Dillard's-specific handler that:
1. **Closes the side modal** first (if open)
2. **Finds and clicks "PROCEED TO CHECKOUT"** on the cart page
3. **Avoids modal buttons** by checking z-index and modal context

## Files Changed

### New Files
- `special_sites/dillards_automator.py` - Dillard's-specific checkout handler
- `special_sites/__init__.py` - Site handler registry
- `special_sites/README.md` - Documentation

### Modified Files
- `phase2/checkout_flow.py` - Added site-specific handler check
- `phase2/ai_checkout_flow.py` - Added site-specific handler check
- `phase2/checkout_dom_finder.py` - Improved button matching with better scoring
- `shared/checkout_keywords.py` - Reordered keywords (most specific first)

## How It Works

1. **Automatic Detection**: When URL contains `dillards.com`, the system automatically uses the special handler
2. **Modal Closure**: Closes any open side modals first
3. **Smart Button Selection**: Finds "PROCEED TO CHECKOUT" while avoiding modal buttons
4. **Fallback**: If special handler fails, falls back to generic logic

## Testing

Run your automation on Dillard's:
```bash
python app.py
# Enter Dillard's product URL when prompted
```

The system will:
- Detect Dillard's automatically
- Log: "Detected Dillards - using special handler"
- Close modal → Click "PROCEED TO CHECKOUT"

## Adding More Sites

To add handlers for other problematic sites:

1. Create `special_sites/yoursite_automator.py`
2. Implement `handle_yoursite_checkout(page)` function
3. Register in `special_sites/__init__.py`

Example:
```python
# special_sites/yoursite_automator.py
async def handle_yoursite_checkout(page):
    # Your custom logic
    return {'success': True}

def is_yoursite(url):
    return 'yoursite.com' in url.lower()

# special_sites/__init__.py
SITE_HANDLERS = {
    'yoursite.com': {
        'detector': is_yoursite,
        'checkout_handler': handle_yoursite_checkout
    }
}
```

## Debug Tool

Created `debug_checkout_button.py` to analyze buttons on any page:
```bash
python debug_checkout_button.py https://www.dillards.com/cart
```

This shows all buttons, their properties, and helps identify issues.
