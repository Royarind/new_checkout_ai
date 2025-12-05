"""
Special Sites Module
Site-specific handlers for e-commerce sites with unique checkout flows
"""

from .dillards_automator import handle_dillards_checkout, select_dillards_variant
from .farfetch_automator import handle_farfetch_checkout
from .patagonia_automator import select_patagonia_variant
from .heydude_automator import select_heydude_variant
from .karllagerfeld_automator import select_karllagerfeld_variant, navigate_to_checkout as kl_navigate_to_checkout
from .amazon_automator import handle_amazon_login
from .amazon_automator import select_amazon_variant, add_amazon_to_cart

# Site detection registry
SITE_HANDLERS = {
    'dillards.com': {
        'checkout_handler': handle_dillards_checkout,
        'variant_handler': select_dillards_variant
    },
    'farfetch.com': {
        'checkout_handler': handle_farfetch_checkout
    },
    'patagonia.com': {
        'variant_handler': select_patagonia_variant
    },
    'heydude.com': {
        'variant_handler': select_heydude_variant
    },
    'karllagerfeld.com': {
        'variant_handler': select_karllagerfeld_variant,
        'checkout_handler': kl_navigate_to_checkout
    },
    'amazon.com': {
        'variant_handler': select_amazon_variant,
        'login_handler': handle_amazon_login
    },
    'amazon.in': {
        'variant_handler': select_amazon_variant,
        'login_handler': handle_amazon_login
    },
    'amazon.co.uk': {
        'variant_handler': select_amazon_variant,
        'login_handler': handle_amazon_login
    },
    'amazon.de': {
        'variant_handler': select_amazon_variant,
        'login_handler': handle_amazon_login
    },
    'amazon.fr': {
        'variant_handler': select_amazon_variant,
        'login_handler': handle_amazon_login
    },
    'amazon.ca': {
        'variant_handler': select_amazon_variant,
        'login_handler': handle_amazon_login
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
            return handlers.get('checkout_handler')
    
    return None

async def get_site_specific_variant_handler(page):
    """
    Detect site and return appropriate variant handler
    Returns: handler function or None
    """
    url = page.url.lower()
    
    for domain, handlers in SITE_HANDLERS.items():
        if domain in url:
            return handlers.get('variant_handler')
    
    return None


async def get_site_specific_login_handler(page):
    """
    Detect site and return appropriate login handler
    Returns: handler function or None
    """
    url = page.url.lower()
    
    for domain, handlers in SITE_HANDLERS.items():
        if domain in url:
            return handlers.get('login_handler')
    
    return None
