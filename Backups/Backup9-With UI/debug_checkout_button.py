#!/usr/bin/env python3
"""
Debug script to find and analyze PROCEED TO CHECKOUT button
Run this when you're on the cart page to see what buttons are available
"""

import asyncio
from playwright.async_api import async_playwright

async def debug_checkout_button(url):
    """Debug checkout button detection"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print(f"\n{'='*60}")
        print("CHECKOUT BUTTON DEBUGGER")
        print(f"{'='*60}\n")
        
        # Navigate to the URL
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until='domcontentloaded')
        await asyncio.sleep(3)
        
        # Find all buttons on the page
        print("\n" + "="*60)
        print("ANALYZING ALL BUTTONS ON PAGE")
        print("="*60 + "\n")
        
        buttons = await page.evaluate("""
            () => {
                const elements = document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"]');
                const results = [];
                
                elements.forEach((el, index) => {
                    // Check visibility
                    if (!el.offsetParent) return;
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) return;
                    
                    const text = el.textContent?.trim() || '';
                    const ariaLabel = el.getAttribute('aria-label') || '';
                    const className = el.className || '';
                    const id = el.id || '';
                    const disabled = el.disabled || el.getAttribute('disabled') || el.classList.contains('disabled');
                    
                    // Get z-index and modal info
                    const style = window.getComputedStyle(el);
                    const zIndex = parseInt(style.zIndex) || 0;
                    const isInModal = !!el.closest('[role="dialog"], .modal, .overlay, [class*="modal"], [class*="overlay"], [class*="popup"], [class*="drawer"], [class*="cart"]');
                    
                    results.push({
                        index: index + 1,
                        tag: el.tagName,
                        text: text.substring(0, 80),
                        ariaLabel: ariaLabel.substring(0, 50),
                        className: className.substring(0, 50),
                        id: id.substring(0, 30),
                        disabled: disabled,
                        zIndex: zIndex,
                        inModal: isInModal,
                        position: {
                            top: Math.round(rect.top),
                            left: Math.round(rect.left),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        }
                    });
                });
                
                return results;
            }
        """)
        
        print(f"Found {len(buttons)} visible buttons\n")
        
        # Filter for checkout-related buttons
        checkout_buttons = []
        for btn in buttons:
            text_lower = btn['text'].lower()
            aria_lower = btn['ariaLabel'].lower()
            class_lower = btn['className'].lower()
            
            if any(keyword in text_lower or keyword in aria_lower or keyword in class_lower 
                   for keyword in ['checkout', 'proceed', 'cart', 'bag', 'continue']):
                checkout_buttons.append(btn)
        
        print(f"{'='*60}")
        print(f"CHECKOUT-RELATED BUTTONS ({len(checkout_buttons)} found)")
        print(f"{'='*60}\n")
        
        for btn in checkout_buttons:
            print(f"Button #{btn['index']}:")
            print(f"  Tag: {btn['tag']}")
            print(f"  Text: '{btn['text']}'")
            if btn['ariaLabel']:
                print(f"  Aria-Label: '{btn['ariaLabel']}'")
            if btn['className']:
                print(f"  Class: '{btn['className']}'")
            if btn['id']:
                print(f"  ID: '{btn['id']}'")
            print(f"  Disabled: {btn['disabled']}")
            print(f"  Z-Index: {btn['zIndex']}")
            print(f"  In Modal: {btn['inModal']}")
            print(f"  Position: top={btn['position']['top']}px, left={btn['position']['left']}px")
            print()
        
        # Check for "PROCEED TO CHECKOUT" specifically
        print(f"{'='*60}")
        print("SEARCHING FOR 'PROCEED TO CHECKOUT'")
        print(f"{'='*60}\n")
        
        proceed_buttons = [btn for btn in buttons if 'proceed' in btn['text'].lower() and 'checkout' in btn['text'].lower()]
        
        if proceed_buttons:
            print(f"✓ Found {len(proceed_buttons)} button(s) with 'PROCEED TO CHECKOUT':\n")
            for btn in proceed_buttons:
                print(f"  Text: '{btn['text']}'")
                print(f"  Disabled: {btn['disabled']}")
                print(f"  In Modal: {btn['inModal']}")
                print(f"  Z-Index: {btn['zIndex']}")
                print()
        else:
            print("✗ No button found with 'PROCEED TO CHECKOUT' text\n")
            print("Possible reasons:")
            print("  1. Button text is different (check all buttons above)")
            print("  2. Button is in a hidden modal/drawer")
            print("  3. Button is disabled")
            print("  4. Button hasn't loaded yet")
        
        print(f"\n{'='*60}")
        print("Press Enter to close browser...")
        print(f"{'='*60}")
        input()
        
        await browser.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python debug_checkout_button.py <cart_url>")
        print("Example: python debug_checkout_button.py https://example.com/cart")
        sys.exit(1)
    
    url = sys.argv[1]
    asyncio.run(debug_checkout_button(url))
