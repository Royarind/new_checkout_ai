"""
Checkout DOM Finder - Phase 2
Fresh DOM finder specifically for checkout flow elements
Handles buttons, form inputs, and dropdowns
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def normalize_text(text):
    """Normalize text for comparison"""
    if not text:
        return ""
    return text.lower().strip().replace('-', '').replace('_', '').replace(' ', '')


async def find_and_click_button(page, keywords, max_retries=3):
    """
    Find and click button by keyword matching with scoring system
    Returns: {'success': bool, 'matched_text': str, 'error': str}
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Attempt {attempt + 1}/{max_retries} - Finding button with keywords: {keywords[:3]}...")
            
            result = await page.evaluate("""
                (keywords) => {
                    function normalize(text) {
                        if (!text) return '';
                        return text.toLowerCase().trim().replace(/[-_\\s]/g, '');
                    }
                    
                    const elements = document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"], div[onclick], span[onclick]');
                    let bestMatch = null;
                    let bestScore = 0;
                    
                    elements.forEach(el => {
                        if (!el.offsetParent) return;
                        
                        const text = el.textContent?.trim() || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const value = el.getAttribute('value') || '';
                        const title = el.getAttribute('title') || '';
                        const className = el.className || '';
                        const id = el.id || '';
                        
                        const allText = [text, ariaLabel, value, title, className, id].join(' ');
                        const normalized = normalize(allText);
                        
                        if (text.length > 100) return;
                        
                        let score = 0;
                        keywords.forEach(keyword => {
                            const normKeyword = normalize(keyword);
                            if (normalized === normKeyword) {
                                score += 100;
                            } else if (normalized.includes(normKeyword)) {
                                score += 50;
                            } else if (normKeyword.includes(normalized) && normalized.length > 3) {
                                score += 30;
                            }
                        });
                        
                        if (score > bestScore) {
                            bestScore = score;
                            bestMatch = { element: el, text: text || ariaLabel || value, score: score };
                        }
                    });
                    
                    if (!bestMatch || bestScore === 0) {
                        return { found: false };
                    }
                    
                    const element = bestMatch.element;
                    element.scrollIntoView({ block: 'center', behavior: 'smooth' });
                    
                    let clicked = false;
                    let currentElement = element;
                    
                    for (let level = 0; level < 3 && !clicked; level++) {
                        if (!currentElement) break;
                        
                        try {
                            currentElement.click();
                            clicked = true;
                            break;
                        } catch (e) {
                            try {
                                const rect = currentElement.getBoundingClientRect();
                                ['mousedown', 'mouseup', 'click'].forEach(eventType => {
                                    currentElement.dispatchEvent(new MouseEvent(eventType, {
                                        bubbles: true,
                                        cancelable: true,
                                        view: window,
                                        clientX: rect.left + rect.width / 2,
                                        clientY: rect.top + rect.height / 2
                                    }));
                                });
                                clicked = true;
                                break;
                            } catch (e2) {}
                        }
                        
                        currentElement = currentElement.parentElement;
                    }
                    
                    return {
                        found: true,
                        clicked: clicked,
                        matchedText: bestMatch.text,
                        score: bestScore
                    };
                }
            """, keywords)
            
            if result.get('found') and result.get('clicked'):
                logger.info(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Button clicked: '{result.get('matchedText')}' (score: {result.get('score')})")
                await asyncio.sleep(1)
                return {'success': True, 'matched_text': result.get('matchedText')}
            
            if result.get('found'):
                logger.warning(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Button found but click failed: '{result.get('matchedText')}'")
            
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Button click attempt {attempt + 1} failed: {e}")
    
    return {'success': False, 'error': 'Button not found after retries'}


async def find_input_by_label(page, label_keywords):
    """
    Find input field by associated label text with strict matching
    Returns: element handle or None
    """
    try:
        logger.info(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Finding input for labels: {label_keywords[:3]}...")
        
        import random
        marker = f"found-{random.randint(100000, 999999)}"
        
        result = await page.evaluate("""
            (args) => {
                const { keywords, marker } = args;
                
                function normalize(text) {
                    if (!text) return '';
                    return text.toLowerCase().trim().replace(/[-_\\s]/g, '');
                }
                
                const fields = Array.from(document.querySelectorAll('input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]), select, textarea'));
                const visibleFields = fields.filter(f => f.offsetParent).sort((a, b) => {
                    const rectA = a.getBoundingClientRect();
                    const rectB = b.getBoundingClientRect();
                    return rectA.top - rectB.top;
                });
                
                for (const keyword of keywords) {
                    const normKeyword = normalize(keyword);
                    
                    for (const field of visibleFields) {
                        const label = field.closest('label') || document.querySelector(`label[for="${field.id}"]`);
                        const labelText = normalize(label?.textContent || '');
                        const fieldName = normalize(field.name || '');
                        const fieldId = normalize(field.id || '');
                        const placeholder = normalize(field.placeholder || '');
                        const autocomplete = normalize(field.autocomplete || '');
                        const ariaLabel = normalize(field.getAttribute('aria-label') || '');
                        
                        let matched = false;
                        let matchMethod = '';
                        
                        if (labelText === normKeyword || labelText.startsWith(normKeyword)) {
                            matched = true;
                            matchMethod = 'label';
                        } else if (fieldName === normKeyword || fieldName.startsWith(normKeyword)) {
                            matched = true;
                            matchMethod = 'name';
                        } else if (fieldId === normKeyword || fieldId.startsWith(normKeyword)) {
                            matched = true;
                            matchMethod = 'id';
                        } else if (autocomplete === normKeyword || autocomplete.includes(normKeyword)) {
                            matched = true;
                            matchMethod = 'autocomplete';
                        } else if (placeholder.includes(normKeyword)) {
                            matched = true;
                            matchMethod = 'placeholder';
                        } else if (ariaLabel.includes(normKeyword)) {
                            matched = true;
                            matchMethod = 'aria';
                        }
                        
                        if (matched) {
                            if (normKeyword.includes('name') && !normKeyword.includes('address')) {
                                if (fieldName.includes('address') || fieldId.includes('address') || labelText.includes('address') || fieldName.includes('street') || fieldId.includes('street')) {
                                    continue;
                                }
                            }
                            if (normKeyword.includes('address') || normKeyword.includes('street')) {
                                if ((fieldName.includes('name') && !fieldName.includes('address')) || (fieldId.includes('name') && !fieldId.includes('address'))) {
                                    continue;
                                }
                            }
                            
                            // Strict filtering for first/last name to prevent same field reuse
                            if (normKeyword.includes('firstname') || normKeyword.includes('givenname')) {
                                if (fieldName.includes('last') || fieldId.includes('last') || labelText.includes('last') || fieldName.includes('surname') || fieldId.includes('surname')) {
                                    continue;
                                }
                            }
                            if (normKeyword.includes('lastname') || normKeyword.includes('surname')) {
                                if (fieldName.includes('first') || fieldId.includes('first') || labelText.includes('first') || fieldName.includes('given') || fieldId.includes('given')) {
                                    continue;
                                }
                            }
                            
                            field.setAttribute('data-checkout-marker', marker);
                            return { found: true, marker: marker, method: matchMethod };
                        }
                    }
                }
                
                return { found: false };
            }
        """, {'keywords': label_keywords, 'marker': marker})
        
        if result.get('found'):
            element = await page.query_selector(f"[data-checkout-marker='{result['marker']}']")
            if element:
                field_info = await element.evaluate('el => ({ name: el.name, id: el.id })')
                # Don't mark as used - allow reuse after page navigation
                # await page.evaluate("(marker) => { document.querySelector(`[data-checkout-marker='${marker}']`).setAttribute('data-checkout-used', 'true'); }", result['marker'])
                logger.info(f"CHECKOUT DOM: MATCHED '{label_keywords[0]}' by {result['method']} -> name='{field_info['name']}' id='{field_info['id']}'")
                return element
        
        logger.error(f"CHECKOUT DOM: NOT FOUND - Keywords: {label_keywords}")
        return None
        
    except Exception as e:
        logger.error(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Error finding input: {e}")
        return None


async def fill_input_field(page, label_keywords, value, max_retries=3):
    """
    Find and fill input field with retry, validation, and autocomplete handling
    Returns: {'success': bool, 'error': str}
    """
    for attempt in range(max_retries):
        try:
            # Wait for page to stabilize before searching
            await page.wait_for_load_state('domcontentloaded', timeout=3000)
            await asyncio.sleep(1)
            
            element = await find_input_by_label(page, label_keywords)
            if not element:
                if attempt < max_retries - 1:
                    logger.info(f"CHECKOUT DOM: Field not found, waiting for lazy load ({attempt + 1}/{max_retries})...")
                    await asyncio.sleep(3)
                    continue
                return {'success': False, 'error': f'Input field not found for {label_keywords[0]}'}
            
            # Re-query element immediately before interaction to avoid stale reference
            is_attached = await element.evaluate('el => el.isConnected')
            if not is_attached:
                logger.warning(f"CHECKOUT DOM: Element detached, re-querying...")
                await asyncio.sleep(1)
                element = await find_input_by_label(page, label_keywords)
                if not element:
                    continue
            
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)
            await element.click()
            await asyncio.sleep(0.3)
            
            # Clear and fill with error recovery
            try:
                await element.fill('')
                await asyncio.sleep(0.2)
                await element.fill(value)
                await asyncio.sleep(0.3)
            except Exception as fill_error:
                if 'not attached' in str(fill_error).lower():
                    logger.warning(f"CHECKOUT DOM: Element detached during fill, retrying...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                        continue
                raise
            
            # Trigger autocomplete/validation events
            await element.evaluate('el => { el.dispatchEvent(new Event("input", {bubbles: true})); el.dispatchEvent(new Event("change", {bubbles: true})); el.dispatchEvent(new Event("blur", {bubbles: true})); }')
            await asyncio.sleep(0.5)
            
            # Check for autocomplete dropdown
            has_autocomplete = await page.evaluate("""
                () => {
                    const dropdowns = document.querySelectorAll('[role="listbox"], [class*="autocomplete"], [class*="suggestion"]');
                    return Array.from(dropdowns).some(d => d.offsetParent);
                }
            """)
            
            if has_autocomplete:
                logger.info(f"CHECKOUT DOM: Autocomplete detected, waiting for options...")
                await asyncio.sleep(1)
                # Press Enter or Arrow Down to select first option
                await element.press('ArrowDown')
                await asyncio.sleep(0.3)
                await element.press('Enter')
                await asyncio.sleep(0.5)
            
            # Verify value (case-insensitive)
            filled_value = await element.input_value()
            if filled_value.lower() == value.lower() or filled_value.lower().startswith(value[:5].lower()):
                logger.info(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Filled '{label_keywords[0]}' (verified)")
                return {'success': True}
            else:
                logger.warning(f"CHECKOUT DOM: Value mismatch: expected '{value}', got '{filled_value}'")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
            
            return {'success': True}
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"CHECKOUT DOM: Error filling (attempt {attempt + 1}): {error_msg}")
            
            # If element detached, wait longer for page to stabilize
            if 'not attached' in error_msg.lower() or 'detached' in error_msg.lower():
                if attempt < max_retries - 1:
                    logger.info(f"CHECKOUT DOM: Waiting for page to stabilize (3s)...")
                    await asyncio.sleep(3)
                    continue
            elif attempt < max_retries - 1:
                await asyncio.sleep(2)
            else:
                return {'success': False, 'error': error_msg}
    
    return {'success': False, 'error': 'Max retries exceeded'}


async def find_and_select_dropdown(page, label_keywords, option_value):
    """
    Find and select dropdown option (handles both native SELECT and custom dropdowns)
    Returns: {'success': bool, 'error': str}
    """
    try:
        logger.info(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Finding dropdown for: {label_keywords[0]} = {option_value}")
        
        # Try all SELECT elements on page
        try:
            all_selects = await page.query_selector_all('select')
            for select in all_selects:
                options = await select.query_selector_all('option')
                for option in options:
                    text = await option.text_content()
                    value = await option.get_attribute('value')
                    
                    text_norm = normalize_text(text or '')
                    value_norm = normalize_text(value or '')
                    option_norm = normalize_text(option_value)
                    
                    if text_norm == option_norm or value_norm == option_norm or \
                       text_norm.startswith(option_norm) or option_norm.startswith(text_norm) or \
                       option_norm in text_norm or text_norm in option_norm:
                        await select.select_option(value=value)
                        await select.evaluate('el => el.dispatchEvent(new Event("change", {bubbles: true}))')
                        logger.info(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Selected '{text}' from SELECT dropdown")
                        return {'success': True}
        except Exception as e:
            logger.warning(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] SELECT search failed: {e}")
        
        # Custom dropdown fallback
        result = await page.evaluate("""
            (args) => {
                const { keywords, optionValue } = args;
                
                function normalize(text) {
                    if (!text) return '';
                    return text.toLowerCase().trim().replace(/[-_\\s]/g, '');
                }
                
                const normalizedOption = normalize(optionValue);
                
                for (const keyword of keywords) {
                    const labels = document.querySelectorAll('label, div, span');
                    for (const label of labels) {
                        if (normalize(label.textContent).includes(normalize(keyword))) {
                            const dropdown = label.parentElement.querySelector('[role="combobox"], [role="listbox"], button, div[class*="select"]');
                            if (dropdown) {
                                dropdown.click();
                                setTimeout(() => {
                                    const options = document.querySelectorAll('[role="option"], li, div[class*="option"]');
                                    for (const option of options) {
                                        if (normalize(option.textContent) === normalizedOption) {
                                            option.click();
                                            return { success: true };
                                        }
                                    }
                                }, 200);
                                return { success: true, opened: true };
                            }
                        }
                    }
                }
                return { success: false };
            }
        """, {'keywords': label_keywords, 'optionValue': option_value})
        
        if result.get('success'):
            await asyncio.sleep(1);
            logger.info(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Custom dropdown handled")
            return {'success': True}
        
        return {'success': False, 'error': f'Dropdown not found for {label_keywords[0]}'}
        
    except Exception as e:
        logger.error(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Error with dropdown: {e}")
        return {'success': False, 'error': str(e)}
