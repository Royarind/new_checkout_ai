#!/usr/bin/env python3

import os
import asyncio
import logging
from typing import Dict, Any
from playwright.async_api import Page

# Optional OCR imports - gracefully handle if not installed
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.getLogger(__name__).warning("pytesseract not installed. OCR verification disabled. Install with: pip install pytesseract")

logger = logging.getLogger(__name__)

async def verify_selection_with_ocr(page: Page, variant_type: str, variant_value: str, debug_dir: str) -> Dict[str, Any]:
    """
    Verify variant selection using OCR by taking a screenshot and extracting text.
    This works for SPAs and sites where selection state isn't reflected in DOM.
    
    Args:
        page: Playwright page object
        variant_type: Type of variant (e.g., 'color', 'size')
        variant_value: Expected value (e.g., 'Cool Brown', 'Medium')
        debug_dir: Directory to save debug files
        
    Returns:
        Dict with verification result: {verified: bool, matched_text: str, method: str}
    """
    if not OCR_AVAILABLE:
        logger.warning(f"VARIANT SELECTION: OCR verification skipped - pytesseract not installed")
        logger.warning(f"   Install with: pip install pytesseract")
        logger.warning(f"   Then install Tesseract: brew install tesseract (macOS)")
        return {
            'verified': False,
            'matched_text': None,
            'method': 'OCR unavailable - pytesseract not installed'
        }
    
    try:
        logger.info(f"VARIANT SELECTION: Trying OCR verification as fallback...")
        
        # Take screenshot of the page
        screenshot_path = f'{debug_dir}/screenshot_{variant_type}_{variant_value}.png'
        await page.screenshot(path=screenshot_path, full_page=True)
        logger.info(f"VARIANT SELECTION: Screenshot saved to {screenshot_path}")
        
        # Extract text using pytesseract
        image = Image.open(screenshot_path)
        extracted_text = pytesseract.image_to_string(image)
        
        # Save extracted text to debug file
        ocr_text_path = f'{debug_dir}/ocr_{variant_type}_{variant_value}.txt'
        with open(ocr_text_path, 'w', encoding='utf-8') as f:
            f.write(extracted_text)
        logger.info(f"VARIANT SELECTION: OCR text saved to {ocr_text_path}")
        
        # Normalize text for comparison
        def normalize_strict(text):
            """Remove all spaces and special characters"""
            return ''.join(c.lower() for c in text if c.isalnum())
        
        def normalize_fuzzy(text):
            """Keep spaces but remove special characters"""
            return ''.join(c.lower() if c.isalnum() or c.isspace() else ' ' for c in text).strip()
        
        normalized_value_strict = normalize_strict(variant_value)
        normalized_value_fuzzy = normalize_fuzzy(variant_value)
        normalized_extracted_strict = normalize_strict(extracted_text)
        normalized_extracted_fuzzy = normalize_fuzzy(extracted_text)
        
        # Try different matching strategies
        verified = False
        matched_text = None
        method = None
        
        # Strategy 1: Strict match (no spaces)
        if normalized_value_strict in normalized_extracted_strict:
            verified = True
            method = "OCR strict match"
            # Find the matching portion in original text
            for line in extracted_text.split('\n'):
                if normalize_strict(line) and normalized_value_strict in normalize_strict(line):
                    matched_text = line.strip()
                    break
        
        # Strategy 2: Fuzzy match (with spaces)
        elif normalized_value_fuzzy in normalized_extracted_fuzzy:
            verified = True
            method = "OCR fuzzy match"
            for line in extracted_text.split('\n'):
                if normalize_fuzzy(line) and normalized_value_fuzzy in normalize_fuzzy(line):
                    matched_text = line.strip()
                    break
        
        # Strategy 3: Word-by-word match
        else:
            words = normalized_value_fuzzy.split()
            all_words_found = all(word in normalized_extracted_fuzzy for word in words if len(word) > 2)
            if all_words_found and len(words) > 0:
                verified = True
                method = "OCR word match"
                matched_text = variant_value
        
        if verified:
            logger.info(f"VARIANT SELECTION: VERIFICATION PASSED via OCR")
            logger.info(f"   Method: {method}")
            logger.info(f"   Matched Text: {matched_text or variant_value}")
            return {
                'verified': True,
                'matched_text': matched_text or variant_value,
                'method': method
            }
        else:
            logger.warning(f"VARIANT SELECTION: OCR verification failed - text not found in screenshot")
            logger.warning(f"   Expected: {variant_value}")
            logger.warning(f"   OCR extracted {len(extracted_text)} characters")
            return {
                'verified': False,
                'matched_text': None,
                'method': 'OCR failed'
            }
            
    except Exception as e:
        logger.error(f"VARIANT SELECTION: OCR verification error: {e}")
        return {
            'verified': False,
            'matched_text': None,
            'method': f'OCR error: {str(e)}'
        }

async def find_variant_dom(page: Page, variant_type: str, variant_value: str) -> Dict[str, Any]:
    """Universal DOM finder for product variant selection."""
    debug_dir = '/Users/abcom/Documents/Checkout_ai/variant_debug'
    os.makedirs(debug_dir, exist_ok=True)
    debug_file = f'{debug_dir}/dom_{variant_type}_{variant_value}.txt'
    
    # Log the start of selection
    logger.info(f"VARIANT SELECTION: SELECTING: {variant_type} = {variant_value}")
    
    # Try Patagonia-specific handler first
    if 'patagonia.com' in page.url:
        try:
            from special_sites.patagonia_handler import select_patagonia_variant
            result = await select_patagonia_variant(page, variant_type, variant_value)
            if result.get('success'):
                logger.info(f"Patagonia handler succeeded: {result.get('method')}")
                return {
                    'success': True,
                    'content': f"SUCCESS: {variant_type}={variant_value} (Patagonia handler)",
                    'action': 'click'
                }
        except Exception as e:
            logger.warning(f"Patagonia handler failed: {e}, falling back to universal")
    
    for attempt in range(3):
        try:
            # Wait for DOM to stabilize before each search
            if attempt > 0:
                logger.info(f"VARIANT SELECTION: Retry attempt {attempt + 1}/3: Extracting fresh DOM tree...")
                await asyncio.sleep(2.0)
            
            # CRITICAL: Extract FRESH DOM structure on EVERY attempt
            # This ensures we're searching the current page state, not stale data
            dom_content = await page.evaluate("""
                () => {
                    return document.body.outerHTML;
                }
            """)
            with open(debug_file, 'w') as f:
                f.write(f"Complete DOM for {variant_type}: {variant_value} (Attempt {attempt + 1})\\n" + "=" * 80 + "\\n" + dom_content)
            logger.info(f"Fresh DOM extracted and saved to {debug_file}")
            
            # PHASE 1: Overlay-based element search ...The overlays are made transparent to avoid interference
            result = await page.evaluate("""
                (val) => {
                    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                    const normalizedVal = normalize(val);
                    
                    const match = (text) => {
                        if (!text) return false;
                        const t = normalize(text);
                        
                        // Exact match
                        if (t === normalizedVal) return true;
                        
                        // Multi-word match: check if all words from search value exist in text
                        const searchWords = normalizedVal.split(/\s+/).filter(w => w.length > 0);
                        const textWords = t.split(/\s+/).filter(w => w.length > 0);
                        
                        if (searchWords.length >= 2) {
                            // First try exact phrase match
                            if (t.includes(normalizedVal)) {
                                return true;
                            }
                            
                            // Then try all words present match
                            const hasAllWords = searchWords.every(word => 
                                textWords.some(textWord => textWord === word || textWord.includes(word) || word.includes(textWord))
                            );
                            if (hasAllWords) return true;
                        }
                        
                        return false;
                    };
                    
                    // Clear existing overlays
                    document.querySelectorAll('.automation-overlay').forEach(el => el.remove());
                    
                    // Create overlay container
                    const overlayContainer = document.createElement('div');
                    overlayContainer.id = 'automation-overlays';
                    overlayContainer.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 999999;';
                    document.body.appendChild(overlayContainer);
                    
                    let elementIndex = 0;
                    const indexedElements = [];
                    
                    // Function to create overlay for element
                    const createOverlay = (element, index, color = '#ff0000') => {
                        const rect = element.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return null;
                        
                        const overlay = document.createElement('div');
                        overlay.className = 'automation-overlay';
                        overlay.setAttribute('data-element-index', index);
                        overlay.style.cssText = `
                            position: absolute;
                            left: ${rect.left}px;
                            top: ${rect.top}px;
                            width: ${rect.width}px;
                            height: ${rect.height}px;
                            border: 2px solid transparent;
                            background: transparent;
                            pointer-events: none;
                            font-family: monospace;
                            font-size: 12px;
                            font-weight: bold;
                            color: transparent;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                        `;
                        overlay.textContent = index;
                        overlayContainer.appendChild(overlay);
                        return overlay;
                    };
                    
                    // First: Search DOM tree for exact text matches
                    const searchDOMTree = (node, depth = 0) => {
                        if (!node || depth > 10) return null;
                        
                        // Check current node
                        if (node.nodeType === 1) { // Element node
                            const text = node.textContent?.trim();
                            const value = node.value;
                            const ariaLabel = node.getAttribute('aria-label');
                            const title = node.getAttribute('title');
                            const dataValue = node.getAttribute('data-value');
                            
                            // Skip non-product elements
                            const skipPatterns = ['country', 'localization', 'currency', 'language', 'region', 'shipping', 'search', 'filter', 'sort', 'breadcrumb', 'navigation'];
                            const elementInfo = (node.id + ' ' + node.className + ' ' + (node.name || '')).toLowerCase();
                            const shouldSkip = skipPatterns.some(pattern => elementInfo.includes(pattern));
                            
                            if (!shouldSkip) {
                                // Check for exact matches
                                if (match(text) || match(value) || match(ariaLabel) || match(title) || match(dataValue)) {
                                    // Determine if element is interactive
                                    const isInteractive = node.tagName === 'BUTTON' || 
                                                        node.tagName === 'A' || 
                                                        node.tagName === 'INPUT' || 
                                                        node.tagName === 'SELECT' ||
                                                        node.onclick || 
                                                        node.getAttribute('onclick') ||
                                                        node.style.cursor === 'pointer' ||
                                                        node.classList && node.classList.contains('clickable') ||
                                                        node.classList && node.classList.contains('selectable') ||
                                                        node.hasAttribute('role');
                                    
                                    if (isInteractive) {
                                        return node;
                                    }
                                    
                                    // Check if parent is interactive
                                    let parent = node.parentElement;
                                    let parentDepth = 0;
                                    while (parent && parentDepth < 3) {
                                        const parentInteractive = parent.tagName === 'BUTTON' || 
                                                                 parent.tagName === 'A' || 
                                                                 parent.onclick || 
                                                                 parent.getAttribute('onclick') ||
                                                                 parent.style.cursor === 'pointer' ||
                                                                 parent.classList && parent.classList.contains('clickable') ||
                                                                 parent.classList && parent.classList.contains('selectable');
                                        
                                        if (parentInteractive) {
                                            return parent;
                                        }
                                        parent = parent.parentElement;
                                        parentDepth++;
                                    }
                                }
                            }
                        }
                        
                        // Search children
                        for (const child of node.childNodes) {
                            const found = searchDOMTree(child, depth + 1);
                            if (found) return found;
                        }
                        
                        return null;
                    };
                    
                    // Index all clickable elements with overlays
                    const clickableSelectors = [
                        'button[name="Size"], button[name="Color"], button[name="Fit"]', // PRIORITY: Dillards Size/Color/Fit buttons
                        'input[type="radio"][name*="Shade"], input[type="radio"][name*="option"], input[type="radio"][name*="Color"]',
                        'input[type="number"], input[name*="quantity"], input[id*="quantity"], input[class*="quantity"]',
                        'select[name*="quantity"], select[id*="quantity"], select[class*="quantity"]',
                        'button[class*="quantity"], button[aria-label*="quantity"], button[class*="plus"], button[class*="minus"]',
                        'button[name="add"], button[class*="add-to-cart"], .action--add-to-cart', // Cart buttons
                        'button', 'a', 'select', 'input[type="button"]', 'input[type="submit"]',
                        '[role="button"]', '[onclick]', '.clickable', '.selectable'
                    ];
                    
                    let matchedIndex = null;
                    
                    for (const selector of clickableSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const element of elements) {
                            // Skip localization elements
                            if (element.id === 'LocalizationForm-Select' || 
                                element.classList && element.classList.contains('country-picker') ||
                                element.name === 'country_code') {
                                continue;
                            }
                            
                            const rect = element.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                const currentIndex = elementIndex++;
                                
                                // Check if this element matches our target
                                let isMatch = false;
                                let elementType = 'general';
                                
                                // Universal quantity detection patterns
                                const ariaLabel = (element.getAttribute('aria-label') || '').toLowerCase();
                                const className = (typeof element.className === 'string' ? element.className : element.className.toString()).toLowerCase();
                                const elementId = (element.id || '').toLowerCase();
                                const elementName = (element.name || '').toLowerCase();
                                const buttonText = (element.textContent || '').trim();
                                
                                // PRIORITY 1: Cart button detection - MUST come before quantity detection
                                if (normalizedVal.includes('cart') || normalizedVal.includes('add')) {
                                    if (element.tagName === 'BUTTON' && (
                                        element.name === 'add' ||
                                        element.name?.includes('add-to') ||
                                        element.id?.includes('add-to') ||
                                        (element.classList && element.classList.contains('add-to-cart')) ||
                                        (element.classList && element.classList.contains('add-to-bag')) ||
                                        buttonText.toLowerCase().includes('add to cart') ||
                                        buttonText.toLowerCase().includes('add to bag') ||
                                        buttonText.toLowerCase().includes('buy now') ||
                                        // Match standalone "ADD" button near product area
                                        (buttonText.toLowerCase().trim() === 'add' && element.type === 'submit') ||
                                        (buttonText.toLowerCase() === 'add' && element.classList && element.classList.contains('product')))) {
                                        elementType = 'cart_button';
                                        isMatch = true;
                                    }
                                }
                                
                                // PRIORITY 2: Quantity field detection - exclude cart buttons
                                if (!isMatch && (elementName.includes('quantity') || elementName.includes('qty') ||
                                    elementId.includes('quantity') || elementId.includes('qty') ||
                                    (element.classList && element.classList.contains('quantity')) || (element.classList && element.classList.contains('qty'))) &&
                                    !buttonText.toLowerCase().includes('add') &&
                                    !buttonText.toLowerCase().includes('cart') &&
                                    !buttonText.toLowerCase().includes('buy') &&
                                    !ariaLabel.includes('add') &&
                                    !ariaLabel.includes('cart') &&
                                    !(element.classList && element.classList.contains('cart')) &&
                                    !(element.classList && element.classList.contains('add-to-cart'))) {
                                    
                                    // Only match actual form inputs, not buttons
                                    if (element.tagName === 'SELECT' || element.tagName === 'INPUT' || 
                                        (element.tagName === 'BUTTON' && element.type !== 'submit')) {
                                        
                                        // Determine actual field type
                                        if (element.tagName === 'SELECT') {
                                            elementType = 'quantity_dropdown';
                                        } else if (element.type === 'number' || element.tagName === 'INPUT') {
                                            elementType = 'quantity_input';
                                        } else if (element.classList && element.classList.contains('dropdown') || element.getAttribute('role') === 'combobox') {
                                            elementType = 'quantity_dropdown';
                                        } else {
                                            elementType = 'quantity_input'; // fallback
                                        }
                                        isMatch = true;
                                    }
                                }
                                // Universal quantity buttons (only if no input field found)
                                else if (element.tagName === 'BUTTON' && !document.querySelector('input[type="number"], input[name*="quantity"], input[id*="quantity"], input[class*="quantity"]') && (
                                    ariaLabel.includes('increase') || ariaLabel.includes('add') || ariaLabel.includes('plus') ||
                                    (element.classList && element.classList.contains('plus')) || (element.classList && element.classList.contains('increase')) || (element.classList && element.classList.contains('increment')) ||
                                    buttonText === '+' || buttonText === '＋' || buttonText.includes('+'))) {
                                    elementType = 'quantity_increase';
                                    isMatch = true;
                                }
                                // Universal decrease button patterns (only if no input field found)
                                else if (element.tagName === 'BUTTON' && !document.querySelector('input[type="number"], input[name*="quantity"], input[id*="quantity"], input[class*="quantity"]') && (
                                    ariaLabel.includes('decrease') || ariaLabel.includes('subtract') || ariaLabel.includes('minus') ||
                                    (element.classList && element.classList.contains('minus')) || (element.classList && element.classList.contains('decrease')) || (element.classList && element.classList.contains('decrement')) ||
                                    buttonText === '-' || buttonText === '－' || buttonText.includes('-'))) {
                                    elementType = 'quantity_decrease';
                                    isMatch = true;
                                } else {
                                    // Regular text matching for other elements
                                    const texts = [
                                        element.textContent,
                                        element.value,
                                        element.getAttribute('aria-label'),
                                        element.getAttribute('title'),
                                        element.getAttribute('alt')
                                    ];
                                    
                                        // For radio buttons, also check associated label
                                    if (element.type === 'radio') {
                                        const label = document.querySelector(`label[for="${element.id}"]`);
                                        if (label) texts.push(label.textContent);
                                    }
                                    
                                    // Regular text matching (cart button already handled above)
                                    if (!isMatch) {
                                        for (const text of texts) {
                                            if (match(text)) {
                                                isMatch = true;
                                                break;
                                            }
                                        }
                                    }
                                }
                                
                                // Create overlay (green for matches, red for others)
                                const overlayColor = isMatch ? '#00ff00' : '#ff0000';
                                createOverlay(element, currentIndex, overlayColor);
                                
                                // Store element info
                                indexedElements.push({
                                    index: currentIndex,
                                    element: element,
                                    isMatch: isMatch,
                                    elementType: elementType,
                                    text: element.textContent?.trim() || '',
                                    value: element.value || '',
                                    tagName: element.tagName,
                                    type: element.type || '',
                                    id: element.id || '',
                                    className: element.className || ''
                                });
                                
                                if (isMatch && matchedIndex === null) {
                                    matchedIndex = currentIndex;
                                }
                            }
                        }
                    }
                    
                    if (matchedIndex !== null) {
                        // Determine action based on element type
                        const matchedElement = indexedElements.find(el => el.index === matchedIndex);
                        let action = 'click';
                        
                        if (matchedElement) {
                            if (matchedElement.elementType === 'quantity_input') {
                                action = 'quantity_input';
                            } else if (matchedElement.elementType === 'quantity_dropdown') {
                                action = 'quantity_dropdown';
                            } else if (matchedElement.elementType === 'quantity_increase' || matchedElement.elementType === 'quantity_decrease') {
                                action = 'quantity_button';
                            } else if (matchedElement.elementType === 'cart_button') {
                                action = 'click';
                            }
                        }
                        
                        return { found: true, action: action, elementIndex: matchedIndex, allElements: indexedElements, phase: 'overlay' };
                    }
                    
                    return { found: false, phase: 'overlay' };
                }
            """, variant_value)
            
            # If Phase 1 (overlay) found something, use it and move on
            if result['found'] and attempt == 0:
                logger.info(f"Phase 1 (Overlay): Found {variant_type}={variant_value}")
            else:
                if attempt == 0:
                    logger.info(f"Phase 1 (Overlay): Not found, trying Phase 2 (DOM Tree)")
                else:
                    logger.info(f"Attempt {attempt+1}: Trying Phase 2 (DOM Tree) for {variant_type}={variant_value}")
                
                # PHASE 2: DOM Tree Search
                result = await page.evaluate("""
                    (val) => {
                        const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                        const normalizedVal = normalize(val);
                        
                        const match = (text) => {
                            if (!text) return false;
                            const t = normalize(text);
                            
                            // Exact match
                            if (t === normalizedVal) return true;
                            
                            // Multi-word match
                            const searchWords = normalizedVal.split(/\s+/).filter(w => w.length > 0);
                            const textWords = t.split(/\s+/).filter(w => w.length > 0);
                            
                            if (searchWords.length >= 2) {
                                // First try exact phrase match
                                if (t.includes(normalizedVal)) {
                                    return true;
                                }
                                
                                // Then try all words present match
                                const hasAllWords = searchWords.every(word => 
                                    textWords.some(textWord => textWord === word || textWord.includes(word) || word.includes(textWord))
                                );
                                if (hasAllWords) return true;
                            }
                            
                            return false;
                        };
                        
                        // DOM tree search function
                        const searchDOMTree = (node, depth = 0) => {
                            if (!node || depth > 10) return null;
                            
                            if (node.nodeType === 1) {
                                const text = node.textContent?.trim();
                                const value = node.value;
                                const ariaLabel = node.getAttribute('aria-label');
                                const title = node.getAttribute('title');
                                const dataValue = node.getAttribute('data-value');
                                
                                // Skip non-product elements
                                const skipPatterns = ['country', 'localization', 'currency', 'language', 'region', 'shipping', 'search', 'filter', 'sort', 'breadcrumb', 'navigation'];
                                const elementInfo = (node.id + ' ' + node.className + ' ' + (node.name || '')).toLowerCase();
                                const shouldSkip = skipPatterns.some(pattern => elementInfo.includes(pattern));
                                
                                if (!shouldSkip) {
                                    if (match(text) || match(value) || match(ariaLabel) || match(title) || match(dataValue)) {
                                        const isInteractive = node.tagName === 'BUTTON' || 
                                                            node.tagName === 'A' || 
                                                            node.tagName === 'INPUT' || 
                                                            node.tagName === 'SELECT' ||
                                                            node.onclick || 
                                                            node.getAttribute('onclick') ||
                                                            node.style.cursor === 'pointer' ||
                                                            node.classList && node.classList.contains('clickable') ||
                                                            node.classList && node.classList.contains('selectable') ||
                                                            node.hasAttribute('role');
                                        
                                        if (isInteractive) {
                                            return node;
                                        }
                                        
                                        // Check parent elements
                                        let parent = node.parentElement;
                                        let parentDepth = 0;
                                        while (parent && parentDepth < 3) {
                                            const parentInteractive = parent.tagName === 'BUTTON' || 
                                                                     parent.tagName === 'A' || 
                                                                     parent.onclick || 
                                                                     parent.getAttribute('onclick') ||
                                                                     parent.style.cursor === 'pointer' ||
                                                                     parent.classList && parent.classList.contains('clickable') ||
                                                                     parent.classList && parent.classList.contains('selectable');
                                            
                                            if (parentInteractive) {
                                                return parent;
                                            }
                                            parent = parent.parentElement;
                                            parentDepth++;
                                        }
                                    }
                                }
                            }
                            
                            // Search children
                            for (const child of node.childNodes) {
                                const found = searchDOMTree(child, depth + 1);
                                if (found) return found;
                            }
                            
                            return null;
                        };
                        
                        // Search in product-focused containers
                        const productContainers = [
                            'form[data-product-id]',
                            '.variant-selector',
                            '.shade-selector', 
                            '[class*="product"]',
                            '[class*="variant"]', 
                            '[class*="option"]',
                            '[class*="shade"]',
                            'main',
                            'body'
                        ];
                        
                        for (const containerSelector of productContainers) {
                            const container = document.querySelector(containerSelector);
                            if (container) {
                                if (container.id === 'localization_form' || container.classList && container.classList.contains('localization')) {
                                    continue;
                                }
                                
                                const found = searchDOMTree(container);
                                if (found) {
                                    if (found.id === 'LocalizationForm-Select' || 
                                        found.classList && found.classList.contains('country-picker') ||
                                        found.name === 'country_code') {
                                        continue;
                                    }
                                    
                                    found.setAttribute('data-dom-el', 'true');
                                    
                                    let action = 'click';
                                    if (found.tagName === 'SELECT') {
                                        action = 'select';
                                        for (const option of found.options) {
                                            if (match(option.text)) {
                                                return { found: true, action: 'select', value: option.value, phase: 'dom_tree' };
                                            }
                                        }
                                    } else if (found.classList && found.classList.contains('dropdown') || found.classList && found.classList.contains('select') || found.hasAttribute('role') && found.getAttribute('role').includes('combobox')) {
                                        action = 'dropdown';
                                    } else if (found.tagName === 'INPUT' && found.type === 'number') {
                                        action = 'quantity_input';
                                    }
                                    
                                    return { found: true, action: action, searchValue: val, phase: 'dom_tree' };
                                }
                            }
                        }
                        
                        return { found: false, phase: 'dom_tree' };
                    }
                """, variant_value)
                
                if result['found']:
                    logger.info(f"Phase 2 (DOM Tree): Found {variant_type}={variant_value}")
                else:
                    logger.info(f"Phase 2 (DOM Tree): Not found, trying Phase 3 (Pattern Match)")
                    
                    # PHASE 3: Pattern Matching
                    result = await page.evaluate("""
                        (val) => {
                            const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                            const normalizedVal = normalize(val);
                            
                            const match = (text) => {
                                if (!text) return false;
                                const t = normalize(text);
                                
                                // Exact match
                                if (t === normalizedVal) return true;
                                
                                // Multi-word match
                                const searchWords = normalizedVal.split(/\s+/).filter(w => w.length > 0);
                                const textWords = t.split(/\s+/).filter(w => w.length > 0);
                                
                                if (searchWords.length >= 2) {
                                    // First try exact phrase match
                                    if (t.includes(normalizedVal)) {
                                        return true;
                                    }
                                    
                                    // Then try all words present match
                                    const hasAllWords = searchWords.every(word => 
                                        textWords.some(textWord => textWord === word || textWord.includes(word) || word.includes(textWord))
                                    );
                                    if (hasAllWords) return true;
                                }
                                
                                return false;
                            };
                            
                            // Clear markers
                            document.querySelectorAll('[data-dom-el]').forEach(el => el.removeAttribute('data-dom-el'));
                            const skipElements = new Set(document.querySelectorAll('[data-already-selected]'));
                            
                            // Universal search patterns
                            const searchPatterns = [
                                // Native SELECT dropdowns (highest priority for size/variant selection)
                                { selector: 'select', action: 'select',
                                  extraCheck: (el) => {
                                      // Skip localization/country selects
                                      if (el.id === 'LocalizationForm-Select' || el.name === 'country_code') return false;
                                      
                                      // Check if any option matches
                                      for (const option of el.options) {
                                          if (match(option.text) || match(option.value)) {
                                              return true;
                                          }
                                      }
                                      return false;
                                  }
                                },
                                
                                // Size radio buttons (specific pattern for Hollister/A&F)
                                { selector: 'input[name="pdp_size-primary"], input[name="pdp_size-secondary"]', action: 'click',
                                  extraCheck: (el) => {
                                      const label = document.querySelector(`label[for="${el.id}"]`);
                                      const labelText = label?.querySelector('.sitg-label-text')?.textContent;
                                      if (match(labelText) || match(el.value) || match(el.getAttribute('aria-label'))) return true;
                                      
                                      // Check label's title and children's title
                                      if (label) {
                                          if (match(label.getAttribute('title'))) return true;
                                          const childrenWithTitle = label.querySelectorAll('[title]');
                                          for (const child of childrenWithTitle) {
                                              if (match(child.getAttribute('title'))) return true;
                                          }
                                      }
                                      return false;
                                  }
                                },
                                
                                // Dropdowns and comboboxes (including Vue Select) - only if they contain the search value
                                { selector: '.v-select, .vs__dropdown-toggle, .vs__selected-options, .dropdown, [role="combobox"], select, [class*="dropdown"], [class*="select"]', action: 'dropdown',
                                  extraCheck: (el) => {
                                      // Skip quantity, size, and other non-matching dropdowns
                                      if ((el.classList && el.classList.contains('quantity')) || el.closest('.quantity-selector')) {
                                          return false;
                                      }
                                      const excludePatterns = ['country', 'localization', 'currency', 'language', 'region', 'shipping', 'search', 'filter', 'sort', 'size'];
                                      const elementInfo = (el.id + ' ' + el.className + ' ' + (el.name || '') + ' ' + (el.textContent || '')).toLowerCase();
                                      if (excludePatterns.some(pattern => elementInfo.includes(pattern))) {
                                          return false;
                                      }
                                      // Only match if dropdown actually contains the search value
                                      const dropdownTexts = [
                                          el.textContent,
                                          el.value,
                                          el.getAttribute('aria-label'),
                                          el.getAttribute('title')
                                      ];
                                      return dropdownTexts.some(text => match(text));
                                  }
                                },
                                
                                // Labels containing radio buttons or checkboxes (size buttons, etc.)
                                { selector: 'label', action: 'click', 
                                  extraCheck: (el) => {
                                      // Check if label contains input OR points to input via 'for'
                                      let input = el.querySelector('input[type="radio"], input[type="checkbox"]');
                                      if (!input && el.getAttribute('for')) {
                                          input = document.getElementById(el.getAttribute('for'));
                                      }
                                      if (!input || (input.type !== 'radio' && input.type !== 'checkbox')) return false;
                                      
                                      // Check label text content
                                      if (match(el.textContent)) return true;
                                      
                                      // Check label's title attribute
                                      if (match(el.getAttribute('title'))) return true;
                                      
                                      // Check all child elements' title attributes
                                      const childrenWithTitle = el.querySelectorAll('[title]');
                                      for (const child of childrenWithTitle) {
                                          if (match(child.getAttribute('title'))) return true;
                                      }
                                      
                                      // Check the input value and attributes
                                      if (match(input.value) || match(input.getAttribute('aria-label'))) return true;
                                      
                                      // Check associated images for color swatches
                                      const parentSection = el.closest('section');
                                      const img = parentSection?.querySelector('img');
                                      if (img && match(img.alt)) return true;
                                      
                                      return false;
                                  }
                                },
                                
                                // Fallback for standalone radio/checkbox inputs
                                { selector: 'input[type="radio"], input[type="checkbox"]', action: 'click', 
                                  extraCheck: (el) => {
                                      // Skip if already handled by parent label
                                      if (el.closest('label')) return false;
                                      
                                      // Check input's own attributes first
                                      if (match(el.value) || match(el.getAttribute('aria-label'))) return true;
                                      
                                      // Check associated label via 'for' attribute
                                      const label = document.querySelector(`label[for="${el.id}"]`);
                                      if (label) {
                                          if (match(label.textContent)) return true;
                                          if (match(label.getAttribute('title'))) return true;
                                          
                                          // Check label's children with title
                                          const childrenWithTitle = label.querySelectorAll('[title]');
                                          for (const child of childrenWithTitle) {
                                              if (match(child.getAttribute('title'))) return true;
                                          }
                                      }
                                      
                                      // Check images in parent section
                                      const parentSection = el.closest('section');
                                      const img = parentSection?.querySelector('img');
                                      if (img && match(img.alt)) return true;
                                      
                                      return false;
                                  }
                                },
                                
                                // Universal element traversal (images, labels, spans, divs)
                                { selector: 'img, label, span, div, li, td, a', action: 'click',
                                  extraCheck: (el) => {
                                      // Check if current element matches
                                      const elementTexts = [
                                          el.textContent?.trim(),
                                          el.alt,
                                          el.getAttribute('aria-label'),
                                          el.getAttribute('title'),
                                          el.getAttribute('data-value'),
                                          el.value
                                      ];
                                      
                                      const hasMatch = elementTexts.some(text => match(text));
                                      if (!hasMatch) return false;
                                      
                                      // Universal traversal to find best clickable element
                                      
                                      // Priority 1: Check if element is inside a label with 'for' attribute
                                      let labelParent = el.closest('label[for]');
                                      if (labelParent) {
                                          const targetInput = document.getElementById(labelParent.getAttribute('for'));
                                          if (targetInput && (targetInput.type === 'radio' || targetInput.type === 'checkbox')) {
                                              targetInput.setAttribute('data-dom-el', 'true');
                                              return false;
                                          }
                                      }
                                      
                                      // Priority 2: Look for associated radio/checkbox by traversing up and down
                                      let current = el;
                                      let attempts = 0;
                                      
                                      while (current && attempts < 10) {
                                          // Look for radio/checkbox inputs in current container
                                          const inputs = current.querySelectorAll ? current.querySelectorAll('input[type="radio"], input[type="checkbox"]') : [];
                                          for (const input of inputs) {
                                              if (input.offsetParent !== null) {
                                                  input.setAttribute('data-dom-el', 'true');
                                                  return false;
                                              }
                                          }
                                          
                                          // Look for labels with 'for' attribute in current container
                                          const labels = current.querySelectorAll ? current.querySelectorAll('label[for]') : [];
                                          for (const label of labels) {
                                              const targetInput = document.getElementById(label.getAttribute('for'));
                                              if (targetInput && (targetInput.type === 'radio' || targetInput.type === 'checkbox')) {
                                                  targetInput.setAttribute('data-dom-el', 'true');
                                                  return false;
                                              }
                                          }
                                          
                                          // Look for buttons
                                          const buttons = current.querySelectorAll ? current.querySelectorAll('button') : [];
                                          for (const button of buttons) {
                                              if (button.offsetParent !== null) {
                                                  button.setAttribute('data-dom-el', 'true');
                                                  return false;
                                              }
                                          }
                                          
                                          // Check if current element itself is clickable
                                          const isClickable = current.onclick || 
                                                            current.getAttribute('onclick') ||
                                                            current.style.cursor === 'pointer' ||
                                                            (current.classList && current.classList.contains('clickable')) ||
                                                            (current.classList && current.classList.contains('selectable')) ||
                                                            current.hasAttribute('role');
                                          
                                          if (isClickable && current.offsetParent !== null) {
                                              current.setAttribute('data-dom-el', 'true');
                                              return false;
                                          }
                                          
                                          // Move to parent and continue traversal
                                          current = current.parentElement;
                                          attempts++;
                                      }
                                      
                                      // If no better element found, use original element
                                      return true;
                                  }
                                },
                                
                                // Quantity inputs
                                { selector: 'input[type="number"], input[type="text"], input:not([type])', action: 'quantity_input',
                                  extraCheck: (el) => {
                                      const name = (el.name || '').toLowerCase();
                                      const id = (el.id || '').toLowerCase();
                                      const className = (el.className || '').toLowerCase();
                                      return name.includes('quantity') || name.includes('qty') ||
                                             id.includes('quantity') || id.includes('qty') ||
                                             (el.classList && el.classList.contains('quantity')) || (el.classList && el.classList.contains('qty'));
                                  }
                                },
                                
                                // Quantity buttons
                                { selector: 'button, [role="button"]', action: 'quantity_button',
                                  extraCheck: (el) => {
                                      const text = (el.textContent || '').trim();
                                      const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
                                      const className = (el.className || '').toLowerCase();
                                      return text === '+' || text === '-' || text === '＋' || text === '－' ||
                                             ariaLabel.includes('increase') || ariaLabel.includes('decrease') ||
                                             ariaLabel.includes('plus') || ariaLabel.includes('minus') ||
                                             (el.classList && el.classList.contains('quantity')) && ((el.classList && el.classList.contains('plus')) || (el.classList && el.classList.contains('minus')) || (el.classList && el.classList.contains('increment')) || (el.classList && el.classList.contains('decrement')));
                                  }
                                },
                                
                                // Buttons
                                { selector: 'button, [role="button"]', action: 'click',
                                  extraCheck: (el) => match(el.textContent) || match(el.getAttribute('aria-label')) || 
                                                    match(el.value) || match(el.getAttribute('title'))
                                },
                                

                                
                                // Color swatch links (specific for Lulus-style swatches)
                                { selector: 'a[aria-label*="Change selection to"], a[aria-label*="Current selection"]', action: 'click',
                                  extraCheck: (el) => {
                                      const ariaLabel = el.getAttribute('aria-label') || '';
                                      // Extract color name from aria-label like "Change selection to Beige"
                                      const colorMatch = ariaLabel.match(/(?:Change selection to|Current selection:)\s+(.+)/);
                                      if (colorMatch && colorMatch[1]) {
                                          return match(colorMatch[1]);
                                      }
                                      return match(ariaLabel);
                                  }
                                },
                                
                                // Links and clickable elements
                                { selector: 'a, [onclick], [class*="clickable"], [class*="selectable"]', action: 'click',
                                  extraCheck: (el) => match(el.textContent) || match(el.getAttribute('aria-label'))
                                },
                                
                                // Color swatches and images
                                { selector: 'a[class*="swatch"], img[alt*="Beige"], img[alt*="Black"], img[alt*="White"], img[alt*="Red"], img[alt*="Blue"], img[alt*="Green"], img[alt*="Brown"], img[alt*="Gray"], img[alt*="Pink"], img[alt*="Purple"], img[alt*="Yellow"], img[alt*="Orange"], [class*="swatch"], [class*="color"]', action: 'click',
                                  extraCheck: (el) => {
                                      // Check element itself
                                      if (match(el.alt) || match(el.getAttribute('title')) || 
                                          match(el.getAttribute('data-color')) || match(el.getAttribute('data-value')) ||
                                          match(el.getAttribute('aria-label'))) return true;
                                      
                                      // Check parent link for aria-label
                                      const parentLink = el.closest('a');
                                      if (parentLink && match(parentLink.getAttribute('aria-label'))) return true;
                                      
                                      // Check child images
                                      const childImg = el.querySelector('img');
                                      if (childImg && (match(childImg.alt) || match(childImg.getAttribute('aria-label')))) return true;
                                      
                                      return false;
                                  }
                                },
                                
                                // Generic clickable elements with data attributes
                                { selector: '[data-caption], [data-value], [data-option], [data-variant], [data-size], [data-color]', action: 'click',
                                  extraCheck: (el) => {
                                      const dataAttrs = ['data-caption', 'data-value', 'data-option', 'data-variant', 'data-size', 'data-color'];
                                      return dataAttrs.some(attr => match(el.getAttribute(attr)));
                                  }
                                },
                                
                                // Text elements
                                { selector: 'span, div, label, li, td', action: 'click',
                                  extraCheck: (el) => {
                                      const text = el.textContent?.trim();
                                      return text && text.length < 100 && match(text) && 
                                             (el.onclick || el.getAttribute('onclick') || 
                                              el.style.cursor === 'pointer' || 
                                              (el.classList && el.classList.contains('clickable')) ||
                                              (el.classList && el.classList.contains('selectable')));
                                  }
                                }
                            ];
                            
                            // Search through patterns
                            for (const pattern of searchPatterns) {
                                const elements = document.querySelectorAll(pattern.selector);
                                for (const el of elements) {
                                    if (skipElements.has(el)) continue;
                                    
                                    let isMatch = false;
                                    if (pattern.extraCheck) {
                                        isMatch = pattern.extraCheck(el);
                                    } else {
                                        isMatch = match(el.textContent) || match(el.value) || match(el.getAttribute('aria-label'));
                                    }
                                    
                                    if (isMatch) {
                                        el.setAttribute('data-dom-el', 'true');
                                        const actionData = { found: true, action: pattern.action, phase: 'pattern_match' };
                                        
                                        if (pattern.action === 'dropdown' && el.tagName === 'SELECT') {
                                            for (const option of el.options) {
                                                if (match(option.text)) {
                                                    actionData.value = option.value;
                                                    actionData.action = 'select';
                                                    break;
                                                }
                                            }
                                        } else if (pattern.action === 'dropdown') {
                                            actionData.searchValue = val;
                                        } else if (pattern.action === 'input') {
                                            actionData.value = val;
                                        }
                                        
                                        return actionData;
                                    }
                                }
                            }
                            
                            return { found: false, phase: 'pattern_match' };
                        }
                    """, variant_value)
                    
                    if result['found']:
                        logger.info(f"Phase 3 (Pattern Match): Found {variant_type}={variant_value}")
                    else:
                        logger.info(f"Phase 3 (Pattern Match): Not found - element does not exist")
                        # Force overlay search as final fallback
                        if attempt > 0:
                            logger.info(f"Final fallback: Trying Phase 1 (Overlay) again")
                            result = await page.evaluate("""
                                (val) => {
                                    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                                    const normalizedVal = normalize(val);
                                    
                                    const match = (text) => {
                                        if (!text) return false;
                                        const t = normalize(text);
                                        if (t === normalizedVal) return true;
                                        const searchWords = normalizedVal.split(/\s+/).filter(w => w.length > 0);
                                        const textWords = t.split(/\s+/).filter(w => w.length > 0);
                                        if (searchWords.length >= 2) {
                                            // First try exact phrase match
                                            if (t.includes(normalizedVal)) {
                                                return true;
                                            }
                                            
                                            // Then try all words present match
                                            const hasAllWords = searchWords.every(word => 
                                                textWords.some(textWord => textWord === word || textWord.includes(word) || word.includes(textWord))
                                            );
                                            if (hasAllWords) return true;
                                        }
                                        return false;
                                    };
                                    
                                    // Quick overlay search for any matching element
                                    const clickableSelectors = ['button', 'a', 'input', 'select', '[onclick]', '[role="button"]'];
                                    for (const selector of clickableSelectors) {
                                        const elements = document.querySelectorAll(selector);
                                        for (const element of elements) {
                                            const texts = [element.textContent, element.value, element.getAttribute('aria-label')];
                                            for (const text of texts) {
                                                if (match(text)) {
                                                    element.setAttribute('data-dom-el', 'true');
                                                    return { found: true, action: 'click', phase: 'overlay_fallback' };
                                                }
                                            }
                                        }
                                    }
                                    return { found: false, phase: 'overlay_fallback' };
                                }
                            """, variant_value)
                            
                            if result['found']:
                                logger.info(f"Final fallback (Overlay): Found {variant_type}={variant_value}")
            
            if result['found']:
                # Execute action
                if result['action'] == 'select':
                    element_index = result.get('elementIndex')
                    if element_index is not None:
                        await page.evaluate("""
                            (args) => {
                                const { targetIndex, value } = args;
                                const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                                if (overlay) {
                                    const rect = overlay.getBoundingClientRect();
                                    const centerX = rect.left + (rect.width / 2);
                                    const centerY = rect.top + (rect.height / 2);
                                    const selectElement = document.elementFromPoint(centerX, centerY);
                                    if (selectElement && selectElement.tagName === 'SELECT') {
                                        selectElement.value = value;
                                        selectElement.dispatchEvent(new Event('change', { bubbles: true }));
                                    }
                                }
                            }
                        """, {'targetIndex': element_index, 'value': result['value']})
                    else:
                        await page.select_option('[data-dom-el]', result['value'])
                    
                elif result['action'] == 'dropdown':
                    element_index = result.get('elementIndex')

                    # Ensure dropdown is in viewport before interaction. TODO: Refine scrolling logic and move this to a utility function
                    if element_index is not None:
                        await page.evaluate("""
                            (targetIndex) => {
                                const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                                if (overlay) {
                                    const rect = overlay.getBoundingClientRect();
                                    const centerX = rect.left + (rect.width / 2);
                                    const centerY = rect.top + (rect.height / 2);
                                    const el = document.elementFromPoint(centerX, centerY);
                                    if (el) {
                                        const elementRect = el.getBoundingClientRect();
                                        const isInViewport = elementRect.top >= 0 && elementRect.left >= 0 && 
                                                           elementRect.bottom <= window.innerHeight && 
                                                           elementRect.right <= window.innerWidth;
                                        if (!isInViewport) {
                                            el.scrollIntoView({block: 'center', behavior: 'smooth'});
                                        }
                                    }
                                }
                            }
                        """, element_index)
                        await asyncio.sleep(0.5)  # Wait for scroll
                    
                    # Debug: Log what element was found
                    if element_index is not None:
                        element_info = await page.evaluate("""
                            (targetIndex) => {
                                const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                                if (!overlay) return 'No overlay found';
                                const rect = overlay.getBoundingClientRect();
                                const centerX = rect.left + (rect.width / 2);
                                const centerY = rect.top + (rect.height / 2);
                                const el = document.elementFromPoint(centerX, centerY);
                                if (!el) return 'No element found';
                                return {
                                    tagName: el.tagName,
                                    className: el.className,
                                    id: el.id,
                                    textContent: el.textContent?.substring(0, 100)
                                };
                            }
                        """, element_index)
                    else:
                        # Ensure DOM element is in viewport
                        await page.evaluate("""
                            () => {
                                const el = document.querySelector('[data-dom-el]');
                                if (el) {
                                    const rect = el.getBoundingClientRect();
                                    const isInViewport = rect.top >= 0 && rect.left >= 0 && 
                                                       rect.bottom <= window.innerHeight && 
                                                       rect.right <= window.innerWidth;
                                    if (!isInViewport) {
                                        el.scrollIntoView({block: 'center', behavior: 'smooth'});
                                    }
                                }
                            }
                        """)
                        await asyncio.sleep(0.5)
                        
                        element_info = await page.evaluate("""
                            () => {
                                const el = document.querySelector('[data-dom-el]');
                                if (!el) return 'No element found';
                                return {
                                    tagName: el.tagName,
                                    className: el.className,
                                    id: el.id,
                                    textContent: el.textContent?.substring(0, 100)
                                };
                            }
                        """)
                    logger.info(f"Dropdown element found: {element_info}")
                    
                    # Try multiple click strategies
                    if element_index is not None:
                        dropdown_clicked = await page.evaluate("""
                            (targetIndex) => {
                                const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                                if (!overlay) return {success: false, reason: 'No overlay found'};
                                
                                const rect = overlay.getBoundingClientRect();
                                const centerX = rect.left + (rect.width / 2);
                                const centerY = rect.top + (rect.height / 2);
                                const targetEl = document.elementFromPoint(centerX, centerY);
                                if (!targetEl) return {success: false, reason: 'No target element'};
                        """, element_index)
                    else:
                        dropdown_clicked = await page.evaluate("""
                            () => {
                                const targetEl = document.querySelector('[data-dom-el]');
                                if (!targetEl) return {success: false, reason: 'No target element'};
                            
                            // Strategy 1: Direct click on target
                            try {
                                targetEl.scrollIntoView({block: 'center'});
                                if (typeof targetEl.click === 'function') {
                                    targetEl.click();
                                    return {success: true, strategy: 'direct'};
                                } else {
                                    console.log('Element does not have click function');
                                }
                            } catch (e) {
                                console.log('Direct click failed:', e);
                            }
                            
                            // Strategy 2: Find Vue Select dropdown toggle
                            const vueSelect = targetEl.closest('.v-select') || document.querySelector('.v-select');
                            if (vueSelect) {
                                const toggle = vueSelect.querySelector('.vs__dropdown-toggle');
                                if (toggle) {
                                    try {
                                        toggle.scrollIntoView({block: 'center'});
                                        if (typeof toggle.click === 'function') {
                                            toggle.click();
                                            return {success: true, strategy: 'vue-toggle'};
                                        }
                                    } catch (e) {
                                        console.log('Vue toggle click failed:', e);
                                    }
                                }
                            }
                            
                            // Strategy 3: Parent traversal with clickability check
                            let currentEl = targetEl;
                            let attempts = 0;
                            const maxAttempts = 5;
                            
                            while (currentEl && attempts < maxAttempts) {
                                try {
                                    // Check if element is clickable
                                    const rect = currentEl.getBoundingClientRect();
                                    const style = window.getComputedStyle(currentEl);
                                    
                                    const isClickable = rect.width > 0 && rect.height > 0 && 
                                                       style.display !== 'none' && 
                                                       style.visibility !== 'hidden' && 
                                                       style.pointerEvents !== 'none';
                                    
                                    if (isClickable) {
                                        currentEl.scrollIntoView({block: 'center'});
                                        if (typeof currentEl.click === 'function') {
                                            currentEl.click();
                                            return {success: true, strategy: 'traversal', element: currentEl.tagName + '.' + currentEl.className};
                                        }
                                    }
                                } catch (e) {
                                    console.log(`Click failed on ${currentEl.tagName}, trying parent:`, e);
                                }
                                
                                // Move to parent element
                                currentEl = currentEl.parentElement;
                                attempts++;
                            }
                            
                            return {success: false, reason: 'All strategies failed including parent traversal'};
                        }
                    """)
                    
                    logger.info(f"Dropdown click result: {dropdown_clicked}")
                    
                    if dropdown_clicked.get('success'):
                        await asyncio.sleep(1.5)  # Wait for dropdown to expand
                        
                        # Find and click the option
                        clicked = await page.evaluate("""
                            (val) => {
                                const normalize = (text) => text ? text.toLowerCase().trim() : '';
                                const match = (text) => normalize(text).includes(normalize(val));
                                
                                const selectors = [
                                    '[role="option"]', 'option', 'li', 
                                    '[class*="option"]', '[class*="item"]', 
                                    '[class*="choice"]', '[class*="select"]',
                                    '.vs__dropdown-option', '[class*="vs__option"]'
                                ];
                                
                                for (const sel of selectors) {
                                    for (const opt of document.querySelectorAll(sel)) {
                                        if (match(opt.textContent)) {
                                            opt.scrollIntoView({block: 'center'});
                                            opt.click();
                                            return true;
                                        }
                                    }
                                }
                                return false;
                            }
                        """, result.get('searchValue', variant_value))
                        
                        if not clicked:
                            raise Exception("Dropdown option not found after expansion")
                    else:
                        # Final fallback: Force click with Playwright
                        try:
                            await page.evaluate('document.querySelector("[data-dom-el]").scrollIntoView({block: "center"})')
                            await asyncio.sleep(0.5)
                            await page.click('[data-dom-el]', timeout=3000, force=True)
                            await asyncio.sleep(1.5)
                            
                            # Try to find options after force click
                            clicked = await page.evaluate("""
                                (val) => {
                                    const normalize = (text) => text ? text.toLowerCase().trim() : '';
                                    const match = (text) => normalize(text).includes(normalize(val));
                                    
                                    const selectors = [
                                        '[role="option"]', 'option', 'li', 
                                        '[class*="option"]', '[class*="item"]', 
                                        '[class*="choice"]', '[class*="select"]',
                                        '.vs__dropdown-option', '[class*="vs__option"]'
                                    ];
                                    
                                    for (const sel of selectors) {
                                        for (const opt of document.querySelectorAll(sel)) {
                                            if (match(opt.textContent)) {
                                                opt.scrollIntoView({block: 'center'});
                                                opt.click();
                                                return true;
                                            }
                                        }
                                    }
                                    return false;
                                }
                            """, result.get('searchValue', variant_value))
                            
                            if not clicked:
                                raise Exception("Dropdown option not found even after force click")
                                
                        except Exception as force_error:
                            raise Exception(f"All dropdown strategies failed: {dropdown_clicked.get('reason', 'Unknown')} | JavaScript fallback: {force_error}")
                        
                elif result['action'] == 'quantity_dropdown':
                    # Handle quantity dropdown selection
                    element_index = result.get('elementIndex')
                    target_quantity = variant_value
                    
                    # First try to open dropdown and select option
                    dropdown_result = await page.evaluate("""
                        (args) => {
                            const { targetIndex, quantity } = args;
                            const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                            if (!overlay) return { success: false, reason: 'No overlay found' };
                            
                            const rect = overlay.getBoundingClientRect();
                            const centerX = rect.left + (rect.width / 2);
                            const centerY = rect.top + (rect.height / 2);
                            const element = document.elementFromPoint(centerX, centerY);
                            
                            if (!element) return { success: false, reason: 'No element found' };
                            
                            console.log('🔽 Dropdown element:', element.tagName, element.className);
                            
                            // Handle SELECT dropdown
                            if (element.tagName === 'SELECT') {
                                console.log('📋 Native SELECT dropdown detected');
                                for (const option of element.options) {
                                    if (option.value === quantity || option.text.trim() === quantity) {
                                        element.value = option.value;
                                        element.dispatchEvent(new Event('change', { bubbles: true }));
                                        element.dispatchEvent(new Event('input', { bubbles: true }));
                                        console.log('✅ Selected option:', option.text);
                                        return { success: true, method: 'select', value: option.value, text: option.text };
                                    }
                                }
                                return { success: false, reason: 'Option not found in select' };
                            }
                            
                            // Handle custom dropdown - click to open
                            console.log('🎯 Custom dropdown detected, clicking to open...');
                            element.scrollIntoView({ block: 'center', behavior: 'smooth' });
                            
                            // Mark the dropdown for reference
                            element.setAttribute('data-dropdown-opened', 'true');
                            
                            // Try multiple click strategies
                            let clicked = false;
                            try {
                                element.click();
                                clicked = true;
                            } catch (e) {
                                console.log('Direct click failed:', e.message);
                                // Try dispatching click event
                                element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                                clicked = true;
                            }
                            
                            if (clicked) {
                                console.log('✅ Dropdown opened');
                                return { success: true, method: 'click', needsOption: true, dropdownElement: element.className };
                            }
                            
                            return { success: false, reason: 'Cannot interact with dropdown' };
                        }
                    """, {'targetIndex': element_index, 'quantity': target_quantity})
                    
                    logger.info(f"Quantity dropdown result: {dropdown_result}")
                    
                    # If dropdown was opened, find and click the option
                    if dropdown_result.get('needsOption'):
                        # Wait longer for dropdown to fully render and animate
                        await asyncio.sleep(1.5)
                        
                        # Try to find and click the option with multiple strategies
                        option_clicked = await page.evaluate("""
                            (quantity) => {
                                console.log('🔍 Looking for option:', quantity);
                                
                                // Strategy 1: Look for the opened dropdown container first
                                const dropdownTrigger = document.querySelector('[data-dropdown-opened="true"]');
                                let searchRoot = document;
                                
                                if (dropdownTrigger) {
                                    console.log('📍 Found dropdown trigger, searching nearby...');
                                    // Look for dropdown menu near the trigger
                                    const parent = dropdownTrigger.closest('[class*="dropdown"], [class*="select"], [class*="menu"]');
                                    if (parent) {
                                        searchRoot = parent;
                                        console.log('🎯 Searching within parent container');
                                    }
                                }
                                
                                // Common selectors for dropdown options
                                const selectors = [
                                    '[role="option"]',
                                    '[role="listitem"]', 
                                    'li[class*="option"]',
                                    'li[class*="item"]',
                                    'div[class*="option"]',
                                    'div[class*="item"]',
                                    'button[class*="option"]',
                                    'a[class*="option"]',
                                    '[data-value]',
                                    '.dropdown-item',
                                    '.select-option'
                                ];
                                
                                console.log('📋 Searching with', selectors.length, 'selectors...');
                                
                                for (const selector of selectors) {
                                    const options = searchRoot.querySelectorAll(selector);
                                    console.log('  Selector', selector, ':', options.length, 'elements');
                                    
                                    for (const option of options) {
                                        // Skip if element is not visible
                                        const rect = option.getBoundingClientRect();
                                        if (rect.width === 0 || rect.height === 0) continue;
                                        
                                        const text = option.textContent?.trim();
                                        const value = option.getAttribute('data-value') || option.getAttribute('value') || option.value;
                                        
                                        console.log('    Checking:', text, '| value:', value);
                                        
                                        // Match by text or value
                                        if (text === quantity || value === quantity || 
                                            text === quantity.toString() || value === quantity.toString()) {
                                            
                                            console.log('✅ FOUND MATCH:', text || value);
                                            
                                            // Scroll option into view within its container
                                            option.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                                            
                                            // Small delay for scroll
                                            setTimeout(() => {
                                                console.log('🖱️ Clicking option...');
                                                
                                                // Try multiple click strategies
                                                try {
                                                    option.click();
                                                    console.log('✅ Click successful');
                                                } catch (e) {
                                                    console.log('Direct click failed, trying event dispatch');
                                                    option.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                                                    option.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                                                    option.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                                }
                                            }, 200);
                                            
                                            return { success: true, text: text, value: value, selector: selector };
                                        }
                                    }
                                }
                                
                                console.log('❌ No matching option found');
                                return { success: false, reason: 'Option not found in dropdown' };
                            }
                        """, target_quantity)
                        
                        logger.info(f"Quantity option click result: {option_clicked}")
                        
                        # Wait for click to register
                        if option_clicked.get('success'):
                            await asyncio.sleep(1.0)
                            logger.info(f"VARIANT SELECTION: Quantity dropdown selection completed: {option_clicked.get('text')} selected")
                            return {
                                'success': True,
                                'content': f"SUCCESS: quantity={target_quantity} selected from dropdown",
                                'action': 'quantity_dropdown'
                            }
                        else:
                            logger.warning(f"VARIANT SELECTION: Failed to select option from dropdown: {option_clicked.get('reason')}")
                            # Continue to next attempt
                            continue
                    elif dropdown_result.get('success') and dropdown_result.get('method') == 'select':
                        # Native select dropdown was handled successfully
                        logger.info(f"VARIANT SELECTION: Native select quantity set: {dropdown_result.get('text')}")
                        return {
                            'success': True,
                            'content': f"SUCCESS: quantity={target_quantity} selected from native select",
                            'action': 'quantity_dropdown'
                        }
                    else:
                        # Dropdown interaction failed
                        logger.warning(f"VARIANT SELECTION: Dropdown interaction failed: {dropdown_result.get('reason')}")
                        # Continue to next attempt
                        continue
                    
                elif result['action'] == 'quantity_input':
                    # Skip if this is actually a cart action being misidentified
                    if variant_type.lower() in ['cart', 'add_to_cart', 'add_to_bag'] or 'cart' in variant_value.lower() or 'add' in variant_value.lower():
                        logger.warning(f"Cart action misidentified as quantity_input, skipping: {variant_type}={variant_value}")
                        continue
                    
                    # Handle quantity input using element index with viewport scrolling
                    element_index = result.get('elementIndex')
                    target_quantity = variant_value
                    
                    # Ensure quantity input is in viewport and focus it
                    cleared_and_typed = await page.evaluate("""
                        (targetIndex) => {
                            const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                            if (!overlay) return false;
                            
                            const rect = overlay.getBoundingClientRect();
                            const centerX = rect.left + (rect.width / 2);
                            const centerY = rect.top + (rect.height / 2);
                            
                            const inputElement = document.elementFromPoint(centerX, centerY);
                            if (inputElement && (inputElement.type === 'number' || inputElement.name?.includes('quantity'))) {
                                // Check if element is in viewport, scroll if needed
                                const elementRect = inputElement.getBoundingClientRect();
                                const isInViewport = elementRect.top >= 0 && elementRect.left >= 0 && 
                                                   elementRect.bottom <= window.innerHeight && 
                                                   elementRect.right <= window.innerWidth;
                                
                                if (!isInViewport) {
                                    inputElement.scrollIntoView({block: 'center', behavior: 'smooth'});
                                }
                                
                                inputElement.focus();
                                return true;
                            }
                            return false;
                        }
                    """, element_index)
                    
                    if cleared_and_typed:
                        # Set quantity using JavaScript with enhanced event handling and persistence check
                        set_result = await page.evaluate("""
                            (args) => {
                                const { targetIndex, quantity } = args;
                                const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                                if (overlay) {
                                    const rect = overlay.getBoundingClientRect();
                                    const centerX = rect.left + (rect.width / 2);
                                    const centerY = rect.top + (rect.height / 2);
                                    const inputElement = document.elementFromPoint(centerX, centerY);
                                    if (inputElement && (inputElement.type === 'number' || inputElement.name?.includes('quantity'))) {
                                        // Store original value for comparison
                                        const originalValue = inputElement.value;
                                        
                                        // Set value with comprehensive event handling
                                        inputElement.focus();
                                        inputElement.value = quantity;
                                        
                                        // Dispatch multiple events to ensure website recognition
                                        const events = ['input', 'change', 'keyup', 'blur'];
                                        events.forEach(eventType => {
                                            const event = new Event(eventType, { bubbles: true, cancelable: true });
                                            inputElement.dispatchEvent(event);
                                        });
                                        
                                        // Wait a moment and check if value persisted
                                        setTimeout(() => {
                                            const currentValue = inputElement.value;
                                            console.log(`Quantity set: ${originalValue} → ${quantity}, Current: ${currentValue}`);
                                            if (currentValue !== quantity) {
                                                console.warn(`Quantity value was reset by website: ${quantity} → ${currentValue}`);
                                                // Try setting again
                                                inputElement.value = quantity;
                                                inputElement.dispatchEvent(new Event('change', { bubbles: true }));
                                            }
                                        }, 500);
                                        
                                        return { success: true, originalValue, setTo: quantity };
                                    }
                                }
                                return { success: false };
                            }
                        """, {'targetIndex': element_index, 'quantity': target_quantity})
                        
                        logger.info(f"Quantity set result: {set_result}")
                        
                        # Additional wait to let any website JavaScript settle
                        await asyncio.sleep(1.0)
                        
                        # Final persistence check
                        final_value = await page.evaluate("""
                            (targetIndex) => {
                                const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                                if (overlay) {
                                    const rect = overlay.getBoundingClientRect();
                                    const centerX = rect.left + (rect.width / 2);
                                    const centerY = rect.top + (rect.height / 2);
                                    const inputElement = document.elementFromPoint(centerX, centerY);
                                    if (inputElement) {
                                        return {
                                            currentValue: inputElement.value,
                                            isVisible: inputElement.offsetParent !== null,
                                            isEnabled: !inputElement.disabled
                                        };
                                    }
                                }
                                return null;
                            }
                        """, element_index)
                        
                        logger.info(f"Final quantity check: {final_value}")
                        
                        # If value was reset, try alternative approach
                        if final_value and final_value['currentValue'] != target_quantity:
                            logger.warning(f"Quantity reset by website, trying alternative approach")
                            await page.evaluate("""
                                (args) => {
                                    const { targetIndex, quantity } = args;
                                    const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                                    if (overlay) {
                                        const rect = overlay.getBoundingClientRect();
                                        const centerX = rect.left + (rect.width / 2);
                                        const centerY = rect.top + (rect.height / 2);
                                        const inputElement = document.elementFromPoint(centerX, centerY);
                                        if (inputElement) {
                                            inputElement.focus();
                                            inputElement.select();
                                            inputElement.value = '';
                                            
                                            for (let char of quantity) {
                                                inputElement.value += char;
                                                inputElement.dispatchEvent(new Event('input', { bubbles: true }));
                                            }
                                            
                                            inputElement.dispatchEvent(new Event('change', { bubbles: true }));
                                            inputElement.blur();
                                        }
                                    }
                                }
                            """, {'targetIndex': element_index, 'quantity': target_quantity})
                    
                elif result['action'] == 'quantity_button':
                    # Use overlay-based element targeting for quantity buttons with viewport scrolling
                    element_index = result.get('elementIndex')
                    
                    # Scroll quantity button into viewport and click
                    await page.evaluate("""
                        (targetIndex) => {
                            const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                            if (overlay) {
                                const rect = overlay.getBoundingClientRect();
                                const centerX = rect.left + (rect.width / 2);
                                const centerY = rect.top + (rect.height / 2);
                                const button = document.elementFromPoint(centerX, centerY);
                                if (button) {
                                    // Check if button is in viewport, scroll if needed
                                    const buttonRect = button.getBoundingClientRect();
                                    const isInViewport = buttonRect.top >= 0 && buttonRect.left >= 0 && 
                                                       buttonRect.bottom <= window.innerHeight && 
                                                       buttonRect.right <= window.innerWidth;
                                    
                                    if (!isInViewport) {
                                        button.scrollIntoView({block: 'center', behavior: 'smooth'});
                                        // Small delay for scroll
                                        setTimeout(() => button.click(), 300);
                                    } else {
                                        button.click();
                                    }
                                    return true;
                                }
                            }
                            return false;
                        }
                    """, element_index)
                    
                elif result['action'] == 'input':
                    # Skip - input action disabled to prevent conflicts with quantity_input
                    pass
                    
                elif result['action'] == 'click':
                    # JavaScript-only click functionality with viewport scrolling
                    element_index = result.get('elementIndex')
                    
                    clicked = False
                    
                    # Enhanced JavaScript click with viewport scrolling and multiple approaches
                    clicked = False
                    if element_index is not None:
                        clicked = await page.evaluate("""
                            (targetIndex) => {
                                const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                                if (!overlay) return false;
                                
                                const rect = overlay.getBoundingClientRect();
                                const centerX = rect.left + (rect.width / 2);
                                const centerY = rect.top + (rect.height / 2);
                                const element = document.elementFromPoint(centerX, centerY);
                                
                                if (!element) return false;
                                
                                // Check if element is in viewport, scroll if needed
                                const elementRect = element.getBoundingClientRect();
                                const isInViewport = elementRect.top >= 0 && elementRect.left >= 0 && 
                                                   elementRect.bottom <= window.innerHeight && 
                                                   elementRect.right <= window.innerWidth;
                                
                                if (!isInViewport) {
                                    element.scrollIntoView({block: 'center', behavior: 'smooth'});
                                    // Wait for scroll animation to complete
                                    return new Promise(resolve => setTimeout(() => {
                                        element.click();
                                        resolve(true);
                                    }, 800));
                                }
                                
                                // Multiple click strategies
                                const strategies = [
                                    // Strategy A0: WooCommerce variation items (li with data-value)
                                    () => {
                                        if (element.tagName === 'LI' && element.getAttribute('data-value') && 
                                            (element.classList.contains('variable-item') || element.classList.contains('color-variable-item'))) {
                                            console.log('WooCommerce variation item detected');
                                            element.scrollIntoView({ block: 'center' });
                                            element.click();
                                            // Also update hidden select if present
                                            const hiddenSelect = element.closest('.woo-variation-items-wrapper')?.querySelector('select[style*="display:none"], select.woo-variation-raw-select');
                                            if (hiddenSelect) {
                                                const dataValue = element.getAttribute('data-value');
                                                hiddenSelect.value = dataValue;
                                                hiddenSelect.dispatchEvent(new Event('change', { bubbles: true }));
                                                console.log('Updated hidden select to:', dataValue);
                                            }
                                            return true;
                                        }
                                        return false;
                                    },
                                    
                                    // Strategy A: Direct click (with type check)
                                    () => { 
                                        if (typeof element.click === 'function') {
                                            element.click(); 
                                            return true;
                                        }
                                        return false;
                                    },
                                    
                                    // Strategy B: Focus then click
                                    () => { 
                                        if (element.focus) element.focus();
                                        if (typeof element.click === 'function') {
                                            element.click();
                                            return true;
                                        }
                                        return false;
                                    },
                                    
                                    // Strategy C: Enhanced mouse events for images
                                    () => {
                                        const rect = element.getBoundingClientRect();
                                        const centerX = rect.left + (rect.width / 2);
                                        const centerY = rect.top + (rect.height / 2);
                                        
                                        // For images, try clicking at the center coordinates
                                        if (element.tagName === 'IMG') {
                                            const clickableParent = document.elementFromPoint(centerX, centerY);
                                            if (clickableParent && clickableParent !== element && typeof clickableParent.click === 'function') {
                                                clickableParent.click();
                                                return true;
                                            }
                                        }
                                        
                                        const events = ['mousedown', 'mouseup', 'click'];
                                        events.forEach(eventType => {
                                            const event = new MouseEvent(eventType, {
                                                bubbles: true,
                                                cancelable: true,
                                                view: window,
                                                clientX: centerX,
                                                clientY: centerY
                                            });
                                            element.dispatchEvent(event);
                                        });
                                        return true;
                                    },
                                    
                                    // Strategy D: For radio/checkbox inputs
                                    () => {
                                        if (element.type === 'radio' || element.type === 'checkbox') {
                                            element.checked = true;
                                            element.dispatchEvent(new Event('change', {bubbles: true}));
                                            return element.checked;
                                        }
                                        return false;
                                    },
                                    
                                    // Strategy E: Enhanced container and input finding
                                    () => {
                                        // For images, look for clickable containers with data attributes
                                        if (element.tagName === 'IMG') {
                                            let container = element.parentElement;
                                            let depth = 0;
                                            while (container && depth < 5) {
                                                // Check for Saks-style selectable containers
                                                if (container.getAttribute('data-testid')?.includes('selectable') ||
                                                    container.classList && container.classList.contains('selectable') ||
                                                    container.classList && container.classList.contains('clickable') ||
                                                    container.getAttribute('role') === 'button') {
                                                    
                                                    if (typeof container.click === 'function') {
                                                        container.click();
                                                        return true;
                                                    }
                                                    
                                                    // Try mouse events on container
                                                    const rect = container.getBoundingClientRect();
                                                    if (rect.width > 0 && rect.height > 0) {
                                                        const centerX = rect.left + (rect.width / 2);
                                                        const centerY = rect.top + (rect.height / 2);
                                                        const event = new MouseEvent('click', {
                                                            bubbles: true,
                                                            cancelable: true,
                                                            view: window,
                                                            clientX: centerX,
                                                            clientY: centerY
                                                        });
                                                        container.dispatchEvent(event);
                                                        return true;
                                                    }
                                                }
                                                container = container.parentElement;
                                                depth++;
                                            }
                                        }
                                        
                                        // Look for radio/checkbox in container
                                        const container = element.closest('.sitg-input-inner-wrapper') || 
                                                        element.closest('[data-testid="sitg-input-inner-wrapper"]') || 
                                                        element.parentElement;
                                        
                                        if (container) {
                                            const input = container.querySelector('input[type="radio"], input[type="checkbox"]');
                                            if (input) {
                                                input.checked = true;
                                                input.dispatchEvent(new Event('change', {bubbles: true}));
                                                return input.checked;
                                            }
                                        }
                                        
                                        // Look for label association
                                        if (element.tagName === 'LABEL' && element.getAttribute('for')) {
                                            const input = document.getElementById(element.getAttribute('for'));
                                            if (input && (input.type === 'radio' || input.type === 'checkbox')) {
                                                input.checked = true;
                                                input.dispatchEvent(new Event('change', {bubbles: true}));
                                                return input.checked;
                                            }
                                        }
                                        
                                        return false;
                                    },
                                    
                                    // Strategy F: Enhanced parent traversal click
                                    () => {
                                        let parent = element.parentElement;
                                        let depth = 0;
                                        while (parent && depth < 8) {  // Increased depth for complex sites
                                            try {
                                                // Check if parent is clickable
                                                const style = window.getComputedStyle(parent);
                                                const isClickable = parent.onclick || 
                                                                   parent.getAttribute('onclick') ||
                                                                   style.cursor === 'pointer' ||
                                                                   parent.classList && parent.classList.contains('clickable') ||
                                                                   parent.classList && parent.classList.contains('selectable') ||
                                                                   parent.hasAttribute('role');
                                                
                                                if (isClickable && typeof parent.click === 'function') {
                                                    parent.click();
                                                    return true;
                                                }
                                                
                                                // For images, also try mouse events on parent
                                                if (element.tagName === 'IMG' && parent.tagName !== 'BODY') {
                                                    const rect = parent.getBoundingClientRect();
                                                    if (rect.width > 0 && rect.height > 0) {
                                                        const centerX = rect.left + (rect.width / 2);
                                                        const centerY = rect.top + (rect.height / 2);
                                                        const event = new MouseEvent('click', {
                                                            bubbles: true,
                                                            cancelable: true,
                                                            view: window,
                                                            clientX: centerX,
                                                            clientY: centerY
                                                        });
                                                        parent.dispatchEvent(event);
                                                        return true;
                                                    }
                                                }
                                            } catch (e) {
                                                // Continue to next parent
                                            }
                                            parent = parent.parentElement;
                                            depth++;
                                        }
                                        return false;
                                    }
                                ];
                                
                                // Try each strategy
                                for (let i = 0; i < strategies.length; i++) {
                                    try {
                                        if (strategies[i]()) {
                                            console.log(`Click strategy ${String.fromCharCode(65 + i)} succeeded`);
                                            return true;
                                        }
                                    } catch (e) {
                                        console.log(`Click strategy ${String.fromCharCode(65 + i)} failed:`, e);
                                    }
                                }
                                
                                return false;
                            }
                        """, element_index)
                        
                        if clicked:
                            logger.info("Enhanced JavaScript click successful")
                            # Extra wait for WooCommerce variation updates
                            await asyncio.sleep(1.5)
                    
                    # Fallback to DOM element click with viewport scrolling
                    if not clicked:
                        clicked = await page.evaluate("""
                            () => {
                                const element = document.querySelector('[data-dom-el]');
                                if (element) {
                                    // Check if element is in viewport, scroll if needed
                                    const rect = element.getBoundingClientRect();
                                    const isInViewport = rect.top >= 0 && rect.left >= 0 && 
                                                       rect.bottom <= window.innerHeight && 
                                                       rect.right <= window.innerWidth;
                                    
                                    if (!isInViewport) {
                                        element.scrollIntoView({block: 'center', behavior: 'smooth'});
                                        // Small delay for smooth scroll
                                        setTimeout(() => {
                                            if (typeof element.click === 'function') {
                                                element.click();
                                            }
                                        }, 300);
                                    } else {
                                        if (typeof element.click === 'function') {
                                            element.click();
                                        }
                                    }
                                    return true;
                                }
                                return false;
                            }
                        """)
                        
                        if clicked:
                            logger.info("DOM element fallback click successful")
                    
                    if not clicked:
                        logger.warning(f"All enhanced click strategies failed for {variant_type}={variant_value}")
                
                await asyncio.sleep(2.0)  # Wait for page update after selection
                
                # Enhanced individual validation after each selection
                validated = await page.evaluate("""
                    (args) => {
                        const { variantType, variantValue } = args;
                        const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                        const normalizedVal = normalize(variantValue);
                        
                        const match = (text) => {
                            if (!text) return false;
                            const t = normalize(text);
                            return t === normalizedVal;
                        };
                        
                        // Strategy 1: Check for checked radio buttons with matching labels
                        const checkedRadios = document.querySelectorAll('input[type="radio"]:checked, input[type="checkbox"]:checked');
                        for (const radio of checkedRadios) {
                            // Check radio value
                            if (match(radio.value)) return true;
                            
                            // Check associated label
                            const label = document.querySelector(`label[for="${radio.id}"]`);
                            if (label) {
                                const labelText = label.querySelector('.sitg-label-text')?.textContent || label.textContent;
                                if (match(labelText)) return true;
                            }
                            
                            // Check aria-label
                            if (match(radio.getAttribute('aria-label'))) return true;
                            
                            // For color swatches, check the alt text of associated images
                            if (variantType === 'color') {
                                const parentSection = radio.closest('section') || radio.parentElement;
                                const img = parentSection?.querySelector('img');
                                if (img && match(img.alt)) return true;
                            }
                        }
                        
                        // Strategy 1.5: Check current selection display (like "Color: heather gray")
                        if (variantType === 'color') {
                            const colorDisplay = document.querySelector('.shown_in__h3-mfe .h3__span');
                            if (colorDisplay && match(colorDisplay.textContent)) {
                                return true;
                            }
                        }
                        

                        
                        // Strategy 3: Check visual selection states (expanded list)
                        const selectionStates = [
                            '.selected', '.active', '.chosen', '.current',
                            '[aria-selected="true"]', '[aria-pressed="true"]', 
                            '[aria-current="true"]', '[data-selected="true"]',
                            '.is-selected', '.is-active', '.is-chosen',
                            '[class*="selected"]', '[class*="active"]'
                        ];
                        
                        for (const selector of selectionStates) {
                            const elements = document.querySelectorAll(selector);
                            for (const el of elements) {
                                // FILTER: For colors, only check elements that are actually selectable color options
                                if (variantType === 'color') {
                                    // Must be within a color/swatch/variant container
                                    const isInColorContainer = el.closest('[class*="color"], [class*="swatch"], [class*="variant"], [data-color], section, form');
                                    if (!isInColorContainer) continue;
                                    
                                    // Must be clickable or a radio/checkbox input
                                    const isClickable = el.tagName === 'BUTTON' || el.tagName === 'A' || el.tagName === 'INPUT' ||
                                                       el.onclick || el.getAttribute('onclick') || el.style.cursor === 'pointer' ||
                                                       el.classList.contains('clickable') || el.classList.contains('selectable') ||
                                                       el.hasAttribute('role');
                                    if (!isClickable) continue;
                                }
                                
                                const texts = [
                                    el.textContent,
                                    el.value,
                                    el.getAttribute('aria-label'),
                                    el.getAttribute('title'),
                                    el.getAttribute('data-value'),
                                    el.getAttribute('alt')
                                ];
                                
                                for (const text of texts) {
                                    if (match(text)) return true;
                                }
                            }
                        }
                        
                        // Strategy 4: Check recently clicked element (marked with data-dom-el) - MUST be in selected state
                        const recentElement = document.querySelector('[data-dom-el]');
                        if (recentElement) {
                            // CRITICAL: Only validate if element is actually in a selected state
                            const isSelected = recentElement.classList.contains('selected') ||
                                             recentElement.classList.contains('active') ||
                                             recentElement.classList.contains('chosen') ||
                                             recentElement.classList.contains('is-selected') ||
                                             recentElement.getAttribute('aria-selected') === 'true' ||
                                             recentElement.getAttribute('aria-pressed') === 'true' ||
                                             recentElement.getAttribute('aria-checked') === 'true' ||
                                             recentElement.getAttribute('aria-current') === 'true' ||
                                             recentElement.disabled === true ||
                                             (recentElement.type === 'radio' && recentElement.checked) ||
                                             (recentElement.type === 'checkbox' && recentElement.checked) ||
                                             (recentElement.tagName === 'BUTTON' && recentElement.name && recentElement.value && recentElement.getAttribute('aria-pressed') === 'true');
                            
                            if (isSelected) {
                                const texts = [
                                    recentElement.textContent,
                                    recentElement.value,
                                    recentElement.getAttribute('aria-label'),
                                    recentElement.getAttribute('title'),
                                    recentElement.getAttribute('data-value'),
                                    recentElement.getAttribute('alt')
                                ];
                                
                                for (const text of texts) {
                                    if (match(text)) return true;
                                }
                            }
                            
                            // Check if recent element is a label pointing to a checked input
                            if (recentElement.tagName === 'LABEL' && recentElement.getAttribute('for')) {
                                const input = document.getElementById(recentElement.getAttribute('for'));
                                if (input && input.checked) {
                                    const inputTexts = [input.value, input.getAttribute('aria-label')];
                                    for (const text of inputTexts) {
                                        if (match(text)) return true;
                                    }
                                }
                            }
                            
                            // Check if recent element contains a checked input
                            const containedInput = recentElement.querySelector('input[type="radio"]:checked, input[type="checkbox"]:checked');
                            if (containedInput) {
                                const inputTexts = [containedInput.value, containedInput.getAttribute('aria-label')];
                                for (const text of inputTexts) {
                                    if (match(text)) return true;
                                }
                            }
                        }
                        
                        // Strategy 5: Check for elements that were just interacted with (look for focus, hover states)
                        const interactedStates = [':focus', ':hover', '.focus', '.hover'];
                        for (const state of interactedStates) {
                            try {
                                const elements = document.querySelectorAll(state);
                                for (const el of elements) {
                                    const texts = [el.textContent, el.value, el.getAttribute('aria-label')];
                                    for (const text of texts) {
                                        if (match(text)) return true;
                                    }
                                }
                            } catch (e) {
                                // Some pseudo-selectors might not work, continue
                            }
                        }
                        
                        // Strategy 6: Quantity validation - Actually validate quantity fields
                        if (variantType === 'quantity') {
                            // Check quantity input fields
                            const quantityInputs = document.querySelectorAll('input[type="number"], input[name*="quantity"], input[id*="quantity"], input[class*="quantity"]');
                            for (const input of quantityInputs) {
                                if (input.value === normalizedVal) {
                                    return true;
                                }
                            }
                            
                            // Check quantity dropdowns
                            const quantitySelects = document.querySelectorAll('select[name*="quantity"], select[id*="quantity"], select[class*="quantity"]');
                            for (const select of quantitySelects) {
                                const selectedOption = select.options[select.selectedIndex];
                                if (selectedOption && (selectedOption.value === normalizedVal || selectedOption.text.trim() === normalizedVal)) {
                                    return true;
                                }
                            }
                            
                            // Check custom quantity dropdowns
                            const customDropdowns = document.querySelectorAll('[class*="quantity"][class*="dropdown"], [class*="qty"][class*="dropdown"]');
                            for (const dropdown of customDropdowns) {
                                const selectedText = dropdown.textContent?.trim();
                                if (selectedText && normalize(selectedText) === normalizedVal) {
                                    return true;
                                }
                            }
                            
                            console.warn(`Quantity validation failed: Expected ${normalizedVal}, but no matching quantity field found`);
                            return false;
                        }
                        
                        // Strategy 7: Fallback - check if any element on page contains the exact text and appears selected
                        const allElements = document.querySelectorAll('*');
                        for (const el of allElements) {
                            if (match(el.textContent)) {
                                // Check if this element or its parent has selection indicators
                                const hasSelectionIndicator = el.classList.contains('selected') ||
                                                             el.classList.contains('active') ||
                                                             el.classList.contains('chosen') ||
                                                             el.getAttribute('aria-selected') === 'true' ||
                                                             el.getAttribute('aria-pressed') === 'true' ||
                                                             (el.parentElement && (
                                                                 el.parentElement.classList.contains('selected') ||
                                                                 el.parentElement.classList.contains('active') ||
                                                                 el.parentElement.getAttribute('aria-selected') === 'true'
                                                             ));
                                
                                if (hasSelectionIndicator) return true;
                            }
                        }
                        
                        // Final strict check: For colors, ensure the current displayed color matches exactly
                        if (variantType === 'color') {
                            const currentColorDisplay = document.querySelector('.shown_in__h3-mfe .h3__span');
                            if (currentColorDisplay) {
                                const displayedColor = normalize(currentColorDisplay.textContent);
                                // Only return true if the displayed color exactly matches what we're looking for
                                return displayedColor === normalizedVal;
                            }
                        }
                        
                        return false;
                    }
                """, {'variantType': variant_type, 'variantValue': variant_value})
                
                if validated:
                    # Mark as selected
                    await page.evaluate("""
                        () => {
                            const el = document.querySelector('[data-dom-el]');
                            if (el) el.setAttribute('data-already-selected', 'true');
                        }
                    """)
                    logger.info(f"VALIDATED: {variant_type}={variant_value} matches current selection (Phase: {result.get('phase', 'unknown')})")
                    return {
                        'success': True,
                        'content': f"VALIDATED: {variant_type}={variant_value} (Phase: {result.get('phase', 'unknown')})",
                        'action': result['action']
                    }
                else:
                    # Only assume success if we actually clicked something  
                    clicked = locals().get('clicked', False)
                    if result['found'] and clicked:
                        # Do a quick re-validation to be sure
                        quick_validation = await page.evaluate("""
                            (args) => {
                                const { variantValue } = args;
                                const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                                const normalizedVal = normalize(variantValue);
                                
                                // Quick check for obvious selection indicators
                                const checkedInputs = document.querySelectorAll('input[type="radio"]:checked, input[type="checkbox"]:checked');
                                for (const input of checkedInputs) {
                                    if (normalize(input.value) === normalizedVal) return true;
                                    const label = document.querySelector(`label[for="${input.id}"]`);
                                    if (label && normalize(label.textContent) === normalizedVal) return true;
                                }
                                
                                // Check for obvious visual selection
                                const selected = document.querySelectorAll('.selected, .active, [aria-selected="true"]');
                                for (const el of selected) {
                                    if (normalize(el.textContent) === normalizedVal) return true;
                                }
                                
                                return false;
                            }
                        """, {'variantValue': variant_value})
                        
                        if quick_validation:
                            logger.info(f"VARIANT SELECTION: VERIFICATION PASSED: {variant_type}={variant_value}")
                            logger.info(f"   Method: Quick validation")
                            logger.info(f"{'='*70}")
                            return {
                                'success': True,
                                'content': f"VALIDATED: {variant_type}={variant_value} (quick validation passed)",
                                'action': result['action']
                            }
                        else:
                            # MANDATORY: Even if click succeeded, verify actual selection before claiming success
                            # But skip verification for action types (buttons that don't select a value)
                            action_types = ['add_to_cart', 'add_to_bag', 'cart', 'bag', 'checkout', 
                                           'view_cart', 'proceed', 'buy', 'purchase', 'order', 'place_order',
                                           'submit', 'continue', 'next', 'confirm']
                            
                            is_action = any(action in variant_type.lower() for action in action_types)
                            
                            if is_action:
                                # For actions (buttons), just confirm click succeeded
                                logger.info(f"VARIANT SELECTION: ACTION COMPLETED: {variant_type}={variant_value}")
                                logger.info(f"{'='*70}")
                                return {
                                    'success': True,
                                    'content': f"SUCCESS: {variant_type}={variant_value} clicked",
                                    'action': result['action']
                                }
                            
                            # For selections (color, size, etc.), verify the actual selected value
                            logger.info(f"VARIANT SELECTION: Verifying selection of {variant_type}={variant_value}...")
                            
                            # Wait for any navigation or page updates
                            await asyncio.sleep(2)
                            
                            # CRITICAL: Extract fresh DOM tree for verification
                            logger.info(f"VARIANT SELECTION: Extracting fresh DOM tree for verification...")
                            verification_debug_file = f'{debug_dir}/dom_{variant_type}_{variant_value}_verification.txt'
                            dom_content_verify = await page.evaluate("""
                                () => {
                                    return document.body.outerHTML;
                                }
                            """)
                            with open(verification_debug_file, 'w') as f:
                                f.write(f"Verification DOM for {variant_type}: {variant_value}\\n" + "=" * 80 + "\\n" + dom_content_verify)
                            logger.info(f"Verification DOM saved to {verification_debug_file}")
                            
                            # Perform strict verification on FRESH DOM
                            try:
                                verification_result = await page.evaluate("""
                                    (args) => {
                                        const { variantType, variantValue } = args;
                                        
                                        // Strict normalization (removes spaces)
                                        const normalizeStrict = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9]/g, '') : '';
                                        
                                        // Fuzzy normalization (keeps spaces, useful for multi-word matches)
                                        const normalizeFuzzy = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '').replace(/\\s+/g, ' ') : '';
                                        
                                        const normalizedTargetStrict = normalizeStrict(variantValue);
                                        const normalizedTargetFuzzy = normalizeFuzzy(variantValue);
                                        
                                        console.log('🔍 VERIFICATION: Checking if', variantType, '=', variantValue, 'is actually selected');
                                        console.log('🔍 Normalized target (strict):', normalizedTargetStrict);
                                        console.log('🔍 Normalized target (fuzzy):', normalizedTargetFuzzy);
                                        
                                        // Helper to check if text matches (tries both strict and fuzzy)
                                        const matches = (text) => {
                                            if (!text) return false;
                                            const textStrict = normalizeStrict(text);
                                            const textFuzzy = normalizeFuzzy(text);
                                            
                                            // Exact match (strict)
                                            if (textStrict === normalizedTargetStrict) return true;
                                            
                                            // Fuzzy match (keeps spaces)
                                            if (textFuzzy === normalizedTargetFuzzy) return true;
                                            
                                            // Contains match (for longer text containing the variant)
                                            if (textStrict.includes(normalizedTargetStrict) || textFuzzy.includes(normalizedTargetFuzzy)) return true;
                                            
                                            return false;
                                        };
                                        
                                        // Check 1: URL parameters (for sites that put variant in URL)
                                        const url = window.location.href;
                                        if (matches(url)) {
                                            console.log('✅ VERIFIED via URL:', variantValue);
                                            return { verified: true, method: 'URL', actualValue: variantValue };
                                        }
                                        
                                        // Check 2: Checked radio buttons
                                        const radios = document.querySelectorAll('input[type="radio"]:checked');
                                        for (const radio of radios) {
                                            // Check radio value
                                            if (matches(radio.value)) {
                                                console.log('✅ VERIFIED via radio value:', radio.value);
                                                return { verified: true, method: 'radio_value', actualValue: radio.value };
                                            }
                                            
                                            // Check label
                                            const label = document.querySelector(`label[for="${radio.id}"]`);
                                            if (label && matches(label.textContent)) {
                                                console.log('✅ VERIFIED via radio label:', label.textContent.trim());
                                                return { verified: true, method: 'radio_label', actualValue: label.textContent.trim() };
                                            }
                                            
                                            // Check aria-label
                                            const ariaLabel = radio.getAttribute('aria-label');
                                            if (ariaLabel && matches(ariaLabel)) {
                                                console.log('✅ VERIFIED via aria-label:', ariaLabel);
                                                return { verified: true, method: 'aria_label', actualValue: ariaLabel };
                                            }
                                            
                                            // Check data attributes
                                            const dataColor = radio.getAttribute('data-color') || radio.getAttribute('data-value');
                                            if (dataColor && matches(dataColor)) {
                                                console.log('✅ VERIFIED via data attribute:', dataColor);
                                                return { verified: true, method: 'data_attribute', actualValue: dataColor };
                                            }
                                        }
                                        
                                        // Check 3: Selected state elements (buttons, divs, etc.)
                                        const selectedSelectors = [
                                            '.selected',
                                            '.active',
                                            '[aria-selected="true"]',
                                            '[aria-pressed="true"]',
                                            '[aria-checked="true"]',
                                            '[aria-current="true"]',
                                            '[data-selected="true"]',
                                            '.is-selected',
                                            '.is-active',
                                            'button[aria-pressed="true"]',
                                            'button.selected',
                                            'button.active',
                                            '[class*="selected"]',
                                            '[class*="active"]',
                                            '[class*="checked"]'
                                        ];
                                        
                                        for (const selector of selectedSelectors) {
                                            const selectedElements = document.querySelectorAll(selector);
                                            for (const el of selectedElements) {
                                                // FILTER: For colors, only check elements in color-related containers
                                                if (variantType === 'color') {
                                                    const colorContainer = el.closest('[class*="color"], [class*="swatch"], [data-color], section');
                                                    if (!colorContainer) continue;
                                                    
                                                    // Skip size/navigation elements
                                                    const ctx = (el.className + ' ' + el.id).toLowerCase();
                                                    if (ctx.includes('size') || ctx.includes('nav') || ctx.includes('menu')) continue;
                                                }
                                                
                                                // Check text content
                                                if (matches(el.textContent)) {
                                                    console.log('✅ VERIFIED via selected element text:', el.textContent.trim(), '(selector:', selector + ')');
                                                    return { verified: true, method: 'selected_element', actualValue: el.textContent.trim() };
                                                }
                                                
                                                // Check aria-label
                                                const ariaLabel = el.getAttribute('aria-label');
                                                if (ariaLabel && matches(ariaLabel)) {
                                                    console.log('✅ VERIFIED via selected element aria-label:', ariaLabel, '(selector:', selector + ')');
                                                    return { verified: true, method: 'selected_aria_label', actualValue: ariaLabel };
                                                }
                                                
                                                // Check title
                                                const title = el.getAttribute('title');
                                                if (title && matches(title)) {
                                                    console.log('✅ VERIFIED via selected element title:', title, '(selector:', selector + ')');
                                                    return { verified: true, method: 'selected_title', actualValue: title };
                                                }
                                                
                                                // Check data attributes (common for color swatches)
                                                const dataAttrs = ['data-name', 'data-color', 'data-value', 'data-shade', 'data-variant'];
                                                for (const attr of dataAttrs) {
                                                    const value = el.getAttribute(attr);
                                                    if (value && matches(value)) {
                                                        console.log('✅ VERIFIED via', attr + ':', value, '(selector:', selector + ')');
                                                        return { verified: true, method: attr, actualValue: value };
                                                    }
                                                }
                                            }
                                        }
                                        
                                        // Check 4: Currently displayed selection (common pattern: "Selected: Cool Brown" or similar)
                                        const displayElements = document.querySelectorAll('[class*="current"], [class*="chosen"], [class*="display"]');
                                        for (const el of displayElements) {
                                            if (matches(el.textContent)) {
                                                console.log('✅ VERIFIED via display element:', el.textContent.trim());
                                                return { verified: true, method: 'display_element', actualValue: el.textContent.trim() };
                                            }
                                        }
                                        
                                        // VERIFICATION FAILED - Collect diagnostic information
                                        const actuallySelected = [];
                                        
                                        // Check all radios
                                        const allRadios = document.querySelectorAll('input[type="radio"]:checked');
                                        allRadios.forEach(radio => {
                                            const label = document.querySelector(`label[for="${radio.id}"]`);
                                            if (label) actuallySelected.push({type: 'radio', value: label.textContent.trim()});
                                            else if (radio.value) actuallySelected.push({type: 'radio', value: radio.value});
                                            else if (radio.getAttribute('aria-label')) actuallySelected.push({type: 'radio', value: radio.getAttribute('aria-label')});
                                        });
                                        
                                        // Check all selected elements
                                        const allSelected = document.querySelectorAll('.selected, .active, [aria-selected="true"], [aria-pressed="true"], [aria-checked="true"], [aria-current="true"]');
                                        allSelected.forEach(el => {
                                            const text = el.textContent?.trim();
                                            const ariaLabel = el.getAttribute('aria-label');
                                            const title = el.getAttribute('title');
                                            const dataColor = el.getAttribute('data-color') || el.getAttribute('data-name');
                                            
                                            if (text && text.length < 100) actuallySelected.push({type: 'selected', value: text});
                                            if (ariaLabel) actuallySelected.push({type: 'aria-label', value: ariaLabel});
                                            if (title) actuallySelected.push({type: 'title', value: title});
                                            if (dataColor) actuallySelected.push({type: 'data-attr', value: dataColor});
                                        });
                                        
                                        console.log('❌ VERIFICATION FAILED');
                                        console.log('Expected:', variantValue);
                                        console.log('Found selected elements:', actuallySelected);
                                        return { verified: false, expected: variantValue, actuallySelected: actuallySelected };
                                    }
                                """, {'variantType': variant_type, 'variantValue': variant_value})
                                
                                if verification_result.get('verified'):
                                    logger.info(f"VARIANT SELECTION: VERIFICATION PASSED: {variant_type}={variant_value}")
                                    logger.info(f"   Method: {verification_result.get('method')}")
                                    logger.info(f"   Actual Value: {verification_result.get('actualValue')}")
                                    logger.info(f"{'='*70}")
                                    return {
                                        'success': True,
                                        'content': f"VERIFIED: {variant_type}={variant_value} (actual value: {verification_result.get('actualValue')})",
                                        'action': result['action']
                                    }
                                else:
                                    logger.error(f"VARIANT SELECTION: VERIFICATION FAILED: {variant_type}={variant_value}")
                                    logger.error(f"   Expected: {variant_value}")
                                    logger.error(f"   Actually Selected: {verification_result.get('actuallySelected')}")
                                    
                                    # Try OCR verification as fallback
                                    ocr_result = await verify_selection_with_ocr(page, variant_type, variant_value, debug_dir)
                                    
                                    if ocr_result.get('verified'):
                                        logger.info(f"VARIANT SELECTION: VERIFICATION PASSED via OCR (fallback)")
                                        logger.info(f"   Method: {ocr_result.get('method')}")
                                        logger.info(f"   Matched Text: {ocr_result.get('matched_text')}")
                                        logger.info(f"{'='*70}")
                                        return {
                                            'success': True,
                                            'content': f"VERIFIED via OCR: {variant_type}={variant_value} (matched: {ocr_result.get('matched_text')})",
                                            'action': result['action']
                                        }
                                    else:
                                        logger.error(f"   OCR verification also failed")
                                        logger.error(f"   Will retry (Attempt {attempt + 1}/3)")
                                        # Don't return success - continue to retry
                                        if attempt < 2:
                                            continue
                                    
                            except Exception as verify_error:
                                logger.warning(f"Verification check failed: {verify_error}")
                                # If verification fails due to error, don't assume success
                                if attempt < 2:
                                    continue
                    
                    if attempt < 2:
                        await asyncio.sleep(1.0)
                        continue
            
            # Only assume success from previous attempts if we have strong evidence
            if result.get('found') and attempt > 1:
                # Final validation check before assuming success
                final_check = await page.evaluate("""
                    (args) => {
                        const { variantValue } = args;
                        const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '') : '';
                        const normalizedVal = normalize(variantValue);
                        
                        // Very strict final check - only return true if we're confident
                        const checkedInputs = document.querySelectorAll('input[type="radio"]:checked, input[type="checkbox"]:checked');
                        for (const input of checkedInputs) {
                            if (normalize(input.value) === normalizedVal) return true;
                            const label = document.querySelector(`label[for="${input.id}"]`);
                            if (label && normalize(label.textContent) === normalizedVal) return true;
                        }
                        return false;
                    }
                """, {'variantValue': variant_value})
                
                if final_check:
                    logger.info(f"FINAL CHECK SUCCESS: {variant_type}={variant_value} is confirmed selected")
                    return {
                        'success': True,
                        'content': f"CONFIRMED: {variant_type}={variant_value} (final validation passed)",
                        'action': result.get('action', 'click')
                    }
                else:
                    logger.warning(f"Final validation failed, retrying {variant_type}={variant_value}")
                    # Continue to next attempt to retry the failed item
            
            logger.warning(f"Attempt {attempt+1}/3: {variant_value} not found")
            if attempt < 2:
                await asyncio.sleep(0.5)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Attempt {attempt+1}/3 failed: {e}")
            
            # If execution context was destroyed, it usually means page navigated (SUCCESS!)
            if "Execution context was destroyed" in error_msg or "navigation" in error_msg.lower():
                logger.info(f"VARIANT SELECTION: Page navigation detected after {variant_type}={variant_value} - treating as success")
                await asyncio.sleep(2)  # Wait for navigation to complete
                return {
                    'success': True,
                    'content': f"SUCCESS: {variant_type}={variant_value} triggered navigation",
                    'action': 'click',
                    'navigated': True
                }
            
            # Check for browser/page closed
            if "Target page, context or browser has been closed" in error_msg or "closed" in error_msg.lower():
                return {
                    'success': False,
                    'content': f"Browser disconnected during {variant_type}={variant_value}",
                    'error': 'Browser disconnected'
                }
            
            if attempt < 2:
                await asyncio.sleep(0.5)
    
    # DISCOVERY PHASE: If direct search failed, try to discover all available options
    # Only use discovery for actual product variants (color, size, etc.), not for navigation
    navigation_types = ['add_to_cart', 'add_to_bag', 'cart', 'bag', 'checkout', 'view_cart', 
                        'proceed', 'buy', 'purchase', 'order', 'place_order']
    
    is_navigation = any(nav in variant_type.lower() for nav in navigation_types)
    
    if not is_navigation:
        logger.info(f"VARIANT SELECTION: DISCOVERY PHASE: Trying to find any {variant_type} options and match with '{variant_value}'...")
    else:
        logger.debug(f"Skipping discovery phase for navigation type: {variant_type}")
        logger.error(f"VARIANT SELECTION: FINAL FAILURE: {variant_type}={variant_value}")
        logger.error(f"   Could not find or interact with element after 3 attempts")
        logger.error(f"{'='*70}")
        return {
            'success': False,
            'content': f"FAILED: Could not find/interact with {variant_type}={variant_value}",
            'error': f"Element not found after 3 attempts"
        }
    
    try:
        discovery_result = await page.evaluate("""
            (args) => {
                const { variantType, variantValue } = args;
                const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9]/g, '') : '';
                const normalizedTarget = normalize(variantValue);
                
                console.log('🔍 DISCOVERY: Looking for', variantType, '=', variantValue);
                console.log('🔍 Normalized target:', normalizedTarget);
                
                // Discover all clickable elements that might be variant options
                const potentialElements = [];
                
                // Strategy 1: Find radio buttons (common for colors/sizes)
                const radios = document.querySelectorAll('input[type="radio"]');
                console.log('📻 Found', radios.length, 'radio buttons');
                
                radios.forEach((radio, index) => {
                    const label = document.querySelector(`label[for="${radio.id}"]`);
                    const labelText = label ? label.textContent?.trim() : '';
                    const value = radio.value;
                    const ariaLabel = radio.getAttribute('aria-label');
                    
                    // Get all possible texts
                    const texts = [value, labelText, ariaLabel].filter(t => t);
                    
                    potentialElements.push({
                        index: index,
                        element: radio,
                        type: 'radio',
                        texts: texts,
                        normalizedTexts: texts.map(t => normalize(t)),
                        id: radio.id,
                        name: radio.name
                    });
                });
                
                // Strategy 2: Find buttons/links that might be variant selectors
                const buttons = document.querySelectorAll('button, a, [role="button"]');
                console.log('🔘 Found', buttons.length, 'buttons/links');
                
                buttons.forEach((btn, index) => {
                    const text = btn.textContent?.trim();
                    const ariaLabel = btn.getAttribute('aria-label');
                    const title = btn.getAttribute('title');
                    const dataValue = btn.getAttribute('data-value');
                    
                    // Priority: text content > aria-label > title > data-value (data-value can be ID)
                    // Only include SHORT texts that are likely user-visible labels (not long descriptions or IDs)
                    const texts = [];
                    
                    // Prioritize actual displayed text
                    if (text && text.length < 30 && text.length > 0) {
                        texts.push({ value: text, priority: 1, source: 'textContent' });
                    }
                    
                    if (ariaLabel && ariaLabel.length < 30) {
                        texts.push({ value: ariaLabel, priority: 2, source: 'aria-label' });
                    }
                    
                    if (title && title.length < 30) {
                        texts.push({ value: title, priority: 3, source: 'title' });
                    }
                    
                    // Only include data-value if it's short and looks like a label (not an ID)
                    // IDs typically are long numbers or alphanumeric strings like "60264341"
                    if (dataValue && dataValue.length < 15 && !/^\\d{5,}$/.test(dataValue)) {
                        texts.push({ value: dataValue, priority: 4, source: 'data-value' });
                    }
                    
                    if (texts.length > 0) {
                        potentialElements.push({
                            index: index,
                            element: btn,
                            type: 'button',
                            texts: texts.map(t => t.value),
                            textPriorities: texts.map(t => t.priority),
                            textSources: texts.map(t => t.source),
                            normalizedTexts: texts.map(t => normalize(t.value)),
                            className: btn.className
                        });
                    }
                });
                
                console.log('📦 Total potential elements:', potentialElements.length);
                
                // Try to match with our target value
                let bestMatch = null;
                let bestMatchScore = 0;
                let bestTextIndex = -1;
                
                for (const item of potentialElements) {
                    for (let i = 0; i < item.normalizedTexts.length; i++) {
                        const normalized = item.normalizedTexts[i];
                        const priority = item.textPriorities ? item.textPriorities[i] : 5;
                        
                        // Exact match - prioritize by text source priority
                        if (normalized === normalizedTarget) {
                            const score = 100 - priority; // Lower priority number = higher score
                            if (score > bestMatchScore) {
                                const source = item.textSources ? item.textSources[i] : 'unknown';
                                console.log('✅ EXACT MATCH:', item.texts[i], '(source:', source, ', priority:', priority, ')');
                                bestMatch = item;
                                bestMatchScore = score;
                                bestTextIndex = i;
                            }
                        }
                        
                        // Partial match (contains) - but with lower score
                        else if ((normalized.includes(normalizedTarget) || normalizedTarget.includes(normalized)) && normalized.length < 20) {
                            const score = 50 - priority;
                            if (score > bestMatchScore) {
                                const source = item.textSources ? item.textSources[i] : 'unknown';
                                console.log('🎯 PARTIAL MATCH:', item.texts[i], '(source:', source, ')');
                                bestMatch = item;
                                bestMatchScore = score;
                                bestTextIndex = i;
                            }
                        }
                    }
                }
                
                if (!bestMatch) {
                    console.log('❌ No matches found in discovery phase');
                    return { found: false, allOptions: potentialElements.slice(0, 20).map(e => e.texts) };
                }
                
                // Log what we matched
                console.log('🎯 Best match found:', bestMatch.texts[bestTextIndex], '(score:', bestMatchScore, ')');
                
                // Try to click the matched element
                console.log('🎯 Attempting to click best match...');
                const element = bestMatch.element;
                
                // Mark for later reference
                element.setAttribute('data-discovery-matched', 'true');
                
                // Scroll into view
                element.scrollIntoView({ block: 'center', behavior: 'smooth' });
                
                // Try click strategies
                let clicked = false;
                
                // Strategy 1: Direct click
                try {
                    element.click();
                    clicked = true;
                    console.log('✅ Direct click succeeded');
                } catch (e) {
                    console.log('❌ Direct click failed:', e.message);
                }
                
                // Strategy 2: For radio buttons, set checked and dispatch change
                if (!clicked && bestMatch.type === 'radio') {
                    try {
                        element.checked = true;
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                        clicked = element.checked;
                        console.log('✅ Radio click succeeded');
                    } catch (e) {
                        console.log('❌ Radio click failed:', e.message);
                    }
                }
                
                // Strategy 3: Mouse events
                if (!clicked) {
                    try {
                        const rect = element.getBoundingClientRect();
                        const events = ['mousedown', 'mouseup', 'click'];
                        events.forEach(eventType => {
                            element.dispatchEvent(new MouseEvent(eventType, {
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: rect.left + rect.width / 2,
                                clientY: rect.top + rect.height / 2
                            }));
                        });
                        clicked = true;
                        console.log('✅ Mouse events dispatched');
                    } catch (e) {
                        console.log('❌ Mouse events failed:', e.message);
                    }
                }
                
                return {
                    found: true,
                    clicked: clicked,
                    matchedText: bestMatch.texts[0],
                    matchScore: bestMatchScore,
                    elementType: bestMatch.type
                };
            }
        """, {'variantType': variant_type, 'variantValue': variant_value})
        
        if discovery_result.get('found') and discovery_result.get('clicked'):
            logger.info(f"VARIANT SELECTION: DISCOVERY SUCCESS: Matched '{discovery_result.get('matchedText')}' (score: {discovery_result.get('matchScore')})")
            await asyncio.sleep(1)
            
            return {
                'success': True,
                'content': f"DISCOVERY: Matched {variant_type}={discovery_result.get('matchedText')} for target '{variant_value}'",
                'action': 'click',
                'phase': 'discovery'
            }
        else:
            logger.warning(f"VARIANT SELECTION: DISCOVERY FAILED: No matching options found")
            if 'allOptions' in discovery_result:
                logger.info(f"Available options: {discovery_result['allOptions'][:10]}")
            
    except Exception as e:
        logger.error(f"Discovery phase error: {e}")
    
    return {
        'success': False,
        'content': f"FAILED: Could not find/interact with {variant_type}={variant_value}",
        'error': f"Element not found after 3 attempts and discovery phase"
    }