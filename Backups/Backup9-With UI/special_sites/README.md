# Special Sites Handlers

This folder contains site-specific automation handlers for e-commerce sites with unique checkout flows.

## Current Handlers

### Dillard's (`dillards_automator.py`)
**Problem**: Dillard's has two "Checkout" buttons:
1. Side modal button (labeled "Checkout" but acts as "View Cart")
2. Cart page button ("PROCEED TO CHECKOUT" - the correct one)

**Solution**: 
- Closes side modal first
- Then clicks "PROCEED TO CHECKOUT" on cart page
- Avoids clicking the wrong button in the modal

**Trigger**: Automatically detected when URL contains `dillards.com`

### Farfetch (`farfetch_automator.py`)
**Problem**: Farfetch may have modal overlays or unique checkout button patterns

**Solution**: 
- Closes any open modals first
- Finds and clicks checkout/proceed button
- Handles Farfetch-specific DOM structure

**Trigger**: Automatically detected when URL contains `farfetch.com`

## Adding New Site Handlers

1. Create new file: `special_sites/yoursite_automator.py`
2. Implement:
   ```python
   async def handle_yoursite_checkout(page):
       # Your custom logic
       return {'success': True/False}
   
   def is_yoursite(url):
       return 'yoursite.com' in url.lower()
   ```
3. Register in `special_sites/__init__.py`:
   ```python
   SITE_HANDLERS = {
       'yoursite.com': {
           'detector': is_yoursite,
           'checkout_handler': handle_yoursite_checkout
       }
   }
   ```

## How It Works

Both `checkout_flow.py` and `ai_checkout_flow.py` check for site-specific handlers before running generic logic:

```python
from special_sites import get_site_specific_checkout_handler
handler = await get_site_specific_checkout_handler(page)
if handler:
    return await handler(page)
```

This ensures site-specific logic takes priority over generic automation.
