from playwright.async_api import Page
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

async def select_patagonia_variant(page: Page, variant_type: str, variant_value: str) -> Dict[str, Any]:
    """
    Specific handler for Patagonia.com
    """
    logger.info(f"Patagonia Handler: Selecting {variant_type}={variant_value}")
    
    try:
        # Patagonia usually uses standard radio buttons or swatches
        # We can try to leverage the page's specific structure if known
        # For now, we'll use a targeted search for their specific classes
        
        if variant_type == 'color':
            # Look for color swatches
            # Patagonia often uses <input type="radio" name="color"> or similar
            result = await page.evaluate("""
                (value) => {
                    const normalize = t => t.toLowerCase().trim();
                    const target = normalize(value);
                    
                    // Try finding by aria-label or title in swatches
                    const swatches = document.querySelectorAll('.swatch-element, [class*="color-swatch"]');
                    for (const swatch of swatches) {
                        const text = swatch.textContent || swatch.getAttribute('aria-label') || swatch.getAttribute('title');
                        if (text && normalize(text).includes(target)) {
                            swatch.click();
                            return { success: true, method: 'swatch_click' };
                        }
                    }
                    return { success: false };
                }
            """, variant_value)
            
            if result['success']:
                return {'success': True, 'content': f"Patagonia: Selected color {variant_value}"}
                
        elif variant_type == 'size':
            # Look for size buttons
            result = await page.evaluate("""
                (value) => {
                    const normalize = t => t.toLowerCase().trim();
                    const target = normalize(value);
                    
                    const sizes = document.querySelectorAll('.size-swatch, [class*="size-tile"]');
                    for (const size of sizes) {
                        if (normalize(size.textContent) === target) {
                            size.click();
                            return { success: true, method: 'size_click' };
                        }
                    }
                    return { success: false };
                }
            """, variant_value)
            
            if result['success']:
                return {'success': True, 'content': f"Patagonia: Selected size {variant_value}"}
                
    except Exception as e:
        logger.error(f"Patagonia handler error: {e}")
        
    return {'success': False, 'reason': 'Patagonia specific selectors not found'}
