#!/usr/bin/env python3

import json
import asyncio
import html
import re
from automation_engine import ProductVariant, WebsiteDetails, ProductVariantAutomator
from special_sites.farfetch_automator import FarfetchAutomator
from special_sites.zara_automator import ZaraAutomator

def validate_selection(dom_content, expected_value):
    """Utility to validate selected variant in DOM content"""
    sections = re.findall(r'<section>.*?<input[^>]*name="pdp_swatch"[^>]*>(.*?)</section>', dom_content, re.DOTALL)
    
    for section in sections:
        if 'checked=""' in section:
            alt_match = re.search(r'alt="([^"]+)"', section)
            if alt_match:
                return alt_match.group(1).lower() == expected_value.lower()
    return False

def detect_website_type(url):
    """Detect website type for specialized automation"""
    if 'farfetch.com' in url.lower():
        return 'farfetch'
    elif 'zara.com' in url.lower():
        return 'zara'
    return 'generic'

async def automate_from_json(payload):
    """Automate product selection from JSON payload with site-specific handling"""
    
    # Extract data from payload
    url = payload.get('url')
    quantity = payload.get('quantity', 1)
    selected_variant = payload.get('selectedVariant', {})
    
    print(f"URL: {url}")
    print(f"Quantity: {quantity}")
    print(f"Variants: {selected_variant}")
    
    # Detect website type
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
            # Navigate to product page
            await page.goto(url)
            
            automator = FarfetchAutomator()
            
            # Select variants
            for variant_type, variant_value in selected_variant.items():
                print(f"Selecting {variant_type}: {variant_value}")
                success = await automator.select_variant(page, variant_type, variant_value)
                if not success:
                    print(f"Failed to select {variant_type}: {variant_value}")
                    return False
                await asyncio.sleep(1)
            
            # Add to cart
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
    
    # Decode HTML entities in URL
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
            # Try with domcontentloaded first, then fallback
            try:
                await page.goto(clean_url, timeout=45000, wait_until='domcontentloaded')
                print("✅ Page loaded with domcontentloaded")
            except:
                print("⚠️ Trying with load event...")
                await page.goto(clean_url, timeout=30000, wait_until='load')
                print("✅ Page loaded with load event")
            
            automator = ZaraAutomator(page)
            
            # Process color first
            if 'color' in selected_variant:
                print(f"Selecting color: {selected_variant['color']}")
                result = await automator.select_color(selected_variant['color'])
                print(result.get('content', ''))
                if not result.get('success'):
                    print(f"Failed to select color: {selected_variant['color']}")
                    return False
                await asyncio.sleep(2)
            
            # Set quantity if needed
            if quantity > 1:
                print(f"Setting quantity: {quantity}")
                # Use generic quantity setting for now
                await page.fill('input[type="number"]', str(quantity))
                await asyncio.sleep(1)
            
            # Use universal DOM finder for ADD button
            print("Looking for ADD button with universal DOM finder...")
            from phase1.universal_dom_finder import find_variant_dom
            
            # Try to find and click ADD button
            add_result = await find_variant_dom(page, 'add_to_cart', 'add')
            
            if not add_result or not add_result.get('success'):
                print("Failed to find ADD button with universal finder")
                return False
            
            print("✅ ADD button clicked with universal finder")
            await asyncio.sleep(3)
            
            # Select size after ADD
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
    # Create ProductVariant with dynamic variant handling
    variant = ProductVariant(quantity=quantity)
    
    # Map common variants to dedicated fields if they exist
    if 'color' in selected_variant:
        variant.color = selected_variant['color']
    if 'size' in selected_variant:
        variant.size = selected_variant['size']
    if 'fit' in selected_variant:
        variant.fit = selected_variant['fit']
    if 'length' in selected_variant:
        variant.length = selected_variant['length']
    
    # Add ALL variants (including mapped ones) to custom_variants for processing
    variant.custom_variants = selected_variant.copy()
    
    # Create website details
    website_details = WebsiteDetails(
        url=url,
        variant=variant
    )
    
    # Run automation using only custom_variants (dynamic approach)
    automator = ProductVariantAutomator()
    success = await automator.automate_product_selection_dynamic(website_details)
    
    return success

async def main():
    """Main function that accepts JSON input"""
    
    print("=== Product Automation System ===")
    
    # Get JSON input from user
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
        
        # Parse JSON (decode HTML entities and fix common issues)
        decoded_input = html.unescape(json_input)
        
        # Fix missing closing brace if needed
        if decoded_input.count('{') > decoded_input.count('}'):
            decoded_input += '}'
        
        payload = json.loads(decoded_input)
        
        # Validate required fields
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
        
        # Run automation
        success = await automate_from_json(payload)
        
        if success:
            print("\nSUCCESS: JSON automation completed successfully!")
        else:
            print("\nERROR: JSON automation failed!")
            
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON format: {e}")
        print("\nTry this valid JSON:")
        print('{"url": "https://www.abercrombie.com/shop/wd/p/cinched-fleece-sweatpants-46667321?categoryId=12202&faceout=model&seq=62", "quantity": 3, "selectedVariant": {"color": "burgundy", "size": "M", "length": "Long"}}')
    except KeyboardInterrupt:
        print("\n👋 Automation cancelled by user")
    except Exception as e:
        print(f"ERROR: Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())