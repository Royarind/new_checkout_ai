#!/usr/bin/env python3

import json
import asyncio
import html
import re
from checkout_ai.legacy.automation_engine import ProductVariant, WebsiteDetails, ProductVariantAutomator
from checkout_ai.legacy.phase2.checkout_flow import run_checkout_flow

# def validate_selection(dom_content, expected_value):
#     """Utility to validate selected variant in DOM content"""
#     sections = re.findall(r'<section>.*?<input[^>]*name="pdp_swatch"[^>]*>(.*?)</section>', dom_content, re.DOTALL)
    
#     for section in sections:
#         if 'checked=""' in section:
#             alt_match = re.search(r'alt="([^"]+)"', section)
#             if alt_match:
#                 return alt_match.group(1).lower() == expected_value.lower()
#     return False


from bs4 import BeautifulSoup

def validate_selection(dom_content: str, expected_value: str, variant_type: str = None) -> bool:
    """Robust validation using proper HTML parsing"""
    soup = BeautifulSoup(dom_content, 'html.parser')
    
    # Strategy 1: Look for checked swatch inputs
    checked_swatches = soup.find_all('input', {'name': 'pdp_swatch', 'checked': True})
    
    for swatch in checked_swatches:
        # Check multiple attribute sources for the value
        possible_sources = [
            swatch.get('alt'),
            swatch.get('title'),
            swatch.get('data-value'),
            swatch.get('value'),
            # Also check parent elements for text content
            swatch.find_parent('label').get_text(strip=True) if swatch.find_parent('label') else None,
            swatch.find_previous_sibling('span').get_text(strip=True) if swatch.find_previous_sibling('span') else None
        ]
        
        for source in possible_sources:
            if source and expected_value.lower() in source.lower():
                return True
    
    # Strategy 2: Look for visual selection indicators
    selected_indicators = soup.find_all(class_=['selected', 'active', 'is-selected'])
    for indicator in selected_indicators:
        indicator_text = indicator.get_text(strip=True).lower()
        if expected_value.lower() in indicator_text:
            return True
    
    return False

def detect_website_type(url):
    """Detect website type for specialized automation"""
    url_lower = url.lower()
    if 'farfetch.com' in url_lower:
        return 'farfetch'
    elif 'zara.com' in url_lower:
        return 'zara'
    elif 'heydude.com' in url_lower:
        return 'heydude'
    elif 'dillards.com' in url_lower:
        return 'dillards'
    elif 'karllagerfeld.com' in url_lower:
        return 'karllagerfeld'
    elif 'patagonia.com' in url_lower:
        return 'patagonia'
    return 'generic'

async def automate_from_json(payload):
    """Automate product selection from JSON payload with site-specific handling"""
    
    # Check if this is full checkout flow (has customer data)
    if 'customer' in payload:
        return await automate_full_checkout(payload)
    
    # Phase 1 only (legacy)
    url = payload.get('url')
    quantity = payload.get('quantity', 1)
    selected_variant = payload.get('selectedVariant', {})
    
    print(f"URL: {url}")
    print(f"Quantity: {quantity}")
    print(f"Variants: {selected_variant}")
    
    site_type = detect_website_type(url)
    print(f"Site Type: {site_type}")
    print()
    
    if site_type == 'farfetch':
        return await automate_farfetch(url, selected_variant)
    elif site_type == 'zara':
        return await automate_zara(url, quantity, selected_variant)
    else:
        return await automate_generic(url, quantity, selected_variant)

async def automate_farfetch(url, selected_variant):
    """Specialized Farfetch automation"""
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        await stealth_async(page)
        
        try:
            await page.goto(url)
            automator = FarfetchAutomator()
            
            for variant_type, variant_value in selected_variant.items():
                print(f"Selecting {variant_type}: {variant_value}")
                success = await automator.select_variant(page, variant_type, variant_value)
                if not success:
                    print(f"Failed to select {variant_type}: {variant_value}")
                    return False
                await asyncio.sleep(1)
            
            print("Adding to cart...")
            cart_success = await automator.add_to_cart(page)
            
            if cart_success:
                print("✅ Farfetch automation completed successfully!")
                return True
            else:
                print("❌ Failed to add to cart")
                return False
                
        except Exception as e:
            print(f"❌ Farfetch automation error: {e}")
            return False
        finally:
            await browser.close()

async def automate_zara(url, quantity, selected_variant):
    """Specialized Zara automation"""
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async
    
    clean_url = html.unescape(url)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        await stealth_async(page)
        
        try:
            print(f"Navigating to: {clean_url}")
            try:
                await page.goto(clean_url, timeout=45000, wait_until='domcontentloaded')
                print("✅ Page loaded with domcontentloaded")
            except:
                print("⚠️ Trying with load event...")
                await page.goto(clean_url, timeout=30000, wait_until='load')
                print("✅ Page loaded with load event")
            
            automator = ZaraAutomator(page)
            
            if 'color' in selected_variant:
                print(f"Selecting color: {selected_variant['color']}")
                result = await automator.select_color(selected_variant['color'])
                print(result.get('content', ''))
                if not result.get('success'):
                    print(f"Failed to select color: {selected_variant['color']}")
                    return False
                await asyncio.sleep(2)
            
            if quantity > 1:
                print(f"Setting quantity: {quantity}")
                await page.fill('input[type="number"]', str(quantity))
                await asyncio.sleep(1)
            
            print("Looking for ADD button with universal DOM finder...")
            from checkout_ai.dom.service import UniversalDOMFinder
            
            # Assuming find_variant_dom is now a static method of UniversalDOMFinder or needs to be instantiated
            # Based on previous pattern, we might need to adjust usage too.
            # But earlier I aliased it: from checkout_ai.dom.service import UniversalDOMFinder as find_variant_dom
            # Let's check how I moved it. I moved the file.
            # If the file had `async def find_variant_dom(...)`, it still has it.
            # So I can import it from module.
            from checkout_ai.dom.service import UniversalDOMFinder as find_variant_dom
            
            add_result = await find_variant_dom(page, 'add_to_cart', 'add')
            
            if not add_result or not add_result.get('success'):
                print("Failed to find ADD button with universal finder")
                return False
            
            print("✅ ADD button clicked with universal finder")
            await asyncio.sleep(3)
            
            if 'size' in selected_variant:
                print(f"Selecting size: {selected_variant['size']}")
                size_result = await automator.select_size_after_add(selected_variant['size'])
                print(size_result.get('content', ''))
                if not size_result.get('success'):
                    print(f"Failed to select size: {selected_variant['size']}")
                    return False
            
            print("✅ Zara automation completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Zara automation error: {e}")
            return False
        finally:
            await browser.close()

async def automate_generic(url, quantity, selected_variant):
    """Generic automation for other sites"""
    variant = ProductVariant(quantity=quantity)
    
    if 'color' in selected_variant:
        variant.color = selected_variant['color']
    if 'size' in selected_variant:
        variant.size = selected_variant['size']
    if 'fit' in selected_variant:
        variant.fit = selected_variant['fit']
    if 'length' in selected_variant:
        variant.length = selected_variant['length']
    
    variant.custom_variants = selected_variant.copy()
    
    website_details = WebsiteDetails(
        url=url,
        variant=variant
    )
    
    automator = ProductVariantAutomator()
    success = await automator.automate_product_selection_dynamic(website_details)
    
    return success

async def automate_full_checkout(payload):
    """Full checkout flow: Phase 1 (add to cart) + Phase 2 (checkout) with agent fallback"""
    from playwright.async_api import async_playwright
    from checkout_ai.dom.service import UniversalDOMFinder as find_variant_dom
    from checkout_ai.legacy.phase1.add_to_cart_robust import add_to_cart_robust
    from checkout_ai.legacy.phase1.cart_navigator import navigate_to_cart
    from checkout_ai.agents.legacy_adapter import create_agent_system
    
    customer = payload['customer']
    tasks = payload.get('tasks', [])
    
    if not tasks:
        print("ERROR: No tasks provided")
        return False
    
    max_retries = 3
    
    for retry in range(max_retries):
        if retry > 0:
            print(f"\n=== Retry {retry}/{max_retries - 1} ===")
        
        async with async_playwright() as p:
            # Use persistent context with real Chrome
            profile_path = '/tmp/checkout_ai_chrome_profile'
            print(f"Launching Chrome with persistent profile at {profile_path}...")
            
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                channel='chrome',
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--exclude-switches=enable-automation',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                    '--disable-features=UserAgentClientHint',
                    '--use-fake-ui-for-media-stream',
                    '--use-fake-device-for-media-stream',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    # Popup and modal blocking
                    '--disable-popup-blocking',
                    '--disable-notifications',
                    '--disable-infobars',
                    '--disable-extensions',
                    '--disable-default-apps',
                    '--no-first-run',
                    '--disable-features=TranslateUI',
                    '--disable-features=Translate',
                    '--disable-component-extensions-with-background-pages'
                ],
                viewport={'width': 1280, 'height': 720},
                permissions=[],  # Grant no permissions
                geolocation={'latitude': 0, 'longitude': 0},  # Provide fake geolocation to avoid prompt
                ignore_https_errors=True,
                slow_mo=1000
            )
            
            # Get the first page (or create one if none exists)
            if len(context.pages) > 0:
                page = context.pages[0]
            else:
                page = await context.new_page()
            
            # Initialize agent system (use_mock=False for real LLM)
            agent_coordinator = create_agent_system(page, use_mock=False)
            print("✅ Agent system initialized (Groq primary, OpenAI fallback)")
        
            try:
                # Phase 1: Process all tasks
                for i, task in enumerate(tasks):
                    print(f"\n=== Task {i + 1}/{len(tasks)} ===")
                    url = task['url']
                    quantity = task.get('quantity', 1)
                    selected_variant = task.get('selectedVariant', {})
                    
                    print(f"URL: {url}")
                    print(f"Quantity: {quantity}")
                    print(f"Variants: {selected_variant}")
                    
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(2)
                    
                    # Dismiss ALL popups before variant selection
                    from shared.popup_dismisser import dismiss_popups
                    print("⏳ Waiting for all popups to close...")
                    for attempt in range(5):
                        dismissed = await dismiss_popups(page)
                        await asyncio.sleep(2)
                        if not dismissed:
                            break
                    print("✅ All popups cleared, starting variant selection")
                    
                    for variant_type, variant_value in selected_variant.items():
                        print(f"Selecting {variant_type}: {variant_value}")
                        for attempt in range(3):
                            result = await find_variant_dom(page, variant_type, variant_value)
                            if result.get('success'):
                                print(f"✅ {variant_type} selected")
                                break
                            print(f"Retry {attempt + 1}/3")
                            await asyncio.sleep(1)
                        await asyncio.sleep(1)
                    
                    if quantity > 1:
                        print(f"Setting quantity: {quantity}")
                        await find_variant_dom(page, 'quantity', str(quantity))
                        await asyncio.sleep(1)
                    
                    print("Adding to cart...")
                    cart_result = await add_to_cart_robust(page)
                    if not cart_result.get('success'):
                        print("❌ Failed to add to cart")
                        return False
                    print("✅ Added to cart")
                    await asyncio.sleep(2)
                
                print("\n=== Navigating to cart ===")
                nav_result = await navigate_to_cart(page)
                if not nav_result.get('success'):
                    print("❌ Failed to navigate to cart")
                    return False
                print("✅ Cart page loaded")
                await asyncio.sleep(2)
                
                # Phase 2: Checkout with agent support
                print("\n=== Starting Phase 2: Checkout (with AI agent fallback) ===")
                checkout_result = await run_checkout_flow(page, customer, agent_coordinator)
            
                if checkout_result['success']:
                    print("\n✅ Full checkout flow completed!")
                    print("Browser will stay open for 120 seconds for inspection...")
                    await asyncio.sleep(120)
                    await context.close()
                    return True
                else:
                    print(f"\n❌ Checkout failed at step: {checkout_result.get('step')}")
                    print(f"Error: {checkout_result.get('error')}")
                    print("Browser will stay open for 180 seconds for debugging...")
                    await asyncio.sleep(180)
                    if retry < max_retries - 1:
                        print(f"Will retry...")
                        await context.close()
                        await asyncio.sleep(2)
                        continue
                    else:
                        print("Max retries reached, keeping browser open...")
                        await asyncio.sleep(120)
                        await context.close()
                        return False
                
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
                print("\nBrowser will stay open for 300 seconds (5 min) for debugging...")
                await asyncio.sleep(300)
                if retry < max_retries - 1:
                    print(f"Will retry...")
                    await context.close()
                    await asyncio.sleep(2)
                    continue
                else:
                    print("Max retries reached, keeping browser open for 2 more minutes...")
                    await asyncio.sleep(120)
                    await context.close()
                    return False
    
    return False

async def main():
    """Main function that accepts JSON input"""
    
    print("=== Product Automation System ===")
    
    try:
        print("Enter JSON payload (press Enter twice when done):")
        lines = []
        while True:
            line = input()
            if line.strip() == "" and lines:
                break
            lines.append(line)
        
        json_input = '\n'.join(lines).strip()
        if not json_input:
            print("ERROR: JSON payload is required!")
            return
        
        decoded_input = html.unescape(json_input)
        
        if decoded_input.count('{') > decoded_input.count('}'):
            decoded_input += '}'
        
        payload = json.loads(decoded_input)
        
        # Check if full checkout or Phase 1 only
        if 'customer' in payload:
            print("\n📋 Full Checkout Flow Detected")
            print(f"Customer: {payload['customer']['contact']['firstName']} {payload['customer']['contact']['lastName']}")
            print(f"Tasks: {len(payload.get('tasks', []))}")
        else:
            if 'url' not in payload:
                print("ERROR: 'url' field is required in JSON payload!")
                return
            
            if 'selectedVariant' not in payload:
                print("ERROR: 'selectedVariant' field is required in JSON payload!")
                return
            
            print(f"\n📋 Processing payload:")
            print(f"URL: {payload.get('url')}")
            print(f"Quantity: {payload.get('quantity', 1)}")
            print(f"Variants: {payload.get('selectedVariant')}")
        
        print()
        
        success = await automate_from_json(payload)
        
        if success:
            print("\nSUCCESS: Automation completed successfully!")
        else:
            print("\nERROR: Automation failed!")
            
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON format: {e}")
    except KeyboardInterrupt:
        print("\n👋 Automation cancelled by user")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
