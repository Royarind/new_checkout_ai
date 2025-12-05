#!/usr/bin/env python3
"""
Karl Lagerfeld Automator
Handles Karl Lagerfeld-specific checkout quirks
"""

import asyncio
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)

async def add_to_cart_with_double_click(page: Page, button_locator) -> bool:
    """
    Karl Lagerfeld-specific add to cart with double-click
    First click often doesn't register, so we click twice
    Removes overlays before clicking
    """
    try:
        logger.info("KARL LAGERFELD: Removing overlays and executing add to cart")
        
        # Remove overlays that block interaction
        await page.evaluate("""
            () => {
                // Remove all overlays/backdrops
                document.querySelectorAll('[class*="overlay"], [class*="backdrop"], [class*="modal-backdrop"]').forEach(el => el.remove());
                // Enable interactions
                document.body.style.pointerEvents = 'auto';
                document.body.style.overflow = 'auto';
            }
        """)
        await asyncio.sleep(0.3)
        
        # Try form submission first (Add to Bag is a submit button)
        form_submitted = await page.evaluate("""
            () => {
                const btn = document.querySelector('button[type="submit"][form="main-product-form"]');
                if (btn) {
                    const formId = btn.getAttribute('form');
                    const form = document.getElementById(formId);
                    if (form) {
                        form.requestSubmit();
                        return true;
                    }
                }
                return false;
            }
        """)
        
        if form_submitted:
            logger.info("KARL LAGERFELD: Form submitted successfully")
            await asyncio.sleep(2)
            return True
        
        # Fallback: double-click
        logger.info("KARL LAGERFELD: Form submit failed, trying double-click")
        await button_locator.click(timeout=5000, force=True)
        logger.info("KARL LAGERFELD: First click executed")
        await asyncio.sleep(0.8)
        await button_locator.click(timeout=5000, force=True)
        logger.info("KARL LAGERFELD: Second click executed")
        await asyncio.sleep(2)
        return True
        
    except Exception as e:
        logger.error(f"KARL LAGERFELD: Add to cart failed - {e}")
        return False


async def dismiss_geolocation_modal(page: Page) -> bool:
    """
    Dismiss Karl Lagerfeld's geolocation/country selector modal
    """
    try:
        await asyncio.sleep(1)
        
        dismissed = await page.evaluate("""
            () => {
                const keywords = ['shop now', 'continue', 'close', 'dismiss'];
                const buttons = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                
                for (const btn of buttons) {
                    const text = (btn.textContent || '').toLowerCase().trim();
                    if (keywords.some(kw => text.includes(kw))) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }
        """)
        
        if dismissed:
            logger.info("KARL LAGERFELD: Geolocation modal dismissed")
            await asyncio.sleep(1)
        
        return dismissed
        
    except Exception as e:
        logger.debug(f"KARL LAGERFELD: Could not dismiss modal - {e}")
        return False


async def navigate_to_checkout(page: Page) -> bool:
    """
    Karl Lagerfeld-specific checkout navigation
    Strategy: Navigate directly to cart URL, then click checkout
    """
    try:
        logger.info("KARL LAGERFELD: Navigating to checkout")
        
        # Get base URL and navigate to cart page
        current_url = page.url
        if '/en-us/' in current_url:
            cart_url = 'https://www.karllagerfeld.com/en-us/cart'
        elif '/en-in/' in current_url:
            cart_url = 'https://www.karllagerfeld.com/en-in/cart'
        else:
            cart_url = 'https://www.karllagerfeld.com/cart'
        
        logger.info(f"KARL LAGERFELD: Navigating to {cart_url}")
        await page.goto(cart_url, wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(2)
        
        # Scroll to top to ensure button loads
        logger.info("KARL LAGERFELD: Scrolling to top")
        await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        await asyncio.sleep(2)
        
        # Aggressive overlay removal and interaction enabling
        await page.evaluate("""
            () => {
                // Remove all overlays
                document.querySelectorAll('[class*="overlay"], [class*="backdrop"], [class*="modal"]').forEach(el => {
                    if (el.style.position === 'fixed' || el.style.position === 'absolute') {
                        el.remove();
                    }
                });
                // Enable all interactions
                document.body.style.pointerEvents = 'auto';
                document.body.style.overflow = 'auto';
                // Remove disabled attribute from all buttons
                document.querySelectorAll('button[disabled]').forEach(btn => btn.removeAttribute('disabled'));
            }
        """)
        await asyncio.sleep(1)
        
        # Scroll to checkout button and click with mouse events
        clicked = await page.evaluate("""
            () => {
                const btn = document.querySelector('button[type="submit"][name="checkout"]');
                if (!btn) return false;
                
                // Scroll into view
                btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                
                // Wait a bit for scroll
                return new Promise(resolve => {
                    setTimeout(() => {
                        // Dispatch full mouse event sequence
                        const rect = btn.getBoundingClientRect();
                        const x = rect.left + rect.width / 2;
                        const y = rect.top + rect.height / 2;
                        
                        ['mousedown', 'mouseup', 'click'].forEach(eventType => {
                            btn.dispatchEvent(new MouseEvent(eventType, {
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: x,
                                clientY: y
                            }));
                        });
                        
                        resolve(true);
                    }, 1000);
                });
            }
        """)
        
        if clicked:
            logger.info("KARL LAGERFELD: Checkout button clicked with mouse events, waiting for navigation")
            await asyncio.sleep(3)
            await page.wait_for_load_state('domcontentloaded', timeout=10000)
            logger.info(f"KARL LAGERFELD: Navigated to {page.url}")
            return True
        
        logger.error("KARL LAGERFELD: Checkout button not found or not clickable")
        return False
        
    except Exception as e:
        logger.error(f"KARL LAGERFELD: Checkout navigation failed - {e}")
        return False



# __all__ = ['add_to_cart_with_double_click', 'dismiss_geolocation_modal', 'navigate_to_checkout', 'is_karl_lagerfeld', 'select_karllagerfeld_variant']


async def select_karllagerfeld_variant(page: Page, variant_type: str, variant_value: str) -> dict:
    """
    Karl Lagerfeld-specific variant selection
    Uses swatch links with aria-label for colors and radio buttons for sizes
    """
    logger.info(f"KARL LAGERFELD: Selecting {variant_type}={variant_value}")
    
    try:
        result = await page.evaluate(
            """(args) => {
                const { variantValue } = args;
                const normalize = (text) => text ? text.toLowerCase().trim() : '';
                const target = normalize(variantValue);
                
                // Try swatch links first (for colors)
                const swatches = document.querySelectorAll('a[class*="swatch"], a[aria-label]');
                for (const swatch of swatches) {
                    const ariaLabel = normalize(swatch.getAttribute('aria-label') || '');
                    if (ariaLabel === target) {
                        swatch.scrollIntoView({ block: 'center', behavior: 'smooth' });
                        swatch.click();
                        return { 
                            success: true, 
                            selected: ariaLabel,
                            method: 'swatch_link'
                        };
                    }
                }
                
                // Try radio buttons (for sizes)
                const radios = document.querySelectorAll('input[type="radio"][name*="option"], input[type="radio"][name*="Option"]');
                for (const radio of radios) {
                    const label = document.querySelector('label[for="' + radio.id + '"]');
                    const labelText = label ? normalize(label.textContent) : '';
                    const radioValue = normalize(radio.value);
                    
                    if (labelText === target || radioValue === target) {
                        radio.scrollIntoView({ block: 'center', behavior: 'smooth' });
                        radio.checked = true;
                        radio.dispatchEvent(new Event('change', { bubbles: true }));
                        if (label) label.click();
                        return { 
                            success: true, 
                            selected: labelText || radioValue,
                            method: 'radio_button'
                        };
                    }
                }
                
                return { success: false, error: 'Variant not found' };
            }""",
            {'variantValue': variant_value}
        )
        
        if result.get('success'):
            logger.info(f"KARL LAGERFELD: ✓ Selected {result.get('selected')} via {result.get('method')}")
            # Wait for page navigation if color was selected
            if variant_type.lower() == 'color':
                await asyncio.sleep(3)
                try:
                    await page.wait_for_load_state('domcontentloaded', timeout=5000)
                    logger.info("KARL LAGERFELD: Page reloaded after color selection")
                except:
                    pass
            else:
                await asyncio.sleep(1.5)
            return {'success': True}
        else:
            logger.error(f"KARL LAGERFELD: ✗ {result.get('error')}")
            return {'success': False, 'error': result.get('error')}
            
    except Exception as e:
        logger.error(f"KARL LAGERFELD: Variant selection error - {e}")
        return {'success': False, 'error': str(e)}
    
def is_karl_lagerfeld(url: str) -> bool:
    """Check if URL is Karl Lagerfeld"""
    return 'karllagerfeld.com' in url.lower()
