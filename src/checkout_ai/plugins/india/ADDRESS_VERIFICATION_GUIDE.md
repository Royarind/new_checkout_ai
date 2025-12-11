# Address Verification Handler - Usage Example

## Quick Overview

The `AddressVerificationHandler` intelligently matches user's delivery address with saved addresses on Indian e-commerce sites.

## **How It Works**

### **Weighted Scoring Algorithm**:
```
Match Score = (
    PIN_CODE_match × 40% +     ← Most critical!
    CITY_match × 25% +
    STREET_match × 20% +
    NAME_match × 15%
)

If score ≥ 70% → Select existing address
If score < 70% → Add new address
```

### **Usage**:

```python
from src.checkout_ai.plugins.india import get_address_verifier

# After login, user lands on address selection page
verifier = get_address_verifier(page)

# User's delivery address
target_address = {
    'firstName': 'Arindam',
    'lastName': 'Roy',
    'addressLine1': '903, Alina, Hiranandani Estate',
    'addressLine2': 'off Godbunder Rd',
    'city': 'Thane West',
    'province': 'Maharashtra',
    'postalCode': '400607',  # PIN code
    'phone': '9820132767'
}

# Verify and select
result = await verifier.verify_and_select_address(target_address)

if result['action'] == 'selected_existing':
    print(f"✅ Selected saved address (match: {result['match_score']:.2%})")
    # Proceed to next step
    
elif result['action'] == 'add_new_address_initiated':
    print("➕ Clicked 'Add New Address', form is now visible")
    # Agent will fill address form in next step
```

## **Matching Examples**

### **Example 1: Perfect Match**
```
Saved:  "903 Alina Hiranandani, Thane West, 400607"
Target: "903, Alina, Hiranandani Estate, Thane West, 400607"

PIN: 400607 = 400607 → 40% ✅
City: "Thane West" = "Thane West" → 25% ✅  
Street: 85% similarity → 17%
Name: 70% similarity → 10.5%

Total: 92.5% → MATCH! Select existing
```

### **Example 2: Different Address**
```
Saved:  "123 MG Road, Mumbai, 400001"
Target: "903 Alina, Thane West, 400607"

PIN: 400001 ≠ 400607 → 0% ❌
City: "Mumbai" ≠ "Thane West" → 5%
Street: 20% similarity → 4%
Name: 60% similarity → 9%

Total: 18% → NO MATCH! Add new
```

## **Integration with Workflow**

The India plugin's `WorkflowHooksPlugin` can automatically inject this step:

```python
Original plan:
1. Login
2. OTP verification
3. Fill address
4. Payment

Enhanced plan (with saved addresses):
1. Login
2. OTP verification
3. **Verify saved address** ← Auto-added
4. Fill address (if needed)
5. Payment
```

## **Advantages**

✅ **Intelligent**: Fuzzy matching, not exact string comparison
✅ **Weighted**: PIN code matters most (40%)
✅ **Robust**: Handles variations in formatting
✅ **User-friendly**: Selects best match automatically
✅ **Fallback**: Adds new address if no good match

## **Site-Specific Behavior**

| Site | Saved Addresses | Behavior |
|------|----------------|----------|
| Myntra | Always shows after login | Verifies & selects |
| Flipkart | Shows in address step | Verifies & selects |
| Amazon.in | Multiple saved addresses | Selects best match |
| Ajio | Address book | Verifies & selects |
