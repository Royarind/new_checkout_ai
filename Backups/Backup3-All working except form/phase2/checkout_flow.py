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
    
    # Store current URL to detect navigation
    url_before = page.url
    logger.info(f"CHECKOUT FLOW: Current URL: {url_before}")
    
    # First try clicking cart icon to open cart drawer/modal
    logger.info(f"CHECKOUT FLOW: Looking for cart icon...")
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
        logger.info(f"CHECKOUT FLOW: Cart icon clicked, waiting for drawer...")
        await asyncio.sleep(2)
    
    # Try checkout button on modal/drawer (flying modal pattern)
    logger.info(f"CHECKOUT FLOW: Looking for checkout button...")
    result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=3)
    
    if result['success']:
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Checkout button clicked on modal")
        await asyncio.sleep(3)
        
        # Check if we navigated to checkout or homepage
        url_after = page.url
        logger.info(f"CHECKOUT FLOW: URL after click: {url_after}")
        
        if 'checkout' in url_after.lower() or 'cart' not in url_after.lower():
            logger.info(f"CHECKOUT FLOW: Successfully navigated to checkout")
            return {'success': True}
        else:
            logger.warning(f"CHECKOUT FLOW: Clicked wrong button, still on cart/homepage")
            # Continue to try other methods
    
    # Try View Cart first then Checkout
    logger.info(f"CHECKOUT FLOW: Trying View Cart button...")
    view_cart_keywords = ['proceed to cart', 'view cart', 'go to cart', 'view bag', 'view basket']
    view_cart_result = await find_and_click_button(page, view_cart_keywords, max_retries=2)
    
    if view_cart_result['success']:
        logger.info(f"CHECKOUT FLOW: View Cart clicked, waiting for page...")
        await asyncio.sleep(3)
        result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=3)
        if result['success']:
            logger.info(f"CHECKOUT FLOW: Checkout button clicked")
            await asyncio.sleep(3)
            
            # Verify we're on checkout page
            url_final = page.url
            logger.info(f"CHECKOUT FLOW: Final URL: {url_final}")
            if 'checkout' in url_final.lower():
                return {'success': True}
            else:
                logger.error(f"CHECKOUT FLOW: Not on checkout page after clicking")
                return {'success': False, 'error': 'Navigation to checkout failed'}
    
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


async def fill_contact_info(page, contact_data, user_prompt_callback=None, llm_client=None):
    """
    Fill contact information: Email first → Continue → Then First/Last Name
    contact_data: {'email': str, 'firstName': str, 'lastName': str, 'phone': str, 'password': str (optional)}
    user_prompt_callback: Optional callback function to prompt user for missing data
    Returns: {'success': bool, 'errors': list}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filling contact information...")
    
    # Dismiss any popups/modals before filling
    logger.info(f"CHECKOUT FLOW: Dismissing popups before contact info...")
    await dismiss_popups(page)
    await asyncio.sleep(1)
    
    await log_available_fields(page, "CONTACT_INFO")
    
    # Check for password field
    has_password = await page.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll('input[type="password"]'));
            return inputs.some(el => el.offsetParent);
        }
    """)
    
    if has_password and not contact_data.get('password') and user_prompt_callback:
        logger.info(f"CHECKOUT FLOW: Password field detected, prompting user...")
        password = await user_prompt_callback('password', 'A password is required for this checkout. Please enter your password:')
        if password:
            contact_data['password'] = password
        else:
            return {'success': False, 'errors': ['Password required but not provided']}
    
    filled_count = 0
    
    # Check if email is already filled (pre-filled or user signed in)
    email_filled = await page.evaluate("""
        () => {
            const emailInput = document.querySelector('input[type="email"], input[name*="email" i], input[id*="email" i]');
            return emailInput && emailInput.value && emailInput.value.length > 0;
        }
    """)
    
    if email_filled:
        logger.info(f"CHECKOUT FLOW: Email already filled, clicking Continue...")
        filled_count += 1
    elif contact_data.get('email'):
        logger.info(f"CHECKOUT FLOW: Step 1 - Filling email: {contact_data['email']}")
        result = await fill_input_field(page, EMAIL_LABELS, contact_data['email'], max_retries=1)
        if result['success']:
            filled_count += 1
            logger.info(f"CHECKOUT FLOW: ✓ Email filled")
        else:
            logger.info(f"CHECKOUT FLOW: Email field not found")
    
    # STEP 2: Click Continue to proceed to next form
    logger.info(f"CHECKOUT FLOW: Step 2 - Clicking Continue button...")
    continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=2)
    if continue_result['success']:
        logger.info(f"CHECKOUT FLOW: ✓ Continue clicked, waiting for next form...")
        try:
            await page.wait_for_load_state('networkidle', timeout=5000)
        except:
            await asyncio.sleep(3)
        await log_available_fields(page, "AFTER_CONTINUE")
    else:
        logger.info(f"CHECKOUT FLOW: No Continue button, may already be on next step")
    
    # STEP 3: Fill First Name
    if contact_data.get('firstName'):
        logger.info(f"CHECKOUT FLOW: Step 3 - Filling first name: {contact_data['firstName']}")
        result = await fill_input_field(page, FIRST_NAME_LABELS, contact_data['firstName'], max_retries=3)
        if result['success']:
            filled_count += 1
            logger.info(f"CHECKOUT FLOW: ✓ First name filled successfully")
        else:
            logger.warning(f"CHECKOUT FLOW: ✗ First name not found (may not be required)")
        await asyncio.sleep(0.5)
    
    # STEP 4: Fill Last Name
    if contact_data.get('lastName'):
        logger.info(f"CHECKOUT FLOW: Step 4 - Filling last name: {contact_data['lastName']}")
        result = await fill_input_field(page, LAST_NAME_LABELS, contact_data['lastName'])
        if result['success']:
            filled_count += 1
            logger.info(f"CHECKOUT FLOW: ✓ Last name filled successfully")
        else:
            logger.warning(f"CHECKOUT FLOW: ✗ Last name not found (may not be required)")
        await asyncio.sleep(0.5)
    
    # STEP 5: Fill Phone (optional)
    if contact_data.get('phone'):
        logger.info(f"CHECKOUT FLOW: Step 5 - Filling phone: {contact_data['phone']}")
        result = await fill_input_field(page, PHONE_LABELS, contact_data['phone'])
        if result['success']:
            filled_count += 1
            logger.info(f"CHECKOUT FLOW: ✓ Phone filled successfully")
        else:
            logger.info(f"CHECKOUT FLOW: Phone field not found (optional)")
        await asyncio.sleep(0.5)
    
    # STEP 6: Fill Password (if required)
    if contact_data.get('password'):
        logger.info(f"CHECKOUT FLOW: Step 6 - Filling password")
        result = await fill_input_field(page, ['password', 'pass', 'pwd'], contact_data['password'])
        if result['success']:
            filled_count += 1
            logger.info(f"CHECKOUT FLOW: ✓ Password filled successfully")
        else:
            logger.info(f"CHECKOUT FLOW: Password field not found")
        await asyncio.sleep(0.5)
    
    if filled_count > 0:
        logger.info(f"CHECKOUT FLOW: Contact information completed ({filled_count} fields filled)")
        return {'success': True}
    
    logger.warning(f"CHECKOUT FLOW: No fields were filled - assuming user is signed in")
    return {'success': True}


async def fill_shipping_address(page, address_data, llm_client=None):
    """
    Fill shipping address form
    address_data: {'addressLine1': str, 'addressLine2': str, 'city': str, 'province': str, 'postalCode': str}
    Returns: {'success': bool, 'errors': list}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filling shipping address...")
    
    # Dismiss any popups/modals before filling
    logger.info(f"CHECKOUT FLOW: Dismissing popups before shipping address...")
    await dismiss_popups(page)
    await asyncio.sleep(1)
    
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
        # FALLBACK: Fill in correct order: address1 → address2 → postal → city → state → country → phone
        addr1 = address_data.get('addressLine1') or address_data.get('address1') or address_data.get('address')
        if addr1:
            logger.info(f"CHECKOUT FLOW: Attempting to fill address line 1: {addr1}")
            result = await fill_input_field(page, ADDRESS_LINE1_LABELS, addr1)
            if result['success']:
                filled_count += 1
                logger.info(f"CHECKOUT FLOW: ✓ Address line 1 filled")
            else:
                logger.error(f"CHECKOUT FLOW: ✗ Address line 1 failed: {result.get('error')}")
            await asyncio.sleep(1)
        
        addr2 = address_data.get('addressLine2') or address_data.get('address2')
        if addr2:
            logger.info(f"CHECKOUT FLOW: Attempting to fill address line 2: {addr2}")
            result = await fill_input_field(page, ADDRESS_LINE2_LABELS, addr2)
            if result['success']:
                filled_count += 1
                logger.info(f"CHECKOUT FLOW: ✓ Address line 2 filled")
            await asyncio.sleep(1)
        
        postal = address_data.get('postalCode') or address_data.get('zipCode') or address_data.get('zip')
        if postal:
            logger.info(f"CHECKOUT FLOW: Attempting to fill postal code: {postal}")
            result = await fill_input_field(page, POSTAL_CODE_LABELS, postal)
            if result['success']:
                filled_count += 1
                logger.info(f"CHECKOUT FLOW: ✓ Postal code filled")
            else:
                logger.error(f"CHECKOUT FLOW: ✗ Postal code failed: {result.get('error')}")
            await asyncio.sleep(1)
        
        city = address_data.get('city')
        if city:
            logger.info(f"CHECKOUT FLOW: Attempting to fill city: {city}")
            result = await fill_input_field(page, CITY_LABELS, city)
            if result['success']:
                filled_count += 1
                logger.info(f"CHECKOUT FLOW: ✓ City filled")
            else:
                logger.error(f"CHECKOUT FLOW: ✗ City failed: {result.get('error')}")
            await asyncio.sleep(1)
        
        state = address_data.get('province') or address_data.get('state')
        if state:
            logger.info(f"CHECKOUT FLOW: Attempting to select state: {state}")
            result = await find_and_select_dropdown(page, STATE_LABELS, state)
            if result['success']:
                filled_count += 1
                logger.info(f"CHECKOUT FLOW: ✓ State selected")
            else:
                logger.error(f"CHECKOUT FLOW: ✗ State failed: {result.get('error')}")
            await asyncio.sleep(1)
        
        country = address_data.get('country')
        if country:
            logger.info(f"CHECKOUT FLOW: Attempting to select country: {country}")
            result = await find_and_select_dropdown(page, ['country'], country)
            if result['success']:
                filled_count += 1
                logger.info(f"CHECKOUT FLOW: ✓ Country selected")
            else:
                logger.error(f"CHECKOUT FLOW: ✗ Country failed: {result.get('error')}")
            await asyncio.sleep(1)
        
        phone = address_data.get('phone') or address_data.get('phoneNumber')
        if phone:
            logger.info(f"CHECKOUT FLOW: Attempting to fill phone: {phone}")
            result = await fill_input_field(page, PHONE_LABELS, phone)
            if result['success']:
                filled_count += 1
                logger.info(f"CHECKOUT FLOW: ✓ Phone filled")
            await asyncio.sleep(1)
        
        # Check if all visible required fields are filled
        if filled_count >= 3:
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Shipping address filled ({filled_count} fields)")
            
            # Check if there are any empty required fields
            empty_fields = await page.evaluate("""
                () => {
                    const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select'))
                        .filter(el => el.offsetParent && el.required && !el.value);
                    return inputs.map(el => ({
                        name: el.name || el.id || 'unknown',
                        type: el.tagName.toLowerCase()
                    }));
                }
            """)
            
            if empty_fields and len(empty_fields) > 0:
                logger.info(f"CHECKOUT FLOW: Still have {len(empty_fields)} empty required fields: {[f['name'] for f in empty_fields]}")
                return {'success': True}
            
            # All required fields filled, click continue
            await asyncio.sleep(1)
            continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=2)
            if continue_result['success']:
                logger.info(f"CHECKOUT FLOW: Continue clicked after all fields filled")
                await asyncio.sleep(2)
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


async def run_checkout_flow(page, customer_data, agent_coordinator=None, user_prompt_callback=None):
    """
    Main entry point for Phase 2 checkout flow with optional agent fallback
    customer_data: Full customer object from JSON
    agent_coordinator: Optional AgentCoordinator for AI fallback
    user_prompt_callback: Optional callback to prompt user for missing data (e.g., password)
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
        
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Checkout flow completed successfully")
        return {'success': True, 'message': 'Checkout flow completed'}
        
    except Exception as e:
        logger.error(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Checkout flow error: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"CHECKOUT FLOW: Keeping browser open for debugging...")
        # Don't close browser, just return error
        return {'success': False, 'error': str(e)}
