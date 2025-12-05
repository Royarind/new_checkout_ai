#!/usr/bin/env python3
"""
HeyDude Specific Automator
Handles HeyDude's Shopify-based variant selection
"""

import asyncio
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)

async def select_heydude_variant(page: Page, variant_type: str, variant_value: str) -> dict:
    """
    HeyDude-specific variant selection
    Uses Shopify variant selector patterns with radio buttons
    """
    logger.info(f"HEYDUDE: Selecting {variant_type}={variant_value}")
    
    try:
        result = await page.evaluate(
            """(args) => {
                const { variantValue } = args;
                const normalize = (text) => text ? text.toLowerCase().trim() : '';
                const target = normalize(variantValue);
                
                // HeyDude uses Shopify radio buttons for variants
                const selectors = [
                    'input[type="radio"][name*="option"]',
                    'input[type="radio"][name*="Option"]',
                    'input[type="radio"][data-product-color-label]',
                ];
                
                for (const selector of selectors) {
                    const radios = document.querySelectorAll(selector);
                    
                    for (const radio of radios) {
                        const value = normalize(radio.value);
                        const ariaLabel = normalize(radio.getAttribute('aria-label') || '');
                        const dataColorLabel = normalize(radio.getAttribute('data-product-color-label') || '');
                        
                        // Find associated label
                        const label = radio.id ? document.querySelector('label[for="' + radio.id + '"]') : null;
                        const labelText = label ? normalize(label.textContent) : '';
                        
                        if (value === target || ariaLabel === target || dataColorLabel === target || labelText === target) {
                            radio.scrollIntoView({ block: 'center', behavior: 'smooth' });
                            radio.checked = true;
                            radio.dispatchEvent(new Event('change', { bubbles: true }));
                            if (label) label.click();
                            return { 
                                success: true, 
                                selected: dataColorLabel || labelText || value || ariaLabel,
                                method: 'radio_button'
                            };
                        }
                    }
                }
                
                return { success: false, error: 'Variant not found' };
            }""",
            {'variantValue': variant_value}
        )
        
        if result.get('success'):
            logger.info(f"HEYDUDE: ✓ Selected {result.get('selected')} via {result.get('method')}")
            await asyncio.sleep(1.5)
            return {'success': True}
        else:
            logger.error(f"HEYDUDE: ✗ {result.get('error')}")
            return {'success': False, 'error': result.get('error')}
            
    except Exception as e:
        logger.error(f"HEYDUDE: Variant selection error - {e}")
        return {'success': False, 'error': str(e)}




def is_heydude(url: str) -> bool:
    """Check if URL is HeyDude"""
    return 'heydude.com' in url.lower()
