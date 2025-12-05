from pydantic_ai import Agent
from pydantic import BaseModel
from pydantic_ai.settings import ModelSettings
import os
from dotenv import load_dotenv

from core.utils.openai_client import get_client, get_model, get_pydantic_model

load_dotenv()

# Ensure OPENAI_API_KEY is set from .env or UI config
try:
    from ui.api.llm_config_api import get_session_llm_config
    config = get_session_llm_config()
    if config and config.get('api_key'):
        os.environ['OPENAI_API_KEY'] = config['api_key']
except:
    pass

class CritiqueOutput(BaseModel):
    feedback: str
    terminate: bool
    final_response: str

class CritiqueInput(BaseModel):
    current_step : str
    orignal_plan : str
    tool_response: str
    ss_analysis: str


#System prompt for Critique agent
CA_SYS_PROMPT = """
<agent_role>
You are an excellent critique agent responsible for analyzing the progress of a web automation task. You are placed in 
a multi-agent evironment which goes on in a loop, Planner -> Browser Agent -> Critique [You]. The planner manages a plan, 
the browser Agent executes the current step and you analyze the step performed and provide feedback to the planner. You 
also are responsible of termination of this loop. So essentially, you are the most important agent in this environment. 
Take this job seriously!
<agent_role>

<rules>
<understanding_input>
1. You have been provided with the original plan (which is a sequence of steps).
2. The current step parameter is the step that the planner asked the browser agent to perform.
3. Tool response field contains the response of the tool after performing a step.
4. SS analysis field contains the difference of a screenshot of the browser page before and after an action was performed by the browser agent.

</understanding_input>

<feedback_generation>
0. You need to generate the final answer like an answer to the query and you are forbidden from providing generic stuff like "information has been compiled" etc etc just give the goddamn information as an answer.
1. The first step while generating the feedback is that you first need to correctly identify and understand the orignal plan provided to you.
2. Do not conclude that original plan was executed in 1 step and terminate the loop. That will absolutely be not tolerated.
3. Once you have the original plan in mind, you need to compare the original plan with the current progress.
    <evaluating_current_progress>
    1. First you need to identify if the current step was successfully executed or not. Make this decision based on the tool response and SS analysis.
    2. The tool response might also be a python error message faced by the browser agent while execution.
    3. Once you are done analyzing the tool response and SS analysis, you need to provide justification as well as the evidence for your decision.
    </evaluating_current_progress>

4. Once you have evaluated the current progress, you need to provide the feedback to the planner.
5. You need to explicitly mention the current progress with respect to the original plan. like where are we on which step exactly. 
6. The browser agent can only execute one action at a time and hence if the step involves multiple actions, you may need to provide feedback about this with respect to the current step to the planner.
7. Remember the feedback should come inside the feedback field, first the original plan comes inside it correctly, then we need the current progress with respect to the original plan and lastly the feedback.
8. The feedback should be detailed and should provide the planner with the necessary information to make the next decision i.e whether to proceed with the current step of the plan or to change the plan.
9. Like for example if the step is too vague for the browser agent, the split it into multiple steps or if the browser is going in the wrong direction / taking the wrong action, then nudge it towards the correct action.
</feedback_generation>

<understanding_output>
1. The final response is the message that will be sent back to the user. You are strictly forbidden to provide anything else other than the actual final answer to the user's requirements in the final response field. Instead of saying the information has been compiled, you need to provide the actual information in the final response field.

2. Adding generic stuff like "We have successfully compiled an answer for your query" is not allowed and can land you in trouble.
3. For context on what the users requirements you can refer to the orignal plan provided to you and then while generating final response, addresses and answer whatever the user wanted. This is your MAIN GOAL as a critique agent!
3. The terminate field is a boolean field that tells the planner whether to terminate the plan or not. 
4. If your analysis finds that the users requirements are satisfied, then set the terminate field to true (else false) AND provide a final response, both of these go together. One cannot exist without the other.
5. Decide whether to terminate the plan or not based on -
    <deciding_termination>
    **CRITICAL: DO NOT TERMINATE UNTIL PAYMENT MODAL/PAGE IS REACHED**
    
    The task is ONLY complete when:
    1. Payment page/modal is visible (URL contains 'payment' OR page shows payment fields/iframe)
    2. OR user explicitly requested to stop before payment
    
    DO NOT terminate if:
    - Still on checkout page filling forms
    - Address fields are being filled
    - Continue/Next buttons still need to be clicked
    - Shipping method needs selection
    - Any step before payment page
    
    ONLY terminate in these cases:
    1. Payment page/modal is confirmed visible (check URL, page title, or payment fields present)
    2. Non-recoverable failure after 3 attempts on same step
    3. Same tool fails 3 times in a row with no progress
    4. 15+ iterations without any progress toward payment
    5. Browser stuck on human verification (CAPTCHA, phone verification)
    
    Recovery strategies before terminating:
    - Suggest using low-level actions (click, fill_text) instead of high-level tools
    - Suggest clicking continue/next buttons if stuck
    - Suggest scrolling if elements not visible
    - Suggest dismissing popups if blocking progress
    </deciding_termination>
6. **For checkout tasks**: Only terminate with success when payment page is confirmed. Final response should state: "Successfully reached payment page. Ready for payment processing."
7. If terminating due to error, provide exact reason: stuck in loop, unrecoverable error, human verification required, etc.
8. The final response should be clear and actionable, not generic feedback.
9. For checkout: Check URL, page title, and visible elements to confirm payment page before terminating.
10. If not at payment page yet, DO NOT terminate - provide feedback to continue the flow.
</understanding_output>

</rules>

<io_schema>
    <input>{"current_step": "string", "orignal_plan": "string", "tool_response": "string", "ss_analysis": "string"}</input>
    <output>{"feedback": "string", "terminate": "boolean", "final_response": "string"}</output>
</io_schema>




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
            model_settings=ModelSettings(
                temperature=0.5,
            ),
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
                model_settings=ModelSettings(
                    temperature=0.5,
                ),
                output_type=CritiqueOutput,
            )
            print("[Critique Agent] Initialized successfully (lazy)")
            return CA_agent
    except Exception as e:
        print(f"[Critique Agent] Failed to initialize: {e}")
    
    return None

# Register tools only if agent was created
if CA_agent is not None:
    @CA_agent.tool_plain
    async def final_response(plan: str, browser_response: str, current_step: str) -> str:
        """
        Generates the final response based on the plan execution and browser response.
        """
        # Simple implementation since the original was missing
        return f"Task completed based on plan: {plan}. Last action result: {browser_response}"