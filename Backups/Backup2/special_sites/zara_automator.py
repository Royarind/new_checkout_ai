#!/usr/bin/env python3

import asyncio
import logging
from typing import Dict, Any
from playwright.async_api import Page

logger = logging.getLogger(__name__)

class ZaraAutomator:
    """Specialized automation for Zara website"""
    
    def __init__(self, page: Page):
        self.page = page
    
    async def select_color(self, color_value: str) -> Dict[str, Any]:
        """Zara-specific color selection"""
        try:
            result = await self.page.evaluate("""
                (colorValue) => {
                    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                    const normalizedColor = normalize(colorValue);
                    
                    // Debug: Log available color elements
                    const colorItems = document.querySelectorAll('.product-detail-color-item, [class*="color"]');
                    console.log('Found color items:', colorItems.length);
                    
                    // Strategy 1: Find by screen reader text and click parent item
                    for (const item of colorItems) {
                        const screenReaderText = item.querySelector('.screen-reader-text');
                        if (screenReaderText) {
                            const itemColor = normalize(screenReaderText.textContent);
                            console.log('Color item text:', screenReaderText.textContent, 'normalized:', itemColor);
                            if (itemColor === normalizedColor) {
                                // Try clicking the parent item first
                                if (typeof item.click === 'function') {
                                    item.click();
                                    return { success: true, method: 'parent_item_click', clicked: screenReaderText.textContent };
                                }
                                // Fallback to button within item
                                const colorButton = item.querySelector('.product-detail-color-item__color-button, button, [role="button"]');
                                if (colorButton && typeof colorButton.click === 'function') {
                                    colorButton.click();
                                    return { success: true, method: 'button_click', clicked: screenReaderText.textContent };
                                }
                            }
                        }
                    }
                    
                    // Strategy 2: Find by aria-label or title
                    const allButtons = document.querySelectorAll('button, [role="button"], [class*="color"]');
                    console.log('Found buttons:', allButtons.length);
                    for (const button of allButtons) {
                        const texts = [
                            button.getAttribute('aria-label'),
                            button.getAttribute('title'),
                            button.textContent
                        ];
                        for (const text of texts) {
                            if (text && normalize(text) === normalizedColor) {
                                console.log('Matched button text:', text);
                                if (typeof button.click === 'function') {
                                    button.click();
                                    return { success: true, method: 'aria_label_title', clicked: text };
                                }
                            }
                        }
                    }
                    
                    // Strategy 3: Fallback - click any element containing the color text
                    const allElements = document.querySelectorAll('*');
                    console.log('Fallback: searching all elements for color text');
                    for (const element of allElements) {
                        if (element.textContent && normalize(element.textContent).includes(normalizedColor)) {
                            console.log('Found element with color text:', element.textContent, element.tagName);
                            if (typeof element.click === 'function') {
                                element.click();
                                return { success: true, method: 'fallback_text_match', clicked: element.textContent };
                            }
                        }
                    }
                    
                    return { success: false, reason: 'Color button not found with any strategy', searched: normalizedColor };
                }
            """, color_value)
            
            if result['success']:
                await asyncio.sleep(2.0)  # Longer wait for DOM update
                # Validate selection
                validated = await self.validate_color_selection(color_value)
                return {
                    'success': True,  # Accept click success for now
                    'content': f"Zara color {color_value} clicked ({result.get('method')}) - validation: {'passed' if validated else 'failed'}",
                    'action': 'click',
                    'debug': result
                }
            
            return {
                'success': False,
                'content': f"Failed to find Zara color button for {color_value}",
                'error': result.get('reason', 'Unknown error')
            }
            
        except Exception as e:
            return {
                'success': False,
                'content': f"Zara color selection error: {str(e)}",
                'error': str(e)
            }
    
    async def validate_color_selection(self, color_value: str) -> bool:
        """Validate Zara color selection by checking selected states"""
        try:
            return await self.page.evaluate("""
                (colorValue) => {
                    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                    const normalizedColor = normalize(colorValue);
                    
                    // Check multiple selection indicators
                    const selectors = [
                        '.product-detail-color-item[aria-current="true"] .screen-reader-text',
                        '.product-detail-color-item__color-button--is-selected .screen-reader-text',
                        '[class*="selected"] .screen-reader-text',
                        '[aria-selected="true"]',
                        '[class*="active"]'
                    ];
                    
                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const element of elements) {
                            const texts = [
                                element.textContent,
                                element.getAttribute('aria-label'),
                                element.getAttribute('title')
                            ];
                            for (const text of texts) {
                                if (text && normalize(text) === normalizedColor) {
                                    return true;
                                }
                            }
                        }
                    }
                    return false;
                }
            """, color_value)
        except:
            return False
    
    async def add_to_cart(self) -> Dict[str, Any]:
        """Zara-specific add to cart - triggers size selector"""
        try:
            result = await self.page.evaluate("""
                () => {
                    // Look for various add button patterns
                    const selectors = [
                        'button[name="add"]',
                        'button[class*="add"]',
                        '[class*="add-to-cart"]',
                        'button',
                        '[role="button"]'
                    ];
                    
                    console.log('Searching for ADD buttons...');
                    
                    for (const selector of selectors) {
                        const buttons = document.querySelectorAll(selector);
                        console.log(`Found ${buttons.length} elements with selector: ${selector}`);
                        
                        for (const button of buttons) {
                            const texts = [
                                button.textContent?.toLowerCase() || '',
                                button.getAttribute('aria-label')?.toLowerCase() || '',
                                button.getAttribute('title')?.toLowerCase() || ''
                            ];
                            
                            for (const text of texts) {
                                // More specific matching - exclude wishlist
                                if (text && (text.includes('add') || text.includes('añadir')) && 
                                    text.includes('cart') && !text.includes('wishlist')) {
                                    console.log('Found ADD TO CART button:', text);
                                    if (typeof button.click === 'function') {
                                        button.click();
                                        return { success: true, method: 'add_to_cart', text: text };
                                    }
                                }
                            }
                        }
                    }
                    
                    // Strategy 3: Look for common ADD button patterns
                    const allButtons = document.querySelectorAll('button');
                    console.log(`Total buttons found: ${allButtons.length}`);
                    
                    for (const button of allButtons) {
                        const buttonText = button.textContent?.toLowerCase().trim() || '';
                        const ariaLabel = button.getAttribute('aria-label')?.toLowerCase() || '';
                        
                        console.log('Button text:', buttonText, 'aria-label:', ariaLabel);
                        
                        // Look for various ADD patterns
                        const addPatterns = [
                            'add to bag',
                            'add to cart', 
                            'añadir',
                            'agregar',
                            'comprar',
                            'buy now'
                        ];
                        
                        for (const pattern of addPatterns) {
                            if (buttonText.includes(pattern) || ariaLabel.includes(pattern)) {
                                console.log('Found ADD button with pattern:', pattern, 'text:', buttonText);
                                if (typeof button.click === 'function') {
                                    button.click();
                                    return { success: true, method: 'pattern_match', text: buttonText || ariaLabel };
                                }
                            }
                        }
                    }
                    
                    return { success: false, reason: 'Add button not found after extensive search' };
                }
            """)
            
            if result['success']:
                return {
                    'success': True,
                    'content': f"Zara ADD button clicked ({result.get('method')}: {result.get('text')}) - size selector should appear",
                    'action': 'click'
                }
            
            return {
                'success': False,
                'content': "Failed to find Zara ADD button",
                'error': result.get('reason', 'Unknown error')
            }
            
        except Exception as e:
            return {
                'success': False,
                'content': f"Zara add to cart error: {str(e)}",
                'error': str(e)
            }
    
    async def select_size_after_add(self, size_value: str) -> Dict[str, Any]:
        """Zara-specific size selection after ADD button"""
        try:
            # Wait for size selector to appear
            await asyncio.sleep(2.0)
            
            result = await self.page.evaluate("""
                (sizeValue) => {
                    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                    const normalizedSize = normalize(sizeValue);
                    
                    // Look for size options in modal/popup
                    const sizeElements = document.querySelectorAll('[class*="size"], [data-size], button, a, [role="button"]');
                    for (const element of sizeElements) {
                        const texts = [
                            element.textContent,
                            element.getAttribute('data-size'),
                            element.getAttribute('aria-label'),
                            element.getAttribute('title')
                        ];
                        
                        for (const text of texts) {
                            if (text && normalize(text) === normalizedSize) {
                                if (typeof element.click === 'function') {
                                    element.click();
                                    return { success: true, method: 'zara_size_after_add' };
                                }
                            }
                        }
                    }
                    return { success: false, reason: 'Size option not found after ADD' };
                }
            """, size_value)
            
            if result['success']:
                return {
                    'success': True,
                    'content': f"Zara size {size_value} selected after ADD",
                    'action': 'click'
                }
            
            return {
                'success': False,
                'content': f"Failed to find Zara size {size_value} after ADD",
                'error': result.get('reason', 'Unknown error')
            }
            
        except Exception as e:
            return {
                'success': False,
                'content': f"Zara size after ADD error: {str(e)}",
                'error': str(e)
            }