import requests
import json

# Test the actual API endpoint the frontend calls
url = "http://localhost:8000/api/chat/llm"
data = {"message": "https://www.myntra.com/kurta-sets/varanga/varanga-ethnic-motifs-printed-zari-kurta-with-trouser--dupatta/36904064/buy"}

try:
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Raw response: {result}")
    print(f"Message field: '{result.get('message', '')}'")
    print(f"Message starts with {{: {result.get('message', '').strip().startswith('{')}")
except Exception as e:
    print(f"Error: {e}")