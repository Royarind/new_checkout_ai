
import asyncio
import os
import sys
import tempfile
from playwright.async_api import async_playwright

# WINDOWS FIX
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    print("🚀 Starting Debug Script...")
    
    # 1. Config
    url = "https://www.meesho.com/mens-kurta-pyjama-lackhnavi-work-mens-premium-style-chikankari-cotton-rayon-embroidery-lakhnavi-work-kurta-with-white-pyjama-pair/p/6xzfby"
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    # 2. Launch
    print("launching playwright...")
    async with async_playwright() as p:
        profile_path = tempfile.mkdtemp(prefix='debug_chrome_')
        print(f"Profile: {profile_path}")
        
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                user_agent=user_agent,
                headless=False,
                channel='chrome', # Try explicit channel first
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--exclude-switches=enable-automation',
                    '--disable-infobars',
                    '--start-maximized'
                ]
            )
            print("Browser launched.")
            
            page = context.pages[0] if context.pages else await context.new_page()
            
            # 3. Apply Stealth
            try:
                from playwright_stealth import stealth_async
                print("Applying stealth...")
                await stealth_async(page)
                print("Stealth applied.")
            except ImportError:
                print(f"Stealth not installed. Python: {sys.executable}")
                print(f"Path: {sys.path}")
            except Exception as e:
                print(f"Error applying stealth: {e}")

            # 4. Navigate
            print(f"Navigating to {url}...")
            await page.goto(url, timeout=60000)
            print("Navigation complete.")
            
            # Keep open for a bit
            print("Waiting 30 seconds...")
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            print("Closing...")
            # await context.close()

if __name__ == "__main__":
    asyncio.run(main())
