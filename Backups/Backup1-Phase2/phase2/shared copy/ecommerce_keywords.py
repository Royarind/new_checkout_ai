#!/usr/bin/env python3
"""
Comprehensive E-commerce Keyword Library
Centralized keyword definitions for all e-commerce automation stages
"""

from typing import Dict, List
from dataclasses import dataclass

@dataclass
class KeywordSet:
    """Container for keyword variations"""
    primary: List[str]  # Primary keywords to try first
    secondary: List[str]  # Fallback keywords
    patterns: List[str]  # Regex patterns for flexible matching
    
    def all_keywords(self) -> List[str]:
        """Get all keywords combined"""
        return self.primary + self.secondary


# ============================================
# PRODUCT SELECTION STAGE
# ============================================

PRODUCT_VARIANTS = {
    'color': KeywordSet(
        primary=['color', 'colour', 'shade'],
        secondary=['hue', 'tone', 'tint'],
        patterns=[r'color.*', r'colour.*', r'shade.*']
    ),
    'size': KeywordSet(
        primary=['size', 'sizes'],
        secondary=['fit size', 'clothing size', 'shoe size'],
        patterns=[r'size.*', r'sz.*']
    ),
    'fit': KeywordSet(
        primary=['fit', 'style'],
        secondary=['fit type', 'cut', 'style fit'],
        patterns=[r'fit.*', r'style.*']
    ),
    'length': KeywordSet(
        primary=['length', 'inseam'],
        secondary=['leg length', 'pant length', 'inseam length'],
        patterns=[r'length.*', r'inseam.*']
    ),
    'width': KeywordSet(
        primary=['width', 'wide'],
        secondary=['shoe width', 'feet width'],
        patterns=[r'width.*', r'wide.*']
    ),
    'material': KeywordSet(
        primary=['material', 'fabric'],
        secondary=['fabric type', 'material type'],
        patterns=[r'material.*', r'fabric.*']
    ),
    'quantity': KeywordSet(
        primary=['quantity', 'qty', 'amount'],
        secondary=['number', 'count', 'pieces'],
        patterns=[r'quantity.*', r'qty.*', r'amount.*']
    )
}


# ============================================
# CART STAGE
# ============================================

ADD_TO_CART_KEYWORDS = KeywordSet(
    primary=[
        'add to cart',
        'add to bag',
        'add to basket',
        'add for ship',      # Ulta-specific
        'buy now',
        'purchase',
        'add',
    ],
    secondary=[
        'add item',
        'add product',
        'add for pickup',    # Store pickup option
        'add for delivery',  # Delivery option
        'shop now',
        'order now',
        'get it now',
        'buy',
        'añadir a la bolsa',  # Spanish
        'ajouter au panier',  # French
        'in den warenkorb',   # German
    ],
    patterns=[
        r'add.*cart',
        r'add.*bag',
        r'add.*basket',
        r'add.*ship',        # Matches "add for ship", "add to ship"
        r'add.*pickup',      # Matches pickup variations
        r'add.*delivery',    # Matches delivery variations
        r'buy.*now',
        r'purchase.*'
    ]
)

VIEW_CART_KEYWORDS = KeywordSet(
    primary=[
        'view cart',
        'view bag',
        'shopping cart',
        'shopping bag',
        'cart',
        'bag',
        'basket'
    ],
    secondary=[
        'my cart',
        'my bag',
        'show cart',
        'go to cart',
        'checkout cart',
        'ver bolsa',  # Spanish
    ],
    patterns=[
        r'view.*cart',
        r'view.*bag',
        r'.*cart.*',
        r'.*bag.*'
    ]
)

CART_ITEM_QUANTITY = KeywordSet(
    primary=[
        'quantity',
        'qty',
        'update quantity',
        'change quantity'
    ],
    secondary=[
        'item quantity',
        'product quantity',
        'amount'
    ],
    patterns=[
        r'quantity.*',
        r'qty.*'
    ]
)

REMOVE_FROM_CART = KeywordSet(
    primary=[
        'remove',
        'delete',
        'remove item',
        'delete item'
    ],
    secondary=[
        'remove from cart',
        'remove from bag',
        'delete from cart'
    ],
    patterns=[
        r'remove.*',
        r'delete.*'
    ]
)

PROMO_CODE = KeywordSet(
    primary=[
        'promo code',
        'promotional code',
        'coupon code',
        'discount code',
        'voucher code'
    ],
    secondary=[
        'promo',
        'coupon',
        'discount',
        'voucher',
        'code'
    ],
    patterns=[
        r'promo.*code',
        r'coupon.*',
        r'discount.*',
        r'voucher.*'
    ]
)

APPLY_PROMO = KeywordSet(
    primary=[
        'apply',
        'apply code',
        'apply promo',
        'apply coupon',
        'redeem'
    ],
    secondary=[
        'use code',
        'submit',
        'add promo'
    ],
    patterns=[
        r'apply.*',
        r'redeem.*'
    ]
)


# ============================================
# CHECKOUT STAGE
# ============================================

CHECKOUT_KEYWORDS = KeywordSet(
    primary=[
        'checkout',
        'proceed to checkout',
        'continue to checkout',
        'secure checkout',
        'check out'
    ],
    secondary=[
        'go to checkout',
        'start checkout',
        'begin checkout',
        'place order'
    ],
    patterns=[
        r'.*checkout.*',
        r'proceed.*',
        r'continue.*'
    ]
)

GUEST_CHECKOUT = KeywordSet(
    primary=[
        'guest checkout',
        'checkout as guest',
        'continue as guest',
        'guest'
    ],
    secondary=[
        'skip registration',
        'no account',
        'without account'
    ],
    patterns=[
        r'guest.*',
        r'.*as guest',
        r'continue.*guest'
    ]
)

LOGIN_CHECKOUT = KeywordSet(
    primary=[
        'login',
        'sign in',
        'log in',
        'sign in to checkout'
    ],
    secondary=[
        'member login',
        'customer login',
        'account login',
        'returning customer'
    ],
    patterns=[
        r'log.*in',
        r'sign.*in'
    ]
)

CONTINUE_BUTTON = KeywordSet(
    primary=[
        'continue',
        'next',
        'proceed',
        'save and continue'
    ],
    secondary=[
        'continue to payment',
        'continue to shipping',
        'move to next',
        'go to next'
    ],
    patterns=[
        r'continue.*',
        r'next.*',
        r'proceed.*'
    ]
)


# ============================================
# SHIPPING/ADDRESS STAGE
# ============================================

ADDRESS_FIELDS = {
    'email': KeywordSet(
        primary=['email', 'email address', 'e-mail'],
        secondary=['mail', 'email id', 'contact email'],
        patterns=[r'e.*mail.*', r'.*email.*']
    ),
    'first_name': KeywordSet(
        primary=['first name', 'firstname', 'given name'],
        secondary=['name', 'forename', 'first'],
        patterns=[r'first.*name', r'given.*name']
    ),
    'last_name': KeywordSet(
        primary=['last name', 'lastname', 'surname', 'family name'],
        secondary=['name', 'surname', 'last'],
        patterns=[r'last.*name', r'sur.*name', r'family.*name']
    ),
    'phone': KeywordSet(
        primary=['phone', 'phone number', 'mobile', 'mobile number', 'telephone'],
        secondary=['cell', 'contact number', 'tel', 'cell phone'],
        patterns=[r'phone.*', r'mobile.*', r'tel.*']
    ),
    'address_line1': KeywordSet(
        primary=['address', 'street address', 'address line 1', 'address1'],
        secondary=['street', 'address line', 'line 1', 'addr1'],
        patterns=[r'address.*1', r'street.*', r'address.*line.*1']
    ),
    'address_line2': KeywordSet(
        primary=['address line 2', 'address2', 'apartment', 'apt', 'suite', 'unit'],
        secondary=['line 2', 'addr2', 'apartment number', 'suite number'],
        patterns=[r'address.*2', r'line.*2', r'apt.*', r'suite.*', r'unit.*']
    ),
    'city': KeywordSet(
        primary=['city', 'town'],
        secondary=['municipality', 'locality'],
        patterns=[r'city.*', r'town.*']
    ),
    'state': KeywordSet(
        primary=['state', 'province', 'region'],
        secondary=['state/province', 'county'],
        patterns=[r'state.*', r'province.*', r'region.*']
    ),
    'zip_code': KeywordSet(
        primary=['zip', 'zip code', 'postal code', 'postcode'],
        secondary=['pin', 'pin code', 'postal'],
        patterns=[r'zip.*', r'postal.*', r'post.*code']
    ),
    'country': KeywordSet(
        primary=['country', 'country/region'],
        secondary=['nation', 'country code'],
        patterns=[r'country.*']
    ),
    'company': KeywordSet(
        primary=['company', 'company name', 'organization'],
        secondary=['business', 'firm', 'org'],
        patterns=[r'company.*', r'org.*']
    )
}

SHIPPING_METHOD = KeywordSet(
    primary=[
        'shipping method',
        'delivery method',
        'shipping option',
        'delivery option'
    ],
    secondary=[
        'shipping',
        'delivery',
        'shipping speed',
        'delivery speed'
    ],
    patterns=[
        r'shipping.*method',
        r'delivery.*method'
    ]
)

SAME_AS_BILLING = KeywordSet(
    primary=[
        'same as shipping',
        'same as delivery',
        'billing same as shipping',
        'use shipping address'
    ],
    secondary=[
        'same address',
        'copy address',
        'same as above'
    ],
    patterns=[
        r'same.*shipping',
        r'same.*delivery',
        r'same.*address'
    ]
)


# ============================================
# PAYMENT STAGE
# ============================================

PAYMENT_METHOD = KeywordSet(
    primary=[
        'payment method',
        'payment option',
        'pay with',
        'payment type'
    ],
    secondary=[
        'payment',
        'pay',
        'billing method'
    ],
    patterns=[
        r'payment.*method',
        r'pay.*with'
    ]
)

CREDIT_CARD_FIELDS = {
    'card_number': KeywordSet(
        primary=['card number', 'credit card number', 'debit card number'],
        secondary=['card', 'cc number', 'card no'],
        patterns=[r'card.*number', r'cc.*number']
    ),
    'card_name': KeywordSet(
        primary=['name on card', 'cardholder name', 'card holder name'],
        secondary=['card name', 'name', 'cardholder'],
        patterns=[r'name.*card', r'card.*name', r'holder.*name']
    ),
    'expiry_date': KeywordSet(
        primary=['expiry date', 'expiration date', 'exp date', 'valid thru'],
        secondary=['expiry', 'expiration', 'exp', 'valid until'],
        patterns=[r'exp.*date', r'expir.*', r'valid.*']
    ),
    'cvv': KeywordSet(
        primary=['cvv', 'cvc', 'security code', 'card security code'],
        secondary=['cvv2', 'card code', 'verification code'],
        patterns=[r'cvv.*', r'cvc.*', r'security.*code']
    )
}

PAYPAL_KEYWORDS = KeywordSet(
    primary=['paypal', 'pay with paypal', 'paypal checkout'],
    secondary=['pp', 'paypal button'],
    patterns=[r'paypal.*', r'pay.*pal']
)

APPLE_PAY = KeywordSet(
    primary=['apple pay', 'applepay'],
    secondary=['pay with apple', 'apple payment'],
    patterns=[r'apple.*pay']
)

GOOGLE_PAY = KeywordSet(
    primary=['google pay', 'googlepay', 'gpay'],
    secondary=['pay with google'],
    patterns=[r'google.*pay', r'gpay']
)

BILLING_ADDRESS_SAME = KeywordSet(
    primary=[
        'billing address same as shipping',
        'same as shipping address',
        'use shipping address for billing'
    ],
    secondary=[
        'same address',
        'same as shipping',
        'copy shipping address'
    ],
    patterns=[
        r'same.*shipping',
        r'billing.*same.*'
    ]
)


# ============================================
# ORDER REVIEW & PLACEMENT STAGE
# ============================================

PLACE_ORDER = KeywordSet(
    primary=[
        'place order',
        'complete order',
        'confirm order',
        'submit order',
        'finalize order'
    ],
    secondary=[
        'order now',
        'complete purchase',
        'confirm purchase',
        'buy now',
        'complete checkout'
    ],
    patterns=[
        r'place.*order',
        r'complete.*order',
        r'confirm.*order',
        r'submit.*order'
    ]
)

REVIEW_ORDER = KeywordSet(
    primary=[
        'review order',
        'review and submit',
        'order summary',
        'order review'
    ],
    secondary=[
        'review',
        'summary',
        'order details'
    ],
    patterns=[
        r'review.*order',
        r'order.*review'
    ]
)

TERMS_AND_CONDITIONS = KeywordSet(
    primary=[
        'terms and conditions',
        'terms of service',
        'terms & conditions',
        'accept terms'
    ],
    secondary=[
        'terms',
        'conditions',
        'agree to terms',
        'i agree'
    ],
    patterns=[
        r'terms.*',
        r'conditions.*',
        r'.*agree.*'
    ]
)

NEWSLETTER_SIGNUP = KeywordSet(
    primary=[
        'newsletter',
        'sign up for newsletter',
        'email updates',
        'promotional emails'
    ],
    secondary=[
        'subscribe',
        'updates',
        'news',
        'promotions'
    ],
    patterns=[
        r'newsletter.*',
        r'sign.*up',
        r'subscribe.*'
    ]
)


# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_keywords(category: str, subcategory: str = None) -> List[str]:
    """
    Get keywords for a specific category or subcategory
    
    Args:
        category: Main category (e.g., 'cart', 'checkout', 'payment')
        subcategory: Optional subcategory (e.g., 'address_line1', 'card_number')
    
    Returns:
        List of all keywords for the specified category/subcategory
    """
    category_map = {
        'product_variants': PRODUCT_VARIANTS,
        'address': ADDRESS_FIELDS,
        'card': CREDIT_CARD_FIELDS
    }
    
    if category in category_map and subcategory:
        keyword_set = category_map[category].get(subcategory)
        if keyword_set:
            return keyword_set.all_keywords()
    
    # Direct keyword sets
    keyword_sets = {
        'add_to_cart': ADD_TO_CART_KEYWORDS,
        'view_cart': VIEW_CART_KEYWORDS,
        'checkout': CHECKOUT_KEYWORDS,
        'guest_checkout': GUEST_CHECKOUT,
        'login_checkout': LOGIN_CHECKOUT,
        'continue': CONTINUE_BUTTON,
        'shipping_method': SHIPPING_METHOD,
        'payment_method': PAYMENT_METHOD,
        'place_order': PLACE_ORDER,
        'promo_code': PROMO_CODE,
        'apply_promo': APPLY_PROMO,
        'remove_from_cart': REMOVE_FROM_CART,
        'terms': TERMS_AND_CONDITIONS,
        'newsletter': NEWSLETTER_SIGNUP,
        'paypal': PAYPAL_KEYWORDS,
        'apple_pay': APPLE_PAY,
        'google_pay': GOOGLE_PAY
    }
    
    keyword_set = keyword_sets.get(category)
    if keyword_set:
        return keyword_set.all_keywords()
    
    return []


def get_primary_keywords(category: str, subcategory: str = None) -> List[str]:
    """Get only primary keywords for faster matching"""
    category_map = {
        'product_variants': PRODUCT_VARIANTS,
        'address': ADDRESS_FIELDS,
        'card': CREDIT_CARD_FIELDS
    }
    
    if category in category_map and subcategory:
        keyword_set = category_map[category].get(subcategory)
        if keyword_set:
            return keyword_set.primary
    
    # Direct keyword sets
    keyword_sets = {
        'add_to_cart': ADD_TO_CART_KEYWORDS,
        'view_cart': VIEW_CART_KEYWORDS,
        'checkout': CHECKOUT_KEYWORDS,
        'guest_checkout': GUEST_CHECKOUT,
        'login_checkout': LOGIN_CHECKOUT,
        'continue': CONTINUE_BUTTON,
        'shipping_method': SHIPPING_METHOD,
        'payment_method': PAYMENT_METHOD,
        'place_order': PLACE_ORDER,
        'promo_code': PROMO_CODE,
        'apply_promo': APPLY_PROMO
    }
    
    keyword_set = keyword_sets.get(category)
    if keyword_set:
        return keyword_set.primary
    
    return []


def get_all_stage_keywords() -> Dict[str, List[str]]:
    """
    Get all keywords organized by stage for comprehensive matching
    
    Returns:
        Dictionary with stage names as keys and keyword lists as values
    """
    return {
        # Product Selection Stage
        'product_color': get_keywords('product_variants', 'color'),
        'product_size': get_keywords('product_variants', 'size'),
        'product_fit': get_keywords('product_variants', 'fit'),
        'product_quantity': get_keywords('product_variants', 'quantity'),
        
        # Cart Stage
        'add_to_cart': get_keywords('add_to_cart'),
        'view_cart': get_keywords('view_cart'),
        'promo_code': get_keywords('promo_code'),
        'apply_promo': get_keywords('apply_promo'),
        'remove_item': get_keywords('remove_from_cart'),
        
        # Checkout Stage
        'checkout': get_keywords('checkout'),
        'guest_checkout': get_keywords('guest_checkout'),
        'login': get_keywords('login_checkout'),
        'continue': get_keywords('continue'),
        
        # Address Stage
        'email': get_keywords('address', 'email'),
        'first_name': get_keywords('address', 'first_name'),
        'last_name': get_keywords('address', 'last_name'),
        'phone': get_keywords('address', 'phone'),
        'address_line1': get_keywords('address', 'address_line1'),
        'address_line2': get_keywords('address', 'address_line2'),
        'city': get_keywords('address', 'city'),
        'state': get_keywords('address', 'state'),
        'zip': get_keywords('address', 'zip_code'),
        'country': get_keywords('address', 'country'),
        
        # Payment Stage
        'payment_method': get_keywords('payment_method'),
        'card_number': get_keywords('card', 'card_number'),
        'card_name': get_keywords('card', 'card_name'),
        'expiry': get_keywords('card', 'expiry_date'),
        'cvv': get_keywords('card', 'cvv'),
        'paypal': get_keywords('paypal'),
        'apple_pay': get_keywords('apple_pay'),
        'google_pay': get_keywords('google_pay'),
        
        # Order Placement Stage
        'place_order': get_keywords('place_order'),
        'terms': get_keywords('terms'),
        'newsletter': get_keywords('newsletter')
    }


# ============================================
# STAGE DEFINITIONS
# ============================================

class EcommerceStage:
    """Enumeration of e-commerce automation stages"""
    PRODUCT_SELECTION = "product_selection"
    ADD_TO_CART = "add_to_cart"
    VIEW_CART = "view_cart"
    CART_MANAGEMENT = "cart_management"
    CHECKOUT_START = "checkout_start"
    GUEST_OR_LOGIN = "guest_or_login"
    SHIPPING_ADDRESS = "shipping_address"
    SHIPPING_METHOD = "shipping_method"
    PAYMENT_METHOD = "payment_method"
    PAYMENT_DETAILS = "payment_details"
    BILLING_ADDRESS = "billing_address"
    ORDER_REVIEW = "order_review"
    ORDER_PLACEMENT = "order_placement"
    ORDER_CONFIRMATION = "order_confirmation"


if __name__ == "__main__":
    # Test the keyword library
    print("=== E-commerce Keyword Library Test ===\n")
    
    print("Add to Cart Keywords:")
    print(get_keywords('add_to_cart'))
    print("\n")
    
    print("Email Address Keywords:")
    print(get_keywords('address', 'email'))
    print("\n")
    
    print("Place Order Keywords:")
    print(get_keywords('place_order'))
    print("\n")
    
    print("All Stage Keywords (sample):")
    all_keywords = get_all_stage_keywords()
    for stage, keywords in list(all_keywords.items())[:5]:
        print(f"{stage}: {keywords[:3]}...")