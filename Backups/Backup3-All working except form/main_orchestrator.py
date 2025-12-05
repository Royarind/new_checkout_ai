#!/usr/bin/env python3
"""
Main Orchestrator - Stitches Phase 1 and Phase 2
Handles complete flow: Product Selection → Cart → Checkout → Shipping Form
"""

import asyncio
import json
import logging
from datetime import datetime
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Phase 1 imports
from phase1.universal_dom_finder import find_variant_dom
from phase1.add_to_cart_robust import add_to_cart_robust
from phase1.cart_navigator import navigate_to_cart

# Phase 2 imports
from phase2.checkout_flow import run_checkout_flow

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def run_phase1(page, task):
    """
    Phase 1: Product selection and add to cart
    Returns: {'success': bool, 'error': str}
    """
    logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Starting Phase 1 for {task['url']}")
    
    try:
        # Navigate to product URL
        await page.goto(task['url'], wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(2)
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Loaded product page")
        
        # Select variants
        selected_variant = task.get('selectedVariant', {})
        
        for variant_type, variant_value in selected_variant.items():
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Selecting {variant_type}: {variant_value}")
            
            for attempt in range(3):
                result = await find_variant_dom(page, variant_type, variant_value)
                if result.get('success'):
                    logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] {variant_type} selected successfully")
                    break
                logger.warning(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] {variant_type} attempt {attempt + 1}/3 failed")
                await asyncio.sleep(1)
            
            if not result.get('success'):
                return {'success': False, 'error': f'Failed to select {variant_type}: {variant_value}'}
            
            await asyncio.sleep(1)
        
        # Set quantity if needed
        quantity = task.get('quantity', 1)
        if quantity > 1:
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Setting quantity: {quantity}")
            result = await find_variant_dom(page, 'quantity', str(quantity))
            await asyncio.sleep(1)
        
        # Add to cart
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Adding to cart...")
        cart_result = await add_to_cart_robust(page)
        
        if not cart_result.get('success'):
            return {'success': False, 'error': 'Failed to add to cart'}
        
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Added to cart successfully")
        await asyncio.sleep(2)
        
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
        
        # Launch browser once
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,
            args=['--no-sandbox', '--disable-dev-shm-usage'],
            slow_mo=1000
        )
        
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Browser launched")
        
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
        nav_result = await navigate_to_cart(page)
        
        if not nav_result.get('success'):
            return {
                'success': False,
                'phase': 'cart_navigation',
                'error': 'Failed to navigate to cart'
            }
        
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Cart page loaded")
        await asyncio.sleep(2)
        
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
        
        # Keep browser open for inspection
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Browser will stay open for 30 seconds...")
        await asyncio.sleep(30)
        
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
