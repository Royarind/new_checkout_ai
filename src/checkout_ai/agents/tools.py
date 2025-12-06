import logging
import asyncio
from typing import Dict, Any, List, Optional
from playwright.async_api import Page

# Import existing robust logic
from src.checkout_ai.dom.service import UniversalDOMFinder
from src.checkout_ai.legacy.phase1.add_to_cart_robust import add_to_cart_robust
from src.checkout_ai.legacy.phase2.smart_form_filler import SmartFormFiller
from src.checkout_ai.legacy.phase2.checkout_flow import run_checkout_flow
from src.checkout_ai.legacy.phase2.ai_checkout_flow import run_ai_checkout_flow

logger = logging.getLogger(__name__)

# Global page context
_PAGE: Optional[Page] = None

def set_page(page: Page):
    """Set the global page context for tools."""
    global _PAGE
    _PAGE = page
    logger.info("Tools: Page context set")

def get_page() -> Page:
    """Get the global page context."""
    if _PAGE is None:
        raise ValueError("Page context not set. Call set_page() first.")
    return _PAGE

async def variant_selection_tool(variant_type: str, variant_value: str) -> str:
    """
    Selects a product variant (e.g., Color, Size) on the current page.
    
    Args:
        variant_type: The type of variant (e.g., 'color', 'size', 'memory').
        variant_value: The value to select (e.g., 'Black', 'XL', '256GB').
        
    Returns:
        A string describing the result of the operation.
    """
    page = get_page()
    logger.info(f"TOOL: Selecting {variant_type}={variant_value}")
    
    try:
        finder = UniversalDOMFinder(page)
        result = await finder.find_variant_dom(page, variant_type, variant_value)
        
        if result['success']:
            return f"Successfully selected {variant_type}: {variant_value}"
        else:
            return f"Failed to select {variant_type} '{variant_value}'. Error: {result.get('error', 'Unknown error')}"
    except Exception as e:
        logger.error(f"TOOL: Variant selection failed: {e}")
        return f"Error selecting {variant_type}: {str(e)}"

async def add_to_cart_tool() -> str:
    """
    Adds the currently selected product to the shopping cart.
    
    Returns:
        A string describing the result of the operation.
    """
    page = get_page()
    logger.info("TOOL: Adding to cart")
    
    try:
        # Use the robust add to cart function
        result = await add_to_cart_robust(page)
        
        if result['success']:
            return "Successfully added product to cart."
        else:
            return f"Failed to add to cart. Error: {result.get('error', 'Unknown error')}"
    except Exception as e:
        logger.error(f"TOOL: Add to cart failed: {e}")
        return f"Error adding to cart: {str(e)}"

async def checkout_tool(customer_data: Dict[str, Any]) -> str:
    """
    Performs the checkout process using the provided customer data.
    
    Args:
        customer_data: Dictionary containing 'email', 'shipping_address', 'payment_info', etc.
        
    Returns:
        A string describing the result of the checkout process.
    """
    page = get_page()
    logger.info("TOOL: Starting checkout")
    
    try:
        # Try AI checkout flow first as it's more robust
        result = await run_ai_checkout_flow(page, customer_data)
        
        if result['success']:
            return "Checkout completed successfully."
        else:
            # Fallback to rule-based if AI fails (though run_ai_checkout_flow might handle fallback)
            return f"Checkout failed. Reason: {result.get('message', 'Unknown error')}"
    except Exception as e:
        logger.error(f"TOOL: Checkout failed: {e}")
        return f"Error during checkout: {str(e)}"

async def get_page_details_tool() -> str:
    """
    Returns a summary of the current page state, including URL and key interactive elements.
    Useful for understanding what to do next.
    """
    page = get_page()
    url = page.url
    title = await page.title()
    
    # Get a simplified representation of interactive elements
    # This is a basic implementation, could be enhanced with get_dom_fields logic if available
    return f"Current Page: {title}\nURL: {url}\n"

async def navigate_tool(url: str) -> str:
    """
    Navigates the browser to the specified URL.
    """
    page = get_page()
    try:
        await page.goto(url, wait_until='domcontentloaded')
        return f"Navigated to {url}"
    except Exception as e:
        return f"Navigation failed: {e}"

async def google_search_tool(query: str) -> str:
    """
    Performs a google search (simulated via direct navigation for now, or use API if available).
    """
    page = get_page()
    # For now, just navigate to google search results
    encoded_query = query.replace(' ', '+')
    url = f"https://www.google.com/search?q={encoded_query}"
    await page.goto(url, wait_until='domcontentloaded')
    return f"Performed Google search for '{query}'. Results are displayed on the page."

def get_agent_tools() -> List[Any]:
    """Return a list of available tools for the agent."""
    return [
        variant_selection_tool,
        add_to_cart_tool,
        checkout_tool,
        get_page_details_tool,
        navigate_tool,
        google_search_tool
    ]
