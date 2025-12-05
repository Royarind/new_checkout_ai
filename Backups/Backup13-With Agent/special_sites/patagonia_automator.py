#!/usr/bin/env python3
"""
Patagonia Specific Automator
Handles Patagonia's silhouette selection (alternate products)
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def select_patagonia_variant(page, variant_type, variant_value):
    """
    Patagonia-specific variant selection
    Handles silhouette (alternate products) which are links to different product pages
    For Patagonia: silhouette must be selected FIRST, then color, then size
    """
    logger.info(f"PATAGONIA: Selecting {variant_type}={variant_value}")
    
    try:
        # Check if silhouette is already selected
        if variant_type.lower() == 'silhouette':
            is_active = await page.evaluate(
                """(value) => {
                    const normalize = (text) => text ? text.toLowerCase().trim() : '';
                    const target = normalize(value);
                    
                    // Check if already active
                    const activeLink = document.querySelector('.alternate-product-link a.active strong');
                    if (activeLink && normalize(activeLink.textContent) === target) {
                        return true;
                    }
                    return false;
                }""",
                variant_value
            )
            
            if is_active:
                logger.info(f"PATAGONIA: ✓ {variant_value} already selected")
                return {'success': True, 'already_selected': True}
        
        # Select the variant
        result = await page.evaluate(
            """(args) => {
                const { variantType, variantValue } = args;
                const normalize = (text) => text ? text.toLowerCase().trim() : '';
                const target = normalize(variantValue);
                
                // Handle silhouette (alternate products)
                if (variantType.toLowerCase() === 'silhouette') {
                    const links = document.querySelectorAll('.alternate-product-link a');
                    for (const link of links) {
                        const strong = link.querySelector('strong');
                        if (strong && normalize(strong.textContent) === target) {
                            link.click();
                            return { success: true, selected: strong.textContent, navigates: true };
                        }
                    }
                }
                
                // Handle color swatches
                const swatches = document.querySelectorAll('button.product-swatch[data-caption]');
                for (const swatch of swatches) {
                    const caption = normalize(swatch.getAttribute('data-caption') || '');
                    if (caption === target) {
                        swatch.scrollIntoView({ block: 'center' });
                        swatch.click();
                        return { success: true, selected: swatch.getAttribute('data-caption') };
                    }
                }
                
                // Handle size radios
                const radios = document.querySelectorAll('input[type="radio"]');
                for (const radio of radios) {
                    const label = document.querySelector('label[for="' + radio.id + '"]');
                    const labelText = label ? normalize(label.textContent) : '';
                    const radioValue = normalize(radio.value);
                    
                    if (labelText === target || radioValue === target) {
                        radio.scrollIntoView({ block: 'center' });
                        radio.checked = true;
                        radio.dispatchEvent(new Event('change', { bubbles: true }));
                        if (label) label.click();
                        return { success: true, selected: labelText || radioValue };
                    }
                }
                
                return { success: false, error: 'Variant not found' };
            }""",
            {'variantType': variant_type, 'variantValue': variant_value}
        )
        
        if result.get('success'):
            logger.info(f"PATAGONIA: ✓ Selected {result.get('selected')}")
            
            # Wait for navigation if it's a silhouette change
            if result.get('navigates'):
                await asyncio.sleep(3)
                try:
                    await page.wait_for_load_state('domcontentloaded', timeout=10000)
                    await asyncio.sleep(2)  # Extra wait for page to fully load
                    logger.info(f"PATAGONIA: Page navigated to {page.url}")
                except Exception as e:
                    logger.warning(f"PATAGONIA: Navigation wait error: {e}")
            else:
                await asyncio.sleep(1.5)
            
            return {'success': True}
        else:
            logger.error(f"PATAGONIA: ✗ {result.get('error')}")
            return {'success': False, 'error': result.get('error')}
            
    except Exception as e:
        logger.error(f"PATAGONIA: Variant selection error - {e}")
        return {'success': False, 'error': str(e)}


def is_patagonia(url: str) -> bool:
    """Check if URL is Patagonia"""
    return 'patagonia.com' in url.lower()
