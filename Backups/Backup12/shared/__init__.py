"""
Shared Utilities & Keywords
Common resources used across all phases
"""

from .ecommerce_keywords import (
    ADD_TO_CART_KEYWORDS,
    VIEW_CART_KEYWORDS,
    PRODUCT_VARIANTS
)

try:
    from .popup_dismisser import dismiss_popups
    from .process_killer import kill_chrome_processes
    __all__ = [
        'ADD_TO_CART_KEYWORDS',
        'VIEW_CART_KEYWORDS',
        'PRODUCT_VARIANTS',
        'dismiss_popups',
        'kill_chrome_processes'
    ]
except ImportError:
    # Utils not yet moved
    __all__ = [
        'ADD_TO_CART_KEYWORDS',
        'VIEW_CART_KEYWORDS',
        'PRODUCT_VARIANTS'
    ]

__version__ = '1.0.0'
