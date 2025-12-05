#!/usr/bin/env python3
"""
TravisMathew Specific Automator
Handles TravisMathew's variant selection
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def select_travismathew_variant(page, variant_type, variant_value):
    """
    TravisMathew-specific variant selection
    Uses input elements with name attributes for Color and Size
    """
    logger.info(f"TRAVISMATHEW: Selecting {variant_type}={variant_value}")
    
    try:
        # Determine the input name based on variant type
        if variant_type.lower() == 'color':
            input_name = 'Color'
        elif variant_type.lower() == 'size':
            input_name = 'Size'
        else:
            return {'success': False, 'error': f'Unknown variant type: {variant_type}'}
        
        # Try to find and click the input
        clicked = await page.evaluate("""
            (args) => {
                const { inputName, value } = args;
                const input = document.querySelector(`input[name="${inputName}"][value="${value}"]`);
                if (input) {
                    input.scrollIntoView({ block: 'center' });
                    input.click();
                    return true;
                }
                return false;
            }
        """, {'inputName': input_name, 'value': variant_value})
        
        if clicked:
            logger.info(f"TRAVISMATHEW: ✓ Selected {variant_value}")
            await asyncio.sleep(0.5)
            return {'success': True}
        else:
            logger.error(f"TRAVISMATHEW: ✗ {variant_value} not found")
            return {'success': False, 'error': f'{variant_value} not found'}
            
    except Exception as e:
        logger.error(f"TRAVISMATHEW: Error - {e}")
        return {'success': False, 'error': str(e)}


