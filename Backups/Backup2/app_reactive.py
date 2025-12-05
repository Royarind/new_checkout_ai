#!/usr/bin/env python3
"""
Reactive Agent Demo - Full checkout with observe-reason-act loop
"""

import json
import asyncio
import html
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from agent.reactive_agent_factory import create_reactive_agent

load_dotenv()


async def run_reactive_checkout(payload):
    """Run checkout with reactive agent"""
    customer = payload['customer']
    tasks = payload.get('tasks', [])
    
    if not tasks:
        print("ERROR: No tasks provided")
        return False
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--no-sandbox'],
            slow_mo=500
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            # Phase 1: Add to cart (using existing logic)
            for i, task in enumerate(tasks):
                print(f"\n=== Task {i + 1}/{len(tasks)} ===")
                url = task['url']
                quantity = task.get('quantity', 1)
                selected_variant = task.get('selectedVariant', {})
                
                print(f"URL: {url}")
                print(f"Variants: {selected_variant}")
                
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(2)
                
                # Analyze page and clear viewport before variant selection
                from shared.popup_dismisser import dismiss_popups
                from shared.page_analyzer import analyze_page_content
                
                print("⏳ Analyzing page and clearing viewport...")
                for attempt in range(8):
                    analysis = await analyze_page_content(page)
                    
                    if analysis['hasBlockingOverlay']:
                        print(f"  Overlay detected (attempt {attempt + 1}): {len(analysis['overlayInfo'])} overlays")
                        await dismiss_popups(page)
                        await asyncio.sleep(0.5)
                        try:
                            await page.mouse.click(50, 50)
                            await asyncio.sleep(0.5)
                        except:
                            pass
                    else:
                        print("✅ Viewport clear - page ready")
                        break
                    
                    await asyncio.sleep(1.5)
                
                await asyncio.sleep(1)
                
                # Select variants
                from phase1.universal_dom_finder import find_variant_dom
                for variant_type, variant_value in selected_variant.items():
                    print(f"Selecting {variant_type}: {variant_value}")
                    result = await find_variant_dom(page, variant_type, variant_value)
                    if result.get('success'):
                        print(f"✅ {variant_type} selected")
                    await asyncio.sleep(1)
                
                # Set quantity if > 1
                if quantity > 1:
                    print(f"Setting quantity to {quantity}...")
                    qty_set = await page.evaluate(f"""
                        (qty) => {{
                            const selectors = [
                                'input[name="quantity"]', 'input[id*="quantity" i]', 'input[id*="qty" i]',
                                'select[name="quantity"]', 'select[id*="quantity" i]', 'select[id*="qty" i]',
                                'input[type="number"]'
                            ];
                            for (const sel of selectors) {{
                                const el = document.querySelector(sel);
                                if (el) {{
                                    if (el.tagName === 'SELECT') {{
                                        el.value = qty;
                                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    }} else {{
                                        el.value = qty;
                                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    }}
                                    return true;
                                }}
                            }}
                            return false;
                        }}
                    """, quantity)
                    if qty_set:
                        print(f"✅ Quantity set to {quantity}")
                    else:
                        print(f"⚠️  Could not find quantity selector")
                    await asyncio.sleep(1)
                
                # Add to cart
                from phase1.add_to_cart_robust import add_to_cart_robust
                print("Adding to cart...")
                cart_result = await add_to_cart_robust(page)
                if not cart_result.get('success'):
                    print("❌ Failed to add to cart")
                    return False
                print("✅ Added to cart")
                await asyncio.sleep(2)
            
            # Navigate to checkout page immediately
            print("\n🛒 Navigating to checkout...")
            from phase2.checkout_flow import proceed_to_checkout
            from shared.page_analyzer import wait_for_page_ready
            
            checkout_result = await proceed_to_checkout(page)
            if not checkout_result.get('success'):
                print("❌ Failed to navigate to checkout")
                return False
            print("✅ On checkout page")
            
            print("⏳ Waiting for checkout page to load...")
            await wait_for_page_ready(page, timeout=10)
            await asyncio.sleep(2)
            
            # Phase 2: Reactive agent for checkout form filling
            print("\n" + "="*60)
            print("STARTING REACTIVE AGENT FOR CHECKOUT FORM")
            print("="*60)
            
            await page.wait_for_load_state('domcontentloaded')
            
            agent = create_reactive_agent(page, use_mock=False)
            
            goal = f"""Complete the checkout form:
1. Select guest checkout if needed
2. Fill contact information (email: {customer['contact']['email']}, name: {customer['contact']['firstName']} {customer['contact']['lastName']})
3. Fill shipping address ({customer['shippingAddress']['addressLine1']}, {customer['shippingAddress']['city']}, {customer['shippingAddress']['province']} {customer['shippingAddress']['postalCode']}, {customer['shippingAddress']['country']})
4. Select cheapest shipping method
5. Proceed to payment page (stop before entering payment details)
"""
            
            result = await agent.run(goal, customer)
            
            if result['success']:
                print(f"\n✅ Reactive agent completed checkout in {result['iterations']} iterations!")
                print("Browser will stay open for 30 seconds...")
                await asyncio.sleep(30)
                await browser.close()
                return True
            else:
                print(f"\n❌ Reactive agent failed: {result.get('error')}")
                print("Browser will stay open for inspection...")
                await asyncio.sleep(60)
                await browser.close()
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            await browser.close()
            return False


async def main():
    print("=== Reactive Agent Checkout System ===")
    
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
        payload = json.loads(decoded_input)
        
        if 'customer' not in payload:
            print("ERROR: 'customer' field is required!")
            return
        
        print(f"\n📋 Customer: {payload['customer']['contact']['firstName']} {payload['customer']['contact']['lastName']}")
        print(f"Tasks: {len(payload.get('tasks', []))}")
        print()
        
        success = await run_reactive_checkout(payload)
        
        if success:
            print("\n✅ SUCCESS: Reactive checkout completed!")
        else:
            print("\n❌ FAILED: Reactive checkout failed!")
            
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON format: {e}")
    except KeyboardInterrupt:
        print("\n👋 Cancelled by user")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
