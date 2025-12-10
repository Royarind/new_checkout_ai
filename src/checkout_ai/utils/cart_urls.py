"""
Cart & Checkout URL Patterns for Fallback Navigation
Comprehensive URL patterns for all major e-commerce platforms
"""

# ========================================
# CART PAGE URLS
# ========================================

CART_URL_PATTERNS = [
    # Standard patterns
    '/cart',
    '/cart/',
    '/cart.html',
    '/cart.php',
    '/basket',
    '/basket/',
    '/view-cart',
    '/viewcart',
    '/shopping-cart',
    '/shopping_cart',
    '/order/cart',
    '/checkout/cart',
    '/cart/index',
    '/bag',
    '/bag/',
    '/shopping-bag',
    '/shoppingbag',
    
    # Shopify
    '/cart',
    
    # WooCommerce
    '/cart',
    
    # Magento
    '/checkout/cart',
    
    # Indian sites specific
    '/viewcart',
    '/shoppingbag',
    '/mybag'
]

# ========================================
# CHECKOUT START URLS
# ========================================

CHECKOUT_START_URL_PATTERNS = [
    '/checkout',
    '/checkout/',
    '/checkout/index',
    '/checkout/start',
    '/checkout/begin',
    '/checkout?step=1',
    '/cart/checkout',
    '/cart?checkout',
    '/checkout/login',
    '/checkout-guest',
    '/guest-checkout',
    '/en/checkout',
    '/checkout/start-checkout',
    '/checkoutStep1',
    '/onestepcheckout',
    '/one-step-checkout',
    
    # Shopify
    '/checkouts/',
    
    # Indian sites
    '/checkout/login',
    '/secure/checkout'
]

# ========================================
# GUEST CHECKOUT URLS
# ========================================

GUEST_CHECKOUT_URL_PATTERNS = [
    '/checkout/guest',
    '/checkout?guest=true',
    '/guest-checkout',
    '/guest/checkout',
    '/checkout?as_guest=1'
]

# ========================================
# LOGIN DURING CHECKOUT URLS
# ========================================

LOGIN_CHECKOUT_URL_PATTERNS = [
    '/account/login?checkout=1',
    '/login?return_to=checkout',
    '/signin?redirect=checkout',
    '/customer/login?checkout',
    '/customer/account/login',
    '/account/login/checkout',
    '/checkout/login',
    '/login/checkout'
]

# ========================================
# ADDRESS (SHIPPING) URLS
# ========================================

ADDRESS_URL_PATTERNS = [
    '/checkout/address',
    '/checkout/shipping-address',
    '/checkout?step=address',
    '/checkout/contact',
    '/checkout/information',
    '/checkout/customer-information',
    '/checkout/shipping',
    '/checkout?step=shipping',
    '/shipping-address',
    '/delivery-address'
]

# ========================================
# SHIPPING METHOD URLS
# ========================================

SHIPPING_METHOD_URL_PATTERNS = [
    '/checkout/shipping',
    '/checkout?step=shipping_method',
    '/checkout/delivery',
    '/shipping-method',
    '/checkout/shipping-options',
    '/delivery-options'
]

# ========================================
# PAYMENT URLS
# ========================================

PAYMENT_URL_PATTERNS = [
    '/checkout/payment',
    '/checkout/payment-method',
    '/checkout?step=payment',
    '/checkout/payment_information',
    '/cart/payment',
    '/payment',
    '/checkout/billing',
    '/billing',
    '/billing-address',
    '/checkout/payment-options',
    '/secure/payment'
]

# ========================================
# REVIEW/CONFIRMATION URLS
# ========================================

REVIEW_URL_PATTERNS = [
    '/checkout/review',
    '/checkout/order-review',
    '/checkout?step=review',
    '/order/confirm',
    '/order/review',
    '/review-order',
    '/order-summary'
]

# ========================================
# ORDER COMPLETE/THANK YOU URLS
# ========================================

ORDER_COMPLETE_URL_PATTERNS = [
    '/checkout/thank_you',
    '/thankyou',
    '/thank-you',
    '/order-complete',
    '/order/complete',
    '/order-confirmation',
    '/confirmation',
    '/success',
    '/checkout/success',
    '/order/success',
    '/order-received',
    
    # Shopify
    '/checkouts/',  # Shopify checkout IDs
    '/thank_you',
    
    # WooCommerce
    '/checkout/order-received',
    
    # Magento
    '/checkout/onepage/success'
]

# ========================================
# COMBINED PATTERNS BY STAGE
# ========================================

CHECKOUT_STAGE_PATTERNS = {
    'cart': CART_URL_PATTERNS,
    'checkout_start': CHECKOUT_START_URL_PATTERNS,
    'guest_checkout': GUEST_CHECKOUT_URL_PATTERNS,
    'login': LOGIN_CHECKOUT_URL_PATTERNS,
    'address': ADDRESS_URL_PATTERNS,
    'shipping': SHIPPING_METHOD_URL_PATTERNS,
    'payment': PAYMENT_URL_PATTERNS,
    'review': REVIEW_URL_PATTERNS,
    'complete': ORDER_COMPLETE_URL_PATTERNS
}

# ========================================
# UTILITY FUNCTIONS
# ========================================

def get_cart_url_from_domain(domain: str) -> str:
    """
    Get most likely cart URL for a domain
    
    Args:
        domain: Domain name (e.g., 'myntra.com')
        
    Returns:
        Cart URL path
    """
    # Site-specific cart URLs
    site_specific = {
        'myntra.com': '/checkout/cart',
        'ajio.com': '/bag',
        'flipkart.com': '/viewcart',
        'amazon.in': '/cart',
        'amazon.com': '/cart',
        'nykaa.com': '/cart',
        'bigbasket.com': '/basket',
    }
    
    for site, cart_url in site_specific.items():
        if site in domain.lower():
            return cart_url
    
    # Default fallback
    return '/cart'


def detect_checkout_stage_from_url(url: str) -> str:
    """
    Detect checkout stage from current URL
    
    Args:
        url: Current page URL
        
    Returns:
        Stage name: 'cart', 'checkout_start', 'address', 'payment', 'review', 'complete', or 'unknown'
    """
    url_lower = url.lower()
    
    # Check each stage in order of specificity
    for stage, patterns in CHECKOUT_STAGE_PATTERNS.items():
        for pattern in patterns:
            if pattern in url_lower:
                return stage
    
    return 'unknown'


def is_cart_url(url: str) -> bool:
    """Check if URL is a cart page"""
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in CART_URL_PATTERNS)


def is_checkout_url(url: str) -> bool:
    """Check if URL is any checkout page"""
    url_lower = url.lower()
    all_checkout_patterns = (
        CHECKOUT_START_URL_PATTERNS +
        ADDRESS_URL_PATTERNS +
        SHIPPING_METHOD_URL_PATTERNS +
        PAYMENT_URL_PATTERNS +
        REVIEW_URL_PATTERNS
    )
    return any(pattern in url_lower for pattern in all_checkout_patterns)


def is_order_complete_url(url: str) -> bool:
    """Check if URL is order complete/thank you page"""
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in ORDER_COMPLETE_URL_PATTERNS)
