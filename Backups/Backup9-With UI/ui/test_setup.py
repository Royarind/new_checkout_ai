"""Test CHKout.ai Setup"""

import sys
import os

print("="*60)
print("🧪 Testing CHKout.ai Setup")
print("="*60)
print()

# Test 1: Check Python version
print("1. Checking Python version...")
if sys.version_info >= (3, 8):
    print(f"   ✅ Python {sys.version_info.major}.{sys.version_info.minor} (OK)")
else:
    print(f"   ❌ Python {sys.version_info.major}.{sys.version_info.minor} (Need 3.8+)")
    sys.exit(1)

# Test 2: Check dependencies
print("\n2. Checking dependencies...")
try:
    import dash
    print(f"   ✅ dash {dash.__version__}")
except ImportError:
    print("   ❌ dash not installed")
    print("      Run: pip install -r requirements.txt")

try:
    import dash_bootstrap_components as dbc
    print(f"   ✅ dash-bootstrap-components")
except ImportError:
    print("   ❌ dash-bootstrap-components not installed")

try:
    from playwright.async_api import async_playwright
    print(f"   ✅ playwright")
except ImportError:
    print("   ❌ playwright not installed")

# Test 3: Check project structure
print("\n3. Checking project structure...")
required_files = [
    'app.py',
    'config.py',
    'assets/style.css',
    'components/chat_panel.py',
    'components/info_cards.py',
    'services/conversation_agent.py',
    'services/variant_detector.py',
    'services/screenshot_service.py'
]

for file in required_files:
    if os.path.exists(file):
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} missing")

# Test 4: Check parent project files
print("\n4. Checking parent project...")
parent_files = [
    '../agent/llm_client.py',
    '../phase1/universal_dom_finder.py',
    '../phase2/checkout_flow.py',
    '../.env'
]

for file in parent_files:
    if os.path.exists(file):
        print(f"   ✅ {file}")
    else:
        print(f"   ⚠️  {file} missing (may cause issues)")

# Test 5: Check .env
print("\n5. Checking environment variables...")
sys.path.append('..')
try:
    from dotenv import load_dotenv
    load_dotenv('../.env')
    
    groq_key = os.getenv('GROQ_API_KEY')
    if groq_key:
        print(f"   ✅ GROQ_API_KEY found")
    else:
        print(f"   ⚠️  GROQ_API_KEY not found in .env")
except Exception as e:
    print(f"   ⚠️  Could not load .env: {e}")

# Test 6: Test LLM client
print("\n6. Testing LLM client...")
try:
    sys.path.append('..')
    from agent.llm_client import LLMClient
    print("   ✅ LLMClient imported successfully")
except Exception as e:
    print(f"   ❌ LLMClient import failed: {e}")

print("\n" + "="*60)
print("✅ Setup test complete!")
print("="*60)
print("\nTo start CHKout.ai:")
print("  ./run.sh")
print("  OR")
print("  python app.py")
print("\nThen open: http://localhost:8050")
print("="*60)
