"""
Special Sites Module
Site-specific handlers for e-commerce sites with unique checkout flows
"""

from .dillards_automator import is_dillards, handle_dillards_checkout
from .farfetch_automator import is_farfetch, handle_farfetch_checkout

# Site detection registry
SITE_HANDLERS = {
    'dillards.com': {
        'detector': is_dillards,
        'checkout_handler': handle_dillards_checkout
    },
    'farfetch.com': {
        'detector': is_farfetch,
        'checkout_handler': handle_farfetch_checkout
    }
}

async def get_site_specific_checkout_handler(page):
    """
    Detect site and return appropriate checkout handler
    Returns: handler function or None
    """
    url = page.url.lower()
    
    for domain, handlers in SITE_HANDLERS.items():
        if domain in url:
            return handlers['checkout_handler']
    
    return None
