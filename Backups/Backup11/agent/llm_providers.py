"""
LLM Provider Implementations
Supports multiple providers with custom model names
"""

import os
import json
import time
from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Base class for all LLM providers"""
    
    def __init__(self, api_key=None, model=None, temperature=0.7, max_tokens=1024):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    @abstractmethod
    async def complete(self, prompt, **kwargs):
        """Generate completion"""
        pass
    
    @abstractmethod
    async def test_connection(self):
        """Test if provider is accessible"""
        pass


class GroqProvider(BaseLLMProvider):
    """Groq LLM Provider"""
    
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    
    def __init__(self, api_key=None, model=None, **kwargs):
        super().__init__(api_key or os.getenv('GROQ_API_KEY'), model or self.DEFAULT_MODEL, **kwargs)
        from groq import AsyncGroq
        self.client = AsyncGroq(api_key=self.api_key)
    
    async def complete(self, prompt, **kwargs):
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get('temperature', self.temperature),
                max_tokens=kwargs.get('max_tokens', self.max_tokens)
            )
            
            content = response.choices[0].message.content
            try:
                return json.loads(content)
            except:
                return {'text': content, 'message': content}
        except Exception as e:
            return {'error': str(e)}
    
    async def test_connection(self):
        start = time.time()
        try:
            result = await self.complete("Respond with 'OK'", max_tokens=10)
            elapsed = (time.time() - start) * 1000
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'model': self.model,
                'response_time_ms': int(elapsed),
                'sample_response': result.get('text', result.get('message', 'OK'))
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM Provider"""
    
    DEFAULT_MODEL = "gpt-4o-mini"
    
    def __init__(self, api_key, model=None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL, **kwargs)
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=self.api_key)
    
    async def complete(self, prompt, **kwargs):
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get('temperature', self.temperature),
                max_tokens=kwargs.get('max_tokens', self.max_tokens)
            )
            
            content = response.choices[0].message.content
            try:
                return json.loads(content)
            except:
                return {'text': content, 'message': content}
        except Exception as e:
            return {'error': str(e)}
    
    async def test_connection(self):
        start = time.time()
        try:
            result = await self.complete("Respond with 'OK'", max_tokens=10)
            elapsed = (time.time() - start) * 1000
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'model': self.model,
                'response_time_ms': int(elapsed),
                'sample_response': result.get('text', 'OK')
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude Provider"""
    
    DEFAULT_MODEL = "claude-3-5-sonnet-20240620"
    
    def __init__(self, api_key, model=None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL, **kwargs)
        try:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
    
    async def complete(self, prompt, **kwargs):
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            try:
                return json.loads(content)
            except:
                return {'text': content, 'message': content}
        except Exception as e:
            return {'error': str(e)}
    
    async def test_connection(self):
        start = time.time()
        try:
            result = await self.complete("Respond with 'OK'", max_tokens=10)
            elapsed = (time.time() - start) * 1000
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'model': self.model,
                'response_time_ms': int(elapsed),
                'sample_response': result.get('text', 'OK')
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider"""
    
    DEFAULT_MODEL = "gemini-pro"
    
    def __init__(self, api_key, model=None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL, **kwargs)
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model)
        except ImportError:
            raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")
    
    async def complete(self, prompt, **kwargs):
        try:
            response = await self.client.generate_content_async(
                prompt,
                generation_config={
                    'temperature': kwargs.get('temperature', self.temperature),
                    'max_output_tokens': kwargs.get('max_tokens', self.max_tokens)
                }
            )
            
            content = response.text
            try:
                return json.loads(content)
            except:
                return {'text': content, 'message': content}
        except Exception as e:
            return {'error': str(e)}
    
    async def test_connection(self):
        start = time.time()
        try:
            result = await self.complete("Respond with 'OK'", max_tokens=10)
            elapsed = (time.time() - start) * 1000
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'model': self.model,
                'response_time_ms': int(elapsed),
                'sample_response': result.get('text', 'OK')
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


class AzureOpenAIProvider(BaseLLMProvider):
    """Azure OpenAI Provider"""
    
    def __init__(self, api_key, endpoint, deployment_name, **kwargs):
        super().__init__(api_key, deployment_name, **kwargs)
        self.endpoint = endpoint
        from openai import AsyncAzureOpenAI
        self.client = AsyncAzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version="2024-02-15-preview"
        )
    
    async def complete(self, prompt, **kwargs):
        try:
            response = await self.client.chat.completions.create(
                model=self.model,  # deployment name
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get('temperature', self.temperature),
                max_tokens=kwargs.get('max_tokens', self.max_tokens)
            )
            
            content = response.choices[0].message.content
            try:
                return json.loads(content)
            except:
                return {'text': content, 'message': content}
        except Exception as e:
            return {'error': str(e)}
    
    async def test_connection(self):
        start = time.time()
        try:
            result = await self.complete("Respond with 'OK'", max_tokens=10)
            elapsed = (time.time() - start) * 1000
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'model': self.model,
                'response_time_ms': int(elapsed),
                'sample_response': result.get('text', 'OK')
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


class CustomProvider(BaseLLMProvider):
    """Custom OpenAI-compatible endpoint (Ollama, LM Studio, etc.)"""
    
    def __init__(self, base_url, model, api_key=None, **kwargs):
        super().__init__(api_key or "not-needed", model, **kwargs)
        self.base_url = base_url
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    async def complete(self, prompt, **kwargs):
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get('temperature', self.temperature),
                max_tokens=kwargs.get('max_tokens', self.max_tokens)
            )
            
            content = response.choices[0].message.content
            try:
                return json.loads(content)
            except:
                return {'text': content, 'message': content}
        except Exception as e:
            return {'error': str(e)}
    
    async def test_connection(self):
        start = time.time()
        try:
            result = await self.complete("Respond with 'OK'", max_tokens=10)
            elapsed = (time.time() - start) * 1000
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'model': self.model,
                'response_time_ms': int(elapsed),
                'sample_response': result.get('text', 'OK')
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


# Provider registry
PROVIDERS = {
    'groq': GroqProvider,
    'openai': OpenAIProvider,
    'anthropic': AnthropicProvider,
    'gemini': GeminiProvider,
    'azure': AzureOpenAIProvider,
    'custom': CustomProvider
}


# Common models for each provider
COMMON_MODELS = {
    'groq': [
        {'id': 'llama-3.3-70b-versatile', 'name': 'Llama 3.3 70B', 'description': 'Most capable'},
        {'id': 'llama-3.1-8b-instant', 'name': 'Llama 3.1 8B', 'description': 'Fast & efficient'},
        {'id': 'meta-llama/llama-guard-4-12b', 'name': 'Meta Llama Guard 4 12B', 'description': 'Safety'},
        {'id': 'openai/gpt-oss-120b', 'name': 'OpenAI GPT OSS 120B', 'description': 'Large'},
        {'id': 'openai/gpt-oss-20b', 'name': 'OpenAI GPT OSS 20B', 'description': 'Balanced'},
        {'id': 'whisper-large-v3', 'name': 'OpenAI Whisper Large V3', 'description': 'Speech'},
        {'id': 'whisper-large-v3-turbo', 'name': 'OpenAI Whisper Large V3 Turbo', 'description': 'Fast Speech'},
        {'id': 'groq/compound', 'name': 'Groq Compound', 'description': 'System'},
        {'id': 'groq/compound-mini', 'name': 'Groq Compound Mini', 'description': 'Light System'},
        {'id': 'meta-llama/llama-4-maverick-17b-128e-instruct', 'name': 'Meta Llama 4 Maverick 17B', 'description': 'Creative'},
        {'id': 'meta-llama/llama-4-scout-17b-16e-instruct', 'name': 'Meta Llama 4 Scout 17B', 'description': 'Conversational'},
        {'id': 'meta-llama/llama-prompt-guard-2-22m', 'name': 'Meta Prompt Guard 2 22M', 'description': 'Filter'},
        {'id': 'meta-llama/llama-prompt-guard-2-86m', 'name': 'Meta Prompt Guard 2 86M', 'description': 'Safe Filter'},
        {'id': 'moonshotai/kimi-k2-instruct-0905', 'name': 'Moonshot AI Kimi K2', 'description': 'Reasoning'},
        {'id': 'openai/gpt-oss-safeguard-20b', 'name': 'OpenAI GPT OSS Safeguard 20B', 'description': 'Safety'},
        {'id': 'playai-tts', 'name': 'PlayAI TTS', 'description': 'Speech'},
        {'id': 'playai-tts-arabic', 'name': 'PlayAI TTS Arabic', 'description': 'Arabic Speech'},
        {'id': 'qwen/qwen3-32b', 'name': 'Alibaba Qwen3 32B', 'description': 'Enterprise'}
    ],
    'openai': [
        {'id': 'gpt-4o', 'name': 'GPT-4o', 'description': 'Most capable'},
        {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini', 'description': 'Fast & affordable'},
        {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo', 'description': 'Previous generation'},
        {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'description': 'Legacy model'},
        {"id": "gpt-4.1", "name": "GPT-4.1", "description": "Frontier"},
        {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "description": "Fast reasoning"},
        {"id": "gpt-4.5", "name": "GPT-4.5", "description": "Enhanced"},
        {"id": "gpt-oss-120b", "name": "GPT OSS 120B", "description": "Open-weight large"},
        {"id": "gpt-oss-20b", "name": "GPT OSS 20B", "description": "Open-weight medium"}
    ],
    'anthropic': [
        {'id': 'claude-3-5-sonnet-20240620', 'name': 'Claude 3.5 Sonnet', 'description': 'Most capable'},
        {'id': 'claude-3-opus-20240229', 'name': 'Claude 3 Opus', 'description': 'Previous flagship'},
        {'id': 'claude-3-sonnet-20240229', 'name': 'Claude 3 Sonnet', 'description': 'Balanced'},
        {'id': 'claude-3-haiku-20240307', 'name': 'Claude 3 Haiku', 'description': 'Fast & affordable'},
        {'id': 'anthropic/claude-4-opus', 'name': 'Claude Opus 4', 'description': 'Frontier'},
        {'id': 'anthropic/claude-4-sonnet', 'name': 'Claude Sonnet 4', 'description': 'Standard'},
        {'id': 'anthropic/claude-4-haiku', 'name': 'Claude Haiku 4', 'description': 'Lightweight'},
        {'id': 'anthropic/claude-3-7-sonnet', 'name': 'Claude 3.7 Sonnet', 'description': 'Hybrid Reasoning'},
        {'id': 'anthropic/claude-3-5-sonnet', 'name': 'Claude 3.5 Sonnet', 'description': 'Balanced'},
        {'id': 'anthropic/claude-3-5-haiku', 'name': 'Claude 3.5 Haiku', 'description': 'Fast'}
    ],
    'gemini': [
        {'id': 'gemini-pro', 'name': 'Gemini Pro', 'description': 'Most capable'},
        {'id': 'gemini-pro-vision', 'name': 'Gemini Pro Vision', 'description': 'Multimodal'},
        {'id': 'gemini-1.5-pro', 'name': 'Gemini 1.5 Pro', 'description': 'Latest version'},
        {'id': 'gemini-2.5-pro', 'name': 'Gemini 2.5 Pro', 'description': 'Top-tier'},
        {'id': 'gemini-2.5-flash', 'name': 'Gemini 2.5 Flash', 'description': 'Balanced'},
        {'id': 'gemini-2.5-flash-lite', 'name': 'Gemini 2.5 Flash-Lite', 'description': 'Cost-efficient'},
        {'id': 'gemini-2.5-flash-image', 'name': 'Gemini 2.5 Flash Image', 'description': 'Vision'},
        {'id': 'gemini-2.0-flash', 'name': 'Gemini 2.0 Flash', 'description': 'Previous gen'},
        {'id': 'gemini-2.0-flash-lite', 'name': 'Gemini 2.0 Flash-Lite', 'description': 'Lightweight'}
    ]
}
