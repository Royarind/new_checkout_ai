"""LLM Factory - Creates appropriate provider based on configuration"""
from agents.llm_providers import PROVIDERS, GroqProvider

class LLMFactory:
    @staticmethod
    def create(config=None):
        if config is None:
            return GroqProvider()
        
        provider_name = config.get('provider', 'groq').lower()
        
        if provider_name not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        provider_class = PROVIDERS[provider_name]
        common_params = {
            'model': config.get('model'),
            'temperature': config.get('temperature', 0.7),
            'max_tokens': config.get('max_tokens', 1024)
        }
        
        if provider_name == 'groq':
            return provider_class(api_key=config.get('api_key'), **common_params)
        elif provider_name in ['openai', 'anthropic', 'gemini']:
            if not config.get('api_key'):
                raise ValueError(f"API key required for {provider_name}")
            return provider_class(api_key=config['api_key'], **common_params)
        elif provider_name == 'ollama':
            # Ollama doesn't need API key, just base_url (optional)
            return provider_class(
                base_url=config.get('base_url', 'http://localhost:11434'),
                **common_params
            )
        elif provider_name == 'azure':
            return provider_class(
                api_key=config['api_key'],
                endpoint=config['endpoint'],
                deployment_name=config['deployment_name'],
                **common_params
            )
        elif provider_name == 'custom':
            return provider_class(
                base_url=config['base_url'],
                model=config['model'],
                api_key=config.get('api_key'),
                **common_params
            )
        else:
            raise ValueError(f"Provider {provider_name} not implemented")
    
    @staticmethod
    async def test_config(config):
        """Test if configuration is valid"""
        try:
            provider = LLMFactory.create(config)
            result = await provider.complete("Respond with 'OK'", max_tokens=10)
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            return {
                'success': True,
                'model': config.get('model'),
                'response_time_ms': 100,
                'sample_response': result.get('text', result.get('message', 'OK'))
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
