"""
Checkout Flow - Phase 2
Main orchestration for checkout process
Handles: checkout button, guest checkout, contact info, shipping address
"""

import asyncio
import logging
from datetime import datetime
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

logger = logging.getLogger(__name__)


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
        logger.info(f"CHECKOUT FLOW: [{step_name}] Found {len(fields)} visible fields:")
        for i, field in enumerate(fields[:15]):  # Log first 15
            logger.info(f"  Field {i+1}: {field['tag']} name='{field['name']}' id='{field['id']}' placeholder='{field['placeholder']}' label='{field['label'][:50]}'")
    except Exception as e:
        logger.warning(f"CHECKOUT FLOW: Could not log fields: {e}")


async def proceed_to_checkout(page):
    """
    Click checkout button to proceed from cart to checkout
    Handles: flying modal with checkout button
    Returns: {'success': bool, 'error': str}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Proceeding to checkout...")
    
    # Wait for any flying modals to appear
    await asyncio.sleep(2)
    
    # Try checkout button on modal first (flying modal pattern)
    logger.info(f"CHECKOUT FLOW: Looking for checkout button on modal...")
    result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=3)
    
    if result['success']:
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Checkout button clicked on modal")
        await asyncio.sleep(2)
        return {'success': True}
    
    # If not found, try View Cart first then Checkout
    logger.info(f"CHECKOUT FLOW: Trying View Cart button...")
    view_cart_keywords = ['proceed to cart', 'view cart', 'go to cart', 'view bag', 'view basket']
    view_cart_result = await find_and_click_button(page, view_cart_keywords, max_retries=2)
    
    if view_cart_result['success']:
        logger.info(f"CHECKOUT FLOW: View Cart clicked, waiting for page...")
        await asyncio.sleep(3)
        result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=3)
        if result['success']:
            logger.info(f"CHECKOUT FLOW: Checkout button clicked")
            await asyncio.sleep(2)
            return {'success': True}
    
    logger.error(f"CHECKOUT FLOW: Failed to find checkout button")
    return {'success': False, 'error': 'Checkout button not found'}


async def handle_guest_checkout(page, country):
    """
    Handle guest checkout selection - try guest checkout for all countries
    Returns: {'success': bool, 'error': str}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Handling checkout method for country: {country}")
    
    result = await find_and_click_button(page, GUEST_CHECKOUT_BUTTONS, max_retries=3)
    
    if result['success']:
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Guest checkout selected")
        await asyncio.sleep(2)
        return {'success': True}
    else:
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Guest checkout button not found, assuming already on guest form")
        return {'success': True}


async def fill_contact_info(page, contact_data):
    """
    Fill contact information form
    contact_data: {'email': str, 'firstName': str, 'lastName': str, 'phone': str}
    Returns: {'success': bool, 'errors': list}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filling contact information...")
    await log_available_fields(page, "CONTACT_INFO")
    
    errors = []
    filled_count = 0
    
    # Check which fields are actually visible
    email_visible = await detect_field_visibility(page, ['email', 'e-mail'])
    name_visible = await detect_field_visibility(page, ['name', 'first', 'last'])
    
    logger.info(f"CHECKOUT FLOW: Contact fields detected - Email: {email_visible}, Name: {name_visible}")
    
    # Fill email first (often triggers form expansion)
    if contact_data.get('email') and email_visible:
        result = await fill_input_field(page, EMAIL_LABELS, contact_data['email'])
        if result['success']:
            filled_count += 1
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filled email")
            await asyncio.sleep(1)
            # Click continue after email
            continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=1)
            if continue_result['success']:
                logger.info(f"CHECKOUT FLOW: Continue clicked after email")
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(1)
        else:
            logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Email field not found")
            errors.append(f"Email: {result.get('error')}")
        await asyncio.sleep(1.5)
    elif contact_data.get('email') and not email_visible:
        logger.info(f"CHECKOUT FLOW: Email field not visible yet, may appear after other actions")
        errors.append("Email: Field not visible on current page")
    
    # Try separate first/last name fields first
    name_filled = False
    if contact_data.get('firstName'):
        result = await fill_input_field(page, FIRST_NAME_LABELS, contact_data['firstName'])
        if result['success']:
            filled_count += 1
            name_filled = True
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filled first name")
        else:
            logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] First name field not found")
        await asyncio.sleep(1)
    
    if contact_data.get('lastName'):
        result = await fill_input_field(page, LAST_NAME_LABELS, contact_data['lastName'])
        if result['success']:
            filled_count += 1
            name_filled = True
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filled last name")
        else:
            logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Last name field not found")
        await asyncio.sleep(1)
    
    # If separate fields didn't work, try combined name field
    if not name_filled:
        full_name = f"{contact_data.get('firstName', '')} {contact_data.get('lastName', '')}".strip()
        if full_name:
            name_labels = ['name', 'full name', 'your name']
            result = await fill_input_field(page, name_labels, full_name)
            if result['success']:
                filled_count += 1
                logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filled combined name field")
            else:
                logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Combined name field not found")
            await asyncio.sleep(0.5)
    
    # Fill phone (optional)
    if contact_data.get('phone'):
        result = await fill_input_field(page, PHONE_LABELS, contact_data['phone'])
        if result['success']:
            filled_count += 1
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filled phone")
        else:
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Phone field not found (optional)")
        await asyncio.sleep(0.5)
    
    # Success if at least email was filled
    if filled_count > 0:
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Contact information filled ({filled_count} fields)")
        return {'success': True}
    
    logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Contact info errors: {errors}")
    return {'success': False, 'errors': errors}


async def fill_shipping_address(page, address_data):
    """
    Fill shipping address form
    address_data: {'addressLine1': str, 'addressLine2': str, 'city': str, 'province': str, 'postalCode': str}
    Returns: {'success': bool, 'errors': list}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filling shipping address...")
    logger.info(f"CHECKOUT FLOW: Address data: {address_data}")
    await log_available_fields(page, "SHIPPING_ADDRESS")
    
    # Check which address fields are visible
    address_visible = await detect_field_visibility(page, ['address', 'street'])
    city_visible = await detect_field_visibility(page, ['city', 'town'])
    zip_visible = await detect_field_visibility(page, ['zip', 'postal'])
    
    logger.info(f"CHECKOUT FLOW: Address fields detected - Address: {address_visible}, City: {city_visible}, Zip: {zip_visible}")
    
    if not (address_visible or city_visible or zip_visible):
        logger.warning(f"CHECKOUT FLOW: No address fields visible on current page")
        return {'success': False, 'errors': ['No address fields visible']}
    
    errors = []
    filled_count = 0
    
    try:
        # Fill address line 1 (support both formats)
        addr1 = address_data.get('addressLine1') or address_data.get('address1') or address_data.get('address')
        if addr1:
            logger.info(f"CHECKOUT FLOW: Filling address line 1: {addr1}")
            result = await fill_input_field(page, ADDRESS_LINE1_LABELS, addr1)
            logger.info(f"CHECKOUT FLOW: Address line 1 result: {result}")
            if result['success']:
                filled_count += 1
            else:
                errors.append(f"Address line 1: {result.get('error')}")
            await asyncio.sleep(1.5)
        
        # Fill address line 2 (optional)
        addr2 = address_data.get('addressLine2') or address_data.get('address2')
        if addr2:
            result = await fill_input_field(page, ADDRESS_LINE2_LABELS, addr2)
            if result['success']:
                filled_count += 1
            await asyncio.sleep(1)
        
        # Fill city
        city = address_data.get('city')
        if city:
            logger.info(f"CHECKOUT FLOW: Filling city: {city}")
            result = await fill_input_field(page, CITY_LABELS, city)
            logger.info(f"CHECKOUT FLOW: City result: {result}")
            if result['success']:
                filled_count += 1
            else:
                errors.append(f"City: {result.get('error')}")
            await asyncio.sleep(1.5)
        
        # Fill country (dropdown)
        country = address_data.get('country')
        if country:
            country_labels = ['country']
            result = await find_and_select_dropdown(page, country_labels, country)
            if result['success']:
                filled_count += 1
            await asyncio.sleep(1)
        
        # Fill state/province (dropdown, support both formats)
        state = address_data.get('province') or address_data.get('state')
        if state:
            logger.info(f"CHECKOUT FLOW: Selecting state: {state}")
            result = await find_and_select_dropdown(page, STATE_LABELS, state)
            logger.info(f"CHECKOUT FLOW: State result: {result}")
            if result['success']:
                filled_count += 1
            else:
                errors.append(f"State/Province: {result.get('error')}")
            await asyncio.sleep(1)
        
        # Fill postal code (required)
        postal = address_data.get('postalCode') or address_data.get('zipCode') or address_data.get('zip')
        if postal:
            logger.info(f"CHECKOUT FLOW: Filling postal code: {postal}")
            result = await fill_input_field(page, POSTAL_CODE_LABELS, postal)
            logger.info(f"CHECKOUT FLOW: Postal code result: {result}")
            if result['success']:
                filled_count += 1
            else:
                errors.append(f"Postal code: {result.get('error')}")
            await asyncio.sleep(1)
        
        # Success if at least 3 fields filled
        if filled_count >= 3:
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Shipping address filled ({filled_count} fields)")
            return {'success': True}
        
        logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Only {filled_count} fields filled. Errors: {errors}")
        return {'success': False, 'errors': errors}
    
    except Exception as e:
        logger.error(f"CHECKOUT FLOW: EXCEPTION in fill_shipping_address: {e}")
        import traceback
        traceback.print_exc()
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


async def run_checkout_flow(page, customer_data, agent_coordinator=None):
    """
    Main entry point for Phase 2 checkout flow with optional agent fallback
    customer_data: Full customer object from JSON
    agent_coordinator: Optional AgentCoordinator for AI fallback
    Returns: {'success': bool, 'error': str, 'details': dict}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Starting Phase 2 checkout flow")
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
        result = await fill_contact_info(page, contact_data)
        
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
        result = await fill_shipping_address(page, address_data)
        
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
        
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Checkout flow completed successfully")
        return {'success': True, 'message': 'Checkout flow completed'}
        
    except Exception as e:
        logger.error(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Checkout flow error: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"CHECKOUT FLOW: Keeping browser open for debugging...")
        # Don't close browser, just return error
        return {'success': False, 'error': str(e)}
