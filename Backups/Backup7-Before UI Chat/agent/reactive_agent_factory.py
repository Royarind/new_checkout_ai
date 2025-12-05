"""
Factory to create reactive agent system
"""

from agent.reactive_agent import ReactiveAgent
from agent.llm_client import LLMClient


def create_reactive_agent(page, use_mock=False, use_fast_model=True):
    """
    Create reactive agent with LLM client
    use_mock: If True, use mock LLM for testing
    use_fast_model: If True, use llama-3.1-8b-instant (faster, cheaper)
    """
    if use_mock:
        from agent.mock_llm import MockLLM
        llm_client = MockLLM()
    else:
        model = 'llama-3.1-8b-instant' if use_fast_model else 'llama-3.3-70b-versatile'
        llm_client = LLMClient(provider='groq', model=model)
    
    return ReactiveAgent(page, llm_client)
