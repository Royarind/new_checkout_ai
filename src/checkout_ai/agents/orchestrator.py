"""Agent Orchestrator - Manages Planner→Browser→Critique loop"""
import asyncio
import logging
from typing import Dict, Any, List
from playwright.async_api import Page

from src.checkout_ai.agents.llm_factory import LLMFactory
from src.checkout_ai.agents.tools import get_agent_tools
from src.checkout_ai.agents.browser_agent import BrowserAgent, current_step_class
from src.checkout_ai.core.config import LoadConfig
from src.checkout_ai.utils.logger_config import setup_logger
from src.checkout_ai.agents.critique_agent import CritiqueInput
from src.checkout_ai.agents.unified_tools import set_page, set_customer_data

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """Orchestrates the agent loop for ecommerce automation"""
    
    def __init__(self, page: Page, max_iterations: int = 20, customer_data: Dict = None):
        self.page = page
        self.max_iterations = max_iterations
        self.history = []
        self.customer_data = customer_data
        set_page(page)
        if customer_data:
            set_customer_data(customer_data)
    
    async def execute_task(self, task_description: str, customer_data: Dict = None) -> Dict[str, Any]:
        """
        Execute a task using the autonomous agent flow:
        1. Planner: Generates complete plan 
        2. Browser: Executes steps autonomously (calling helpers if stuck)
        3. Critique: Verifies critical gates
        """
        logger.info(f"ORCHESTRATOR: Starting task: {task_description}")
        
        # Ensure API key is loaded
        from src.checkout_ai.agents.planner_agent import _ensure_api_key, get_or_create_planner_agent
        from src.checkout_ai.agents.browser_agent import get_or_create_browser_agent, current_step_class
        from src.checkout_ai.agents.critique_agent import get_or_create_critique_agent, CritiqueInput
        
        if not _ensure_api_key():
            return {'success': False, 'error': "No API key configured.", 'iterations': 0, 'history': []}
        
        # Initialize agents
        planner = get_or_create_planner_agent()
        browser = get_or_create_browser_agent()
        critique = get_or_create_critique_agent()
        
        if not planner or not browser or not critique:
            return {'success': False, 'error': "Failed to initialize agents.", 'iterations': 0, 'history': []}
        
        # Build query
        query = task_description
        if customer_data:
            contact = customer_data.get('contact', {})
            addr = customer_data.get('shippingAddress', {})
            query += f"\n\nCustomer: {contact.get('firstName')} {contact.get('lastName')}, Email: {contact.get('email')}"
            query += f"\nAddress: {addr.get('addressLine1')}, {addr.get('city')}, {addr.get('province')} {addr.get('postalCode')}"

        # --- STEP 1: PLANNING ---
        logger.info("ORCHESTRATOR: Generating initial plan...")
        try:
            # Planner input is simple string for robustness
            plan_result = await planner.run(query) 
            # Parse plan: explicitly expect list of strings
            plan_steps = plan_result.output.plan_steps
            logger.info(f"ORCHESTRATOR: Generated {len(plan_steps)} steps: {plan_steps}")
        except Exception as e:
            msg = f"Planning failed: {str(e)}"
            logger.error(msg)
            return {'success': False, 'error': msg, 'iterations': 0}

        # --- STEP 2: EXECUTION LOOP ---
        current_step_idx = 0
        max_retries = 3
        history = []
        
        # Gate Definitions
        GATES = {
            "Select variant": "variant_selection",
            "Add to Cart": "cart_addition",
            "Fill Email": "checkout_info",
            "Fill Address": "checkout_info",
            "Payment": "payment_info"
        }

        while current_step_idx < len(plan_steps):
            step_text = plan_steps[current_step_idx]
            logger.info(f"ORCHESTRATOR: Executing Step {current_step_idx + 1}/{len(plan_steps)}: {step_text}")
            
            # Execute Step
            step_success = False
            for attempt in range(max_retries):
                try:
                    # Browser executes step
                    # We wrap the string in current_step_class deps
                    result = await browser.run(step_text, deps=current_step_class(current_step=step_text))
                    result_str = str(result.output) # Browser returns string now
                    logger.info(f"ORCHESTRATOR: Browser Result: {result_str}")
                    
                    history.append({"step": step_text, "result": result_str})

                    # Handle Signals
                    if "SIGNAL_CALL_PLANNER" in result_str:
                        logger.info("ORCHESTRATOR: Browser requested Replanning")
                        # Call Planner logic here (simplified for robustness: just log/retry)
                        # Ideally: new_plan = await planner.run(f"Replan: {result_str}")
                        # For now, we'll treat as error
                        raise Exception(f"Replanning requested: {result_str}")
                        
                    elif "SIGNAL_CALL_CRITIQUE" in result_str:
                        logger.info("ORCHESTRATOR: Browser requested Assistance")
                        # Call Critique for Assistance
                        c_input = CritiqueInput(
                            request_type="ASSISTANCE", 
                            current_step=step_text, 
                            action_result=result_str
                        )
                        c_res = await critique.run(c_input)
                        advice = c_res.output.feedback
                        logger.info(f"ORCHESTRATOR: Critique Advice: {advice}")
                        # Retry step with advice attached? Or just retry
                        continue # Retry loop

                    elif "ERROR" in result_str:
                         logger.warning(f"ORCHESTRATOR: Step failed (attempt {attempt+1}): {result_str}")
                         continue # Retry loop
                    
                    else:
                        # SUCCESS case
                        step_success = True
                        break # Exit retry loop

                except Exception as e:
                    logger.warning(f"ORCHESTRATOR: Execution error: {e}")
                    await asyncio.sleep(2)
            
            if not step_success:
                return {'success': False, 'error': f"Failed step: {step_text}", 'history': history}

            # --- STEP 3: GATE VERIFICATION ---
            # Check if this step corresponds to a Gate
            current_gate = None
            for key, gate_name in GATES.items():
                if key.lower() in step_text.lower():
                    current_gate = gate_name
                    break
            
            if current_gate:
                logger.info(f"ORCHESTRATOR: Verifying Gate: {current_gate}")
                c_input = CritiqueInput(
                    request_type="VERIFICATION",
                    current_step=step_text,
                    action_result=result_str, # Provide last result
                    gate_name=current_gate
                )
                try:
                    c_res = await critique.run(c_input)
                    if c_res.output.approved:
                        logger.info(f"ORCHESTRATOR: Gate {current_gate} PASSED")
                    else:
                        logger.warning(f"ORCHESTRATOR: Gate {current_gate} FAILED: {c_res.output.feedback}")
                        # Gate failed - could trigger replan or retry. For now, fail safe.
                        # In robust version: retry step
                        return {'success': False, 'error': f"Gate Failed: {current_gate} - {c_res.output.feedback}", 'history': history}
                    
                    if c_res.output.terminate:
                        logger.info("ORCHESTRATOR: Critique signaled Task Completion (Success)")
                        return {'success': True, 'message': c_res.output.final_response, 'history': history}

                except Exception as e:
                    logger.error(f"Gate verification error: {e}")
            
            # Move to next step
            current_step_idx += 1
            await asyncio.sleep(1)

        return {'success': True, 'message': "All steps executed", 'history': history}
