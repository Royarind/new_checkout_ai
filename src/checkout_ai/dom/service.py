#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
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
        self.debug_dir = Path(debug_dir)
        self.js_assets_dir = Path(__file__).parent / 'js_assets'
        self.debug_dir.mkdir(parents=True, exist_ok=True)

    def _load_js(self, filename: str) -> str:
        """Load JavaScript content from assets directory."""
        path = self.js_assets_dir / filename
        try:
            return path.read_text(encoding='utf-8')
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
            screenshot_path = self.debug_dir / f'screenshot_{variant_type}_{variant_value}.png'
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            
            image = Image.open(screenshot_path)
            extracted_text = pytesseract.image_to_string(image)
            
            ocr_text_path = self.debug_dir / f'ocr_{variant_type}_{variant_value}.txt'
            ocr_text_path.write_text(extracted_text, encoding='utf-8')
            
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

    def _wrap_js_with_sanitization(self, js_code: str) -> str:
        """Wraps JS code to sanitize return values (remove non-ASCII characters) and inject exclusion helper."""
        # Load exclusion helper
        try:
            exclusion_helper = self._load_js('exclusion_helper.js')
        except FileNotFoundError:
            # Backward compatibility: if exclusion helper doesn't exist, proceed without it
            logger.warning("exclusion_helper.js not found, proceeding without exclusion logic")
            exclusion_helper = "// Exclusion helper not loaded\nfunction isInExcludedSection() { return false; }"
        
        return f"""
        async (args) => {{
            // Inject exclusion helper
            {exclusion_helper}
            
            const originalFunc = {js_code};
            try {{
                let result = originalFunc(args);
                
                // If result is a Promise, await it
                if (result && typeof result.then === 'function') {{
                    result = await result;
                }}
                
                const sanitize = (obj) => {{
                    if (typeof obj === 'string') {{
                        // Replace non-ASCII characters with '?' to prevent UnicodeDecodeError on Windows
                        return obj.replace(/[^\\x00-\\x7F]/g, '?');
                    }}
                    if (Array.isArray(obj)) {{
                        return obj.map(sanitize);
                    }}
                    if (typeof obj === 'object' && obj !== null) {{
                        const newObj = {{}};
                        for (const key in obj) {{
                            newObj[key] = sanitize(obj[key]);
                        }}
                        return newObj;
                    }}
                    return obj;
                }};
                
                return sanitize(result);
            }} catch (e) {{
                return {{ found: false, error: e.toString() }};
            }}
        }}
        """

    async def _detect_product_container(self) -> Optional[str]:
        """Detect the main product container to restrict search scope, excluding recommendation sections."""
        try:
            container = await self.page.evaluate("""
                () => {
                    const hostname = window.location.hostname;
                    
                    // Site-specific selectors (highest priority - for Indian e-commerce)
                    const siteSelectors = {
                        'myntra.com': ['.pdp-main', '.pdp-product-detail', '.pdpContent'],
                        'amazon.in': ['#dp-container', '#ppd', '#rightCol', '#centerCol'],
                        'amazon.com': ['#dp-container', '#ppd', '#rightCol', '#centerCol'],
                        'ajio.com': ['.prod-desc', '.pdp-cont', '.product-content'],
                        'flipkart.com': ['._1YokD2', '._2c7YLP', '.col-8-12'],
                        'bigbasket.com': ['.product-main', '.product-detail'],
                        'swiggy.com': ['.product-container', '.item-details']
                    };
                    
                    // Try site-specific selectors first
                    for (const [site, selectors] of Object.entries(siteSelectors)) {
                        if (hostname.includes(site)) {
                            for (const sel of selectors) {
                                const el = document.querySelector(sel);
                                if (el && el.offsetHeight > 100) {
                                    console.log('[CONTAINER] Using site-specific selector:', sel, 'for', site);
                                    return sel;
                                }
                            }
                        }
                    }
                    
                    // Generic fallback selectors (maintain backward compatibility)
                    const genericSelectors = [
                        '[data-testid="product-container"]',
                        '.product-detail',
                        '.product-main',
                        '#product-main',
                        '.pdp-main',
                        '.product-info-main',
                        'main'
                        // NOTE: Removed 'body' fallback - it was causing selection of elements 
                        // from "related products" sections. Return null instead to trigger
                        // more careful element selection.
                    ];
                    
                    for (const s of genericSelectors) {
                        const el = document.querySelector(s);
                        if (el && el.offsetHeight > 100) {
                            console.log('[CONTAINER] Using generic selector:', s);
                            return s;
                        }
                    }
                    
                    // If no container found, return null (not 'body')
                    // This allows search scripts to work without scope restriction
                    // but they should still apply exclusion logic
                    console.log('[CONTAINER] No specific container found, will search entire page with exclusions');
                    return null;
                }
            """)
            return container
        except Exception as e:
            logger.warning(f"Container detection failed: {e}")
            return None

    async def find_variant(self, variant_type: str, variant_value: str, frame: Optional[Any] = None) -> Dict[str, Any]:
        """Main entry point for finding and selecting a variant. Supports iFrames."""
        target_frame = frame or self.page.main_frame
        logger.info(f"VARIANT SELECTION: SELECTING: {variant_type} = {variant_value} (Frame: {target_frame.name or 'main'})")
        
        # Patagonia handler check (only on main frame)
        if not frame and 'patagonia.com' in self.page.url:
            try:
                from special_sites.patagonia_handler import select_patagonia_variant
                result = await select_patagonia_variant(self.page, variant_type, variant_value)
                if result.get('success'):
                    return result
            except Exception as e:
                logger.warning(f"Patagonia handler failed: {e}, falling back to universal")

        # Special handling for Add to Cart to avoid bad input matches
        if variant_type == 'cart':
             # Try to find a BUTTON or A tag specifically first
             cart_result = await self.page.evaluate("""
                (text) => {
                    const normalize = t => t.toLowerCase().trim();
                    const target = normalize(text);
                    const buttons = document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"]');
                    
                    for (const btn of buttons) {
                        // Skip hidden
                        const style = window.getComputedStyle(btn);
                        if (style.display === 'none' || style.visibility === 'hidden') continue;
                        
                        const t = btn.textContent || btn.value || btn.getAttribute('aria-label') || '';
                        if (normalize(t).includes(target)) {
                            return { found: true, element: { tagName: btn.tagName, text: t }, action: 'click' };
                        }
                    }
                    return { found: false };
                }
             """, variant_value)
             
             if cart_result['found']:
                 pass

        # Detect product container (only on main frame for now, or per frame)
        container_selector = None
        if not frame:
             container_selector = await self._detect_product_container()
             if container_selector:
                 logger.info(f"Search restricted to container: {container_selector}")

        # Helper to run search in a specific frame
        async def search_in_frame(current_frame):
            for attempt in range(3):
                try:
                    if attempt > 0:
                        await asyncio.sleep(2.0)
                    
                    # Phase 1: Overlay Search
                    js_overlay = self._load_js('overlay_search.js')
                    js_overlay_safe = self._wrap_js_with_sanitization(js_overlay)
                    
                    try:
                        result = await current_frame.evaluate(js_overlay_safe, {'val': variant_value, 'containerSelector': container_selector})
                        # Defensive check: ensure result is a dict with 'found' key
                        if not isinstance(result, dict):
                            logger.warning(f"Overlay search returned non-dict: {type(result)}, defaulting to not found")
                            result = {'found': False}
                        elif 'found' not in result:
                            logger.warning(f"Overlay search missing 'found' key: {result.keys()}, defaulting to not found")
                            result = {'found': False}
                    except UnicodeDecodeError as e:
                        logger.warning(f"Unicode error in overlay search (attempt {attempt+1}/3): {e}")
                        if attempt < 2:
                            continue
                        result = {'found': False}
                    
                    if result.get('found', False):
                        logger.info(f"Phase 1 (Overlay): Found {variant_type}={variant_value} in frame {current_frame.name or 'main'}")
                        result['container_selector'] = container_selector
                        return result
                    else:
                        # Phase 2: DOM Tree Search
                        js_dom = self._load_js('dom_tree_search.js')
                        js_dom_safe = self._wrap_js_with_sanitization(js_dom)
                        
                        try:
                            result = await current_frame.evaluate(js_dom_safe, {'variantValue': variant_value, 'containerSelector': container_selector})
                            # Defensive check
                            if not isinstance(result, dict):
                                logger.warning(f"DOM search returned non-dict: {type(result)}, defaulting to not found")
                                result = {'found': False}
                            elif 'found' not in result:
                                logger.warning(f"DOM search missing 'found' key: {result.keys()}, defaulting to not found")
                                result = {'found': False}
                        except UnicodeDecodeError as e:
                            logger.warning(f"Unicode error in DOM search (attempt {attempt+1}/3): {e}")
                            if attempt < 2:
                                continue
                            result = {'found': False}
                        
                        if result.get('found', False):
                            logger.info(f"Phase 2 (DOM Tree): Found {variant_type}={variant_value} in frame {current_frame.name or 'main'}")
                            result['container_selector'] = container_selector
                            return result
                        else:
                            # Phase 3: Pattern Match
                            js_pattern = self._load_js('pattern_match.js')
                            js_pattern_safe = self._wrap_js_with_sanitization(js_pattern)
                            
                            try:
                                result = await current_frame.evaluate(js_pattern_safe, {'variantValue': variant_value, 'containerSelector': container_selector})
                                # Defensive check
                                if not isinstance(result, dict):
                                    logger.warning(f"Pattern match returned non-dict: {type(result)}, defaulting to not found")
                                    result = {'found': False}
                                elif 'found' not in result:
                                    logger.warning(f"Pattern match missing 'found' key: {result.keys()}, defaulting to not found")
                                    result = {'found': False}
                            except UnicodeDecodeError as e:
                                logger.warning(f"Unicode error in pattern match (attempt {attempt+1}/3): {e}")
                                if attempt < 2:
                                    continue
                                result = {'found': False}
                            
                            if result.get('found', False):
                                logger.info(f"Phase 3 (Pattern Match): Found {variant_type}={variant_value} in frame {current_frame.name or 'main'}")
                                element_info = result.get('element', {})
                                logger.info(f"   Element: {element_info.get('tagName')} | Class: {element_info.get('className')} | Text: {element_info.get('text')}")
                                result['container_selector'] = container_selector
                                return result
                except UnicodeDecodeError as e:
                    logger.error(f"Attempt {attempt+1}/3 failed in frame {current_frame.name}: Unicode decode error: {e}")
                    if attempt < 2:
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Attempt {attempt+1}/3 failed in frame {current_frame.name}: {type(e).__name__}: {e}")
                    if attempt < 2:
                        await asyncio.sleep(0.5)
            return {'found': False}

        # 1. Search in the target frame (default: main)
        result = await search_in_frame(target_frame)
        
        # 2. If not found and we started on main frame, search all other frames (iFrames)
        if not result['found'] and not frame:
            logger.info(f"Variant not found in main frame, searching {len(self.page.frames)} iFrames...")
            for child_frame in self.page.frames:
                if child_frame == self.page.main_frame: continue
                
                logger.info(f"Searching iFrame: {child_frame.url}")
                try:
                    result = await search_in_frame(child_frame)
                    if result['found']:
                        # Update target_frame so execution happens in the right place
                        target_frame = child_frame
                        break
                except Exception as e:
                    logger.warning(f"Error searching iFrame {child_frame.url}: {e}")

        if result['found']:
            # Execute action in the correct frame
            action_success = await self._execute_action(result, variant_type, variant_value, frame=target_frame)
            if action_success:
                # Verification
                verified = await self._verify_selection(variant_type, variant_value, frame=target_frame)
                if verified['success']:
                    return verified
                
                # If verification failed, try OCR (only works on main page screenshot usually)
                # DISABLED: OCR causes false positives for selection verification.
                # ocr_result = await self.verify_selection_with_ocr(variant_type, variant_value)
                # if ocr_result['verified']:
                #     return {
                #         'success': True,
                #         'content': f"VERIFIED via OCR: {variant_type}={variant_value}",
                #         'action': result['action']
                #     }
        
        # Discovery Phase (only on main frame for now)
        if not frame:
             return await self._discovery_phase(variant_type, variant_value)
        
        return {'success': False}

    async def _execute_action(self, result: Dict[str, Any], variant_type: str, variant_value: str, frame: Optional[Any] = None) -> bool:
        """Execute the action identified by the search phase."""
        target_frame = frame or self.page
        action = result['action']
        element_index = result.get('elementIndex')
        
        try:
            if action == 'select':
                if element_index is not None:
                    await target_frame.evaluate("""
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
                    await target_frame.select_option('[data-dom-el]', result.get('value'))
                return True

            elif action == 'dropdown':
                js_dropdown = self._load_js('action_dropdown.js')
                full_script = js_dropdown + f"\\nreturn clickDropdown({element_index});"
                dropdown_clicked = await target_frame.evaluate(f"(async () => {{ {full_script} }})()")
                
                if dropdown_clicked.get('success'):
                    await asyncio.sleep(1.5)
                    select_script = js_dropdown + f"\\nreturn selectOption('{result.get('searchValue', variant_value)}');"
                    clicked = await target_frame.evaluate(f"(() => {{ {select_script} }})()")
                    return True
                return False

            elif action == 'quantity_dropdown':
                js_qty = self._load_js('action_quantity.js')
                script = js_qty + f"\\nreturn handleQuantityDropdown({{targetIndex: {element_index}, quantity: '{variant_value}'}});"
                result = await target_frame.evaluate(f"(async () => {{ {script} }})()")
                
                if result.get('success') and result.get('needsOption'):
                    await asyncio.sleep(1.5)
                    opt_script = js_qty + f"\\nreturn selectQuantityOption('{variant_value}');"
                    await target_frame.evaluate(f"(async () => {{ {opt_script} }})()")
                return True

            elif action == 'quantity_input':
                js_qty = self._load_js('action_quantity.js')
                script = js_qty + f"\\nreturn handleQuantityInput({{targetIndex: {element_index}, quantity: '{variant_value}'}});"
                await target_frame.evaluate(f"(async () => {{ {script} }})()")
                return True



            elif action == 'click' or action == 'quantity_button':
                return await self._safe_scroll_and_click(target_frame, element_index)

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False
        
        return False

    async def _safe_scroll_and_click(self, frame: Any, element_index: int) -> bool:
        """
        Implements the 'Scan, Plan, Act' logic:
        1. Inspect element state (Scan)
        2. Calculate safe scroll if needed (Plan)
        3. Click using coordinates (Act)
        """
        try:
            js_inspect = self._load_js('inspect_element.js')
            
            # 1. Scan & Plan Loop (max 3 attempts to stabilize)
            for attempt in range(3):
                info = await frame.evaluate(js_inspect, {'targetIndex': element_index})
                
                if not info.get('found'):
                    logger.warning("Safe Click: Element not found during inspection")
                    return False
                
                # Check visibility
                if not info['isVisible']:
                    logger.info(f"Safe Click: Element off-screen (y={info['rect']['y']}), calculating safe scroll...")
                    
                    # Calculate delta to bring to center
                    viewport_height = info['window']['innerHeight']
                    element_y = info['rect']['y']
                    element_height = info['rect']['height']
                    
                    # Target y is center of viewport
                    target_y_in_viewport = viewport_height / 2
                    current_y_center = element_y + (element_height / 2)
                    
                    delta_y = current_y_center - target_y_in_viewport
                    
                    # Execute scroll
                    await frame.evaluate(f"window.scrollBy({{top: {delta_y}, behavior: 'smooth'}})")
                    
                    # Wait for scroll to settle
                    await asyncio.sleep(1.2)
                    
                    # CRITICAL: Re-inspect to get NEW coordinates after scroll
                    logger.info("Safe Click: Re-inspecting after scroll to get updated coordinates")
                    continue # This will re-run the inspect at the top of the loop
                
                # Check enabled state
                if not info['isEnabled']:
                    logger.warning("Safe Click: Element is disabled or not interactive")
                    # We might want to wait here or just try anyway if it's a false negative
                    # For now, let's log and proceed with caution
                
                # Check obscuration
                if info['isObscured']:
                    logger.warning("Safe Click: Element appears to be obscured by another element")
                    # Attempt to scroll slightly to clear it?
                    await frame.evaluate("window.scrollBy({top: 50, behavior: 'smooth'})")
                    await asyncio.sleep(0.5)
                    continue

                # 2. Act: Coordinate-based click
                # At this point, element is visible and coordinates are fresh
                center_x = info['center']['x']
                center_y = info['center']['y']
                
                logger.info(f"Safe Click: Element is visible and ready at ({center_x}, {center_y})")
                
                # Use Playwright's mouse API for precise interaction
                page = frame.page if hasattr(frame, 'page') else frame
                
                if frame == page or frame == page.main_frame:
                    logger.info(f"Safe Click: Using mouse.click at ({center_x}, {center_y})")
                    await page.mouse.click(center_x, center_y)
                else:
                    # For iframes, fall back to JS click
                    logger.info("Safe Click: Inside iframe, falling back to JS click for safety")
                    js_click = self._load_js('action_click.js')
                    await frame.evaluate(js_click, element_index)
                
                await asyncio.sleep(0.5)
                return True
            
            logger.error("Safe Click: Failed to stabilize element after 3 attempts")
            return False

        except Exception as e:
            logger.error(f"Safe Click Error: {e}")
            # Fallback to old method
            js_click = self._load_js('action_click.js')
            return await frame.evaluate(js_click, element_index)

    async def _verify_selection(self, variant_type: str, variant_value: str, frame: Optional[Any] = None) -> Dict[str, Any]:
        """Verify the selection."""
        target_frame = frame or self.page
        js_verify = self._load_js('verification.js')
        result = await target_frame.evaluate(js_verify, {'variantType': variant_type, 'variantValue': variant_value})
        
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