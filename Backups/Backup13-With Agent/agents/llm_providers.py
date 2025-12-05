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
    DEFAULT_MODEL = "gemini-pro"
    
    def __init__(self, api_key, model=None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL, **kwargs)
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model)
    
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

PROVIDERS = {
    'groq': GroqProvider,
    'openai': OpenAIProvider,
    'gemini': GeminiProvider
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
        {'id': 'gemini-2.5-flash', 'name': 'Gemini 2.5 Flash', 'description': 'Balanced'},
        {'id': 'gemini-pro', 'name': 'Gemini Pro', 'description': 'Most capable'}
    ]
}
