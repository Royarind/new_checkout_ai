
from checkout_ai.agents.orchestrator import AgentOrchestrator
from checkout_ai.core.config import CheckoutConfig

class CheckoutAgent:
    """
    Main entry point for the Checkout AI package.
    Wraps the AgentOrchestrator to provide a clean API for library users.
    """
    
    def __init__(self, page, customer_data: dict = None, max_iterations: int = 20):
        """
        Initialize the CheckoutAgent.
        
        Args:
            page: Playwright page object
            customer_data: Dictionary containing customer info (shipping, contact, etc.)
            max_iterations: Maximum number of agent steps
        """
        self.orchestrator = AgentOrchestrator(page, max_iterations, customer_data)
        self.config = CheckoutConfig()

    async def checkout(self, product_url: str, variants: dict):
        """
        Execute the full checkout flow for a product.
        
        Args:
            product_url: URL of the product to purchase
            variants: Dictionary of variant selections (e.g. {'color': 'red', 'size': 'M'})
            
        Returns:
            Dict containing the result of the checkout process
        """
        if not self.orchestrator.customer_data:
            raise ValueError("Customer data is required for checkout")
            
        return await self.orchestrator.execute_checkout_flow(product_url, variants, self.orchestrator.customer_data)

    async def run_custom_task(self, task_description: str):
        """
        Execute a custom natural language task.
        
        Args:
            task_description: The instruction for the agent
            
        Returns:
            Dict containing the result
        """
        return await self.orchestrator.execute_task(task_description, self.orchestrator.customer_data)
