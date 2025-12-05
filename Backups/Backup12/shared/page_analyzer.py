"""
Page Content Analyzer - Detects page type and available actions
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def analyze_page_content(page):
    """
    Analyze page content to determine what's visible and actionable
    Returns: dict with page type, visible elements, and blocking overlays
    """
    try:
        analysis = await page.evaluate("""
            () => {
                const isVisible = (el) => {
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && 
                           style.visibility !== 'hidden' && 
                           style.display !== 'none' &&
                           el.offsetParent !== null;
                };
                
                // Check for blocking overlays
                const overlays = Array.from(document.querySelectorAll(
                    '[class*="modal"], [class*="drawer"], [class*="overlay"], [class*="popup"], [role="dialog"]'
                )).filter(el => {
                    const style = window.getComputedStyle(el);
                    return isVisible(el) && parseInt(style.zIndex) > 100;
                });
                
                const hasBlockingOverlay = overlays.length > 0;
                const overlayInfo = overlays.map(el => ({
                    classes: el.className,
                    zIndex: window.getComputedStyle(el).zIndex,
                    text: el.textContent?.substring(0, 100)
                }));
                
                // Detect page type
                const url = window.location.href.toLowerCase();
                let pageType = 'unknown';
                if (url.includes('/cart') || url.includes('/basket')) pageType = 'cart';
                else if (url.includes('/checkout') || url.includes('/payment')) pageType = 'checkout';
                else if (url.includes('/product') || url.includes('/item')) pageType = 'product';
                
                // Get visible buttons
                const buttons = Array.from(document.querySelectorAll(
                    'button, a[role="button"], input[type="submit"], input[type="button"]'
                )).filter(isVisible).slice(0, 10).map(el => ({
                    text: el.textContent?.trim().substring(0, 40),
                    ariaLabel: el.getAttribute('aria-label')?.substring(0, 40)
                }));
                
                // Get visible form inputs
                const inputs = Array.from(document.querySelectorAll(
                    'input:not([type="hidden"]), select, textarea'
                )).filter(isVisible).slice(0, 10).map(el => ({
                    type: el.type || el.tagName.toLowerCase(),
                    name: el.name,
                    id: el.id,
                    placeholder: el.placeholder?.substring(0, 30)
                }));
                
                // Detect variant selectors (product page)
                const variantSelectors = Array.from(document.querySelectorAll(
                    'select, [role="radiogroup"], [class*="variant"], [class*="option"]'
                )).filter(isVisible).length;
                
                // Detect add to cart button
                const addToCartButton = Array.from(document.querySelectorAll('button, input[type="submit"]'))
                    .filter(isVisible)
                    .find(el => {
                        const text = el.textContent?.toLowerCase() || '';
                        return text.includes('add to cart') || text.includes('add to bag');
                    });
                
                return {
                    pageType,
                    hasBlockingOverlay,
                    overlayInfo,
                    buttons,
                    inputs,
                    hasVariantSelectors: variantSelectors > 0,
                    hasAddToCart: !!addToCartButton,
                    url: window.location.href
                };
            }
        """)
        
        logger.info(f"PAGE ANALYZER: Type={analysis['pageType']}, Overlay={analysis['hasBlockingOverlay']}, Buttons={len(analysis['buttons'])}, Inputs={len(analysis['inputs'])}")
        
        return analysis
        
    except Exception as e:
        logger.error(f"PAGE ANALYZER: Error analyzing page: {e}")
        return {
            'pageType': 'unknown',
            'hasBlockingOverlay': False,
            'overlayInfo': [],
            'buttons': [],
            'inputs': [],
            'hasVariantSelectors': False,
            'hasAddToCart': False,
            'url': ''
        }


async def wait_for_page_ready(page, timeout=10):
    """
    Wait for page to be ready (no blocking overlays, content loaded)
    Returns: True if ready, False if timeout
    """
    start_time = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start_time < timeout:
        analysis = await analyze_page_content(page)
        
        if not analysis['hasBlockingOverlay']:
            logger.info("PAGE ANALYZER: Page ready - no blocking overlays")
            return True
        
        logger.info(f"PAGE ANALYZER: Waiting for overlays to clear... ({len(analysis['overlayInfo'])} found)")
        await asyncio.sleep(1)
    
    logger.warning("PAGE ANALYZER: Timeout waiting for page ready")
    return False
