
import asyncio
import os
import sys
import tempfile
from playwright.async_api import async_playwright

# WINDOWS FIX
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    print("🚀 Verifying System Chrome Launch...")
    
    async with async_playwright() as p:
        profile_path = tempfile.mkdtemp(prefix='verify_chrome_')
        print(f"Temp Profile: {profile_path}")
        
        try:
            # 1. Try launching with channel='chrome'
            print("\nAttempting to launch with channel='chrome'...")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                channel='chrome',
                headless=True, # Headless for quick check
                args=['--no-sandbox']
            )
            
            page = context.pages[0]
            
            # 2. Get Browser Info
            version = p.chromium.executable_path
            # Note: launch_persistent_context returns a BrowserContext, getting executable path is tricky directly if it's not exposed easily, 
            # but we can infer from success.
            # actually p.chromium.executable_path might return the bundled one.
            
            # Let's check navigator.userAgent
            ua = await page.evaluate("navigator.userAgent")
            print(f"✅ Launched Successfully!")
            print(f"User Agent: {ua}")
            
            # Try to identify if it is really chrome
            # Chrome usually has "Google Chrome" in branding?
            
            print("Closing...")
            await context.close()
            
        except Exception as e:
            print(f"❌ Failed to launch channel='chrome': {e}")
            print("This implies Google Chrome is NOT installed or not found by Playwright.")

            # Check for executable paths manually
            paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
            ]
            print("\nChecking common paths:")
            found_any = False
            for path in paths:
                exists = os.path.exists(path)
                print(f"  {path}: {'✅ FOUND' if exists else '❌ NOT FOUND'}")
                if exists: found_any = True
                
            if found_any:
                print("Chrome is installed but Playwright didn't find it via channel='chrome'. We might need to specify executable_path manually.")
            else:
                print("Google Chrome does not appear to be installed in standard locations.")

if __name__ == "__main__":
    asyncio.run(main())
