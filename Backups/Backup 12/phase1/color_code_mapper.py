"""
Color code to name mapper for Patagonia and similar sites
"""

# Common color code mappings
COLOR_CODE_MAP = {
    'PNDG': 'Pond Green',
    'CLMB': 'Clement Blue',
    'OLGG': 'Olive Green',
    'CASG': 'Castle Gray',
    # Add more as needed
}

def normalize_color_code(code):
    """Normalize color code to full name if mapping exists"""
    if not code:
        return code
    
    code_upper = code.upper().strip()
    return COLOR_CODE_MAP.get(code_upper, code)

def matches_color(expected_color, actual_value):
    """Check if actual value matches expected color (handles codes and names)"""
    if not expected_color or not actual_value:
        return False
    
    # Normalize both values
    expected_norm = expected_color.lower().strip().replace(' ', '')
    actual_norm = actual_value.lower().strip().replace(' ', '')
    
    # Direct match
    if expected_norm == actual_norm:
        return True
    
    # Check if actual is a code that maps to expected
    mapped_name = normalize_color_code(actual_value)
    if mapped_name.lower().strip().replace(' ', '') == expected_norm:
        return True
    
    # Check if expected is a code that maps to actual
    mapped_expected = normalize_color_code(expected_color)
    if mapped_expected.lower().strip().replace(' ', '') == actual_norm:
        return True
    
    return False
