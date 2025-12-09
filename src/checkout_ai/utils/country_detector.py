"""
Country Detection and Configuration System

Detects country from URL and provides country-specific checkout configurations.
Designed for easy addition of new countries.
"""

from typing import Optional, Dict, Any
from urllib.parse import urlparse
import re


# Country Configuration Registry
# Add new countries here - this is the single source of truth
COUNTRY_CONFIGS = {
    'IN': {
        'name': 'India',
        'postal_code_label': 'PIN Code',
        'postal_code_pattern': r'^\d{6}$',
        'postal_code_example': '110001',
        'phone_format': '10 digits',
        'phone_example': '9876543210',
        'phone_pattern': r'^\d{10}$',
        'state_required': True,
        'state_label': 'State',
        'currency_symbol': '₹',
        'currency_code': 'INR',
        'address_format': 'address,city,state,pincode,country',
        'common_domains': ['.in', '.co.in'],
        'major_sites': ['amazon.in', 'flipkart.com', 'myntra.com', 'ajio.com', 'nykaa.com'],
    },
    'US': {
        'name': 'United States',
        'postal_code_label': 'ZIP Code',
        'postal_code_pattern': r'^\d{5}(-\d{4})?$',
        'postal_code_example': '10001 or 10001-1234',
        'phone_format': '10 digits',
        'phone_example': '555-123-4567',
        'phone_pattern': r'^\d{10}$',
        'state_required': True,
        'state_label': 'State',
        'currency_symbol': '$',
        'currency_code': 'USD',
        'address_format': 'address,city,state,zip,country',
        'common_domains': ['.com', '.us'],
        'major_sites': ['amazon.com'],
    },
    'GB': {
        'name': 'United Kingdom',
        'postal_code_label': 'Postcode',
        'postal_code_pattern': r'^[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}$',
        'postal_code_example': 'SW1A 1AA',
        'phone_format': '10-11 digits',
        'phone_example': '020 1234 5678',
        'phone_pattern': r'^\d{10,11}$',
        'state_required': False,
        'state_label': 'County (optional)',
        'currency_symbol': '£',
        'currency_code': 'GBP',
        'address_format': 'address,city,postcode,country',
        'common_domains': ['.uk', '.co.uk'],
        'major_sites': ['amazon.co.uk'],
    },
    'CA': {
        'name': 'Canada',
        'postal_code_label': 'Postal Code',
        'postal_code_pattern': r'^[A-Z]\d[A-Z]\s?\d[A-Z]\d$',
        'postal_code_example': 'K1A 0B1',
        'phone_format': '10 digits',
        'phone_example': '416-555-1234',
        'phone_pattern': r'^\d{10}$',
        'state_required': True,
        'state_label': 'Province',
        'currency_symbol': '$',
        'currency_code': 'CAD',
        'address_format': 'address,city,province,postal_code,country',
        'common_domains': ['.ca'],
        'major_sites': ['amazon.ca'],
    },
    'AU': {
        'name': 'Australia',
        'postal_code_label': 'Postcode',
        'postal_code_pattern': r'^\d{4}$',
        'postal_code_example': '2000',
        'phone_format': '10 digits',
        'phone_example': '02 1234 5678',
        'phone_pattern': r'^\d{10}$',
        'state_required': True,
        'state_label': 'State',
        'currency_symbol': '$',
        'currency_code': 'AUD',
        'address_format': 'address,city,state,postcode,country',
        'common_domains': ['.au', '.com.au'],
        'major_sites': ['amazon.com.au'],
    },
}

# Default country (when detection fails)
DEFAULT_COUNTRY = 'US'


def detect_country_from_url(url: str) -> Optional[str]:
    """
    Detect country from URL domain and TLD.
    
    Detection strategy:
    1. Check major e-commerce sites (high confidence)
    2. Check country-specific TLDs (medium confidence)
    3. Default to US for generic .com domains
    
    Args:
        url: Full URL or domain
        
    Returns:
        Country code (e.g., 'IN', 'US', 'GB') or None if cannot determine
        
    Examples:
        >>> detect_country_from_url('https://amazon.in/product')
        'IN'
        >>> detect_country_from_url('https://example.co.uk')
        'GB'
        >>> detect_country_from_url('https://flipkart.com')
        'IN'
    """
    if not url:
        return None
        
    try:
        # Parse URL to get domain
        parsed = urlparse(url.lower())
        domain = parsed.netloc or url.lower()
        
        # Remove www. prefix
        domain = domain.replace('www.', '')
        
        # Strategy 1: Check major sites first (highest confidence)
        for country_code, config in COUNTRY_CONFIGS.items():
            for major_site in config.get('major_sites', []):
                if major_site in domain:
                    return country_code
        
        # Strategy 2: Check TLDs (medium confidence)
        for country_code, config in COUNTRY_CONFIGS.items():
            for tld in config.get('common_domains', []):
                if domain.endswith(tld):
                    return country_code
        
        # Strategy 3: Default to US for .com
        if domain.endswith('.com'):
            return 'US'
            
        return None
        
    except Exception as e:
        print(f"Error detecting country from URL '{url}': {e}")
        return None


def get_country_config(country_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Get country-specific configuration.
    
    Args:
        country_code: ISO country code (e.g., 'IN', 'US', 'GB')
                     If None, returns default country config
                     
    Returns:
        Dict with country-specific settings including:
        - postal_code_label: Display name for postal code field
        - postal_code_pattern: Regex for validation
        - phone_format: Description of phone format
        - state_required: Whether state field is mandatory
        - currency_symbol: Currency symbol (₹, $, £)
        - And more...
        
    Examples:
        >>> config = get_country_config('IN')
        >>> config['postal_code_label']
        'PIN Code'
        >>> config['currency_symbol']
        '₹'
    """
    if not country_code or country_code not in COUNTRY_CONFIGS:
        country_code = DEFAULT_COUNTRY
        
    return COUNTRY_CONFIGS[country_code].copy()


def get_all_countries() -> Dict[str, Dict[str, Any]]:
    """
    Get all available country configurations.
    
    Useful for generating dropdowns or documentation.
    
    Returns:
        Dict mapping country codes to their full configurations
    """
    return COUNTRY_CONFIGS.copy()


def validate_postal_code(postal_code: str, country_code: str) -> bool:
    """
    Validate postal code format for a specific country.
    
    Args:
        postal_code: The postal code to validate
        country_code: Country code (e.g., 'IN', 'US')
        
    Returns:
        True if valid, False otherwise
        
    Examples:
        >>> validate_postal_code('110001', 'IN')
        True
        >>> validate_postal_code('12345', 'US')
        True
        >>> validate_postal_code('ABC', 'IN')
        False
    """
    config = get_country_config(country_code)
    pattern = config.get('postal_code_pattern')
    
    if not pattern:
        return True  # No pattern defined, consider valid
        
    return bool(re.match(pattern, postal_code.strip(), re.IGNORECASE))


def validate_phone(phone: str, country_code: str) -> bool:
    """
    Validate phone number format for a specific country.
    
    Args:
        phone: The phone number to validate
        country_code: Country code (e.g., 'IN', 'US')
        
    Returns:
        True if valid, False otherwise
    """
    config = get_country_config(country_code)
    pattern = config.get('phone_pattern')
    
    if not pattern:
        return True
        
    # Remove common separators before validation
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    return bool(re.match(pattern, clean_phone))


def format_address_for_country(address_data: Dict[str, str], country_code: str) -> str:
    """
    Format address according to country conventions.
    
    Args:
        address_data: Dict with address components
        country_code: Country code
        
    Returns:
        Formatted address string
    """
    config = get_country_config(country_code)
    format_order = config.get('address_format', 'address,city,state,postal_code,country').split(',')
    
    field_map = {
        'address': address_data.get('addressLine1', ''),
        'city': address_data.get('city', ''),
        'state': address_data.get('province', address_data.get('state', '')),
        'postal_code': address_data.get('postalCode', address_data.get('zip', '')),
        'pincode': address_data.get('postalCode', ''),
        'zip': address_data.get('postalCode', ''),
        'postcode': address_data.get('postalCode', ''),
        'country': config['name'],
    }
    
    parts = [field_map.get(field, '').strip() for field in format_order]
    return ', '.join(part for part in parts if part)


# Convenience functions
def is_india(country_code: Optional[str]) -> bool:
    """Check if country is India"""
    return country_code == 'IN'


def is_us(country_code: Optional[str]) -> bool:
    """Check if country is United States"""
    return country_code == 'US'


def is_uk(country_code: Optional[str]) -> bool:
    """Check if country is United Kingdom"""
    return country_code == 'GB'


# Documentation for adding new countries
"""
HOW TO ADD A NEW COUNTRY
========================

1. Add entry to COUNTRY_CONFIGS dictionary above
2. Use existing countries as template
3. Required fields:
   - name: Full country name
   - postal_code_label: What locals call it
   - postal_code_pattern: Regex for validation
   - phone_format: Description
   - state_required: Boolean
   - currency_symbol: e.g., '€'
   - common_domains: List of TLDs
   - major_sites: List of major e-commerce domains

Example for Germany:
--------------------
'DE': {
    'name': 'Germany',
    'postal_code_label': 'Postleitzahl',
    'postal_code_pattern': r'^\d{5}$',
    'postal_code_example': '10115',
    'phone_format': '10-11 digits',
    'phone_example': '030 12345678',
    'phone_pattern': r'^\d{10,11}$',
    'state_required': False,
    'state_label': 'State (optional)',
    'currency_symbol': '€',
    'currency_code': 'EUR',
    'address_format': 'address,postal_code,city,country',
    'common_domains': ['.de'],
    'major_sites': ['amazon.de'],
},

That's it! The system will automatically use this config.
"""
