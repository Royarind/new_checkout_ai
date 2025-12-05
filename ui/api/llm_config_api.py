"""
LLM Configuration API (Simplified)
Loads LLM settings from environment variables (.env) and provides session accessors.
UI-dependent callbacks for provider selection, model testing, etc., have been removed.
"""

import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load env vars immediately
load_dotenv()

# Ensure project root is in sys.path (same logic as original)
_current_dir = Path(__file__).resolve().parent
_ui_dir = _current_dir.parent
_root_dir = _ui_dir.parent
# Session config persists for app runtime
_session_config = {}

def set_session_llm_config(config):
    """Store LLM configuration in session only (no disk persistence)."""
    _session_config['llm'] = config
    # No writing to file - .env is source of truth

def get_session_llm_config():
    """Retrieve current LLM configuration from session."""
    return _session_config.get('llm')

def clear_session_llm_config():
    """Clear LLM configuration from session."""
    if 'llm' in _session_config:
        del _session_config['llm']

def _load_llm_config_from_env():
    """Load LLM settings from environment variables (.env).
    Expected variables:
        - LLM_PROVIDER (default: 'ollama')
        - OLLAMA_BASE_URL, OLLAMA_MODEL for Ollama
        - OPENAI_API_KEY, OPENAI_MODEL for OpenAI
        - GROQ_API_KEY, GROQ_MODEL for Groq
        - GEMINI_API_KEY, GEMINI_MODEL for Gemini
        - AZURE_API_KEY, AZURE_ENDPOINT, AZURE_DEPLOYMENT, AZURE_MODEL for Azure
        - CUSTOM_BASE_URL, CUSTOM_MODEL for custom endpoint
    The function builds a config dict compatible with the original UI expectations.
    """
    provider = os.getenv('LLM_PROVIDER', 'ollama').lower()
    print(f"DEBUG: llm_config_api detected LLM_PROVIDER = {provider}")
    config = {'provider': provider}
    # Map provider to relevant env vars
    if provider == 'ollama':
        config['api_key'] = ''  # Ollama typically doesn't need an API key
        config['model'] = os.getenv('OLLAMA_MODEL', '')
        config['base_url'] = os.getenv('OLLAMA_BASE_URL', '')
    elif provider == 'openai':
        config['api_key'] = os.getenv('OPENAI_API_KEY', '')
        config['model'] = os.getenv('OPENAI_MODEL', '')
    elif provider == 'groq':
        config['api_key'] = os.getenv('GROQ_API_KEY', '')
        config['model'] = os.getenv('GROQ_MODEL', '')
    elif provider == 'gemini':
        config['api_key'] = os.getenv('GEMINI_API_KEY', '')
        config['model'] = os.getenv('GEMINI_MODEL', '')
    elif provider == 'azure':
        config['api_key'] = os.getenv('AZURE_API_KEY', '')
        config['model'] = os.getenv('AZURE_MODEL', '')
        config['endpoint'] = os.getenv('AZURE_ENDPOINT', '')
        config['deployment'] = os.getenv('AZURE_DEPLOYMENT', '')
    elif provider == 'custom':
        config['api_key'] = os.getenv('CUSTOM_API_KEY', '')
        config['model'] = os.getenv('CUSTOM_MODEL', '')
        config['base_url'] = os.getenv('CUSTOM_BASE_URL', '')
    else:
        # Fallback to Ollama if unknown
        config['api_key'] = ''
        config['model'] = os.getenv('OLLAMA_MODEL', '')
        config['base_url'] = os.getenv('OLLAMA_BASE_URL', '')
    # Store in session
    set_session_llm_config(config)

# Load configuration at import time so that any component importing this module gets the settings.
_load_llm_config_from_env()
