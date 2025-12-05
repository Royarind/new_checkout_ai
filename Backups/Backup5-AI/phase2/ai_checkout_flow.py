"""
AI-Driven Checkout Flow
Uses LLM to analyze page and execute checkout stages with DOM tools
"""

import asyncio
import json
from datetime import datetime
from shared.logger_config import setup_logger, log
from shared.popup_dismisser import dismiss_popups
from agent.llm_client import LLMClient

logger = setup_logger('ai_checkout')


# Tool definitions for LLM
CHECKOUT_TOOLS = {
    "find_and_click_button": {
        "description": "Find and click a button by text/label matching",
        "parameters": {"keywords": "list[str]", "max_retries": "int"},
        "returns": {"success": "bool", "matched_text": "str", "error": "str"}
    },
    "fill_input_field": {
        "description": "Fill an input field by label matching",
        "parameters": {"label_keywords": "list[str]", "value": "str", "max_retries": "int"},
        "returns": {"success": "bool", "error": "str"}
    },
    "find_and_select_dropdown": {
        "description": "Select dropdown option by label and value matching",
        "parameters": {"label_keywords": "list[str]", "option_value": "str", "max_retries": "int"},
        "returns": {"success": "bool", "error": "str"}
    },
    "get_page_state": {
        "description": "Get current page state including URL, visible buttons, and form fields",
        "parameters": {},
        "returns": {"url": "str", "buttons": "list", "fields": "list"}
    }
}


async def get_page_state(page):
    """Extract current page state for LLM analysis"""
    try:
        state = await page.evaluate("""
            () => {
                // Get all visible buttons and links
                const buttons = Array.from(document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"]'))
                    .filter(el => {
                        if (!el.offsetParent) return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    })
                    .slice(0, 30)
                    .map(el => ({
                        tag: el.tagName.toLowerCase(),
                        text: (el.textContent?.trim() || el.value || '').substring(0, 100),
                        ariaLabel: el.getAttribute('aria-label') || '',
                        className: el.className || '',
                        id: el.id || '',
                        href: el.href || ''
                    }));
                
                // Get all visible form fields
                const fields = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select, textarea'))
                    .filter(el => el.offsetParent && el.getBoundingClientRect().width > 0)
                    .slice(0, 15)
                    .map(el => {
                        const label = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
                        return {
                            type: el.type || el.tagName.toLowerCase(),
                            name: el.name || '',
                            id: el.id || '',
                            placeholder: el.placeholder || '',
                            label: label?.textContent?.trim() || '',
                            autocomplete: el.autocomplete || '',
                            value: el.value || '',
                            required: el.required
                        };
                    });
                
                console.log(`Found ${buttons.length} buttons, ${fields.length} fields`);
                
                return {
                    url: window.location.href,
                    title: document.title,
                    buttons: buttons,
                    fields: fields
                };
            }
        """)
        
        return state
    except Exception as e:
        log(logger, 'error', f"Error getting page state: {e}", 'CHECKOUT', 'DOM')
        return {"url": page.url, "buttons": [], "fields": []}


async def _find_minicart_with_ai(page, llm_client):
    """Use AI to intelligently find mini-cart icon"""
    log(logger, 'info', 'AI: Searching for mini-cart icon...', 'CHECKOUT', 'LLM')
    
    # Get all clickable elements in header/nav area
    cart_elements = await page.evaluate("""
        () => {
            const elements = Array.from(document.querySelectorAll('header *, nav *, [class*="header"] *, [class*="nav"] *'))
                .filter(el => {
                    if (!el.offsetParent) return false;
                    const rect = el.getBoundingClientRect();
                    return rect.top < 200 && rect.width > 0 && rect.height > 0;
                })
                .slice(0, 50)
                .map(el => ({
                    tag: el.tagName.toLowerCase(),
                    text: (el.textContent?.trim() || '').substring(0, 50),
                    ariaLabel: el.getAttribute('aria-label') || '',
                    className: el.className || '',
                    id: el.id || '',
                    href: el.href || ''
                }));
            return elements;
        }
    """)
    
    prompt = f"""Find the mini-cart/shopping cart icon in the header.

=== HEADER ELEMENTS ===
{json.dumps(cart_elements, indent=2)}

=== TASK ===
Find the element that represents the shopping cart icon (usually in top-right corner).

Look for:
- Text containing: "cart", "bag", "basket", or cart item count (e.g., "2 items")
- ClassName containing: "cart", "bag", "basket", "minicart"
- AriaLabel containing: "cart", "bag", "shopping"
- Links (href) to /cart, /bag, /basket

=== RESPONSE ===
{{
    "reasoning": "Element is cart icon because...",
    "keywords": ["cart", "shopping cart"],
    "confidence": 0.9
}}

Return confidence < 0.5 if no cart icon found.
RESPOND ONLY WITH JSON."""
    
    try:
        response = await llm_client.complete(prompt, max_tokens=300)
        if response.get('confidence', 0) >= 0.5:
            keywords = response.get('keywords', ['cart'])
            log(logger, 'info', f"AI found cart icon with keywords: {keywords}", 'CHECKOUT', 'LLM')
            return keywords
    except Exception as e:
        log(logger, 'error', f"AI cart search error: {e}", 'CHECKOUT', 'LLM')
    
    return None


async def _recovery_checkout_navigation(page, llm_client, retry_count, max_retries, original_url=None):
    """Recovery mechanism for checkout navigation with 3 strategies"""
    retry_count += 1
    log(logger, 'warning', f'=== RECOVERY ATTEMPT {retry_count}/{max_retries} ===', 'CHECKOUT', 'CORE')
    
    # Save original URL on first recovery attempt
    if original_url is None:
        original_url = page.url
        log(logger, 'info', f'Saved original URL: {original_url}', 'CHECKOUT', 'CORE')
    
    # Strategy 1: AI-powered mini-cart icon search
    if retry_count == 1:
        log(logger, 'info', 'Recovery Strategy 1: AI-powered mini-cart search', 'CHECKOUT', 'CORE')
        
        cart_keywords = await _find_minicart_with_ai(page, llm_client)
        
        if cart_keywords:
            from phase2.checkout_dom_finder import find_and_click_button
            result = await find_and_click_button(page, cart_keywords, max_retries=2)
            
            if result.get('success'):
                log(logger, 'info', 'Mini-cart icon clicked, waiting for cart...', 'CHECKOUT', 'CORE')
                await asyncio.sleep(3)
                return await ai_proceed_to_checkout(page, llm_client, retry_count, max_retries)
        
        log(logger, 'warning', 'AI could not find mini-cart icon', 'CHECKOUT', 'CORE')
        return await _recovery_checkout_navigation(page, llm_client, retry_count, max_retries, original_url)
    
    # Strategy 2: Navigate to /cart URL directly and verify checkout button exists
    elif retry_count == 2:
        log(logger, 'info', 'Recovery Strategy 2: Direct cart URL navigation', 'CHECKOUT', 'CORE')
        
        from urllib.parse import urlparse
        parsed = urlparse(original_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        log(logger, 'info', f'Base URL: {base_url}', 'CHECKOUT', 'CORE')
        
        cart_paths = ['/cart', '/checkout', '/bag', '/basket', '/shopping-cart', '/shopping-bag', '/checkout/cart']
        
        for i, cart_path in enumerate(cart_paths):
            cart_url = base_url + cart_path
            log(logger, 'info', f'[{i+1}/{len(cart_paths)}] Trying: {cart_url}', 'CHECKOUT', 'CORE')
            
            try:
                response = await page.goto(cart_url, wait_until='domcontentloaded', timeout=10000)
                
                # Check if page loaded successfully (not 404)
                if response and response.status >= 400:
                    log(logger, 'warning', f'HTTP {response.status} - skipping', 'CHECKOUT', 'CORE')
                    continue
                
                await asyncio.sleep(2)
                page_url = page.url.lower()
                
                # Verify we're on a cart/checkout page
                if 'cart' in page_url or 'bag' in page_url or 'basket' in page_url or 'checkout' in page_url:
                    log(logger, 'info', f'Successfully navigated to: {page_url}', 'CHECKOUT', 'CORE')
                    await dismiss_popups(page)
                    await asyncio.sleep(1)
                    
                    # Validate page: check for checkout button OR checkout form fields
                    state = await get_page_state(page)
                    
                    # Check 1: Checkout button exists
                    has_checkout_btn = any('checkout' in btn.get('text', '').lower() or 
                                          'checkout' in btn.get('className', '').lower() or
                                          'checkout' in btn.get('ariaLabel', '').lower()
                                          for btn in state['buttons'])
                    
                    # Check 2: Already on checkout page (has email/guest checkout/form fields)
                    has_email_field = any('email' in field.get('name', '').lower() or 
                                         'email' in field.get('id', '').lower() or
                                         'email' in field.get('autocomplete', '').lower() or
                                         field.get('type') == 'email'
                                         for field in state['fields'])
                    
                    has_guest_btn = any('guest' in btn.get('text', '').lower() or
                                       'continue as guest' in btn.get('text', '').lower()
                                       for btn in state['buttons'])
                    
                    has_checkout_form = len(state['fields']) >= 3  # Likely checkout form
                    
                    is_checkout_page = 'checkout' in page_url
                    
                    if has_checkout_btn:
                        log(logger, 'info', f'✓ Checkout button found on {page_url}', 'CHECKOUT', 'CORE')
                        return await ai_proceed_to_checkout(page, llm_client, retry_count, max_retries)
                    elif is_checkout_page and (has_email_field or has_guest_btn or has_checkout_form):
                        log(logger, 'info', f'✓ Already on checkout page with form fields: {page_url}', 'CHECKOUT', 'CORE')
                        log(logger, 'info', f'  Email field: {has_email_field}, Guest button: {has_guest_btn}, Form fields: {len(state["fields"])}', 'CHECKOUT', 'CORE')
                        return {'success': True}  # Already on checkout, skip to next stage
                    else:
                        log(logger, 'warning', f'✗ No checkout indicators on {page_url}, trying next URL', 'CHECKOUT', 'CORE')
                        continue
                else:
                    log(logger, 'warning', f'Redirected to: {page_url} - not a cart page', 'CHECKOUT', 'CORE')
                    continue
                    
            except Exception as e:
                log(logger, 'warning', f'Failed to load {cart_url}: {str(e)[:50]}', 'CHECKOUT', 'CORE')
                continue
        
        log(logger, 'warning', 'All cart URLs exhausted without finding checkout button', 'CHECKOUT', 'CORE')
        return await _recovery_checkout_navigation(page, llm_client, retry_count, max_retries, original_url)
    
    # Strategy 3: Return to original URL and retry
    elif retry_count == 3:
        log(logger, 'info', f'Recovery Strategy 3: Returning to original URL and retry', 'CHECKOUT', 'CORE')
        log(logger, 'info', f'Navigating back to: {original_url}', 'CHECKOUT', 'CORE')
        
        try:
            await page.goto(original_url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(2)
            await dismiss_popups(page)
            await asyncio.sleep(1)
            return await ai_proceed_to_checkout(page, llm_client, retry_count, max_retries)
        except Exception as e:
            log(logger, 'error', f'Failed to return to original URL: {e}', 'CHECKOUT', 'CORE')
    
    # All strategies exhausted
    log(logger, 'error', 'All recovery strategies exhausted', 'CHECKOUT', 'CORE')
    return {'success': False, 'error': 'Failed to navigate to checkout after all recovery attempts'}


async def execute_tool(page, tool_name, params):
    """Execute a DOM tool and return result"""
    from phase2.checkout_dom_finder import (
        find_and_click_button,
        fill_input_field,
        find_and_select_dropdown
    )
    from shared.popup_dismisser import dismiss_popups
    
    try:
        if tool_name == "dismiss_popups":
            await dismiss_popups(page)
            return {"success": True}
        elif tool_name == "wait":
            await asyncio.sleep(params.get('seconds', 1))
            return {"success": True}
        elif tool_name == "find_and_click_button":
            return await find_and_click_button(page, params['keywords'], params.get('max_retries', 3))
        elif tool_name == "fill_input_field":
            return await fill_input_field(page, params['label_keywords'], params['value'], params.get('max_retries', 3))
        elif tool_name == "find_and_select_dropdown":
            return await find_and_select_dropdown(page, params['label_keywords'], params['option_value'], params.get('max_retries', 2))
        elif tool_name == "get_page_state":
            return await get_page_state(page)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        log(logger, 'error', f"Tool execution error ({tool_name}): {e}", 'CHECKOUT', 'CORE')
        return {"success": False, "error": str(e)}


async def ai_proceed_to_checkout(page, llm_client, retry_count=0, max_retries=3):
    """AI-driven checkout button click with recovery mechanisms"""
    log(logger, 'info', f'AI: Analyzing page to find checkout button (attempt {retry_count + 1}/{max_retries})...', 'CHECKOUT', 'LLM')
    
    await dismiss_popups(page)
    await asyncio.sleep(1)
    
    # Get page state
    state = await get_page_state(page)
    
    # Check if already on checkout page
    page_url = state['url'].lower()
    if 'checkout' in page_url:
        # Validate we're actually on checkout (has email field or form fields)
        has_email_field = any('email' in field.get('name', '').lower() or 
                             'email' in field.get('id', '').lower() or
                             'email' in field.get('autocomplete', '').lower() or
                             field.get('type') == 'email'
                             for field in state['fields'])
        
        has_checkout_form = len(state['fields']) >= 2
        
        if has_email_field or has_checkout_form:
            log(logger, 'info', f'Already on checkout page: {page_url}', 'CHECKOUT', 'LLM')
            log(logger, 'info', f'Email field: {has_email_field}, Form fields: {len(state["fields"])}', 'CHECKOUT', 'LLM')
            return {'success': True}  # Skip button click, already on checkout
    
    # Debug: Log what buttons we found
    log(logger, 'info', f"Found {len(state['buttons'])} buttons on page", 'CHECKOUT', 'DOM')
    for i, btn in enumerate(state['buttons'][:10]):
        log(logger, 'info', f"Button {i+1}: text='{btn['text'][:50]}' class='{btn['className'][:30]}'", 'CHECKOUT', 'DOM')
    
    # Build prompt
    prompt = f"""You are an expert e-commerce checkout automation agent. Your task is to identify and click the checkout button.

=== CURRENT PAGE STATE ===
URL: {state['url']}
Page Title: {state['title']}

=== VISIBLE BUTTONS (Top 20) ===
{json.dumps(state['buttons'], indent=2)}

=== YOUR TASK ===
You are currently on the CART PAGE. Items are already added to cart.
Your ONLY job is to find and click the CHECKOUT button to proceed to the checkout page.

=== CHECKOUT BUTTON PATTERNS ===
Look for buttons with text containing (case-insensitive):
- "Checkout" / "Check out" / "Check Out"
- "Proceed to Checkout" / "Go to Checkout" / "PROCEDE TO CHECKOUT"
- "Secure Checkout" / "Continue to Checkout"
- "Begin Checkout" / "Start Checkout"
- "Place Order" (if clearly a checkout button)

AVOID these buttons (NOT checkout buttons):
- "Add to Cart" / "Add to Bag" / "Add to Basket"
- "Continue Shopping" / "Keep Shopping" / "Shop More"
- "Update Cart" / "Update Basket"
- "Apply Coupon" / "Apply Discount"
- "Save for Later" / "Move to Wishlist"
- Social media share buttons
- "View Cart" / "Go to Cart" (you're already on cart)

=== ANALYSIS STEPS ===
1. Look through the buttons list above
2. Find buttons with "checkout" in text, ariaLabel, or className
3. Select the most prominent checkout button
4. Return the keywords that will match that button

=== REQUIRED JSON RESPONSE ===
{{
    "reasoning": "I found a button with text '[BUTTON_TEXT]' which is the checkout button because [REASON]",
    "tool": "find_and_click_button",
    "params": {{
        "keywords": ["checkout", "proceed to checkout"],
        "max_retries": 3
    }},
    "confidence": 0.95
}}

=== CONFIDENCE SCORING ===
- 0.9-1.0: Found button with "checkout" in text (exact match)
- 0.7-0.9: Found button with "checkout" in className or ariaLabel
- 0.5-0.7: Found button that might be checkout ("proceed", "continue")
- < 0.5: No checkout button found in the list

=== IMPORTANT ===
- If you find ANY button with "checkout" in it, return confidence >= 0.9
- The keywords array should contain variations that will match the button
- If NO checkout button found, return confidence < 0.5 and explain why

RESPOND ONLY WITH VALID JSON. NO MARKDOWN, NO CODE BLOCKS."""

    try:
        log(logger, 'info', f"Sending prompt to LLM with {len(state['buttons'])} buttons", 'CHECKOUT', 'LLM')
        response = await llm_client.complete(prompt, max_tokens=500)
        log(logger, 'info', f"AI reasoning: {response.get('reasoning', 'N/A')}", 'CHECKOUT', 'LLM')
        log(logger, 'info', f"AI confidence: {response.get('confidence', 0)}", 'CHECKOUT', 'LLM')
        
        if response.get('confidence', 0) < 0.5:
            log(logger, 'warning', 'AI: Low confidence, checkout button not found', 'CHECKOUT', 'LLM')
            log(logger, 'warning', f"Buttons found: {len(state['buttons'])}", 'CHECKOUT', 'LLM')
            
            # Try recovery mechanisms
            if retry_count < max_retries:
                return await _recovery_checkout_navigation(page, llm_client, retry_count, max_retries, original_url=None)
            else:
                log(logger, 'error', f'AI: Max retries ({max_retries}) reached, checkout failed', 'CHECKOUT', 'LLM')
                return {'success': False, 'error': 'Checkout button not found after all recovery attempts'}
        
        # Execute tool
        tool_name = response.get('tool')
        params = response.get('params', {})
        
        result = await execute_tool(page, tool_name, params)
        
        if result.get('success'):
            log(logger, 'info', f"AI: Successfully clicked checkout button", 'CHECKOUT', 'LLM')
            await asyncio.sleep(3)
            return {'success': True}
        else:
            log(logger, 'error', f"AI: Failed to click checkout: {result.get('error')}", 'CHECKOUT', 'LLM')
            
            # Try recovery if retries available
            if retry_count < max_retries:
                return await _recovery_checkout_navigation(page, llm_client, retry_count, max_retries, original_url=None)
            else:
                return result
            
    except Exception as e:
        log(logger, 'error', f"AI checkout error: {e}", 'CHECKOUT', 'LLM')
        return {'success': False, 'error': str(e)}


async def ai_handle_guest_checkout(page, llm_client):
    """AI-driven guest checkout selection"""
    log(logger, 'info', 'AI: Analyzing page for guest checkout option...', 'CHECKOUT', 'LLM')
    
    await dismiss_popups(page)
    await asyncio.sleep(1)
    
    state = await get_page_state(page)
    
    prompt = f"""You are an expert e-commerce checkout automation agent. Your task is to handle guest checkout selection.

=== CURRENT PAGE STATE ===
URL: {state['url']}

=== VISIBLE BUTTONS ===
{json.dumps(state['buttons'], indent=2)}

=== YOUR TASK ===
Determine if there is a guest checkout option and click it if present.

=== GUEST CHECKOUT PATTERNS ===
Look for buttons with text:
- "Guest Checkout" / "Checkout as Guest"
- "Continue as Guest" / "Continue without Account"
- "Guest" (standalone)
- "Skip Registration" / "No Account Needed"

=== DECISION LOGIC ===
1. If you see a clear guest checkout button → Click it (confidence 0.8-1.0)
2. If you see login/register form but NO guest option → Return confidence 0.3 (already on guest form)
3. If page shows contact/shipping fields directly → Return confidence 0.2 (no guest button needed)

=== REQUIRED JSON RESPONSE ===
{{
    "reasoning": "Explain: Did you find guest button? If not, why is it not needed?",
    "tool": "find_and_click_button",
    "params": {{
        "keywords": ["guest checkout", "continue as guest", "checkout as guest"],
        "max_retries": 3
    }},
    "confidence": 0.85
}}

=== CONFIDENCE SCORING ===
- 0.8-1.0: Clear guest checkout button found
- 0.5-0.8: Possible guest option
- 0.2-0.5: Already on guest form or no button needed
- < 0.2: Uncertain state

RESPOND ONLY WITH VALID JSON."""

    try:
        response = await llm_client.complete(prompt, max_tokens=400)
        log(logger, 'info', f"AI reasoning: {response.get('reasoning', 'N/A')}", 'CHECKOUT', 'LLM')
        
        if response.get('confidence', 0) < 0.5:
            log(logger, 'info', 'AI: No guest checkout button needed', 'CHECKOUT', 'LLM')
            return {'success': True}
        
        tool_name = response.get('tool')
        params = response.get('params', {})
        result = await execute_tool(page, tool_name, params)
        
        if result.get('success'):
            log(logger, 'info', 'AI: Guest checkout selected', 'CHECKOUT', 'LLM')
            await asyncio.sleep(2)
        
        return {'success': True}  # Always succeed (guest button optional)
        
    except Exception as e:
        log(logger, 'error', f"AI guest checkout error: {e}", 'CHECKOUT', 'LLM')
        return {'success': True}  # Non-critical


async def ai_fill_contact_info(page, contact_data, llm_client):
    """AI-driven contact info filling"""
    log(logger, 'info', 'AI: Analyzing contact form fields...', 'CHECKOUT', 'LLM')
    
    await dismiss_popups(page)
    await asyncio.sleep(0.5)
    
    state = await get_page_state(page)
    
    if len(state['fields']) == 0:
        log(logger, 'warning', 'AI: No form fields found', 'ADDRESS_FILL', 'LLM')
        return {'success': False, 'error': 'No form fields found'}
    
    prompt = f"""You are an expert e-commerce form filling agent. Your task is to map customer contact data to the correct form fields.

=== CUSTOMER CONTACT DATA ===
Email: {contact_data.get('email', 'N/A')}
First Name: {contact_data.get('firstName', 'N/A')}
Last Name: {contact_data.get('lastName', 'N/A')}
Phone: {contact_data.get('phone', 'N/A')}

=== VISIBLE FORM FIELDS ===
{json.dumps(state['fields'], indent=2)}

=== YOUR TASK ===
Analyze each form field and map it to the correct customer data. Create fill actions for ONLY the fields that exist.

=== FIELD MATCHING RULES ===
1. EMAIL: Match fields with name/id/label/autocomplete containing: "email", "e-mail", "mail"
2. FIRST NAME: Match: "firstname", "first-name", "fname", "given-name", "givenname"
3. LAST NAME: Match: "lastname", "last-name", "lname", "surname", "family-name"
4. PHONE: Match: "phone", "telephone", "mobile", "tel"

=== CRITICAL RULES ===
- Use autocomplete attribute as PRIMARY matching signal (most reliable)
- Check field 'type' attribute (email fields have type="email")
- DO NOT confuse "email" with "email address" in shipping forms
- DO NOT map first name to last name field or vice versa
- Only include fields that ACTUALLY EXIST in the form
- Order actions logically: email → firstName → lastName → phone

=== REQUIRED JSON RESPONSE ===
{{
    "reasoning": "Briefly explain each field mapping (which form field maps to which data)",
    "actions": [
        {{
            "tool": "fill_input_field",
            "params": {{
                "label_keywords": ["email", "e-mail", "mail"],
                "value": "{contact_data.get('email', '')}",
                "max_retries": 3
            }},
            "field_type": "email",
            "critical": true
        }},
        {{
            "tool": "fill_input_field",
            "params": {{
                "label_keywords": ["first name", "firstname", "fname", "given name"],
                "value": "{contact_data.get('firstName', '')}",
                "max_retries": 3
            }},
            "field_type": "firstName",
            "critical": true
        }},
        {{
            "tool": "fill_input_field",
            "params": {{
                "label_keywords": ["last name", "lastname", "lname", "surname"],
                "value": "{contact_data.get('lastName', '')}",
                "max_retries": 3
            }},
            "field_type": "lastName",
            "critical": true
        }},
        {{
            "tool": "fill_input_field",
            "params": {{
                "label_keywords": ["phone", "telephone", "mobile"],
                "value": "{contact_data.get('phone', '')}",
                "max_retries": 3
            }},
            "field_type": "phone",
            "critical": false
        }}
    ],
    "continue_button_needed": true
}}

=== CONTINUE BUTTON ===
Set continue_button_needed to true if you see a "Continue" or "Next" button is likely needed after filling.

RESPOND ONLY WITH VALID JSON. INCLUDE ONLY FIELDS THAT EXIST IN THE FORM."""

    try:
        response = await llm_client.complete(prompt, max_tokens=800)
        log(logger, 'info', f"AI reasoning: {response.get('reasoning', 'N/A')[:100]}...", 'ADDRESS_FILL', 'LLM')
        
        actions = response.get('actions', [])
        if len(actions) == 0:
            log(logger, 'error', 'AI: No field mappings generated', 'ADDRESS_FILL', 'LLM')
            return {'success': False, 'error': 'No field mappings'}
        
        filled_count = 0
        for i, action in enumerate(actions):
            log(logger, 'info', f"AI: Filling field {i+1}/{len(actions)}: {action.get('field_type')}", 'ADDRESS_FILL', 'LLM')
            
            result = await execute_tool(page, action['tool'], action['params'])
            
            if result.get('success'):
                filled_count += 1
                await asyncio.sleep(0.5)
            else:
                log(logger, 'error', f"AI: Failed to fill {action.get('field_type')}: {result.get('error')}", 'ADDRESS_FILL', 'LLM')
                # STRICT: Return failure if critical field fails
                if action.get('field_type') in ['email', 'firstName', 'lastName']:
                    return {'success': False, 'error': f"Critical field failed: {action.get('field_type')}"}
        
        # Click continue if needed
        if response.get('continue_button_needed'):
            log(logger, 'info', 'AI: Clicking continue button...', 'ADDRESS_FILL', 'LLM')
            continue_result = await execute_tool(page, 'find_and_click_button', {
                'keywords': ['continue', 'next', 'proceed'],
                'max_retries': 2
            })
            if continue_result.get('success'):
                await asyncio.sleep(2)
        
        log(logger, 'info', f"AI: Contact info filled ({filled_count}/{len(actions)} fields)", 'ADDRESS_FILL', 'LLM')
        return {'success': filled_count >= 2}
        
    except Exception as e:
        log(logger, 'error', f"AI contact fill error: {e}", 'ADDRESS_FILL', 'LLM')
        return {'success': False, 'error': str(e)}


async def ai_fill_shipping_address(page, address_data, llm_client):
    """AI-driven shipping address filling"""
    log(logger, 'info', 'AI: Analyzing shipping address form...', 'CHECKOUT', 'LLM')
    
    await dismiss_popups(page)
    await asyncio.sleep(0.5)
    
    state = await get_page_state(page)
    
    if len(state['fields']) == 0:
        log(logger, 'warning', 'AI: No form fields found', 'ADDRESS_FILL', 'LLM')
        return {'success': False, 'error': 'No form fields found'}
    
    prompt = f"""You are an expert e-commerce form filling agent. Your task is to map shipping address data to form fields.

=== SHIPPING ADDRESS DATA ===
Address Line 1: {address_data.get('addressLine1', 'N/A')}
City: {address_data.get('city', 'N/A')}
State/Province: {address_data.get('province', 'N/A')}
Postal/Zip Code: {address_data.get('postalCode', 'N/A')}
Country: {address_data.get('country', 'N/A')}

=== VISIBLE FORM FIELDS ===
{json.dumps(state['fields'], indent=2)}

=== YOUR TASK ===
Analyze each form field and map it to the correct address data. Create fill actions for ONLY the fields that exist.

=== FIELD MATCHING RULES ===
1. ADDRESS: Match fields with: "address", "street", "address1", "addressline1", "addr", "street-address"
   - Autocomplete: "address-line1", "street-address"
2. CITY: Match: "city", "town", "locality"
   - Autocomplete: "address-level2"
3. STATE/PROVINCE: Match: "state", "province", "region", "county"
   - Autocomplete: "address-level1"
   - Usually a SELECT dropdown
4. POSTAL CODE: Match: "postal", "postcode", "zip", "zipcode"
   - Autocomplete: "postal-code"
5. COUNTRY: Match: "country"
   - Autocomplete: "country"
   - Usually a SELECT dropdown

=== CRITICAL RULES ===
- Use autocomplete attribute as PRIMARY signal (most reliable)
- Check field 'type' attribute
- For STATE/PROVINCE: Use "find_and_select_dropdown" tool if field type is "select"
- For COUNTRY: Use "find_and_select_dropdown" tool if field type is "select"
- DO NOT confuse city with state or postal code
- Fill address FIRST (may trigger autocomplete for city/state/zip)
- Order: address → postalCode → city → state → country

=== REQUIRED JSON RESPONSE ===
{{
    "reasoning": "Explain each field mapping (which form field maps to which address data)",
    "actions": [
        {{
            "tool": "fill_input_field",
            "params": {{
                "label_keywords": ["address", "street", "address line 1", "address1"],
                "value": "{address_data.get('addressLine1', '')}",
                "max_retries": 3
            }},
            "field_type": "address",
            "critical": true
        }},
        {{
            "tool": "fill_input_field",
            "params": {{
                "label_keywords": ["postal code", "zip code", "zip", "postcode"],
                "value": "{address_data.get('postalCode', '')}",
                "max_retries": 3
            }},
            "field_type": "postalCode",
            "critical": true
        }},
        {{
            "tool": "fill_input_field",
            "params": {{
                "label_keywords": ["city", "town", "locality"],
                "value": "{address_data.get('city', '')}",
                "max_retries": 3
            }},
            "field_type": "city",
            "critical": true
        }},
        {{
            "tool": "find_and_select_dropdown",
            "params": {{
                "label_keywords": ["state", "province", "region"],
                "option_value": "{address_data.get('province', '')}",
                "max_retries": 2
            }},
            "field_type": "state",
            "critical": false
        }}
    ]
}}

=== NOTES ===
- Mark field as critical: true if it's required (address, city, postalCode)
- Mark field as critical: false if it's optional (state, country, address2)
- Use correct tool: "fill_input_field" for text inputs, "find_and_select_dropdown" for select elements

RESPOND ONLY WITH VALID JSON. INCLUDE ONLY FIELDS THAT EXIST IN THE FORM."""

    try:
        response = await llm_client.complete(prompt, max_tokens=1000)
        log(logger, 'info', f"AI reasoning: {response.get('reasoning', 'N/A')[:100]}...", 'ADDRESS_FILL', 'LLM')
        
        actions = response.get('actions', [])
        if len(actions) == 0:
            return {'success': False, 'error': 'No field mappings'}
        
        filled_count = 0
        for i, action in enumerate(actions):
            log(logger, 'info', f"AI: Filling field {i+1}/{len(actions)}: {action.get('field_type')}", 'ADDRESS_FILL', 'LLM')
            
            result = await execute_tool(page, action['tool'], action['params'])
            
            if result.get('success'):
                filled_count += 1
                await asyncio.sleep(0.5)
            else:
                log(logger, 'error', f"AI: Failed to fill {action.get('field_type')}: {result.get('error')}", 'ADDRESS_FILL', 'LLM')
                # STRICT: Fail if critical address fields fail
                if action.get('field_type') in ['address', 'postalCode', 'city']:
                    return {'success': False, 'error': f"Critical field failed: {action.get('field_type')}"}
        
        log(logger, 'info', f"AI: Shipping address filled ({filled_count}/{len(actions)} fields)", 'ADDRESS_FILL', 'LLM')
        return {'success': filled_count >= 3}
        
    except Exception as e:
        log(logger, 'error', f"AI shipping fill error: {e}", 'ADDRESS_FILL', 'LLM')
        return {'success': False, 'error': str(e)}


async def _check_for_password_field(page):
    """Check if password field exists on page"""
    try:
        has_password = await page.evaluate("""
            () => {
                const fields = Array.from(document.querySelectorAll('input[type="password"]'));
                return fields.some(f => f.offsetParent && f.getBoundingClientRect().width > 0);
            }
        """)
        return has_password
    except:
        return False


async def _prompt_user_for_password():
    """Prompt user for password input"""
    log(logger, 'warning', '=' * 60, 'CHECKOUT', 'CORE')
    log(logger, 'warning', 'PASSWORD FIELD DETECTED', 'CHECKOUT', 'CORE')
    log(logger, 'warning', '=' * 60, 'CHECKOUT', 'CORE')
    print("\n" + "="*60)
    print("⚠️  PASSWORD REQUIRED")
    print("="*60)
    print("A password field was detected on the checkout page.")
    print("This usually means you need to create an account or login.")
    print("\nOptions:")
    print("1. Enter password to continue")
    print("2. Skip (try guest checkout)")
    print("="*60)
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == '1':
        password = input("Enter password: ").strip()
        if password:
            log(logger, 'info', 'User provided password', 'CHECKOUT', 'CORE')
            return password
    
    log(logger, 'info', 'User skipped password entry', 'CHECKOUT', 'CORE')
    return None


async def run_ai_checkout_flow(page, customer_data, user_prompt_callback=None):
    """
    Main AI-driven checkout flow
    Uses LLM to analyze and execute each stage
    user_prompt_callback: Optional callback for user prompts (e.g., password)
    """
    log(logger, 'info', '=' * 60, 'CHECKOUT', 'CORE')
    log(logger, 'info', 'Starting AI-Driven Checkout Flow', 'CHECKOUT', 'CORE')
    log(logger, 'info', '=' * 60, 'CHECKOUT', 'CORE')
    
    llm_client = LLMClient()
    
    try:
        # Stage 1: Proceed to checkout
        log(logger, 'info', 'STAGE 1: Proceed to Checkout', 'CHECKOUT', 'CORE')
        result = await ai_proceed_to_checkout(page, llm_client)
        if not result.get('success'):
            return {'success': False, 'error': 'Failed to proceed to checkout', 'stage': 'checkout_button'}
        
        # Check for password field after navigation
        if await _check_for_password_field(page):
            password = await _prompt_user_for_password()
            if password:
                # Try to fill password field
                from phase2.checkout_dom_finder import fill_input_field
                pwd_result = await fill_input_field(page, ['password', 'pwd', 'pass'], password, max_retries=2)
                if pwd_result.get('success'):
                    log(logger, 'info', 'Password field filled', 'CHECKOUT', 'CORE')
                    await asyncio.sleep(1)
        
        # Stage 2: Guest checkout
        log(logger, 'info', 'STAGE 2: Guest Checkout', 'CHECKOUT', 'CORE')
        await ai_handle_guest_checkout(page, llm_client)
        await asyncio.sleep(2)
        
        # Check for password field again after guest checkout
        if await _check_for_password_field(page):
            password = await _prompt_user_for_password()
            if password:
                from phase2.checkout_dom_finder import fill_input_field
                pwd_result = await fill_input_field(page, ['password', 'pwd', 'pass'], password, max_retries=2)
                if pwd_result.get('success'):
                    log(logger, 'info', 'Password field filled', 'CHECKOUT', 'CORE')
                    await asyncio.sleep(1)
        
        # Stage 3: Contact info
        log(logger, 'info', 'STAGE 3: Contact Information', 'CHECKOUT', 'CORE')
        contact_data = customer_data.get('contact', {})
        
        # Check for password field before filling contact info
        if await _check_for_password_field(page):
            password = await _prompt_user_for_password()
            if password:
                from phase2.checkout_dom_finder import fill_input_field
                pwd_result = await fill_input_field(page, ['password', 'pwd', 'pass'], password, max_retries=2)
                if pwd_result.get('success'):
                    log(logger, 'info', 'Password field filled', 'CHECKOUT', 'CORE')
                    await asyncio.sleep(1)
        
        result = await ai_fill_contact_info(page, contact_data, llm_client)
        if not result.get('success'):
            return {'success': False, 'error': 'Failed to fill contact info', 'stage': 'contact_info'}
        
        await asyncio.sleep(2)
        
        # Stage 4: Shipping address
        log(logger, 'info', 'STAGE 4: Shipping Address', 'CHECKOUT', 'CORE')
        address_data = customer_data.get('shippingAddress', {})
        result = await ai_fill_shipping_address(page, address_data, llm_client)
        if not result.get('success'):
            return {'success': False, 'error': 'Failed to fill shipping address', 'stage': 'shipping_address'}
        
        # Stage 5: Continue to payment
        log(logger, 'info', 'STAGE 5: Continue to Payment', 'CHECKOUT', 'CORE')
        continue_result = await execute_tool(page, 'find_and_click_button', {
            'keywords': ['continue', 'next', 'proceed to payment'],
            'max_retries': 2
        })
        if continue_result.get('success'):
            await asyncio.sleep(2)
        
        log(logger, 'info', '=' * 60, 'CHECKOUT', 'CORE')
        log(logger, 'info', 'AI Checkout Flow Completed Successfully', 'CHECKOUT', 'CORE')
        log(logger, 'info', '=' * 60, 'CHECKOUT', 'CORE')
        
        return {'success': True, 'message': 'AI checkout flow completed'}
        
    except Exception as e:
        log(logger, 'error', f"AI checkout flow error: {e}", 'CHECKOUT', 'CORE')
        return {'success': False, 'error': str(e)}
