#!/usr/bin/env python3
"""
Site-specific configuration
Centralized place for site-specific behaviors and quirks
"""

# Sites that require double-click on Add to Cart button
DOUBLE_CLICK_SITES = [
    'karllagerfeld.com',
]

# Sites with custom variant selectors
CUSTOM_VARIANT_SITES = {
    'dillards.com': {
        'selector': '[data-attrval]',
        'attribute': 'data-attrval',
        'wait_selector': '[data-attrval]'
    },
    'heydude.com': {
        'selector': 'a[href*="variant="], input[type="radio"][name*="option"]',
        'attribute': 'data-value',
        'wait_selector': '.product-form__input'
    },
    'karllagerfeld.com': {
        'selector': 'input[type="radio"][name*="option"]',
        'attribute': 'value',
        'wait_selector': 'fieldset'
    },
    'farfetch.com': {
        'selector': 'button[data-testid*="size"], button[data-testid*="color"]',
        'attribute': 'data-testid',
        'wait_selector': 'button[data-testid]'
    },
    'amazon.com': {
        'selector': 'li[class*="swatch"], select[name="size"]',
        'attribute': 'data-dp-url',
        'wait_selector': '#variation_color_name, #variation_size_name'
    },
    'amazon.in': {
        'selector': 'li[class*="swatch"], select[name="size"]',
        'attribute': 'data-dp-url',
        'wait_selector': '#variation_color_name, #variation_size_name'
    }
}

def needs_double_click(url: str) -> bool:
    """Check if site requires double-click for add to cart"""
    url_lower = url.lower()
    return any(domain in url_lower for domain in DOUBLE_CLICK_SITES)

def get_custom_variant_config(url: str) -> dict:
    """Get custom variant selector config for site"""
    url_lower = url.lower()
    for domain, config in CUSTOM_VARIANT_SITES.items():
        if domain in url_lower:
            return config
    return None
