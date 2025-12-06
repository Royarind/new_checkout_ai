"""
Phase 1: Product Selection & Add to Cart
Complete implementation of product variant selection, verification, and cart addition
"""

from src.checkout_ai.dom.service import UniversalDOMFinder as find_variant_dom
from src.checkout_ai.legacy.phase1.add_to_cart_robust import add_to_cart_robust
from src.checkout_ai.legacy.phase1.cart_navigator import navigate_to_cart

__all__ = [
    'find_variant_dom',
    'add_to_cart_robust',
    'navigate_to_cart'
]

__version__ = '1.0.0'
__phase__ = 'Phase 1: Product Selection & Cart'
