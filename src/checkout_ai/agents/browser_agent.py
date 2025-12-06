from pydantic_ai import RunContext
from src.checkout_ai.dom.service import UniversalDOMFinder
import json
import os
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

# Ensure OPENAI_API_KEY is set from .env or UI config
try:
    from ui.api.llm_config_api import get_session_llm_config
    config = get_session_llm_config()
    if config and config.get('api_key'):
        os.environ['OPENAI_API_KEY'] = config['api_key']
except:
    pass


class current_step_class(BaseModel):
    current_step : str

#System prompt for Browser Agent
BA_SYS_PROMPT = """
<agent_role>
You are an intelligent autonomous browser agent. You receive a specific step to execute from a larger plan. 
Your goal is to execute this step successfully using your tools.
</agent_role>

<execution_protocol>
1. **Analyze the Step**: Understand what needs to be done (e.g., "Select variant size=M").
2. **Check Page State**: Use `validate_page` to see if you are on the right page and if elements are visible.
3. **Select Tool**: Choose the most appropriate tool.
   - For checkout forms, use high-level tools like `fill_contact` or `fill_address`.
   - For variants, use `select_variant` (supports any type: color, size, storage, flavor, etc.).
   - For navigation, use `navigate`.
4. **Execute**: Run the tool.
5. **Verify**: Check if the action worked.
</execution_protocol>

<communication_tools>
If you are stuck or need help, use these special tools instead of failing:
- `call_planner(reason, current_state)`: Use this if:
  - You are lost ("I don't know where I am")
  - The current step text doesn't make sense
  - You need the plan to be changed
- `call_critique(concern, step_result)`: Use this if:
  - You are unsure if an action was correct
  - You encountered an error and want advice on how to fix it
  - You hit a critical "Gate" (like Payment Page) and need verification
</communication_tools>

<outputs>
Your tool calls will be executed by the system.
Return a simple confirmation string if successful, formatted as: "SUCCESS: [details]"
If failed, return: "ERROR: [details]"
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
    @BA_agent.tool_plain
    async def select_variant(variant_type: str, variant_value: str) -> str:
        """Select product variant"""
        result = await execute_tool("select_variant", variant_type=variant_type, variant_value=variant_value)
        return str(result)

    @BA_agent.tool_plain
    async def add_to_cart() -> str:
        """Add product to cart"""
        result = await execute_tool("add_to_cart")
        return str(result)

    @BA_agent.tool_plain
    async def navigate_to_cart() -> str:
        """Navigate to cart page"""
        result = await execute_tool("navigate_to_cart")
        return str(result)

    @BA_agent.tool_plain
    async def fill_email(email: str = None) -> str:
        """Fill email field (uses stored customer data if email not provided)"""
        result = await execute_tool("fill_email", email=email)
        return str(result)

    @BA_agent.tool_plain
    async def fill_contact(first_name: str = None, last_name: str = None, phone: str = None) -> str:
        """Fill contact information (uses stored customer data if not provided)"""
        result = await execute_tool("fill_contact", first_name=first_name, last_name=last_name, phone=phone)
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
        """Fill contact fields then click Continue if present.
        If the Continue button is not found, the function still returns the contact‑fill result.
        """
        # Fill the contact information first
        contact_res = await execute_tool("fill_contact", first_name=first_name, last_name=last_name, phone=phone)
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
    async def fill_address(address: str = None, city: str = None, state: str = None, zip_code: str = None) -> str:
        """Fill shipping address (uses stored customer data if not provided)"""
        result = await execute_tool("fill_address", address=address, city=city, state=state, zip_code=zip_code)
        # Auto‑click Continue if it appears after filling address fields
        try:
            cont_res = await execute_tool("click_continue")
            if cont_res.get("success"):
                return f"{result} | continue_clicked"
        except Exception:
            pass
        return str(result)

    @BA_agent.tool_plain
    async def fill_address_and_continue(address: str = None, city: str = None, state: str = None, zip_code: str = None) -> str:
        """Fill address fields then click Continue if present.
        If Continue button is missing, attempts to click payment button.
        """
        addr_res = await execute_tool("fill_address", address=address, city=city, state=state, zip_code=zip_code)
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
