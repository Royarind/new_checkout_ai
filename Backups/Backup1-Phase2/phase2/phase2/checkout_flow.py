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

logger = logging.getLogger(__name__)


async def proceed_to_checkout(page):
    """
    Click checkout button to proceed from cart to checkout
    Returns: {'success': bool, 'error': str}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Proceeding to checkout...")
    
    result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=3)
    
    if result['success']:
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Successfully clicked checkout button")
        await asyncio.sleep(2)  # Wait for checkout page to load
        return {'success': True}
    else:
        logger.error(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Failed to find checkout button")
        return {'success': False, 'error': result.get('error', 'Checkout button not found')}


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
    
    errors = []
    filled_count = 0
    
    # Fill email first (often triggers form expansion)
    if contact_data.get('email'):
        result = await fill_input_field(page, EMAIL_LABELS, contact_data['email'])
        if result['success']:
            filled_count += 1
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filled email")
        else:
            logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Email field not found")
            errors.append(f"Email: {result.get('error')}")
        await asyncio.sleep(0.5)
    
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
        await asyncio.sleep(0.5)
    
    if contact_data.get('lastName'):
        result = await fill_input_field(page, LAST_NAME_LABELS, contact_data['lastName'])
        if result['success']:
            filled_count += 1
            name_filled = True
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Filled last name")
        else:
            logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Last name field not found")
        await asyncio.sleep(0.5)
    
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
    
    errors = []
    filled_count = 0
    
    # Fill address line 1
    if address_data.get('addressLine1'):
        result = await fill_input_field(page, ADDRESS_LINE1_LABELS, address_data['addressLine1'])
        if result['success']:
            filled_count += 1
        else:
            errors.append(f"Address line 1: {result.get('error')}")
        await asyncio.sleep(0.5)
    
    # Fill address line 2 (optional)
    if address_data.get('addressLine2'):
        result = await fill_input_field(page, ADDRESS_LINE2_LABELS, address_data['addressLine2'])
        if result['success']:
            filled_count += 1
        await asyncio.sleep(0.5)
    
    # Fill city
    if address_data.get('city'):
        result = await fill_input_field(page, CITY_LABELS, address_data['city'])
        if result['success']:
            filled_count += 1
        else:
            errors.append(f"City: {result.get('error')}")
        await asyncio.sleep(0.5)
    
    # Fill country (dropdown)
    if address_data.get('country'):
        country_labels = ['country']
        result = await find_and_select_dropdown(page, country_labels, address_data['country'])
        if result['success']:
            filled_count += 1
        await asyncio.sleep(0.5)
    
    # Fill state/province (dropdown)
    if address_data.get('province'):
        result = await find_and_select_dropdown(page, STATE_LABELS, address_data['province'])
        if result['success']:
            filled_count += 1
        else:
            errors.append(f"State/Province: {result.get('error')}")
        await asyncio.sleep(0.5)
    
    # Fill postal code (required)
    if address_data.get('postalCode'):
        result = await fill_input_field(page, POSTAL_CODE_LABELS, address_data['postalCode'])
        if result['success']:
            filled_count += 1
        else:
            errors.append(f"Postal code: {result.get('error')}")
        await asyncio.sleep(0.5)
    
    # Success if all required fields filled (address, city, state, postal code)
    if filled_count >= 4:
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Shipping address filled ({filled_count} fields)")
        return {'success': True}
    
    logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Shipping address errors: {errors}")
    return {'success': False, 'errors': errors}


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
                    
                    // Look for shipping/delivery keywords
                    if (text.includes('ship') || text.includes('delivery') || text.includes('standard') || 
                        text.includes('express') || text.includes('ground') || text.includes('overnight') ||
                        text.includes('freight') || text.includes('mail')) {
                        
                        // Extract all numbers that look like prices
                        const priceMatches = text.match(/\$\s*([0-9]+\.?[0-9]*)|([0-9]+\.?[0-9]*)\s*\$/g);
                        let price = 999999; // Default high price
                        
                        if (priceMatches && priceMatches.length > 0) {
                            // Get first price found
                            const priceStr = priceMatches[0].replace(/[^0-9.]/g, '');
                            price = parseFloat(priceStr) || 0;
                        } else if (text.includes('free')) {
                            price = 0;
                        }
                        
                        options.push({ 
                            element: radio, 
                            price: price, 
                            text: text.substring(0, 150).trim() 
                        });
                    }
                });
                
                if (options.length === 0) return { found: false };
                
                // Sort by price (cheapest first)
                options.sort((a, b) => a.price - b.price);
                
                // Click cheapest option
                const cheapest = options[0];
                cheapest.element.checked = true;
                cheapest.element.click();
                cheapest.element.dispatchEvent(new Event('change', { bubbles: true }));
                cheapest.element.dispatchEvent(new Event('input', { bubbles: true }));
                
                return { 
                    found: true, 
                    selected: cheapest.text, 
                    price: cheapest.price,
                    totalOptions: options.length
                };
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


async def run_checkout_flow(page, customer_data):
    """
    Main entry point for Phase 2 checkout flow
    customer_data: Full customer object from JSON
    Returns: {'success': bool, 'error': str, 'details': dict}
    """
    logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Starting Phase 2 checkout flow")
    
    try:
        # Step 1: Click checkout button
        result = await proceed_to_checkout(page)
        if not result['success']:
            return {'success': False, 'error': 'Failed to proceed to checkout', 'step': 'checkout_button'}
        
        # Step 2: Handle guest checkout
        country = customer_data.get('shippingAddress', {}).get('country', 'US')
        result = await handle_guest_checkout(page, country)
        if not result['success']:
            return {'success': False, 'error': 'Failed to select guest checkout', 'step': 'guest_checkout'}
        
        await asyncio.sleep(2)
        
        # Step 3: Fill contact information
        contact_data = customer_data.get('contact', {})
        result = await fill_contact_info(page, contact_data)
        # Don't fail if contact info not found - might be on next page
        
        await asyncio.sleep(1)
        
        # Step 4: Fill shipping address
        address_data = customer_data.get('shippingAddress', {})
        result = await fill_shipping_address(page, address_data)
        
        # If address fields not found, try clicking continue first
        if not result['success']:
            logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Address fields not found, clicking continue...")
            await click_continue_if_needed(page)
            await asyncio.sleep(2)
            
            # Retry contact info
            await fill_contact_info(page, contact_data)
            await asyncio.sleep(1)
            
            # Retry address
            result = await fill_shipping_address(page, address_data)
            if not result['success']:
                logger.warning(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Address still not found, trying one more continue...")
                await click_continue_if_needed(page)
                await asyncio.sleep(2)
                result = await fill_shipping_address(page, address_data)
                if not result['success']:
                    return {'success': False, 'error': 'Failed to fill shipping address', 'details': result.get('errors'), 'step': 'shipping_address'}
        
        await asyncio.sleep(1)
        
        # Step 5: Select cheapest shipping method
        await select_cheapest_shipping(page)
        
        # Step 6: Click continue to proceed to payment (Phase 3)
        await click_continue_if_needed(page)
        
        logger.info(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Phase 2 checkout flow completed successfully")
        return {'success': True, 'message': 'Checkout flow completed, ready for payment'}
        
    except Exception as e:
        logger.error(f"CHECKOUT FLOW: [{datetime.now().strftime('%H:%M:%S')}] Checkout flow error: {e}")
        return {'success': False, 'error': str(e), 'step': 'unknown'}
