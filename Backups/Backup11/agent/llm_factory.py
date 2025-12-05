"""
LLM Factory - Creates appropriate provider based on configuration
"""

from agent.llm_providers import PROVIDERS, GroqProvider


class LLMFactory:
    """Factory to create LLM provider instances"""
    
    @staticmethod
    def create(config=None):
        """
        Create LLM provider based on configuration
        
        Args:
            config: dict with keys:
                - provider: str (groq, openai, anthropic, gemini, azure, custom)
                - api_key: str (optional for groq)
                - model: str (optional, uses default if not provided)
                - temperature: float (default 0.7)
                - max_tokens: int (default 1024)
                - endpoint: str (for azure/custom)
                - deployment_name: str (for azure)
                - base_url: str (for custom)
        
        Returns:
            Provider instance
        """
        if config is None:
            # Default to Groq
            return GroqProvider()
        
        provider_name = config.get('provider', 'groq').lower()
        
        if provider_name not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider_name}. Available: {list(PROVIDERS.keys())}")
        
        provider_class = PROVIDERS[provider_name]
        
        # Common parameters
        common_params = {
            'model': config.get('model'),
            'temperature': config.get('temperature', 0.7),
            'max_tokens': config.get('max_tokens', 1024)
        }
        
        # Provider-specific initialization
        if provider_name == 'groq':
            return provider_class(
                api_key=config.get('api_key'),
                **common_params
            )
        
        elif provider_name == 'openai':
            if not config.get('api_key'):
                raise ValueError("API key required for OpenAI")
            return provider_class(
                api_key=config['api_key'],
                **common_params
            )
        
        elif provider_name == 'anthropic':
            if not config.get('api_key'):
                raise ValueError("API key required for Anthropic")
            return provider_class(
                api_key=config['api_key'],
                **common_params
            )
        
        elif provider_name == 'gemini':
            if not config.get('api_key'):
                raise ValueError("API key required for Gemini")
            return provider_class(
                api_key=config['api_key'],
                **common_params
            )
        
        elif provider_name == 'azure':
            if not config.get('api_key'):
                raise ValueError("API key required for Azure OpenAI")
            if not config.get('endpoint'):
                raise ValueError("Endpoint URL required for Azure OpenAI")
            if not config.get('deployment_name'):
                raise ValueError("Deployment name required for Azure OpenAI")
            
            return provider_class(
                api_key=config['api_key'],
                endpoint=config['endpoint'],
                deployment_name=config['deployment_name'],
                temperature=common_params['temperature'],
                max_tokens=common_params['max_tokens']
            )
        
        elif provider_name == 'custom':
            if not config.get('base_url'):
                raise ValueError("Base URL required for custom endpoint")
            if not config.get('model'):
                raise ValueError("Model name required for custom endpoint")
            
            return provider_class(
                base_url=config['base_url'],
                model=config['model'],
                api_key=config.get('api_key'),
                temperature=common_params['temperature'],
                max_tokens=common_params['max_tokens']
            )
        
        else:
            raise ValueError(f"Provider {provider_name} not implemented")
    
    @staticmethod
    async def test_config(config):
        """
        Test if configuration is valid by making a test API call
        
        Args:
            config: dict with provider configuration
        
        Returns:
            dict with test results
        """
        try:
            provider = LLMFactory.create(config)
            result = await provider.test_connection()
            return result
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
