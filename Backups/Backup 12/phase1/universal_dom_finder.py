#!/usr/bin/env python3

import os
import asyncio
import logging
from typing import Dict, Any, Optional
from playwright.async_api import Page

# Optional OCR imports
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.getLogger(__name__).warning("pytesseract not installed. OCR verification disabled. Install with: pip install pytesseract")

logger = logging.getLogger(__name__)

class UniversalDOMFinder:
    def __init__(self, page: Page, debug_dir: str = '/Users/abcom/Documents/Checkout_ai/variant_debug'):
        self.page = page
        self.debug_dir = debug_dir
        self.js_assets_dir = os.path.join(os.path.dirname(__file__), 'js_assets')
        os.makedirs(self.debug_dir, exist_ok=True)

    def _load_js(self, filename: str) -> str:
        """Load JavaScript content from assets directory."""
        path = os.path.join(self.js_assets_dir, filename)
        try:
            with open(path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"JavaScript asset not found: {filename}")
            raise

    async def verify_selection_with_ocr(self, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Verify variant selection using OCR."""
        if not OCR_AVAILABLE:
            return {
                'verified': False,
                'matched_text': None,
                'method': 'OCR unavailable - pytesseract not installed'
            }
        
        try:
            logger.info(f"VARIANT SELECTION: Trying OCR verification as fallback...")
            screenshot_path = f'{self.debug_dir}/screenshot_{variant_type}_{variant_value}.png'
            await self.page.screenshot(path=screenshot_path, full_page=True)
            
            image = Image.open(screenshot_path)
            extracted_text = pytesseract.image_to_string(image)
            
            ocr_text_path = f'{self.debug_dir}/ocr_{variant_type}_{variant_value}.txt'
            with open(ocr_text_path, 'w', encoding='utf-8') as f:
                f.write(extracted_text)
            
            # Normalization helpers
            def normalize_strict(text):
                return ''.join(c.lower() for c in text if c.isalnum())
            
            def normalize_fuzzy(text):
                return ''.join(c.lower() if c.isalnum() or c.isspace() else ' ' for c in text).strip()
            
            normalized_value_strict = normalize_strict(variant_value)
            normalized_value_fuzzy = normalize_fuzzy(variant_value)
            normalized_extracted_strict = normalize_strict(extracted_text)
            normalized_extracted_fuzzy = normalize_fuzzy(extracted_text)
            
            verified = False
            matched_text = None
            method = None
            
            if normalized_value_strict in normalized_extracted_strict:
                verified = True
                method = "OCR strict match"
                for line in extracted_text.split('\n'):
                    if normalize_strict(line) and normalized_value_strict in normalize_strict(line):
                        matched_text = line.strip()
                        break
            elif normalized_value_fuzzy in normalized_extracted_fuzzy:
                verified = True
                method = "OCR fuzzy match"
                for line in extracted_text.split('\n'):
                    if normalize_fuzzy(line) and normalized_value_fuzzy in normalize_fuzzy(line):
                        matched_text = line.strip()
                        break
            else:
                words = normalized_value_fuzzy.split()
                all_words_found = all(word in normalized_extracted_fuzzy for word in words if len(word) > 2)
                if all_words_found and len(words) > 0:
                    verified = True
                    method = "OCR word match"
                    matched_text = variant_value
            
            if verified:
                logger.info(f"VARIANT SELECTION: VERIFICATION PASSED via OCR ({method})")
                return {'verified': True, 'matched_text': matched_text or variant_value, 'method': method}
            else:
                return {'verified': False, 'matched_text': None, 'method': 'OCR failed'}
                
        except Exception as e:
            logger.error(f"VARIANT SELECTION: OCR verification error: {e}")
            return {'verified': False, 'matched_text': None, 'method': f'OCR error: {str(e)}'}

    async def _detect_product_container(self) -> Optional[str]:
        """Detect the main product container to restrict search scope."""
        try:
            container = await self.page.evaluate("""
                () => {
                    // Common product container selectors
                    const selectors = [
                        '[data-testid="product-container"]',
                        '.product-detail',
                        '.product-main',
                        '#product-main',
                        '.pdp-main',
                        '.product-info-main',
                        'main',
                        'body' // Fallback
                    ];
                    
                    for (const s of selectors) {
                        const el = document.querySelector(s);
                        if (el && el.offsetHeight > 100) { // Ensure it's visible/substantial
                            return s;
                        }
                    }
                    return null;
                }
            """)
            return container
        except Exception as e:
            logger.warning(f"Container detection failed: {e}")
            return None

    async def find_variant(self, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Main entry point for finding and selecting a variant."""
        logger.info(f"VARIANT SELECTION: SELECTING: {variant_type} = {variant_value}")
        
        # Patagonia handler check
        if 'patagonia.com' in self.page.url:
            try:
                from special_sites.patagonia_handler import select_patagonia_variant
                result = await select_patagonia_variant(self.page, variant_type, variant_value)
                if result.get('success'):
                    return result
            except Exception as e:
                logger.warning(f"Patagonia handler failed: {e}, falling back to universal")

        # Detect product container
        container_selector = await self._detect_product_container()
        logger.info(f"Search restricted to container: {container_selector}")

        for attempt in range(3):
            try:
                if attempt > 0:
                    await asyncio.sleep(2.0)
                
                # Phase 1: Overlay Search
                js_overlay = self._load_js('overlay_search.js')
                # Pass containerSelector to JS
                result = await self.page.evaluate(js_overlay, {'val': variant_value, 'containerSelector': container_selector})
                
                if result['found']:
                    logger.info(f"Phase 1 (Overlay): Found {variant_type}={variant_value}")
                else:
                    # Phase 2: DOM Tree Search
                    js_dom = self._load_js('dom_tree_search.js')
                    # TODO: Update dom_tree_search.js to accept containerSelector if needed, 
                    # but it currently has its own list. For now, we leave it as is or update it later.
                    result = await self.page.evaluate(js_dom, variant_value)
                    
                    if result['found']:
                        logger.info(f"Phase 2 (DOM Tree): Found {variant_type}={variant_value}")
                    else:
                        # Phase 3: Pattern Match
                        js_pattern = self._load_js('pattern_match.js')
                        result = await self.page.evaluate(js_pattern, variant_value)
                        
                        if result['found']:
                            logger.info(f"Phase 3 (Pattern Match): Found {variant_type}={variant_value}")
                        else:
                            pass

                if result['found']:
                    action_success = await self._execute_action(result, variant_type, variant_value)
                    if action_success:
                        # Verification
                        verified = await self._verify_selection(variant_type, variant_value)
                        if verified['success']:
                            return verified
                        
                        # If verification failed, try OCR
                        ocr_result = await self.verify_selection_with_ocr(variant_type, variant_value)
                        if ocr_result['verified']:
                            return {
                                'success': True,
                                'content': f"VERIFIED via OCR: {variant_type}={variant_value}",
                                'action': result['action']
                            }
            
            except Exception as e:
                logger.error(f"Attempt {attempt+1}/3 failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(0.5)

        # Discovery Phase
        return await self._discovery_phase(variant_type, variant_value)

    async def _execute_action(self, result: Dict[str, Any], variant_type: str, variant_value: str) -> bool:
        """Execute the action identified by the search phase."""
        action = result['action']
        element_index = result.get('elementIndex')
        
        try:
            if action == 'select':
                if element_index is not None:
                    await self.page.evaluate("""
                        (args) => {
                            const { targetIndex, value } = args;
                            const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
                            if (overlay) {
                                const rect = overlay.getBoundingClientRect();
                                const el = document.elementFromPoint(rect.left + rect.width/2, rect.top + rect.height/2);
                                if (el && el.tagName === 'SELECT') {
                                    el.value = value;
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            }
                        }
                    """, {'targetIndex': element_index, 'value': result.get('value')})
                else:
                    await self.page.select_option('[data-dom-el]', result.get('value'))
                return True

            elif action == 'dropdown':
                js_dropdown = self._load_js('action_dropdown.js')
                # We need to combine the helper functions with the execution logic
                # Since page.evaluate takes a function body or string, we'll pass the whole file content
                # but we need to invoke the specific function.
                # A better way for complex JS files is to define functions in window or just execute inline.
                # For now, let's assume the JS file returns a function or executes immediately.
                # The extracted JS files currently are just function definitions or blocks.
                # Let's adjust the strategy: Inject the helper functions first, then call them.
                
                # Inject helpers
                await self.page.evaluate(js_dropdown) # This defines clickDropdown and selectOption in local scope if wrapped, 
                                                      # but we need them available. 
                                                      # Actually, the file content I wrote earlier has them as function declarations.
                                                      # If I eval it, they might not persist if not attached to window.
                                                      # Let's wrap them in a block that executes immediately.
                
                # For simplicity in this refactor step, I will inline the logic or use a slightly different approach.
                # I'll read the file and wrap it in an IIFE that returns the result.
                
                full_script = js_dropdown + f"\nreturn clickDropdown({element_index});"
                dropdown_clicked = await self.page.evaluate(f"(async () => {{ {full_script} }})()")
                
                if dropdown_clicked.get('success'):
                    await asyncio.sleep(1.5)
                    # Select option
                    select_script = js_dropdown + f"\nreturn selectOption('{result.get('searchValue', variant_value)}');"
                    clicked = await self.page.evaluate(f"(() => {{ {select_script} }})()")
                    if not clicked:
                         # Fallback force click
                         pass
                    return True
                return False

            elif action == 'quantity_dropdown':
                js_qty = self._load_js('action_quantity.js')
                # Inject and call handleQuantityDropdown
                script = js_qty + f"\nreturn handleQuantityDropdown({{targetIndex: {element_index}, quantity: '{variant_value}'}});"
                result = await self.page.evaluate(f"(async () => {{ {script} }})()")
                
                if result.get('success') and result.get('needsOption'):
                    await asyncio.sleep(1.5)
                    # Select option
                    opt_script = js_qty + f"\nreturn selectQuantityOption('{variant_value}');"
                    await self.page.evaluate(f"(async () => {{ {opt_script} }})()")
                return True

            elif action == 'quantity_input':
                js_qty = self._load_js('action_quantity.js')
                script = js_qty + f"\nreturn handleQuantityInput({{targetIndex: {element_index}, quantity: '{variant_value}'}});"
                await self.page.evaluate(f"(async () => {{ {script} }})()")
                return True

            elif action == 'click' or action == 'quantity_button':
                js_click = self._load_js('action_click.js')
                # The file content is an arrow function `(targetIndex) => { ... }`
                # So we can pass it directly to evaluate
                await self.page.evaluate(js_click, element_index)
                return True

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False
        
        return False

    async def _verify_selection(self, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Verify the selection."""
        js_verify = self._load_js('verification.js')
        result = await self.page.evaluate(js_verify, {'variantType': variant_type, 'variantValue': variant_value})
        
        if result.get('verified'):
            return {
                'success': True,
                'content': f"VERIFIED: {variant_type}={variant_value}",
                'action': 'verified'
            }
        return {'success': False}

    async def _discovery_phase(self, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Try to discover options if direct search failed."""
        navigation_types = ['add_to_cart', 'checkout', 'buy', 'purchase']
        if any(nav in variant_type.lower() for nav in navigation_types):
            return {'success': False, 'error': 'Navigation element not found'}

        js_discovery = self._load_js('discovery.js')
        result = await self.page.evaluate(js_discovery, {'variantType': variant_type, 'variantValue': variant_value})
        
        if result.get('found') and result.get('clicked'):
            return {
                'success': True,
                'content': f"DISCOVERY: Matched {variant_type}={variant_value}",
                'action': 'discovery'
            }
        
        return {'success': False, 'error': 'Discovery failed'}

# Backward compatibility wrapper
async def find_variant_dom(page: Page, variant_type: str, variant_value: str) -> Dict[str, Any]:
    finder = UniversalDOMFinder(page)
    return await finder.find_variant(variant_type, variant_value)

async def verify_selection_with_ocr(page: Page, variant_type: str, variant_value: str, debug_dir: str) -> Dict[str, Any]:
    finder = UniversalDOMFinder(page, debug_dir)
    return await finder.verify_selection_with_ocr(variant_type, variant_value)