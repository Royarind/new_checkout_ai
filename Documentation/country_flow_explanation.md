# Country-Specific Agent Execution Flow

## 🌍 Overview

This document explains how **country detection** influences the execution flow of all three agents (Orchestrator → Planner → Browser) with concrete examples.

---

## 🔄 Complete Flow Diagram

```
User Request
    ↓
1. ORCHESTRATOR (Country Detection)
    ↓
    ├─→ Extract URL from task
    ├─→ detect_country_from_url(url)
    ├─→ get_country_config(country_code)
    └─→ Enrich planner prompt with country context
    ↓
2. PLANNER AGENT (Country-Aware Planning)
    ↓
    ├─→ Receives country context
    ├─→ Generates country-specific steps
    └─→ Returns plan with correct terminology
    ↓
3. BROWSER AGENT (Country-Specific Execution)
    ↓
    ├─→ Executes steps with country awareness
    ├─→ Adapts to local field labels
    └─→ Uses country-specific validation
    ↓
Checkout Complete!
```

---

## 📋 Step-by-Step Flow

### **Phase 1: Orchestrator (Country Detection)**

**What Happens**:
```python
# In orchestrator.execute_task()

# 1. Extract URL
url = customer_data['tasks'][0]['url']  
# Example: "https://amazon.in/product/123"

# 2. Detect country
detected_country = detect_country_from_url(url)
# Returns: 'IN'

# 3. Get country config
country_config = get_country_config('IN')
# Returns: {'name': 'India', 'postal_code_label': 'PIN Code', ...}

# 4. Enrich planner prompt
query += f"""
[COUNTRY CONTEXT]
Country: India (IN)
Postal Code Label: PIN Code (example: 110001)
Phone Format: 10 digits (example: 9876543210)
State Required: Yes
Currency: ₹ (INR)
"""
```

**Output**: Orchestrator passes **enriched query** to Planner

---

### **Phase 2: Planner Agent (Country-Aware Planning)**

**What Changes**: Planner generates steps using **country-specific terminology**

#### Example 1: India (IN)

**Input to Planner**:
```
Task: Checkout product at https://amazon.in/product/123
[COUNTRY CONTEXT]
Country: India (IN)
Postal Code Label: PIN Code (example: 110001)
```

**Generated Plan**:
```python
[
    "Navigate to https://amazon.in/product/123",
    "Select variant: size=M",
    "Click 'Add to Cart'",
    "Navigate to Cart",
    "Click 'Proceed to Checkout'",
    "Fill email: user@example.com",
    "Fill contact details (first name, last name, phone: 10 digits)",
    "Fill shipping address (address, city, state, PIN code: 6 digits)",  # ← PIN Code!
    "Select cheapest shipping",
    "Click 'Continue to Payment'",
    "Wait for payment page"
]
```

#### Example 2: United Kingdom (GB)

**Input to Planner**:
```
Task: Checkout product at https://amazon.co.uk/product/123
[COUNTRY CONTEXT]
Country: United Kingdom (GB)
Postal Code Label: Postcode (example: SW1A 1AA)
State Required: No (optional)
```

**Generated Plan**:
```python
[
    "Navigate to https://amazon.co.uk/product/123",
    "Select variant: size=M",
    "Click 'Add to Cart'",
    "Navigate to Cart",
    "Click 'Proceed to Checkout'",
    "Fill email: user@example.com",
    "Fill contact details (first name, last name, phone)",
    "Fill shipping address (address, city, Postcode)",  # ← Postcode, no state!
    "Select standard shipping",
    "Click 'Continue to Payment'",
    "Wait for payment page"
]
```

**Key Differences**:
- India: "PIN code (6 digits)", state required
- UK: "Postcode", state optional

---

### **Phase 3: Browser Agent (Country-Specific Execution)**

**What Changes**: Browser adapts execution based on **detected country context**

#### Agent Behavior by Country:

**Browser Agent Prompt** (already updated):
```
<country_handling>
Always infer the country from page content and adapt:

- INDIA (IN):
  - Postal code is called PIN (6 digits)
  - Use fill_zip_code for PIN
  - Phone is 10-digit mobile
  - Use fill_landmark if available

- UNITED STATES (US):
  - Use State (2-letter)
  - ZIP code (5 or 9 digits)
  
- UNITED KINGDOM (UK):
  - Postcode (alphanumeric, e.g., SW1A 1AA)
  - State/County optional
</country_handling>
```

#### Execution Example (India):

**Step**: `"Fill shipping address (address, city, state, PIN code)"`

**Browser Agent Does**:
```python
# 1. Reads step text: "PIN code"
# 2. Uses fill_zip_code tool (works for all postal code types)
# 3. Validates: 6 digits for India
# 4. Fills: "110001"
```

**Behind the scenes**:
```python
# Orchestrator has country config available
postal_code = customer_data['shippingAddress']['postalCode']
country = self.detected_country  # 'IN'

# Validate before filling
if not validate_postal_code(postal_code, country):
    raise Error(f"Invalid PIN Code. Expected 6 digits, got: {postal_code}")
```

---

## 🔍 Detailed Country-Specific Examples

### **Scenario 1: India Checkout**

**URL**: `https://flipkart.com/product/xyz`

**Flow**:
1. **Orchestrator**: Detects `'IN'` from `flipkart.com`
2. **Planner**: Generates plan with "PIN Code" terminology
3. **Browser**: Executes with India-specific validation

**Generated Plan Snippet**:
```
- Fill contact: first name, last name, phone (10 digits)
- Fill address: House No., Street, Landmark (common in India)
- Fill city: Bangalore
- Fill state: Karnataka
- Fill PIN Code: 560001
- Click Continue
```

**Validation**:
- PIN: `^\d{6}$` ✅
- Phone: `9876543210` ✅ (10 digits)

---

### **Scenario 2: US Checkout**

**URL**: `https://amazon.com/product/abc`

**Flow**:
1. **Orchestrator**: Detects `'US'` from `.com` domain
2. **Planner**: Generates plan with "ZIP Code" terminology
3. **Browser**: Validates 5 or 9 digit ZIP

**Generated Plan Snippet**:
```
- Fill contact: first name, last name, phone
- Fill address: Street address
- Fill city: New York
- Fill state: NY (or New York from dropdown)
- Fill ZIP Code: 10001
- Click Continue
```

**Validation**:
- ZIP: `10001` ✅ or `10001-1234` ✅
- Phone: `5551234567` ✅ (10 digits)

---

### **Scenario 3: UK Checkout**

**URL**: `https://example.co.uk/checkout`

**Flow**:
1. **Orchestrator**: Detects `'GB'` from `.co.uk`
2. **Planner**: Generates plan with "Postcode" terminology
3. **Browser**: Uses alphanumeric validation

**Generated Plan Snippet**:
```
- Fill contact: first name, last name, phone
- Fill address: Address line 1, Address line 2
- Fill city: London
- Fill Postcode: SW1A 1AA
- Click Continue (no state required!)
```

**Validation**:
- Postcode: `SW1A 1AA` ✅ (alphanumeric)
- Phone: `02012345678` ✅ (10-11 digits)

---

## 🎯 Key Differences Across Countries

| Aspect            | India (IN)     | US            | UK            |
|-------------------|----------------|---------------|---------------|
| **Postal Code**   | PIN Code (6d)  | ZIP (5-9d)    | Postcode (α)  |
| **State Field**   | Required       | Required      | Optional      |
| **Phone Format**  | 10 digits      | 10 digits     | 10-11 digits  |
| **Landmark**      | Common         | Uncommon      | Uncommon      |
| **Currency**      | ₹ (INR)        | $ (USD)       | £ (GBP)       |

---

## 🤖 How Agents Adapt

### **Planner Agent**:
- ✅ Receives country context in prompt
- ✅ Generates steps with correct terminology
- ✅ Knows which fields are required/optional

**Example Adaptation**:
```
India:  "Fill PIN Code (6 digits)"
US:     "Fill ZIP Code (5 digits)"
UK:     "Fill Postcode"
```

### **Browser Agent**:
- ✅ Has country awareness in system prompt
- ✅ Uses generic tools (`fill_zip_code`) that work for all
- ✅ Adapts to page content dynamically

**Example Adaptation**:
```python
# Browser sees step: "Fill PIN Code"
# Uses: fill_zip_code tool
# Page shows: "PIN Code" label
# Browser fills: "110001"
```

### **Critique Agent**:
- ✅ Indirectly benefits (no changes needed)
- ✅ Validates based on orchestrator context

---

## 🔄 Flow Visualization

### **India Flow**:
```
User: "Checkout on Flipkart"
  ↓
Orchestrator: Detects 'IN' from flipkart.com
  ↓
Planner: "Fill PIN Code (6 digits, example: 560001)"
  ↓
Browser: Executes → validates 6 digits → fills "560001"
  ↓
Success! ✅
```

### **US Flow**:
```
User: "Checkout on Amazon.com"
  ↓
Orchestrator: Detects 'US' from .com
  ↓
Planner: "Fill ZIP Code (5 digits, example: 10001)"
  ↓
Browser: Executes → validates 5-9 digits → fills "10001"
  ↓
Success! ✅
```

### **UK Flow**:
```
User: "Checkout on Example.co.uk"
  ↓
Orchestrator: Detects 'GB' from .co.uk
  ↓
Planner: "Fill Postcode (example: SW1A 1AA), state optional"
  ↓
Browser: Executes → validates alphanumeric → fills "SW1A 1AA"
  ↓
Success! ✅
```

---

## 💡 Behind the Scenes (Code)

### **Orchestrator Integration**:
```python
class AgentOrchestrator:
    async def execute_task(self, task_description: str, customer_data: Dict):
        # 1. Detect country
        url = customer_data['tasks'][0]['url']
        self.detected_country = detect_country_from_url(url)
        self.country_config = get_country_config(self.detected_country)
        
        # 2. Enrich planner context
        query = task_description
        query += f"\n\n[COUNTRY CONTEXT]\n"
        query += f"Country: {self.country_config['name']}\n"
        query += f"Postal: {self.country_config['postal_code_label']}\n"
        # ... etc
        
        # 3. Call planner with enriched context
        plan = await planner.run(query)
        
        # 4. Browser executes country-aware plan
        for step in plan_steps:
            await browser.run(step)
```

### **Validation Integration** (Future):
```python
# Can be added to tools
def fill_zip_code(postal_code: str):
    country = orchestrator.detected_country
    
    if not validate_postal_code(postal_code, country):
        config = get_country_config(country)
        raise ValueError(
            f"Invalid {config['postal_code_label']}. "
            f"Expected format: {config['postal_code_example']}"
        )
    
    # Fill the field
    await fill_input_field(page, POSTAL_CODE_LABELS, postal_code)
```

---

## 🎯 Summary

### **What Changes by Country**:
1. **Terminology**: PIN vs ZIP vs Postcode
2. **Validation**: 6 digits vs 5-9 digits vs alphanumeric
3. **Required Fields**: State required/optional
4. **Labels**: What the page shows

### **What Stays the Same**:
1. **Tool Names**: `fill_zip_code` works for all
2. **Flow Structure**: Same checkout phases
3. **Agent Logic**: Same decision-making

### **How It Works**:
1. **Orchestrator**: Detects → Enriches
2. **Planner**: Adapts terminology
3. **Browser**: Validates & executes

**Result**: Country-aware checkout without hardcoding!
