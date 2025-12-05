#!/usr/bin/env python3
"""
Main Orchestrator - Stitches Phase 1 and Phase 2
Handles complete flow: Product Selection → Cart → Checkout → Shipping Form
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Phase 1 imports
from phase1.universal_dom_finder import find_variant_dom
from phase1.add_to_cart_robust import add_to_cart_robust
from phase1.cart_navigator import navigate_to_cart

# Phase 2 imports
from phase2.checkout_flow import run_checkout_flow

# Site-specific handlers (using registry system)
from special_sites import get_site_specific_variant_handler, get_site_specific_checkout_handler

# LLM for cart validation
from agent.llm_client import LLMClient

# Stealth mode
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("WARNING: playwright-stealth not installed. Run: pip install playwright-stealth")
    async def stealth_async(page):
        pass

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCREENSHOT_PATH = '/tmp/chkout_screenshot.png'


async def capture_screenshots(page):
    """Continuously capture screenshots every 5 seconds"""
    try:
        while True:
            try:
                await page.screenshot(path=SCREENSHOT_PATH)
            except Exception as e:
                logger.debug(f"Screenshot error: {e}")
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        if os.path.exists(SCREENSHOT_PATH):
            os.remove(SCREENSHOT_PATH)
        logger.info("Screenshot capture stopped")


async def validate_cart_items(page, tasks):
    """Use LLM to validate cart items match requested variants"""
    try:
        # Extract cart items from page
        cart_html = await page.evaluate("""
            () => {
                const cartItems = document.querySelectorAll('[class*="cart-item"], [class*="line-item"], .cart-item, .line-item');
                let html = '';
                cartItems.forEach(item => {
                    html += item.outerHTML.substring(0, 500) + '\n';
                });
                return html || document.body.innerHTML.substring(0, 2000);
            }
        """)
        
        # Build expected variants string
        expected = []
        for task in tasks:
            variants = task.get('selectedVariant', {})
            expected.append(f"Product: {task['url'].split('/')[-2]}, Variants: {variants}")
        
        # LLM validation prompt
        prompt = f"""Validate if cart items match expected variants.

Expected:
{chr(10).join(expected)}

Cart HTML:
{cart_html[:1500]}

Respond with JSON:
{{
  "valid": true/false,
  "reason": "explanation"
}}"""
        
        llm = LLMClient(provider='openai', api_key=os.getenv('OPENAI_API_KEY'))
        result = await llm.complete(prompt, max_tokens=200)
        
        is_valid = result.get('valid', True)
        reason = result.get('reason', 'No reason provided')
        
        logger.info(f"ORCHESTRATOR: Cart validation - Valid: {is_valid}, Reason: {reason}")
        return is_valid
        
    except Exception as e:
        logger.warning(f"ORCHESTRATOR: Cart validation error: {e}, assuming valid")
        return True


async def dismiss_geolocation_modal(page):
    """Try to dismiss geolocation/location modal by clicking Geolocation or similar buttons"""
    try:
        # Wait a bit for modal to appear
        await asyncio.sleep(1)

        # Try to find and click "Geolocation" or similar buttons
        shop_now_clicked = await page.evaluate("""
            () => {
                const keywords = ['continue', 'close', 'dismiss', 'accept', 'confirm'];
                const buttons = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                
                for (const btn of buttons) {
                    const text = (btn.textContent || btn.innerText || '').toLowerCase().trim();
                    if (keywords.some(kw => text.includes(kw))) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }
        """)
        
        if shop_now_clicked:
            logger.info(f"ORCHESTRATOR: Dismissed geolocation modal")
            await asyncio.sleep(1)
    except Exception as e:
        logger.debug(f"ORCHESTRATOR: Could not dismiss geolocation modal: {e}")


def detect_site_type(url):
    """Detect website type for specialized automation"""
    url_lower = url.lower()
    if 'farfetch.com' in url_lower:
        return 'farfetch'
    elif 'zara.com' in url_lower:
        return 'zara'
    return 'generic'


async def run_phase1(page, task):
    """
    Phase 1: Product selection and add to cart
    Returns: {'success': bool, 'error': str}
    """
    logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Starting Phase 1 for {task['url']}")
    
    try:
        # Detect site type
        site_type = detect_site_type(task['url'])
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Site type: {site_type}")
        
        # Navigate to product URL
        await page.goto(task['url'], wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(2)
        
        # Dismiss popups first (cookie consent, etc.)
        from shared.popup_dismisser import dismiss_popups
        await dismiss_popups(page)
        await asyncio.sleep(1)
        
        # Try to dismiss geolocation modal (generic + Karl Lagerfeld specific)
        await dismiss_geolocation_modal(page)
        
        # Karl Lagerfeld specific modal dismissal
        if site_type == 'karllagerfeld':
            from special_sites.karllagerfeld_automator import dismiss_geolocation_modal as kl_dismiss
            await kl_dismiss(page)
        
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Loaded product page")
        
        # Wait for product content to load
        await asyncio.sleep(2)

        # Select variants - use specialized handlers for Farfetch and Zara
        selected_variant = task.get('selectedVariant', {})
        
        if site_type == 'farfetch':
            # Use Farfetch specialized handler
            from special_sites.farfetch_automator import FarfetchAutomator
            automator = FarfetchAutomator()
            
            for variant_type, variant_value in selected_variant.items():
                if str(variant_value).lower().strip() == 'none':
                    continue
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Selecting {variant_type}: {variant_value} (Farfetch)")
                success = await automator.select_variant(page, variant_type, variant_value)
                if not success:
                    return {'success': False, 'error': f'Failed to select {variant_type}: {variant_value}'}
                await asyncio.sleep(1)
        
        elif site_type == 'zara':
            # Use Zara specialized handler
            from special_sites.zara_automator import ZaraAutomator
            automator = ZaraAutomator(page)
            
            # Zara: color first, then add to cart, then size
            if 'color' in selected_variant:
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Selecting color: {selected_variant['color']} (Zara)")
                result = await automator.select_color(selected_variant['color'])
                if not result.get('success'):
                    return {'success': False, 'error': f"Failed to select color: {selected_variant['color']}"}
                await asyncio.sleep(2)
        
        else:
            # Generic sites - use universal finder or site-specific handlers
            # Check for site-specific variant handler ONCE before variant loop
            site_handler = await get_site_specific_variant_handler(page)
            original_url = page.url
            
            if site_handler:
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Using site-specific variant handler for {page.url}")
            else:
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] No site-specific handler found, using universal DOM finder")
            
            for variant_type, variant_value in selected_variant.items():
                if str(variant_value).lower().strip() == 'none':
                    logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Skipping {variant_type}: product has no variants (value='none')")
                    continue
                
                # Verify we're still on the product page
                current_url = page.url
                if '/products/' in original_url and '/products/' not in current_url:
                    logger.error(f"ORCHESTRATOR: Page navigated away from product page!")
                    logger.error(f"  Expected: {original_url}")
                    logger.error(f"  Current: {current_url}")
                    return {'success': False, 'error': f'Page redirected away from product page to {current_url}'}
                
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Selecting {variant_type}: {variant_value}")
                
                # Use site handler if available, otherwise use universal DOM finder
                if site_handler:
                    result = await site_handler(page, variant_type, variant_value)
                else:
                    result = await find_variant_dom(page, variant_type, variant_value)
                
                if not result.get('success'):
                    return {'success': False, 'error': f'Failed to select {variant_type}: {variant_value}'}
                
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] {variant_type} selected successfully")
                await asyncio.sleep(1)
        
        # Set quantity if needed
        quantity = task.get('quantity', 1)
        if quantity > 1:
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Setting quantity: {quantity}")
            result = await find_variant_dom(page, 'quantity', str(quantity))
            await asyncio.sleep(1)
        
        # Add to cart (Zara has special flow)
        if site_type == 'zara':
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Adding to cart (Zara)...")
            add_result = await find_variant_dom(page, 'add_to_cart', 'add')
            if not add_result or not add_result.get('success'):
                return {'success': False, 'error': 'Failed to add to cart (Zara)'}
            await asyncio.sleep(3)
            
            # Select size after add for Zara
            if 'size' in selected_variant:
                from special_sites.zara_automator import ZaraAutomator
                automator = ZaraAutomator(page)
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Selecting size: {selected_variant['size']} (Zara)")
                size_result = await automator.select_size_after_add(selected_variant['size'])
                if not size_result.get('success'):
                    return {'success': False, 'error': f"Failed to select size: {selected_variant['size']}"}
                await asyncio.sleep(2)
        
        elif site_type == 'farfetch':
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Adding to cart (Farfetch)...")
            from special_sites.farfetch_automator import FarfetchAutomator
            automator = FarfetchAutomator()
            cart_success = await automator.add_to_cart(page)
            if not cart_success:
                return {'success': False, 'error': 'Failed to add to cart (Farfetch)'}
            await asyncio.sleep(3)
        
        else:
            # Check if Amazon - use Amazon-specific add to cart
            if 'amazon.' in page.url.lower():
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Adding to cart (Amazon)...")
                from special_sites.amazon_automator import add_amazon_to_cart
                cart_result = await add_amazon_to_cart(page)
                if not cart_result.get('success'):
                    return {'success': False, 'error': 'Failed to add to cart (Amazon)'}
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Added to cart successfully (Amazon)")
            else:
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Adding to cart...")
                cart_result = await add_to_cart_robust(page)
                if not cart_result.get('success'):
                    return {'success': False, 'error': 'Failed to add to cart'}
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Added to cart successfully")
            await asyncio.sleep(3)
        
        # Verify cart count increased
        cart_count = await page.evaluate("""
            () => {
                const cartSelectors = [
                    '[class*="cart-count"]', '[class*="cart-quantity"]',
                    '[class*="minicart-count"]', '[data-cart-count]',
                    '.cart-count', '.cart-quantity', '.minicart-quantity'
                ];
                
                for (const selector of cartSelectors) {
                    const el = document.querySelector(selector);
                    if (el) {
                        const text = el.textContent.trim();
                        const num = parseInt(text);
                        if (!isNaN(num) && num > 0) {
                            return num;
                        }
                    }
                }
                return 0;
            }
        """)
        
        if cart_count > 0:
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Cart count verified: {cart_count} item(s)")
        else:
            logger.warning(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Cart count is 0 - item may not have been added")
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Phase 1 error: {e}")
        return {'success': False, 'error': str(e)}


async def run_full_flow(json_input):
    """
    Main orchestrator: Phase 1 → Phase 2 in same browser
    json_input: Full JSON with customer data and tasks
    Returns: {'success': bool, 'phase': str, 'error': str}
    """
    logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Starting full checkout flow")
    
    playwright = None
    browser = None
    
    try:
        # Parse input
        customer = json_input['customer']
        tasks = json_input['tasks']
        
        # Extract base URL from first task for fallback
        from urllib.parse import urlparse
        first_url = tasks[0]['url']
        parsed = urlparse(first_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        logger.info(f"ORCHESTRATOR: Base URL: {base_url}")
        
        # Store in page context for Phase 2
        customer['_base_url'] = base_url
        
        # Launch browser - use Playwright's Chromium
        playwright = await async_playwright().start()
        
        # Use headed mode with Chrome
        browser = await playwright.chromium.launch(
            headless=False,
            channel='chrome',
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
            slow_mo=500,
            chromium_sandbox=False
        )
        
        context = await browser.new_context(
            viewport={'width': 1440, 'height': 900},
            permissions=[],  # Grant no permissions
            geolocation={'latitude': 0, 'longitude': 0},  # Provide fake geolocation to avoid prompt
            ignore_https_errors=True
        )
        page = await context.new_page()
        
        # Stealth + Popup blocking + CSS injection
        await page.add_init_script("""
            // Stealth
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            delete navigator.__proto__.webdriver;
            
            // Block popup functions
            window.alert = () => {};
            window.confirm = () => true;
            window.prompt = () => null;
            window.open = () => null;
            
            // Block common modal triggers
            window.addEventListener('beforeunload', (e) => {
                e.preventDefault();
                e.returnValue = '';
            });
            
            // Inject CSS to hide geolocation and common modals
            const style = document.createElement('style');
            style.textContent = `
                /* Hide geolocation modals */
                [class*="geolocation"], [id*="geolocation"],
                [class*="location"], [id*="location"],
                [class*="country-selector"], [id*="country-selector"],
                [class*="region-selector"], [id*="region-selector"],
                /* Common modal patterns */
                [class*="modal"][class*="location"],
                [class*="popup"][class*="location"],
                [class*="overlay"][class*="location"],
                /* Specific selectors */
                .geolocation-modal, #geolocation-modal,
                .location-popup, #location-popup,
                .country-modal, #country-modal {
                    display: none !important;
                    visibility: hidden !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                }
            `;
            document.head.appendChild(style);
        """)
        
        if STEALTH_AVAILABLE:
            await stealth_async(page)
        
        # Start screenshot capture
        screenshot_task = asyncio.create_task(capture_screenshots(page))
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Screenshot capture started")
        
        # Phase 1: Process all tasks (add products to cart)
        for i, task in enumerate(tasks):
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Processing task {i + 1}/{len(tasks)}")
            
            result = await run_phase1(page, task)
            
            if not result['success']:
                return {
                    'success': False,
                    'phase': 'phase1',
                    'task_index': i,
                    'error': result.get('error', 'Phase 1 failed')
                }
            
            await asyncio.sleep(1)
        
        # Navigate to cart
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Navigating to cart...")
        
        # Check if Karl Lagerfeld - use custom navigation
        # Check for site-specific checkout handler
        checkout_handler = await get_site_specific_checkout_handler(page)
        
        if checkout_handler:
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Using site-specific checkout handler")
            checkout_success = await checkout_handler(page)
            if not checkout_success:
                return {
                    'success': False,
                    'phase': 'cart_navigation',
                    'error': 'Failed to navigate to checkout (site-specific handler)'
                }
        else:
            nav_result = await navigate_to_cart(page)
            if not nav_result.get('success'):
                return {
                    'success': False,
                    'phase': 'cart_navigation',
                    'error': 'Failed to navigate to cart'
                }
        
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Cart/Checkout page loaded")
        await asyncio.sleep(2)
        
        # Validate cart items match requested variants
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Validating cart items...")
        cart_valid = await validate_cart_items(page, tasks)
        
        if not cart_valid:
            logger.warning(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Cart validation failed - wrong variants detected")
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Clearing cart and restarting...")
            
            # Clear cart and restart
            first_task = tasks[0]
            await page.goto(first_task['url'], wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)
            
            # Re-run Phase 1
            for i, task in enumerate(tasks):
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Retry task {i + 1}/{len(tasks)}")
                result = await run_phase1(page, task)
                if not result['success']:
                    return {'success': False, 'phase': 'phase1_retry', 'error': 'Phase 1 retry failed'}
                await asyncio.sleep(1)
            
            # Re-navigate to cart
            checkout_handler = await get_site_specific_checkout_handler(page)
            if checkout_handler:
                checkout_success = await checkout_handler(page)
                if not checkout_success:
                    return {'success': False, 'phase': 'cart_navigation_retry', 'error': 'Failed to navigate to checkout after retry'}
            else:
                nav_result = await navigate_to_cart(page)
                if not nav_result.get('success'):
                    return {'success': False, 'phase': 'cart_navigation_retry', 'error': 'Failed to navigate to cart after retry'}
            await asyncio.sleep(2)
        
        # Check if already on checkout page
        current_url = page.url.lower()
        is_on_checkout_page = 'checkout' in current_url
        
        if is_on_checkout_page:
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Already on checkout page, skipping cart validation")
        else:
            # Check if cart is empty (check for checkout button existence)
            has_checkout_button = await page.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button, a, input[type="submit"]'));
                    const checkoutKeywords = ['checkout', 'check out', 'proceed', 'continue to checkout'];
                    
                    for (const btn of buttons) {
                        const text = (btn.textContent || btn.value || '').toLowerCase().trim();
                        if (checkoutKeywords.some(kw => text.includes(kw))) {
                            return true;
                        }
                    }
                    return false;
                }
            """)
            
            # ONLY navigate to product URL if cart is empty
            if not has_checkout_button:
                logger.warning(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Cart appears empty (no checkout button)! Restarting from product URL...")
                
                # EXPLICIT EMPTY CART RECOVERY - Direct navigation to product URL
                first_task = tasks[0]
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] EMPTY CART: Direct navigation to {first_task['url']}")
                
                try:
                    await page.goto(first_task['url'], wait_until='networkidle', timeout=30000)
                    logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Product page loaded")
                except Exception as e:
                    logger.warning(f"ORCHESTRATOR: Navigation timeout: {e}")
                
                await asyncio.sleep(3)
                
                # Re-run Phase 1 for all tasks
                for i, task in enumerate(tasks):
                    logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Re-processing task {i + 1}/{len(tasks)}")
                    result = await run_phase1(page, task)
                    
                    if not result['success']:
                        return {
                            'success': False,
                            'phase': 'phase1_retry',
                            'task_index': i,
                            'error': result.get('error', 'Phase 1 retry failed')
                        }
                    await asyncio.sleep(1)
                
                # Re-navigate to cart
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Re-navigating to cart...")
                nav_result = await navigate_to_cart(page)
                if not nav_result.get('success'):
                    return {
                        'success': False,
                        'phase': 'cart_navigation_retry',
                        'error': 'Failed to navigate to cart after retry'
                    }
                await asyncio.sleep(2)
            else:
                # Cart is not empty - proceed normally
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Cart has items, proceeding to checkout")
        
        # Phase 2: Checkout flow (same browser, same page)
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Starting Phase 2...")
        checkout_result = await run_checkout_flow(page, customer)
        
        if not checkout_result['success']:
            return {
                'success': False,
                'phase': 'phase2',
                'step': checkout_result.get('step'),
                'error': checkout_result.get('error', 'Phase 2 failed'),
                'details': checkout_result.get('details')
            }
        
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Full flow completed successfully!")
        
        # Show success message
        print("\n" + "="*60)
        print("✅ SUCCESS: Checkout completed!")
        print("="*60)
        print("🎉 All steps completed successfully!")
        print("💳 Payment modal is now displayed.")
        print("")
        print("👉 Please complete the payment manually in the browser.")
        print("")
        print("⏳ Browser will remain open for 5 minutes...")
        print("="*60 + "\n")
        
        # Create payment ready notification
        try:
            with open('/tmp/chkout_payment_ready.txt', 'w') as f:
                f.write('ready')
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Payment ready notification created")
        except Exception as e:
            logger.warning(f"ORCHESTRATOR: Could not create notification: {e}")
        
        # Keep browser open for payment
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Browser will stay open for manual payment...")
        await asyncio.sleep(300)
        
        return {
            'success': True,
            'message': 'Full checkout flow completed',
            'final_url': page.url
        }
        
    except Exception as e:
        logger.error(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Fatal error: {e}")
        return {
            'success': False,
            'phase': 'unknown',
            'error': str(e)
        }
    
    finally:
        # Stop screenshot capture
        try:
            screenshot_task.cancel()
        except:
            pass
        
        # Cleanup
        try:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Browser closed")
        except Exception as e:
            logger.error(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Cleanup error: {e}")


async def main():
    """Entry point with sample JSON"""
    
    # Sample JSON input
    json_input = {
        "customer": {
            "contact": {
                "lastName": "Thombare",
                "firstName": "Chaitanya",
                "phone": "+19404792824",
                "email": "chth@gmail.com"
            },
            "shippingAddress": {
                "addressLine1": "2801 Middle Gate Ln",
                "addressLine2": "",
                "city": "Plano",
                "province": "Texas",
                "postalCode": "75093",
                "country": "US"
            }
        },
        "tasks": [
            {
                "url": "https://nalgene.com/product/32oz-narrow-mouth-bottle/",
                "quantity": 1,
                "selectedVariant": {
                    "color": "Cerulean"
                }
            }
        ]
    }
    
    # Run full flow
    result = await run_full_flow(json_input)
    
    # Print result
    print("\n" + "="*60)
    if result['success']:
        print("✅ SUCCESS: Full checkout flow completed!")
        print(f"Final URL: {result.get('final_url')}")
    else:
        print("❌ FAILED")
        print(f"Phase: {result.get('phase')}")
        print(f"Error: {result.get('error')}")
        if result.get('step'):
            print(f"Step: {result.get('step')}")
        if result.get('details'):
            print(f"Details: {result.get('details')}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
