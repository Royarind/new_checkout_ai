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
                    
                    const elements = document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"]');
                    let bestMatch = null;
                    let bestScore = 0;
                    
                    elements.forEach(el => {
                        const text = el.textContent?.trim() || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const value = el.getAttribute('value') || '';
                        const title = el.getAttribute('title') || '';
                        
                        const allText = [text, ariaLabel, value, title].join(' ');
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
    Find input field by associated label text
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
                
                for (const keyword of keywords) {
                    const normKeyword = normalize(keyword);
                    
                    const fields = document.querySelectorAll('input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]):not([data-checkout-used]), select:not([data-checkout-used]), textarea:not([data-checkout-used])');
                    
                    for (const field of fields) {
                        if (!field.offsetParent) continue;
                        const label = field.closest('label') || document.querySelector(`label[for="${field.id}"]`);
                        if (label && normalize(label.textContent).includes(normKeyword)) {
                            field.setAttribute('data-checkout-marker', marker);
                            return { found: true, marker: marker, method: 'label' };
                        }
                        
                        if (field.placeholder && normalize(field.placeholder).includes(normKeyword)) {
                            field.setAttribute('data-checkout-marker', marker);
                            return { found: true, marker: marker, method: 'placeholder' };
                        }
                        
                        if ((field.name && normalize(field.name).includes(normKeyword)) ||
                            (field.id && normalize(field.id).includes(normKeyword))) {
                            field.setAttribute('data-checkout-marker', marker);
                            return { found: true, marker: marker, method: 'name/id' };
                        }
                        
                        if (field.autocomplete && normalize(field.autocomplete).includes(normKeyword)) {
                            field.setAttribute('data-checkout-marker', marker);
                            return { found: true, marker: marker, method: 'autocomplete' };
                        }
                        
                        if (field.getAttribute('aria-label') && normalize(field.getAttribute('aria-label')).includes(normKeyword)) {
                            field.setAttribute('data-checkout-marker', marker);
                            return { found: true, marker: marker, method: 'aria-label' };
                        }
                    }
                }
                
                return { found: false };
            }
        """, {'keywords': label_keywords, 'marker': marker})
        
        if result.get('found'):
            element = await page.query_selector(f"[data-checkout-marker='{result['marker']}']")
            if element:
                await page.evaluate("(marker) => { document.querySelector(`[data-checkout-marker='${marker}']`).setAttribute('data-checkout-used', 'true'); }", result['marker'])
                logger.info(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Found input by {result['method']}: '{label_keywords[0]}'")
                return element
        
        logger.warning(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Input not found for labels: {label_keywords}")
        return None
        
    except Exception as e:
        logger.error(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Error finding input: {e}")
        return None


async def fill_input_field(page, label_keywords, value):
    """
    Find and fill input field
    Returns: {'success': bool, 'error': str}
    """
    try:
        element = await find_input_by_label(page, label_keywords)
        if not element:
            return {'success': False, 'error': f'Input field not found for {label_keywords[0]}'}
        
        await element.scroll_into_view_if_needed()
        await element.click()
        await element.fill(value)
        logger.info(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Filled '{label_keywords[0]}' with value")
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"CHECKOUT DOM: [{datetime.now().strftime('%H:%M:%S')}] Error filling input: {e}")
        return {'success': False, 'error': str(e)}


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
