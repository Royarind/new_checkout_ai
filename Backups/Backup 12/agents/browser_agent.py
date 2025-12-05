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
You are a web automation agent in a Planner→Browser→Critique loop. Execute ONE tool per iteration.
</agent_role>

<available_tools>
HIGH-LEVEL TOOLS (use these first):
- select_variant(variant_type, variant_value) - Select product options
- add_to_cart() - Add to cart
- navigate_to_cart() - Go to cart
- fill_email(email) - Fill email field
- fill_contact(first_name, last_name, phone) - Fill contact info
- fill_address(address, city, state, zip_code) - Fill address
- click_checkout() - Click checkout button
- click_guest_checkout() - Click guest checkout
- click_continue() - Click continue/next
- dismiss_popups() - Close popups
- take_screenshot(path) - Capture screen
- validate_page() - Get page state
- web_search(query) - Search web

LOW-LEVEL ACTIONS (use when high-level fails):
- click(selector/text/x,y) - Click element
- fill_text(selector/label, text_content) - Fill input
- select_dropdown(selector/label, value) - Select option
- scroll(direction, pixels) - Scroll page
- press_key(key) - Press key
- wait(seconds) - Wait
- navigate(url) - Go to URL
</available_tools>

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


# Register all tools dynamically
for tool_name, tool_func in TOOLS.items():
    @BA_agent.tool_plain
    async def tool_wrapper(**kwargs) -> str:
        result = await execute_tool(tool_name, **kwargs)
        return str(result)
    
    # Set proper name and docstring
    tool_wrapper.__name__ = tool_name
    tool_wrapper.__doc__ = f"Execute {tool_name} tool"

