"""Agent Orchestrator - Manages Planner→Browser→Critique loop"""
import asyncio
import logging
from typing import Dict, Any, List
from playwright.async_api import Page

from agents.planner_agent import PA_agent, PLANNER_AGENT_OP
from agents.browser_agent import BA_agent, current_step_class
from agents.critique_agent import CA_agent, CritiqueInput
from agents.unified_tools import set_page, set_customer_data

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
        Execute a task using agent loop
        
        Args:
            task_description: Natural language task description
            customer_data: Optional customer data for checkout
        
        Returns:
            Dict with success status and results
        """
        logger.info(f"ORCHESTRATOR: Starting task: {task_description}")
        
        # Ensure API key is loaded before running agents
        from agents.planner_agent import _ensure_api_key, get_or_create_planner_agent
        from agents.browser_agent import get_or_create_browser_agent
        from agents.critique_agent import get_or_create_critique_agent
        
        if not _ensure_api_key():
            error_msg = "No API key configured. Please configure your LLM API key in Settings."
            logger.error(f"ORCHESTRATOR: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'iterations': 0,
                'history': []
            }
        
        # Get or create agents (they might be None if no API key was available at import)
        planner = get_or_create_planner_agent()
        browser = get_or_create_browser_agent()
        critique = get_or_create_critique_agent()
        
        if not planner or not browser or not critique:
            error_msg = "Failed to initialize agents. Please check your API key configuration."
            logger.error(f"ORCHESTRATOR: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'iterations': 0,
                'history': []
            }
        
        # Build query with customer data if provided
        query = task_description
        if customer_data:
            contact = customer_data.get('contact', {})
            address = customer_data.get('shippingAddress', {})
            query += f"\n\nCustomer: {contact.get('firstName')} {contact.get('lastName')}"
            query += f"\nEmail: {contact.get('email')}"
            query += f"\nAddress: {address.get('addressLine1')}, {address.get('city')}, {address.get('province')} {address.get('postalCode')}"
        
        current_plan = None
        feedback = None
        
        for iteration in range(self.max_iterations):
            logger.info(f"ORCHESTRATOR: Iteration {iteration + 1}/{self.max_iterations}")
            
            try:
                # Retry helper
                async def run_agent_with_retry(agent, input_data, agent_name):
                    for attempt in range(3):
                        try:
                            return await agent.run(input_data)
                        except Exception as e:
                            error_msg = f"{type(e).__name__}: {str(e)}"
                            if "validation error" in str(e).lower() or "rate limit" in str(e).lower():
                                logger.warning(f"ORCHESTRATOR: {agent_name} failed (attempt {attempt+1}/3): {error_msg}. Retrying...")
                                await asyncio.sleep(2)
                                continue
                            logger.error(f"ORCHESTRATOR: {agent_name} failed with non-retryable error: {error_msg}")
                            raise e
                    raise Exception(f"{agent_name} failed after 3 attempts")

                # 1. Planner Agent
                logger.info("ORCHESTRATOR: Calling Planner...")
                pa_input = {
                    "query": query,
                    "og_plan": current_plan,
                    "feedback": feedback
                }
                pa_result = await run_agent_with_retry(planner, str(pa_input), "Planner")
                plan_data = pa_result.output
                
                current_plan = plan_data.plan
                next_step = plan_data.next_step
                logger.info(f"ORCHESTRATOR: Next step: {next_step}")
                
                # 2. Browser Agent
                logger.info("ORCHESTRATOR: Calling Browser Agent...")
                ba_deps = current_step_class(current_step=next_step)
                # Browser agent needs deps, so we can't use the simple helper directly without modification
                # But browser agent usually doesn't fail with validation error as much as Planner/Critique
                # Let's wrap it manually
                for attempt in range(3):
                    try:
                        ba_result = await browser.run(next_step, deps=ba_deps)
                        break
                    except Exception as e:
                        if "validation error" in str(e).lower() or "rate limit" in str(e).lower():
                            logger.warning(f"ORCHESTRATOR: Browser Agent failed (attempt {attempt+1}/3): {e}. Retrying...")
                            await asyncio.sleep(2)
                            continue
                        raise e
                
                tool_response = str(ba_result.output)
                logger.info(f"ORCHESTRATOR: Tool response: {tool_response[:200]}")
                
                # 3. Critique Agent
                logger.info("ORCHESTRATOR: Calling Critique...")
                ca_input = str(CritiqueInput(
                    current_step=next_step,
                    orignal_plan=current_plan,
                    tool_response=tool_response,
                    ss_analysis="Screenshot analysis not implemented"
                ))
                ca_result = await run_agent_with_retry(critique, ca_input, "Critique")
                critique_data = ca_result.output
                
                feedback = critique_data.feedback
                logger.info(f"ORCHESTRATOR: Feedback: {feedback[:200]}")
                
                # Store history
                self.history.append({
                    'iteration': iteration + 1,
                    'step': next_step,
                    'tool_response': tool_response,
                    'feedback': feedback,
                    'terminate': critique_data.terminate
                })
                
                # Check termination
                if critique_data.terminate:
                    logger.info(f"ORCHESTRATOR: Terminating - {critique_data.final_response}")
                    
                    # Check if payment page was reached
                    current_url = self.page.url.lower()
                    payment_reached = 'payment' in current_url or 'billing' in current_url
                    
                    return {
                        'success': payment_reached,
                        'message': critique_data.final_response,
                        'iterations': iteration + 1,
                        'payment_page_reached': payment_reached,
                        'final_url': self.page.url,
                        'history': self.history
                    }
                
                # Small delay between iterations
                await asyncio.sleep(1)
                
            except Exception as e:
                import traceback
                error_details = f"{type(e).__name__}: {str(e)}"
                logger.error(f"ORCHESTRATOR: Error in iteration {iteration + 1}: {error_details}")
                logger.error(f"ORCHESTRATOR: Traceback: {traceback.format_exc()}")
                return {
                    'success': False,
                    'error': error_details if str(e) else type(e).__name__,
                    'iterations': iteration + 1,
                    'history': self.history
                }
        
        # Max iterations reached
        logger.warning(f"ORCHESTRATOR: Max iterations ({self.max_iterations}) reached")
        return {
            'success': False,
            'error': 'Max iterations reached',
            'iterations': self.max_iterations,
            'history': self.history
        }
    
    async def execute_checkout_flow(self, product_url: str, variants: Dict, customer_data: Dict) -> Dict[str, Any]:
        """
        Execute complete checkout flow
        
        Args:
            product_url: Product URL
            variants: Product variants (color, size, etc.)
            customer_data: Customer information
        
        Returns:
            Dict with success status
        """
        # Build task description
        variant_str = ", ".join([f"{k}={v}" for k, v in variants.items()])
        task = f"""Complete checkout for product at {product_url} and reach PAYMENT PAGE.

**CRITICAL**: Task is ONLY complete when payment page/modal is visible.
        
Required Steps:
1. Navigate to {product_url}
2. Select variants: {variant_str}
3. Add to cart
4. Navigate to cart
5. Click checkout
6. Fill email: {customer_data['contact']['email']}
7. Click continue (after email)
8. Fill contact info (first name, last name, phone)
9. Fill shipping address (all fields)
10. Click continue (after address)
11. Select shipping method
12. Click continue to payment
13. **VERIFY payment page is reached** (URL contains 'payment' OR payment fields visible)

Do NOT stop until payment page is confirmed. Execute each step carefully."""
        
        return await self.execute_task(task, customer_data)
