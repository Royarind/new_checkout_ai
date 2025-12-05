"""
Agent Factory - Creates and configures agent system
"""

import os
import logging
from agent.llm_client import LLMClient, MockLLMClient
from agent.simple_agent import SimpleAgent

logger = logging.getLogger(__name__)


def create_agent_system(page, use_mock=False):
    """
    Create simplified agent system with LLM client
    
    Args:
        page: Playwright page object
        use_mock: If True, use mock LLM (no API calls)
    
    Returns:
        SimpleAgent instance
    """
    if use_mock:
        logger.info("AGENT FACTORY: Creating agent system with MOCK LLM")
        llm_client = MockLLMClient()
    else:
        # Primary: Groq, Fallback: OpenAI
        logger.info("AGENT FACTORY: Creating simplified agent with Groq (primary) and OpenAI (fallback)")
        llm_client = LLMClient(
            provider='groq',
            model=os.getenv('GROQ_MODEL'),
            api_key=os.getenv('GROQ_API_KEY')
        )
    
    agent = SimpleAgent(page, llm_client)
    logger.info("AGENT FACTORY: Simplified agent initialized")
    
    return agent


def get_llm_client(provider=None, use_mock=False):
    """
    Get standalone LLM client
    
    Args:
        provider: 'groq', 'openai', 'anthropic', or None (auto-detect from env)
        use_mock: If True, return mock client
    
    Returns:
        LLMClient instance
    """
    if use_mock:
        return MockLLMClient()
    
    # Auto-detect provider from environment
    if provider is None:
        if os.getenv('GROQ_API_KEY'):
            provider = 'groq'
        elif os.getenv('OPENAI_API_KEY'):
            provider = 'openai'
        elif os.getenv('ANTHROPIC_API_KEY'):
            provider = 'anthropic'
        else:
            logger.warning("No API keys found, using mock LLM")
            return MockLLMClient()
    
    return LLMClient(provider=provider)
