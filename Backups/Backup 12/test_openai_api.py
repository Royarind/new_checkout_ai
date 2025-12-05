#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini-2024-07-18')

print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
print(f"Model: {model}")
print("\nTesting OpenAI API connection...")

try:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say 'API is working' if you can read this."}],
        max_tokens=20
    )
    print(f"\n✅ SUCCESS! Response: {response.choices[0].message.content}")
    print(f"Model used: {response.model}")
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
