"""
LLM Client - Handles communication with language models
Supports Anthropic Claude, OpenAI GPT-4, and local models
"""

import os
import json
import base64
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, provider='openai', model=None, api_key=None, config=None):
        """
        Initialize LLM client
        provider: 'groq', 'openai', 'anthropic', or 'local'
        config: dict with full provider configuration (new way)
        """
        # New way: use config dict
        if config:
            from agent.llm_factory import LLMFactory
            self._provider_instance = LLMFactory.create(config)
            self.provider = config.get('provider', 'groq')
            self.model = config.get('model')
            self.use_factory = True
        else:
            # Old way: backward compatibility
            self.provider = provider
            self.api_key = api_key or self._get_api_key(provider)
            self.model = model or self._get_default_model(provider)
            self.client = self._initialize_client()
            self.fallback_client = None
            self._setup_fallback()
            self.use_factory = False
    
    def _get_api_key(self, provider):
        """Get API key from environment"""
        if provider == 'groq':
            return os.getenv('GROQ_API_KEY')
        elif provider == 'openai':
            key = os.getenv('OPENAI_API_KEY')
            if not key:
                logger.warning("OPENAI_API_KEY not set, LLM features will be disabled")
            return key
        elif provider == 'anthropic':
            return os.getenv('ANTHROPIC_API_KEY')
        return None
    
    def _get_default_model(self, provider):
        """Get default model for provider"""
        if provider == 'groq':
            return os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
        elif provider == 'openai':
            return os.getenv('OPENAI_MODEL', 'gpt-4.1-mini-2025-04-14')
        elif provider == 'anthropic':
            return 'claude-3-5-sonnet-20241022'
        elif provider == 'local':
            return 'llama-3.2-vision'
        return None
    
    def _initialize_client(self):
        """Initialize provider-specific client"""
        if self.provider == 'groq':
            try:
                from groq import Groq
                return Groq(api_key=self.api_key)
            except ImportError:
                logger.error("groq package not installed. Run: pip install groq")
                return None
        elif self.provider == 'openai':
            if not self.api_key:
                logger.warning("OpenAI API key not available, client will not be initialized")
                return None
            try:
                from openai import OpenAI
                return OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("openai package not installed. Run: pip install openai")
                return None
        elif self.provider == 'anthropic':
            try:
                import anthropic
                return anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.error("anthropic package not installed. Run: pip install anthropic")
                return None
        elif self.provider == 'local':
            return None
        return None

    def _setup_fallback(self):
        """Setup fallback provider (OpenAI as secondary)"""
        if self.provider == 'groq' and os.getenv('OPENAI_API_KEY'):
            try:
                from openai import OpenAI
                self.fallback_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                self.fallback_model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini-2025-04-14')
                logger.info("LLM: Fallback to OpenAI configured")
            except Exception as e:
                logger.warning(f"LLM: Could not setup fallback: {e}")
    
    async def complete(self, prompt, image=None, max_tokens=None):
        """
        Send prompt to LLM and get response with fallback
        Returns: Parsed JSON response or dict
        """
        # Use env variable or default to 1024
        if max_tokens is None:
            max_tokens = int(os.getenv('MAX_TOKENS', 1024))
        
        logger.info(f"LLM: [{datetime.now().strftime('%H:%M:%S')}] Sending request to {self.provider}")
        
        # New way: use factory provider
        if self.use_factory:
            try:
                return await self._provider_instance.complete(prompt, max_tokens=max_tokens)
            except Exception as e:
                logger.error(f"LLM: Provider failed: {e}")
                return {'error': str(e)}
        
        # Old way: backward compatibility
        if not self.client:
            logger.error(f"LLM client not initialized for provider: {self.provider}")
            return {'error': 'LLM client not available'}
        
        try:
            if self.provider == 'groq':
                return await self._complete_groq(prompt, image, max_tokens)
            elif self.provider == 'openai':
                return await self._complete_openai(prompt, image, max_tokens)
            elif self.provider == 'anthropic':
                return await self._complete_anthropic(prompt, image, max_tokens)
            elif self.provider == 'local':
                return await self._complete_local(prompt, image, max_tokens)
        except Exception as e:
            logger.error(f"LLM: Primary provider failed: {e}")
            
            # Try fallback if available
            if self.fallback_client:
                logger.info(f"LLM: Attempting fallback to OpenAI")
                try:
                    return await self._complete_openai_fallback(prompt, image, max_tokens)
                except Exception as fallback_error:
                    logger.error(f"LLM: Fallback also failed: {fallback_error}")
            
            return {'error': str(e)}
    
    async def _complete_anthropic(self, prompt, image, max_tokens):
        """Complete using Anthropic Claude"""
        messages = []
        
        # Build message content
        content = []
        
        if image:
            # Convert image bytes to base64
            if isinstance(image, bytes):
                image_b64 = base64.b64encode(image).decode('utf-8')
            else:
                image_b64 = image
            
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_b64
                }
            })
        
        content.append({
            "type": "text",
            "text": prompt
        })
        
        messages.append({
            "role": "user",
            "content": content
        })
        
        # Call Claude API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages
        )
        
        # Extract text response
        response_text = response.content[0].text
        
        # Try to parse as JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Return as text if not JSON
            return {'text': response_text}
    
    async def _complete_openai(self, prompt, image, max_tokens):
        """Complete using OpenAI GPT-4"""
        messages = []
        
        content = []
        
        if image:
            # Convert image to base64 data URL
            if isinstance(image, bytes):
                image_b64 = base64.b64encode(image).decode('utf-8')
            else:
                image_b64 = image
            
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_b64}"
                }
            })
        
        content.append({
            "type": "text",
            "text": prompt
        })
        
        messages.append({
            "role": "user",
            "content": content
        })
        
        # Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        response_text = response.choices[0].message.content
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {'text': response_text}
    
    async def _complete_groq(self, prompt, image, max_tokens):
        """Complete using Groq (text-only, no vision)"""
        # Groq doesn't support vision yet, so ignore image
        if image:
            logger.warning("LLM: Groq doesn't support vision, proceeding with text-only")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that ALWAYS responds with valid, complete JSON. Never truncate your response."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        response_text = response.choices[0].message.content
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"LLM: Failed to parse JSON: {e}")
            logger.error(f"LLM: Response text: {response_text[:500]}...")
            return {'text': response_text, 'error': 'Invalid JSON response'}
    
    async def _complete_openai_fallback(self, prompt, image, max_tokens):
        """Complete using OpenAI fallback client"""
        messages = []
        content = []
        
        if image:
            if isinstance(image, bytes):
                image_b64 = base64.b64encode(image).decode('utf-8')
            else:
                image_b64 = image
            
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_b64}"}
            })
        
        content.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": content})
        
        response = self.fallback_client.chat.completions.create(
            model=self.fallback_model,
            max_tokens=max_tokens,
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        response_text = response.choices[0].message.content
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {'text': response_text}
    
    async def _complete_local(self, prompt, image, max_tokens):
        """Complete using local LLM (Ollama/LM Studio)"""
        logger.warning("Local LLM not implemented yet")
        return {'error': 'Local LLM not implemented'}


class MockLLMClient:
    """Mock LLM client for testing without API calls"""
    
    async def complete(self, prompt, image=None, max_tokens=2000):
        """Return mock responses based on prompt keywords"""
        logger.info("MOCK LLM: Generating mock response")
        
        if 'checkout' in prompt.lower():
            return {
                "reasoning": "Mock: Found checkout button in center of page",
                "confidence": 0.85,
                "actions": [
                    {"action": "click_element", "params": {"selector": "Checkout", "method": "text"}},
                    {"action": "wait", "params": {"seconds": 2}}
                ]
            }
        elif 'guest' in prompt.lower():
            return {
                "reasoning": "Mock: Guest checkout button visible",
                "confidence": 0.9,
                "actions": [
                    {"action": "click_element", "params": {"selector": "Continue as Guest", "method": "text"}}
                ]
            }
        elif 'email' in prompt.lower() or 'contact' in prompt.lower():
            return {
                "reasoning": "Mock: Contact form detected",
                "confidence": 0.8,
                "actions": [
                    {"action": "fill_field", "params": {"field_type": "email", "value": "{{email}}"}},
                    {"action": "fill_field", "params": {"field_type": "firstName", "value": "{{firstName}}"}},
                    {"action": "fill_field", "params": {"field_type": "lastName", "value": "{{lastName}}"}}
                ]
            }
        elif 'address' in prompt.lower() or 'shipping' in prompt.lower():
            return {
                "reasoning": "Mock: Shipping address form detected",
                "confidence": 0.85,
                "actions": [
                    {"action": "fill_field", "params": {"field_type": "addressLine1", "value": "{{addressLine1}}"}},
                    {"action": "fill_field", "params": {"field_type": "city", "value": "{{city}}"}},
                    {"action": "select_dropdown", "params": {"field_type": "province", "value": "{{province}}"}},
                    {"action": "fill_field", "params": {"field_type": "postalCode", "value": "{{postalCode}}"}}
                ]
            }
        elif 'failed' in prompt.lower() or 'alternative' in prompt.lower():
            return {
                "reasoning": "Mock: Suggesting alternative selector",
                "root_cause": "wrong_selector",
                "alternative_action": {
                    "action": "click_element",
                    "params": {"selector": "button.checkout-btn", "method": "css"}
                }
            }
        else:
            return {
                "reasoning": "Mock: Generic response",
                "confidence": 0.5,
                "actions": [
                    {"action": "wait", "params": {"seconds": 1}}
                ]
            }
