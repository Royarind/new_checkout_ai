"""OpenAI Client Wrapper - Uses LLM config from UI"""
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

_client = None

def get_client():
    """Get OpenAI client instance"""
    global _client
    if _client is None:
        # Try to get API key from UI config first
        try:
            from ui.api.llm_config_api import get_session_llm_config
            config = get_session_llm_config()
            if config and config.get('provider') == 'openai':
                api_key = config.get('api_key')
            else:
                api_key = os.getenv('OPENAI_API_KEY')
        except:
            api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            api_key = os.getenv('GROQ_API_KEY')  # Fallback to Groq
        
        _client = AsyncOpenAI(api_key=api_key)
    
    return _client
