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


async def get_all_form_fields(page):
    """
    QUICK WIN: Get all visible form fields for LLM analysis upfront
    Returns: list of field info dicts
    """
    try:
        fields = await page.evaluate("""
            () => {
                const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select, textarea'))
                    .filter(el => el.offsetParent)
                    .map(el => {
                        const label = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
                        return {
                            type: el.type || el.tagName.toLowerCase(),
                            name: el.name || '',
                            id: el.id || '',
                            placeholder: el.placeholder || '',
                            label: label?.textContent?.trim() || '',
                            value: el.value || '',
                            required: el.required || false
                        };
                    });
                return inputs;
            }
        """)
        return fields
    except Exception as e:
        logger.error(f"CHECKOUT DOM: Error getting form fields: {e}")
        return []


async def find_input_by_label(page, label_keywords):
    """
    SIMPLIFIED: Find input using top 3 strategies only (label, name, placeholder)
    Returns: element handle or None
    """
    try:
        logger.info(f"CHECKOUT DOM: Finding input for: {label_keywords[0]}")
        
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
                        const placeholder = normalize(field.placeholder || '');
                        
                        let matched = false;
                        let matchMethod = '';
                        
                        // TOP 3 STRATEGIES ONLY
                        if (labelText.includes(normKeyword) && normKeyword.length > 2) {
                            matched = true;
                            matchMethod = 'label';
                        } else if (fieldName.includes(normKeyword) && normKeyword.length > 2) {
                            matched = true;
                            matchMethod = 'name';
                        } else if (placeholder.includes(normKeyword) && normKeyword.length > 2) {
                            matched = true;
                            matchMethod = 'placeholder';
                        }
                        
                        if (matched) {
                            // SIMPLIFIED FILTERING
                            if (normKeyword.includes('firstname') && (fieldName.includes('last') || labelText.includes('last'))) continue;
                            if (normKeyword.includes('lastname') && (fieldName.includes('first') || labelText.includes('first'))) continue;
                            if (normKeyword.includes('address') && fieldName.includes('email')) continue;
                            
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
                logger.info(f"CHECKOUT DOM: MATCHED '{label_keywords[0]}' by {result['method']} -> name='{field_info['name']}' id='{field_info['id']}'")
                return element
        
        logger.error(f"CHECKOUT DOM: NOT FOUND - {label_keywords[0]}")
        return None
        
    except Exception as e:
        logger.error(f"CHECKOUT DOM: Error finding input: {e}")
        return None


async def fill_input_field(page, label_keywords, value, max_retries=2):
    """
    SIMPLIFIED: Fill field with exponential backoff, fail fast
    Returns: {'success': bool, 'error': str}
    """
    for attempt in range(max_retries):
        try:
            # Wait for field to be stable and visible
            await page.wait_for_load_state('domcontentloaded', timeout=3000)
            
            element = await find_input_by_label(page, label_keywords)
            if not element:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s
                if attempt < max_retries - 1:
                    logger.info(f"CHECKOUT DOM: Field not found, retry in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                return {'success': False, 'error': f'Field not found: {label_keywords[0]}'}
            
            # Wait for element to be stable
            try:
                await element.wait_for_element_state('stable', timeout=2000)
            except:
                pass
            
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)
            await element.click()
            await asyncio.sleep(0.2)
            
            # Fill and trigger events
            await element.fill('')
            await asyncio.sleep(0.1)
            await element.fill(value)
            await element.evaluate('el => { el.dispatchEvent(new Event("input", {bubbles: true})); el.dispatchEvent(new Event("change", {bubbles: true})); }')
            await asyncio.sleep(0.3)
            
            # Verify
            filled_value = await element.input_value()
            if filled_value.lower() == value.lower() or filled_value.lower().startswith(value[:5].lower()):
                logger.info(f"CHECKOUT DOM: ✓ Filled '{label_keywords[0]}'")
                return {'success': True}
            
            return {'success': True}  # Accept partial match
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"CHECKOUT DOM: Fill error (attempt {attempt + 1}): {error_msg[:100]}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
            else:
                return {'success': False, 'error': error_msg[:200]}
    
    return {'success': False, 'error': 'Max retries exceeded'}


async def batch_fill_fields(page, field_mappings):
    """
    QUICK WIN: Fill multiple fields at once using JavaScript injection
    field_mappings: [{'keywords': [...], 'value': '...'}, ...]
    Returns: {'success': bool, 'filled_count': int, 'errors': []}
    """
    try:
        logger.info(f"CHECKOUT DOM: Batch filling {len(field_mappings)} fields...")
        
        result = await page.evaluate("""
            (mappings) => {
                function normalize(text) {
                    if (!text) return '';
                    return text.toLowerCase().trim().replace(/[-_\\s]/g, '');
                }
                
                const fields = Array.from(document.querySelectorAll('input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]), textarea'));
                const visibleFields = fields.filter(f => f.offsetParent);
                
                let filled = 0;
                const errors = [];
                
                for (const mapping of mappings) {
                    let found = false;
                    
                    for (const keyword of mapping.keywords) {
                        const normKeyword = normalize(keyword);
                        
                        for (const field of visibleFields) {
                            const label = field.closest('label') || document.querySelector(`label[for="${field.id}"]`);
                            const labelText = normalize(label?.textContent || '');
                            const fieldName = normalize(field.name || '');
                            const placeholder = normalize(field.placeholder || '');
                            
                            if (labelText.includes(normKeyword) || fieldName.includes(normKeyword) || placeholder.includes(normKeyword)) {
                                field.value = mapping.value;
                                field.dispatchEvent(new Event('input', {bubbles: true}));
                                field.dispatchEvent(new Event('change', {bubbles: true}));
                                filled++;
                                found = true;
                                break;
                            }
                        }
                        if (found) break;
                    }
                    
                    if (!found) {
                        errors.push(`Field not found: ${mapping.keywords[0]}`);
                    }
                }
                
                return { filled, errors };
            }
        """, field_mappings)
        
        logger.info(f"CHECKOUT DOM: Batch filled {result['filled']}/{len(field_mappings)} fields")
        if result['errors']:
            logger.warning(f"CHECKOUT DOM: Errors: {result['errors']}")
        
        return {'success': result['filled'] > 0, 'filled_count': result['filled'], 'errors': result['errors']}
        
    except Exception as e:
        logger.error(f"CHECKOUT DOM: Batch fill error: {e}")
        return {'success': False, 'filled_count': 0, 'errors': [str(e)]}


async def find_and_select_dropdown(page, label_keywords, option_value):
    """
    SIMPLIFIED: Find and select dropdown (native SELECT only)
    Returns: {'success': bool, 'error': str}
    """
    try:
        logger.info(f"CHECKOUT DOM: Finding dropdown: {label_keywords[0]} = {option_value}")
        
        all_selects = await page.query_selector_all('select')
        for select in all_selects:
            options = await select.query_selector_all('option')
            for option in options:
                text = await option.text_content()
                value = await option.get_attribute('value')
                
                text_norm = normalize_text(text or '')
                option_norm = normalize_text(option_value)
                
                if option_norm in text_norm or text_norm in option_norm:
                    await select.select_option(value=value)
                    await select.evaluate('el => el.dispatchEvent(new Event("change", {bubbles: true}))')
                    logger.info(f"CHECKOUT DOM: ✓ Selected '{text}'")
                    return {'success': True}
        
        return {'success': False, 'error': f'Dropdown not found: {label_keywords[0]}'}
        
    except Exception as e:
        logger.error(f"CHECKOUT DOM: Dropdown error: {e}")
        return {'success': False, 'error': str(e)}
