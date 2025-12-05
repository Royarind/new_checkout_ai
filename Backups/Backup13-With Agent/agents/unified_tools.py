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
    from phase1.universal_dom_finder import find_variant_dom
    page = get_page()
    result = await find_variant_dom(page, variant_type, variant_value)
    return {"success": result.get('success', False), "message": result.get('content', '')}

async def add_to_cart_tool() -> Dict[str, Any]:
    """Add product to cart"""
    from phase1.add_to_cart_robust import add_to_cart_robust
    page = get_page()
    result = await add_to_cart_robust(page)
    return {"success": result.get('success', False), "message": result.get('content', '')}

async def navigate_to_cart_tool() -> Dict[str, Any]:
    """Navigate to cart page"""
    from phase1.cart_navigator import navigate_to_cart
    page = get_page()
    result = await navigate_to_cart(page)
    return {"success": result.get('success', False), "cart_url": result.get('cart_url', '')}

async def fill_email_tool(email: str = None) -> Dict[str, Any]:
    """Fill email field"""
    from phase2.checkout_dom_finder import fill_input_field
    from shared.checkout_keywords import EMAIL_LABELS
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
    """Fill contact fields"""
    from phase2.checkout_dom_finder import fill_input_field
    from shared.checkout_keywords import FIRST_NAME_LABELS, LAST_NAME_LABELS, PHONE_LABELS
    page = get_page()
    
    # Use provided values or get from customer data
    customer_data = get_customer_data()
    if customer_data:
        contact = customer_data.get('contact', {})
        first_name = first_name or contact.get('firstName')
        last_name = last_name or contact.get('lastName')
        phone = phone or contact.get('phone')
    
    results = []
    if first_name:
        r = await fill_input_field(page, FIRST_NAME_LABELS, first_name, max_retries=2)
        results.append(r.get('success', False))
    if last_name:
        r = await fill_input_field(page, LAST_NAME_LABELS, last_name, max_retries=2)
        results.append(r.get('success', False))
    if phone:
        r = await fill_input_field(page, PHONE_LABELS, phone, max_retries=2)
        results.append(r.get('success', False))
    
    return {"success": all(results) if results else False, "filled_count": sum(results)}

async def fill_address_tool(address: str = None, city: str = None, state: str = None, zip_code: str = None) -> Dict[str, Any]:
    """Fill address fields"""
    from phase2.checkout_dom_finder import fill_input_field, find_and_select_dropdown
    from shared.checkout_keywords import ADDRESS_LINE1_LABELS, CITY_LABELS, STATE_LABELS, POSTAL_CODE_LABELS
    page = get_page()
    
    # Use provided values or get from customer data
    customer_data = get_customer_data()
    if customer_data:
        addr = customer_data.get('shippingAddress', {})
        address = address or addr.get('addressLine1')
        city = city or addr.get('city')
        state = state or addr.get('province')
        zip_code = zip_code or addr.get('postalCode')
    
    results = []
    if address:
        r = await fill_input_field(page, ADDRESS_LINE1_LABELS, address, max_retries=3)
        results.append(r.get('success', False))
        await asyncio.sleep(1)
    if zip_code:
        r = await fill_input_field(page, POSTAL_CODE_LABELS, zip_code, max_retries=3)
        results.append(r.get('success', False))
    if city:
        r = await fill_input_field(page, CITY_LABELS, city, max_retries=2)
        results.append(r.get('success', False))
    if state:
        r = await find_and_select_dropdown(page, STATE_LABELS, state)
        results.append(r.get('success', False))
    
    return {"success": sum(results) >= 3 if results else False, "filled_count": sum(results)}

async def click_checkout_button_tool() -> Dict[str, Any]:
    """Click checkout/proceed button"""
    from phase2.checkout_dom_finder import find_and_click_button
    from shared.checkout_keywords import CHECKOUT_BUTTONS
    page = get_page()
    result = await find_and_click_button(page, CHECKOUT_BUTTONS, max_retries=3)
    return {"success": result.get('success', False)}

async def click_guest_checkout_tool() -> Dict[str, Any]:
    """Click guest checkout button"""
    from phase2.checkout_dom_finder import find_and_click_button
    from shared.checkout_keywords import GUEST_CHECKOUT_BUTTONS
    page = get_page()
    result = await find_and_click_button(page, GUEST_CHECKOUT_BUTTONS, max_retries=2)
    return {"success": result.get('success', False)}

async def click_continue_tool() -> Dict[str, Any]:
    """Click continue/next button"""
    from phase2.checkout_dom_finder import find_and_click_button
    from shared.checkout_keywords import CONTINUE_BUTTONS
    page = get_page()
    result = await find_and_click_button(page, CONTINUE_BUTTONS, max_retries=2)
    return {"success": result.get('success', False)}

async def dismiss_popups_tool() -> Dict[str, Any]:
    """Dismiss all popups and modals"""
    from shared.popup_dismisser import dismiss_popups
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
                .slice(0, 15)
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
                .slice(0, 15)
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

TOOLS = {
    # High-level tools
    "select_variant": select_variant_tool,
    "add_to_cart": add_to_cart_tool,
    "navigate_to_cart": navigate_to_cart_tool,
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
