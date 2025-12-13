
import sys
import subprocess
import os

def install_package(package):
    print(f"Installing {package} using {sys.executable}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"Successfully installed {package}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package}: {e}")

if __name__ == "__main__":
    install_package("playwright-stealth")
    
    # Verify import
    try:
        import playwright_stealth
        print(f"Verified import: {playwright_stealth.__file__}")
    except ImportError as e:
        print(f"Import failed after install: {e}")
