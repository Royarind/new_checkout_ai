"""Agent Orchestrator - Manages Planner→Browser→Critique loop"""
import asyncio
import logging
from typing import Dict, Any, List
from playwright.async_api import Page

from src.checkout_ai.agents.llm_factory import LLMFactory
from src.checkout_ai.agents.browser_agent import BrowserAgent, current_step_class
from src.checkout_ai.core.config import LoadConfig
from src.checkout_ai.utils.logger_config import setup_logger
from src.checkout_ai.agents.critique_agent import CritiqueInput
from src.checkout_ai.agents.unified_tools import set_page, set_customer_data
from src.checkout_ai.utils.country_detector import (
    detect_country_from_url, 
    get_country_config
)

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """Orchestrates the agent loop for ecommerce automation"""
    
    def __init__(self, page: Page, max_iterations: int = 20, customer_data: Dict = None):
        self.page = page
        self.max_iterations = max_iterations
        self.history = []
        self.customer_data = customer_data
        self.detected_country = None
        self.country_config = None
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
        
        # Detect country from URL (if available)
        url = None
        if customer_data and 'tasks' in customer_data:
            tasks = customer_data.get('tasks', [])
            if tasks and len(tasks) > 0:
                url = tasks[0].get('url')
        
        if url:
            self.detected_country = detect_country_from_url(url)
            if self.detected_country:
                self.country_config = get_country_config(self.detected_country)
                logger.info(f"🌍 Detected country: {self.detected_country} ({self.country_config['name']})")
                logger.info(f"   Postal code format: {self.country_config['postal_code_label']}")
                logger.info(f"   Currency: {self.country_config['currency_symbol']} ({self.country_config['currency_code']})")
            else:
                logger.info(f"⚠️  Could not detect country from URL: {url}, defaulting to US")
                self.detected_country = 'US'
                self.country_config = get_country_config('US')
        else:
            # No URL, use default
            logger.info("⚠️  No URL provided, using default country: US")
            self.detected_country = 'US'
            self.country_config = get_country_config('US')
        
        # Build query with country context
        query = task_description
        if customer_data:
            contact = customer_data.get('contact', {})
            addr = customer_data.get('shippingAddress', {})
            query += f"\n\nCustomer: {contact.get('firstName')} {contact.get('lastName')}, Email: {contact.get('email')}"
            query += f"\nAddress: {addr.get('addressLine1')}, {addr.get('city')}, {addr.get('province')} {addr.get('postalCode')}"
        
        # Add country context for planner
        if self.country_config:
            query += f"\n\n[COUNTRY CONTEXT]\n"
            query += f"Country: {self.country_config['name']} ({self.detected_country})\n"
            query += f"Postal Code Label: {self.country_config['postal_code_label']} (example: {self.country_config['postal_code_example']})\n"
            query += f"Phone Format: {self.country_config['phone_format']} (example: {self.country_config['phone_example']})\n"
            query += f"State Required: {'Yes' if self.country_config['state_required'] else 'No (optional)'}\n"
            query += f"Currency: {self.country_config['currency_symbol']} ({self.country_config['currency_code']})"

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
        from src.checkout_ai.agents.loop_detector import LoopDetector
        
        current_step_idx = 0
        max_retries = 3
        history = []
        loop_detector = LoopDetector(window_size=5, threshold=3)  # Detect after 3 failures
        
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
            logger.info(f"ORCHESTRATOR: ============================================")
            logger.info(f"ORCHESTRATOR: Executing Step {current_step_idx + 1}/{len(plan_steps)}")
            logger.info(f"ORCHESTRATOR: Step Text: '{step_text}'")
            logger.info(f"ORCHESTRATOR: ============================================")
            
            # Execute Step
            step_success = False
            for attempt in range(max_retries):
                try:
                    # Browser executes step
                    # We wrap the string in current_step_class deps
                    logger.info(f"ORCHESTRATOR: Passing to Browser Agent with context: current_step='{step_text}'")
                    result = await browser.run(step_text, deps=current_step_class(current_step=step_text))
                    result_str = str(result.output) # Browser returns string now
                    logger.info(f"ORCHESTRATOR: Browser Result: {result_str}")
                    
                    history.append({"step": step_text, "result": result_str})

                    # Handle Signals
                    if "SIGNAL_CALL_PLANNER" in result_str:
                        logger.info("ORCHESTRATOR: Browser requested Replanning")
                        
                        # Extract reason from signal
                        reason = result_str.replace("SIGNAL_CALL_PLANNER:", "").strip()
                        
                        # Build replan context
                        replan_context = f"""
                            Original task: {task_description}

                            Execution history (last 3 steps):
                            {history[-3:] if len(history) > 3 else history}

                            Current step failed: {step_text}
                            Reason: {reason}

                            Please generate a NEW complete plan starting from this point to complete the task.
                            """
                        
                        try:
                            logger.info("ORCHESTRATOR: Calling Planner for replan...")
                            replan_result = await planner.run(replan_context)
                            new_plan_steps = replan_result.output.plan_steps
                            
                            logger.info(f"ORCHESTRATOR: Replan generated {len(new_plan_steps)} steps")
                            
                            # Replace remaining steps with new plan
                            plan_steps = plan_steps[:current_step_idx] + new_plan_steps
                            logger.info(f"ORCHESTRATOR: Updated plan, total steps now: {len(plan_steps)}")
                            
                            # Continue from current position
                            continue
                            
                        except Exception as replan_err:
                            logger.error(f"ORCHESTRATOR: Replanning failed: {replan_err}")
                            raise Exception(f"Replanning failed: {replan_err}")
                        
                    # Track action for loop detection
                    tool_used = "browser_agent"  # Generic, could extract actual tool from result
                    action_success = "SUCCESS" in result_str.upper() or "✓" in result_str
                    loop_detector.add_action(tool_used, action_success, step_text)
                    
                    # Check if agent is stuck in a loop
                    if loop_detector.is_stuck():
                        logger.warning("🔴 ORCHESTRATOR: Agent stuck in loop, triggering replanning...")
                        
                        # Build replan context with loop info
                        loop_context = loop_detector.get_context()
                        replan_context = f"""
Original task: {task_description}

{loop_context}

Current step that keeps failing: {step_text}
Recent history:
{history[-3:] if len(history) > 3 else history}

The agent is stuck. Please generate a NEW plan to recover and complete the task.
Consider:
- Maybe the element isn't available or incorrectly identified
- Maybe we need to try a different approach
- Maybe we need to skip this step and try alternative navigation
"""
                        
                        try:
                            logger.info("ORCHESTRATOR: Calling Planner to recover from loop...")
                            replan_result = await planner.run(replan_context)
                            new_plan_steps = replan_result.output.plan_steps
                            
                            logger.info(f"ORCHESTRATOR: Recovery plan generated with {len(new_plan_steps)} steps")
                            
                            # Replace remaining steps with recovery plan
                            plan_steps = plan_steps[:current_step_idx] + new_plan_steps
                            logger.info(f"ORCHESTRATOR: Updated plan, total steps now: {len(plan_steps)}")
                            
                            # Reset loop detector
                            loop_detector.reset()
                            
                            # Try the new plan
                            break  # Exit retry loop, continue to next step
                            
                        except Exception as replan_err:
                            logger.error(f"ORCHESTRATOR: Recovery planning failed: {replan_err}")
                            # Continue normal flow
                    
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
                        
                        # Store advice to pass on retry
                        # Append advice to step_text so browser agent sees it
                        step_text_with_advice = f"{step_text}\n\n[ADVICE from Critique Agent]: {advice}"
                        
                        # Retry with advice-enhanced step
                        try:
                            result = await browser.run(step_text_with_advice, deps=current_step_class(current_step=step_text_with_advice))
                            result_str = str(result.output)
                            logger.info(f"ORCHESTRATOR: Browser Result (with advice): {result_str}")
                            
                            # Check if successful after advice
                            if "ERROR" not in result_str and "SIGNAL" not in result_str:
                                history.append({"step": step_text, "result": result_str, "with_advice": True})
                                step_success = True
                                break
                        except Exception as e:
                            logger.warning(f"ORCHESTRATOR: Retry with advice failed: {e}")
                        
                        continue # Try next attempt if advice didn't work

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
