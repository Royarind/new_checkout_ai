"""
Checkout Flow - Phase 2
Main orchestration for checkout process
Handles: checkout button, guest checkout, contact info, shipping address
"""

import asyncio
from datetime import datetime
from shared.logger_config import setup_logger, log
from phase2.checkout_dom_finder import (
    find_and_click_button,
    fill_input_field,
    find_and_select_dropdown
)
from shared.checkout_keywords import (
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
from shared.popup_dismisser import dismiss_popups
from phase2.checkout_state_detector import (
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
    Handles: flying modal with checkout button
    Returns: {'success': bool, 'error': str}
    """
    log(logger, 'info', 'Proceeding to checkout...', 'CHECKOUT', 'DOM')
    
    # Check for site-specific handler
    from special_sites import get_site_specific_checkout_handler
    handler = await get_site_specific_checkout_handler(page)
    if handler:
        log(logger, 'info', 'Using site-specific checkout handler', 'CHECKOUT', 'SITE_SPECIFIC')
        return await handler(page)
    
    # Wait for any flying modals to appear
    await asyncio.sleep(2)
    
    # Store current URL to detect navigation
    url_before = page.url
    log(logger, 'info', f"Current URL: {url_before}", 'CHECKOUT', 'DOM')
    
    # First try clicking cart icon to open cart drawer/modal
    log(logger, 'info', 'Looking for cart icon...', 'CHECKOUT', 'DOM')
    cart_opened = await page.evaluate("""
        () => {
            const cartSelectors = [
                '[class*="cart"][class*="icon"]', '[data-cart]', '[aria-label*="cart" i]',
                '[class*="bag"][class*="icon"]', '[aria-label*="bag" i]',
                'a[href*="/cart"]', 'a[href*="/bag"]', '.cart-link', '.bag-link'
            ];
            for (const sel of cartSelectors) {
                const el = document.querySelector(sel);
                if (el && el.offsetParent) {
                    el.click();
                    return true;
                }
            }
            return false;
        }
    """)
    if cart_opened:
        log(logger, 'info', 'Cart icon clicked, waiting for drawer...', 'CHECKOUT', 'DOM')
        await asyncio.sleep(2)
    
    # Try checkout button on modal/drawer (flying modal pattern)
    log(logger, 'info', 'Looking for checkout button...', 'CHECKOUT', 'DOM')
    result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=3)
    
    if result['success']:
        log(logger, 'info', 'Checkout button clicked on modal', 'CHECKOUT', 'DOM')
        await asyncio.sleep(3)
        
        # Check if we navigated to checkout or homepage
        url_after = page.url
        log(logger, 'info', f"URL after click: {url_after}", 'CHECKOUT', 'DOM')
        
        if 'checkout' in url_after.lower() or 'cart' not in url_after.lower():
            log(logger, 'info', 'Successfully navigated to checkout', 'CHECKOUT', 'DOM')
            return {'success': True}
        else:
            log(logger, 'warning', 'Clicked wrong button, still on cart/homepage', 'CHECKOUT', 'DOM')
            # Continue to try other methods
    
    # Try View Cart first then Checkout
    log(logger, 'info', 'Trying View Cart button...', 'CHECKOUT', 'DOM')
    view_cart_keywords = ['proceed to cart', 'view cart', 'go to cart', 'view bag', 'view basket']
    view_cart_result = await find_and_click_button(page, view_cart_keywords, max_retries=2)
    
    if view_cart_result['success']:
        log(logger, 'info', 'View Cart clicked, waiting for page...', 'CHECKOUT', 'DOM')
        await asyncio.sleep(3)
        result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=3)
        if result['success']:
            log(logger, 'info', 'Checkout button clicked', 'CHECKOUT', 'DOM')
            await asyncio.sleep(3)
            
            # Verify we're on checkout page
            url_final = page.url
            log(logger, 'info', f"Final URL: {url_final}", 'CHECKOUT', 'DOM')
            if 'checkout' in url_final.lower():
                return {'success': True}
            else: 
                log(logger, 'error', 'Not on checkout page after clicking', 'CHECKOUT', 'DOM')
                return {'success': False, 'error': 'Navigation to checkout failed'}
    
    log(logger, 'error', 'Failed to find checkout button', 'CHECKOUT', 'DOM')
    return {'success': False, 'error': 'Checkout button not found'}


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
        # Click continue after email
        await asyncio.sleep(1)
        continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=1)
        if continue_result['success']:
            await asyncio.sleep(2)
    
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
            # Wait for autocomplete
            await asyncio.sleep(2)
        
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
        continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=1)
        if continue_result['success']:
            await asyncio.sleep(2)
        return {'success': True}
    
    except Exception as e:
        log(logger, 'error', f"Shipping address error: {e}", 'ADDRESS_FILL', 'RULE_BASED')
        return {'success': False, 'errors': [str(e)]}


async def click_continue_if_needed(page):
    """
    Click continue/next button if checkout has multiple steps
    Returns: {'success': bool}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Looking for continue button...")
    
    result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=1)
    
    if result['success']:
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Continue button clicked")
        await asyncio.sleep(2)
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
            await asyncio.sleep(1)
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
        from phase2.ai_checkout_flow import run_ai_checkout_flow
        return await run_ai_checkout_flow(page, customer_data)
    
    # Legacy rule-based flow
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
        from agent.llm_client import LLMClient
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
