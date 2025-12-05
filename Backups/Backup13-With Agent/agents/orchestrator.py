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
                # 1. Planner Agent
                logger.info("ORCHESTRATOR: Calling Planner...")
                pa_input = {
                    "query": query,
                    "og_plan": current_plan,
                    "feedback": feedback
                }
                pa_result = await PA_agent.run(str(pa_input))
                plan_data = pa_result.output
                
                current_plan = plan_data.plan
                next_step = plan_data.next_step
                logger.info(f"ORCHESTRATOR: Next step: {next_step}")
                
                # 2. Browser Agent
                logger.info("ORCHESTRATOR: Calling Browser Agent...")
                ba_deps = current_step_class(current_step=next_step)
                ba_result = await BA_agent.run(next_step, deps=ba_deps)
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
                ca_result = await CA_agent.run(ca_input)
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
                    return {
                        'success': True,
                        'message': critique_data.final_response,
                        'iterations': iteration + 1,
                        'history': self.history
                    }
                
                # Small delay between iterations
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"ORCHESTRATOR: Error in iteration {iteration + 1}: {e}")
                return {
                    'success': False,
                    'error': str(e),
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
        task = f"""Complete checkout for product at {product_url}
        
Steps:
1. Navigate to {product_url}
2. Select variants: {variant_str}
3. Add to cart
4. Navigate to cart
5. Click checkout
6. Fill contact info: {customer_data['contact']['email']}
7. Fill shipping address
8. Click continue to payment

Execute each step carefully and validate before proceeding."""
        
        return await self.execute_task(task, customer_data)
