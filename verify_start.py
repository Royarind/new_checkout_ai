
import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"CWD: {os.getcwd()}")

try:
    import playwright
    print(f"Playwright imported successfully")
except ImportError:
    print("Playwright NOT installed")

try:
    import playwright_stealth
    print(f"Stealth found at: {playwright_stealth.__file__}")
except ImportError as e:
    print(f"Stealth IMPORT ERROR: {e}")
    
# Test the actual import used in main_orchestrator
try:
    from playwright_stealth import stealth_async
    print("Successfully imported stealth_async")
except ImportError as e:
    print(f"Failed to import stealth_async: {e}")
