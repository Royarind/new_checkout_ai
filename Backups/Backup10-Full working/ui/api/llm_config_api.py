"""
LLM Configuration API Endpoints
Handles testing and configuration of LLM providers
"""

from dash import callback, Input, Output, State, no_update
import json
from agent.llm_factory import LLMFactory
from agent.llm_providers import COMMON_MODELS


# Store session config - persists until app restart
_session_config = {}
_config_file = 'llm_config.json'

# Load config from file on startup
try:
    import os
    if os.path.exists(_config_file):
        with open(_config_file, 'r') as f:
            _session_config = json.load(f)
except Exception:
    pass


@callback(
    Output('llm-test-result', 'children'),
    Output('llm-test-result', 'color'),
    Input('llm-test-button', 'n_clicks'),
    State('llm-provider-dropdown', 'value'),
    State('llm-api-key-input', 'value'),
    State('llm-model-dropdown', 'value'),
    State('llm-custom-model-input', 'value'),
    State('llm-temperature-slider', 'value'),
    State('llm-max-tokens-input', 'value'),
    State('llm-azure-endpoint-input', 'value'),
    State('llm-azure-deployment-input', 'value'),
    State('llm-custom-base-url-input', 'value'),
    prevent_initial_call=True
)
async def test_llm_connection(n_clicks, provider, api_key, model_dropdown, custom_model, 
                              temperature, max_tokens, azure_endpoint, azure_deployment, custom_base_url):
    """Test LLM connection with provided configuration"""
    
    if not n_clicks:
        return no_update, no_update
    
    # Build config
    config = {
        'provider': provider,
        'temperature': temperature or 0.7,
        'max_tokens': max_tokens or 1024
    }
    
    # Use custom model if provided, otherwise use dropdown
    config['model'] = custom_model if custom_model else model_dropdown
    
    # Provider-specific config - API key required
    if not api_key or not api_key.strip():
        return "❌ API key is required", "danger"
    config['api_key'] = api_key.strip()
    
    if provider == 'azure':
        if not azure_endpoint or not azure_deployment:
            return "❌ Endpoint URL and Deployment Name required for Azure", "danger"
        config['endpoint'] = azure_endpoint
        config['deployment_name'] = azure_deployment
    
    if provider == 'custom':
        if not custom_base_url:
            return "❌ Base URL required for custom endpoint", "danger"
        if not config['model']:
            return "❌ Model name required for custom endpoint", "danger"
        config['base_url'] = custom_base_url
    
    # Test connection
    try:
        result = await LLMFactory.test_config(config)
        
        if result['success']:
            # Store config in session and persist to disk
            _session_config['llm'] = config
            try:
                with open(_config_file, 'w') as f:
                    json.dump(_session_config, f, indent=2)
            except Exception:
                pass
            
            message = f"""✅ Connected Successfully!
            
• Provider: {provider.upper()}
• Model: {result['model']}
• Response Time: {result['response_time_ms']}ms
• Sample Response: {result['sample_response']}

Configuration saved for this session."""
            return message, "success"
        else:
            error_msg = result.get('error', 'Unknown error')
            return f"❌ Connection Failed\n\nError: {error_msg}", "danger"
    
    except Exception as e:
        return f"❌ Test Failed\n\nError: {str(e)}", "danger"


@callback(
    Output('llm-model-dropdown', 'options'),
    Output('llm-model-dropdown', 'value'),
    Output('llm-api-key-input', 'placeholder'),
    Output('llm-azure-config', 'style'),
    Output('llm-custom-config', 'style'),
    Input('llm-provider-dropdown', 'value'),
    Input('llm-settings-modal', 'is_open'),
    prevent_initial_call=False
)
def update_provider_options(provider, modal_open):
    """Update available models and show/hide provider-specific fields"""
    from ui.api.llm_config_api import get_session_llm_config
    
    # Get models for provider
    models = COMMON_MODELS.get(provider, [])
    options = [{'label': f"{m['name']} - {m['description']}", 'value': m['id']} for m in models]
    
    # Check if we have saved config
    saved_config = get_session_llm_config()
    if saved_config and saved_config.get('provider') == provider:
        default_value = saved_config.get('model')
    else:
        default_value = models[0]['id'] if models else None
    
    # Update placeholder based on provider
    if provider == 'groq':
        api_key_placeholder = 'Enter your Groq API key...'
    else:
        api_key_placeholder = 'Enter your API key...'
    
    # Show/hide Azure config
    azure_style = {'display': 'block'} if provider == 'azure' else {'display': 'none'}
    
    # Show/hide Custom config
    custom_style = {'display': 'block'} if provider == 'custom' else {'display': 'none'}
    
    return options, default_value, api_key_placeholder, azure_style, custom_style


def get_session_llm_config():
    """Get current LLM configuration from session"""
    config = _session_config.get('llm')
    print(f"\nget_session_llm_config called - returning: {config}")
    print(f"_session_config contents: {_session_config}")
    return config


def set_session_llm_config(config):
    """Set LLM configuration in session"""
    _session_config['llm'] = config
    print(f"\nset_session_llm_config called with: {config}")
    print(f"_session_config after set: {_session_config}")
    # Persist to disk
    try:
        with open(_config_file, 'w') as f:
            json.dump(_session_config, f, indent=2)
    except Exception:
        pass


def clear_session_llm_config():
    """Clear LLM configuration from session"""
    if 'llm' in _session_config:
        del _session_config['llm']
    # Clear from disk
    try:
        import os
        if os.path.exists(_config_file):
            os.remove(_config_file)
    except Exception:
        pass
