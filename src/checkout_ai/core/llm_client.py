
import json
from src.checkout_ai.core.utils.openai_client import get_client

class LLMClient:
    def __init__(self, config=None):
        self.client = get_client()
        
    async def complete(self, prompt, max_tokens=500):
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"LLM Error: {e}")
            return {}
