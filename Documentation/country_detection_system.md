# Country Detection System - Documentation

## 🎯 Overview

Production-ready country detection system that automatically identifies the target country from URLs and provides country-specific checkout configurations. **Designed for easy addition of new countries.**

---

## ✨ Features

✅ **Automatic Detection**: Detects country from URL domain/TLD  
✅ **5 Countries Supported**: India, US, UK, Canada, Australia  
✅ **Extensible**: Add new countries in ~10 lines of config  
✅ **Production-Ready**: Tested, validated, integrated  
✅ **Comprehensive Configs**: Postal codes, phone formats, currency, etc.

---

## 📁 Files

### Core Module
```
src/checkout_ai/utils/country_detector.py
```
- Main detection logic
- Country configuration registry
- Validation functions

### Integration Points
```
src/checkout_ai/agents/orchestrator.py  (lines 11-14, 24-25, 53-98)
```
- Auto-detects country from task URL
- Enriches planner context with country info

---

## 🚀 How It Works

### 1. **Detection Strategy**

```python
from src.checkout_ai.utils.country_detector import detect_country_from_url

url = "https://amazon.in/product/123"
country = detect_country_from_url(url)  # Returns: 'IN'
```

**Detection logic (in order)**:
1. **Major sites** (high confidence): `amazon.in` → `'IN'`
2. **TLD matching** (medium confidence): `.co.uk` → `'GB'`
3. **Default fallback**: `.com` → `'US'`

### 2. **Get Country Config**

```python
from src.checkout_ai.utils.country_detector import get_country_config

config = get_country_config('IN')

# Returns:
{
    'name': 'India',
    'postal_code_label': 'PIN Code',
    'postal_code_example': '110001',
    'phone_example': '9876543210',
    'currency_symbol': '₹',
    'currency_code': 'INR',
    # ... and more
}
```

### 3. **Automatic Integration**

When you run a checkout task, the orchestrator:

1. Extracts URL from task data
2. Detects country → `'IN'`
3. Gets config for India
4. Enriches planner prompt:
   ```
   [COUNTRY CONTEXT]
   Country: India (IN)
   Postal Code Label: PIN Code (example: 110001)
   Phone Format: 10 digits (example: 9876543210)
   State Required: Yes
   Currency: ₹ (INR)
   ```
5. Planner generates country-aware steps!

---

## 🌍 Supported Countries

| Code | Country        | Postal Label | Example      | Currency |
|------|----------------|--------------|--------------|----------|
| IN   | India          | PIN Code     | 110001       | ₹ (INR)  |
| US   | United States  | ZIP Code     | 10001        | $ (USD)  |
| GB   | United Kingdom | Postcode     | SW1A 1AA     | £ (GBP)  |
| CA   | Canada         | Postal Code  | K1A 0B1      | $ (CAD)  |
| AU   | Australia      | Postcode     | 2000         | $ (AUD)  |

**Default**: If detection fails → defaults to `US`

---

## ➕ How to Add a New Country

**Example: Adding Germany**

### Step 1: Add to `COUNTRY_CONFIGS`

Open `src/checkout_ai/utils/country_detector.py` and add:

```python
COUNTRY_CONFIGS = {
    # ... existing countries ...
    
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
        'major_sites': ['amazon.de', 'zalando.de'],
    },
}
```

### Step 2: Done!

That's it! The system automatically:
- ✅ Detects `amazon.de` → `'DE'`
- ✅ Returns German postal code format
- ✅ Validates 5-digit postcodes
- ✅ Shows `€` currency symbol

**No code changes needed anywhere else!**

---

## 🧪 Testing

### Test File Provided

```bash
python test_country_detection.py
```

**Output**:
```
============================================================
COUNTRY DETECTION TEST
============================================================
✓ https://amazon.in/product            -> IN (expected: IN)
✓ https://amazon.co.uk/item            -> GB (expected: GB)
✓ https://amazon.com/item              -> US (expected: US)
✓ https://flipkart.com/product         -> IN (expected: IN)
...

============================================================
COUNTRY CONFIG TEST
============================================================

IN: India
  Postal: PIN Code (110001)
  Currency: ₹ INR
  Phone: 9876543210

US: United States
  Postal: ZIP Code (10001 or 10001-1234)
  Currency: $ USD
  Phone: 555-123-4567
...
```

### Manual Testing

```python
from src.checkout_ai.utils.country_detector import *

# Test detection
detect_country_from_url('https://myntra.com')  # 'IN'
detect_country_from_url('https://shop.co.uk')  # 'GB'

# Test validation
validate_postal_code('110001', 'IN')    # True
validate_postal_code('12345', 'IN')     # False (wrong format)

validate_phone('9876543210', 'IN')      # True
validate_phone('555-123-4567', 'US')    # True
```

---

## 🔧 API Reference

### Functions

#### `detect_country_from_url(url: str) -> Optional[str]`
Detect country from URL.

**Returns**: Country code (`'IN'`, `'US'`, etc.) or `None`

#### `get_country_config(country_code: str) -> Dict`
Get full config for a country.

**Returns**: Dict with all country-specific settings

#### `get_all_countries() -> Dict`
Get all available country configs.

**Use case**: Generate country dropdowns

#### `validate_postal_code(postal_code: str, country_code: str) -> bool`
Validate postal code format for country.

#### `validate_phone(phone: str, country_code: str) -> bool`
Validate phone number format for country.

#### `format_address_for_country(address_data: Dict, country_code: str) -> str`
Format address according to country conventions.

### Convenience Functions

```python
is_india(country_code)   # Check if 'IN'
is_us(country_code)      # Check if 'US'
is_uk(country_code)      # Check if 'GB'
```

---

## 📊 Integration Status

| Component       | Status | Notes                           |
|-----------------|--------|---------------------------------|
| `orchestrator`  | ✅ Done | Auto-detects, enriches planner |
| `planner_agent` | ✅ Done | Receives country context       |
| `browser_agent` | ✅ Done | Updated prompts (manual)       |
| React frontend  | 🔲 TODO | Could show detected country    |
| Validation      | ✅ Done | Postal code & phone validators |

---

## 🎯 Usage Examples

### In Orchestrator

```python
from src.checkout_ai.utils.country_detector import *

url = task_data['tasks'][0]['url']
country = detect_country_from_url(url)
config = get_country_config(country)

print(f"🌍 Detected: {config['name']}")
print(f"   Postal: {config['postal_code_label']}")
```

### In Custom Tools

```python
# Get user's postal code
postal_code = "110001"
country = self.detected_country  # From orchestrator

if validate_postal_code(postal_code, country):
    # Fill the field
    pass
else:
    config = get_country_config(country)
    raise ValueError(
        f"Invalid {config['postal_code_label']}. "
        f"Example: {config['postal_code_example']}"
    )
```

---

## 🔐 Production Readiness

✅ **Error Handling**: Graceful fallbacks, never crashes  
✅ **Logging**: Logs detection results  
✅ **Testable**: Unit tests provided  
✅ **Documented**: Inline docs + this guide  
✅ **Scalable**: Add countries via config only  
✅ **Type Hints**: Full type annotations  
✅ **Validation**: Regex patterns for all fields  

---

## 🚀 Next Steps

### Immediate
- ✅ Country detection implemented
- ✅ Integration with orchestrator complete
- ✅ Test file created

### Future Enhancements
1. **Add more countries** (FR, IT, ES, JP, etc.)
2. **Frontend integration**: Display detected country in UI
3. **User override**: Allow user to manually select country
4. **Currency conversion**: Auto-convert prices
5. **Shipping zones**: Map countries to shipping regions

---

## 📝 Configuration Fields Reference

When adding a country, these fields are available:

| Field                  | Required | Description                        | Example                |
|------------------------|----------|------------------------------------|------------------------|
| `name`                 | ✅       | Full country name                  | `'India'`              |
| `postal_code_label`    | ✅       | What locals call it                | `'PIN Code'`           |
| `postal_code_pattern`  | ✅       | Regex for validation               | `r'^\d{6}$'`           |
| `postal_code_example`  | ✅       | Example postal code                | `'110001'`             |
| `phone_format`         | ✅       | Description                        | `'10 digits'`          |
| `phone_example`        | ✅       | Example number                     | `'9876543210'`         |
| `phone_pattern`        | ✅       | Regex for validation               | `r'^\d{10}$'`          |
| `state_required`       | ✅       | Is state mandatory?                | `True`                 |
| `state_label`          | ✅       | Display label                      | `'State'`              |
| `currency_symbol`      | ✅       | Symbol                             | `'₹'`                  |
| `currency_code`        | ✅       | ISO code                           | `'INR'`                |
| `address_format`       | ✅       | Field order (comma-separated)      | `'address,city,pin'`   |
| `common_domains`       | ✅       | TLDs for this country              | `['.in', '.co.in']`    |
| `major_sites`          | ✅       | Known e-commerce domains           | `['amazon.in']`        |

---

## ✅ Summary

You now have a **production-ready, extensible country detection system** that:

1. ✅ Automatically detects country from URLs
2. ✅ Provides country-specific checkout configs
3. ✅ Integrates seamlessly with your agents
4. ✅ Can be extended with new countries in minutes
5. ✅ Includes validation and testing utilities

**To add a new country**: Just add 1 entry to `COUNTRY_CONFIGS` dict. Done!
