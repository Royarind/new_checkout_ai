#!/usr/bin/env python3
"""
Patagonia Specific Automator
Handles Patagonia's variant selection using data attributes
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def select_patagonia_variant(page, variant_type, variant_value):
    """
    Patagonia-specific variant selection
    Uses data-caption for colors and data-attr-value for sizes
    """
    logger.info(f"PATAGONIA: Selecting {variant_type}={variant_value}")
    
    try:
        if variant_type.lower() == 'color':
            # Patagonia uses data-attr for colors (e.g., PNDG for Pond Green)
            # Try to click the button with matching data-caption
            clicked = await page.evaluate("""
                (colorName) => {
                    const buttons = document.querySelectorAll('button.product-swatch[data-caption]');
                    for (const btn of buttons) {
                        const caption = btn.getAttribute('data-caption');
                        if (caption && caption.toLowerCase().includes(colorName.toLowerCase())) {
                            btn.scrollIntoView({block: 'center'});
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """, variant_value)
            
            if clicked:
                logger.info(f"PATAGONIA: ✓ Selected color {variant_value}")
                await asyncio.sleep(2)
                return {'success': True}
                
        elif variant_type.lower() == 'size':
            # Patagonia size buttons
            clicked = await page.evaluate("""
                (sizeName) => {
                    // Try size buttons
                    const sizeButtons = document.querySelectorAll('button[data-attr-value]');
                    for (const btn of sizeButtons) {
                        const value = btn.getAttribute('data-attr-value');
                        const text = btn.textContent?.trim();
                        if ((value && value === sizeName) || (text && text === sizeName)) {
                            btn.scrollIntoView({block: 'center'});
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """, variant_value)
            
            if clicked:
                logger.info(f"PATAGONIA: ✓ Selected size {variant_value}")
                await asyncio.sleep(2)
                return {'success': True}
        
        logger.error(f"PATAGONIA: ✗ {variant_type}={variant_value} not found")
        return {'success': False, 'error': f'{variant_type} not found'}
        
    except Exception as e:
        logger.error(f"PATAGONIA: Error - {e}")
        return {'success': False, 'error': str(e)}


