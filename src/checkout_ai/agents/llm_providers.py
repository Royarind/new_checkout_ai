"""LLM Provider Implementations"""
import os
import json
from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    def __init__(self, api_key=None, model=None, temperature=0.7, max_tokens=1024):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    @abstractmethod
    async def complete(self, prompt, **kwargs):
        pass

class GroqProvider(BaseLLMProvider):
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

class OpenAIProvider(BaseLLMProvider):
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

class GeminiProvider(BaseLLMProvider):
    DEFAULT_MODEL = "gemini-2.5-flash"
    
    def __init__(self, api_key, model=None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL, **kwargs)
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model)
    
    async def complete(self, prompt, **kwargs):
        try:
            import asyncio
            response = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.client.generate_content(
                    prompt,
                    generation_config={
                        'temperature': kwargs.get('temperature', self.temperature),
                        'max_output_tokens': kwargs.get('max_tokens', self.max_tokens)
                    }
                )
            )
            content = response.text
            try:
                return json.loads(content)
            except:
                return {'text': content, 'message': content}
        except Exception as e:
            return {'error': str(e)}

class OllamaProvider(BaseLLMProvider):
    """Local LLM provider using Ollama"""
    DEFAULT_MODEL = "qwen2.5:7b"
    DEFAULT_BASE_URL = "http://localhost:11434"
    
    def __init__(self, model=None, base_url=None, **kwargs):
        super().__init__(api_key=None, model=model or self.DEFAULT_MODEL, **kwargs)
        self.base_url = base_url or self.DEFAULT_BASE_URL
        
    async def complete(self, prompt, **kwargs):
        try:
            import aiohttp
            
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get('temperature', self.temperature),
                    "num_predict": kwargs.get('max_tokens', self.max_tokens)
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return {'error': f'Ollama error: {error_text}'}
                    
                    result = await response.json()
                    content = result.get('response', '')
                    
                    try:
                        return json.loads(content)
                    except:
                        return {'text': content, 'message': content}
        except Exception as e:
            return {'error': f'Ollama connection failed: {str(e)}. Make sure Ollama is running (ollama serve)'}

class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter provider - supports multiple models through OpenRouter API"""
    DEFAULT_MODEL = "deepseek/deepseek-chat"
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(self, api_key, model=None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL, **kwargs)
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.BASE_URL
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

PROVIDERS = {
    'groq': GroqProvider,
    'openai': OpenAIProvider,
    'gemini': GeminiProvider,
    'ollama': OllamaProvider,
    'openrouter': OpenRouterProvider
}

COMMON_MODELS = {
    'groq': [
        {'id': 'llama-3.3-70b-versatile', 'name': 'Llama 3.3 70B', 'description': 'Most capable'},
        {'id': 'llama-3.1-8b-instant', 'name': 'Llama 3.1 8B', 'description': 'Fast & efficient'}
    ],
    'openai': [
        {'id': 'gpt-4o', 'name': 'GPT-4o', 'description': 'Most capable'},
        {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini', 'description': 'Fast & affordable'},
        {'id': 'gpt-4o-mini-2024-07-18', 'name': 'GPT-4o Mini (July 2024)', 'description': 'Specific version'},
        {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo', 'description': 'Previous generation'},
        {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'description': 'Legacy model'}
    ],
    'gemini': [
        {'id': 'gemini-2.5-flash', 'name': 'Gemini 2.5 Flash', 'description': 'Best price-performance (Recommended)'},
        {'id': 'gemini-2.5-flash-lite', 'name': 'Gemini 2.5 Flash-Lite', 'description': 'Fastest, most cost-efficient'},
        {'id': 'gemini-2.5-pro', 'name': 'Gemini 2.5 Pro', 'description': 'Advanced reasoning for complex tasks'},
        {'id': 'gemini-3-pro', 'name': 'Gemini 3 Pro', 'description': 'Most advanced multimodal model'},
        {'id': 'gemini-2.0-flash', 'name': 'Gemini 2.0 Flash', 'description': 'Previous generation flash'},
        {'id': 'gemini-1.5-flash', 'name': 'Gemini 1.5 Flash', 'description': 'Legacy flash model'},
        {'id': 'gemini-1.5-pro', 'name': 'Gemini 1.5 Pro', 'description': 'Legacy pro model'}
    ],
    'ollama': [
        {'id': 'qwen2.5:0.5b', 'name': 'Qwen 2.5 0.5B', 'description': 'Tiny & fast (~1GB RAM)'},
        {'id': 'qwen2.5:1.5b', 'name': 'Qwen 2.5 1.5B', 'description': 'Small & fast (~2GB RAM)'},
        {'id': 'qwen2.5:3b', 'name': 'Qwen 2.5 3B', 'description': 'Balanced (~3GB RAM)'},
        {'id': 'qwen2.5:7b', 'name': 'Qwen 2.5 7B', 'description': 'Recommended (~6GB RAM)'},
        {'id': 'qwen2.5:14b', 'name': 'Qwen 2.5 14B', 'description': 'High quality (~10GB RAM)'},
        {'id': 'llama3.2:1b', 'name': 'Llama 3.2 1B', 'description': 'Ultra-fast (~1GB RAM)'},
        {'id': 'llama3.2:3b', 'name': 'Llama 3.2 3B', 'description': 'Fast & capable (~2GB RAM)'},
        {'id': 'llama3.1:8b', 'name': 'Llama 3.1 8B', 'description': 'Excellent quality (~5GB RAM)'},
        {'id': 'mistral:7b', 'name': 'Mistral 7B', 'description': 'Great reasoning (~4GB RAM)'},
        {'id': 'phi3:3.8b', 'name': 'Phi-3 Mini', 'description': 'Microsoft model (~2GB RAM)'}
    ],
    'openrouter': [
        {'id': 'deepseek/deepseek-chat', 'name': 'DeepSeek Chat', 'description': 'Excellent reasoning, very affordable'},
        {'id': 'anthropic/claude-3.5-sonnet', 'name': 'Claude 3.5 Sonnet', 'description': 'Best for complex tasks'},
        {'id': 'openai/gpt-4o', 'name': 'GPT-4o', 'description': 'OpenAI via OpenRouter'},
        {'id': 'google/gemini-2.0-flash-exp:free', 'name': 'Gemini 2.0 Flash (Free)', 'description': 'Free tier'},
        {'id': 'meta-llama/llama-3.3-70b-instruct', 'name': 'Llama 3.3 70B', 'description': 'Open source, powerful'}
    ]
}