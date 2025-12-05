"""
Phase 1: Product Selection & Add to Cart
Complete implementation of product variant selection, verification, and cart addition
"""

from .universal_dom_finder import find_variant_dom
from .add_to_cart_robust import add_to_cart_robust
from .cart_navigator import navigate_to_cart

__all__ = [
    'find_variant_dom',
    'add_to_cart_robust',
    'navigate_to_cart'
]

__version__ = '1.0.0'
__phase__ = 'Phase 1: Product Selection & Cart'
