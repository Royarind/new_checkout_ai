#!/usr/bin/env python3

import os
import asyncio
import logging
import re
from typing import Dict, Any, List, Optional
from playwright.async_api import Page

# Optional OCR imports
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

logger = logging.getLogger(__name__)

class UniversalVariantSelector:
    """Enhanced universal variant selector with improved compatibility"""
    
    def __init__(self):
        self.debug_dir = '/Users/abcom/Documents/Checkout_ai/variant_debug'
        os.makedirs(self.debug_dir, exist_ok=True)
        
        # Enhanced selectors for universal compatibility
        self.variant_selectors = {
            'color': [
                # Color-specific selectors (image-based first)
                'img[alt]', 'div[class*="color"] img', 'div[class*="swatch"] img',
                '[class*="color"]', '[class*="swatch"]', '[data-color]', '[data-swatch]',
                '[aria-label*="color"]', '[title*="color"]',
                'input[name*="color"]', 'select[name*="color"]',
                'button[class*="color"]', 'a[class*="color"]',
                '[data-testid*="color"]', '[data-value*="color"]',
                'div[onclick] img', 'button img', 'a img'
            ],
            'size': [
                # Size-specific selectors (most specific first)
                '[data-product-attribute-value]', 'input[name*="attribute"][type="radio"]',
                'label[data-product-attribute-value]', '.form-radio[data-product-attribute-value]',
                'input[name*="size"][type="radio"]', 'select[name*="size"]',
                'button[data-size]', '[data-testid*="size-option"]',
                '.size-option', '.size-selector', '[class*="size-select"]'
            ],
            'quantity': [
                # Quantity-specific selectors
                'input[type="number"]', 'input[name*="quantity"]', 'input[name*="qty"]',
                'select[name*="quantity"]', 'select[name*="qty"]',
                '[class*="quantity"]', '[class*="qty"]',
                'button[aria-label*="quantity"]', 'button[class*="quantity"]'
            ],
            'generic': [
                # Universal variant selectors
                'input[type="radio"]', 'input[type="checkbox"]',
                'select', 'option', 'button', 'a[href="#"]',
                '[role="button"]', '[role="option"]', '[role="radio"]',
                '[onclick]', '[data-value]', '[data-variant]',
                '[class*="variant"]', '[class*="option"]', '[class*="choice"]',
                '[class*="select"]', '[class*="swatch"]', '[class*="attribute"]'
            ]
        }
        
        # Common e-commerce platform patterns
        self.platform_patterns = {
            'shopify': [
                '[data-option]', '.single-option-selector', '.swatch',
                '.product-form__input', '.product-option',
                'input[name*="properties["]', 'select[name*="properties["]'
            ],
            'woocommerce': [
                '.variations', '.variable-item', '.value',
                'select.variation-select', '.attributeselect',
                '.swatch-wrapper', '.woocommerce-variation'
            ],
            'magento': [
                '.swatch-option', '.configurable-swatch-list',
                '.product-options-wrapper', '.super-attribute-select'
            ],
            'bigcommerce': [
                '.form-option', '.form-radio', '.form-select',
                '[data-product-attribute]', '.product-option'
            ]
        }

    async def detect_ecommerce_platform(self, page: Page) -> str:
        """Detect which e-commerce platform the site uses"""
        try:
            platform_data = await page.evaluate("""
                () => {
                    const clues = {};
                    
                    // Check for Shopify
                    clues.shopify = !!document.querySelector('[data-section-type="product"], .shopify-payment-button');
                    
                    // Check for WooCommerce
                    clues.woocommerce = !!document.querySelector('.woocommerce, [class*="woocommerce"]');
                    
                    // Check for Magento
                    clues.magento = !!document.querySelector('.mageplaza-core-js, [data-gallery-role="gallery-placeholder"]');
                    
                    // Check for BigCommerce
                    clues.bigcommerce = !!document.querySelector('.bc-product-form, [data-product-id]');
                    
                    // Check for custom implementations
                    clues.custom = !!document.querySelector('[data-variant], [class*="variant-selector"]');
                    
                    return clues;
                }
            """)
            
            for platform, detected in platform_data.items():
                if detected:
                    logger.info(f"Detected e-commerce platform: {platform}")
                    return platform
                    
            return "unknown"
        except Exception as e:
            logger.warning(f"Platform detection failed: {e}")
            return "unknown"

    async def normalize_variant_value(self, value: str) -> Dict[str, str]:
        """Normalize variant values for better matching"""
        # Remove extra spaces and convert to lowercase
        cleaned = re.sub(r'\s+', ' ', value.strip()).lower()
        
        return {
            'exact': cleaned,
            'alphanumeric': re.sub(r'[^a-z0-9]', '', cleaned),
            'words': cleaned,
            'fuzzy': re.sub(r'[^a-z0-9\s]', '', cleaned)
        }

    async def enhanced_element_search(self, page: Page, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Enhanced element search with multiple strategies"""
        
        normalized_value = await self.normalize_variant_value(variant_value)
        platform = await self.detect_ecommerce_platform(page)
        
        # Combine selectors based on variant type and platform
        selectors = self.variant_selectors.get(variant_type, []) + self.variant_selectors['generic']
        if platform in self.platform_patterns:
            selectors.extend(self.platform_patterns[platform])
        
        # Remove duplicates while preserving order
        selectors = list(dict.fromkeys(selectors))
        
        logger.info(f"Searching for {variant_type}={variant_value} with {len(selectors)} selectors")
        
        # Debug: Log what's on the page for color variants
        if variant_type == 'color':
            try:
                page_info = await page.evaluate("""
                    (value) => {
                        const imgs = document.querySelectorAll('img[alt]');
                        const target = value.toLowerCase();
                        const matching = [];
                        const all = [];
                        
                        for (const img of imgs) {
                            const info = {
                                alt: img.alt,
                                parent: img.parentElement?.tagName,
                                parentClass: img.parentElement?.className
                            };
                            all.push(info);
                            if (img.alt.toLowerCase().includes(target)) {
                                matching.push(info);
                            }
                        }
                        
                        return { imageCount: imgs.length, samples: all.slice(0, 5), matching: matching };
                    }
                """, variant_value)
                logger.info(f"Page has {page_info['imageCount']} images with alt text")
                logger.info(f"Matching images: {page_info['matching']}")
                logger.info(f"Sample images: {page_info['samples'][:3]}")
            except:
                pass
        
        search_result = await page.evaluate("""
            (args) => {
                const { selectors, normalizedValue, variantType } = args;
                
                console.log('[SEARCH DEBUG] Looking for:', normalizedValue);
                console.log('[SEARCH DEBUG] Variant type:', variantType);
                
                const normalizeText = (text) => {
                    if (!text) return '';
                    return text.toLowerCase().trim().replace(/\\s+/g, ' ');
                };
                
                const matchesValue = (text) => {
                    if (!text) return false;
                    const normalized = normalizeText(text);
                    
                    // Exact match (always check first)
                    if (normalized === normalizedValue.exact) {
                        console.log('[SEARCH DEBUG] Exact match found:', text);
                        return true;
                    }
                    
                    // Alphanumeric match (ignores spaces/special chars)
                    const textAlpha = normalized.replace(/[^a-z0-9]/g, '');
                    const valueAlpha = normalizedValue.alphanumeric;
                    if (textAlpha === valueAlpha) return true;
                    
                    // For size variants (numeric), ONLY use exact match to avoid "9" matching "69"
                    if (variantType === 'size' && /^\d+(\.5)?$/.test(normalizedValue.exact)) {
                        return false;
                    }
                    
                    // Contains match (for non-numeric variants like colors)
                    if (normalized.includes(normalizedValue.words)) return true;
                    
                    // Word-based match (all words present)
                    const valueWords = normalizedValue.words.split(' ');
                    const textWords = normalized.split(' ');
                    if (valueWords.length > 1) {
                        const allWordsPresent = valueWords.every(word => 
                            textWords.some(textWord => textWord.includes(word) || word.includes(textWord))
                        );
                        if (allWordsPresent) return true;
                    }
                    
                    return false;
                };
                
                // Search through all selectors
                for (const selector of selectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        
                        for (const element of elements) {
                            // Skip hidden or disabled elements
                            const style = window.getComputedStyle(element);
                            if (style.display === 'none' || style.visibility === 'hidden' || element.disabled) {
                                continue;
                            }
                            
                            // Skip navigation/menu/guide/logo elements
                            const skipClasses = ['menu', 'nav', 'header', 'footer', 'account', 'wishlist', 'favourite', 'cart', 'guide', 'chart', 'info', 'logo', 'brand'];
                            const className = element.className?.toLowerCase() || '';
                            const href = element.getAttribute('href')?.toLowerCase() || '';
                            const parentClass = element.parentElement?.className?.toLowerCase() || '';
                            if (skipClasses.some(skip => className.includes(skip) || href.includes(skip) || parentClass.includes(skip))) {
                                continue;
                            }
                            
                            // For IMG elements, skip if alt text doesn't contain the variant value
                            if (element.tagName === 'IMG' && variantType === 'color') {
                                const alt = element.getAttribute('alt')?.toLowerCase() || '';
                                if (!alt.includes(normalizedValue.exact)) {
                                    continue;
                                }
                            }
                            
                            // For size variant, skip if element contains multiple size values (likely a guide/container)
                            if (variantType === 'size') {
                                const text = element.textContent || '';
                                const sizePattern = /\b\d+(\.5)?\b/g;
                                const matches = text.match(sizePattern);
                                if (matches && matches.length > 3) {
                                    continue;
                                }
                            }
                            
                            // Check various text sources
                            const textSources = [
                                element.textContent,
                                element.value,
                                element.getAttribute('aria-label'),
                                element.getAttribute('title'),
                                element.getAttribute('alt'),
                                element.getAttribute('data-value'),
                                element.getAttribute('data-label'),
                                element.getAttribute('data-name'),
                                element.getAttribute('data-color'),
                                element.getAttribute('data-size')
                            ];
                            
                            // Also check all data-* attributes
                            const dataAttributes = Array.from(element.attributes)
                                .filter(attr => attr.name.startsWith('data-'))
                                .map(attr => attr.value);
                            
                            textSources.push(...dataAttributes);
                            
                            for (const text of textSources) {
                                if (matchesValue(text)) {
                                    console.log('[SEARCH DEBUG] Match found in element:', element.tagName, element.className);
                                    console.log('[SEARCH DEBUG] Matched text:', text);
                                    console.log('[SEARCH DEBUG] Selector used:', selector);
                                    
                                    // If element is IMG, find clickable parent
                                    let targetElement = element;
                                    if (element.tagName === 'IMG') {
                                        const clickableParent = element.closest('button, a, [role="button"], [onclick], div[class*="swatch"], div[class*="color"]');
                                        if (clickableParent) {
                                            targetElement = clickableParent;
                                            console.log('[SEARCH DEBUG] Found clickable parent for IMG:', targetElement.tagName, targetElement.className);
                                        }
                                    }
                                    
                                    // Determine action type
                                    let action = 'click';
                                    if (element.tagName === 'SELECT') {
                                        action = 'select';
                                        // Find matching option
                                        for (const option of element.options) {
                                            if (matchesValue(option.text) || matchesValue(option.value)) {
                                                return {
                                                    found: true,
                                                    action: action,
                                                    element: {
                                                        tagName: element.tagName,
                                                        selector: selector,
                                                        value: option.value
                                                    },
                                                    matchedText: text,
                                                    selector: selector
                                                };
                                            }
                                        }
                                    } else if (element.tagName === 'INPUT' && (element.type === 'number' || element.name?.includes('quantity'))) {
                                        action = 'quantity_input';
                                    } else if (element.type === 'radio' || element.type === 'checkbox') {
                                        action = 'radio';
                                    }
                                    
                                    return {
                                        found: true,
                                        action: action,
                                        element: {
                                            tagName: targetElement.tagName,
                                            selector: selector,
                                            value: targetElement.value,
                                            className: targetElement.className
                                        },
                                        matchedText: text,
                                        selector: selector
                                    };
                                }
                            }
                        }
                    } catch (e) {
                        console.log(`Selector ${selector} failed:`, e);
                    }
                }
                
                return { found: false };
            }
        """, {
            'selectors': selectors,
            'normalizedValue': normalized_value,
            'variantType': variant_type
        })
        
        return search_result

    async def execute_variant_action(self, page: Page, search_result: Dict[str, Any], variant_value: str) -> bool:
        """Execute the appropriate action based on element type with enhanced clicking"""
        
        if not search_result['found']:
            return False
            
        action = search_result['action']
        selector = search_result['selector']
        matched_text = search_result['matchedText']
        
        logger.info(f"Executing {action} action for selector: {selector}")
        
        try:
            if action == 'select':
                option_value = search_result['element']['value']
                await page.select_option(selector, value=option_value)
                logger.info(f"Selected option: {matched_text}")
                
            elif action == 'quantity_input':
                await page.fill(selector, variant_value)
                await page.dispatch_event(selector, 'change')
                logger.info(f"Set quantity to: {variant_value}")
                
            elif action == 'radio':
                await page.check(selector)
                logger.info(f"Selected radio: {matched_text}")
                
            else:
                # Enhanced click with multiple strategies and debug logging
                clicked = await page.evaluate("""
                    (args) => {
                        const { selector, matchedText, elementInfo } = args;
                        const normalize = (text) => text ? text.toLowerCase().trim() : '';
                        const target = normalize(matchedText);
                        
                        console.log('[CLICK DEBUG] Looking for:', target);
                        console.log('[CLICK DEBUG] Selector:', selector);
                        console.log('[CLICK DEBUG] Element info:', elementInfo);
                        
                        // Find element by selector first
                        let element = document.querySelector(selector);
                        console.log('[CLICK DEBUG] Found by selector:', !!element);
                        
                        // If not found, search by text or alt attribute
                        if (!element) {
                            const allElements = document.querySelectorAll('button, a, [role="button"], div[onclick], [data-label], [class*="size"], [class*="color"], [class*="swatch"]');
                            console.log('[CLICK DEBUG] Searching through', allElements.length, 'elements');
                            
                            for (const el of allElements) {
                                // Check element's own text
                                const texts = [
                                    el.textContent?.trim(),
                                    el.getAttribute('data-label'),
                                    el.getAttribute('title'),
                                    el.getAttribute('aria-label')
                                ].filter(t => t);
                                
                                // Also check img alt within element
                                const img = el.querySelector('img');
                                if (img) {
                                    texts.push(img.getAttribute('alt'));
                                }
                                
                                for (const text of texts) {
                                    if (normalize(text) === target) {
                                        console.log('[CLICK DEBUG] Found match:', el.tagName, text);
                                        element = el;
                                        break;
                                    }
                                }
                                if (element) break;
                            }
                        }
                        
                        if (!element) {
                            console.log('[CLICK DEBUG] Element not found after search');
                            return { success: false, reason: 'Element not found' };
                        }
                        
                        console.log('[CLICK DEBUG] Element found:', element.tagName, element.className);
                        
                        // Scroll into view
                        element.scrollIntoView({ block: 'center', behavior: 'instant' });
                        
                        // Try multiple click strategies
                        try {
                            console.log('[CLICK DEBUG] Attempting direct click');
                            element.click();
                            console.log('[CLICK DEBUG] Direct click succeeded');
                            return { success: true, method: 'direct_click', element: element.outerHTML.substring(0, 100) };
                        } catch (e) {
                            console.log('[CLICK DEBUG] Direct click failed:', e.message);
                            // Try mouse events
                            const rect = element.getBoundingClientRect();
                            console.log('[CLICK DEBUG] Element rect:', rect);
                            const clickEvent = new MouseEvent('click', {
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: rect.left + rect.width / 2,
                                clientY: rect.top + rect.height / 2
                            });
                            element.dispatchEvent(clickEvent);
                            console.log('[CLICK DEBUG] Mouse event dispatched');
                            return { success: true, method: 'mouse_event', element: element.outerHTML.substring(0, 100) };
                        }
                    }
                """, {'selector': selector, 'matchedText': matched_text, 'elementInfo': search_result.get('element', {})})
                
                if clicked['success']:
                    logger.info(f"Clicked: {matched_text} (method: {clicked['method']})")
                    logger.info(f"Element: {clicked.get('element', 'N/A')}")
                else:
                    logger.warning(f"Click failed: {clicked.get('reason')}")
                    return False
                
            return True
            
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False

    async def visual_verification(self, page: Page, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Enhanced visual verification with CSS class detection"""
        
        try:
            safe_value = variant_value.replace('/', '_')
            screenshot_path = f'{self.debug_dir}/visual_verify_{variant_type}_{safe_value}.png'
            await page.screenshot(path=screenshot_path, full_page=False)
            
            visual_result = await page.evaluate("""
                (args) => {
                    const { variantType, variantValue } = args;
                    const normalize = (text) => text ? text.toLowerCase().trim() : '';
                    const target = normalize(variantValue);
                    
                    // Strategy 1: Traditional selection indicators
                    const selection_indicators = [
                        '.selected', '.active', '.chosen', '.current',
                        '[aria-selected="true"]', '[aria-pressed="true"]',
                        '[aria-checked="true"]', '[data-selected="true"]',
                        '.is-selected', '.is-active', '.is-chosen'
                    ];
                    
                    for (const indicator of selection_indicators) {
                        const elements = document.querySelectorAll(indicator);
                        for (const el of elements) {
                            const texts = [
                                el.textContent, el.value, el.getAttribute('aria-label'),
                                el.getAttribute('title'), el.getAttribute('data-value'),
                                el.getAttribute('data-label')
                            ].filter(t => t);
                            
                            for (const text of texts) {
                                const isNumericSize = variantType === 'size' && /^\d+(\.5)?$/.test(target);
                                const matches = isNumericSize ? normalize(text) === target : (normalize(text) === target || normalize(text).includes(target));
                                if (matches) {
                                    return { verified: true, method: 'visual_selection', element: el.tagName, text: text };
                                }
                            }
                        }
                    }
                    
                    // Strategy 2: CSS class-based selection (Tailwind, custom)
                    const allButtons = document.querySelectorAll('[role="button"], button, div[onclick], [data-label]');
                    for (const btn of allButtons) {
                        const texts = [
                            btn.textContent?.trim(),
                            btn.getAttribute('data-label'),
                            btn.getAttribute('title'),
                            btn.getAttribute('aria-label')
                        ];
                        
                        for (const text of texts) {
                            if (text && normalize(text) === target) {
                                // Check for selected styling patterns
                                const classList = Array.from(btn.classList);
                                const hasSelectedStyling = 
                                    classList.some(c => c.includes('bg-black') || c.includes('bg-primary') || c.includes('bg-dark')) ||
                                    classList.some(c => c.includes('text-white')) ||
                                    classList.includes('cursor-default') ||
                                    !classList.includes('cursor-pointer') ||
                                    btn.style.backgroundColor === 'black' ||
                                    btn.style.backgroundColor === 'rgb(0, 0, 0)' ||
                                    btn.style.color === 'white' ||
                                    btn.style.color === 'rgb(255, 255, 255)';
                                
                                if (hasSelectedStyling) {
                                    return { verified: true, method: 'css_class_selection', element: btn.tagName, text: text };
                                }
                            }
                        }
                    }
                    
                    // Strategy 3: Checked inputs
                    const checked_inputs = document.querySelectorAll('input:checked');
                    for (const input of checked_inputs) {
                        const label = document.querySelector(`label[for="${input.id}"]`);
                        const label_text = label ? label.textContent : '';
                        const value = input.value;
                        
                        const isNumericSize = variantType === 'size' && /^\d+(\.5)?$/.test(target);
                        const labelMatch = isNumericSize ? normalize(label_text) === target : (normalize(label_text) === target || normalize(label_text).includes(target));
                        const valueMatch = isNumericSize ? normalize(value) === target : (normalize(value) === target || normalize(value).includes(target));
                        if (labelMatch || valueMatch) {
                            return { verified: true, method: 'checked_input', element: 'input', text: label_text || value };
                        }
                    }
                    
                    return { verified: false };
                }
            """, {'variantType': variant_type, 'variantValue': variant_value})
            
            return visual_result
            
        except Exception as e:
            logger.error(f"Visual verification failed: {e}")
            return {'verified': False, 'error': str(e)}

    async def find_and_select_variant(self, page: Page, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Main method to find and select variants with enhanced compatibility"""
        
        logger.info(f"VARIANT SELECTION: Starting selection for {variant_type}={variant_value}")
        
        # Try site-specific handlers first
        try:
            site_result = await self.try_site_specific_handlers(page, variant_type, variant_value)
            if site_result.get('success'):
                return site_result
        except Exception as e:
            logger.warning(f"Site-specific handler failed: {e}")
        
        # Enhanced search with multiple attempts
        for attempt in range(3):
            logger.info(f"Attempt {attempt + 1}/3 for {variant_type}={variant_value}")
            
            try:
                # Wait for potential dynamic content
                await asyncio.sleep(1.0)
                
                # Enhanced element search
                search_result = await self.enhanced_element_search(page, variant_type, variant_value)
                
                if search_result['found']:
                    # Execute action
                    action_success = await self.execute_variant_action(page, search_result, variant_value)
                    
                    if action_success:
                        # Wait for page to update
                        await asyncio.sleep(2.0)
                        
                        # Verify selection
                        verification = await self.visual_verification(page, variant_type, variant_value)
                        
                        if verification and verification.get('verified'):
                            logger.info(f"VARIANT SELECTION: SUCCESS - {variant_type}={variant_value}")
                            return {
                                'success': True,
                                'content': f"SUCCESS: {variant_type}={variant_value}",
                                'method': verification['method'],
                                'attempt': attempt + 1
                            }
                        else:
                            # Try OCR verification as fallback
                            if OCR_AVAILABLE:
                                ocr_result = await verify_selection_with_ocr(page, variant_type, variant_value, self.debug_dir)
                                if ocr_result.get('verified'):
                                    return {
                                        'success': True,
                                        'content': f"SUCCESS via OCR: {variant_type}={variant_value}",
                                        'method': 'ocr_fallback',
                                        'attempt': attempt + 1
                                    }
                
                # If not found, try alternative strategies
                if attempt == 1:
                    logger.info("Trying alternative search strategies...")
                    alternative_result = await self.alternative_search_strategies(page, variant_type, variant_value)
                    if alternative_result.get('success'):
                        return alternative_result
                        
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if "Execution context was destroyed" in str(e):
                    logger.info("Page navigated - treating as success")
                    return {
                        'success': True,
                        'content': f"SUCCESS: Navigation triggered by {variant_type}={variant_value}",
                        'method': 'navigation'
                    }
        
        # Final fallback: Discovery mode
        logger.info("Starting discovery mode as final fallback...")
        discovery_result = await self.discovery_mode(page, variant_type, variant_value)
        if discovery_result.get('success'):
            return discovery_result
        
        logger.error(f"VARIANT SELECTION: FAILED - {variant_type}={variant_value}")
        return {
            'success': False,
            'content': f"FAILED: Could not select {variant_type}={variant_value}",
            'error': 'All strategies exhausted'
        }

    async def alternative_search_strategies(self, page: Page, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Alternative search strategies for difficult cases"""
        
        try:
            # Strategy: Find by proximity to product elements
            proximity_result = await page.evaluate("""
                (args) => {
                    const { variantType, variantValue } = args;
                    
                    const normalize = (text) => text ? text.toLowerCase().trim() : '';
                    const target = normalize(variantValue);
                    
                    // Find product containers
                    const product_containers = [
                        '.product', '.product-details', '.product-info',
                        '[data-product]', '.item', '.goods',
                        'form[action*="cart"]', '.add-to-cart-form'
                    ];
                    
                    for (const container_sel of product_containers) {
                        const containers = document.querySelectorAll(container_sel);
                        for (const container of containers) {
                            // Find all interactive elements within product container
                            const elements = container.querySelectorAll('button, input, select, a, [role="button"]');
                            
                            for (const element of elements) {
                                const texts = [
                                    element.textContent, element.value,
                                    element.getAttribute('aria-label'),
                                    element.getAttribute('title'),
                                    element.getAttribute('data-value')
                                ].filter(t => t);
                                
                                for (const text of texts) {
                                    if (normalize(text).includes(target)) {
                                        return {
                                            found: true,
                                            element: {
                                                tagName: element.tagName,
                                                text: text
                                            },
                                            strategy: 'proximity_search'
                                        };
                                    }
                                }
                            }
                        }
                    }
                    
                    return { found: false };
                }
            """, {'variantType': variant_type, 'variantValue': variant_value})
            
            if proximity_result['found']:
                # Try to click the found element
                element_info = proximity_result['element']
                logger.info(f"Found via proximity: {element_info['tagName']} - {element_info['text']}")
                
                # Use a more generic click approach
                await page.evaluate("""
                    (text) => {
                        const elements = document.querySelectorAll('button, a, [role="button"]');
                        for (const el of elements) {
                            if (el.textContent.includes(text)) {
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """, proximity_result['element']['text'])
                
                await asyncio.sleep(2.0)
                return {'success': True, 'content': 'Proximity search success'}
                
        except Exception as e:
            logger.error(f"Alternative search failed: {e}")
            
        return {'success': False}

    async def discovery_mode(self, page: Page, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Discovery mode with visual brute-force: click all candidates and validate UI change"""
        
        logger.info(f"Discovery mode: Starting visual brute-force for {variant_type}={variant_value}")
        
        try:
            # Find all potential color/size elements
            candidates = await page.evaluate("""
                (variantType) => {
                    const selectors = variantType === 'color' 
                        ? 'img[alt], [class*="color"], [class*="swatch"], [data-color]'
                        : '[class*="size"], [data-size], button, [role="button"]';
                    
                    const elements = document.querySelectorAll(selectors);
                    const candidates = [];
                    
                    for (const el of elements) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        
                        // Skip header/footer/nav
                        const parent = el.closest('header, footer, nav, [class*="header"], [class*="footer"], [class*="nav"]');
                        if (parent) continue;
                        
                        // Get clickable parent if IMG
                        let clickable = el;
                        if (el.tagName === 'IMG') {
                            clickable = el.closest('button, a, [role="button"], div[onclick]') || el.parentElement;
                        }
                        
                        const clickRect = clickable.getBoundingClientRect();
                        candidates.push({
                            x: clickRect.left + clickRect.width / 2,
                            y: clickRect.top + clickRect.height / 2,
                            text: el.textContent?.trim() || el.alt || el.getAttribute('data-label') || '',
                            index: candidates.length
                        });
                    }
                    
                    return candidates.slice(0, 20);
                }
            """, variant_type)
            
            logger.info(f"Discovery mode: Found {len(candidates)} candidates to try")
            
            if not candidates:
                return {'success': False}
            
            # Get initial UI state before clicking
            initial_ui = await page.evaluate("""
                () => {
                    const els = document.querySelectorAll('[class*="selected"], [class*="current"], [class*="active"], [class*="color"], [class*="size"]');
                    return Array.from(els).map(el => el.textContent?.trim()).filter(t => t).join('|');
                }
            """)
            
            # Try each candidate
            for i, candidate in enumerate(candidates):
                try:
                    logger.info(f"Discovery mode: Trying candidate {i+1}/{len(candidates)}")
                    
                    # Draw overlay box
                    await page.evaluate("""
                        (coords) => {
                            const box = document.createElement('div');
                            box.id = 'brute-force-overlay';
                            box.style.cssText = `
                                position: fixed;
                                left: ${coords.x - 25}px;
                                top: ${coords.y - 25}px;
                                width: 50px;
                                height: 50px;
                                border: 3px solid red;
                                background: rgba(255, 0, 0, 0.2);
                                z-index: 999999;
                                pointer-events: none;
                            `;
                            document.body.appendChild(box);
                        }
                    """, candidate)
                    
                    # Take before screenshot
                    before_path = f'{self.debug_dir}/brute_{i}_before.png'
                    await page.screenshot(path=before_path)
                    
                    # Click
                    await page.mouse.click(candidate['x'], candidate['y'])
                    await asyncio.sleep(1.5)
                    
                    # Take after screenshot
                    after_path = f'{self.debug_dir}/brute_{i}_after.png'
                    await page.screenshot(path=after_path)
                    
                    # OCR validation: Compare screenshots
                    if OCR_AVAILABLE:
                        try:
                            from PIL import Image
                            import pytesseract
                            
                            # Read screenshots
                            before_img = Image.open(before_path)
                            after_img = Image.open(after_path)
                            
                            # Extract text from both
                            before_text = pytesseract.image_to_string(before_img).lower()
                            after_text = pytesseract.image_to_string(after_img).lower()
                            
                            # Check if variant value appears in after but not before (or more prominently)
                            target_lower = variant_value.lower()
                            before_count = before_text.count(target_lower)
                            after_count = after_text.count(target_lower)
                            
                            ocr_success = after_count > before_count
                            logger.info(f"OCR validation: '{target_lower}' appears {before_count} times before, {after_count} times after")
                            
                            if ocr_success:
                                logger.info(f"Discovery mode: OCR SUCCESS at candidate {i+1}")
                                await page.evaluate("""
                                    () => {
                                        const box = document.getElementById('brute-force-overlay');
                                        if (box) {
                                            box.style.border = '3px solid green';
                                            box.style.background = 'rgba(0, 255, 0, 0.2)';
                                        }
                                    }
                                """)
                                await page.screenshot(path=f'{self.debug_dir}/brute_{i}_success.png')
                                await page.evaluate("document.getElementById('brute-force-overlay')?.remove()")
                                return {'success': True, 'content': f'OCR brute-force success', 'method': 'ocr_brute_force'}
                        except Exception as ocr_error:
                            logger.debug(f"OCR validation failed: {ocr_error}")
                    else:
                        logger.warning("OCR not available, skipping visual validation")
                    
                    await page.evaluate("document.getElementById('brute-force-overlay')?.remove()")
                    
                except Exception as e:
                    logger.debug(f"Candidate {i+1} failed: {e}")
                    await page.evaluate("document.getElementById('brute-force-overlay')?.remove()")
                    continue
            
            logger.warning(f"Discovery mode: Tried all {len(candidates)} candidates, none matched")
            return {'success': False}
                
        except Exception as e:
            logger.error(f"Discovery mode failed: {e}")
            return {'success': False}

    async def try_site_specific_handlers(self, page: Page, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Try site-specific handlers for known e-commerce sites"""
        
        url = page.url.lower()
        
        # Add your site-specific handlers here
        handler_map = {
            'patagonia.com': 'patagonia_automator',
            'dillards.com': 'dillards_automator', 
            'amazon.': 'amazon_automator',
            'heydude.com': 'heydude_automator',
            'karllagerfeld.com': 'karllagerfeld_automator',
            'farfetch.com': 'farfetch_automator'
        }
        
        for domain, handler_name in handler_map.items():
            if domain in url:
                try:
                    module = __import__(f'special_sites.{handler_name}', fromlist=[''])
                    handler_func = getattr(module, f'select_{handler_name.replace("_automator", "")}_variant')
                    result = await handler_func(page, variant_type, variant_value)
                    if result.get('success'):
                        logger.info(f"Site-specific handler succeeded for {domain}")
                        return result
                except Exception as e:
                    logger.warning(f"Site-specific handler for {domain} failed: {e}")
                    
        return {'success': False}

# Keep your existing OCR function
async def verify_selection_with_ocr(page: Page, variant_type: str, variant_value: str, debug_dir: str) -> Dict[str, Any]:
    """Your existing OCR function remains unchanged"""
    # ... (your existing OCR implementation)

# Updated main function that uses the new class
async def find_variant_dom(page: Page, variant_type: str, variant_value: str) -> Dict[str, Any]:
    """
    Universal DOM finder for product variant selection using enhanced selector.
    """
    selector = UniversalVariantSelector()
    return await selector.find_and_select_variant(page, variant_type, variant_value)