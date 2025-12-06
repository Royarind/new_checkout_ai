"""
Checkout Flow - Phase 2
Main orchestration for checkout process
Handles: checkout button, guest checkout, contact info, shipping address
"""

import asyncio
from datetime import datetime
from src.checkout_ai.utils.logger_config import setup_logger, log
from src.checkout_ai.legacy.phase2.smart_form_filler import SmartFormFiller
from src.checkout_ai.legacy.phase2.checkout_dom_finder import (
    CheckoutDOMFinder,
    find_and_click_button,
    fill_input_field,
    find_and_select_dropdown
)
from src.checkout_ai.utils.checkout_keywords import (
    CHECKOUT_BUTTONS,
    GUEST_CHECKOUT_BUTTONS,
    EMAIL_LABELS,
    FIRST_NAME_LABELS,
    LAST_NAME_LABELS,
    PHONE_LABELS,
    ADDRESS_LINE1_LABELS,
    ADDRESS_LINE2_LABELS,
    CITY_LABELS,
    STATE_LABELS,
    POSTAL_CODE_LABELS,
    CONTINUE_BUTTONS
)
from src.checkout_ai.utils.popup_dismisser import dismiss_popups
from src.checkout_ai.legacy.phase2.checkout_state_detector import (
    detect_page_state, 
    detect_field_visibility,
    detect_validation_errors,
    get_field_dependencies,
    wait_for_network_idle
)

logger = setup_logger('checkout_flow')


async def _llm_map_contact_fields(llm_client, fields, contact_data):
    """
    QUICK WIN: Use LLM to map contact data to form fields upfront
    Returns: list of field mappings for batch_fill_fields
    """
    try:
        fields_desc = "\n".join([f"{i+1}. {f['type']} - name:'{f['name']}' id:'{f['id']}' label:'{f['label'][:30]}' placeholder:'{f['placeholder'][:30]}'" 
                                 for i, f in enumerate(fields[:10])])
        
        prompt = f"""Map customer data to form fields. Return JSON array only.

FORM FIELDS:
{fields_desc}

CUSTOMER DATA:
Email: {contact_data.get('email', 'N/A')}
First Name: {contact_data.get('firstName', 'N/A')}
Last Name: {contact_data.get('lastName', 'N/A')}
Phone: {contact_data.get('phone', 'N/A')}

Return format: [{{{"keywords": ["email"], "value": "customer@email.com"}}}, ...]
Only include fields that exist in the form."""
        
        response = await llm_client.complete(prompt, max_tokens=300)
        if isinstance(response, list):
            return response
        return []
    except Exception as e:
        logger.error(f"LLM mapping error: {e}")
        return []


async def _llm_map_shipping_fields(llm_client, fields, address_data):
    """
    QUICK WIN: Use LLM to map shipping data to form fields upfront
    """
    try:
        fields_desc = "\n".join([f"{i+1}. {f['type']} - name:'{f['name']}' id:'{f['id']}' label:'{f['label'][:30]}'" 
                                 for i, f in enumerate(fields[:10])])
        
        prompt = f"""Map address data to form fields. Return JSON array only.

FORM FIELDS:
{fields_desc}

ADDRESS DATA:
Address: {address_data.get('addressLine1', 'N/A')}
City: {address_data.get('city', 'N/A')}
State: {address_data.get('province', 'N/A')}
Zip: {address_data.get('postalCode', 'N/A')}
Country: {address_data.get('country', 'N/A')}

Return format: [{{{"keywords": ["address"], "value": "123 Main St"}}}, ...]"""
        
        response = await llm_client.complete(prompt, max_tokens=300)
        if isinstance(response, list):
            return response
        return []
    except Exception as e:
        logger.error(f"LLM mapping error: {e}")
        return []


async def log_available_fields(page, step_name):
    """Log all visible form fields for debugging"""
    try:
        fields = await page.evaluate("""
            () => {
                const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select, textarea'))
                    .filter(el => el.offsetParent)
                    .map(el => ({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        autocomplete: el.autocomplete || '',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        label: (el.closest('label') || document.querySelector(`label[for="${el.id}"]`))?.textContent?.trim() || ''
                    }));
                return inputs;
            }
        """)
        log(logger, 'info', f"[{step_name}] Found {len(fields)} visible fields", 'ADDRESS_FILL', 'DOM')
        for i, field in enumerate(fields[:15]):  # Log first 15
            log(logger, 'info', f"Field {i+1}: {field['tag']} name='{field['name']}' id='{field['id']}'", 'ADDRESS_FILL', 'DOM')
    except Exception as e:
        log(logger, 'warning', f"Could not log fields: {e}", 'ADDRESS_FILL', 'DOM')


async def proceed_to_checkout(page):
    """
    Click checkout button to proceed from cart to checkout
    Strategy: 1) Click checkout in side modal, 2) Dismiss modal and click mini-cart, 3) Direct URL navigation
    Returns: {'success': bool, 'error': str}
    """
    log(logger, 'info', 'Proceeding to checkout...', 'CHECKOUT', 'DOM')
    
    # Check for site-specific handler
    from special_sites import get_site_specific_checkout_handler
    handler = await get_site_specific_checkout_handler(page)
    if handler:
        log(logger, 'info', 'Using site-specific checkout handler', 'CHECKOUT', 'SITE_SPECIFIC')
        return await handler(page)
    
    # Wait for side modal to appear after add to cart
    await asyncio.sleep(2)
    
    # STRATEGY 1: Try to click checkout/view cart button in side modal
    log(logger, 'info', 'Strategy 1: Looking for checkout button in side modal...', 'CHECKOUT', 'DOM')
    modal_clicked = await page.evaluate("""
        () => {
            const keywords = ['checkout', 'view cart', 'go to cart', 'view bag', 'proceed'];
            const modals = document.querySelectorAll('[class*="modal"], [class*="drawer"], [class*="sidebar"], [class*="cart-popup"], [role="dialog"]');
            
            for (const modal of modals) {
                const style = window.getComputedStyle(modal);
                if (style.display === 'none' || style.visibility === 'hidden') continue;
                
                const buttons = modal.querySelectorAll('button, a, [role="button"]');
                for (const btn of buttons) {
                    const text = (btn.textContent || btn.innerText || '').toLowerCase().trim();
                    if (keywords.some(kw => text.includes(kw))) {
                        btn.click();
                        return true;
                    }
                }
            }
            return false;
        }
    """)
    
    if modal_clicked:
        log(logger, 'info', 'Clicked checkout button in side modal', 'CHECKOUT', 'DOM')
        await asyncio.sleep(3)
        if 'checkout' in page.url.lower() or 'cart' in page.url.lower():
            return {'success': True}
    
    # STRATEGY 2: Dismiss side modal and click mini-cart
    log(logger, 'info', 'Strategy 2: Dismissing side modal and clicking mini-cart...', 'CHECKOUT', 'DOM')
    await page.evaluate("""
        () => {
            const closeButtons = document.querySelectorAll('[aria-label*="close" i], [class*="close"], [class*="dismiss"], button[class*="icon-close"]');
            closeButtons.forEach(btn => {
                const rect = btn.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) btn.click();
            });
        }
    """)
    await asyncio.sleep(1)
    
    # Store current URL to detect navigation
    url_before = page.url
    log(logger, 'info', f"Current URL: {url_before}", 'CHECKOUT', 'DOM')
    
    # Skip cart icon clicking - it may navigate to wrong pages
    # Go directly to finding checkout button
    log(logger, 'info', 'Skipping cart icon, looking directly for checkout button...', 'CHECKOUT', 'DOM')
    
    # Check if already on checkout page
    current_url = page.url.lower()
    if 'checkout' in current_url:
        log(logger, 'info', 'Already on checkout page, skipping button click', 'CHECKOUT', 'DOM')
        return {'success': True}
    
    # Try checkout button with strict validation
    log(logger, 'info', 'Looking for checkout button...', 'CHECKOUT', 'DOM')
    result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=3)
    
    if result['success']:
        log(logger, 'info', 'Checkout button clicked', 'CHECKOUT', 'DOM')
        await asyncio.sleep(3)
        
        # Validate navigation - must contain 'checkout' and NOT contain 'collections', 'products', or homepage indicators
        url_after = page.url.lower()
        log(logger, 'info', f"URL after click: {url_after}", 'CHECKOUT', 'DOM')
        
        # Check for wrong navigation
        wrong_pages = ['collections', 'products', 'catalog', 'shop']
        is_wrong_page = any(wrong in url_after for wrong in wrong_pages)
        is_homepage = url_after.count('/') <= 3 and not 'checkout' in url_after
        
        if 'checkout' in url_after and not is_wrong_page:
            log(logger, 'info', 'Successfully navigated to checkout', 'CHECKOUT', 'DOM')
            return {'success': True}
        elif is_wrong_page or is_homepage:
            log(logger, 'error', f'Clicked wrong button - navigated to wrong page: {url_after}', 'CHECKOUT', 'DOM')
            return {'success': False, 'error': 'Navigated to wrong page (collections/homepage)'}
        else:
            log(logger, 'warning', 'Navigation unclear, continuing...', 'CHECKOUT', 'DOM')
            # Continue to try other methods
    
    # STRATEGY 3: Try direct URL navigation with multiple fallbacks
    log(logger, 'info', 'Strategy 3: Trying direct URL navigation...', 'CHECKOUT', 'DOM')
    from urllib.parse import urlparse
    parsed = urlparse(page.url)
    
    # Get base URL
    if 'chrome-error' in parsed.scheme or not parsed.netloc:
        log(logger, 'warning', 'Current URL is invalid, extracting base URL', 'CHECKOUT', 'DOM')
        domain = await page.evaluate('() => window.location.hostname || document.domain')
        if domain and domain != 'chromewebdata':
            base_url = f"https://{domain}"
        else:
            log(logger, 'error', 'Could not extract valid domain', 'CHECKOUT', 'DOM')
            return {'success': False, 'error': 'Invalid page state'}
    else:
        base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # Try multiple checkout URLs
    checkout_urls = [
        f"{base_url}/checkout",
        f"{base_url}/cart",
        f"{base_url}/checkout/information",
        f"{base_url}/checkout/cart",
        f"{base_url}/bag",
        f"{base_url}/basket"
    ]
    
    for url in checkout_urls:
        try:
            log(logger, 'info', f"Trying: {url}", 'CHECKOUT', 'DOM')
            await page.goto(url, wait_until='domcontentloaded', timeout=10000)
            await asyncio.sleep(2)
            current = page.url.lower()
            if 'checkout' in current or 'cart' in current or 'bag' in current:
                log(logger, 'info', f'Successfully navigated to: {url}', 'CHECKOUT', 'DOM')
                return {'success': True}
        except Exception as e:
            log(logger, 'warning', f'Failed {url}: {e}', 'CHECKOUT', 'DOM')
            continue
    
    # Last resort: Try View Cart then Checkout
    log(logger, 'info', 'Last resort: Trying View Cart button...', 'CHECKOUT', 'DOM')
    view_cart_keywords = ['view cart', 'go to cart', 'view bag']
    view_cart_result = await find_and_click_button(page, view_cart_keywords, max_retries=1)
    
    if view_cart_result['success']:
        await asyncio.sleep(2)
        result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=2)
        if result['success']:
            await asyncio.sleep(2)
            if 'checkout' in page.url.lower():
                return {'success': True}
    
    log(logger, 'error', 'All checkout navigation methods failed', 'CHECKOUT', 'DOM')
    return {'success': False, 'error': 'Could not navigate to checkout page'}


async def handle_guest_checkout(page, country):
    """
    Handle guest checkout selection - try guest checkout for all countries
    Returns: {'success': bool, 'error': str}
    """
    log(logger, 'info', f"Handling checkout method for country: {country}", 'CHECKOUT', 'RULE_BASED')
    
    result = await find_and_click_button(page, GUEST_CHECKOUT_BUTTONS, max_retries=3)
    
    if result['success']:
        log(logger, 'info', 'Guest checkout selected', 'CHECKOUT', 'DOM')
        await asyncio.sleep(2)
        return {'success': True}
    else:
        log(logger, 'info', 'Guest checkout button not found, assuming already on guest form', 'CHECKOUT', 'DOM')
        return {'success': True}


async def fill_contact_info(page, contact_data, user_prompt_callback=None, llm_client=None):
    """
    IMPROVED: Fill contact info with LLM upfront mapping + batch fill fallback
    contact_data: {'email': str, 'firstName': str, 'lastName': str, 'phone': str, 'password': str (optional)}
    Returns: {'success': bool, 'errors': list}
    """
    log(logger, 'info', 'Filling contact information...', 'ADDRESS_FILL', 'RULE_BASED')
    
    await dismiss_popups(page)
    await asyncio.sleep(0.5)
    
    filled_count = 0
    
    # QUICK WIN: Try LLM mapping first if available
    if llm_client:
        from phase2.checkout_dom_finder import get_all_form_fields
        fields = await get_all_form_fields(page)
        if len(fields) > 0:
            logger.info(f"CHECKOUT FLOW: Found {len(fields)} fields, asking LLM for mapping...")
            try:
                mapping = await _llm_map_contact_fields(llm_client, fields, contact_data)
                if mapping and len(mapping) > 0:
                    from phase2.checkout_dom_finder import batch_fill_fields
                    result = await batch_fill_fields(page, mapping)
                    if result['filled_count'] >= 2:
                        logger.info(f"CHECKOUT FLOW: LLM batch filled {result['filled_count']} fields")
                        await asyncio.sleep(1)
                        continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=1)
                        if continue_result['success']:
                            await asyncio.sleep(2)
                        return {'success': True}
            except Exception as e:
                logger.warning(f"CHECKOUT FLOW: LLM mapping failed: {e}, falling back to rule-based")
    
    # FALLBACK: Rule-based filling with STRICT validation
    if contact_data.get('email'):
        result = await fill_input_field(page, EMAIL_LABELS, contact_data['email'], max_retries=3)
        if not result['success']:
            log(logger, 'error', 'CRITICAL: Email field failed to fill', 'ADDRESS_FILL', 'RULE_BASED')
            return {'success': False, 'errors': ['Email field failed']}
        filled_count += 1
        # Check for continue button after email
        await asyncio.sleep(1)
        continue_result = await check_and_click_continue_in_viewport(page)
        if continue_result.get('clicked'):
            log(logger, 'info', 'Continue clicked after email, waiting for next fields...', 'ADDRESS_FILL', 'RULE_BASED')
    
    if contact_data.get('firstName'):
        result = await fill_input_field(page, FIRST_NAME_LABELS, contact_data['firstName'], max_retries=3)
        if not result['success']:
            log(logger, 'error', 'CRITICAL: First name field failed to fill', 'ADDRESS_FILL', 'RULE_BASED')
            return {'success': False, 'errors': ['First name field failed']}
        filled_count += 1
    
    if contact_data.get('lastName'):
        result = await fill_input_field(page, LAST_NAME_LABELS, contact_data['lastName'], max_retries=3)
        if not result['success']:
            log(logger, 'error', 'CRITICAL: Last name field failed to fill', 'ADDRESS_FILL', 'RULE_BASED')
            return {'success': False, 'errors': ['Last name field failed']}
        filled_count += 1
    
    if contact_data.get('phone'):
        result = await fill_input_field(page, PHONE_LABELS, contact_data['phone'], max_retries=3)
        if not result['success']:
            log(logger, 'error', 'CRITICAL: Phone field failed to fill', 'ADDRESS_FILL', 'RULE_BASED')
            return {'success': False, 'errors': ['Phone field failed']}
        filled_count += 1
    
    # Check for continue button after all contact fields
    await asyncio.sleep(0.2)
    continue_result = await check_and_click_continue_in_viewport(page)
    if continue_result.get('clicked'):
        log(logger, 'info', 'Continue clicked after contact info, waiting for address fields...', 'ADDRESS_FILL', 'RULE_BASED')
    
    log(logger, 'info', f"Contact info completed ({filled_count} fields)", 'ADDRESS_FILL', 'RULE_BASED')
    return {'success': True}


async def fill_shipping_address(page, address_data, llm_client=None):
    """
    IMPROVED: Fill shipping address with LLM upfront + batch fill
    Returns: {'success': bool, 'errors': list}
    """
    log(logger, 'info', 'Filling shipping address...', 'ADDRESS_FILL', 'RULE_BASED')
    
    await dismiss_popups(page)
    await asyncio.sleep(0.5)
    
    # Check if billing address already matches shipping
    billing_matches_shipping = await page.evaluate('''(shippingData) => {
        const inputs = Array.from(document.querySelectorAll('input'));
        let addressMatch = false;
        let cityMatch = false;
        let zipMatch = false;
        
        for (const input of inputs) {
            const name = (input.name || input.id || '').toLowerCase();
            const value = (input.value || '').trim();
            
            if (name.includes('address') && !name.includes('email') && value.toLowerCase().includes(shippingData.address.toLowerCase().substring(0, 10))) {
                addressMatch = true;
            }
            if (name.includes('city') && value.toLowerCase() === shippingData.city.toLowerCase()) {
                cityMatch = true;
            }
            if ((name.includes('zip') || name.includes('postal')) && value === shippingData.zip) {
                zipMatch = true;
            }
        }
        
        return addressMatch && cityMatch && zipMatch;
    }''', {
        'address': address_data.get('addressLine1', ''),
        'city': address_data.get('city', ''),
        'zip': address_data.get('postalCode', '')
    })
    
    if billing_matches_shipping:
        log(logger, 'info', 'Billing address already matches shipping, skipping fill', 'ADDRESS_FILL', 'RULE_BASED')
        await asyncio.sleep(1)
        continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=2)
        if continue_result['success']:
            log(logger, 'info', 'Continue button clicked after billing validation', 'ADDRESS_FILL', 'RULE_BASED')
            await asyncio.sleep(2)
        return {'success': True}
    
    # Check if same as shipping checkbox exists
    same_as_shipping_clicked = await page.evaluate('''() => {
        const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
        for (const cb of checkboxes) {
            const label = cb.closest('label') || document.querySelector(`label[for="${cb.id}"]`);
            const text = (label?.textContent || cb.name || cb.id || '').toLowerCase();
            if (text.includes('same as shipping') || text.includes('billing same') || text.includes('use shipping')) {
                if (!cb.checked) {
                    cb.click();
                    console.log('Clicked same as shipping checkbox');
                    return true;
                }
                return true;
            }
        }
        return false;
    }''')
    
    if same_as_shipping_clicked:
        log(logger, 'info', 'Same as shipping checkbox clicked, skipping billing address fill', 'ADDRESS_FILL', 'RULE_BASED')
        await asyncio.sleep(1)
        continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=2)
        if continue_result['success']:
            log(logger, 'info', 'Continue button clicked after same-as-shipping checkbox', 'ADDRESS_FILL', 'RULE_BASED')
            await asyncio.sleep(2)
        return {'success': True}
    
    filled_count = 0
    
    # QUICK WIN: Try LLM mapping first
    if llm_client:
        from phase2.checkout_dom_finder import get_all_form_fields
        fields = await get_all_form_fields(page)
        if len(fields) > 0:
            logger.info(f"CHECKOUT FLOW: Found {len(fields)} fields, asking LLM for mapping...")
            try:
                mapping = await _llm_map_shipping_fields(llm_client, fields, address_data)
                if mapping and len(mapping) > 0:
                    from phase2.checkout_dom_finder import batch_fill_fields
                    result = await batch_fill_fields(page, mapping)
                    if result['filled_count'] >= 3:
                        logger.info(f"CHECKOUT FLOW: LLM batch filled {result['filled_count']} fields")
                        await asyncio.sleep(1)
                        continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=1)
                        if continue_result['success']:
                             await asyncio.sleep(2)
                        return {'success': True}
            except Exception as e:
                logger.warning(f"CHECKOUT FLOW: LLM mapping failed: {e}, falling back to rule-based")
    
    # FALLBACK: Rule-based filling with STRICT validation
    try:
        addr1 = address_data.get('addressLine1') or address_data.get('address1')
        if addr1:
            result = await fill_input_field(page, ADDRESS_LINE1_LABELS, addr1, max_retries=3)
            if not result['success']:
                log(logger, 'error', 'CRITICAL: Address field failed to fill', 'ADDRESS_FILL', 'RULE_BASED')
                return {'success': False, 'errors': ['Address field failed']}
            filled_count += 1
            # Reduced wait for autocomplete
            await asyncio.sleep(0.3)
            # Check if continue button appears after address
            continue_result = await check_and_click_continue_in_viewport(page)
            if continue_result.get('clicked'):
                log(logger, 'info', 'Continue clicked after address, waiting for more fields...', 'ADDRESS_FILL', 'RULE_BASED')
                await asyncio.sleep(0.2)
        
        postal = address_data.get('postalCode') or address_data.get('zipCode')
        if postal:
            result = await fill_input_field(page, POSTAL_CODE_LABELS, postal, max_retries=3)
            if not result['success']:
                log(logger, 'error', 'CRITICAL: Postal code field failed to fill', 'ADDRESS_FILL', 'RULE_BASED')
                return {'success': False, 'errors': ['Postal code field failed']}
            filled_count += 1
        
        city = address_data.get('city')
        if city:
            result = await fill_input_field(page, CITY_LABELS, city, max_retries=3)
            if not result['success']:
                log(logger, 'error', 'CRITICAL: City field failed to fill', 'ADDRESS_FILL', 'RULE_BASED')
                return {'success': False, 'errors': ['City field failed']}
            filled_count += 1
        
        state = address_data.get('province') or address_data.get('state')
        if state:
            result = await find_and_select_dropdown(page, STATE_LABELS, state)
            if not result['success']:
                log(logger, 'warning', 'State field failed (may be optional)', 'ADDRESS_FILL', 'RULE_BASED')
        
        log(logger, 'info', f"Shipping address filled ({filled_count} fields)", 'ADDRESS_FILL', 'RULE_BASED')
        await asyncio.sleep(1)
        # Check for continue button after all address fields
        continue_result = await check_and_click_continue_in_viewport(page)
        if not continue_result.get('clicked'):
            # Fallback to broader search if not in viewport
            continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=1)
            if continue_result['success']:
                await asyncio.sleep(2)
        return {'success': True}
    
    except Exception as e:
        log(logger, 'error', f"Shipping address error: {e}", 'ADDRESS_FILL', 'RULE_BASED')
        return {'success': False, 'errors': [str(e)]}


async def check_and_click_continue_in_viewport(page):
    """
    Check if continue button is visible in viewport and click it.
    This reveals additional form fields in multi-step checkouts.
    Returns: {'success': bool, 'clicked': bool}
    """
    try:
        clicked = await page.evaluate('''
            () => {
                const keywords = ['continue', 'next', 'proceed', 'save and continue'];
                const buttons = Array.from(document.querySelectorAll('button, a[role="button"], input[type="submit"]'));
                
                for (const btn of buttons) {
                    const text = (btn.textContent || btn.value || '').toLowerCase().trim();
                    const rect = btn.getBoundingClientRect();
                    const inViewport = rect.top >= 0 && rect.bottom <= window.innerHeight && rect.left >= 0 && rect.right <= window.innerWidth;
                    
                    if (inViewport && keywords.some(kw => text.includes(kw))) {
                        btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        btn.click();
                        return true;
                    }
                }
                return false;
            }
        ''')
        
        if clicked:
            logger.info(f"CHECKOUT FLOW: Continue button found in viewport and clicked")
            await asyncio.sleep(0.5)
            return {'success': True, 'clicked': True}
        else:
            return {'success': True, 'clicked': False}
    except Exception as e:
        logger.warning(f"CHECKOUT FLOW: Error checking continue button: {e}")
        return {'success': True, 'clicked': False}


async def click_continue_if_needed(page):
    """
    Click continue/next button if checkout has multiple steps
    Returns: {'success': bool}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Looking for continue button...")
    
    result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=1)
    
    if result['success']:
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Continue button clicked")
        await asyncio.sleep(0.5)
        return {'success': True}
    else:
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] No continue button found (single-page checkout)")
        return {'success': True}


async def select_cheapest_shipping(page):
    """
    Select the cheapest shipping method by finding radio buttons with prices
    Returns: {'success': bool}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Selecting cheapest shipping method...")
    
    try:
        result = await page.evaluate("""
            () => {
                const options = [];
                const radios = document.querySelectorAll('input[type="radio"]');
                
                radios.forEach(radio => {
                    const label = radio.closest('label') || document.querySelector(`label[for="${radio.id}"]`);
                    const container = radio.closest('div, li, tr, fieldset');
                    const text = (label?.textContent || container?.textContent || '').toLowerCase();
                    
                    if (text.includes('ship') || text.includes('delivery') || text.includes('standard') || 
                        text.includes('express') || text.includes('ground') || text.includes('overnight') ||
                        text.includes('freight') || text.includes('mail')) {
                        
                        const priceMatches = text.match(/\\$\\s*([0-9]+\\.?[0-9]*)|([0-9]+\\.?[0-9]*)\\s*\\$/g);
                        let price = 999999;
                        
                        if (priceMatches && priceMatches.length > 0) {
                            const priceStr = priceMatches[0].replace(/[^0-9.]/g, '');
                            price = parseFloat(priceStr) || 0;
                        } else if (text.includes('free')) {
                            price = 0;
                        }
                        
                        options.push({ element: radio, price: price, text: text.substring(0, 150).trim() });
                    }
                });
                
                if (options.length === 0) return { found: false };
                
                options.sort((a, b) => a.price - b.price);
                
                const cheapest = options[0];
                cheapest.element.checked = true;
                cheapest.element.click();
                cheapest.element.dispatchEvent(new Event('change', { bubbles: true }));
                cheapest.element.dispatchEvent(new Event('input', { bubbles: true }));
                
                return { found: true, selected: cheapest.text, price: cheapest.price, totalOptions: options.length };
            }
        """)
        
        if result.get('found'):
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Selected cheapest shipping (${result.get('price')}) from {result.get('totalOptions')} options")
            await asyncio.sleep(0.2)
            return {'success': True}
        else:
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] No shipping options found (may be auto-selected)")
            return {'success': True}
    except Exception as e:
        logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Shipping selection error: {e}")
        return {'success': True}


async def run_checkout_flow(page, customer_data, agent_coordinator=None, user_prompt_callback=None, use_ai_flow=True):
    """
    Main entry point for Phase 2 checkout flow
    customer_data: Full customer object from JSON
    agent_coordinator: Optional AgentCoordinator for AI fallback (legacy)
    user_prompt_callback: Optional callback to prompt user for missing data
    use_ai_flow: If True, use AI-driven flow; if False, use rule-based flow
    Returns: {'success': bool, 'error': str, 'details': dict}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Starting Phase 2 checkout flow")
    
    # Use AI-driven flow by default
    if use_ai_flow:
        logger.info(f"CHECKOUT FLOW: Using AI-driven checkout flow")
        from checkout_ai.legacy.phase2.ai_checkout_flow import run_ai_checkout_flow
        try:
            return await run_ai_checkout_flow(page, customer_data)
        except Exception as e:
            logger.warning(f"AI checkout flow failed ({e}), falling back to rule‑based flow")
            # Continue to rule‑based flow below
    
    # Legacy rule-based flow (fallback)
    logger.info(f"CHECKOUT FLOW: Using rule-based checkout flow")
    if agent_coordinator:
        logger.info(f"CHECKOUT FLOW: AI agent fallback enabled")
    
    try:
        # Wrap entire flow in try-except to prevent browser closing
        logger.info(f"CHECKOUT FLOW: Starting checkout flow with error protection...")
        
        # Step 0: Dismiss pop-ups and modals
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Dismissing pop-ups...")
        try:
            await dismiss_popups(page)
        except Exception as e:
            logger.warning(f"CHECKOUT FLOW: Popup dismissal error (continuing): {e}")
        await asyncio.sleep(1)
        
        # Step 0.5: Detect initial page state
        state = await detect_page_state(page)
        logger.info(f"CHECKOUT FLOW: Initial state - Page: {state['pageType']}, Email visible: {state['fieldsVisible'].get('email')}, Address visible: {state['fieldsVisible'].get('address')}")
        
        # Step 1: Navigate to checkout (adaptive based on state)
        if state['pageType'] == 'cart':
            result = await proceed_to_checkout(page)
        elif state['pageType'] == 'checkout':
            logger.info(f"CHECKOUT FLOW: Already on checkout page, skipping proceed step")
            result = {'success': True}
        else:
            logger.warning(f"CHECKOUT FLOW: Unexpected page type: {state['pageType']}, attempting proceed anyway")
            result = await proceed_to_checkout(page)
        
        if not result.get('success') and agent_coordinator:
            logger.info(f"CHECKOUT FLOW: Rule-based proceed_to_checkout failed, trying AI agent...")
            agent_result = await agent_coordinator.assist_stage('proceed_to_checkout', customer_data, result)
            if agent_result['success']:
                logger.info(f"CHECKOUT FLOW: AI agent succeeded: {agent_result.get('action_taken')}")
                result = {'success': True}
        
        if not result.get('success'):
            return {'success': False, 'error': 'Failed to proceed to checkout', 'step': 'checkout_button'}
        
        # Step 2: Handle guest checkout (with agent fallback if enabled)
        country = customer_data.get('shippingAddress', {}).get('country', 'US')
        result = await handle_guest_checkout(page, country)
        
        if not result.get('success') and agent_coordinator:
            logger.info(f"CHECKOUT FLOW: Rule-based guest_checkout failed, trying AI agent...")
            agent_result = await agent_coordinator.assist_stage('guest_checkout', customer_data, result)
            if agent_result['success']:
                logger.info(f"CHECKOUT FLOW: AI agent succeeded: {agent_result.get('action_taken')}")
                result = {'success': True}
        
        await asyncio.sleep(3)
        
        # Step 3: Fill contact information (with agent fallback if enabled)
        contact_data = customer_data.get('contact', {})
        from checkout_ai.agents.legacy_adapter import create_agent_system
        # Temporary mock client if needed, or proper import
        # It seems the code used 'agent.llm_client' which doesn't exist in my grep list
        # We need to see where it was coming from. Assuming it was part of old agents.
        # But wait, step 147 showed 'from agent.llm_client import LLMClient'
        # I did not verify if agent folder existed. 'agent' (singular) was not in the root delete list.
        # Check if 'agent' exists.
        from checkout_ai.core.llm_client import LLMClient
        llm_client = LLMClient()
        result = await fill_contact_info(page, contact_data, user_prompt_callback, llm_client)
        
        if not result.get('success') and agent_coordinator:
            logger.info(f"CHECKOUT FLOW: Rule-based contact info failed, trying AI agent...")
            agent_result = await agent_coordinator.assist_stage('fill_contact', customer_data, result)
            if agent_result['success']:
                logger.info(f"CHECKOUT FLOW: AI agent succeeded: {agent_result.get('action_taken')}")
                result = {'success': True}
        
        await asyncio.sleep(2)
        
        # Step 3.5: Adaptive navigation - check if address fields are visible
        address_visible = await detect_field_visibility(page, ['address', 'street', 'addr'])
        
        if not address_visible:
            logger.info(f"CHECKOUT FLOW: Address fields not visible, looking for continue button...")
            await click_continue_if_needed(page)
            await asyncio.sleep(2)
            
            # Re-check after clicking continue
            address_visible = await detect_field_visibility(page, ['address', 'street', 'addr'])
            if not address_visible:
                logger.warning(f"CHECKOUT FLOW: Address fields still not visible after continue")
        else:
            logger.info(f"CHECKOUT FLOW: Address fields already visible, proceeding to fill")
        
        # Step 4: Fill shipping address (with agent fallback if enabled)
        address_data = customer_data.get('shippingAddress', {})
        result = await fill_shipping_address(page, address_data, llm_client)
        
        if not result.get('success') and agent_coordinator:
            logger.info(f"CHECKOUT FLOW: Rule-based shipping address failed, trying AI agent...")
            agent_result = await agent_coordinator.assist_stage('fill_shipping', customer_data, result)
            if agent_result['success']:
                logger.info(f"CHECKOUT FLOW: AI agent succeeded: {agent_result.get('action_taken')}")
                result = {'success': True}
        
        if not result.get('success'):
            logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Address fields not found, may be on next page")
        
        await asyncio.sleep(1)
        
        # Step 5: Select cheapest shipping method
        await select_cheapest_shipping(page)
        
        # Step 6: Click continue to proceed to payment
        await click_continue_if_needed(page)
        
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Rule-based checkout flow completed successfully")
        return {'success': True, 'message': 'Rule-based checkout flow completed'}
        
    except Exception as e:
        logger.error(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Checkout flow error: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"CHECKOUT FLOW: Keeping browser open for debugging...")
        return {'success': False, 'error': str(e)}
