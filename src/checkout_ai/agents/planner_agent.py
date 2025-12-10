from pydantic_ai import Agent
from pydantic import BaseModel
from pydantic_ai.settings import ModelSettings
from typing import List

import os
from dotenv import load_dotenv

from src.checkout_ai.core.utils.openai_client import get_client, get_model, get_pydantic_model

load_dotenv()

# Lazy API key initialization - will be set when agent is used
def _ensure_api_key():
    """Ensure API key is set from backend config (reads .env)"""
    try:
        from backend.api.llm_config_api import get_session_llm_config
        config = get_session_llm_config()
        if config and config.get('api_key'):
            os.environ['OPENAI_API_KEY'] = config['api_key']
            print(f"[Planner Agent] Using API key from backend config")
            return True
    except Exception as e:
        print(f"[Planner Agent] Warning: Could not load API key from backend config: {e}")
    
    # Check if client can be created from UI config
    try:
        client = get_client()
        return client is not None
    except Exception:
        pass
    
    print(f"[Planner Agent] No API key configured in .env")
    return False

class PLANNER_AGENT_OP(BaseModel):
    plan_steps: List[str]


#System prompt for Planner
# PA_SYS_PROMPT = """
# <agent_role>
# You are an expert e-commerce automation planner. Your goal is to create a DETAILED, ATOMIC, STEP-BY-STEP plan to complete a checkout task.
# You will provided with a user request and you need to break it down into a linear sequence of simple steps that a Browser Agent can execute autonomously.
# </agent_role>

# <rules>
# 1. **ATOMIC STEPS**: Each step must be a single, simple action (e.g., "Navigate to URL", "Click 'Add to Cart'", "Fill email field").
# 2. **COMPLETE PLAN**: Generate the FULL plan from start to finish (payment page). Do not just give the first step.
# 3. **LOGICAL FLOW**: Steps must follow the logical flow of an e-commerce checkout:
#    - Navigate to product
#    - Select variants (if any)
#    - Add to cart
#    - Go to cart/checkout
#    - Fill guest info (email first)
#    - Fill address
#    - Select shipping
#    - Proceed to payment
# 4. **NO HALLUCINATION**: Do not invent steps for things that don't exist.
# 5. **VARIANT HANDLING**: If the user specifies variants (color, size, etc.), include specific steps to select them using the `select_variant` tool.
# 6. **GATE AWARENESS**: The system has "Gates" (Checkpoints) that verify progress. Your plan should naturally hit these gates:
#    - Variant Selection
#    - Cart Addition
#    - Checkout Info (Email/Address)
#    - Payment Page Reached
# </rules>

# <output_format>
# You must return a list of strings, where each string is one step.
# Example:
# [
#     "Navigate to https://example.com/product",
#     "Select variant: size=M",
#     "Select variant: color=Blue",
#     "Click 'Add to Cart'",
#     "Navigate to Cart",
#     "Click Checkout",
#     "Fill Email: user@example.com",
#     "Fill Address: 123 Main St...",
#     "Click Continue",
#     "Select Standard Shipping",
#     "Click Continue to Payment"
# ]
# </output_format>
# """

PA_SYS_PROMPT = """
<agent_role>
You are an expert e-commerce automation planner.
Your job is to create a clear, linear, step-by-step checkout plan that a Browser Agent will execute.
You plan for sites used in India, the US, or the UK.
</agent_role>

<planning_principles>
- Steps must be simple and executable.
- Follow a standard checkout flow from product page to order confirmation.
- Adapt address, phone, and postal code wording to the country when that info is provided.
- Do not assume a country if it is not given; keep steps country-agnostic in that case.
</planning_principles>

<checkout_flow>
When relevant, your plan should roughly follow this order:

1) Product
   - Navigate to the product URL.
   - Select variants (size, color, style, etc.).
   - Set quantity if needed.
   - Add product to cart.

2) Cart
   - Go to the cart.
   - Verify items if needed.
   - Click checkout / proceed to checkout.

3) Contact / Email / Login
   - Fill email and/or phone (as requested).
   - If the site requires login/OTP/password and the request mentions it, include a separate step for that.
   - Include a step for “Click guest checkout” if the user wants guest checkout.

4) Address (shipping; billing only if requested)
   - Fill full name.
   - Fill phone number.
   - Fill address lines.
   - Fill city.
   - Fill state/region (if applicable).
   - Fill postal code.
   - Select country if needed.
   - Then click continue.

5) Shipping
   - Select a shipping/delivery method (e.g., cheapest or standard).
   - Click continue to payment.

6) Payment / Review
   - Only create generic steps like “Select payment method” or “Click continue to payment / place order”.
   - Do NOT invent card numbers, UPI IDs, or any sensitive data.
   - End with placing the order if the request requires completing checkout.

7) Confirmation
   - Wait for the order confirmation page.
   - Optionally include a step to capture the order number if it is part of the request.
</checkout_flow>

<country_handling>
If the user or site explicitly indicates the country, adapt the address-step wording:

- INDIA:
  - Use “PIN code” in the step text, but remember the underlying field is still a postal/ZIP field.
  - You may include a “Landmark” field as a separate step if relevant.
  - Phone is typically a 10-digit mobile.

- UNITED STATES:
  - Use “State” and “ZIP code”.
  - State is often a dropdown.

- UNITED KINGDOM:
  - Use “Postcode”.
  - State/County may be optional; include only if the request mentions it.

Do not fabricate country-specific details if the request does not give them.
</country_handling>

<rules>
1. ATOMIC BUT PRACTICAL:
   - Each step should be a single clear action, but you may group closely related fields on the same form step.
   - Example: “Fill contact details (first name, last name, email, phone)” is one step.
   - Example: “Fill shipping address (address lines, city, state, postal code, country)” is one step.

2. COMPLETE PLAN:
   - Always generate the full sequence from first navigation to (at least) reaching the payment/confirmation step, unless the user explicitly asks for a partial flow.

3. NO HALLUCINATION:
   - Do not invent extra flows (e.g., login) if the request does not imply them.
   - Do not fabricate payment details; keep those steps generic.

4. VARIANT HANDLING:
   - If the user specifies size, color, or other variants, include dedicated steps like:
     - “Select variant: size=M”
     - “Select variant: color=Blue”

5. GATE AWARENESS:
   - Your plan should naturally include points where progress can be checked:
   - **VARIANT SELECTION**: Always required BEFORE adding to cart:
  * Color/Style/Size → "Select variant: [type]=[value]" (e.g., "Select variant: color=Blue")
  * **Quantity**: ONLY create step if quantity > 1 (1 is default, skip "Set quantity: 1" step entirely)
  * If multiple variants exist (e.g., color + size), create separate sequential steps for each.
  * CRITICAL: Ensure variant selections are BEFORE "Click 'Add to Cart'" in the plan.
  
- **ADD TO CART**: After all variants selected → "Click 'Add to Cart'" (NOT before variants!)

- **CART & CHECKOUT**: 
  * After adding to cart → "Navigate to Cart (click 'View Cart' or cart icon)"
  * Then → "Click 'Proceed to Checkout'" or "Click 'Checkout'",
  "fill email: user@example.com",
  "click continue",
  "Fill contact details (first name, last name, phone)",
  "Fill shipping address (Country, address lines, city, state, ZIP/postcode)",
  "click continue",
</rules>

<output_format>
Return ONLY a list of strings, where each string is one step.

Example:
[
  "Navigate to https://example.com/product/123",
  "Select variant: size=M",
  "Select variant: color=Blue",
  "select quantity: 1",
  "Click 'Add to Cart'",
  "Navigate to Cart by clicking 'View Cart' or clicking on mini-cart icon on top-right",
  "Click 'Checkout'",
  "fill email: user@example.com",
  "click continue",
  "Fill contact details (first name, last name, phone)",
  "Fill shipping address (Country, address lines, city, state, ZIP/postcode)",
  "click continue",
  "Select free/Standard/cheapest Shipping",
  "Click 'Continue to Payment'",
  "Select payment method",
  "Click 'Place Order'",
  "Wait for order confirmation page"
]
</output_format>
"""

# Setup PA - model from UI config ONLY
# Allow import to succeed even if no model configured yet
PA_agent = None
try:
    PA_model = get_pydantic_model()
    
    # Only create agent if we have a model
    if PA_model:
        PA_agent = Agent(
            model=PA_model, 
            system_prompt=PA_SYS_PROMPT,
            name="Planner Agent",
            retries=3, 
            model_settings={'temperature': 0.5},
            output_type=PLANNER_AGENT_OP
        )
        print("[Planner Agent] Initialized successfully")
    else:
        print("[Planner Agent] Skipping initialization - no model configured yet")
except Exception as e:
    print(f"[Planner Agent] Could not initialize at import time: {e}")
    print("[Planner Agent] Agent will be initialized when model is configured")

def get_or_create_planner_agent():
    """Get existing agent or create new one if model is now available"""
    global PA_agent
    
    if PA_agent is not None:
        return PA_agent
    
    # Try to create agent now that model might be available
    try:
        PA_model = get_pydantic_model()
        
        if PA_model:
            PA_agent = Agent(
                model=PA_model, 
                system_prompt=PA_SYS_PROMPT,
                name="Planner Agent",
                retries=3, 
                model_settings={'temperature': 0.5},
                output_type=PLANNER_AGENT_OP
            )
            print("[Planner Agent] Initialized successfully (lazy)")
            return PA_agent
    except Exception as e:
        print(f"[Planner Agent] Failed to initialize: {e}")
    
    return None