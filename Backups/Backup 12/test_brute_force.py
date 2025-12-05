#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright
from phase1.universal_dom_finder import find_variant_dom

async def test_brute_force():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            channel='chrome',
            slow_mo=500
        )
        
        page = await browser.new_page()
        
        # Test URL
        await page.goto('https://www.uniqlo.com/us/en/products/E422992-000/00?colorDisplayCode=00&sizeDisplayCode=004')
        await asyncio.sleep(3)
        
        # Create selector instance
        selector = find_variant_dom()
        
        # Test visual brute-force for color
        print("\n" + "="*60)
        print("Testing visual brute-force for color: slate grey")
        print("="*60)
        
        result = await selector.discovery_mode(page, 'color', 'Pink')
        
        print("\n" + "="*60)
        if result['success']:
            print(f"✅ SUCCESS: {result.get('content')}")
            print(f"Method: {result.get('method')}")
        else:
            print(f"❌ FAILED: {result.get('content', 'No match found')}")
        print("="*60)
        
        # Keep browser open to see result
        input("\nPress Enter to close browser...")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_brute_force())
