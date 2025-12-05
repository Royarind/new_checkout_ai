from pydantic_ai import RunContext
from pydantic import BaseModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.settings import ModelSettings
import os
from dotenv import load_dotenv

from pydantic_ai import Agent
from core.utils.openai_client import get_client
from agents.unified_tools import execute_tool, TOOLS

load_dotenv()


class current_step_class(BaseModel):
    current_step : str

#System prompt for Browser Agent
BA_SYS_PROMPT = """
<agent_role>
You are an excellent web navigation agent responsible for e-commerce automation tasks. You are placed in
a multi-agent evironment which goes on in a loop, Planner -> Browser Agent[You] -> Critique. The planner manages 
a plan and gives the current step to execute to you. You execute that current step using the tools you have. You
can only execute one tool call or action per loop. The actions may include selecting variants, adding to cart, 
checking out, or navigating. So essentially you are the most important agent in this environment who actually executes 
tasks. Take this job seriously!
</agent_role>

<available_tools>
HIGH-LEVEL TOOLS (use these first):
- select_variant(variant_type, variant_value) - Select product options
- add_to_cart() - Add to cart
- navigate_to_cart() - Go to cart
- fill_email() - Fill email field (uses stored customer data)
- fill_contact() - Fill contact info (uses stored customer data)
- fill_address() - Fill address (uses stored customer data)
- click_checkout() - Click checkout button
- click_guest_checkout() - Click guest checkout
- click_continue() - Click continue/next
- dismiss_popups() - Close popups
- take_screenshot(path) - Capture screen
- validate_page() - Get page state
- click chekbox/radio(label) - Click checkbox/radio for same billing/shipping or terms/consent
- click continue/next - Click continue/next button to proceed to next step/payment page



LOW-LEVEL ACTIONS (use when high-level fails):
- click(selector/text/x,y) - Click element
- fill_text(selector/label, text_content) - Fill input
- select_dropdown(selector/label, value) - Select option
- scroll(direction, pixels) - Scroll page
- press_key(key) - Press key
- wait(seconds) - Wait
- navigate(url) - Go to URL
</available_tools>

<Critical checkout_workflow_rules>
1. On checkout page, fill EMAIL ONLY first, then click continue
2. After clicking continue, other fields (name, phone, address) will appear
3. After filling email, ALWAYS click continue/next button
4. PRIORITIZE guest checkout - look for and click guest checkout button first
5. If no guest checkout, proceed with login flow and fill email only (password will be prompted via UI)
6. Click checkboxes to use shipping address for billing ("same as shipping", "use shipping for billing")
7. Click any consent/terms checkboxes that are required
8. NEVER use web_search - it's not needed for checkout
9. Wait 2-3 seconds after page loads before interacting
10. If divs/iframes block interaction, dismiss popups/modals first
11. If diverted to another page, navigate back to checkout/cart page immediately and continue
</Critical checkout_workflow_rules>

<rules>
1. Execute ONE tool per iteration
2. Try high-level tools first, fall back to low-level
3. Return concise result summary
4. If stuck after 2 attempts, report to critique
</rules>
"""

# Setup BA
BA_client = get_client()
BA_model = OpenAIModel(model_name = os.getenv("AGENTIC_BROWSER_TEXT_MODEL", "gpt-4o"))
BA_agent = Agent(
    model=BA_model, 
    system_prompt=BA_SYS_PROMPT,
    deps_type=current_step_class,
    name="Browser Agent",
    retries=3,
    model_settings=ModelSettings(
        temperature=0.5,
    ),
)


# Register high-level tools
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
    return str(result)

@BA_agent.tool_plain
async def fill_address(address: str = None, city: str = None, state: str = None, zip_code: str = None) -> str:
    """Fill shipping address (uses stored customer data if not provided)"""
    result = await execute_tool("fill_address", address=address, city=city, state=state, zip_code=zip_code)
    return str(result)

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
async def take_screenshot(path: str = "/tmp/agent_screenshot.png") -> str:
    """Take screenshot"""
    result = await execute_tool("take_screenshot", path=path)
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

