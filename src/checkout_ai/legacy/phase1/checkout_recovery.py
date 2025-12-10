"""
Checkout URL Recovery System

Handles navigation failures during checkout by attempting direct URL navigation
Similar to cart_navigator.py but for checkout flow pages
"""

import asyncio
import logging
from playwright.async_api import Page
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def recover_checkout_page(page: Page, expected_step: str = "") -> Dict[str, Any]:
    """
    Attempt to recover checkout flow by trying common checkout URLs
    
    Args:
        page: Playwright page
        expected_step: What step we expect (e.g., "shipping", "payment", "review")
    
    Returns:
        Dict with 'success': bool, 'url': str, 'method': str
    """
    logger.info(f"CHECKOUT RECOVERY: Attempting to recover checkout page (expected: {expected_step})")
    
    current_url = page.url.lower()
    base_url = '/'.join(page.url.split('/')[:3])
    
    # If already on checkout page, no recovery needed
    if '/checkout' in current_url and 'cart' not in current_url:
        logger.info("CHECKOUT RECOVERY: Already on checkout page, no recovery needed")
        return {'success': True, 'url': page.url, 'method': 'already_there'}
    
    # Strategy 1: Try common checkout URLs
    checkout_urls = [
        f"{base_url}/checkout",
        f"{base_url}/checkout/",
        f"{base_url}/checkout/shipping",
        f"{base_url}/checkout/information",
        f"{base_url}/checkout/contact",
        f"{base_url}/secure/checkout",
    ]
    
    for checkout_url in checkout_urls:
        try:
            logger.info(f"CHECKOUT RECOVERY: Trying URL: {checkout_url}")
            await page.goto(checkout_url, wait_until='domcontentloaded', timeout=10000)
            await asyncio.sleep(1)
            
            # Verify it's a checkout page
            is_checkout = await page.evaluate("""
                () => {
                    const text = document.body.textContent.toLowerCase();
                    const url = window.location.href.toLowerCase();
                    const hasCheckoutIndicators = 
                        url.includes('checkout') ||
                        text.includes('shipping address') ||
                        text.includes('billing address') ||
                        text.includes('delivery address') ||
                        text.includes('payment method') ||
                        text.includes('place order') ||
                        text.includes('complete order');
                    
                    // Not home page or product page
                    const notWrongPage = 
                        !url.includes('/product') &&
                        !text.includes('shop now') &&
                        !text.includes('featured products');
                    
                    return hasCheckoutIndicators && notWrongPage;
                }
            """)
            
            if is_checkout:
                logger.info(f"CHECKOUT RECOVERY: ✓ Successfully recovered to {page.url}")
                return {'success': True, 'url': page.url, 'method': 'direct_url'}
                
        except Exception as e:
            logger.warning(f"CHECKOUT RECOVERY: URL {checkout_url} failed: {e}")
            continue
    
    # Strategy 2: Click checkout button from current page
    logger.info("CHECKOUT RECOVERY: Trying to find checkout button on current page")
    try:
        checkout_clicked = await page.evaluate("""
            () => {
                const buttons = document.querySelectorAll('button, a, [role="button"]');
                for (const btn of buttons) {
                    const text = (btn.textContent || '').toLowerCase();
                    const href = (btn.getAttribute('href') || '').toLowerCase();
                    
                    if (text.includes('checkout') || 
                        text.includes('proceed') ||
                        href.includes('checkout')) {
                        
                        // Skip if it's navigation or footer link
                        const isNav = btn.closest('nav, header, footer, .nav, .header, .footer');
                        if (!isNav) {
                            btn.click();
                            return true;
                        }
                    }
                }
                return false;
            }
        """)
        
        if checkout_clicked:
            await asyncio.sleep(2)
            logger.info(f"CHECKOUT RECOVERY: ✓ Clicked checkout button, now at {page.url}")
            return {'success': True, 'url': page.url, 'method': 'checkout_button'}
            
    except Exception as e:
        logger.warning(f"CHECKOUT RECOVERY: Checkout button click failed: {e}")
    
    logger.error("CHECKOUT RECOVERY: All recovery strategies failed")
    return {'success': False, 'url': page.url, 'method': 'none'}


async def is_on_wrong_page(page: Page) -> bool:
    """Check if page navigated to wrong place (home, product, etc.)"""
    try:
        result = await page.evaluate("""
            () => {
                const url = window.location.href.toLowerCase();
                const text = document.body.textContent.toLowerCase();
                
                // Check if on wrong page
                const isHomePage = url === window.location.origin + '/' || 
                                  url.endsWith('.com/') || 
                                  text.includes('shop now') ||
                                  text.includes('featured products');
                
                const isProductPage = url.includes('/product') || 
                                     url.includes('/p/') ||
                                     text.includes('add to cart');
                
                const isCategoryPage = url.includes('/collections') ||
                                      url.includes('/categories') ||
                                      url.includes('/shop');
                
                return isHomePage || isProductPage || isCategoryPage;
            }
        """)
        return result
    except:
        return False


# Export for use
__all__ = ['recover_checkout_page', 'is_on_wrong_page']
