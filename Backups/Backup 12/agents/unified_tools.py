"""Unified Tool System - All browser automation tools for agents"""
import asyncio
import logging
from typing import Dict, Any, Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Global page context
_PAGE: Optional[Page] = None

def set_page(page: Page):
    global _PAGE
    _PAGE = page

def get_page() -> Page:
    if _PAGE is None:
        raise ValueError("Page not set")
    return _PAGE

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

async def fill_email_tool(email: str) -> Dict[str, Any]:
    """Fill email field"""
    from phase2.checkout_dom_finder import fill_input_field
    from shared.checkout_keywords import EMAIL_LABELS
    page = get_page()
    result = await fill_input_field(page, EMAIL_LABELS, email, max_retries=3)
    return {"success": result.get('success', False)}

async def fill_contact_tool(first_name: str, last_name: str, phone: str) -> Dict[str, Any]:
    """Fill contact fields"""
    from phase2.checkout_dom_finder import fill_input_field
    from shared.checkout_keywords import FIRST_NAME_LABELS, LAST_NAME_LABELS, PHONE_LABELS
    page = get_page()
    
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
    
    return {"success": all(results), "filled_count": sum(results)}

async def fill_address_tool(address: str, city: str, state: str, zip_code: str) -> Dict[str, Any]:
    """Fill address fields"""
    from phase2.checkout_dom_finder import fill_input_field, find_and_select_dropdown
    from shared.checkout_keywords import ADDRESS_LINE1_LABELS, CITY_LABELS, STATE_LABELS, POSTAL_CODE_LABELS
    page = get_page()
    
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
    
    return {"success": sum(results) >= 3, "filled_count": sum(results)}

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
    """Get current page state"""
    page = get_page()
    url = page.url
    title = await page.title()
    
    fields = await page.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]), select, textarea'))
                .filter(el => el.offsetParent)
                .slice(0, 10)
                .map(el => ({
                    type: el.type || el.tagName.toLowerCase(),
                    name: el.name || el.id || '',
                    placeholder: el.placeholder || ''
                }));
            return inputs;
        }
    """)
    
    return {"success": True, "url": url, "title": title, "fields": fields}

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
