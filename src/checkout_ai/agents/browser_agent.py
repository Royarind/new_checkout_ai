from pydantic_ai import RunContext
from src.checkout_ai.dom.service import UniversalDOMFinder
import json
import os
import asyncio
from dotenv import load_dotenv
from pydantic import BaseModel
try:
    from pydantic_ai import Agent, ModelSettings
except ImportError:
    from pydantic_ai import Agent
    # Mock ModelSettings if import fails (older version?)
    class ModelSettings(BaseModel):
        temperature: float = 0.0

BrowserAgent = Agent

from pydantic_ai import Agent
from src.checkout_ai.core.utils.openai_client import get_client, get_model, get_pydantic_model
from src.checkout_ai.agents.unified_tools import execute_tool, TOOLS
from typing import List

async def _all_required_fields_filled(required_labels: List[str]) -> bool:
    """Return True if every label in *required_labels* has a non‑empty value on the page.
    Uses the low‑level `validate_page` tool which returns a dict with a `fields` list.
    Each field dict contains at least `label` and `value` keys.
    """
    page_state = await execute_tool("validate_page")
    fields = page_state.get("fields", []) if isinstance(page_state, dict) else []
    for lbl in required_labels:
        match = next((f for f in fields if lbl.lower() in f.get("label", "").lower()), None)
        if not match or not match.get("value"):
            return False
    return True
load_dotenv()

# API key loaded from backend config (reads .env)
try:
    from backend.api.llm_config_api import get_session_llm_config
    config = get_session_llm_config()
    if config and config.get('api_key'):
        os.environ['OPENAI_API_KEY'] = config['api_key']
except:
    pass


class current_step_class(BaseModel):
    current_step : str

#System prompt for Browser Agent
# BA_SYS_PROMPT = """
# <agent_role>
# You are an intelligent autonomous browser agent. You receive a specific step to execute from a larger plan. 
# Your goal is to execute this step successfully using your tools.
# </agent_role>

# <execution_protocol>
# 1. **Analyze the Step**: Understand what needs to be done (e.g., "Select variant size=M").
# 2. **Check Page State**: Use `validate_page` to see if you are on the right page and if elements are visible.
# 3. **Select Tool**: Choose the most appropriate tool.
#    - For checkout forms, use high-level tools like `fill_contact` or `fill_address`.
#    - For variants, use `select_variant` (supports any type: color, size, storage, flavor, etc.).
#    - For navigation, use `navigate`.
# 4. **Execute**: Run the tool.
# 5. **Verify**: Check if the action worked.
# </execution_protocol>

# <communication_tools>
# If you are stuck or need help, use these special tools instead of failing:
# - `call_planner(reason, current_state)`: Use this if:
#   - You are lost ("I don't know where I am")
#   - The current step text doesn't make sense
#   - You need the plan to be changed
# - `call_critique(concern, step_result)`: Use this if:
#   - You are unsure if an action was correct
#   - You encountered an error and want advice on how to fix it
#   - You hit a critical "Gate" (like Payment Page) and need verification
# </communication_tools>

# <outputs>
# Your tool calls will be executed by the system.
# Return a simple confirmation string if successful, formatted as: "SUCCESS: [details]"
# If failed, return: "ERROR: [details]"
# </outputs>
# """

BA_SYS_PROMPT = """
<agent_role>
You are an intelligent autonomous browser agent executing ONE checkout step at a time for e-commerce sites in India, the US, or the UK.

**CRITICAL: Execute ONLY the current step you receive. Do NOT anticipate or execute future steps.**
**The orchestrator manages the overall flow - you focus on the single step given to you.**

You always:
- Execute ONLY the action described in the current step text.
- Use the provided tools safely and efficiently.
- Adapt address, phone, and payment actions to the country shown on the page.
- Return immediately after completing the current step.
</agent_role>

<single_step_execution>
**IMPORTANT RULES:**
1. You receive ONE step description (e.g., "Navigate to URL", "Select variant: color=Blue", "Fill email").
2. Execute ONLY that step - do not do anything else.
3. Do NOT try to be smart by executing multiple steps at once.
4. Trust that the orchestrator will give you the next step when needed.
5. If the current step is "Navigate to URL", ONLY navigate - do not select variants or add to cart.
6. If the current step is "Select variant: color=Blue", ONLY select that variant - do not add to cart.

**Examples of CORRECT single-step execution:**
- Step: "Navigate to product page" → Call `navigate()` only, return
- Step: "Select variant: size=M" → Call `select_variant()` only, return  
- Step: "Add to Cart" → Call `add_to_cart()` only, return
- Step: "Fill email" → Call `fill_email()` only, return

**Examples of WRONG multi-step execution:**
- Step: "Navigate to product page" → ❌ Do NOT call navigate() + select_variant() + add_to_cart()
- Step: "Select variant: size=M" → ❌ Do NOT call select_variant() + add_to_cart()
</single_step_execution>

<mental_model_of_checkout>
For context only (the orchestrator follows this flow, not you):

1) Product page: Select variants → Add to cart → Navigate to cart
2) Cart: Click checkout
3) Contact / Email / Login: Fill email/phone, handle login if required
4) Address: Fill shipping address → Continue
5) Shipping: Select shipping method → Continue to payment
6) Payment / Review: Follow given step only (do not invent payment data)
7) Confirmation: Wait for confirmation page
</mental_model_of_checkout>

<country_handling>
Always infer the country from page content (country dropdown, currency, labels, etc.) and adapt:

- COMMON:
  - Use `fill_contact`, `fill_address`, `fill_email`, `select_country`, `select_state`, `fill_zip_code`.
  - Use `fill_contact_and_address_and_continue` if both contact + address appear on the same page.
  - Use `select_shipping_method` then `click_continue_to_payment` on shipping steps.

- INDIA (IN):
  - Postal code is called PIN (6 digits) but still use `fill_zip_code`.
  - Phone is usually a 10-digit mobile; use `fill_phone`.
  - Use `fill_landmark` if a landmark field is present.
  - Payment methods may include UPI, Netbanking, Cards, COD. Only click/select what the current step specifies.

- UNITED STATES (US):
  - Use State (2-letter or full) with `select_state`.
  - Postal code is ZIP (5 or 9 digits) using `fill_zip_code`.
  - Phone in standard US format; still use `fill_phone`.

- UNITED KINGDOM (UK):
  - Country is United Kingdom / UK.
  - Use `fill_zip_code` for Postcode (alphanumeric, e.g., SW1A 1AA).
  - State/County may be optional; still use `select_state` if required on the page.

Never create fake personal or payment data; rely on given values or stored customer data via tools.
</country_handling>

<execution_protocol>
1. **Read the current step text carefully** (e.g., "Select variant: size=M", "Fill shipping address").
2. **Identify the ONE action required** by this step.
3. Use `validate_page` ONLY if needed to understand where you are.
4. **Choose the ONE tool** that matches the step:
   - Variants: `select_variant` (parses from step text automatically).
   - Quantity: Skip if quantity=1 (default), otherwise use `select_variant`.
   - Add to cart: `add_to_cart` or `click_add_to_cart`.
   - Navigate to cart: `navigate_to_cart` (handles modals/URLs automatically).
   - Cart: `click_checkout`, `click_guest_checkout`.
   - Contact & address: `fill_email`, `fill_contact`, `fill_address`.
   - Shipping: `select_shipping_method`, `click_continue_to_payment`.
   - Generic forward: `click_continue` or `finalize_checkout`.
   - Low-level: `click`, `fill_text`, `select_dropdown` only if no high-level tool fits.
5. **Execute the ONE tool and return** - let the orchestrator give you the next step.
6. If stuck or confused, use `call_planner(reason, current_state)` to request help.
7. If unsure about a critical action, use `call_critique(concern, step_result)`.
</execution_protocol>

<good_behavior>
- **Execute ONE action per step** - do not chain multiple actions.
- Be decisive: pick the ONE clear tool for the current step.
- Do not loop on the same failing action.
- Do not change the user's plan; request help via `call_planner` instead.
- Do not hallucinate data; use only tool-provided / plan-provided values.
- **NEVER click navigation links** (Home, Shop, About, Contact, etc.).
- **CRITICAL: Call fill tools WITHOUT parameters - they auto-get customer data:**
  - WRONG: `fill_contact(first_name="John")` or `fill_address(city="Sample City")`
  - CORRECT: `fill_contact()` and `fill_address()` with NO arguments
  - NEVER invent, hallucinate, or provide example values!
</good_behavior>

<outputs>
On success, return: "SUCCESS: [what you did]"
On failure, return: "ERROR: [what went wrong]"
</outputs>
"""

# Setup BA - model from UI config ONLY
# Allow import to succeed even if no API key configured yet
BA_agent = None
try:
    BA_model = get_pydantic_model()
    
    # Only create agent if we have a model
    if BA_model:
        BA_agent = Agent(
            model=BA_model, 
            system_prompt=BA_SYS_PROMPT,
            deps_type=current_step_class,
            name="Browser Agent",
            retries=3,
            model_settings={'temperature': 0.5},
        )
        print("[Browser Agent] Initialized successfully")
    else:
        print("[Browser Agent] Skipping initialization - no model configured yet")
except Exception as e:
    print(f"[Browser Agent] Could not initialize at import time: {e}")
    print("[Browser Agent] Agent will be initialized when model is configured")

def get_or_create_browser_agent():
    """Get existing agent or create new one if model is now available"""
    global BA_agent
    
    if BA_agent is not None:
        return BA_agent
    
    # Try to create agent now that model might be available
    try:
        BA_model = get_pydantic_model()
        
        if BA_model:
            BA_agent = Agent(
                model=BA_model, 
                system_prompt=BA_SYS_PROMPT,
                deps_type=current_step_class,
                name="Browser Agent",
                retries=3,
                model_settings={'temperature': 0.5},
            )
            print("[Browser Agent] Initialized successfully (lazy)")
            return BA_agent
    except Exception as e:
        print(f"[Browser Agent] Failed to initialize: {e}")
    
    return None




# Register high-level tools - only if agent was successfully created
if BA_agent is not None:
    @BA_agent.tool
    async def select_variant(ctx: RunContext) -> str:
        """Select product variant by parsing the current step description.
        The step format should be: 'Select variant: color=Slate Grey' or 'Select variant: size=L'
        """
        import re
        import logging
        logger = logging.getLogger(__name__)
        
        # Get current_step from context deps, not from LLM parameter!
        current_step = ctx.deps.current_step
        logger.info(f"🔍 [SELECT_VARIANT] Received step: '{current_step}'")
        
        # Extract variant_type and variant_value from step description
        match = re.search(r'(\w+)\s*=\s*([^,]+)', current_step)
        if not match:
            logger.error(f"❌ [SELECT_VARIANT] Could not parse variant from: '{current_step}'")
            logger.error(f"   Expected format: 'Select variant: type=value' (e.g., 'Select variant: color=Blue')")
            return "ERROR: Could not parse variant from step. Expected format: 'Select variant: type=value'"
        
        variant_type = match.group(1).strip()
        variant_value = match.group(2).strip()
        
        logger.info(f"✅ [SELECT_VARIANT] Parsed successfully: {variant_type}={variant_value}")
        
        result = await execute_tool("select_variant", variant_type=variant_type, variant_value=variant_value)
        return str(result)

    @BA_agent.tool_plain
    async def add_to_cart() -> str:
        """Add product to cart"""
        result = await execute_tool("add_to_cart")
        return str(result)

    @BA_agent.tool_plain
    async def click_add_to_cart(quantity: int = 1) -> str:
        """Click the add to cart button (alias). Optional: Set quantity first if > 1."""
        # Only set quantity if > 1 (1 is default, no need to change)
        if quantity > 1:
            await execute_tool("select_variant", variant_type="quantity", variant_value=str(quantity))
        result = await execute_tool("add_to_cart")
        return str(result)

    @BA_agent.tool_plain
    async def navigate_to_cart() -> str:
        """Navigate to cart page"""
        result = await execute_tool("navigate_to_cart")
        return str(result)

    @BA_agent.tool_plain
    async def fill_email() -> str:
        """Fill email using stored customer data. NO parameters needed."""
        result = await execute_tool("fill_email")
        await asyncio.sleep(1)
        return str(result)

    @BA_agent.tool_plain
    async def fill_contact() -> str:
        """Fill contact information using stored customer data. Call with NO parameters."""
        result = await execute_tool("fill_contact")
        await asyncio.sleep(1) # Wait for UI update
        # Auto‑click Continue if it appears after filling contact fields
        try:
            cont_res = await execute_tool("click_continue")
            if cont_res.get("success"):
                return f"{result} | continue_clicked"
        except Exception:
            pass
        return str(result)

    @BA_agent.tool_plain
    async def fill_contact_and_continue(first_name: str = None, last_name: str = None, phone: str = None) -> str:
        """Fill contact fields then click Continue if present."""
        # Handle "None" strings from LLM
        if first_name == "None": first_name = None
        if last_name == "None": last_name = None
        if phone == "None": phone = None
        
        # Fill the contact information first
        contact_res = await execute_tool("fill_contact", first_name=first_name, last_name=last_name, phone=phone)
        await asyncio.sleep(1)
        # Attempt to click Continue; ignore failure
        try:
            cont_res = await execute_tool("click_continue")
            # If click succeeded, include that info
            if cont_res.get('success'):
                return f"{contact_res} | continue_clicked"
        except Exception:
            # Any unexpected error is ignored – we just proceed
            pass
        return str(contact_res)

    @BA_agent.tool_plain
    async def fill_address() -> str:
        """Fill address using stored customer data. NO parameters needed."""
        result = await execute_tool("fill_address")
        await asyncio.sleep(1)
        # Auto-click Continue if it appears
        try:
            cont_res = await execute_tool("click_continue")
            if cont_res.get("success"):
                return f"{result} | continue_clicked"
        except Exception:
            pass
        return str(result)

    @BA_agent.tool_plain
    async def fill_address_and_continue(address: str = None, city: str = None, state: str = None, zip_code: str = None) -> str:
        """Fill address fields then click Continue if present."""
        # Handle "None" strings
        if address == "None": address = None
        if city == "None": city = None
        if state == "None": state = None
        if zip_code == "None": zip_code = None
        
        addr_res = await execute_tool("fill_address", address=address, city=city, state=state, zip_code=zip_code)
        await asyncio.sleep(1)
        # Try generic Continue button
        try:
            cont_res = await execute_tool("click_continue")
            if cont_res.get("success"):
                return f"{addr_res} | continue_clicked"
        except Exception:
            pass
        # Fallback to payment continue button
        try:
            pay_res = await execute_tool("click_continue_to_payment")
            if pay_res.get("success"):
                return f"{addr_res} | payment_continue_clicked"
        except Exception:
            pass
        return str(addr_res)
    @BA_agent.tool_plain
    async def fill_contact_and_address_and_continue(first_name: str = None, last_name: str = None, phone: str = None, address: str = None, city: str = None, state: str = None, zip_code: str = None) -> str:
        """Fill contact *and* address fields, then click Continue if present.
        If the Continue button is missing, falls back to the payment‑continue button.
        This reduces round‑trips and speeds up the checkout flow.
        """
        # 1️⃣ Fill contact information
        contact_res = await execute_tool("fill_contact", first_name=first_name, last_name=last_name, phone=phone)
        # 2️⃣ Fill address information
        address_res = await execute_tool("fill_address", address=address, city=city, state=state, zip_code=zip_code)
        # Combine results for reporting
        combined_res = f"{contact_res} | {address_res}"
        # 3️⃣ Try generic Continue button
        try:
            cont_res = await execute_tool("click_continue")
            if cont_res.get("success"):
                return f"{combined_res} | continue_clicked"
        except Exception:
            pass
        # 4️⃣ Fallback to payment Continue button
        try:
            pay_res = await execute_tool("click_continue_to_payment")
            if pay_res.get("success"):
                return f"{combined_res} | payment_continue_clicked"
        except Exception:
            pass
        return str(combined_res)
    @BA_agent.tool_plain
    async def click_checkout() -> str:
        """Click checkout button"""
        result = await execute_tool("click_checkout")
        return str(result)

    @BA_agent.tool_plain
    async def click_guest_checkout() -> str:
        """Click guest checkout"""
        result = await execute_tool("click_guest_checkout")
        return str(result)

    @BA_agent.tool_plain
    async def click_continue() -> str:
        """Click continue button"""
        result = await execute_tool("click_continue")
        return str(result)

    @BA_agent.tool_plain
    async def dismiss_popups() -> str:
        """Dismiss all popups"""
        result = await execute_tool("dismiss_popups")
        return str(result)

    @BA_agent.tool_plain
    async def validate_page() -> str:
        """Get current page state"""
        result = await execute_tool("validate_page")
        return str(result)

    @BA_agent.tool_plain
    async def finalize_checkout() -> str:
        """Attempt to click any remaining Continue/Next/Proceed button.
        Tries `click_continue`, `click_continue_to_payment`, and `click_checkout` in order.
        Returns a short summary of the action taken.
        """
        # Ordered list of possible continuation actions
        for tool_name in ["click_continue", "click_continue_to_payment", "click_checkout"]:
            try:
                res = await execute_tool(tool_name)
                if isinstance(res, dict) and res.get("success"):
                    return f"{tool_name}_clicked"
            except Exception:
                # Ignore any errors (e.g., tool not found or button absent) and try the next one
                continue
        return "no_continue_button_found"

    @BA_agent.tool_plain
    async def take_screenshot(path: str = "/tmp/agent_screenshot.png") -> str:
        """Take screenshot"""
        result = await execute_tool("take_screenshot", path=path)
        return str(result)

    @BA_agent.tool_plain
    async def fill_first_name(first_name: str = None) -> str:
        """Fill first name"""
        result = await execute_tool("fill_first_name", first_name=first_name)
        return str(result)

    @BA_agent.tool_plain
    async def fill_last_name(last_name: str = None) -> str:
        """Fill last name"""
        result = await execute_tool("fill_last_name", last_name=last_name)
        return str(result)

    @BA_agent.tool_plain
    async def fill_phone(phone: str = None) -> str:
        """Fill phone number"""
        result = await execute_tool("fill_phone", phone=phone)
        return str(result)

    @BA_agent.tool_plain
    async def select_country(country: str = None) -> str:
        """Select country"""
        result = await execute_tool("select_country", country=country)
        return str(result)

    @BA_agent.tool_plain
    async def fill_address_line1(address: str = None) -> str:
        """Fill address line 1"""
        result = await execute_tool("fill_address_line1", address=address)
        return str(result)

    @BA_agent.tool_plain
    async def fill_address_line2(address_line2: str = None) -> str:
        """Fill address line 2"""
        result = await execute_tool("fill_address_line2", address_line2=address_line2)
        return str(result)

    @BA_agent.tool_plain
    async def fill_landmark(landmark: str = None) -> str:
        """Fill landmark"""
        result = await execute_tool("fill_landmark", landmark=landmark)
        return str(result)

    @BA_agent.tool_plain
    async def fill_city(city: str = None) -> str:
        """Fill city"""
        result = await execute_tool("fill_city", city=city)
        return str(result)

    @BA_agent.tool_plain
    async def fill_zip_code(zip_code: str = None) -> str:
        """Fill zip code"""
        result = await execute_tool("fill_zip_code", zip_code=zip_code)
        return str(result)

    @BA_agent.tool_plain
    async def select_state(state: str = None) -> str:
        """Select state"""
        result = await execute_tool("select_state", state=state)
        return str(result)

    @BA_agent.tool_plain
    async def click_same_as_billing() -> str:
        """Click Same as billing checkbox"""
        result = await execute_tool("click_same_as_billing")
        return str(result)

    @BA_agent.tool_plain
    async def select_shipping_method(method: str = "cheapest") -> str:
        """Select shipping method"""
        result = await execute_tool("select_shipping_method", method=method)
        return str(result)

    @BA_agent.tool_plain
    async def click_continue_to_payment() -> str:
        """Click continue to payment"""
        result = await execute_tool("click_continue_to_payment")
        return str(result)

    # Low-level actions
    @BA_agent.tool_plain
    async def click(selector: str = None, text: str = None, x: int = None, y: int = None) -> str:
        """Click element"""
        result = await execute_tool("click", selector=selector, text=text, x=x, y=y)
        return str(result)

    @BA_agent.tool_plain
    async def fill_text(selector: str = None, text_content: str = "", label: str = None) -> str:
        """Fill text field"""
        result = await execute_tool("fill_text", selector=selector, text_content=text_content, label=label)
        return str(result)

    @BA_agent.tool_plain
    async def select_dropdown(selector: str = None, value: str = "", label: str = None) -> str:
        """Select dropdown option"""
        result = await execute_tool("select_dropdown", selector=selector, value=value, label=label)
        return str(result)

    @BA_agent.tool_plain
    async def scroll(direction: str = "down", pixels: int = 500) -> str:
        """Scroll page"""
        result = await execute_tool("scroll", direction=direction, pixels=pixels)
        return str(result)

    @BA_agent.tool_plain
    async def press_key(key: str) -> str:
        """Press keyboard key"""
        result = await execute_tool("press_key", key=key)
        return str(result)

    @BA_agent.tool_plain
    async def wait(seconds: float) -> str:
        """Wait for seconds"""
        result = await execute_tool("wait", seconds=seconds)
        return str(result)

    @BA_agent.tool_plain
    async def navigate(url: str) -> str:
        """Navigate to URL"""
        result = await execute_tool("navigate", url=url)
        return str(result)

    @BA_agent.tool_plain
    async def call_planner(reason: str, current_state: str) -> str:
        """Call Planner Agent to request a plan update.
        Use this when you are lost, the plan is invalid, or you are stuck loop.
        """
        # This returns a signal string that the Orchestrator intercepts
        return f"SIGNAL_CALL_PLANNER: {reason} | State: {current_state}"

    @BA_agent.tool_plain
    async def call_critique(concern: str, step_result: str) -> str:
        """Call Critique Agent to request help or verification.
        Use this when unsure of an action, facing an error, or hitting a Gate.
        """
        # This returns a signal string that the Orchestrator intercepts
        return f"SIGNAL_CALL_CRITIQUE: {concern} | Result: {step_result}"
