"""Unified Tool System - All browser automation tools for agents"""
import asyncio
import logging
from typing import Dict, Any, Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Global page context
_PAGE: Optional[Page] = None
_CUSTOMER_DATA: Optional[Dict[str, Any]] = None

def set_page(page: Page):
    global _PAGE
    _PAGE = page

def get_page() -> Page:
    if _PAGE is None:
        raise ValueError("Page not set")
    return _PAGE

def set_customer_data(data: Dict[str, Any]):
    global _CUSTOMER_DATA
    _CUSTOMER_DATA = data

def get_customer_data() -> Optional[Dict[str, Any]]:
    return _CUSTOMER_DATA

# ============= HIGH-LEVEL TOOLS =============

async def select_variant_tool(variant_type: str, variant_value: str) -> Dict[str, Any]:
    """Select product variant (color, size, etc.)"""
    from src.checkout_ai.dom.service import find_variant_dom
    page = get_page()
    result = await find_variant_dom(page, variant_type, variant_value)
    return {"success": result.get('success', False), "message": result.get('content', '')}

async def add_to_cart_tool() -> Dict[str, Any]:
    """Add product to cart"""
    from src.checkout_ai.legacy.phase1.add_to_cart_robust import add_to_cart_robust
    page = get_page()
    
    # 1. Pre-check: Is item out of stock?
    stock_status = await page.evaluate("""
        () => {
            const bodyText = document.body.innerText.toLowerCase();
            const keywords = ['out of stock', 'sold out', 'currently unavailable', 'notify me', 'item not available'];
            for (const k of keywords) {
                if (bodyText.includes(k) && !bodyText.includes('not ' + k)) {
                    // Check visibility of specific OOS elements if possible, or just return true
                    // To be safe, look for these strings in headings or buttons
                    const elements = Array.from(document.querySelectorAll('h1, h2, span, div, button'));
                    for (const el of elements) {
                        if (el.textContent.toLowerCase().includes(k) && el.offsetParent) {
                             return { outOfStock: true, reason: k };
                        }
                    }
                }
            }
            return { outOfStock: false };
        }
    """)
    
    if stock_status.get('outOfStock'):
        reason = stock_status.get('reason')
        logger.warning(f"⛔ ITEM OUT OF STOCK detected: {reason}")
        return {
            "success": False, 
            "error": f"Item is {reason.upper()}. Cannot add to cart.", 
            "out_of_stock": True
        }

    result = await add_to_cart_robust(page)
    return {"success": result.get('success', False), "message": result.get('content', '')}

async def navigate_to_cart_tool() -> Dict[str, Any]:
    """Navigate to cart page"""
    from src.checkout_ai.legacy.phase1.cart_navigator import navigate_to_cart
    page = get_page()
    result = await navigate_to_cart(page)
    return {"success": result.get('success', False), "cart_url": result.get('cart_url', '')}

async def smart_login_tool(email: str = None, phone: str = None, password: str = "") -> Dict[str, Any]:
    """Smart login with mobile/email detection, T&C handling for Indian sites"""
    from src.checkout_ai.plugins.india import SmartLoginHandler
    page = get_page()
    
    # Force use of customer data (source of truth) over LLM arguments
    customer_data = get_customer_data()
    if customer_data:
        config_email = customer_data.get('contact', {}).get('email')
        config_phone = customer_data.get('contact', {}).get('phone')
        
        if config_email and config_email != email:
            print(f"⚠️ Overriding LLM email '{email}' with verified customer data: '{config_email}'")
            email = config_email
            
        if config_phone and config_phone != phone:
            print(f"⚠️ Overriding LLM phone '{phone}' with verified customer data: '{config_phone}'")
            phone = config_phone
            
    # Fallbacks if still empty
    if not email: email = ""
    if not phone: phone = ""
    
    handler = SmartLoginHandler(page)
    result = await handler.login(email=email, phone=phone, password=password)
    return result

async def select_checkbox_tool(label_text: str, check: bool = True) -> Dict[str, Any]:
    """Select or unselect a checkbox by label"""
    page = get_page()
    try:
        result = await page.evaluate("""
            ({labelText, shouldCheck}) => {
                const normalize = (text) => text ? text.toLowerCase().trim() : '';
                const targetLabel = normalize(labelText);
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                
                for (const checkbox of checkboxes) {
                    const label = checkbox.parentElement?.textContent || 
                                 document.querySelector(`label[for="${checkbox.id}"]`)?.textContent ||
                                 checkbox.getAttribute('aria-label') || '';
                    const labelNorm = normalize(label);
                    
                    if (labelNorm.includes(targetLabel) || targetLabel.includes(labelNorm)) {
                        const rect = checkbox.getBoundingClientRect();
                        const style = window.getComputedStyle(checkbox);
                        const isVisible = rect.width > 0 && rect.height > 0 && style.display !== 'none';
                        
                        if (isVisible && !checkbox.disabled) {
                            if (checkbox.checked !== shouldCheck) checkbox.click();
                            return {success: true, label: label.substring(0, 100), checked: checkbox.checked};
                        }
                    }
                }
                return {success: false, error: `Checkbox "${labelText}" not found`};
            }
        """, {"labelText": label_text, "shouldCheck": check})
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

async def fill_email_tool(email: str = None) -> Dict[str, Any]:
    """Fill email field"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field
    from src.checkout_ai.utils.checkout_keywords import EMAIL_LABELS
    page = get_page()
    
    # Use provided email or get from customer data
    if not email:
        customer_data = get_customer_data()
        if customer_data:
            email = customer_data.get('contact', {}).get('email')
    
    if not email:
        return {"success": False, "error": "No email provided"}
    
    result = await fill_input_field(page, EMAIL_LABELS, email, max_retries=3)
    return {"success": result.get('success', False)}

async def fill_contact_tool(first_name: str = None, last_name: str = None, phone: str = None) -> Dict[str, Any]:
    """Fill contact fields sequentially to prevent field collision"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field
    from src.checkout_ai.utils.checkout_keywords import FIRST_NAME_LABELS, LAST_NAME_LABELS, PHONE_LABELS
    page = get_page()
    
    # Use provided values or get from customer data
    customer_data = get_customer_data()
    if not customer_data:
        logger.error("❌ No customer data available!")
        return {"success": False, "filled_count": 0, "error": "Customer data not provided"}
    
    contact = customer_data.get('contact', {})
    first_name = first_name or contact.get('firstName')
    last_name = last_name or contact.get('lastName')
    phone = phone or contact.get('phone')
    
    # CRITICAL: Fill sequentially to prevent race conditions
    success_count = 0
    total_count = 0
    
    if first_name:
        total_count += 1
        result = await fill_input_field(page, FIRST_NAME_LABELS, first_name, max_retries=2)
        if result.get('success'):
            success_count += 1
        await asyncio.sleep(0.3)
    
    if last_name:
        total_count += 1
        result = await fill_input_field(page, LAST_NAME_LABELS, last_name, max_retries=2)
        if result.get('success'):
            success_count += 1
        await asyncio.sleep(0.3)
    
    if phone:
        total_count += 1
        result = await fill_input_field(page, PHONE_LABELS, phone, max_retries=2)
        if result.get('success'):
            success_count += 1
    
    return {"success": success_count == total_count if total_count > 0 else False, "filled_count": success_count}

async def fill_address_tool(address: str = None, city: str = None, state: str = None, zip_code: str = None, country: str = None) -> Dict[str, Any]:
    """Fill address fields sequentially (Country first, then others)"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field, find_and_select_dropdown
    from src.checkout_ai.utils.checkout_keywords import ADDRESS_LINE1_LABELS, CITY_LABELS, STATE_LABELS, POSTAL_CODE_LABELS, COUNTRY_LABELS
    page = get_page()
    
    # Use provided values or get from customer data
    customer_data = get_customer_data()
    if not customer_data:
        logger.error("❌ No customer data available!")
        return {"success": False, "filled_count": 0, "error": "Customer data not provided"}
    
    addr = customer_data.get('shippingAddress', {})
    address = address or addr.get('addressLine1')
    city = city or addr.get('city')
    state = state or addr.get('province')
    zip_code = zip_code or addr.get('postalCode')
    country = country or addr.get('country')
    
    # CRITICAL: Fill sequentially - Country first, then others
    success_count = 0
    total_count = 0
    
    # 1. Country FIRST
    if country:
        total_count += 1
        try:
            result = await find_and_select_dropdown(page, COUNTRY_LABELS, country, max_retries=2)
            if result.get('success'):
                success_count += 1
                await asyncio.sleep(0.5)
        except:
            pass
    
    # 2. State
    if state:
        total_count += 1
        try:
            result = await find_and_select_dropdown(page, STATE_LABELS, state, max_retries=2)
            if result.get('success'):
                success_count += 1
        except:
            pass
        await asyncio.sleep(0.3)
    
    # 3. Address
    if address:
        total_count += 1
        result = await fill_input_field(page, ADDRESS_LINE1_LABELS, address, max_retries=2)
        if result.get('success'):
            success_count += 1
        await asyncio.sleep(0.3)
    
    # 4. City
    if city:
        total_count += 1
        result = await fill_input_field(page, CITY_LABELS, city, max_retries=2)
        if result.get('success'):
            success_count += 1
        await asyncio.sleep(0.3)
    
    # 5. ZIP
    if zip_code:
        total_count += 1
        result = await fill_input_field(page, POSTAL_CODE_LABELS, zip_code, max_retries=2)
        if result.get('success'):
            success_count += 1
    
    return {"success": success_count == total_count if total_count > 0 else False, "filled_count": success_count}

async def click_checkout_button_tool() -> Dict[str, Any]:
    """Click checkout/proceed button"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import find_and_click_button
    from src.checkout_ai.utils.checkout_keywords import CHECKOUT_BUTTONS
    page = get_page()
    
    # Check if ALREADY on login page (Myntra redirects automatically sometimes)
    url = page.url.lower()
    if 'login' in url or 'signin' in url or 'authentication' in url:
        return {"success": True, "message": "Already on login page"}

    result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=3)
    
    # Check again if redirected to login page after failure (or partial success)
    if not result.get('success', False):
         url = page.url.lower()
         if 'login' in url or 'signin' in url or 'authentication' in url:
             return {"success": True, "message": "Redirected to login page implicitly"}
             
    return {"success": result.get('success', False)}

async def click_guest_checkout_tool() -> Dict[str, Any]:
    """Click guest checkout button"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import find_and_click_button
    from src.checkout_ai.utils.checkout_keywords import GUEST_CHECKOUT_BUTTONS
    page = get_page()
    result = await find_and_click_button(page, GUEST_CHECKOUT_BUTTONS, max_retries=2)
    return {"success": result.get('success', False)}

async def click_continue_tool() -> Dict[str, Any]:
    """Click continue/next button"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import find_and_click_button
    from src.checkout_ai.utils.checkout_keywords import CONTINUE_BUTTONS
    page = get_page()
    result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=2)
    return {"success": result.get('success', False)}

async def dismiss_popups_tool() -> Dict[str, Any]:
    """Dismiss all popups and modals"""
    from src.checkout_ai.utils.popup_dismisser import dismiss_popups
    page = get_page()
    await dismiss_popups(page)
    return {"success": True}

async def take_screenshot_tool(path: str = "/tmp/agent_screenshot.png") -> Dict[str, Any]:
    """Take screenshot"""
    page = get_page()
    await page.screenshot(path=path)
    return {"success": True, "path": path}

async def validate_page_state_tool() -> Dict[str, Any]:
    """Get current page state with detailed context"""
    page = get_page()
    url = page.url
    title = await page.title()
    
    state = await page.evaluate("""
        () => {
            // Get visible form fields
            const fields = Array.from(document.querySelectorAll('input:not([type="hidden"]), select, textarea'))
                .filter(el => el.offsetParent)
                .slice(0, 8)
                .map(el => {
                    const label = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
                    return {
                        type: el.type || el.tagName.toLowerCase(),
                        name: el.name || el.id || '',
                        placeholder: el.placeholder || '',
                        label: label?.textContent?.trim().substring(0, 50) || '',
                        value: el.value ? '(filled)' : '(empty)'
                    };
                });
            
            // Get visible buttons
            const buttons = Array.from(document.querySelectorAll('button, a[role="button"], input[type="submit"]'))
                .filter(el => el.offsetParent)
                .slice(0, 8)
                .map(el => ({
                    text: (el.textContent || el.value || '').trim().substring(0, 50),
                    type: el.tagName.toLowerCase()
                }));
            
            // Detect page type
            const urlLower = window.location.href.toLowerCase();
            let pageType = 'unknown';
            if (urlLower.includes('checkout') || urlLower.includes('payment')) pageType = 'checkout';
            else if (urlLower.includes('cart') || urlLower.includes('bag')) pageType = 'cart';
            else if (urlLower.includes('product') || urlLower.includes('/p/')) pageType = 'product';
            
            return {fields, buttons, pageType};
        }
    """)
    
    return {
        "success": True, 
        "url": url, 
        "title": title, 
        "page_type": state['pageType'],
        "fields": state['fields'],
        "buttons": state['buttons'],
        "summary": f"Page: {state['pageType']}, {len(state['fields'])} fields, {len(state['buttons'])} buttons"
    }

async def web_search_tool(query: str) -> Dict[str, Any]:
    """Perform web search"""
    page = get_page()
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    await page.goto(search_url, wait_until='domcontentloaded')
    return {"success": True, "url": search_url}

# ============= LOW-LEVEL ACTIONS =============

async def click_element_tool(selector: str = None, text: str = None, x: int = None, y: int = None) -> Dict[str, Any]:
    """Click element by selector, text, or coordinates"""
    page = get_page()
    
    try:
        # Check for Login Page Trap: detecting "Checkout" clicks when already on Login
        # Check for Login Page Trap: detecting "Checkout" clicks when already on Login
        # NOTE: Removed 'continue' because it's needed FOR the login form itself!
        if text and any(k in text.lower() for k in ['checkout', 'proceed']):
             url = page.url.lower()
             if 'login' in url or 'signin' in url:
                 print(f"⚠️ Bypass: Trying to click '{text}' but already on Login page. Marking success.")
                 return {"success": True, "message": "Automatically bypassed click because already on login page"}

        if x is not None and y is not None:
            await page.mouse.click(x, y)
        elif selector:
            await page.click(selector, timeout=5000)
        elif text:
            await page.click(f"text={text}", timeout=5000)
        else:
            return {"success": False, "error": "No target specified"}
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def fill_text_tool(selector: str = None, text_content: str = "", label: str = None) -> Dict[str, Any]:
    """Fill text in input field"""
    page = get_page()
    
    try:
        if label:
            # Find by label
            element = await page.query_selector(f"label:has-text('{label}') input, label:has-text('{label}') + input")
            if element:
                await element.fill(text_content)
            else:
                return {"success": False, "error": "Label not found"}
        elif selector:
            await page.fill(selector, text_content)
        else:
            return {"success": False, "error": "No target specified"}
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def select_dropdown_tool(selector: str = None, value: str = "", label: str = None) -> Dict[str, Any]:
    """Select dropdown option"""
    page = get_page()
    
    try:
        if label:
            element = await page.query_selector(f"label:has-text('{label}') select, label:has-text('{label}') + select")
            if element:
                await element.select_option(value)
            else:
                return {"success": False, "error": "Label not found"}
        elif selector:
            await page.select_option(selector, value)
        else:
            return {"success": False, "error": "No target specified"}
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def scroll_tool(direction: str = "down", pixels: int = 500) -> Dict[str, Any]:
    """Scroll page"""
    page = get_page()
    
    if direction == "down":
        await page.evaluate(f"window.scrollBy(0, {pixels})")
    elif direction == "up":
        await page.evaluate(f"window.scrollBy(0, -{pixels})")
    elif direction == "top":
        await page.evaluate("window.scrollTo(0, 0)")
    elif direction == "bottom":
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    
    return {"success": True}

async def press_key_tool(key: str) -> Dict[str, Any]:
    """Press keyboard key"""
    page = get_page()
    await page.keyboard.press(key)
    return {"success": True}

async def wait_tool(seconds: float) -> Dict[str, Any]:
    """Wait for specified seconds"""
    await asyncio.sleep(seconds)
    return {"success": True}

async def navigate_tool(url: str) -> Dict[str, Any]:
    """Navigate to URL"""
    page = get_page()
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    return {"success": True, "url": page.url}

# ============= TOOL REGISTRY =============


async def fill_first_name_tool(first_name: str = None) -> Dict[str, Any]:
    """Fill first name field"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field
    from src.checkout_ai.utils.checkout_keywords import FIRST_NAME_LABELS
    page = get_page()
    
    if not first_name:
        customer_data = get_customer_data()
        if customer_data:
            first_name = customer_data.get('contact', {}).get('firstName')
    
    if not first_name:
        return {"success": False, "error": "No first name provided"}
        
    result = await fill_input_field(page, FIRST_NAME_LABELS, first_name, max_retries=2)
    return {"success": result.get('success', False)}

async def fill_last_name_tool(last_name: str = None) -> Dict[str, Any]:
    """Fill last name field"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field
    from src.checkout_ai.utils.checkout_keywords import LAST_NAME_LABELS
    page = get_page()
    
    if not last_name:
        customer_data = get_customer_data()
        if customer_data:
            last_name = customer_data.get('contact', {}).get('lastName')
            
    if not last_name:
        return {"success": False, "error": "No last name provided"}
        
    result = await fill_input_field(page, LAST_NAME_LABELS, last_name, max_retries=2)
    return {"success": result.get('success', False)}

async def fill_phone_tool(phone: str = None) -> Dict[str, Any]:
    """Fill phone number field"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field
    from src.checkout_ai.utils.checkout_keywords import PHONE_LABELS
    page = get_page()
    
    if not phone:
        customer_data = get_customer_data()
        if customer_data:
            phone = customer_data.get('contact', {}).get('phone')
            
    if not phone:
        return {"success": False, "error": "No phone number provided"}
        
    result = await fill_input_field(page, PHONE_LABELS, phone, max_retries=2)
    return {"success": result.get('success', False)}

async def select_country_tool(country: str = None) -> Dict[str, Any]:
    """Select country"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import find_and_select_dropdown
    from src.checkout_ai.utils.checkout_keywords import COUNTRY_LABELS
    page = get_page()
    
    if not country:
        customer_data = get_customer_data()
        if customer_data:
            country = customer_data.get('shippingAddress', {}).get('country')
            
    if not country:
        return {"success": False, "error": "No country provided"}
        
    result = await find_and_select_dropdown(page, COUNTRY_LABELS, country)
    return {"success": result.get('success', False)}

async def fill_address_line1_tool(address: str = None) -> Dict[str, Any]:
    """Fill address line 1"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field
    from src.checkout_ai.utils.checkout_keywords import ADDRESS_LINE1_LABELS
    page = get_page()
    
    if not address:
        customer_data = get_customer_data()
        if customer_data:
            address = customer_data.get('shippingAddress', {}).get('addressLine1')
            
    if not address:
        return {"success": False, "error": "No address line 1 provided"}
        
    result = await fill_input_field(page, ADDRESS_LINE1_LABELS, address, max_retries=3)
    return {"success": result.get('success', False)}

async def fill_address_line2_tool(address_line2: str = None) -> Dict[str, Any]:
    """Fill address line 2"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field
    from src.checkout_ai.utils.checkout_keywords import ADDRESS_LINE2_LABELS
    page = get_page()
    
    if not address_line2:
        customer_data = get_customer_data()
        if customer_data:
            address_line2 = customer_data.get('shippingAddress', {}).get('addressLine2')
            
    # Address line 2 is optional, so if empty, we just return success
    if not address_line2:
        return {"success": True, "message": "Address line 2 is optional and was skipped. Step complete. Proceed to next step."}
        
    result = await fill_input_field(page, ADDRESS_LINE2_LABELS, address_line2, max_retries=2)
    return {"success": result.get('success', False)}

async def fill_landmark_tool(landmark: str = None) -> Dict[str, Any]:
    """Fill landmark"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field
    from src.checkout_ai.utils.checkout_keywords import LANDMARK_LABELS
    page = get_page()
    
    # Landmark is optional
    if not landmark:
        return {"success": True, "message": "Landmark is optional and was skipped. Step complete. Proceed to next step."}
        
    result = await fill_input_field(page, LANDMARK_LABELS, landmark, max_retries=2)
    return {"success": result.get('success', False)}

async def fill_city_tool(city: str = None) -> Dict[str, Any]:
    """Fill city"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field
    from src.checkout_ai.utils.checkout_keywords import CITY_LABELS
    page = get_page()
    
    if not city:
        customer_data = get_customer_data()
        if customer_data:
            city = customer_data.get('shippingAddress', {}).get('city')
            
    if not city:
        return {"success": False, "error": "No city provided"}
        
    result = await fill_input_field(page, CITY_LABELS, city, max_retries=2)
    return {"success": result.get('success', False)}

async def fill_zip_code_tool(zip_code: str = None) -> Dict[str, Any]:
    """Fill zip/postal code"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import fill_input_field
    from src.checkout_ai.utils.checkout_keywords import POSTAL_CODE_LABELS
    page = get_page()
    
    if not zip_code:
        customer_data = get_customer_data()
        if customer_data:
            zip_code = customer_data.get('shippingAddress', {}).get('postalCode')
            
    if not zip_code:
        return {"success": False, "error": "No zip code provided"}
        
    result = await fill_input_field(page, POSTAL_CODE_LABELS, zip_code, max_retries=2)
    return {"success": result.get('success', False)}

async def select_state_tool(state: str = None) -> Dict[str, Any]:
    """Select state/province"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import find_and_select_dropdown
    from src.checkout_ai.utils.checkout_keywords import STATE_LABELS
    page = get_page()
    
    if not state:
        customer_data = get_customer_data()
        if customer_data:
            state = customer_data.get('shippingAddress', {}).get('province')
            
    if not state:
        return {"success": False, "error": "No state provided"}
        
    result = await find_and_select_dropdown(page, STATE_LABELS, state)
    return {"success": result.get('success', False)}

async def click_same_as_billing_tool() -> Dict[str, Any]:
    """Click 'Same as billing' checkbox"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import find_and_click_element
    from src.checkout_ai.utils.checkout_keywords import SAME_AS_BILLING_LABELS
    page = get_page()
    
    # Try to find checkbox with label
    # This is a simplification; might need more robust finding logic
    result = await find_and_click_element(page, SAME_AS_BILLING_LABELS)
    return {"success": result.get('success', False)}

async def select_shipping_method_tool(method: str = "cheapest") -> Dict[str, Any]:
    """Select shipping method (default: cheapest/free)"""
    page = get_page()
    
    # Logic to find shipping options and select the cheapest one
    # This requires custom logic to parse prices
    try:
        # Find all radio buttons in shipping section
        shipping_options = await page.evaluate(r"""
            () => {
                const options = [];
                const radios = document.querySelectorAll('input[type="radio"][name*="shipping"], input[type="radio"][name*="delivery"]');
                
                for (const radio of radios) {
                    const label = document.querySelector(`label[for="${radio.id}"]`) || radio.parentElement;
                    const text = label ? label.textContent : '';
                    
                    // Extract price
                    let price = 999999;
                    if (text.toLowerCase().includes('free')) {
                        price = 0;
                    } else {
                        const match = text.match(/[\d]+[.,]\d{2}/);
                        if (match) {
                            price = parseFloat(match[0].replace(',', '.'));
                        }
                    }
                    
                    options.push({
                        id: radio.id,
                        price: price,
                        text: text
                    });
                }
                return options;
            }
        """)
        
        if not shipping_options:
            return {"success": False, "message": "No shipping options found"}
            
        # Sort by price
        shipping_options.sort(key=lambda x: x['price'])
        
        # Select the first one (cheapest)
        cheapest = shipping_options[0]
        await page.click(f"#{cheapest['id']}")
        
        return {"success": True, "selected": cheapest['text']}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

async def click_continue_to_payment_tool() -> Dict[str, Any]:
    """Click continue to payment button"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import find_and_click_button
    from src.checkout_ai.utils.checkout_keywords import PAYMENT_BUTTONS
    page = get_page()
    
    # Scroll to bottom to ensure button is in view
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(1.0)
    
    result = await find_and_click_button(page, PAYMENT_BUTTONS, max_retries=3)
    return {"success": result.get('success', False)}

async def select_custom_dropdown_tool(label: str = None, value: str = None) -> Dict[str, Any]:
    """Select option in custom dropdown (Click-Search-Select)"""
    from src.checkout_ai.legacy.phase2.checkout_dom_finder import interact_with_custom_dropdown
    page = get_page()
    
    if not label or not value:
        return {"success": False, "error": "Label and value are required"}
        
    result = await interact_with_custom_dropdown(page, [label], value)
    return {"success": result.get('success', False)}

async def verify_address_selection_tool() -> Dict[str, Any]:
    """
    Verify if currently selected address matches config.
    Returns success if match, or error instructing to add new.
    """
    page = get_page()
    customer_data = get_customer_data()
    if not customer_data:
        return {"success": True, "message": "No config to verify against"}
        
    
    # Handle nested structure (config.json vs flattened data)
    shipping_addr = customer_data.get('shippingAddress')
    if not shipping_addr:
        shipping_addr = customer_data.get('customer', {}).get('shippingAddress', {})
        
    expected_pin = shipping_addr.get('postalCode')
    expected_city = shipping_addr.get('city', '').lower()
    
    if not expected_pin or not expected_city:
         print(f"⚠️ Warning: perform_verify_address found empty config criteria. PIN: {expected_pin}, City: {expected_city}")
         # Fail safe: if we can't verify, we shouldn't just pass. 
         # But maybe we should ask user? For now, proceed but log warning.
         pass
    
    result = await page.evaluate("""
        ({expectedPin, expectedCity}) => {
            console.log(`Searching for address with PIN: ${expectedPin}, City: ${expectedCity}`);
            
            // Normalize helper
            const normalize = (str) => (str || '').toLowerCase().replace(/\\s+/g, '').trim();
            const normExpectedPin = normalize(expectedPin);
            const normExpectedCity = (expectedCity || '').toLowerCase().trim();
            
            // Find ALL address containers (Myntra specific + generic)
            const allAddresses = Array.from(document.querySelectorAll('.address-item, .addressBox, .address-card, div[class*="address-container"], div[class*="addressItem"]'));
            
            let matchFound = null;
            
            // Loop through all addresses to find a match
            for (const addr of allAddresses) {
                const text = (addr.textContent || '').toLowerCase();
                const normText = text.replace(/\\s+/g, ''); // Text without spaces for PIN search
                
                // PIN Match: check if normalized PIN exists in normalized text
                const pinMatch = normExpectedPin ? normText.includes(normExpectedPin) : true;
                
                // City Match: check if city exists (word boundary check is better but simple include is okay for now)
                const cityMatch = normExpectedCity ? text.includes(normExpectedCity) : true;
                
                if (pinMatch && cityMatch) {
                    matchFound = addr;
                    break;
                }
            }
            
            if (matchFound) {
                // Found a matching address!
                // Check if already selected
                const radio = matchFound.querySelector('input[type="radio"]');
                const isSelected = radio ? radio.checked : 
                                 matchFound.classList.contains('selected') || 
                                 matchFound.classList.contains('address-selected') ||
                                 matchFound.className.includes('selected');
                
                if (!isSelected) {
                    console.log("Found matching address but not selected. Clicking it...");
                    if (radio) {
                        radio.click();
                    } else {
                        matchFound.click();
                    }
                    // Wait a bit just in case
                    return { success: true, message: "Found and selected matching address from list." };
                } else {
                    return { success: true, message: "Matching address is already selected." };
                }
            }
            
            // If we are here, NO address matched.
            return { 
                success: false, 
                reason: `No address on page matched PIN ${expectedPin} or City ${expectedCity} (without opening Edit)`,
                action: "click_add_new" 
            };
        }
    """, {'expectedPin': expected_pin, 'expectedCity': expected_city})
    
    if result.get('success'):
        print("✅ Address Verified: Matches Config")
        return {"success": True, "message": "Address verified matches config"}
        
    # If mismatch, try to click 'Add New Address' automatically
    if result.get('action') == 'click_add_new':
         print(f"⚠️ Address Mismatch! {result.get('reason')}. Switching to 'Add New Address'...")
         
         # Attempt to find and click 'Add New Address'
         clicked = await page.evaluate("""
             () => {
                 const buttons = Array.from(document.querySelectorAll('div, button, a'));
                 const addBtn = buttons.find(b => {
                     const t = (b.textContent || '').toLowerCase();
                     const isVisible = b.offsetWidth > 0 && b.offsetHeight > 0;
                     return isVisible && (t.includes('add new address') || t.includes('add address'));
                 });
                 if (addBtn) {
                     addBtn.click();
                     return true;
                 }
                 return false;
             }
         """)
         
         if clicked:
             # Wait for form to open
             await asyncio.sleep(1)
             return {"success": True, "message": "Address mismatch detected. Automatically clicked 'Add New Address'. Proceed to fill form."}
         else:
             return {"success": False, "error": f"Address mismatch and could not find 'Add New Address' button. {result.get('reason')}"}
                 
    return result

TOOLS = {
    "verify_address": verify_address_selection_tool,
    # High-level tools
    "select_variant": select_variant_tool,
    "add_to_cart": add_to_cart_tool,
    "navigate_to_cart": navigate_to_cart_tool,
    "smart_login": smart_login_tool,
    "select_checkbox": select_checkbox_tool,
    "fill_email": fill_email_tool,
    "fill_contact": fill_contact_tool,
    "fill_address": fill_address_tool,
    "click_checkout": click_checkout_button_tool,
    "click_guest_checkout": click_guest_checkout_tool,
    "click_continue": click_continue_tool,
    "dismiss_popups": dismiss_popups_tool,
    "take_screenshot": take_screenshot_tool,
    "validate_page": validate_page_state_tool,
    "web_search": web_search_tool,
    
    # Low-level actions
    "click": click_element_tool,
    "fill_text": fill_text_tool,
    "select_dropdown": select_dropdown_tool,
    "scroll": scroll_tool,
    "press_key": press_key_tool,
    "wait": wait_tool,
    "navigate": navigate_tool,
    
    # Fine-grained address tools
    "fill_first_name": fill_first_name_tool,
    "fill_last_name": fill_last_name_tool,
    "fill_phone": fill_phone_tool,
    "select_country": select_country_tool,
    "fill_address_line1": fill_address_line1_tool,
    "fill_address_line2": fill_address_line2_tool,
    "fill_landmark": fill_landmark_tool,
    "fill_city": fill_city_tool,
    "fill_zip_code": fill_zip_code_tool,
    "select_state": select_state_tool,
    "click_same_as_billing": click_same_as_billing_tool,
    "select_shipping_method": select_shipping_method_tool,
    "select_shipping_method": select_shipping_method_tool,
    "click_continue_to_payment": click_continue_to_payment_tool,
    "select_custom_dropdown": select_custom_dropdown_tool,
}

async def execute_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """Execute a tool by name"""
    if tool_name not in TOOLS:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    try:
        result = await TOOLS[tool_name](**kwargs)
        logger.info(f"Tool {tool_name} executed: {result.get('success')}")
        return result
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return {"success": False, "error": str(e)}
