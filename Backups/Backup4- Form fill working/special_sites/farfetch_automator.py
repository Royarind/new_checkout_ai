import asyncio
import json
import re
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)

class FarfetchAutomator:
    def __init__(self):
        self.size_map = {
            'XS': '18', 'S': '19', 'M': '20', 'L': '21', 
            'XL': '22', 'XXL': '23', 'XXXL': '24', '4XL': '25'
        }
    
    async def select_variant(self, page, variant_type, variant_value):
        """Human-like variant selection for Farfetch with loading state handling"""
        # Wait for initial page load with shorter timeout
        try:
            await page.wait_for_load_state('domcontentloaded', timeout=5000)
        except:
            pass
        await asyncio.sleep(1)
        
        if variant_type.lower() == 'size':
            return await self._select_size(page, variant_value)
        elif variant_type.lower() == 'color':
            return await self._select_color(page, variant_value)
        return False
    
    async def _select_size(self, page, size):
        """Select size using multiple strategies"""
        # Wait for page to load
        try:
            await page.wait_for_load_state('domcontentloaded', timeout=3000)
        except:
            pass
        await asyncio.sleep(1)
        
        # Strategy 1: Try clicking size selector buttons
        clicked = await page.evaluate("""
            (size) => {
                const normalize = (text) => text ? text.toLowerCase().trim() : '';
                const sizeNorm = normalize(size);
                
                // Look for size buttons/selectors
                const selectors = [
                    'button[data-testid*="size"]',
                    '[data-testid*="size"] button',
                    'button[aria-label*="size"]',
                    '.size-selector button',
                    '[class*="size"] button'
                ];
                
                for (const selector of selectors) {
                    const buttons = document.querySelectorAll(selector);
                    for (const btn of buttons) {
                        const text = normalize(btn.textContent);
                        const ariaLabel = normalize(btn.getAttribute('aria-label') || '');
                        if (text === sizeNorm || ariaLabel.includes(sizeNorm)) {
                            btn.scrollIntoView({block: 'center'});
                            btn.click();
                            return true;
                        }
                    }
                }
                return false;
            }
        """, size)
        
        if clicked:
            logger.info(f"Selected size {size} via button click")
            return True
        
        # Strategy 2: URL-based selection (fallback)
        size_data = await page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                for (const script of scripts) {
                    try {
                        const data = JSON.parse(script.textContent);
                        if (data.hasVariant) {
                            return data.hasVariant.map(v => ({
                                size: v.size,
                                url: v.offers.url,
                                sku: v.sku
                            }));
                        }
                    } catch (e) {}
                }
                return null;
            }
        """)
        
        if size_data:
            target_size = next((item for item in size_data if item['size'].upper() == size.upper()), None)
            if target_size:
                url_match = re.search(r'size=(\d+)', target_size['url'])
                if url_match:
                    size_param = url_match.group(1)
                    current_url = page.url
                    if 'size=' in current_url:
                        new_url = re.sub(r'size=\d+', f'size={size_param}', current_url)
                    else:
                        separator = '&' if '?' in current_url else '?'
                        new_url = f"{current_url}{separator}size={size_param}"
                    
                    await page.goto(new_url)
                    await asyncio.sleep(2)
                    logger.info(f"Selected size {size} via URL navigation")
                    return True
        
        logger.error(f"Size {size} not found")
        return False
    
    async def _select_color(self, page, color):
        """Select color using human-like clicking"""
        strategies = [
            self._click_color_swatch,
            self._click_color_button,
            self._select_color_dropdown
        ]
        
        for strategy in strategies:
            if await strategy(page, color):
                return True
        
        logger.error(f"Color {color} not found")
        return False
    
    async def _click_color_swatch(self, page, color):
        """Click color swatch/image with improved selectors"""
        return await page.evaluate("""
            (color) => {
                const normalize = (text) => text ? text.toLowerCase().trim() : '';
                const colorNorm = normalize(color);
                
                const selectors = [
                    '[data-testid*="color"] button',
                    '[data-testid*="colour"] button', 
                    'button[data-testid*="color"]',
                    'button[aria-label*="color"]',
                    'button[aria-label*="colour"]',
                    '[class*="color-swatch"] button',
                    '[class*="colour-swatch"] button',
                    'img[alt*="color"]',
                    'img[title*="color"]'
                ];
                
                for (const selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    for (const element of elements) {
                        const texts = [
                            element.textContent,
                            element.alt,
                            element.title,
                            element.getAttribute('data-color'),
                            element.getAttribute('aria-label')
                        ];
                        
                        for (const text of texts) {
                            if (text && normalize(text).includes(colorNorm)) {
                                element.scrollIntoView({block: 'center'});
                                element.click();
                                return true;
                            }
                        }
                    }
                }
                return false;
            }
        """, color)
    
    async def _click_color_button(self, page, color):
        """Click color button"""
        return await page.evaluate("""
            (color) => {
                const normalize = (text) => text ? text.toLowerCase().trim() : '';
                const colorNorm = normalize(color);
                
                const buttons = document.querySelectorAll('button, [role="button"]');
                for (const btn of buttons) {
                    if (normalize(btn.textContent).includes(colorNorm) || 
                        normalize(btn.getAttribute('aria-label')).includes(colorNorm)) {
                        btn.scrollIntoView({block: 'center'});
                        btn.click();
                        return true;
                    }
                }
                return false;
            }
        """, color)
    
    async def _select_color_dropdown(self, page, color):
        """Select from color dropdown"""
        return await page.evaluate("""
            (color) => {
                const normalize = (text) => text ? text.toLowerCase().trim() : '';
                const colorNorm = normalize(color);
                
                const selects = document.querySelectorAll('select');
                for (const select of selects) {
                    for (const option of select.options) {
                        if (normalize(option.text).includes(colorNorm)) {
                            select.value = option.value;
                            select.dispatchEvent(new Event('change', {bubbles: true}));
                            return true;
                        }
                    }
                }
                return false;
            }
        """, color)
    
    async def add_to_cart(self, page):
        """Add item to cart with loading state handling"""
        await page.wait_for_load_state('domcontentloaded')
        
        try:
            await page.wait_for_function("""
                () => {
                    const skeletons = document.querySelectorAll('[data-component*="Skeleton"]');
                    return skeletons.length === 0;
                }
            """, timeout=5000)
        except:
            pass
        
        await asyncio.sleep(1)
        
        clicked = await page.evaluate("""
            () => {
                const strategies = [
                    () => {
                        const selectors = [
                            'button[data-testid*="addToBag"]',
                            'button[data-testid*="add-to-bag"]',
                            '[data-testid*="addToBag"] button',
                            'button[name="add"]'
                        ];
                        for (const selector of selectors) {
                            const btn = document.querySelector(selector);
                            if (btn && !btn.disabled) {
                                btn.scrollIntoView({block: 'center'});
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    },
                    
                    () => {
                        const buttons = document.querySelectorAll('button, [role="button"]');
                        for (const btn of buttons) {
                            const text = btn.textContent.toLowerCase();
                            if ((text.includes('add to cart') || text.includes('add to bag') || 
                                 text.includes('add to basket')) && !btn.disabled) {
                                btn.scrollIntoView({block: 'center'});
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }
                ];
                
                for (const strategy of strategies) {
                    if (strategy()) return true;
                }
                return false;
            }
        """)
        
        if clicked:
            logger.info("Added to cart successfully")
            await asyncio.sleep(2)
        else:
            logger.error("Add to cart button not found or not clickable")
        
        return clicked