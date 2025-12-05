"""
Quick diagnostic for Patagonia page
"""
import asyncio
from playwright.async_api import async_playwright

async def diagnose_patagonia():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        print("🔍 Loading Patagonia page...")
        await page.goto('https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/198077145677.html')
        await asyncio.sleep(3)
        
        # Check for modals
        print("\n📋 Checking for modals/overlays...")
        modals = await page.evaluate("""
            () => {
                const selectors = ['.modal', '[role="dialog"]', '.overlay', '[class*="modal"]', '[id*="modal"]'];
                const found = [];
                selectors.forEach(sel => {
                    const els = document.querySelectorAll(sel);
                    els.forEach(el => {
                        if (el.offsetParent) {
                            found.push({
                                selector: sel,
                                id: el.id,
                                class: el.className,
                                visible: true
                            });
                        }
                    });
                });
                return found;
            }
        """)
        print(f"Found {len(modals)} visible modals: {modals}")
        
        # Check for add to cart button
        print("\n🛒 Checking for Add to Cart button...")
        add_to_cart = await page.evaluate("""
            () => {
                const buttons = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                const cartButtons = buttons.filter(b => {
                    const text = (b.textContent || '').toLowerCase();
                    return text.includes('add to cart') || text.includes('add to bag');
                }).map(b => ({
                    text: b.textContent.trim(),
                    id: b.id,
                    class: b.className,
                    visible: b.offsetParent !== null,
                    disabled: b.disabled
                }));
                return cartButtons;
            }
        """)
        print(f"Add to cart buttons: {add_to_cart}")
        
        # Check for size/color selectors
        print("\n👕 Checking for variant selectors...")
        variants = await page.evaluate("""
            () => {
                const sizeSelectors = document.querySelectorAll('[class*="size"], [data-size], select[name*="size"]');
                const colorSelectors = document.querySelectorAll('[class*="color"], [data-color], select[name*="color"]');
                return {
                    sizes: Array.from(sizeSelectors).map(s => ({
                        tag: s.tagName,
                        class: s.className,
                        id: s.id,
                        visible: s.offsetParent !== null
                    })),
                    colors: Array.from(colorSelectors).map(c => ({
                        tag: c.tagName,
                        class: c.className,
                        id: c.id,
                        visible: c.offsetParent !== null
                    }))
                };
            }
        """)
        print(f"Size selectors: {len(variants['sizes'])}")
        print(f"Color selectors: {len(variants['colors'])}")
        
        # Check URL
        print(f"\n🌐 Current URL: {page.url}")
        
        # Take screenshot
        await page.screenshot(path='/Users/abcom/Documents/Checkout_ai/patagonia_debug.png')
        print("\n📸 Screenshot saved to patagonia_debug.png")
        
        print("\n⏸️  Pausing for manual inspection (60s)...")
        await asyncio.sleep(60)
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(diagnose_patagonia())
