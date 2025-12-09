# CheckoutAI Complete Debug Flow
## Data Flow Diagram with File Paths

---

## Flow Overview

```
USER INPUT (manual_test_flow.py)
    ↓
ORCHESTRATOR (main_orchestrator.py)
    ↓
PLANNER AGENT (planner_agent.py) → Generates Plan
    ↓
BROWSER AGENT (browser_agent.py) → Executes Steps
    ↓
UNIFIED TOOLS (unified_tools.py) → Tool Router
    ↓
DOM SERVICES (dom/service.py, legacy/phase2/*.py) → DOM Interaction
    ↓
PLAYWRIGHT PAGE → Browser Actions
    ↓
RESULT (back to orchestrator)
```

---

## Detailed Step-by-Step Flow

### **STEP 1: User Initiates Flow**

**File**: `manual_test_flow.py`

**Input**:
```python
TEST_CONFIG = {
    "customer": {
        "contact": {
            "firstName": "Roy",
            "lastName": "Arindam",
            "email": "aroy23@gmail.com",
            "phone": "555-0123"
        },
        "shippingAddress": {
            "addressLine1": "8600 Eversham Rd",
            "city": "Henrico",
            "province": "VA",
            "postalCode": "23294",
            "country": "United States"
        }
    },
    "tasks": [{
        "url": "https://www.tommiecopper.com/product",
        "quantity": 1,
        "selectedVariant": {
            "color": "Slate Grey",
            "size": "L"
        }
    }]
}
```

**Function Call**:
```python
result = await run_full_flow(TEST_CONFIG)
```

**Output** → Passes to `main_orchestrator.py`

---

### **STEP 2: Main Orchestrator Initialization**

**File**: `main_orchestrator.py`

**Function**: `run_full_flow(config: Dict)`

**Actions**:
1. Set event loop policy (Windows fix)
   ```python
   asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
   ```

2. Launch Playwright browser
   ```python
   browser = await playwright.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
   ```

3. Store customer data globally
   ```python
   set_customer_data(config["customer"])
   ```

4. Store page reference
   ```python
   set_page(page)
   ```

5. Call orchestrator
   ```python
   await AgentOrchestrator.run(page, config["tasks"][0])
   ```

**Output** → Passes task to `orchestrator.py`

---

### **STEP 3: Agent Orchestrator**

**File**: `src/checkout_ai/agents/orchestrator.py`

**Function**: `AgentOrchestrator.run(page, task)`

**Input**:
```python
task = {
    "url": "https://www.tommiecopper.com/product",
    "quantity": 1,
    "selectedVariant": {"color": "Slate Grey", "size": "L"}
}
```

**Actions**:

#### 3.1: Generate Plan (Call Planner Agent)

**Function**: `planner.run(user_prompt)`

**User Prompt Construction**:
```python
user_prompt = f"""
Navigate to {task.url}, 
select variants (color={task.selectedVariant.color}, size={task.selectedVariant.size}), 
add to cart with quantity {task.quantity}. 
Then proceed to checkout and fill all information 
(email, shipping, payment) to place the order.
"""
```

**Output** → Goes to Planner Agent

---

### **STEP 4: Planner Agent**

**File**: `src/checkout_ai/agents/planner_agent.py`

**Input**: User prompt (string)

**LLM Call**:
```python
PA_agent.run(user_prompt)
```

**LLM Model**: `ollama:qwen2.5:7b` OR `groq:llama-3.3-70b-versatile`

**LLM Response** (Pydantic Model):
```python
PLANNER_AGENT_OP(
    plan_steps=[
        "Navigate to https://www.tommiecopper.com/product",
        "Select variant: color=Slate Grey",
        "Select variant: size=L",
        "Click 'Add to Cart'",
        "Navigate to Cart",
        "Click Checkout",
        "Fill Email: aroy23@gmail.com",
        "Fill Address Line 1: 8600 Eversham Rd",
        "Fill City: Henrico",
        "Select State/Province: Virginia",
        "Fill Zip/Postal Code: 23294",
        "Click Continue",
        "Select Shipping Method (Standard)",
        "Click Continue to Payment"
    ]
)
```

**Output** → Plan steps (List[str]) returned to Orchestrator

---

### **STEP 5: Execute Steps Loop (Orchestrator)**

**File**: `src/checkout_ai/agents/orchestrator.py`

**Loop**: For each step in `plan_steps`:

```python
for step_text in plan_steps:
    result = await browser.run(
        step_text, 
        deps=current_step_class(current_step=step_text)
    )
```

**Example Step**: `"Select variant: size=L"`

**Output** → Passes to Browser Agent

---

### **STEP 6: Browser Agent**

**File**: `src/checkout_ai/agents/browser_agent.py`

**Input**:
```python
current_step_class(current_step="Select variant: size=L")
```

**LLM Call**:
```python
BA_agent.run(
    "Select variant: size=L",
    deps=current_step_class(...)
)
```

**LLM Model**: Same as Planner

**LLM Decision** (Tool Call):
```python
Tool: select_variant
Args: {
    "variant_type": "size",
    "variant_value": "L"
}
```

**Function Executed**:
```python
@BA_agent.tool_plain
async def select_variant(variant_type: str, variant_value: str) -> str:
    result = await execute_tool("select_variant", variant_type=variant_type, variant_value=variant_value)
    return str(result)
```

**Output** → Calls `execute_tool` in unified_tools.py

---

### **STEP 7: Unified Tools Router**

**File**: `src/checkout_ai/agents/unified_tools.py`

**Function**: `execute_tool(tool_name, **kwargs)`

**Input**:
```python
tool_name = "select_variant"
kwargs = {"variant_type": "size", "variant_value": "L"}
```

**Tool Mapping**:
```python
TOOLS = {
    "select_variant": select_variant_tool,
    "add_to_cart": add_to_cart_tool,
    "fill_email": fill_email_tool,
    # ... etc
}
```

**Function Called**:
```python
async def select_variant_tool(variant_type: str, variant_value: str) -> Dict[str, Any]:
    from src.checkout_ai.dom.service import find_variant_dom
    page = get_page()
    result = await find_variant_dom(page, variant_type, variant_value)
    return {"success": result.get('success', False), "message": result.get('content', '')}
```

**Output** → Calls DOM Service

---

### **STEP 8: DOM Service (Universal Variant Finder)**

**File**: `src/checkout_ai/dom/service.py`

**Function**: `find_variant_dom(page, variant_type, variant_value)`

**Input**:
```python
page = <Playwright Page object>
variant_type = "size"
variant_value = "L"
```

**Actions**:

#### 8.1: Create Finder Instance
```python
finder = UniversalDOMFinder(page)
```

#### 8.2: Detect Product Container
```python
container = await page.evaluate("""
    () => {
        const selectors = ['.product-main', 'main', 'body'];
        for (const s of selectors) {
            const el = document.querySelector(s);
            if (el) return s;
        }
        return null;
    }
""")
# Result: "main"
```

#### 8.3: Phase 1 - Overlay Search
**File**: `src/checkout_ai/dom/js_assets/overlay_search.js`

```javascript
// Executed in browser via page.evaluate()
(args) => {
    const { val, containerSelector } = args;
    const container = document.querySelector(containerSelector || 'body');
    const elements = container.querySelectorAll('button, label, a, div[role="button"]');
    
    for (const el of elements) {
        const text = el.textContent.trim();
        if (text === 'L' && el.offsetHeight > 0) {
            return {
                found: true,
                action: 'click',
                elementIndex: el.dataset.elementIndex,
                element: {
                    tagName: el.tagName,
                    text: text,
                    className: el.className
                }
            };
        }
    }
    return { found: false };
}
```

**Result**:
```python
{
    "found": True,
    "action": "click",
    "elementIndex": 42,
    "element": {
        "tagName": "LABEL",
        "text": "L",
        "className": "form-option"
    }
}
```

#### 8.4: Execute Action (Click)

**File**: `src/checkout_ai/dom/service.py` → `_safe_scroll_and_click()`

**Actions**:
1. Inspect element position
   ```python
   info = await page.evaluate(inspect_element.js, {'targetIndex': 42})
   # Returns: {"center": {"x": 882, "y": 480}, "isVisible": True}
   ```

2. Click via mouse
   ```python
   await page.mouse.click(882, 480)
   ```

#### 8.5: Verify Selection

**File**: `src/checkout_ai/dom/js_assets/verification.js`

```javascript
(args) => {
    const { variantValue } = args;
    // Check if size L is now selected (active class, aria-selected, etc)
    const selected = document.querySelector('[aria-selected="true"]');
    if (selected && selected.textContent.includes('L')) {
        return { verified: true };
    }
    return { verified: false };
}
```

**Result**:
```python
{
    "success": True,
    "content": "VERIFIED: size=L",
    "action": "verified"
}
```

**Output** → Returns to unified_tools.py

---

### **STEP 9: Return to Browser Agent**

**File**: `src/checkout_ai/agents/browser_agent.py`

**Receives**:
```python
result = {"success": True, "message": "VERIFIED: size=L"}
```

**Returns to LLM**:
```python
return str(result)
# "{'success': True, 'message': 'VERIFIED: size=L'}"
```

**LLM Final Response**:
```python
"SUCCESS: variant_selected_size_L"
```

**Output** → Returns to Orchestrator

---

### **STEP 10: Orchestrator Logs Result**

**File**: `src/checkout_ai/agents/orchestrator.py`

**Receives**:
```python
result.output = "SUCCESS: variant_selected_size_L"
```

**Logs**:
```python
logger.info(f"ORCHESTRATOR: Browser Result: SUCCESS: variant_selected_size_L")
history.append({"step": "Select variant: size=L", "result": "SUCCESS: variant_selected_size_L"})
```

**Next Step**: Loop continues with next plan step

---

## Example: Form Filling Flow

### **STEP: "Fill Email: aroy23@gmail.com"**

**Browser Agent** → Calls `fill_email(email="aroy23@gmail.com")`

**Unified Tools** → `fill_email_tool()`

**DOM Interaction**:

**File**: `src/checkout_ai/legacy/phase2/checkout_dom_finder.py`

**Function**: `fill_input_field(page, EMAIL_LABELS, email)`

**Keywords** (`checkout_keywords.py`):
```python
EMAIL_LABELS = [
    "email", "e-mail", "emailaddress", "email address",
    "your email", "enter email", "customerEmail"
]
```

**DOM Search**:
```python
for label in EMAIL_LABELS:
    for frame in page.frames:
        inputs = await frame.query_selector_all('input[type="text"], input[type="email"], input')
        for inp in inputs:
            field_label = await inp.get_attribute('name') or await inp.get_attribute('placeholder')
            if label.lower() in field_label.lower():
                await inp.fill(email)
                return {"success": True}
```

**Result**:
```python
{"success": True}
```

---

## Data Format Summary

### **1. Entry (manual_test_flow.py)**
```python
Dict[str, Any] = {
    "customer": {...},
    "tasks": [...]
}
```

### **2. Planner Output**
```python
List[str] = [
    "Navigate to URL",
    "Select variant: size=L",
    ...
]
```

### **3. Browser Agent Tool Call**
```python
{
    "tool": "select_variant",
    "args": {"variant_type": "size", "variant_value": "L"}
}
```

### **4. Unified Tools**
```python
Dict[str, Any] = {
    "success": True,
    "message": "VERIFIED: size=L"
}
```

### **5. Final Output (to user)**
```python
{
    "success": True,
    "message": "Checkout completed successfully",
    "order_number": "ORD-12345"
}
```

---

## Key Files Reference

| File | Purpose | Input | Output |
|------|---------|-------|--------|
| `manual_test_flow.py` | Entry point | User config | Calls orchestrator |
| `main_orchestrator.py` | Browser setup | Config dict | Playwright page |
| `orchestrator.py` | Agent loop | Task dict | Success/Failure |
| `planner_agent.py` | Plan generation | User prompt | List of steps |
| `browser_agent.py` | Step execution | Single step text | Tool results |
| `unified_tools.py` | Tool router | Tool name + kwargs | Tool result dict |
| `dom/service.py` | Variant selection | page, type, value | DOM result |
| `checkout_dom_finder.py` | Form filling | page, labels, value | Success/Fail |
| `checkout_keywords.py` | Label keywords | N/A | Constants |

---

## Common Debug Points

### **Debug Point 1: LLM Not Parsing Step Correctly**
**Location**: `browser_agent.py` (LLM response)  
**Check**: Does step text "Select variant: size=L" get parsed to `select_variant("size", "L")`?  
**Fix**: Enhance `BA_SYS_PROMPT` with examples

### **Debug Point 2: Tool Not Found**
**Location**: `unified_tools.py` → `TOOLS` dict  
**Check**: Is tool name in registry?  
**Fix**: Add to `TOOLS` mapping

### **Debug Point 3: DOM Element Not Found**
**Location**: `dom/service.py` → `find_variant()`  
**Check**: Did phase 1/2/3 search find the element?  
**Fix**: Check `container_selector`, adjust JS search logic

### **Debug Point 4: Form Field Not Filled**
**Location**: `checkout_dom_finder.py` → `fill_input_field()`  
**Check**: Are keywords matching field labels?  
**Fix**: Add more keywords to `checkout_keywords.py`

### **Debug Point 5: Click Not Working**
**Location**: `dom/service.py` → `_safe_scroll_and_click()`  
**Check**: Is element visible? Coordinates correct?  
**Fix**: Add scroll, wait for element

---

## Logging Points

To trace the full flow, check logs at:

1. **Orchestrator**: `logger.info(f"Executing Step {i}: {step}")`
2. **Planner**: `logger.info(f"Generated {len(plan_steps)} steps")`
3. **Browser Agent**: Tool execution logs (in LLM trace)
4. **Unified Tools**: `logger.info(f"Tool {tool_name} executed: {result}")`
5. **DOM Service**: `logger.info(f"Phase 3 (Pattern Match): Found {variant_type}={variant_value}")`
6. **Form Filler**: `logger.info(f"[ADDRESS_FILL] - ✓ FILLED - {field_name}")`
