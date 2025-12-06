from checkout_ai.agents.orchestrator import AgentOrchestrator
import logging

logger = logging.getLogger(__name__)

class AgentCoordinatorAdapter:
    def __init__(self, page, use_mock=False):
        self.orchestrator = AgentOrchestrator(page)
    
    async def assist_stage(self, stage, customer_data, error_result=None):
        logger.info(f"ADAPTER: Assisting stage '{stage}' using AgentOrchestrator")
        task_map = {
            'proceed_to_checkout': "Navigate to checkout page. Find and click checkout button or view cart then checkout.",
            'guest_checkout': "Find and click guest checkout button or continue as guest.",
            'fill_contact': "Fill contact information (email, phone, name) and click continue.",
            'fill_shipping': "Fill shipping address and click continue."
        }
        task = task_map.get(stage, f"Fix issue at stage: {stage}")
        if error_result and error_result.get('error'):
            task += f"\nPrevious error: {error_result['error']}"
            
        result = await self.orchestrator.execute_task(task, customer_data)
        
        return {
            'success': result['success'],
            'action_taken': result.get('message', 'Agent executed task'),
            'details': result
        }

def create_agent_system(page, use_mock=False):
    return AgentCoordinatorAdapter(page, use_mock)
