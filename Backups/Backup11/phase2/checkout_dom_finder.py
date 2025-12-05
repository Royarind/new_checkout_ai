"""
Checkout DOM Finder - Phase 2 (FIXED)
Fresh DOM finder specifically for checkout flow elements
Handles buttons, form inputs, and dropdowns
"""

import asyncio
from datetime import datetime
from shared.logger_config import setup_logger, log

logger = setup_logger('checkout_dom')


def normalize_text(text):
    """Normalize text for comparison"""
    if not text:
        return ""
    return text.lower().strip().replace('-', '').replace('_', '').replace(' ', '')


async def wait_for_page_stability(page, timeout=3000):
    """Wait for page to be stable before interacting"""
    try:
        await page.wait_for_load_state('domcontentloaded', timeout=timeout)
        await asyncio.sleep(0.5)  # Additional stability wait
        return True
    except Exception as e:
        log(logger, 'warning', f"Page stability timeout: {e}", 'CHECKOUT', 'DOM')
        return False


async def find_and_click_button(page, keywords, max_retries=3):
    """
    Find and click button by keyword matching with scoring system
    Returns: {'success': bool, 'matched_text': str, 'error': str}
    """
    for attempt in range(max_retries):
        try:
            log(logger, 'info', f"Attempt {attempt + 1}/{max_retries} - Finding button: {keywords[0]}", 'CHECKOUT', 'DOM')
            
            # Wait for page stability
            await wait_for_page_stability(page)
            
            result = await page.evaluate("""
                (keywords) => {
                    function normalize(text) {
                        if (!text) return '';
                        return text.toLowerCase().trim().replace(/[-_\\s]/g, '');
                    }
                    
                    const elements = document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"], div[onclick], span[onclick]');
                    let bestMatch = null;
                    let bestScore = 0;
                    const allButtons = [];  // For debugging
                    
                    elements.forEach(el => {
                        // Check if element is visible and interactable
                        if (!el.offsetParent) return;
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return;
                        
                        // Check if disabled
                        if (el.disabled || el.getAttribute('disabled') || el.classList.contains('disabled')) return;
                        
                        const text = el.textContent?.trim() || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const value = el.getAttribute('value') || '';
                        const title = el.getAttribute('title') || '';
                        const className = el.className || '';
                        const id = el.id || '';
                        
                        // Log all visible buttons for debugging
                        allButtons.push({text: text.substring(0, 50), className: className.substring(0, 30)});
                        
                        const allText = [text, ariaLabel, value, title, className, id].join(' ');
                        const normalized = normalize(allText);
                        
                        if (text.length > 100) return;
                        
                        let score = 0;
                        keywords.forEach(keyword => {
                            const normKeyword = normalize(keyword);
                            const normText = normalize(text);
                            
                            // Exact match (highest priority)
                            if (normalized === normKeyword || normText === normKeyword) {
                                score += 100;
                            } 
                            // Contains keyword
                            else if (normalized.includes(normKeyword) || normText.includes(normKeyword)) {
                                score += 50;
                            } 
                            // Keyword contains text (partial match)
                            else if (normKeyword.includes(normalized) && normalized.length > 3) {
                                score += 30;
                            }
                            
                            // Boost for exact phrase matches in original text (before normalization)
                            if (text.toLowerCase().includes(keyword.toLowerCase())) {
                                score += 25;
                            }
                        });
                        
                        // Prioritize overlay/modal/dialog buttons (higher z-index)
                        const style = window.getComputedStyle(el);
                        const zIndex = parseInt(style.zIndex) || 0;
                        const isInModal = el.closest('[role="dialog"], .modal, .overlay, [class*="modal"], [class*="overlay"], [class*="popup"], [class*="drawer"], [class*="cart"]');
                        
                        if (isInModal || zIndex > 100) {
                            score += 200; // Boost score for modal/overlay buttons
                        }
                        
                        // Additional boost for primary/CTA buttons
                        if (className.includes('primary') || className.includes('cta') || className.includes('checkout')) {
                            score += 50;
                        }
                        
                        if (score > bestScore) {
                            bestScore = score;
                            bestMatch = { element: el, text: text || ariaLabel || value, score: score };
                        }
                    });
                    
                    if (!bestMatch || bestScore === 0) {
                        console.log('DEBUG: No button matched. All visible buttons:', allButtons.slice(0, 10));
                        return { found: false, allButtons: allButtons.slice(0, 10) };
                    }
                    
                    const element = bestMatch.element;
                    element.scrollIntoView({ block: 'center', behavior: 'smooth' });
                    
                    return {
                        found: true,
                        matchedText: bestMatch.text,
                        score: bestScore
                    };
                }
            """, keywords)
            
            if result.get('found'):
                log(logger, 'info', f"Found button: '{result.get('matchedText')}' with score {result.get('score')}", 'CHECKOUT', 'DOM')
                # Wait after scroll
                await asyncio.sleep(0.8)
                
                # Try multiple click methods
                click_success = await page.evaluate("""
                    (keywords) => {
                        function normalize(text) {
                            if (!text) return '';
                            return text.toLowerCase().trim().replace(/[-_\\s]/g, '');
                        }
                        
                        const elements = document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"]');
                        let bestMatch = null;
                        let bestScore = 0;
                        
                        elements.forEach(el => {
                            if (!el.offsetParent) return;
                            const allText = [el.textContent, el.getAttribute('aria-label'), el.getAttribute('value')].join(' ');
                            const normalized = normalize(allText);
                            
                            let score = 0;
                            keywords.forEach(keyword => {
                                const normKeyword = normalize(keyword);
                                if (normalized.includes(normKeyword)) score += 50;
                            });
                            
                            if (score > bestScore) {
                                bestScore = score;
                                bestMatch = el;
                            }
                        });
                        
                        if (!bestMatch) return false;
                        
                        // Try clicking
                        try {
                            bestMatch.click();
                            return true;
                        } catch (e) {
                            // Try event dispatch as fallback
                            try {
                                bestMatch.dispatchEvent(new MouseEvent('click', {
                                    bubbles: true,
                                    cancelable: true,
                                    view: window
                                }));
                                return true;
                            } catch (e2) {
                                return false;
                            }
                        }
                    }
                """, keywords)
                
                if click_success:
                    log(logger, 'info', f"✓ Button clicked: '{result.get('matchedText')}' (score: {result.get('score')})", 'CHECKOUT', 'DOM')
                    await asyncio.sleep(1.5)  # Wait for navigation/action
                    return {'success': True, 'matched_text': result.get('matchedText')}
                else:
                    log(logger, 'warning', f"Button found but click failed: '{result.get('matchedText')}'", 'CHECKOUT', 'DOM')
            else:
                log(logger, 'warning', f"Button not found with keywords: {keywords}", 'CHECKOUT', 'DOM')
                if result.get('allButtons'):
                    log(logger, 'info', f"Visible buttons on page: {result.get('allButtons')}", 'CHECKOUT', 'DOM')
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            
        except Exception as e:
            log(logger, 'error', f"Button click attempt {attempt + 1} failed: {e}", 'CHECKOUT', 'DOM')
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
    
    return {'success': False, 'error': 'Button not found after retries'}


async def get_all_form_fields(page):
    """
    QUICK WIN: Get all visible form fields for LLM analysis upfront
    Returns: list of field info dicts
    """
    try:
        await wait_for_page_stability(page)
        
        fields = await page.evaluate("""
            () => {
                const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select, textarea'))
                    .filter(el => {
                        // Check visibility
                        if (!el.offsetParent) return false;
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return false;
                        
                        // Check if not covered by another element
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                        
                        return true;
                    })
                    .map(el => {
                        const label = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
                        return {
                            type: el.type || el.tagName.toLowerCase(),
                            name: el.name || '',
                            id: el.id || '',
                            placeholder: el.placeholder || '',
                            label: label?.textContent?.trim() || '',
                            value: el.value || '',
                            required: el.required || false,
                            disabled: el.disabled || false
                        };
                    });
                return inputs;
            }
        """)
        
        log(logger, 'info', f"Found {len(fields)} visible form fields", 'ADDRESS_FILL', 'DOM')
        return fields
        
    except Exception as e:
        log(logger, 'error', f"Error getting form fields: {e}", 'ADDRESS_FILL', 'DOM')
        return []


async def find_input_by_label(page, label_keywords, retry_count=0):
    """
    IMPROVED: Find input using enhanced strategies with better filtering
    Returns: element handle or None
    """
    try:
        log(logger, 'info', f"Finding input: {label_keywords[0]} (retry: {retry_count})", 'ADDRESS_FILL', 'DOM')
        
        await wait_for_page_stability(page)
        
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
                
                // Filter visible and enabled fields
                const visibleFields = fields.filter(f => {
                    if (!f.offsetParent) return false;
                    if (f.disabled) return false;
                    const rect = f.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }).sort((a, b) => {
                    const rectA = a.getBoundingClientRect();
                    const rectB = b.getBoundingClientRect();
                    return rectA.top - rectB.top;
                });
                
                console.log(`Searching ${visibleFields.length} visible fields for: ${keywords[0]}`);
                
                for (const keyword of keywords) {
                    const normKeyword = normalize(keyword);
                    
                    for (const field of visibleFields) {
                        // Skip if already filled with non-empty value
                        if (field.value && field.value.trim().length > 0) {
                            continue;
                        }
                        
                        const label = field.closest('label') || document.querySelector(`label[for="${field.id}"]`);
                        const labelText = normalize(label?.textContent || '');
                        const fieldName = normalize(field.name || '');
                        const fieldId = normalize(field.id || '');
                        const placeholder = normalize(field.placeholder || '');
                        const autocomplete = normalize(field.getAttribute('autocomplete') || '');
                        const dataTestId = normalize(field.getAttribute('data-testid') || '');
                        
                        let matched = false;
                        let matchMethod = '';
                        
                        // IMPROVED MATCHING WITH ID/NAME/TESTID PRIORITY
                        if ((normKeyword.includes('zip') || normKeyword.includes('postal') || normKeyword.includes('postcode')) && (autocomplete.includes('postal') || autocomplete.includes('zip'))) {
                            matched = true;
                            matchMethod = 'autocomplete-postal';
                        } else if (fieldId.includes(normKeyword) && normKeyword.length > 2) {
                            matched = true;
                            matchMethod = 'id';
                        } else if (fieldName.includes(normKeyword) && normKeyword.length > 2) {
                            matched = true;
                            matchMethod = 'name';
                        } else if (dataTestId.includes(normKeyword) && normKeyword.length > 2) {
                            matched = true;
                            matchMethod = 'data-testid';
                        } else if (autocomplete && autocomplete.includes(normKeyword)) {
                            matched = true;
                            matchMethod = 'autocomplete';
                        } else if (labelText.includes(normKeyword) && normKeyword.length > 2) {
                            matched = true;
                            matchMethod = 'label';
                        } else if (fieldName.includes(normKeyword) && normKeyword.length > 2) {
                            matched = true;
                            matchMethod = 'name';
                        } else if (fieldId.includes(normKeyword) && normKeyword.length > 2) {
                            matched = true;
                            matchMethod = 'id';
                        } else if (placeholder.includes(normKeyword) && normKeyword.length > 2) {
                            matched = true;
                            matchMethod = 'placeholder';
                        }
                        
                        if (matched) {
                            // ENHANCED FILTERING - prevent wrong field matches
                            const allFieldText = labelText + fieldName + fieldId + placeholder;
                            
                            // Prevent cross-contamination
                            if (normKeyword.includes('firstname') || normKeyword.includes('fname')) {
                                if (allFieldText.includes('last') || allFieldText.includes('surname')) continue;
                            }
                            if (normKeyword.includes('lastname') || normKeyword.includes('lname')) {
                                if (allFieldText.includes('first') || allFieldText.includes('given')) continue;
                            }
                            if (normKeyword.includes('address')) {
                                if (allFieldText.includes('email') || allFieldText.includes('name')) continue;
                            }
                            if (normKeyword.includes('email')) {
                                if (allFieldText.includes('address') && !allFieldText.includes('email')) continue;
                            }
                            if (normKeyword.includes('phone') || normKeyword.includes('mobile')) {
                                if (allFieldText.includes('name') || allFieldText.includes('email')) continue;
                            }
                            if (normKeyword.includes('city')) {
                                if (allFieldText.includes('state') || allFieldText.includes('country') || allFieldText.includes('zip')) continue;
                            }
                            if (normKeyword.includes('zip') || normKeyword.includes('postal')) {
                                if ((allFieldText.includes('city') || allFieldText.includes('state')) && !allFieldText.includes('zip') && !allFieldText.includes('postal') && !allFieldText.includes('code')) continue;
                            }
                            
                            field.setAttribute('data-checkout-marker', marker);
                            console.log(`✓ Matched field by ${matchMethod}: ${label?.textContent || field.name || field.id}`);
                            return { found: true, marker: marker, method: matchMethod };
                        }
                    }
                }
                
                console.log(`✗ No match found for: ${keywords[0]}`);
                
                // DEBUG: Log all visible fields for postal code search
                if (keywords.some(k => k.includes('zip') || k.includes('postal') || k.includes('postcode'))) {
                    console.log('=== DEBUG: All visible fields on page ===');
                    visibleFields.forEach((f, idx) => {
                        const label = f.closest('label') || document.querySelector(`label[for="${f.id}"]`);
                        console.log(`Field ${idx + 1}: type=${f.type}, name=${f.name}, id=${f.id}, label=${label?.textContent?.trim()}, autocomplete=${f.getAttribute('autocomplete')}, value=${f.value}`);
                    });
                    console.log('=== END DEBUG ===');
                    
                    console.log('Trying fallback: looking for empty numeric/text input...');
                    for (const field of visibleFields) {
                        if (field.value && field.value.trim().length > 0) continue;
                        const fieldType = field.type || '';
                        if (fieldType === 'text' || fieldType === 'tel' || fieldType === 'number') {
                            const fieldName = normalize(field.name || '');
                            const fieldId = normalize(field.id || '');
                            const placeholder = normalize(field.placeholder || '');
                            const label = field.closest('label') || document.querySelector(`label[for="${field.id}"]`);
                            const labelText = normalize(label?.textContent || '');
                            const allText = fieldName + fieldId + placeholder + labelText;
                            if (!allText.includes('email') && !allText.includes('phone') && !allText.includes('name') && !allText.includes('address') && !allText.includes('city') && !allText.includes('company') && !allText.includes('coupon') && !allText.includes('promo') && !allText.includes('discount') && !allText.includes('gift') && !allText.includes('code') && !allText.includes('voucher')) {
                                field.setAttribute('data-checkout-marker', marker);
                                console.log(`✓ Fallback matched empty field: ${field.name || field.id}`);
                                return { found: true, marker: marker, method: 'fallback-empty' };
                            } else {
                                console.log(`Skipping field (excluded): name=${field.name}, id=${field.id}, label=${labelText}`);
                            }
                        }
                    }
                }
                
                return { found: false };
            }
        """, {'keywords': label_keywords, 'marker': marker})
        
        if result.get('found'):
            element = await page.query_selector(f"[data-checkout-marker='{result['marker']}']")
            if element:
                log(logger, 'info', f"✓ Found '{label_keywords[0]}' by {result['method']}", 'ADDRESS_FILL', 'DOM')
                return element
        
        log(logger, 'warning', f"✗ NOT FOUND - {label_keywords[0]}", 'ADDRESS_FILL', 'DOM')
        return None
        
    except Exception as e:
        log(logger, 'error', f"Error finding input '{label_keywords[0]}': {e}", 'ADDRESS_FILL', 'DOM')
        return None


async def fill_input_field(page, label_keywords, value, max_retries=3):
    """
    IMPROVED: Fill field with better error handling and verification
    Returns: {'success': bool, 'error': str}
    """
    for attempt in range(max_retries):
        try:
            log(logger, 'info', f"Filling '{label_keywords[0]}' = '{value}' (attempt {attempt + 1})", 'ADDRESS_FILL', 'DOM')
            
            # Wait for page stability
            await wait_for_page_stability(page)
            
            element = await find_input_by_label(page, label_keywords, retry_count=attempt)
            if not element:
                wait_time = 1.5 ** attempt  # Exponential backoff: 1.5s, 2.25s, 3.4s
                if attempt < max_retries - 1:
                    log(logger, 'info', f"Field not found, retrying in {wait_time:.1f}s...", 'ADDRESS_FILL', 'DOM')
                    await asyncio.sleep(wait_time)
                    continue
                return {'success': False, 'error': f'Field not found: {label_keywords[0]}'}
            
            # Check if element is still attached and visible
            try:
                is_visible = await element.is_visible()
                if not is_visible:
                    log(logger, 'warning', f"Element not visible for '{label_keywords[0]}'", 'ADDRESS_FILL', 'DOM')
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1.5)
                        continue
            except Exception as e:
                log(logger, 'warning', f"Element detached for '{label_keywords[0]}': {e}", 'ADDRESS_FILL', 'DOM')
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.5)
                    continue
            
            # Slow scroll to bring field into viewport
            await page.evaluate('''(element) => {
                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }''', element)
            await asyncio.sleep(0.8)
            
            # Check if field is already filled with correct value
            try:
                current_value = await element.input_value()
                if current_value and current_value.strip():
                    value_lower = value.lower().strip()
                    current_lower = current_value.lower().strip()
                    if current_lower == value_lower or current_lower.startswith(value_lower[:5]) or value_lower in current_lower:
                        log(logger, 'info', f"✓ Field '{label_keywords[0]}' already filled with '{current_value}'", 'ADDRESS_FILL', 'DOM')
                        return {'success': True}
            except:
                pass
            
            # Slow scroll into view for better visibility
            await page.evaluate('''(element) => {
                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }''', element)
            await asyncio.sleep(1.0)
            
            # Try multiple filling strategies
            fill_success = False
            
            # Strategy 1: Type with delays (most realistic)
            try:
                await element.focus()
                await asyncio.sleep(0.2)
                await element.evaluate('el => el.value = ""')
                await asyncio.sleep(0.1)
                await element.type(value, delay=50)
                await asyncio.sleep(0.3)
                fill_success = True
            except Exception as e:
                log(logger, 'warning', f"Type method failed for '{label_keywords[0]}': {e}", 'ADDRESS_FILL', 'DOM')
            
            # Strategy 2: Force fill if type failed
            if not fill_success:
                try:
                    await element.fill(value, force=True)
                    await asyncio.sleep(0.3)
                    fill_success = True
                except Exception as e:
                    log(logger, 'warning', f"Force fill failed for '{label_keywords[0]}': {e}", 'ADDRESS_FILL', 'DOM')
            
            # Strategy 3: JavaScript injection as last resort
            if not fill_success:
                try:
                    await element.evaluate(f'el => {{ el.value = "{value}"; }}')
                    await asyncio.sleep(0.2)
                    fill_success = True
                except Exception as e:
                    log(logger, 'error', f"All fill strategies failed for '{label_keywords[0]}': {e}", 'ADDRESS_FILL', 'DOM')
                    if attempt < max_retries - 1:
                        continue
                    return {'success': False, 'error': 'Cannot fill field'}
            
            # Trigger events
            await element.evaluate('''el => {
                el.dispatchEvent(new Event("input", {bubbles: true}));
                el.dispatchEvent(new Event("change", {bubbles: true}));
                el.dispatchEvent(new Event("blur", {bubbles: true}));
            }''')
            await asyncio.sleep(0.5)
            
            # Verify the value was set
            try:
                filled_value = await element.input_value()
                if filled_value and (filled_value.lower() == value.lower() or 
                                    filled_value.lower().startswith(value[:3].lower()) or
                                    value.lower() in filled_value.lower()):
                    log(logger, 'info', f"✓ Successfully filled '{label_keywords[0]}' with '{value}'", 'ADDRESS_FILL', 'DOM')
                    return {'success': True}
                else:
                    log(logger, 'error', f"✗ Value mismatch for '{label_keywords[0]}': expected '{value}', got '{filled_value}'", 'ADDRESS_FILL', 'DOM')
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1.5)
                        continue
                    return {'success': False, 'error': f'Value not retained: {filled_value}'}
            except Exception as e:
                log(logger, 'error', f"Cannot verify value for '{label_keywords[0]}': {e}", 'ADDRESS_FILL', 'DOM')
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return {'success': False, 'error': f'Verification failed: {e}'}
            
        except Exception as e:
            error_msg = str(e)
            log(logger, 'error', f"Fill error for '{label_keywords[0]}' (attempt {attempt + 1}): {error_msg[:100]}", 'ADDRESS_FILL', 'DOM')
            
            if attempt < max_retries - 1:
                wait_time = 1.5 ** attempt
                await asyncio.sleep(wait_time)
            else:
                return {'success': False, 'error': error_msg[:200]}
    
    return {'success': False, 'error': 'Max retries exceeded'}


async def batch_fill_fields(page, field_mappings):
    """
    IMPROVED: Fill multiple fields sequentially with better error handling
    field_mappings: [{'keywords': [...], 'value': '...'}, ...]
    Returns: {'success': bool, 'filled_count': int, 'errors': []}
    """
    try:
        log(logger, 'info', f"Starting batch fill of {len(field_mappings)} fields...", 'ADDRESS_FILL', 'DOM')
        
        await wait_for_page_stability(page)
        
        filled_count = 0
        errors = []
        
        for i, mapping in enumerate(field_mappings):
            log(logger, 'info', f"Filling field {i+1}/{len(field_mappings)}: {mapping['keywords'][0]}", 'ADDRESS_FILL', 'DOM')
            
            result = await fill_input_field(page, mapping['keywords'], mapping['value'], max_retries=2)
            
            if result['success']:
                filled_count += 1
                await asyncio.sleep(0.3)  # Small delay between fields
            else:
                error_msg = f"Failed to fill '{mapping['keywords'][0]}': {result.get('error', 'Unknown error')}"
                errors.append(error_msg)
                log(logger, 'error', error_msg, 'ADDRESS_FILL', 'DOM')
        
        log(logger, 'info', f"✓ Batch fill completed: {filled_count}/{len(field_mappings)} fields filled", 'ADDRESS_FILL', 'DOM')
        
        return {
            'success': filled_count > 0,
            'filled_count': filled_count,
            'errors': errors
        }
        
    except Exception as e:
        log(logger, 'error', f"Batch fill error: {e}", 'ADDRESS_FILL', 'DOM')
        return {'success': False, 'filled_count': 0, 'errors': [str(e)]}


async def select_address_autocomplete(page):
    """Select first address autocomplete suggestion"""
    try:
        await asyncio.sleep(2.0)
        log(logger, 'info', 'Selecting first autocomplete suggestion', 'ADDRESS_FILL', 'DOM')
        
        result = await page.evaluate('''() => {
            const selectors = [
                '[role="option"]:not([aria-disabled="true"])',
                '[role="listbox"] > *',
                '.autocomplete-suggestion',
                '[class*="suggestion"]:not(.disabled)',
                '[class*="dropdown"] li:not(.disabled)',
                'ul[class*="autocomplete"] li',
                '[class*="menu"] [class*="item"]',
                '[data-suggestion]'
            ];
            
            const suggestions = document.querySelectorAll(selectors.join(', '));
            const visible = Array.from(suggestions).filter(s => {
                const rect = s.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && s.offsetParent;
            });
            
            if (visible.length === 0) return {found: false};
            
            const first = visible[0];
            const selected = first.textContent?.trim();
            console.log(`Selecting first of ${visible.length}: ${selected}`);
            first.click();
            return {found: true, selected: selected};
        }''');
        
        if result.get('found'):
            log(logger, 'info', f"✓ First autocomplete selected: {result.get('selected', '')[:60]}", 'ADDRESS_FILL', 'DOM')
            await asyncio.sleep(3.0)
            return {'success': True}
        else:
            log(logger, 'info', 'No autocomplete suggestions found', 'ADDRESS_FILL', 'DOM')
            return {'success': False}
    except Exception as e:
        log(logger, 'warning', f'Autocomplete selection error: {e}', 'ADDRESS_FILL', 'DOM')
        return {'success': False}


async def find_and_select_dropdown(page, label_keywords, option_value, max_retries=2):
    """
    IMPROVED: Find and select dropdown with better matching
    Returns: {'success': bool, 'error': str}
    """
    for attempt in range(max_retries):
        try:
            log(logger, 'info', f"Finding dropdown: {label_keywords[0]} = {option_value} (attempt {attempt+1})", 'ADDRESS_FILL', 'DOM')
            
            await wait_for_page_stability(page)
            
            all_selects = await page.query_selector_all('select')
            log(logger, 'info', f"Found {len(all_selects)} total select elements", 'ADDRESS_FILL', 'DOM')
            
            # First pass: Try to match by keywords
            matched_selects = []
            for select in all_selects:
                # Check if visible
                is_visible = await select.is_visible()
                if not is_visible:
                    continue
                
                # Check if this is the right select by label/name
                select_info = await select.evaluate('''el => {
                    const label = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
                    return {
                        name: el.name || '',
                        id: el.id || '',
                        label: label?.textContent?.trim() || ''
                    };
                }''')
                
                # Check if this select matches our keywords
                select_text = f"{select_info['name']} {select_info['id']} {select_info['label']}".lower()
                if any(keyword.lower() in select_text for keyword in label_keywords):
                    matched_selects.append((select, select_info))
            
            # Fallback: If no keyword match, try all visible selects
            if not matched_selects:
                log(logger, 'warning', f"No dropdown matched keywords {label_keywords}, trying all visible dropdowns", 'ADDRESS_FILL', 'DOM')
                for select in all_selects:
                    is_visible = await select.is_visible()
                    if is_visible:
                        select_info = await select.evaluate('''el => {
                            const label = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
                            return {
                                name: el.name || '',
                                id: el.id || '',
                                label: label?.textContent?.trim() || ''
                            };
                        }''')
                        matched_selects.append((select, select_info))
            
            for select, select_info in matched_selects:
                log(logger, 'info', f"Trying select: {select_info['label'] or select_info['name'] or select_info['id']}", 'ADDRESS_FILL', 'DOM')
                
                # Get all options for debugging
                options_debug = await select.evaluate('''el => {
                    return Array.from(el.options).map(opt => ({
                        text: opt.textContent?.trim(),
                        value: opt.value
                    }));
                }''')
                log(logger, 'info', f"Available options: {options_debug[:10]}", 'ADDRESS_FILL', 'DOM')
                
                # Find matching option with improved state matching
                options = await select.query_selector_all('option')
                matched_option = None
                matched_text = None
                
                # Build state abbreviation map for US states
                state_map = {
                    'texas': 'TX', 'california': 'CA', 'florida': 'FL', 'newyork': 'NY',
                    'illinois': 'IL', 'pennsylvania': 'PA', 'ohio': 'OH', 'georgia': 'GA',
                    'northcarolina': 'NC', 'michigan': 'MI', 'newjersey': 'NJ', 'virginia': 'VA',
                    'washington': 'WA', 'arizona': 'AZ', 'massachusetts': 'MA', 'tennessee': 'TN',
                    'indiana': 'IN', 'missouri': 'MO', 'maryland': 'MD', 'wisconsin': 'WI',
                    'colorado': 'CO', 'minnesota': 'MN', 'southcarolina': 'SC', 'alabama': 'AL'
                }
                
                # Country keyword map
                country_keywords = {
                    'US': ['United States', 'United States of America', 'USA', 'US'],
                    'IN': ['India', 'IND', 'IN'],
                    'CA': ['Canada', 'CAN', 'CA'],
                    'GB': ['United Kingdom', 'UK', 'GB', 'Great Britain'],
                    'AU': ['Australia', 'AUS', 'AU']
                }
                
                option_norm = normalize_text(option_value)
                state_abbr = state_map.get(option_norm, option_value.upper()[:2] if len(option_value) == 2 else '')
                
                # Build list of values to try
                values_to_try = [option_value]
                
                # Add country variations
                for code, keywords in country_keywords.items():
                    if option_value.upper() == code or option_value.upper() in [k.upper() for k in keywords]:
                        values_to_try.extend(keywords)
                        break
                
                if state_abbr:
                    values_to_try.append(state_abbr)
                # Add full state name if abbreviation provided
                state_full_names = {v: k.title().replace('', ' ') for k, v in state_map.items()}
                if option_value.upper() in state_full_names:
                    values_to_try.append(state_full_names[option_value.upper()])
                
                log(logger, 'info', f"Looking for: {values_to_try}", 'ADDRESS_FILL', 'DOM')
                
                for option in options:
                    text = await option.text_content()
                    value = await option.get_attribute('value')
                    
                    # Skip placeholder options
                    if not value or value.strip() == '' or text.lower().startswith('select'):
                        continue
                    
                    text_norm = normalize_text(text or '')
                    value_norm = normalize_text(value or '')
                    
                    # Try matching against all value variations
                    for try_value in values_to_try:
                        try_norm = normalize_text(try_value)
                        
                        # Exact match (case insensitive) - PRIORITY
                        if (text.upper() == try_value.upper() or value.upper() == try_value.upper() or
                            text_norm == try_norm or value_norm == try_norm):
                            matched_option = value
                            matched_text = text
                            log(logger, 'info', f"Exact match '{try_value}': text='{text}', value='{value}'", 'ADDRESS_FILL', 'DOM')
                            break
                    
                    if matched_option:
                        break
                
                # Only try partial match if no exact match found
                if not matched_option:
                    for option in options:
                        text = await option.text_content()
                        value = await option.get_attribute('value')
                        if not value or value.strip() == '':
                            continue
                        
                        text_norm = normalize_text(text or '')
                        value_norm = normalize_text(value or '')
                        
                        for try_value in values_to_try:
                            try_norm = normalize_text(try_value)
                            # Partial match only if try_value is in text/value (not vice versa)
                            if len(try_norm) > 2 and (try_norm in text_norm or try_norm in value_norm):
                                matched_option = value
                                matched_text = text
                                log(logger, 'info', f"Partial match '{try_value}': text='{text}', value='{value}'", 'ADDRESS_FILL', 'DOM')
                                break
                        if matched_option:
                            break
                
                if matched_option:
                    await select.select_option(value=matched_option)
                    await asyncio.sleep(0.3)
                    await select.evaluate('el => el.dispatchEvent(new Event("change", {bubbles: true}))')
                    await asyncio.sleep(0.5)
                    
                    # Verify selection
                    selected_value = await select.input_value()
                    if selected_value == matched_option:
                        log(logger, 'info', f"✓ Selected and verified '{matched_text}' in dropdown", 'ADDRESS_FILL', 'DOM')
                        return {'success': True}
                    else:
                        log(logger, 'warning', f"Selection not verified: expected '{matched_option}', got '{selected_value}'", 'ADDRESS_FILL', 'DOM')
                        return {'success': False, 'error': 'Selection verification failed'}
            
            # Check if this might be a country mismatch (US state vs Indian state)
            if options_debug and len(options_debug) > 0:
                first_option_text = options_debug[0].get('text', '').lower()
                # If we see Indian states but trying to fill US state, skip gracefully
                if any(indian in first_option_text for indian in ['andhra', 'arunachal', 'assam', 'bihar', 'goa', 'gujarat']):
                    if option_value.upper() in ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']:
                        log(logger, 'warning', f"Country mismatch detected: US state '{option_value}' not available in Indian state list. Skipping state field.", 'ADDRESS_FILL', 'DOM')
                        return {'success': False, 'error': f'Country mismatch: {option_value} not available', 'skip': True}
            
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5)
                continue
            
            return {'success': False, 'error': f'Dropdown option not found: {label_keywords[0]} = {option_value}'}
            
        except Exception as e:
            log(logger, 'error', f"Dropdown error (attempt {attempt+1}): {e}", 'ADDRESS_FILL', 'DOM')
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5)
            else:
                return {'success': False, 'error': str(e)}
    
    return {'success': False, 'error': 'Max retries exceeded'}