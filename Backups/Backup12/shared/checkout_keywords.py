"""
Checkout Keywords for Phase 2
Contains all keyword variations for checkout buttons and form fields
"""

# Checkout button keywords (ordered by priority - most specific first)
CHECKOUT_BUTTONS = [
    'proceed to checkout',  # Most specific - try first
    'continue to checkout',
    'secure checkout',
    'checkout',
    'check out',
    'go to checkout',
    'proceed',
    'continue',
    'proceed to cart',
    'view cart',
    'go to cart',
    'shopping cart',
    'view bag',
    'place order',
    'complete order',
    'pay now',
    'payment',
    'secure payment',
    'continue to payment',
    'go to bag',
    'view shopping bag'
]

# Guest checkout button keywords (ordered by priority)
GUEST_CHECKOUT_BUTTONS = [
    'continue as guest',
    'checkout as guest',
    'guest checkout',
    'continue without account',
    'checkout without account',
    'shop as guest',
    'guest',
    'skip registration',
    'no account needed',
    'no thanks',
    'skip'
]

# Email field labels
EMAIL_LABELS = [
    'email', 'e-mail', 'email address', 'e-mail address', 'your email',
    'emailaddress', 'mail', 'contact email', 'user email'
]

# First name field labels
FIRST_NAME_LABELS = [
    'firstname', 'first_name', 'first name', 'fname', 'given name', 'givenname',
    'billingfirstname', 'billing_first_name', 'shippingfirstname', 'shipping_first_name'
]

# Last name field labels
LAST_NAME_LABELS = [
    'lastname', 'last_name', 'last name', 'lname', 'surname', 'family name', 'familyname',
    'billinglastname', 'billing_last_name', 'shippinglastname', 'shipping_last_name'
]

# Phone field labels
PHONE_LABELS = [
    'phone', 'phone number', 'telephone', 'mobile', 'mobile number', 'contact number', 'tel',
    'phonenumber', 'phone_number', 'tel number', 'telnumber', 'cell', 'cellphone',
    'billing phone', 'shipping phone', 'contact phone'
]

# Address line 1 field labels
ADDRESS_LINE1_LABELS = [
    'address', 'street address', 'address line 1', 'address 1', 'street', 'address line1', 'address1',
    'addressline1', 'address_line_1', 'street 1', 'street1', 'billing address',
    'shipping address', 'billingaddress', 'shippingaddress', 'addr1', 'addr'
]

# Address line 2 field labels
ADDRESS_LINE2_LABELS = [
    'address line 2', 'address 2', 'apartment', 'apt', 'suite', 'unit', 'address line2', 'address2',
    'addressline2', 'address_line_2', 'street 2', 'street2', 'apt number',
    'suite number', 'building', 'floor', 'addr2'
]

# City field labels
CITY_LABELS = [
    'city', 'town', 'locality', 'suburb', 'municipality',
    'billing city', 'shipping city', 'billingcity', 'shippingcity'
]

# State/Province field labels
STATE_LABELS = [
    'state', 'province', 'region', 'county', 'state/province',
    'billing state', 'shipping state', 'billingstate', 'shippingstate',
    'billing province', 'shipping province'
]

# Postal code field labels
POSTAL_CODE_LABELS = [
    'zip', 'zip code', 'postal code', 'postcode', 'post code',
    'zipcode', 'postalcode', 'postal', 'billing zip', 'shipping zip',
    'billingzip', 'shippingzip', 'billing postal code', 'shipping postal code'
]

# Country field labels
COUNTRY_LABELS = [
    'country'
]

# Continue/Next button keywords (for multi-step forms)
CONTINUE_BUTTONS = [
    'continue', 'next', 'proceed', 'save and continue', 'continue to shipping'
]
