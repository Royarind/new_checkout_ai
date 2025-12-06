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
    """Ensure API key is set from UI config ONLY"""
    try:
        from ui.api.llm_config_api import get_session_llm_config
        config = get_session_llm_config()
        if config and config.get('api_key'):
            os.environ['OPENAI_API_KEY'] = config['api_key']
            print(f"[Planner Agent] Using API key from UI config")
            return True
    except Exception as e:
        print(f"[Planner Agent] Warning: Could not load API key from UI config: {e}")
    
    # Check if client can be created from UI config
    try:
        client = get_client()
        return client is not None
    except Exception:
        pass
    
    print(f"[Planner Agent] No API key configured in UI")
    return False

class PLANNER_AGENT_OP(BaseModel):
    plan_steps: List[str]


#System prompt for Planner
PA_SYS_PROMPT = """
<agent_role>
You are an expert e-commerce automation planner. Your goal is to create a DETAILED, ATOMIC, STEP-BY-STEP plan to complete a checkout task.
You will provided with a user request and you need to break it down into a linear sequence of simple steps that a Browser Agent can execute autonomously.
</agent_role>

<rules>
1. **ATOMIC STEPS**: Each step must be a single, simple action (e.g., "Navigate to URL", "Click 'Add to Cart'", "Fill email field").
2. **COMPLETE PLAN**: Generate the FULL plan from start to finish (payment page). Do not just give the first step.
3. **LOGICAL FLOW**: Steps must follow the logical flow of an e-commerce checkout:
   - Navigate to product
   - Select variants (if any)
   - Add to cart
   - Go to cart/checkout
   - Fill guest info (email first)
   - Fill address
   - Select shipping
   - Proceed to payment
4. **NO HALLUCINATION**: Do not invent steps for things that don't exist.
5. **VARIANT HANDLING**: If the user specifies variants (color, size, etc.), include specific steps to select them using the `select_variant` tool.
6. **GATE AWARENESS**: The system has "Gates" (Checkpoints) that verify progress. Your plan should naturally hit these gates:
   - Variant Selection
   - Cart Addition
   - Checkout Info (Email/Address)
   - Payment Page Reached
</rules>

<output_format>
You must return a list of strings, where each string is one step.
Example:
[
    "Navigate to https://example.com/product",
    "Select variant: size=M",
    "Select variant: color=Blue",
    "Click 'Add to Cart'",
    "Navigate to Cart",
    "Click Checkout",
    "Fill Email: user@example.com",
    "Fill Address: 123 Main St...",
    "Click Continue",
    "Select Standard Shipping",
    "Click Continue to Payment"
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