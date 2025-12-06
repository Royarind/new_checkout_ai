
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

class CheckoutConfig:
    """
    Central configuration management for Checkout AI.
    Handles environment variables, paths, and API keys.
    """
    
    @staticmethod
    def get_openai_api_key():
        return os.getenv("OPENAI_API_KEY")
    
    @staticmethod
    def get_project_root():
        # Assuming this file is in src/checkout_ai/core/config.py
        # Root is 3 levels up: src/checkout_ai/core/ -> src/checkout_ai/ -> src/ -> root
        return Path(__file__).parent.parent.parent.parent

# Legacy support
class LoadConfig:
    """
    Legacy configuration loader for backward compatibility.
    """
    @staticmethod
    def load():
        return CheckoutConfig()
