"""
Checkout DOM Finder - Phase 2 (FIXED)
Fresh DOM finder specifically for checkout flow elements
Handles buttons, form inputs, and dropdowns
"""

import asyncio
from datetime import datetime
from src.checkout_ai.dom.service import UniversalDOMFinder
from src.checkout_ai.legacy.phase2.smart_form_filler import SmartFormFiller
from src.checkout_ai.utils.logger_config import setup_logger, log

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
        await page.wait_for_load_state('domcontentloaded', timeout=timeout)
        # Minimal stability wait reduced to speed up interactions
        await asyncio.sleep(0.02)
        return True
    except Exception as e:
        log(logger, 'warning', f"Page stability timeout: {e}", 'CHECKOUT', 'DOM')
        return False


async def detect_stripe_iframe(page, label_keywords):
    """
    Detect if the target field is likely inside a Stripe iframe
    Returns: {'is_stripe': bool, 'iframe_selector': str or None}
    """
    try:
        result = await page.evaluate("""
            (keywords) => {
                // Find all Stripe iframes
                const stripeIframes = Array.from(document.querySelectorAll('iframe'))
                    .filter(iframe => {
                        const src = iframe.src || '';
                        return src.includes('stripe.com') || 
                               iframe.className.includes('Stripe') ||
                               iframe.title?.toLowerCase().includes('stripe') ||
                               iframe.title?.toLowerCase().includes('secure');
                    });
                
                if (stripeIframes.length === 0) return { is_stripe: false };
                
                // Check if any Stripe iframe matches our field keywords
                for (const iframe of stripeIframes) {
                    const title = (iframe.title || '').toLowerCase();
                    const name = (iframe.name || '').toLowerCase();
                    
                    for (const keyword of keywords) {
                        const kw = keyword.toLowerCase();
                        if (title.includes(kw) || name.includes(kw)) {
                            return {
                                is_stripe: true,
                                iframe_title: iframe.title,
                                iframe_name: iframe.name,
                                iframe_class: iframe.className
                            };
                        }
                    }
                }
                
                // REMOVED: Don't assume all email/address fields are in Stripe iframes
                // Only return true if we actually found a matching Stripe iframe above
                
                return { is_stripe: false };
            }
        """, label_keywords)
        
        return result
    except Exception as e:
        log(logger, 'warning', f"Error detecting Stripe iframe: {e}", 'CHECKOUT', 'DOM')
        return {'is_stripe': False}


async def interact_with_stripe_iframe(page, label_keywords, value):
    """
    Special handling for Stripe Elements (cross-origin iframes)
    Strategy: Click iframe to focus, then use keyboard input
    """
    try:
        log(logger, 'info', f"Attempting Stripe iframe interaction for: {label_keywords[0]}", 'CHECKOUT', 'DOM')
        
        # Find the Stripe iframe
        iframe_info = await detect_stripe_iframe(page, label_keywords)
        if not iframe_info.get('is_stripe'):
            return {'success': False, 'error': 'Not a Stripe iframe'}
        
        # Strategy 1: Click the iframe container to focus it
        clicked = await page.evaluate("""
            (keywords) => {
                const iframes = Array.from(document.querySelectorAll('iframe'))
                    .filter(iframe => {
                        const src = iframe.src || '';
                        const title = (iframe.title || '').toLowerCase();
                        return src.includes('stripe.com') || title.includes('secure');
                    });
                
                for (const iframe of iframes) {
                    const title = (iframe.title || '').toLowerCase();
                    for (const kw of keywords) {
                        if (title.includes(kw.toLowerCase())) {
                            iframe.scrollIntoView({ block: 'center' });
                            iframe.click();
                            iframe.focus();
                            return true;
                        }
                    }
                }
                
                // Fallback: click first Stripe iframe
                if (iframes.length > 0) {
                    iframes[0].scrollIntoView({ block: 'center' });
                    iframes[0].click();
                    iframes[0].focus();
                    return true;
                }
                
                return false;
            }
        """, label_keywords)
        
        if not clicked:
            return {'success': False, 'error': 'Could not click Stripe iframe'}
        
        # Wait for iframe to be focused
        await asyncio.sleep(0.5)
        
        # Strategy 2: Use keyboard to type the value
        await page.keyboard.type(value, delay=50)
        await asyncio.sleep(0.3)
        
        # Press Tab to move to next field (triggers validation)
        await page.keyboard.press('Tab')
        await asyncio.sleep(0.2)
        
        log(logger, 'info', f"✓ Stripe iframe interaction completed for: {label_keywords[0]}", 'CHECKOUT', 'DOM')
        return {'success': True}
        
    except Exception as e:
        log(logger, 'error', f"Stripe iframe interaction failed: {e}", 'CHECKOUT', 'DOM')
        return {'success': False, 'error': str(e)}


async def wait_for_dependent_dropdown(page, parent_selector=None, timeout=3000):
    """
    Wait for a new <select> element that appears after interacting with a parent element.
    Returns True if a dependent dropdown is found/ready, otherwise False.
    """
    try:
        # If we have a specific parent selector, look for siblings/descendants
        if parent_selector:
            # Try finding a select that is a sibling or inside a common container
            has_dependent = await page.evaluate("""
                (selector) => {
                    const parent = document.querySelector(selector);
                    if (!parent) return false;
                    
                    // Look for a form or container
                    const container = parent.closest('form') || parent.closest('.form-group') || parent.parentElement?.parentElement;
                    if (!container) return false;
                    
                    // Check if there's another select in the container that wasn't there or is now visible
                    const selects = container.querySelectorAll('select');
                    return selects.length > 0;
                }
            """, parent_selector)
            
            if has_dependent:
                return True

        # Generic wait for any select to be visible and stable
        await page.wait_for_selector('select:visible', timeout=timeout)
        return True
    except Exception:
        return False


async def find_and_click_button(page, keywords, max_retries=3):
    """
    Find and click button by keyword matching with scoring system
    Returns: {'success': bool, 'matched_text': str, 'error': str}
    """
    for attempt in range(max_retries):
        # Short pause before each button search attempt
        await asyncio.sleep(0.3)
        try:
            log(logger, 'info', f"Attempt {attempt + 1}/{max_retries} - Finding button: {keywords[0]}", 'CHECKOUT', 'DOM')
            
            # Wait for page stability
            await wait_for_page_stability(page)
            
            # Search through all frames (iframes) and Shadow DOMs
            frames = page.frames
            log(logger, 'info', f"Searching in {len(frames)} frames", 'CHECKOUT', 'DOM')
            
            best_global_match = None
            best_global_score = 0
            best_global_frame = None
            
            for frame in frames:
                try:
                    if frame.is_detached():
                        continue
                        
                    result = await frame.evaluate("""
                        (keywords) => {
                            function normalize(text) {
                                if (!text) return '';
                                return text.toLowerCase().trim().replace(/[-_\\s]/g, '');
                            }
                            
                            // Recursive function to collect buttons from Shadow DOMs
                            function collectButtons(root) {
                                let buttons = [];
                                const selectors = 'button, a, input[type="submit"], input[type="button"], [role="button"], div[onclick], span[onclick], [class*="button"], [class*="btn"]';
                                
                                // Get buttons in current root
                                const elements = root.querySelectorAll(selectors);
                                buttons = [...buttons, ...Array.from(elements)];
                                
                                // Recursively check Shadow DOMs
                                const allElements = root.querySelectorAll('*');
                                allElements.forEach(el => {
                                    if (el.shadowRoot) {
                                        buttons = [...buttons, ...collectButtons(el.shadowRoot)];
                                    }
                                });
                                
                                return buttons;
                            }
                            
                            const elements = collectButtons(document);
                            let bestMatch = null;
                            let bestScore = 0;
                            const allButtons = [];
                            
                            elements.forEach(el => {
                                // Check visibility
                                const rect = el.getBoundingClientRect();
                                if (rect.width === 0 || rect.height === 0) return;
                                
                                // Check if disabled
                                if (el.disabled || el.getAttribute('disabled') || el.classList.contains('disabled')) return;
                                
                                const text = el.textContent?.trim() || el.innerText?.trim() || '';
                                const ariaLabel = el.getAttribute('aria-label') || '';
                                const value = el.getAttribute('value') || '';
                                const title = el.getAttribute('title') || '';
                                const className = typeof el.className === 'string' ? el.className : '';
                                const id = el.id || '';
                                
                                allButtons.push({text: text.substring(0, 50), className: className.substring(0, 30)});
                                
                                const allText = [text, ariaLabel, value, title, className, id].join(' ');
                                const normalized = normalize(allText);
                                
                                if (text.length > 100) return;
                                
                                let score = 0;
                                keywords.forEach(keyword => {
                                    const normKeyword = normalize(keyword);
                                    const normText = normalize(text);
                                    
                                    if (normalized === normKeyword || normText === normKeyword) {
                                        score += 100;
                                    } else if (normalized.includes(normKeyword) || normText.includes(normKeyword)) {
                                        score += 50;
                                    } else if (normKeyword.includes(normalized) && normalized.length > 3) {
                                        score += 30;
                                    }
                                    
                                    if (text.toLowerCase().includes(keyword.toLowerCase())) {
                                        score += 25;
                                    }
                                });
                                
                                // Prioritize modal/overlay buttons
                                const style = window.getComputedStyle(el);
                                const zIndex = parseInt(style.zIndex) || 0;
                                const isInModal = el.closest('[role="dialog"], .modal, .overlay, [class*="modal"], [class*="overlay"], [class*="popup"], [class*="drawer"], [class*="cart"]');
                                
                                if (isInModal || zIndex > 100) {
                                    score += 200;
                                }
                                
                                if (className.includes('primary') || className.includes('cta') || className.includes('checkout')) {
                                    score += 50;
                                }
                                
                                // Filter unwanted buttons
                                const unwantedKeywords = ['continue shopping', 'shop now', 'keep shopping', 'back to shop', 'return to'];
                                const textLower = text.toLowerCase();
                                const isUnwanted = unwantedKeywords.some(kw => textLower.includes(kw));
                                
                                if (score > bestScore && !isUnwanted) {
                                    bestScore = score;
                                    bestMatch = { text: text || ariaLabel || value, score: score };
                                }
                            });
                            
                            return {
                                found: !!bestMatch,
                                matchedText: bestMatch ? bestMatch.text : null,
                                score: bestScore,
                                allButtons: allButtons.slice(0, 5)
                            };
                        }
                    """, keywords)
                    
                    if result.get('found') and result.get('score', 0) > best_global_score:
                        best_global_score = result.get('score')
                        best_global_match = result
                        best_global_frame = frame
                        
                except Exception:
                    # Frame might be cross-origin or detached
                    continue
            
            if best_global_match and best_global_frame:
                log(logger, 'info', f"Found button in frame '{best_global_frame.url}': '{best_global_match.get('matchedText')}' with score {best_global_score}", 'CHECKOUT', 'DOM')
                
                # Click the button in the identified frame
                click_success = await best_global_frame.evaluate("""
                    (keywords) => {
                        function normalize(text) {
                            if (!text) return '';
                            return text.toLowerCase().trim().replace(/[-_\\s]/g, '');
                        }
                        
                        function collectButtons(root) {
                            let buttons = [];
                            const selectors = 'button, a, input[type="submit"], input[type="button"], [role="button"], div[onclick], span[onclick], [class*="button"], [class*="btn"]';
                            const elements = root.querySelectorAll(selectors);
                            buttons = [...buttons, ...Array.from(elements)];
                            const allElements = root.querySelectorAll('*');
                            allElements.forEach(el => {
                                if (el.shadowRoot) {
                                    buttons = [...buttons, ...collectButtons(el.shadowRoot)];
                                }
                            });
                            return buttons;
                        }
                        
                        const elements = collectButtons(document);
                        let bestMatch = null;
                        let bestScore = 0;
                        
                        elements.forEach(el => {
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) return;
                            
                            const text = el.textContent?.trim() || el.innerText?.trim() || '';
                            const ariaLabel = el.getAttribute('aria-label') || '';
                            const value = el.getAttribute('value') || '';
                            const className = typeof el.className === 'string' ? el.className : '';
                            
                            const allText = [text, ariaLabel, value, className].join(' ');
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
                    log(logger, 'info', f"✓ Button clicked: '{best_global_match.get('matchedText')}' (score: {best_global_score})", 'CHECKOUT', 'DOM')
                    await asyncio.sleep(1.5)
                    return {'success': True, 'matched_text': best_global_match.get('matchedText')}
                else:
                    log(logger, 'warning', f"Button found but click failed: '{best_global_match.get('matchedText')}'", 'CHECKOUT', 'DOM')
            else:
                log(logger, 'warning', f"Button not found with keywords: {keywords}", 'CHECKOUT', 'DOM')
            
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
    Now with Stripe Element detection and iframe/Shadow DOM support
    Returns: element handle or None
    """
    try:
        log(logger, 'info', f"Finding input: {label_keywords[0]} (retry: {retry_count})", 'ADDRESS_FILL', 'DOM')
        
        await wait_for_page_stability(page)
        
        # FIRST: Check if this field is in a Stripe iframe
        stripe_info = await detect_stripe_iframe(page, label_keywords)
        if stripe_info.get('is_stripe'):
            log(logger, 'info', f"Detected Stripe iframe for '{label_keywords[0]}' - will use special handling", 'ADDRESS_FILL', 'DOM')
            # Return None to signal that fill_input_field should use Stripe interaction
            return None
        
        import random
        marker = f"found-{random.randint(100000, 999999)}"
        
        best_global_element = None
        best_global_method = None
        
        frames = page.frames
        for frame in frames:
            try:
                if frame.is_detached():
                    continue

                result = await frame.evaluate("""
                    (args) => {
                        const { keywords, marker } = args;
                        
                        function normalize(text) {
                            if (!text) return '';
                            return text.toLowerCase().trim().replace(/[-_\\s]/g, '');
                        }
                        
                        // Recursive function to collect inputs from Shadow DOMs
                        function collectInputs(root) {
                            let inputs = [];
                            const selectors = 'input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]), select, textarea';
                            
                            // Get inputs in current root
                            const elements = root.querySelectorAll(selectors);
                            inputs = [...inputs, ...Array.from(elements)];
                            
                            // Recursively check Shadow DOMs
                            const allElements = root.querySelectorAll('*');
                            allElements.forEach(el => {
                                if (el.shadowRoot) {
                                    inputs = [...inputs, ...collectInputs(el.shadowRoot)];
                                }
                            });
                            
                            return inputs;
                        }

                        const fields = collectInputs(document);
                        
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
                                    if (normKeyword.includes('address') || normKeyword.includes('street')) {
                                        // Address shouldn't match phone, email, name, city, state, zip
                                        if (allFieldText.includes('email') || allFieldText.includes('name') || 
                                            allFieldText.includes('phone') || allFieldText.includes('mobile') || allFieldText.includes('tel') ||
                                            allFieldText.includes('city') || allFieldText.includes('state') || 
                                            allFieldText.includes('zip') || allFieldText.includes('postal')) continue;
                                            
                                        // Address shouldn't match type="tel"
                                        if (field.type === 'tel') continue;
                                    }
                                    if (normKeyword.includes('email')) {
                                        // Email can contain 'address' (e.g. 'email address'), but shouldn't be JUST 'address'
                                        if (allFieldText.includes('address') && !allFieldText.includes('email')) continue;
                                    }
                                    if (normKeyword.includes('phone') || normKeyword.includes('mobile') || normKeyword.includes('tel')) {
                                        // Phone shouldn't match name, email, city
                                        // ALLOW 'address' if it's part of a compound label like "Shipping Address Phone"
                                        if (allFieldText.includes('name') || allFieldText.includes('email') || 
                                            allFieldText.includes('city')) continue;
                                            
                                        // Only block 'address' if 'phone' isn't in the matched text part (heuristic)
                                        // Actually, let's just be less strict about 'address' for phone, 
                                        // as "Shipping Address Phone" is common.
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
                        
                        // FALLBACK: Email specific search
                        if (keywords.some(k => k.includes('email'))) {
                            console.log('Trying fallback: looking for any email-like field...');
                            for (const field of visibleFields) {
                                // Check type="email"
                                if (field.type === 'email') {
                                    field.setAttribute('data-checkout-marker', marker);
                                    console.log(`✓ Fallback matched type=email: ${field.name || field.id}`);
                                    return { found: true, marker: marker, method: 'fallback-type-email' };
                                }
                                
                                // Check name/id/label for "email"
                                const label = field.closest('label') || document.querySelector(`label[for="${field.id}"]`);
                                const allText = normalize((field.name || '') + (field.id || '') + (label?.textContent || '') + (field.placeholder || ''));
                                
                                if (allText.includes('email') || allText.includes('e-mail')) {
                                     field.setAttribute('data-checkout-marker', marker);
                                     console.log(`✓ Fallback matched email text: ${field.name || field.id}`);
                                     return { found: true, marker: marker, method: 'fallback-text-email' };
                                }
                            }
                        }

                        // FALLBACK: Phone specific search
                        if (keywords.some(k => k.includes('phone') || k.includes('mobile'))) {
                            console.log('Trying fallback: looking for any phone-like field...');
                            for (const field of visibleFields) {
                                // Check type="tel"
                                if (field.type === 'tel') {
                                    field.setAttribute('data-checkout-marker', marker);
                                    console.log(`✓ Fallback matched type=tel: ${field.name || field.id}`);
                                    return { found: true, marker: marker, method: 'fallback-type-tel' };
                                }
                                
                                // Check name/id/label for "phone"
                                const label = field.closest('label') || document.querySelector(`label[for="${field.id}"]`);
                                const allText = normalize((field.name || '') + (field.id || '') + (label?.textContent || '') + (field.placeholder || ''));
                                
                                if (allText.includes('phone') || allText.includes('mobile') || allText.includes('tel')) {
                                     field.setAttribute('data-checkout-marker', marker);
                                     console.log(`✓ Fallback matched phone text: ${field.name || field.id}`);
                                     return { found: true, marker: marker, method: 'fallback-text-phone' };
                                }
                            }
                        }


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
                    best_global_element = await frame.query_selector(f"[data-checkout-marker='{result['marker']}']")
                    best_global_method = result['method']
                    break # Found in this frame, no need to check others

            except Exception:
                # Frame might be cross-origin or detached
                continue
        
        if best_global_element:
            log(logger, 'info', f"✓ Found '{label_keywords[0]}' by {best_global_method}", 'ADDRESS_FILL', 'DOM')
            return best_global_element
        
        log(logger, 'warning', f"✗ NOT FOUND - {label_keywords[0]}", 'ADDRESS_FILL', 'DOM')
        return None
        
    except Exception as e:
        log(logger, 'error', f"Error finding input '{label_keywords[0]}': {e}", 'ADDRESS_FILL', 'DOM')
        return None


async def fill_input_field(page, label_keywords, value, max_retries=3):
    """
    OPTIMIZED: Fill field with minimal delays and strict verification
    Returns: {'success': bool, 'error': str, 'verified': bool}
    """
    for attempt in range(max_retries):
        try:
            log(logger, 'info', f"Filling '{label_keywords[0]}' = '{value}' (attempt {attempt + 1})", 'ADDRESS_FILL', 'DOM')
            
            # Wait for page stability (optimized)
            await wait_for_page_stability(page)
            
            # Add city keywords if not present
            if 'city' in label_keywords[0].lower() and 'town' not in label_keywords:
                label_keywords.extend(['town', 'municipality', 'suburb'])
            
            element = await find_input_by_label(page, label_keywords, retry_count=attempt)
            
            if element:
                # Ensure element is visible and scrolled into view
                try:
                    await element.scroll_into_view_if_needed()
                    # Force scroll to center to avoid sticky headers
                    await element.evaluate('el => el.scrollIntoView({block: "center", inline: "center"})')
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

                # Check if already filled
                try:
                    current_value = await element.input_value()
                    if normalize(current_value) == normalize(value):
                        log(logger, 'info', f"Field '{label_keywords[0]}' already filled correctly.", 'ADDRESS_FILL', 'DOM')
                        return {'success': True, 'verified': True}
                except Exception:
                    pass # Element might be detached, will catch in fill

            # Special handling for Stripe Elements (when find_input_by_label returns None)
            if element is None:
                # Check if it's a Stripe iframe
                stripe_info = await detect_stripe_iframe(page, label_keywords)
                if stripe_info.get('is_stripe'):
                    log(logger, 'info', f"Using Stripe iframe interaction for '{label_keywords[0]}'", 'ADDRESS_FILL', 'DOM')
                    result = await interact_with_stripe_iframe(page, label_keywords, value)
                    if result.get('success'):
                        return {'success': True, 'verified': True} # Stripe verification is internal
                    else:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1.0)
                            continue
                        return {'success': False, 'error': f"Stripe iframe interaction failed: {result.get('error')}"}
                
                # Not Stripe, just field not found
                # Smart retry: if field not found on first attempt, it might not exist at all
                # Only retry if we suspect it might appear (e.g., dynamic form)
                if attempt < max_retries - 1:
                    wait_time = 1.0  # Reduced from exponential
                    log(logger, 'info', f"Field not found, retrying in {wait_time:.1f}s...", 'ADDRESS_FILL', 'DOM')
                    await asyncio.sleep(wait_time)
                    continue
                return {'success': False, 'error': f'Field not found: {label_keywords[0]}'}
            
            # Check visibility (optimized)
            try:
                if not await element.is_visible():
                    log(logger, 'warning', f"Element not visible for '{label_keywords[0]}'", 'ADDRESS_FILL', 'DOM')
                    # Try to scroll into view immediately
                    await element.scroll_into_view_if_needed()
                    await asyncio.sleep(0.2)
                    if not await element.is_visible():
                        if attempt < max_retries - 1: continue
            except Exception:
                pass # Element might be detached, will catch in fill
            

            
            # Filling Strategy: Fast Type -> Force Fill -> JS
            fill_success = False
            
            # 1. Fast Type (Primary)
            try:
                await element.focus()
                await element.fill(value) # Playwright fill is faster/better than type for forms
                fill_success = True
            except Exception as e:
                log(logger, 'warning', f"Fill failed for '{label_keywords[0]}', trying JS: {e}", 'ADDRESS_FILL', 'DOM')
            
            # 2. JS Injection (Fallback)
            if not fill_success:
                try:
                    await element.evaluate(f'el => {{ el.value = "{value}"; el.dispatchEvent(new Event("input", {{bubbles: true}})); el.dispatchEvent(new Event("change", {{bubbles: true}})); }}')
                    fill_success = True
                except Exception as e:
                    log(logger, 'error', f"JS fill failed for '{label_keywords[0]}': {e}", 'ADDRESS_FILL', 'DOM')
            
            if not fill_success:
                if attempt < max_retries - 1: continue
                return {'success': False, 'error': 'All fill strategies failed'}

            # Trigger events to ensure validation runs
            try:
                await element.evaluate('el => { el.dispatchEvent(new Event("blur", {bubbles: true})); }')
            except:
                pass
                
            # STRICT VALIDATION (Read-After-Write)
            try:
                # Small pause for framework validation
                await asyncio.sleep(0.1) 
                
                final_value = await element.input_value()
                
                # Normalize
                import re
                def normalize(v): return re.sub(r'\s+', '', str(v).lower())
                
                norm_input = normalize(value)
                norm_final = normalize(final_value)
                
                # Check match
                is_match = norm_input == norm_final or norm_input in norm_final or norm_final in norm_input
                
                # Special phone handling
                if not is_match and any(k in ['phone', 'mobile', 'tel'] for k in label_keywords):
                    def digits(v): return re.sub(r'\D', '', str(v))
                    if digits(value) in digits(final_value):
                        is_match = True

                if is_match:
                    log(logger, 'info', f"✓ Verified '{label_keywords[0]}': '{final_value}'", 'ADDRESS_FILL', 'DOM')
                    return {'success': True, 'verified': True}
                else:
                    log(logger, 'error', f"✗ Validation failed for '{label_keywords[0]}': Expected '{value}', Got '{final_value}'", 'ADDRESS_FILL', 'DOM')
                    # If validation failed, we MUST retry
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5)
                        continue
                    return {'success': False, 'error': f"Validation failed: Got '{final_value}'", 'verified': False}
                    
            except Exception as e:
                log(logger, 'warning', f"Validation error: {e}", 'ADDRESS_FILL', 'DOM')
                # If we can't verify, we assume success but warn
                return {'success': True, 'verified': False, 'warning': 'Could not verify value'}
            
        except Exception as e:
            log(logger, 'error', f"Error filling '{label_keywords[0]}': {e}", 'ADDRESS_FILL', 'DOM')
            if attempt < max_retries - 1:
                await asyncio.sleep(1.0)
            else:
                return {'success': False, 'error': str(e)}
    
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
        # Reduced wait before autocomplete selection
        await asyncio.sleep(0.5)
        log(logger, 'info', 'Selecting first autocomplete suggestion', 'ADDRESS_FILL', 'DOM')
        
        result = await page.evaluate('''() => {
            const selectors = [
                '[role="option"]:not([aria-disabled="true"])',
                '[role="listbox"] > *',
                '.autocomplete-suggestion',
                '.pac-item',
                '.tt-suggestion',
                '[class*="suggestion"]:not(.disabled)',
                '[class*="dropdown"] li:not(.disabled)',
                'ul[class*="autocomplete"] li',
                '[class*="menu"] [class*="item"]',
                '[data-suggestion]',
                '.pca-item',
                '.address-suggestion'
            ];
            
            const suggestions = document.querySelectorAll(selectors.join(', '));
            const visible = Array.from(suggestions).filter(s => {
                const style = window.getComputedStyle(s);
                if (style.display === 'none' || style.visibility === 'hidden') return false;
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
            # Short pause before checking for Continue button
            await asyncio.sleep(0.5)
            # Assuming check_and_click_continue_in_viewport is defined elsewhere or will be added
            # continue_result = await check_and_click_continue_in_viewport(page)
            # if continue_result.get('clicked'):
            #     log(logger, 'info', 'Continue clicked after address, proceeding...', 'ADDRESS_FILL', 'RULE_BASED')
            await asyncio.sleep(0.2)
            return {'success': True}
        else:
            log(logger, 'info', 'No autocomplete suggestions found', 'ADDRESS_FILL', 'DOM')
            return {'success': False}
    except Exception as e:
        log(logger, 'warning', f'Autocomplete selection error: {e}', 'ADDRESS_FILL', 'DOM')
        return {'success': False}

async def wait_for_dependent_dropdown(page, timeout=5.0):
    """
    Waits for a dependent dropdown to appear or update after a selection.
    This is a heuristic approach, checking for changes in the number of options
    or the visibility of a new select element.
    """
    start_time = time.time()
    initial_select_count = len(await page.query_selector_all('select'))
    
    log(logger, 'info', f"Waiting for dependent dropdowns (initial count: {initial_select_count})...", 'ADDRESS_FILL', 'DOM')

    while time.time() - start_time < timeout:
        await asyncio.sleep(0.5) # Check every 0.5 seconds
        current_select_count = len(await page.query_selector_all('select'))
        
        if current_select_count > initial_select_count:
            log(logger, 'info', f"New dropdown detected (count: {current_select_count}). Dependent dropdown likely updated.", 'ADDRESS_FILL', 'DOM')
            return True
        
        # Also check if existing dropdowns have changed their options (e.g., state list updated)
        # This is more complex to implement robustly without knowing the specific dropdown.
        # For now, rely on new dropdowns or a general stability wait.
        
    log(logger, 'info', "Dependent dropdown wait timed out or no changes detected.", 'ADDRESS_FILL', 'DOM')
    return False

    return {'success': False, 'error': 'Max retries exceeded'}


async def interact_with_custom_dropdown(page, label_keywords, option_value):
    """
    Handle custom dropdowns (div/ul based) that require:
    1. Click trigger to open
    2. Scroll to find option
    3. Click option
    """
    try:
        log(logger, 'info', f"Attempting custom dropdown interaction for {label_keywords[0]}='{option_value}'", 'ADDRESS_FILL', 'DOM')
        
        # 1. Find the trigger element
        # Look for something that looks like a dropdown trigger near the label
        trigger = await page.evaluate_handle("""
            (keywords) => {
                const labels = Array.from(document.querySelectorAll('label'));
                for (const label of labels) {
                    if (keywords.some(k => label.textContent.toLowerCase().includes(k.toLowerCase()))) {
                        // Look for a sibling or child that acts as a trigger
                        // Common patterns: div[role="combobox"], div.select, button[aria-haspopup]
                        const container = label.parentElement;
                        const trigger = container.querySelector('[role="combobox"], [aria-haspopup], .select, .dropdown, .picker');
                        if (trigger) return trigger;
                        
                        // Or maybe the label target itself is a custom div
                        if (label.htmlFor) {
                            const target = document.getElementById(label.htmlFor);
                            if (target && target.tagName !== 'SELECT' && target.tagName !== 'INPUT') return target;
                        }
                    }
                }
                
                // Fallback: Look for any element with 'country' or keywords in class/id
                for (const kw of keywords) {
                    const el = document.querySelector(`[id*="${kw}"], [class*="${kw}"]`);
                    if (el && (el.getAttribute('role') === 'combobox' || el.classList.contains('select'))) return el;
                }
                return null;
            }
        """, label_keywords)
        
        if not trigger:
            log(logger, 'warning', "Could not find custom dropdown trigger", 'ADDRESS_FILL', 'DOM')
            return {'success': False}

        # 2. Click to open
        await trigger.scroll_into_view_if_needed()
        await trigger.click()
        await asyncio.sleep(0.5) # Wait for animation/render
        
        # 3. Find and select option
        # We look for the option text in the entire document (since it might be in a portal/overlay)
        # and ensure it's visible.
        
        # Try to type to filter if it's a combobox
        try:
            await page.keyboard.type(option_value[:3])
            await asyncio.sleep(0.5)
        except:
            pass

        # Find option element
        option_element = await page.evaluate_handle("""
            (text) => {
                // Helper to normalize
                const norm = t => t.toLowerCase().trim().replace(/[^a-z0-9]/g, '');
                const target = norm(text);
                
                // Look in common list containers
                const options = Array.from(document.querySelectorAll('[role="option"], li, .item, .option'));
                
                for (const opt of options) {
                    if (!opt.offsetParent) continue; // Skip invisible
                    
                    const optText = norm(opt.textContent);
                    if (optText === target || optText.includes(target)) {
                        return opt;
                    }
                }
                return null;
            }
        """, option_value)
        
        if option_element:
            # Scroll and click
            await option_element.scroll_into_view_if_needed()
            await option_element.click()
            log(logger, 'info', f"✓ Selected custom option '{option_value}'", 'ADDRESS_FILL', 'DOM')
            return {'success': True}
            
        log(logger, 'warning', f"Custom option '{option_value}' not found in list", 'ADDRESS_FILL', 'DOM')
        
        # Try clicking outside to close
        await page.mouse.click(0, 0)
        return {'success': False, 'error': 'Option not found'}
        
    except Exception as e:
        log(logger, 'error', f"Custom dropdown error: {e}", 'ADDRESS_FILL', 'DOM')
        return {'success': False, 'error': str(e)}


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
            
            target_select = None

            # First pass: Try to match by keywords
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
                    target_select = select
                    log(logger, 'info', f"Matched select by keywords: {select_info['label'] or select_info['name'] or select_info['id']}", 'ADDRESS_FILL', 'DOM')
                    break
            
            # Fallback: If no keyword match, try the first visible select
            if not target_select:
                log(logger, 'warning', f"No dropdown matched keywords {label_keywords}, trying first visible dropdown", 'ADDRESS_FILL', 'DOM')
                for select in all_selects:
                    is_visible = await select.is_visible()
                    if is_visible:
                        target_select = select
                        log(logger, 'info', f"Using first visible select: {await select.evaluate('el => el.name || el.id || el.outerHTML.substring(0, 50)')}", 'ADDRESS_FILL', 'DOM')
                        break
            
            # If standard select found, use it
            if target_select:
                # Check if this is a country field
                is_country = any(k in label_keywords[0].lower() for k in ['country', 'nation', 'region'])
                
                # Scroll into view
                await target_select.scroll_into_view_if_needed()
                
                # Get all options to find the best match
                options = await target_select.query_selector_all('option')
                
                # Map for common country codes/names if needed
                country_map = {
                    'US': ['United States', 'USA', 'US'],
                    'IN': ['India', 'IND', 'IN'],
                    'CA': ['Canada', 'CAN', 'CA'],
                    'GB': ['United Kingdom', 'UK', 'GB', 'Great Britain'],
                    'AU': ['Australia', 'AUS', 'AU']
                }
                
                option_norm = normalize_text(option_value)
                values_to_try = [option_value]
                
                # Try direct selection first (fastest)
                found_option = False
                for val in values_to_try:
                    try:
                        await target_select.select_option(value=val)
                        found_option = True
                        log(logger, 'info', f"✓ Selected by value: '{val}'", 'ADDRESS_FILL', 'DOM')
                        break
                    except:
                        try:
                            await target_select.select_option(label=val)
                            found_option = True
                            log(logger, 'info', f"✓ Selected by label: '{val}'", 'ADDRESS_FILL', 'DOM')
                            break
                        except:
                            pass
                
                # Fallback: Iterate options to find fuzzy match if direct selection failed
                if not found_option:
                    for option in options:
                        text = await option.text_content()
                        value = await option.get_attribute('value')
                        
                        if not value or value.strip() == '':
                            continue
                            
                        text_norm = normalize_text(text or '')
                        value_norm = normalize_text(value or '')
                        
                        matched_val = None
                        for try_value in values_to_try:
                            try_norm = normalize_text(try_value)
                            
                            # Exact match (case insensitive)
                            if (text.upper() == try_value.upper() or value.upper() == try_value.upper() or
                                text_norm == try_norm or value_norm == try_norm):
                                matched_val = value
                                break
                                
                            # Partial match
                            if len(try_norm) > 2 and (try_norm in text_norm or try_norm in value_norm):
                                matched_val = value
                                break
                        
                        if matched_val:
                            try:
                                await target_select.select_option(value=matched_val)
                                found_option = True
                                log(logger, 'info', f"✓ Selected by fuzzy match: '{text}' (value='{matched_val}')", 'ADDRESS_FILL', 'DOM')
                                break
                            except Exception as e:
                                log(logger, 'warning', f"Failed to select matched option: {e}", 'ADDRESS_FILL', 'DOM')

                if found_option:
                    # Trigger events to ensure page reacts
                    await asyncio.sleep(0.3)
                    await target_select.evaluate('el => el.dispatchEvent(new Event("change", {bubbles: true}))')
                    
                    # If this was a country selection, wait for dependent fields
                    if is_country:
                        log(logger, 'info', "Country selected, waiting for dependent fields...", 'ADDRESS_FILL', 'DOM')
                        await asyncio.sleep(1.0) # Give AJAX time to fire
                        await wait_for_dependent_dropdown(page)
                        await wait_for_page_stability(page)
                        
                    return {'success': True}
            
            # Fallback to Custom Dropdown Strategy if no select found or select failed
            log(logger, 'info', "Standard select failed or not found, trying custom dropdown strategy...", 'ADDRESS_FILL', 'DOM')
            custom_result = await interact_with_custom_dropdown(page, label_keywords, option_value)
            if custom_result['success']:
                return custom_result
            
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


async def select_cheapest_shipping_option(page, max_retries=3):
    """
    Find and select the cheapest shipping option (radio button)
    Returns: {'success': bool, 'selected_option': str, 'price': float}
    """
    for attempt in range(max_retries):
        # Reduced wait before retrying shipping selection
        await asyncio.sleep(0.5)
        try:
            log(logger, 'info', f"Selecting cheapest shipping option (attempt {attempt+1})", 'CHECKOUT', 'DOM')
            
            await wait_for_page_stability(page)
            
            # Find all shipping options (radio buttons)
            # We look for radio buttons inside containers that might have price text
            result = await page.evaluate("""
                () => {
                    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                    const options = [];
                    
                    radios.forEach(radio => {
                        if (!radio.offsetParent) return; // Skip invisible
                        
                        // Find container (label or parent div)
                        const label = document.querySelector(`label[for="${radio.id}"]`);
                        const parent = radio.closest('div, label, tr, li');
                        const container = label || parent;
                        
                        if (!container) return;
                        
                        const text = container.innerText || container.textContent || '';
                        const textLower = text.toLowerCase();
                        
                        // Look for price indicators
                        let price = 999999;
                        if (textLower.includes('free') || textLower.includes('$0.00')) {
                            price = 0;
                        } else {
                            // Extract price regex
                            const match = text.match(/[\\$£€](\\d+\\.\\d{2})/);
                            if (match) {
                                price = parseFloat(match[1]);
                            }
                        }
                        
                        options.push({
                            id: radio.id,
                            text: text.substring(0, 50),
                            price: price,
                            checked: radio.checked
                        });
                    });
                    
                    if (options.length === 0) return {found: false};
                    
                    // Sort by price ascending
                    options.sort((a, b) => a.price - b.price);
                    
                    const best = options[0];
                    const el = document.getElementById(best.id);
                    if (el) {
                        el.click();
                        return {found: true, selected: best};
                    }
                    return {found: false};
                }
            """)
            
            if result.get('found'):
                selected = result['selected']
                log(logger, 'info', f"✓ Selected cheapest shipping: {selected['text']} (${selected['price']})", 'CHECKOUT', 'DOM')
                await asyncio.sleep(1)
                return {'success': True, 'selected_option': selected['text'], 'price': selected['price']}
            
            log(logger, 'warning', "No shipping options found", 'CHECKOUT', 'DOM')
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                
        except Exception as e:
            log(logger, 'error', f"Error selecting shipping option: {e}", 'CHECKOUT', 'DOM')
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                
    return {'success': False, 'error': 'Failed to select shipping option'}


class CheckoutDOMFinder:
    """Wrapper class for Checkout DOM operations to maintain backward compatibility"""
    def __init__(self, page):
        self.page = page

    async def find_and_click_button(self, keywords, max_retries=3):
        return await find_and_click_button(self.page, keywords, max_retries)

    async def fill_input_field(self, label_keywords, value, max_retries=3):
        return await fill_input_field(self.page, label_keywords, value, max_retries)

    async def find_and_select_dropdown(self, label_keywords, option_value, max_retries=2):
        return await find_and_select_dropdown(self.page, label_keywords, option_value, max_retries)
        
    async def select_cheapest_shipping_option(self, max_retries=3):
        return await select_cheapest_shipping_option(self.page, max_retries)
        
    async def get_all_form_fields(self):
        return await get_all_form_fields(self.page)
        
    async def interact_with_custom_dropdown(self, label_keywords, option_value):
        return await interact_with_custom_dropdown(self.page, label_keywords, option_value)

    async def select_address_autocomplete(self):
        return await select_address_autocomplete(self.page)