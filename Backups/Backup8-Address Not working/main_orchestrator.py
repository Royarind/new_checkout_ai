#!/usr/bin/env python3
"""
Main Orchestrator - Stitches Phase 1 and Phase 2
Handles complete flow: Product Selection → Cart → Checkout → Shipping Form
"""

import asyncio
import json
import logging
from datetime import datetime
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Phase 1 imports
from phase1.universal_dom_finder import find_variant_dom
from phase1.add_to_cart_robust import add_to_cart_robust
from phase1.cart_navigator import navigate_to_cart

# Phase 2 imports
from phase2.checkout_flow import run_checkout_flow

# Stealth mode
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    async def stealth_async(page):
        pass

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
        
        # Launch browser once with stealth mode
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
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
                '--disable-renderer-backgrounding'
            ],
            slow_mo=500,
            chromium_sandbox=False
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            color_scheme='light',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-User': '?1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Ch-Ua': '"Chromium";v="131", "Not_A Brand";v="24"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"macOS"'
            },
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True
        )

        
        page = await context.new_page()
        
        # Block detection scripts and trackers
        await page.route('**/*', lambda route: (
            route.abort() if any(x in route.request.url.lower() for x in [
                'datadome', 'perimeterx', 'distilnetworks', 'shape-security',
                'recaptcha', 'hcaptcha', 'funcaptcha', 'arkoselabs',
                'cloudflare.com/cdn-cgi/challenge', 'px-cloud.net',
                'imperva.com', 'kasada', 'akamai/bot-manager'
            ]) else route.continue_()
        ))
        
        # Screenshot capture loop
        async def capture_screenshots():
            screenshot_path = '/tmp/chkout_screenshot.png'
            while True:
                try:
                    await page.screenshot(path=screenshot_path)
                    await asyncio.sleep(4)
                except:
                    break
        
        # Start screenshot capture in background
        asyncio.create_task(capture_screenshots())
        
        # Add human-like behavior simulation
        await page.evaluate("""
            () => {
                // Random mouse movements with realistic patterns
                let lastMove = Date.now();
                let mouseX = window.innerWidth / 2;
                let mouseY = window.innerHeight / 2;
                
                setInterval(() => {
                    if (Date.now() - lastMove > 2000) {
                        // Smooth movement instead of teleporting
                        mouseX += (Math.random() - 0.5) * 200;
                        mouseY += (Math.random() - 0.5) * 200;
                        mouseX = Math.max(0, Math.min(window.innerWidth, mouseX));
                        mouseY = Math.max(0, Math.min(window.innerHeight, mouseY));
                        
                        const event = new MouseEvent('mousemove', {
                            clientX: mouseX,
                            clientY: mouseY,
                            bubbles: true,
                            cancelable: true,
                            view: window
                        });
                        document.dispatchEvent(event);
                        lastMove = Date.now();
                    }
                }, 2000 + Math.random() * 3000);
                
                // Random scroll events with momentum
                let scrollPos = 0;
                setInterval(() => {
                    if (Math.random() > 0.6) {
                        const delta = (Math.random() - 0.5) * 150;
                        window.scrollBy({top: delta, behavior: 'smooth'});
                        scrollPos += delta;
                    }
                }, 10000 + Math.random() * 5000);
                
                // Keyboard activity simulation
                setInterval(() => {
                    if (Math.random() > 0.85) {
                        const event = new KeyboardEvent('keydown', {
                            key: 'Tab',
                            code: 'Tab',
                            bubbles: true
                        });
                        document.dispatchEvent(event);
                    }
                }, 20000 + Math.random() * 15000);
            }
        """)
        
        # Override navigator properties - aggressive anti-detection
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 1});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
            window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
            delete navigator.__proto__.webdriver;
            
            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            

            
            // Connection type
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                })
            });
            
            // Platform consistency
            Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});
            Object.defineProperty(navigator, 'vendor', {get: () => 'Google Inc.'});
            
            // Media devices
            if (navigator.mediaDevices) {
                navigator.mediaDevices.enumerateDevices = () => Promise.resolve([
                    {deviceId: 'default', kind: 'audioinput', label: 'Microphone', groupId: '1'},
                    {deviceId: 'default', kind: 'videoinput', label: 'Camera', groupId: '2'}
                ]);
            }
            
            // Canvas fingerprint randomization
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            const originalToBlob = HTMLCanvasElement.prototype.toBlob;
            const noise = () => Math.floor(Math.random() * 3) - 1;
            HTMLCanvasElement.prototype.toDataURL = function() {
                const context = this.getContext('2d');
                if (context && this.width > 0 && this.height > 0) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] += noise();
                        imageData.data[i+1] += noise();
                    }
                    context.putImageData(imageData, 0, 0);
                }
                return originalToDataURL.apply(this, arguments);
            };
            
            HTMLCanvasElement.prototype.toBlob = function(callback) {
                const context = this.getContext('2d');
                if (context && this.width > 0 && this.height > 0) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] += noise();
                    }
                    context.putImageData(imageData, 0, 0);
                }
                return originalToBlob.apply(this, arguments);
            };
            
            // WebGL fingerprint randomization
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                if (parameter === 7936) return 'WebKit';
                if (parameter === 7937) return 'WebKit WebGL';
                return getParameter.apply(this, arguments);
            };
            
            if (window.WebGL2RenderingContext) {
                const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return getParameter2.apply(this, arguments);
                };
            }
            
            // Audio context fingerprint
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                const originalCreateOscillator = AudioContext.prototype.createOscillator;
                AudioContext.prototype.createOscillator = function() {
                    const oscillator = originalCreateOscillator.apply(this, arguments);
                    const originalStart = oscillator.start;
                    oscillator.start = function() {
                        return originalStart.apply(this, arguments);
                    };
                    return oscillator;
                };
            }
            
            // Battery API
            if (navigator.getBattery) {
                navigator.getBattery = () => Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1
                });
            }
            
            // Screen properties
            Object.defineProperty(screen, 'availWidth', {get: () => 1920});
            Object.defineProperty(screen, 'availHeight', {get: () => 1080});
            Object.defineProperty(screen, 'width', {get: () => 1920});
            Object.defineProperty(screen, 'height', {get: () => 1080});
            Object.defineProperty(screen, 'colorDepth', {get: () => 24});
            Object.defineProperty(screen, 'pixelDepth', {get: () => 24});
            
            // Date/Time consistency
            const originalDate = Date;
            Date.prototype.getTimezoneOffset = function() { return 300; };
            
            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Speech synthesis
            if (window.speechSynthesis) {
                window.speechSynthesis.getVoices = () => [
                    {name: 'Google US English', lang: 'en-US', default: true}
                ];
            }
        """)
        
        # Apply stealth mode
        if STEALTH_AVAILABLE:
            await stealth_async(page)
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Browser launched with stealth mode")
        else:
            logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Browser launched (stealth mode not available)")
        
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
        logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Browser will stay open for 1 minute...")
        await asyncio.sleep(60)
        
        # Cleanup screenshot
        try:
            import os
            screenshot_path = '/tmp/chkout_screenshot.png'
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Screenshot cleaned up")
        except Exception as e:
            logger.warning(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Screenshot cleanup failed: {e}")
        
        return {
            'success': True,
            'message': 'Full checkout flow completed',
            'final_url': page.url
        }
        
    except Exception as e:
        logger.error(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Fatal error: {e}")
        # Cleanup screenshot on error
        try:
            import os
            screenshot_path = '/tmp/chkout_screenshot.png'
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
        except:
            pass
        
        return {
            'success': False,
            'phase': 'unknown',
            'error': str(e)
        }
    
    finally:
        # Cleanup
        try:
            # Delete screenshot file
            import os
            screenshot_path = '/tmp/chkout_screenshot.png'
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
                logger.info(f"ORCHESTRATOR: [{datetime.now().strftime('%H:%M:%S')}] Screenshot deleted")
            
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
