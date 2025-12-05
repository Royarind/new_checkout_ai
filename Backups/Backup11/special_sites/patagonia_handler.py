"""
Patagonia-specific variant selection handler
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

async def select_patagonia_variant(page, variant_type, variant_value):
    """Handle Patagonia color/size selection using data attributes"""
    
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
                await asyncio.sleep(2)
                return {'success': True, 'method': 'patagonia_color'}
                
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
                await asyncio.sleep(2)
                return {'success': True, 'method': 'patagonia_size'}
        
        return {'success': False}
        
    except Exception as e:
        logger.error(f"Patagonia handler error: {e}")
        return {'success': False}
