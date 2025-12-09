"""Automatic Variant Detection from Product Pages"""

import asyncio
from playwright.async_api import async_playwright


async def detect_variants(url):
    """
    Detect available variants from product page
    Returns: {'variants': {...}, 'product_name': str, 'price': str}
    """
    
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                print(f"Playwright launch failed: {e}")
                return {'variants': {}, 'product_name': '', 'price': '', 'error': f"Browser launch failed: {e}"}
                
            page = await browser.new_page()
            
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(2)
                
                # Extract variants using JavaScript
                result = await page.evaluate("""
                    () => {
                        const variants = {};
                        
                        // Detect size options
                        const sizeSelectors = [
                            'select[name*="size" i]',
                            'select[id*="size" i]',
                            '[class*="size"] button',
                            '[data-testid*="size"] button'
                        ];
                        
                        for (const selector of sizeSelectors) {
                            const elements = document.querySelectorAll(selector);
                            if (elements.length > 0) {
                                const sizes = [];
                                elements.forEach(el => {
                                    const text = el.textContent?.trim() || el.value;
                                    if (text && text.length < 10) sizes.push(text);
                                });
                                if (sizes.length > 0) {
                                    variants.size = {required: true, options: sizes};
                                    break;
                                }
                            }
                        }
                        
                        // Detect color options
                        const colorSelectors = [
                            'select[name*="color" i]',
                            '[class*="color"] button',
                            '[data-testid*="color"] button'
                        ];
                        
                        for (const selector of colorSelectors) {
                            const elements = document.querySelectorAll(selector);
                            if (elements.length > 0) {
                                const colors = [];
                                elements.forEach(el => {
                                    const text = el.textContent?.trim() || el.getAttribute('aria-label') || el.value;
                                    if (text && text.length < 30) colors.push(text);
                                });
                                if (colors.length > 0) {
                                    variants.color = {required: true, options: colors};
                                    break;
                                }
                            }
                        }
                        
                        // Get product name
                        const nameSelectors = ['h1', '[class*="product-name"]', '[class*="product-title"]'];
                        let productName = '';
                        for (const selector of nameSelectors) {
                            const el = document.querySelector(selector);
                            if (el) {
                                productName = el.textContent?.trim();
                                break;
                            }
                        }
                        
                        // Get price
                        const priceSelectors = ['[class*="price"]', '[data-testid*="price"]'];
                        let price = '';
                        for (const selector of priceSelectors) {
                            const el = document.querySelector(selector);
                            if (el && el.textContent?.includes('$')) {
                                price = el.textContent?.trim();
                                break;
                            }
                        }
                        
                        return {
                            variants: variants,
                            product_name: productName,
                            price: price
                        };
                    }
                """)
                
                await browser.close()
                return result
                
            except Exception as e:
                await browser.close()
                return {
                    'variants': {},
                    'product_name': '',
                    'price': '',
                    'error': str(e)
                }
    except Exception as e:
        return {
            'variants': {},
            'product_name': '',
            'price': '',
            'error': f"Playwright error: {str(e)}"
        }
