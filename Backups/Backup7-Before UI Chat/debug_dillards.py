#!/usr/bin/env python3
"""
Diagnostic script to investigate Dillards size button selection issue
"""

import asyncio
from playwright.async_api import async_playwright

async def investigate_dillards():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=500,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        
        url = "https://www.dillards.com/p/polo-ralph-lauren-classic-fit-logo-jersey-short-sleeve-t-shirt/520187801"
        print(f"🔍 Navigating to: {url}")
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(5)
        
        print("\n" + "="*70)
        print("INVESTIGATION 1: Finding Size Buttons")
        print("="*70)
        
        # Check if size buttons exist
        size_buttons = await page.evaluate("""
            () => {
                const buttons = document.querySelectorAll('button[name="Size"]');
                console.log('Found', buttons.length, 'size buttons');
                
                const info = [];
                buttons.forEach((btn, i) => {
                    const rect = btn.getBoundingClientRect();
                    info.push({
                        index: i,
                        value: btn.value,
                        text: btn.textContent.trim(),
                        visible: rect.width > 0 && rect.height > 0,
                        disabled: btn.disabled,
                        ariaPressed: btn.getAttribute('aria-pressed'),
                        ariaDisabled: btn.getAttribute('aria-disabled'),
                        classes: btn.className,
                        rect: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height
                        }
                    });
                });
                return info;
            }
        """)
        
        print(f"\n✅ Found {len(size_buttons)} size buttons:")
        for btn in size_buttons:
            print(f"  [{btn['index']}] Value: {btn['value']}, Text: '{btn['text']}', Visible: {btn['visible']}")
            print(f"      Disabled: {btn['disabled']}, aria-pressed: {btn['ariaPressed']}, aria-disabled: {btn['ariaDisabled']}")
            print(f"      Classes: {btn['classes']}")
            print(f"      Position: x={btn['rect']['x']:.0f}, y={btn['rect']['y']:.0f}, w={btn['rect']['width']:.0f}, h={btn['rect']['height']:.0f}")
        
        print("\n" + "="*70)
        print("INVESTIGATION 2: Trying Different Click Methods on 'M' Button")
        print("="*70)
        
        # Method 1: Playwright click
        print("\n🔹 Method 1: Playwright click with selector")
        try:
            await page.click('button[name="Size"][value="M"]', timeout=3000)
            print("  ✅ Click executed")
            await asyncio.sleep(2)
            
            # Check if selected
            is_selected = await page.evaluate("""
                () => {
                    const btn = document.querySelector('button[name="Size"][value="M"]');
                    return btn ? btn.getAttribute('aria-pressed') : null;
                }
            """)
            print(f"  aria-pressed after click: {is_selected}")
        except Exception as e:
            print(f"  ❌ Failed: {e}")
        
        # Method 2: JavaScript click
        print("\n🔹 Method 2: JavaScript click")
        result = await page.evaluate("""
            () => {
                const btn = document.querySelector('button[name="Size"][value="M"]');
                if (!btn) return { success: false, reason: 'Button not found' };
                
                const beforePressed = btn.getAttribute('aria-pressed');
                btn.click();
                
                // Wait a bit for state to update
                return new Promise(resolve => {
                    setTimeout(() => {
                        const afterPressed = btn.getAttribute('aria-pressed');
                        resolve({
                            success: true,
                            beforePressed: beforePressed,
                            afterPressed: afterPressed,
                            changed: beforePressed !== afterPressed
                        });
                    }, 500);
                });
            }
        """)
        print(f"  Result: {result}")
        await asyncio.sleep(2)
        
        # Method 3: Focus + Click
        print("\n🔹 Method 3: Focus + Click")
        result = await page.evaluate("""
            () => {
                const btn = document.querySelector('button[name="Size"][value="M"]');
                if (!btn) return { success: false, reason: 'Button not found' };
                
                btn.focus();
                btn.click();
                
                return new Promise(resolve => {
                    setTimeout(() => {
                        resolve({
                            success: true,
                            ariaPressed: btn.getAttribute('aria-pressed'),
                            disabled: btn.disabled
                        });
                    }, 500);
                });
            }
        """)
        print(f"  Result: {result}")
        await asyncio.sleep(2)
        
        # Method 4: Mouse events
        print("\n🔹 Method 4: Dispatch mouse events")
        result = await page.evaluate("""
            () => {
                const btn = document.querySelector('button[name="Size"][value="M"]');
                if (!btn) return { success: false, reason: 'Button not found' };
                
                const rect = btn.getBoundingClientRect();
                const events = ['mousedown', 'mouseup', 'click'];
                
                events.forEach(eventType => {
                    const event = new MouseEvent(eventType, {
                        bubbles: true,
                        cancelable: true,
                        view: window,
                        clientX: rect.left + rect.width / 2,
                        clientY: rect.top + rect.height / 2
                    });
                    btn.dispatchEvent(event);
                });
                
                return new Promise(resolve => {
                    setTimeout(() => {
                        resolve({
                            success: true,
                            ariaPressed: btn.getAttribute('aria-pressed')
                        });
                    }, 500);
                });
            }
        """)
        print(f"  Result: {result}")
        await asyncio.sleep(2)
        
        # Method 5: Check for event listeners
        print("\n🔹 Method 5: Checking event listeners")
        listeners = await page.evaluate("""
            () => {
                const btn = document.querySelector('button[name="Size"][value="M"]');
                if (!btn) return null;
                
                // Check for onclick
                const hasOnclick = btn.onclick !== null;
                const onclickAttr = btn.getAttribute('onclick');
                
                // Check parent container
                const parent = btn.parentElement;
                const parentInfo = parent ? {
                    tagName: parent.tagName,
                    className: parent.className,
                    id: parent.id,
                    hasOnclick: parent.onclick !== null
                } : null;
                
                return {
                    hasOnclick: hasOnclick,
                    onclickAttr: onclickAttr,
                    parent: parentInfo
                };
            }
        """)
        print(f"  Listeners: {listeners}")
        
        print("\n" + "="*70)
        print("INVESTIGATION 3: Check if there's a parent wrapper that needs clicking")
        print("="*70)
        
        parent_info = await page.evaluate("""
            () => {
                const btn = document.querySelector('button[name="Size"][value="M"]');
                if (!btn) return null;
                
                let current = btn.parentElement;
                const parents = [];
                let depth = 0;
                
                while (current && depth < 5) {
                    const rect = current.getBoundingClientRect();
                    parents.push({
                        depth: depth,
                        tagName: current.tagName,
                        className: current.className,
                        id: current.id,
                        hasOnclick: current.onclick !== null,
                        clickable: current.style.cursor === 'pointer' || current.onclick !== null,
                        rect: {
                            width: rect.width,
                            height: rect.height
                        }
                    });
                    current = current.parentElement;
                    depth++;
                }
                
                return parents;
            }
        """)
        
        print("\n  Parent hierarchy:")
        for p in parent_info:
            print(f"    [{p['depth']}] {p['tagName']}.{p['className'][:30] if p['className'] else 'no-class'}")
            print(f"        Clickable: {p['clickable']}, Has onclick: {p['hasOnclick']}")
        
        print("\n" + "="*70)
        print("INVESTIGATION 4: Try clicking parent wrapper")
        print("="*70)
        
        result = await page.evaluate("""
            () => {
                const btn = document.querySelector('button[name="Size"][value="M"]');
                if (!btn) return { success: false };
                
                // Try clicking the parent div
                const parent = btn.closest('.attrSelect');
                if (parent) {
                    console.log('Found parent .attrSelect, clicking button inside it');
                    btn.click();
                    
                    return new Promise(resolve => {
                        setTimeout(() => {
                            resolve({
                                success: true,
                                method: 'parent_wrapper',
                                ariaPressed: btn.getAttribute('aria-pressed')
                            });
                        }, 1000);
                    });
                }
                
                return { success: false, reason: 'No parent wrapper found' };
            }
        """)
        print(f"  Result: {result}")
        await asyncio.sleep(3)
        
        print("\n" + "="*70)
        print("INVESTIGATION 5: Final state check")
        print("="*70)
        
        final_state = await page.evaluate("""
            () => {
                const buttons = document.querySelectorAll('button[name="Size"]');
                const states = [];
                
                buttons.forEach(btn => {
                    states.push({
                        value: btn.value,
                        ariaPressed: btn.getAttribute('aria-pressed'),
                        disabled: btn.disabled,
                        classes: btn.className
                    });
                });
                
                return states;
            }
        """)
        
        print("\n  All size buttons final state:")
        for state in final_state:
            selected = "✅ SELECTED" if state['ariaPressed'] == 'true' else ""
            print(f"    {state['value']}: aria-pressed={state['ariaPressed']} {selected}")
        
        print("\n" + "="*70)
        print("Press Enter to close browser...")
        print("="*70)
        input()
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(investigate_dillards())
