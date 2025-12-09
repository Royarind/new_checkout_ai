"""
Sequential Checkout Flow - Strict Order
Email → Continue → Password (if needed) → First Name → Last Name → 
Address1 → Address2 → Zip → City → State → Country → Phone → 
Same as Billing Checkbox → Continue → Payment
"""

import asyncio
import logging
from src.checkout_ai.legacy.phase2.smart_form_filler import SmartFormFiller
from src.checkout_ai.legacy.phase2.checkout_dom_finder import CheckoutDOMFinder, find_and_click_button, fill_input_field, find_and_select_dropdown
from src.checkout_ai.utils.checkout_keywords import CONTINUE_BUTTONS
from src.checkout_ai.utils.popup_dismisser import dismiss_popups

logger = logging.getLogger(__name__)


async def sequential_checkout_flow(page, customer_data, user_prompt_callback=None):
    """Execute checkout in strict sequential order"""
    
    logger.info("SEQUENTIAL CHECKOUT: Starting strict order flow")
    await dismiss_popups(page)
    await asyncio.sleep(1)
    
    contact = customer_data.get('contact', {})
    address = customer_data.get('shippingAddress', {})
    
    # STEP 1: Email
    if contact.get('email'):
        logger.info(f"STEP 1: Filling email: {contact['email']}")
        await _fill_field(page, ['email', 'e-mail', 'mail'], contact['email'])
        await asyncio.sleep(1)
    
    # STEP 2: Continue/Next button (MANDATORY)
    logger.info("STEP 2: Clicking Continue/Next button")
    continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=3)
    if continue_result['success']:
        logger.info("✓ Continue clicked, waiting for next page...")
        await asyncio.sleep(3)
        try:
            await page.wait_for_load_state('domcontentloaded', timeout=5000)
        except:
            pass
    else:
        logger.warning("Continue button not found, proceeding anyway")
    
    # STEP 3: Password (if field exists, prompt user)
    has_password = await page.evaluate("""
        () => Array.from(document.querySelectorAll('input[type="password"]')).some(el => el.offsetParent)
    """)
    
    if has_password:
        logger.info("STEP 3: Password field detected")
        if not contact.get('password') and user_prompt_callback:
            password = await user_prompt_callback('password', 'Password required. Please enter:')
            if password:
                contact['password'] = password
        
        if contact.get('password'):
            await _fill_field(page, ['password', 'pass', 'pwd'], contact['password'])
            await asyncio.sleep(1)
    
    # STEP 4: First Name
    if contact.get('firstName'):
        logger.info(f"STEP 4: Filling first name: {contact['firstName']}")
        await _fill_field(page, ['firstname', 'first', 'givenname', 'fname'], contact['firstName'])
        await asyncio.sleep(0.5)
    
    # STEP 5: Last Name
    if contact.get('lastName'):
        logger.info(f"STEP 5: Filling last name: {contact['lastName']}")
        await _fill_field(page, ['lastname', 'last', 'surname', 'familyname', 'lname'], contact['lastName'])
        await asyncio.sleep(0.5)
    
    # STEP 6: Address Line 1
    addr1 = address.get('addressLine1') or address.get('address1')
    if addr1:
        logger.info(f"STEP 6: Filling address line 1: {addr1}")
        await _fill_field(page, ['address1', 'address', 'street', 'addressline1'], addr1)
        await asyncio.sleep(0.5)
    
    # STEP 7: Address Line 2
    addr2 = address.get('addressLine2') or address.get('address2')
    if addr2:
        logger.info(f"STEP 7: Filling address line 2: {addr2}")
        await _fill_field(page, ['address2', 'addressline2', 'apartment', 'suite'], addr2)
        await asyncio.sleep(0.5)
    
    # STEP 8: Zip/Postal Code
    postal = address.get('postalCode') or address.get('zipCode')
    if postal:
        logger.info(f"STEP 8: Filling postal code: {postal}")
        await _fill_field(page, ['zip', 'postal', 'postcode', 'zipcode'], postal)
        await asyncio.sleep(0.5)
    
    # STEP 9: City
    if address.get('city'):
        logger.info(f"STEP 9: Filling city: {address['city']}")
        await _fill_field(page, ['city', 'town', 'locality'], address['city'])
        await asyncio.sleep(0.5)
    
    # STEP 10: State/Province
    state = address.get('province') or address.get('state')
    if state:
        logger.info(f"STEP 10: Selecting state: {state}")
        await _select_dropdown(page, ['state', 'province', 'region'], state)
        await asyncio.sleep(0.5)
    
    # STEP 11: Country
    if address.get('country'):
        logger.info(f"STEP 11: Selecting country: {address['country']}")
        await _select_dropdown(page, ['country', 'nation'], address['country'])
        await asyncio.sleep(0.5)
    
    # STEP 12: Phone Number
    phone = contact.get('phone') or address.get('phone')
    if phone:
        logger.info(f"STEP 12: Filling phone: {phone}")
        await _fill_field(page, ['phone', 'telephone', 'mobile', 'tel'], phone)
        await asyncio.sleep(0.5)
    
    # STEP 13: Same as Billing Address Checkbox
    logger.info("STEP 13: Checking 'Same as Billing' checkbox if exists")
    await _check_billing_checkbox(page)
    await asyncio.sleep(0.5)
    
    # STEP 14: Continue Button (to payment)
    logger.info("STEP 14: Clicking Continue to proceed to payment")
    continue_result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=3)
    if continue_result['success']:
        logger.info("✓ Continue clicked, proceeding to payment phase")
        await asyncio.sleep(2)
    
    logger.info("SEQUENTIAL CHECKOUT: Flow completed")
    return {'success': True}


async def _fill_field(page, keywords, value):
    """Fill field by keywords"""
    try:
        filled = await page.evaluate("""
            (args) => {
                const normalize = (text) => text.toLowerCase().replace(/[-_\\s]/g, '');
                const fields = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), textarea'))
                    .filter(el => el.offsetParent && !el.disabled && !el.readOnly && !el.value);
                
                for (const keyword of args.keywords) {
                    const normKey = normalize(keyword);
                    for (const field of fields) {
                        const fieldText = [field.name, field.id, field.placeholder, field.autocomplete, 
                                          field.getAttribute('aria-label'), 
                                          (field.closest('label') || document.querySelector(`label[for="${field.id}"]`))?.textContent].join(' ');
                        if (normalize(fieldText).includes(normKey)) {
                            field.value = args.value;
                            field.dispatchEvent(new Event('input', {bubbles: true}));
                            field.dispatchEvent(new Event('change', {bubbles: true}));
                            field.dispatchEvent(new Event('blur', {bubbles: true}));
                            return true;
                        }
                    }
                }
                return false;
            }
        """, {'keywords': keywords, 'value': str(value)})
        
        if filled:
            logger.info(f"✓ Filled field with keywords: {keywords[0]}")
        else:
            logger.warning(f"✗ Field not found for keywords: {keywords}")
        return filled
    except Exception as e:
        logger.error(f"Error filling field: {e}")
        return False


async def _select_dropdown(page, keywords, value):
    """Select dropdown option"""
    try:
        selected = await page.evaluate("""
            (args) => {
                const normalize = (text) => text.toLowerCase().replace(/[-_\\s]/g, '');
                const selects = Array.from(document.querySelectorAll('select')).filter(el => el.offsetParent);
                
                for (const keyword of args.keywords) {
                    const normKey = normalize(keyword);
                    for (const select of selects) {
                        const selectText = [select.name, select.id, 
                                           (select.closest('label') || document.querySelector(`label[for="${select.id}"]`))?.textContent].join(' ');
                        if (normalize(selectText).includes(normKey)) {
                            const options = Array.from(select.options);
                            const match = options.find(opt => 
                                normalize(opt.text).includes(normalize(args.value)) ||
                                normalize(opt.value).includes(normalize(args.value))
                            );
                            if (match) {
                                select.value = match.value;
                                select.dispatchEvent(new Event('change', {bubbles: true}));
                                return true;
                            }
                        }
                    }
                }
                return false;
            }
        """, {'keywords': keywords, 'value': str(value)})
        
        if selected:
            logger.info(f"✓ Selected dropdown: {keywords[0]} = {value}")
        else:
            logger.warning(f"✗ Dropdown not found for: {keywords}")
        return selected
    except Exception as e:
        logger.error(f"Error selecting dropdown: {e}")
        return False


async def _check_billing_checkbox(page):
    """Check 'Same as Billing Address' checkbox"""
    try:
        checked = await page.evaluate("""
            () => {
                const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'))
                    .filter(el => el.offsetParent);
                
                for (const cb of checkboxes) {
                    const label = cb.closest('label') || document.querySelector(`label[for="${cb.id}"]`);
                    const text = (label?.textContent || cb.getAttribute('aria-label') || '').toLowerCase();
                    
                    if (text.includes('same') && (text.includes('billing') || text.includes('shipping'))) {
                        if (!cb.checked) {
                            cb.checked = true;
                            cb.dispatchEvent(new Event('change', {bubbles: true}));
                            return true;
                        }
                        return true;
                    }
                }
                return false;
            }
        """)
        
        if checked:
            logger.info("✓ Checked 'Same as Billing' checkbox")
        return checked
    except Exception as e:
        logger.error(f"Error checking billing checkbox: {e}")
        return False
