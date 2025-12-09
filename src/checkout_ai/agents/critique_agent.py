from pydantic_ai import Agent
from pydantic import BaseModel
from pydantic_ai.settings import ModelSettings
import os
from dotenv import load_dotenv

from src.checkout_ai.core.utils.openai_client import get_client, get_model, get_pydantic_model

load_dotenv()

# API key loaded from backend config (reads .env)
try:
    from backend.api.llm_config_api import get_session_llm_config
    config = get_session_llm_config()
    if config and config.get('api_key'):
        os.environ['OPENAI_API_KEY'] = config['api_key']
except:
    pass

class CritiqueOutput(BaseModel):
    feedback: str
    approved: bool # For gate verification: True if passed, False if rejected
    terminate: bool # True only for fatal errors or final success
    final_response: str

class CritiqueInput(BaseModel):
    request_type: str # "VERIFICATION" or "ASSISTANCE"
    current_step: str
    action_result: str
    gate_name: str = None

#System prompt for Critique agent
CA_SYS_PROMPT = """
<agent_role>
You are an expert quality assurance and assistance agent for e-commerce automation.
You have two distinct roles:
1. **GATE KEEPER ("VERIFICATION")**: You verify if a critical milestone (Gate) has been successfully reached.
2. **HELPER ("ASSISTANCE")**: You provide guidance when the Browser Agent is stuck or unsure.
</agent_role>

<rules>
**IF request_type is "VERIFICATION"**:
- You are checking a "Gate" (e.g., "cart_addition", "payment_info").
- Analyze the `action_result` to see if the criteria for the gate are met.
- If met, set `approved=True`.
- If NOT met, set `approved=False` and provide specific `feedback` on what is missing.
- **CRITICAL**: For the FINAL Gate (Order Verification), if successful, set `terminate=True` and put the final summary in `final_response`.

**IF request_type is "ASSISTANCE"**:
- The Browser Agent is stuck or encountered an error.
- Analyze the `action_result` (which contains the error or state).
- Provide clear, actionable steps in `feedback` to fix the issue.
- Set `approved=False` (since this isn't a gate check).
- Only set `terminate=True` if the error is completely unrecoverable.
</rules>

<gates_criteria>
- **variant_selection**: All required variants (size, color, etc.) are selected.
- **cart_addition**: Item is in cart, cart count updated.
- **checkout_info**: Email and Address fields are filled.
- **payment_info**: Payment page is reached (URL contains 'payment' or fields visible).
</gates_criteria>

<critical_rules>
**CRITICAL JSON FORMATTING**: 
1. When generating output, avoid complex nested strings with escape sequences. Keep strings simple and avoid newlines in JSON values. If you need to include multiple points, use spaces instead of newlines.
2. **BOOLEAN VALUES**: The "terminate" and "approved" fields MUST be booleans (true/false), NOT strings.
</critical_rules>
"""

# Setup CA - model from UI config ONLY
# Allow import to succeed even if no model configured yet
CA_agent = None
try:
    CA_model = get_pydantic_model()
    
    # Only create agent if we have a model
    if CA_model:
        CA_agent = Agent(
            model=CA_model, 
            name="Critique Agent",
            system_prompt=CA_SYS_PROMPT,
            retries=3,
            model_settings={'temperature': 0.5},
            output_type=CritiqueOutput,
        )
        print("[Critique Agent] Initialized successfully")
    else:
        print("[Critique Agent] Skipping initialization - no model configured yet")
except Exception as e:
    print(f"[Critique Agent] Could not initialize at import time: {e}")
    print("[Critique Agent] Agent will be initialized when model is configured")

def get_or_create_critique_agent():
    """Get existing agent or create new one if model is now available"""
    global CA_agent
    
    if CA_agent is not None:
        return CA_agent
    
    # Try to create agent now that model might be available
    try:
        CA_model = get_pydantic_model()
        
        if CA_model:
            CA_agent = Agent(
                model=CA_model, 
                name="Critique Agent",
                system_prompt=CA_SYS_PROMPT,
                retries=3,
                model_settings={'temperature': 0.5},
                output_type=CritiqueOutput,
            )
            print("[Critique Agent] Initialized successfully (lazy)")
            return CA_agent
    except Exception as e:
        print(f"[Critique Agent] Failed to initialize: {e}")
    return None

# Note: Removed final_response tool as it was causing JSON formatting issues with Groq
# The CritiqueOutput model already includes final_response as a field