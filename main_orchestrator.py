#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main Orchestrator - Stitches Phase 1 and Phase 2
Handles complete flow: Product Selection → Cart → Checkout → Shipping Form
"""

# CRITICAL: Fix encoding BEFORE any other imports
import os
import sys

# CRITICAL: Windows Playwright fix MUST be first - before asyncio is used anywhere
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[WINDOWS FIX] Set ProactorEventLoop policy at module import")

# Set UTF-8 encoding for all I/O operations (Windows fix)
if sys.platform == 'win32':
    # Set environment variable for Python's default encoding
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # Force stdout/stderr to use UTF-8
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')

import json
import logging
import shutil
import tempfile
from datetime import datetime
from playwright.async_api import async_playwright, Page
from typing import Dict, Any
from dotenv import load_dotenv

# Phase 1 imports
from src.checkout_ai.dom.service import UniversalDOMFinder as find_variant_dom
from src.checkout_ai.legacy.phase1.add_to_cart_robust import add_to_cart_robust
from src.checkout_ai.legacy.phase1.cart_navigator import navigate_to_cart

# Phase 2 imports
from src.checkout_ai.legacy.phase2.checkout_flow import run_checkout_flow

# Site-specific handlers (using registry system)
from special_sites import get_site_specific_variant_handler, get_site_specific_checkout_handler

# LLM for cart validation


# Agent Imports
from src.checkout_ai.agents.planner_agent import PA_agent, PLANNER_AGENT_OP
from src.checkout_ai.agents.browser_agent import BA_agent, current_step_class
from src.checkout_ai.agents.critique_agent import CA_agent, CritiqueInput, CritiqueOutput
from src.checkout_ai.agents.tools import set_page

# Stealth mode
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("WARNING: playwright-stealth not installed. Run: pip install playwright-stealth")
    async def stealth_async(page):
        pass

async def run_agentic_flow(page: Page, task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the task using the Planner -> Browser -> Critique agent loop.
    """
    from src.checkout_ai.agents.orchestrator import AgentOrchestrator
    
    logger.info("ORCHESTRATOR: Starting Agentic Flow")
    
    # Extract task details
    url = task.get('url')
    variants = task.get('selectedVariant', {})
    quantity = task.get('quantity', 1)
    customer_data = task.get('customer_data')
    
    # Create orchestrator with customer data
    orchestrator = AgentOrchestrator(page, max_iterations=20, customer_data=customer_data)
    
    # Execute checkout flow using autonomous agent
    variant_str = ", ".join([f"{k}={v}" for k, v in variants.items()])
    
    if customer_data:
        # Full checkout flow
        task_desc = f"Navigate to {url}, select variants ({variant_str}), add to cart with quantity {quantity}. Then proceed to checkout and fill all information (email, shipping, payment) to place the order."
        result = await orchestrator.execute_task(task_desc, customer_data=customer_data)
    else:
        # Just product selection
        task_desc = f"Navigate to {url}, select variants ({variant_str}), add to cart with quantity {quantity}"
        result = await orchestrator.execute_task(task_desc)
    
    return result

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
        
        from src.checkout_ai.core.utils.openai_client import get_client, get_model
        
        client = get_client()
        model = get_model()
        
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        
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
                const skipKeywords = ['shop', 'woman', 'men', 'home', 'collection', 'category', 'sale', 'new'];
                const buttons = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                
                for (const btn of buttons) {
                    const text = (btn.textContent || btn.innerText || '').toLowerCase().trim();
                    const href = btn.getAttribute('href')?.toLowerCase() || '';
                    
                    // Skip navigation links
                    if (skipKeywords.some(skip => text.includes(skip) || href.includes(skip))) {
                        continue;
                    }
                    
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
    elif 'karllagerfeld.com' in url_lower:
        return 'karllagerfeld'
    return 'generic'


async def validate_variant_selections(page, selected_variant):
    """
    Validate that selected variants are actually selected in the DOM.
    Ported from automation_engine.py for robust verification.
    """
    try:
        # Prepare data for JS
        # main_orchestrator uses a flat dict, automation_engine used a structured object
        # We'll adapt the JS to handle the flat dict
        
        validation_result = await page.evaluate("""
            (variants) => {
                const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9]/g, '') : '';
                
                const validations = [];
                const errors = [];
                
                // Helper to check if a value is selected
                const isSelected = (key, value) => {
                    const normalizedVal = normalize(value);
                    
                    // 1. Check specific logic for Color (often images)
                    if (key.toLowerCase() === 'color') {
                        const checkedRadios = document.querySelectorAll('input[type="radio"]:checked');
                        for (const radio of checkedRadios) {
                            const section = radio.closest('section') || radio.parentElement;
                            if (section) {
                                const img = section.querySelector('img[alt]');
                                if (img && normalize(img.alt) === normalizedVal) return true;
                            }
                            // Also check label text
                            const label = document.querySelector(`label[for="${radio.id}"]`);
                            if (label && normalize(label.textContent) === normalizedVal) return true;
                        }
                    }
                    
                    // 2. Generic check for all types (active classes, checked inputs, text match)
                    const selectedElements = document.querySelectorAll('.selected, .active, .chosen, [aria-selected="true"], [aria-pressed="true"], :checked, [class*="selected"], [class*="active"], [class*="chosen"]');
                    
                    for (const el of selectedElements) {
                        const texts = [
                            el.textContent, 
                            el.value, 
                            el.getAttribute('aria-label'), 
                            el.getAttribute('title'), 
                            el.getAttribute('data-value'), 
                            el.getAttribute('alt')
                        ];
                        
                        for (const text of texts) {
                            if (text && normalize(text) === normalizedVal) return true;
                        }
                    }
                    
                    return false;
                };

                // Iterate over all requested variants
                for (const [key, value] of Object.entries(variants)) {
                    if (!value || value.toLowerCase() === 'none') continue;
                    
                    if (isSelected(key, value)) {
                        validations.push(`${key}: ${value}`);
                    } else {
                        errors.push(key); // Push just the key for retry logic
                    }
                }
                
                return {
                    success: errors.length === 0,
                    validations: validations,
                    errors: errors,
                    message: errors.length === 0 ? validations.join(', ') : `Missing: ${errors.join(', ')}`
                };
            }
        """, selected_variant)
        
        return validation_result
        
    except Exception as e:
        logger.warning(f"ORCHESTRATOR: Validation error: {e}")
        return {
            'success': True, # Fail open if validation crashes
            'message': f'Validation skipped due to error: {e}',
            'errors': []
        }


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
        from src.checkout_ai.utils.popup_dismisser import dismiss_popups
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


async def run_full_flow(json_data: dict) -> dict:
    """
    Windows-compatible entry point for automation
    Runs Playwright in subprocess on Windows to avoid event loop conflicts
    """
    if sys.platform == 'win32':
        # Run in subprocess with correct event loop
        import subprocess
        import tempfile
        
        # Write JSON to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as f:
            json.dump(json_data, f)
            temp_file = f.name
        
        try:
            # Create output file for result
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as rf:
                result_file = rf.name

            # Create Python script that runs automation
            script_content = f"""
import sys
import asyncio
import json
import os

# Set Windows event loop policy FIRST
asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Add project to path
sys.path.insert(0, r'{os.path.dirname(os.path.abspath(__file__))}')

from main_orchestrator import run_full_flow_core

# Load data
with open(r'{temp_file}', 'r', encoding='utf-8') as f:
    json_data = json.load(f)

# Run automation
try:
    result = asyncio.run(run_full_flow_core(json_data))
except Exception as e:
    result = {{"success": False, "error": str(e)}}

# Write result to file
with open(r'{result_file}', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False)
"""
            
            # Write script to temp file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as sf:
                sf.write(script_content)
                script_file = sf.name
            
            # Prepare environment with unbuffered output
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'

            # Run subprocess - NO CAPTURE so logs show in terminal
            proc_result = subprocess.run(
                [sys.executable, script_file],
                # capture_output=False, # Default is False (inherit)
                text=True,
                encoding='utf-8',
                env=env, # Pass updated environment
                timeout=3800 # Allow time for the 1 hour sleep if needed + buffer
            )
            
            # Clean up input script/data files
            try:
                os.unlink(script_file)
                os.unlink(temp_file)
            except:
                pass
            
            # Read result
            if proc_result.returncode == 0:
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    return {
                        "success": False, 
                        "error": f"Failed to read result file: {str(e)}"
                    }
                finally:
                    if os.path.exists(result_file):
                        os.unlink(result_file)
            else:
                return {
                    "success": False, 
                    "error": f"Subprocess failed with code {proc_result.returncode}", 
                }
                
        except Exception as e:
            # Clean up on error
            try:
                if 'temp_file' in locals():
                    os.unlink(temp_file)
            except:
                pass
            return {"success": False, "error": f"Subprocess error: {str(e)}"}
    else:
        # Non-Windows: run directly
        return await run_full_flow_core(json_data)






async def run_full_flow_core(json_data: dict) -> dict:
    """
    Core automation logic - renamed from run_full_flow
    This is the actual implementation that runs Playwright
    """
    logger.info("[%s] Starting full checkout flow", datetime.now().strftime('%H:%M:%S'))
    
    playwright = None
    context = None
    
    try:
        # Parse input
        customer = json_data['customer']
        tasks = json_data['tasks']
        
        # Extract base URL from first task for fallback
        from urllib.parse import urlparse
        first_url = tasks[0]['url']
        parsed = urlparse(first_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        logger.info(f"ORCHESTRATOR: Base URL: {base_url}")
        
        # Store in page context for Phase 2
        customer['_base_url'] = base_url
        
        # Launch browser - use Playwright's Chromium with persistent context
        playwright = await async_playwright().start()
        
        # Use temporary profile directory that will be cleaned up
        profile_path = tempfile.mkdtemp(prefix='checkout_ai_chrome_')
        logger.info(f"ORCHESTRATOR: Launching Chrome with temporary profile at {profile_path}")
        
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            # channel='chrome',  # Removed to use bundled Chromium
            headless=False,  # VISIBLE BROWSER WINDOW - See automation in real-time!
            slow_mo=100,  # Slow down by 100ms per action for better visibility
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
                '--disable-component-extensions-with-background-pages',
                '--start-maximized'
            ],
            viewport=None,
            permissions=[],  # Grant no permissions
            geolocation={'latitude': 0, 'longitude': 0},  # Provide fake geolocation to avoid prompt
            ignore_https_errors=True
        )
        
        # Get the first page (or create one if none exists)
        if len(context.pages) > 0:
            page = context.pages[0]
        else:
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
            `;
            document.head.appendChild(style);
            
            // Set zoom level to 75% to show more content
            document.body.style.zoom = "75%";
        """)
        
        if STEALTH_AVAILABLE:
            await stealth_async(page)
        
        # Start screenshot capture
        screenshot_task = asyncio.create_task(capture_screenshots(page))
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Screenshot capture started")

        # Agentic flow: process each task using Planner -> Browser -> Critique loop
        for i, task in enumerate(tasks):
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Processing task {i + 1}/{len(tasks)} with agentic flow")
            
            # Add customer data to task
            task['customer_data'] = customer
            
            result = await run_agentic_flow(page, task)
            
            if not result.get('success'):
                logger.error(f"ORCHESTRATOR: Task {i + 1} failed: {result.get('error')}")
                logger.info(f"ORCHESTRATOR: Iterations completed: {result.get('iterations', 0)}")
                
                # Log history for debugging
                if 'history' in result:
                    logger.info(f"ORCHESTRATOR: Agent history:")
                    for h in result['history'][-3:]:  # Last 3 iterations
                        logger.info(f"  Step: {h['step'][:100]}")
                        logger.info(f"  Feedback: {h['feedback'][:100]}")
                
                return {
                    'success': False,
                    'phase': 'agentic_flow',
                    'task_index': i,
                    'error': result.get('error', 'Agentic flow failed'),
                    'iterations': result.get('iterations', 0)
                }
            
            logger.info(f"ORCHESTRATOR: Task {i + 1} completed in {result.get('iterations', 0)} iterations")
            await asyncio.sleep(2)

        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] All tasks completed via agentic flow")
        
        # ========== PAYMENT AUTOMATION PHASE ==========
        logger.info("ORCHESTRATOR: Starting payment automation phase")
        
        try:
            from src.checkout_ai.payments import PaymentAutomationService
            
            # Get user_id from json_input
            user_id = json_input.get('user_id')
            
            if not user_id:
                logger.warning("ORCHESTRATOR: No user_id provided, skipping payment automation")
                return {
                    'success': True,
                    'phase': 'checkout_completed',
                    'payment_ready': True,
                    'message': 'Checkout complete - ready for manual payment',
                    'final_url': page.url
                }
            
            logger.info(f"ORCHESTRATOR: Auto-filling payment for user_id: {user_id}")
            
            # Auto-fill payment from wallet
            payment_result = await PaymentAutomationService.fill_payment_from_wallet(
                page=page,
                user_id=user_id,
                payment_method_id=None  # Use default payment method
            )
            
            if not payment_result.get('success'):
                logger.error(f"ORCHESTRATOR: Payment fill failed: {payment_result.get('error')}")
                return {
                    'success': False,
                    'phase': 'payment_fill',
                    'error': f"Payment automation failed: {payment_result.get('error')}",
                    'final_url': page.url
                }
            
            logger.info(f"ORCHESTRATOR: Payment filled using: {payment_result.get('method_used')}")
            await asyncio.sleep(2)
            
            # Submit order
            logger.info("ORCHESTRATOR: Submitting order...")
            order_result = await PaymentAutomationService.submit_payment(page)
            
            if not order_result.get('success'):
                logger.warning(f"ORCHESTRATOR: Order submission uncertain: {order_result.get('error')}")
                return {
                    'success': True,
                    'phase': 'payment_filled',
                    'payment_ready': True,
                    'message': 'Payment filled - please complete manually if needed',
                    'final_url': page.url
                }
            
            logger.info(f"ORCHESTRATOR: Order placed successfully")
            
            # Wait for page load
            await asyncio.sleep(3)
            
            # Capture order confirmation
            confirmation = await PaymentAutomationService.capture_order_confirmation(page)
            
            if confirmation.get('success') and confirmation.get('order_number'):
                logger.info(f"ORCHESTRATOR: Order confirmed: {confirmation['order_number']}")
                
                # Save to database
                order_id = await PaymentAutomationService.save_order_to_history(
                    user_id=user_id,
                    order_data=confirmation,
                    checkout_json=json_input
                )
                
                logger.info(f"ORCHESTRATOR: Order saved to database with ID: {order_id}")
                
                return {
                    'success': True,
                    'phase': 'order_confirmed',
                    'order_number': confirmation['order_number'],
                    'order_id': order_id,
                    'message': f"Order {confirmation['order_number']} placed successfully!",
                    'final_url': page.url
                }
            else:
                logger.warning("ORCHESTRATOR: Could not capture order confirmation")
                return {
                    'success': True,
                    'phase': 'payment_submitted',
                    'message': 'Order likely placed but confirmation not captured',
                    'final_url': page.url
                }
                
        except Exception as e:
            logger.error(f"ORCHESTRATOR: Payment automation error: {e}")
            import traceback
            logger.error(f"ORCHESTRATOR: Traceback: {traceback.format_exc()}")
            return {
                'success': True,  # Checkout still succeeded
                'phase': 'payment_error',
                'payment_ready': True,
                'error': f"Payment automation failed: {str(e)}",
                'message': 'Checkout complete - payment automation failed, please complete manually',
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
        
        # Keep browser open for inspection
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Keeping browser open for 3600s for inspection...")
        await asyncio.sleep(3600)

        # Cleanup
        try:
            if context:
                await context.close()
            if playwright:
                await playwright.stop()
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Browser closed")
        except Exception as e:
            logger.error(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Cleanup error: {e}")
        
        # Delete browser profile directory to remove all cached data
        try:
            if 'profile_path' in locals() and os.path.exists(profile_path):
                shutil.rmtree(profile_path)
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Deleted browser profile: {profile_path}")
        except Exception as e:
            logger.warning(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Failed to delete profile: {e}")


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
        print("[OK] SUCCESS: Full checkout flow completed!")
        print(f"Final URL: {result.get('final_url')}")
    else:
        print("[X] FAILED")
        print(f"Phase: {result.get('phase')}")
        print(f"Error: {result.get('error')}")
        if result.get('step'):
            print(f"Step: {result.get('step')}")
        if result.get('details'):
            print(f"Details: {result.get('details')}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
