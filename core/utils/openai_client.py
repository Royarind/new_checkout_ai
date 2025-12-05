"""LLM Client Wrapper - Uses LLM config from UI (supports all providers)"""
import os
from dotenv import load_dotenv

load_dotenv()

_client = None
_pydantic_model = None
_last_config = None

def get_client():
    """Get LLM client instance from UI config - supports all providers"""
    global _client, _last_config
    
    # Get config from UI
    try:
        from ui.api.llm_config_api import get_session_llm_config
        config = get_session_llm_config()
        
        if not config:
            print(f"[LLM Client] No LLM configured in UI - client will be None")
            return None
        
        # Check if config changed
        config_str = str(config)
        if config_str != _last_config:
            print(f"[LLM Client] Creating new client for provider: {config.get('provider', 'unknown')}")
            _last_config = config_str
            
            # Use LLM factory to create appropriate provider
            from agents.llm_factory import LLMFactory
            _client = LLMFactory.create(config)
            print(f"[LLM Client] Client created successfully")
        
        return _client
        
    except Exception as e:
        print(f"[LLM Client] Error getting client: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_pydantic_model():
    """Get appropriate pydantic_ai model based on UI config"""
    global _pydantic_model, _last_config
    
    try:
        from ui.api.llm_config_api import get_session_llm_config
        config = get_session_llm_config()
        
        if not config:
            print(f"[LLM Client] No LLM configured in UI - pydantic model will be None")
            return None
        
        # Check if config changed
        config_str = str(config)
        if config_str != _last_config or _pydantic_model is None:
            print(f"[LLM Client] Creating new pydantic model for provider: {config.get('provider', 'unknown')}")
            _last_config = config_str
            
            provider = config.get('provider', '').lower()
            model_name = config.get('model', '')
            api_key = config.get('api_key', '')
            
            if provider == 'groq':
                try:
                    from pydantic_ai.models.groq import GroqModel
                    if api_key:
                        os.environ['GROQ_API_KEY'] = api_key
                    _pydantic_model = GroqModel(model_name=model_name)
                    print(f"[LLM Client] Created GroqModel successfully")
                except ImportError:
                    print(f"[LLM Client] GroqModel not available, falling back to OpenAI client with Groq endpoint")
                    from pydantic_ai.models.openai import OpenAIModel
                    if api_key:
                        os.environ['OPENAI_API_KEY'] = api_key
                    # Use Groq's OpenAI-compatible endpoint
                    _pydantic_model = OpenAIModel(model_name=model_name, base_url='https://api.groq.com/openai/v1')
            elif provider == 'openai':
                from pydantic_ai.models.openai import OpenAIModel
                if api_key:
                    os.environ['OPENAI_API_KEY'] = api_key
                _pydantic_model = OpenAIModel(model_name=model_name)
                print(f"[LLM Client] Created OpenAIModel successfully")
            elif provider == 'gemini':
                try:
                    from pydantic_ai.models.gemini import GeminiModel
                    if api_key:
                        os.environ['GEMINI_API_KEY'] = api_key
                    _pydantic_model = GeminiModel(model_name=model_name)
                    print(f"[LLM Client] Created GeminiModel successfully")
                except ImportError:
                    print(f"[LLM Client] GeminiModel not available, falling back to OpenAI")
                    from pydantic_ai.models.openai import OpenAIModel
                    if api_key:
                        os.environ['OPENAI_API_KEY'] = api_key
                    _pydantic_model = OpenAIModel(model_name=model_name)
            elif provider == 'ollama':
                try:
                    # Check if pydantic_ai has native Ollama support
                    try:
                        from pydantic_ai.models.ollama import OllamaModel
                        base_url = config.get('base_url', 'http://localhost:11434')
                        _pydantic_model = OllamaModel(model_name=model_name, base_url=base_url)
                        print(f"[LLM Client] Created OllamaModel successfully")
                    except ImportError:
                        # Fallback to OpenAI compatible endpoint for Ollama
                        print(f"[LLM Client] Native OllamaModel not found, using OpenAIModel with base_url")
                        from pydantic_ai.models.openai import OpenAIModel
                        base_url = config.get('base_url', 'http://localhost:11434') + '/v1'
                        os.environ['OPENAI_API_KEY'] = 'ollama' # Dummy key for local
                        os.environ['OPENAI_BASE_URL'] = base_url
                        _pydantic_model = OpenAIModel(model_name=model_name, base_url=base_url)
                except Exception as e:
                    print(f"[LLM Client] Error initializing Ollama: {e}, falling back to OpenAI default")
                    from pydantic_ai.models.openai import OpenAIModel
                    if api_key:
                        os.environ['OPENAI_API_KEY'] = api_key
                    _pydantic_model = OpenAIModel(model_name=model_name)
            else:
                print(f"[LLM Client] Unsupported provider: {provider}, falling back to OpenAI")
                from pydantic_ai.models.openai import OpenAIModel
                if api_key:
                    os.environ['OPENAI_API_KEY'] = api_key
                _pydantic_model = OpenAIModel(model_name=model_name)
        
        return _pydantic_model
        
    except Exception as e:
        print(f"[LLM Client] Error creating pydantic model: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_model():
    """Get model name from UI config"""
    try:
        from ui.api.llm_config_api import get_session_llm_config
        config = get_session_llm_config()
        if config and config.get('model'):
            print(f"[LLM Client] Using model from UI config: {config['model']}")
            return config['model']
    except Exception as e:
        print(f"[LLM Client] Could not get model from UI config: {e}")
    
    print(f"[LLM Client] No model configured in UI - returning None")
    return None
