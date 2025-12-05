#!/usr/bin/env python3
"""
Zara Specific Automator
Handles Zara's variant selection with screen-reader-text elements
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def select_zara_variant(page, variant_type, variant_value):
    """
    Zara-specific variant selection
    Uses screen-reader-text elements and aria-labels
    """
    logger.info(f"ZARA: Selecting {variant_type}={variant_value}")
    
    try:
        result = await page.evaluate("""
            (args) => {
                const { variantValue } = args;
                const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                const normalizedValue = normalize(variantValue);
                
                // Strategy 1: Find by screen reader text
                const items = document.querySelectorAll('.product-detail-color-item, .product-detail-size-item, [class*="variant"]');
                for (const item of items) {
                    const screenReaderText = item.querySelector('.screen-reader-text');
                    if (screenReaderText) {
                        const itemText = normalize(screenReaderText.textContent);
                        if (itemText === normalizedValue) {
                            if (typeof item.click === 'function') {
                                item.click();
                                return { success: true, selected: screenReaderText.textContent };
                            }
                            const button = item.querySelector('button, [role="button"]');
                            if (button && typeof button.click === 'function') {
                                button.click();
                                return { success: true, selected: screenReaderText.textContent };
                            }
                        }
                    }
                }
                
                // Strategy 2: Find by aria-label or title
                const allButtons = document.querySelectorAll('button, [role="button"]');
                for (const button of allButtons) {
                    const texts = [
                        button.getAttribute('aria-label'),
                        button.getAttribute('title'),
                        button.textContent
                    ];
                    for (const text of texts) {
                        if (text && normalize(text) === normalizedValue) {
                            if (typeof button.click === 'function') {
                                button.click();
                                return { success: true, selected: text };
                            }
                        }
                    }
                }
                
                return { success: false, error: `Variant "${variantValue}" not found` };
            }
        """, {'variantValue': variant_value})
        
        if result.get('success'):
            logger.info(f"ZARA: ✓ Selected {result.get('selected')}")
            await asyncio.sleep(2)
            return {'success': True}
        else:
            logger.error(f"ZARA: ✗ {result.get('error')}")
            return {'success': False, 'error': result.get('error')}
            
    except Exception as e:
        logger.error(f"ZARA: Error - {e}")
        return {'success': False, 'error': str(e)}


