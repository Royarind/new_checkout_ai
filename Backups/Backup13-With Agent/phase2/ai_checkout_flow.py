"""
AI-Driven Checkout Flow
Uses LLM to analyze page and execute checkout stages with DOM tools
"""

import asyncio
import json
from datetime import datetime
from shared.logger_config import setup_logger, log
from shared.popup_dismisser import dismiss_popups
from core.utils.openai_client import get_client

class LLMClient:
    def __init__(self, config=None):
        self.client = get_client()
        
    async def complete(self, prompt, max_tokens=500):
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"LLM Error: {e}")
            return {}

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
    
    # Simplify cart elements
    simple_elements = [{"text": e.get('text','')[:40], "class": e.get('className','')[:40], "aria": e.get('ariaLabel','')[:40]} for e in cart_elements[:20]]
    
    prompt = f"""Find cart icon in header.

ELEMENTS:
{json.dumps(simple_elements)}

Find: "cart", "bag", "basket" in text/class/aria.

RESPONSE:
{{"reasoning": "...", "keywords": ["cart"], "confidence": 0.9}}

JSON ONLY."""
    
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
    
    # Check for site-specific handler
    from special_sites import get_site_specific_checkout_handler
    handler = await get_site_specific_checkout_handler(page)
    if handler:
        log(logger, 'info', 'Using site-specific checkout handler', 'CHECKOUT', 'SITE_SPECIFIC')
        return await handler(page)
    
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
    
    # Filter and simplify buttons for LLM
    simplified_buttons = []
    for btn in state['buttons'][:15]:
        simplified_buttons.append({
            'text': btn.get('text', '')[:80],
            'aria': btn.get('ariaLabel', '')[:50],
            'class': btn.get('className', '')[:50]
        })
    
    # Build compact prompt
    prompt = f"""Find checkout button on cart page.

BUTTONS:
{json.dumps(simplified_buttons)}

TASK: Find button with "checkout", "proceed to checkout", or "secure checkout" in text/aria/class.
AVOID: "add to cart", "continue shopping", "update cart"

RESPONSE:
{{
    "reasoning": "Found '[TEXT]' - it's checkout button",
    "tool": "find_and_click_button",
    "params": {{"keywords": ["proceed to checkout", "checkout"], "max_retries": 3}},
    "confidence": 0.95
}}

Confidence: 0.9+ if checkout found, <0.5 if not found.
JSON ONLY."""

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
            await asyncio.sleep(5)  # Wait for page navigation
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
    """AI-driven guest checkout selection - ALWAYS PRIORITIZE GUEST"""
    log(logger, 'info', 'AI: PRIORITY - Looking for guest checkout...', 'CHECKOUT', 'LLM')
    
    await dismiss_popups(page)
    await asyncio.sleep(1)
    
    # First, try direct guest checkout button click (no AI needed)
    log(logger, 'info', 'Trying direct guest checkout detection...', 'CHECKOUT', 'CORE')
    direct_result = await execute_tool(page, 'find_and_click_button', {
        'keywords': ['continue as guest', 'guest checkout', 'checkout as guest', 'continue without account'],
        'max_retries': 2
    })
    
    if direct_result.get('success'):
        log(logger, 'info', '✓ Guest checkout clicked (direct)', 'CHECKOUT', 'CORE')
        return {'success': True}
    
    # Fallback to AI if direct method fails
    log(logger, 'info', 'Direct method failed, using AI...', 'CHECKOUT', 'LLM')
    state = await get_page_state(page)
    simple_btns = [{"text": b.get('text','')[:60]} for b in state['buttons'][:15]]
    
    prompt = f"""Find guest checkout button (HIGH PRIORITY).

BUTTONS:
{json.dumps(simple_btns)}

Find: "guest", "continue as guest", "checkout as guest", "continue without account"

RESPONSE:
{{"reasoning": "...", "tool": "find_and_click_button", "params": {{"keywords": ["guest"], "max_retries": 3}}, "confidence": 0.8}}

Confidence: 0.8+ if found, <0.5 if not needed.
JSON ONLY."""

    try:
        response = await llm_client.complete(prompt, max_tokens=400)
        log(logger, 'info', f"AI reasoning: {response.get('reasoning', 'N/A')}", 'CHECKOUT', 'LLM')
        
        if response.get('confidence', 0) < 0.5:
            log(logger, 'info', 'AI: No guest checkout button found (proceeding)', 'CHECKOUT', 'LLM')
            return {'success': True}
        
        tool_name = response.get('tool')
        params = response.get('params', {})
        result = await execute_tool(page, tool_name, params)
        
        if result.get('success'):
            log(logger, 'info', '✓ Guest checkout selected (AI)', 'CHECKOUT', 'LLM')
        
        return {'success': True}  # Always succeed (guest button optional)
        
    except Exception as e:
        log(logger, 'error', f"AI guest checkout error: {e}", 'CHECKOUT', 'LLM')
        return {'success': True}  # Non-critical


async def ai_fill_contact_info(page, contact_data, llm_client):
    """AI-driven contact info filling"""
    log(logger, 'info', 'AI: Analyzing contact form fields...', 'CHECKOUT', 'LLM')
    
    await dismiss_popups(page)
    await asyncio.sleep(2)  # Wait for page to stabilize
    
    state = await get_page_state(page)
    
    if len(state['fields']) == 0:
        log(logger, 'warning', 'AI: No form fields found', 'ADDRESS_FILL', 'LLM')
        return {'success': False, 'error': 'No form fields found'}
    
    # Simplify fields
    simple_fields = [{"type": f.get('type',''), "name": f.get('name','')[:30], "label": f.get('label','')[:40], "autocomplete": f.get('autocomplete','')} for f in state['fields'][:10]]
    
    # Build actions based on available data
    actions = []
    if contact_data.get('email'):
        actions.append({
            "tool": "fill_input_field",
            "params": {"label_keywords": ["email", "e-mail", "email address"], "value": contact_data['email'], "max_retries": 3},
            "field_type": "email",
            "critical": True
        })
    if contact_data.get('firstName'):
        actions.append({
            "tool": "fill_input_field",
            "params": {"label_keywords": ["first name", "firstname", "fname", "given name"], "value": contact_data['firstName'], "max_retries": 3},
            "field_type": "firstName",
            "critical": True
        })
    if contact_data.get('lastName'):
        actions.append({
            "tool": "fill_input_field",
            "params": {"label_keywords": ["last name", "lastname", "lname", "surname", "family name"], "value": contact_data['lastName'], "max_retries": 3},
            "field_type": "lastName",
            "critical": True
        })
    if contact_data.get('phone'):
        actions.append({
            "tool": "fill_input_field",
            "params": {"label_keywords": ["phone", "telephone", "mobile", "tel"], "value": contact_data['phone'], "max_retries": 3},
            "field_type": "phone",
            "critical": False
        })
    
    prompt = f"""Analyze form fields and determine which contact fields to fill.

AVAILABLE DATA:
- email: {contact_data.get('email', 'N/A')}
- firstName: {contact_data.get('firstName', 'N/A')}
- lastName: {contact_data.get('lastName', 'N/A')}
- phone: {contact_data.get('phone', 'N/A')}

FORM FIELDS:
{json.dumps(simple_fields, indent=2)}

TASK: Determine which fields exist on the form and should be filled.
Look for:
- email: type="email" OR name/label contains "email"
- firstName: name/label contains "first", "fname", "given"
- lastName: name/label contains "last", "lname", "surname", "family"
- phone: type="tel" OR name/label contains "phone", "tel", "mobile"

RESPONSE FORMAT (JSON ONLY):
{{
    "reasoning": "Found email field (type=email), firstName field (name=firstname), lastName field (name=lastname)",
    "actions": [
        {{"tool": "fill_input_field", "params": {{"label_keywords": ["email"], "value": "{contact_data.get('email','')}", "max_retries": 3}}, "field_type": "email", "critical": true}},
        {{"tool": "fill_input_field", "params": {{"label_keywords": ["first name", "firstname"], "value": "{contact_data.get('firstName','')}", "max_retries": 3}}, "field_type": "firstName", "critical": true}},
        {{"tool": "fill_input_field", "params": {{"label_keywords": ["last name", "lastname"], "value": "{contact_data.get('lastName','')}", "max_retries": 3}}, "field_type": "lastName", "critical": true}}
    ],
    "continue_button_needed": true
}}

IMPORTANT: Return valid JSON with at least the email field action."""

    try:
        response = await llm_client.complete(prompt, max_tokens=1500)
        log(logger, 'info', f"AI reasoning: {response.get('reasoning', 'N/A')[:100]}...", 'ADDRESS_FILL', 'LLM')
        
        # Use LLM actions if available, otherwise use pre-built actions
        llm_actions = response.get('actions', [])
        if len(llm_actions) == 0:
            log(logger, 'warning', 'AI: No field mappings from LLM, using fallback actions', 'ADDRESS_FILL', 'LLM')
            # Use pre-built actions as fallback - but ONLY fill email first
            if len(actions) == 0:
                log(logger, 'error', 'AI: No contact data available to fill', 'ADDRESS_FILL', 'LLM')
                return {'success': False, 'error': 'No contact data available'}
            # Only use email action initially
            actions = [a for a in actions if a.get('field_type') == 'email']
        else:
            actions = llm_actions
        
        filled_count = 0
        filled_fields = {}  # Track what we filled
        
        for i, action in enumerate(actions):
            field_type = action.get('field_type')
            log(logger, 'info', f"AI: Filling field {i+1}/{len(actions)}: {field_type}", 'ADDRESS_FILL', 'LLM')
            
            result = await execute_tool(page, action['tool'], action['params'])
            
            if result.get('success'):
                filled_count += 1
                filled_fields[field_type] = action['params']['value']
                await asyncio.sleep(0.5)
            else:
                log(logger, 'error', f"AI: Failed to fill {field_type}: {result.get('error')}", 'ADDRESS_FILL', 'LLM')
                # STRICT: Return failure if critical field fails
                if field_type == 'email':
                    return {'success': False, 'error': f"Critical field failed: {field_type}"}
        
        # Check for duplicate fields (e.g., "Confirm Email")
        await asyncio.sleep(1)
        duplicate_result = await _fill_duplicate_fields(page, filled_fields)
        if duplicate_result.get('filled_count', 0) > 0:
            filled_count += duplicate_result['filled_count']
            log(logger, 'info', f"Filled {duplicate_result['filled_count']} duplicate/confirmation fields", 'ADDRESS_FILL', 'LLM')
        
        log(logger, 'info', f"AI: Contact info filled ({filled_count}/{len(actions)} fields)", 'ADDRESS_FILL', 'LLM')
        
        # Try to click continue - if it fails, use AI to determine next action
        continue_button_needed = response.get('continue_button_needed', True)
        if continue_button_needed or filled_count >= 1:
            log(logger, 'info', 'AI: Clicking continue button...', 'ADDRESS_FILL', 'LLM')
            continue_result = await execute_tool(page, 'find_and_click_button', {
                'keywords': ['continue', 'next', 'proceed'],
                'max_retries': 2
            })
            
            if not continue_result.get('success'):
                # AI fallback: analyze page and determine next action
                log(logger, 'warning', 'Continue button not found, using AI to determine next step...', 'ADDRESS_FILL', 'LLM')
                next_action = await _ai_determine_next_action(page, llm_client, 'contact_info')
                if next_action.get('success'):
                    log(logger, 'info', f"AI determined action: {next_action.get('action')}", 'ADDRESS_FILL', 'LLM')
                    await asyncio.sleep(2)
                else:
                    log(logger, 'warning', 'AI could not determine next action, proceeding anyway', 'ADDRESS_FILL', 'LLM')
            
            if continue_result.get('success'):
                log(logger, 'info', 'Continue clicked, waiting for new page...', 'ADDRESS_FILL', 'LLM')
                await asyncio.sleep(3)
                try:
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except:
                    pass
                
                # Re-detect fields on new page
                new_state = await get_page_state(page)
                log(logger, 'info', f"After continue: Found {len(new_state['fields'])} fields", 'ADDRESS_FILL', 'LLM')
                
                if len(new_state['fields']) > 0:
                    # Try to fill remaining contact fields (firstName, lastName, phone)
                    remaining_fields = []
                    if contact_data.get('firstName'):
                        remaining_fields.append({'tool': 'fill_input_field', 'params': {'label_keywords': ['first name', 'firstname', 'fname', 'given name'], 'value': contact_data['firstName'], 'max_retries': 3}, 'field_type': 'firstName'})
                    if contact_data.get('lastName'):
                        remaining_fields.append({'tool': 'fill_input_field', 'params': {'label_keywords': ['last name', 'lastname', 'lname', 'surname', 'family name'], 'value': contact_data['lastName'], 'max_retries': 3}, 'field_type': 'lastName'})
                    if contact_data.get('phone'):
                        remaining_fields.append({'tool': 'fill_input_field', 'params': {'label_keywords': ['phone', 'telephone', 'mobile', 'tel'], 'value': contact_data['phone'], 'max_retries': 3}, 'field_type': 'phone'})
                    
                    for field in remaining_fields:
                        log(logger, 'info', f"Attempting to fill {field['field_type']}...", 'ADDRESS_FILL', 'LLM')
                        result = await execute_tool(page, field['tool'], field['params'])
                        if result.get('success'):
                            filled_count += 1
                            log(logger, 'info', f"✓ Filled {field['field_type']}", 'ADDRESS_FILL', 'LLM')
                            await asyncio.sleep(0.5)
                        else:
                            log(logger, 'warning', f"✗ Could not fill {field['field_type']}: {result.get('error')}", 'ADDRESS_FILL', 'LLM')
        
        return {'success': filled_count >= 1}
        
    except Exception as e:
        log(logger, 'error', f"AI contact fill error: {e}", 'ADDRESS_FILL', 'LLM')
        return {'success': False, 'error': str(e)}


async def ai_fill_shipping_address(page, address_data, llm_client):
    """AI-driven shipping address filling"""
    log(logger, 'info', 'AI: Analyzing shipping address form...', 'CHECKOUT', 'LLM')
    
    await dismiss_popups(page)
    await asyncio.sleep(2)  # Wait for page to stabilize
    
    state = await get_page_state(page)
    
    if len(state['fields']) == 0:
        log(logger, 'warning', 'AI: No form fields found', 'ADDRESS_FILL', 'LLM')
        return {'success': False, 'error': 'No form fields found'}
    
    # Simplify fields
    simple_fields = [{"type": f.get('type',''), "name": f.get('name','')[:30], "label": f.get('label','')[:40], "autocomplete": f.get('autocomplete','')} for f in state['fields'][:12]]
    
    prompt = f"""Map address to form fields.

DATA: address={address_data.get('addressLine1')}, city={address_data.get('city')}, state={address_data.get('province')}, zip={address_data.get('postalCode')}, country={address_data.get('country', 'United States')}

FIELDS:
{json.dumps(simple_fields)}

RULES:
- country: "country", type="select" → use find_and_select_dropdown (FILL FIRST if exists)
- address: "address", "street", autocomplete="address-line1" → use fill_input_field
- city: "city", autocomplete="address-level2" → use fill_input_field
- state: "state", "province", type="select" → MUST use find_and_select_dropdown with state value
- zip: "postal", "zip", "zipcode", "postcode", autocomplete="postal-code" → use fill_input_field with keywords ["zipcode", "zip code", "postal code", "postcode", "zip", "postal"]
- MANDATORY: address, city, state, zip must be filled and VALIDATED against {address_data} before continuing.
- Suggested Address should be preferred if available. If suggested address dropdown exists, select the alredy suggested address matching the input address.
- Save and Continue button may need to be clicked after filling address or selecting suggested address in the same modal where the address suggestion is selected if present.
- Mandatory: Always find a way to proceed after filling address. You can click Continue/Next/Save button if available or dismiss any modal if present.

Order: country→address→zip→city→state (country FIRST, state LAST)



RESPONSE:
{{"reasoning": "...", "actions": [
  {{"tool": "find_and_select_dropdown", "params": {{"label_keywords": ["country"], "option_value": "{address_data.get('country', 'United States')}", "max_retries": 2}}, "field_type": "country", "critical": false}},
  {{"tool": "fill_input_field", "params": {{"label_keywords": ["address", "street"], "value": "{address_data.get('addressLine1','')}", "max_retries": 3}}, "field_type": "address", "critical": true}},
  {{"tool": "fill_input_field", "params": {{"label_keywords": ["zipcode", "zip-code", "zip code", "postal code", "postcode", "zip", "postal"], "value": "{address_data.get('postalCode','')}", "max_retries": 3}}, "field_type": "postalCode", "critical": true}},
  {{"tool": "fill_input_field", "params": {{"label_keywords": ["city"], "value": "{address_data.get('city','')}", "max_retries": 3}}, "field_type": "city", "critical": true}},
  {{"tool": "find_and_select_dropdown", "params": {{"label_keywords": ["state", "province"], "option_value": "{address_data.get('province','')}", "max_retries": 2}}, "field_type": "state", "critical": true}}
]}}

JSON ONLY."""

    try:
        response = await llm_client.complete(prompt, max_tokens=1500)
        log(logger, 'info', f"AI reasoning: {response.get('reasoning', 'N/A')[:100]}...", 'ADDRESS_FILL', 'LLM')
        
        actions = response.get('actions', [])
        if len(actions) == 0:
            log(logger, 'warning', 'AI: No field mappings from LLM, using fallback', 'ADDRESS_FILL', 'LLM')
            # Fallback: build actions from address data
            actions = []
            
            # Determine country from state if not provided
            country = address_data.get('country', '')
            state = address_data.get('province', '')
            
            if not country and state:
                us_states = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']
                if state.upper() in us_states:
                    country = 'United States'
                    log(logger, 'info', f'Detected US state {state}, setting country=United States', 'ADDRESS_FILL', 'LLM')
                else:
                    log(logger, 'error', f'Country required for state: {state}', 'ADDRESS_FILL', 'LLM')
                    print(f"\n⚠️  Country required for state: {state}")
                    country = input("Enter country (United States/India/Canada/United Kingdom): ").strip() or 'United States'
            elif not country:
                country = 'United States'
            
            # Country MUST be first and critical
            country_codes = {'United States': 'US', 'India': 'IN', 'Canada': 'CA', 'United Kingdom': 'GB'}
            country_value = country_codes.get(country, country)
            actions.append({'tool': 'find_and_select_dropdown', 'params': {'label_keywords': ['country'], 'option_value': country_value, 'max_retries': 2}, 'field_type': 'country', 'critical': True})
            
            if address_data.get('addressLine1'):
                actions.append({'tool': 'fill_input_field', 'params': {'label_keywords': ['address', 'street', 'address line 1'], 'value': address_data['addressLine1'], 'max_retries': 3}, 'field_type': 'address', 'critical': True})
            if address_data.get('postalCode'):
                actions.append({'tool': 'fill_input_field', 'params': {'label_keywords': ['zipcode', 'zip code', 'postal code', 'postcode', 'zip', 'postal'], 'value': address_data['postalCode'], 'max_retries': 3}, 'field_type': 'postalCode', 'critical': True})
            if address_data.get('city'):
                actions.append({'tool': 'fill_input_field', 'params': {'label_keywords': ['city'], 'value': address_data['city'], 'max_retries': 3}, 'field_type': 'city', 'critical': True})
            if address_data.get('province'):
                actions.append({'tool': 'find_and_select_dropdown', 'params': {'label_keywords': ['state', 'province'], 'option_value': address_data['province'], 'max_retries': 2}, 'field_type': 'state', 'critical': True})
            
            if len(actions) == 0:
                return {'success': False, 'error': 'No address data available'}
        
        filled_count = 0
        filled_fields = {}  # Track filled fields
        
        for i, action in enumerate(actions):
            field_type = action.get('field_type')
            log(logger, 'info', f"AI: Filling field {i+1}/{len(actions)}: {field_type}", 'ADDRESS_FILL', 'LLM')
            
            result = await execute_tool(page, action['tool'], action['params'])
            
            if result.get('success'):
                filled_count += 1
                value = action['params'].get('value') or action['params'].get('option_value')
                if value:
                    filled_fields[field_type] = value
                await asyncio.sleep(0.5)
            else:
                log(logger, 'error', f"AI: Failed to fill {field_type}: {result.get('error')}", 'ADDRESS_FILL', 'LLM')
                
                if action.get('field_type') == 'postalCode':
                    log(logger, 'warning', 'Checking if postal code was auto-filled...', 'ADDRESS_FILL', 'LLM')
                    await asyncio.sleep(1.5)
                    auto_filled = await page.evaluate('''(expectedZip) => {
                        const fields = Array.from(document.querySelectorAll('input'));
                        for (const f of fields) {
                            if (!f.offsetParent) continue;
                            const name = (f.name || f.id || '').toLowerCase();
                            const value = f.value || '';
                            if ((name.includes('zip') || name.includes('postal') || name.includes('postcode')) && value.trim() === expectedZip) {
                                return true;
                            }
                        }
                        return false;
                    }''', action['params']['value'])
                    if auto_filled:
                        filled_count += 1
                        log(logger, 'info', 'Postal code was auto-filled', 'ADDRESS_FILL', 'LLM')
                        continue
                    log(logger, 'warning', 'Trying comprehensive postal code keyword variations...', 'ADDRESS_FILL', 'LLM')
                    keyword_sets = [
                        ['zipcode', 'zip-code', 'zip_code'],
                        ['zip code', 'zip'],
                        ['postal code', 'postalcode', 'postal-code'],
                        ['postcode', 'post-code'],
                        ['postal', 'post']
                    ]
                    postal_filled = False
                    for keywords in keyword_sets:
                        alt_result = await execute_tool(page, 'fill_input_field', {
                            'label_keywords': keywords,
                            'value': action['params']['value'],
                            'max_retries': 1
                        })
                        if alt_result.get('success'):
                            filled_count += 1
                            postal_filled = True
                            log(logger, 'info', f'Postal code filled with: {keywords}', 'ADDRESS_FILL', 'LLM')
                            break
                        await asyncio.sleep(0.5)
                    if not postal_filled:
                        return {'success': False, 'error': 'Critical field failed: postalCode'}
                elif action.get('field_type') == 'city':
                    log(logger, 'warning', 'Checking if city was auto-filled...', 'ADDRESS_FILL', 'LLM')
                    await asyncio.sleep(1.0)
                    auto_filled = await page.evaluate('''(expectedCity) => {
                        const fields = Array.from(document.querySelectorAll('input'));
                        for (const f of fields) {
                            if (!f.offsetParent) continue;
                            const name = (f.name || f.id || '').toLowerCase();
                            const value = f.value || '';
                            if (name.includes('city') && value.trim().toLowerCase() === expectedCity.toLowerCase()) {
                                return true;
                            }
                        }
                        return false;
                    }''', action['params']['value'])
                    if auto_filled:
                        filled_count += 1
                        log(logger, 'info', 'City was auto-filled', 'ADDRESS_FILL', 'LLM')
                    else:
                        return {'success': False, 'error': 'Critical field failed: city'}
                elif action.get('field_type') == 'state':
                    log(logger, 'warning', 'Checking if state was auto-filled...', 'ADDRESS_FILL', 'LLM')
                    await asyncio.sleep(1.0)
                    auto_filled = await page.evaluate('''(expectedState) => {
                        const fields = Array.from(document.querySelectorAll('input, select'));
                        for (const f of fields) {
                            if (!f.offsetParent) continue;
                            const name = (f.name || f.id || '').toLowerCase();
                            const value = f.value || '';
                            if ((name.includes('state') || name.includes('province') || name.includes('region')) && (value.trim().toUpperCase() === expectedState.toUpperCase() || value.trim().toLowerCase() === expectedState.toLowerCase())) {
                                return true;
                            }
                        }
                        return false;
                    }''', action['params'].get('option_value', action['params'].get('value', '')))
                    if auto_filled:
                        filled_count += 1
                        log(logger, 'info', 'State was auto-filled', 'ADDRESS_FILL', 'LLM')
                    else:
                        log(logger, 'warning', 'State not auto-filled, may be optional', 'ADDRESS_FILL', 'LLM')
                elif action.get('field_type') == 'country':
                    log(logger, 'warning', 'Checking if country was auto-filled...', 'ADDRESS_FILL', 'LLM')
                    await asyncio.sleep(1.0)
                    auto_filled = await page.evaluate('''(expectedCountry) => {
                        const fields = Array.from(document.querySelectorAll('select'));
                        for (const f of fields) {
                            if (!f.offsetParent) continue;
                            const name = (f.name || f.id || '').toLowerCase();
                            const value = f.value || '';
                            const text = f.options[f.selectedIndex]?.text || '';
                            if (name.includes('country') && (value.toUpperCase() === 'US' || text.includes('United States'))) {
                                return true;
                            }
                        }
                        return false;
                    }''', action['params'].get('option_value', 'United States'))
                    if auto_filled:
                        filled_count += 1
                        log(logger, 'info', 'Country was auto-filled', 'ADDRESS_FILL', 'LLM')
                    else:
                        log(logger, 'warning', 'Country not auto-filled, may be optional', 'ADDRESS_FILL', 'LLM')
                elif action.get('field_type') == 'address':
                    return {'success': False, 'error': 'Critical field failed: address'}
        
        # Check for duplicate address fields
        await asyncio.sleep(1)
        duplicate_result = await _fill_duplicate_fields(page, filled_fields)
        if duplicate_result.get('filled_count', 0) > 0:
            filled_count += duplicate_result['filled_count']
            log(logger, 'info', f"Filled {duplicate_result['filled_count']} duplicate address fields", 'ADDRESS_FILL', 'LLM')
        
        log(logger, 'info', f"AI: Shipping address filled ({filled_count}/{len(actions)} fields)", 'ADDRESS_FILL', 'LLM')
        required_fields = ['address', 'city', 'postalCode']
        filled_required = sum(1 for action in actions if action.get('field_type') in required_fields and any(action.get('field_type') == a.get('field_type') for a in actions[:filled_count]))
        return {'success': filled_count >= 3 and filled_required >= 3}
        
    except Exception as e:
        log(logger, 'error', f"AI shipping fill error: {e}", 'ADDRESS_FILL', 'LLM')
        return {'success': False, 'error': str(e)}


async def _fill_duplicate_fields(page, filled_fields):
    """Fill duplicate/confirmation fields (e.g., Confirm Email, Confirm Phone)"""
    try:
        duplicate_keywords = {
            'email': ['confirm email', 'verify email', 'email confirmation', 'confirm e-mail', 'retype email'],
            'phone': ['confirm phone', 'verify phone', 'phone confirmation', 'retype phone'],
            'firstName': ['confirm first name', 'verify first name'],
            'lastName': ['confirm last name', 'verify last name']
        }
        
        filled_count = 0
        from phase2.checkout_dom_finder import fill_input_field
        
        for field_type, value in filled_fields.items():
            if field_type in duplicate_keywords:
                keywords = duplicate_keywords[field_type]
                result = await fill_input_field(page, keywords, value, max_retries=1)
                if result.get('success'):
                    filled_count += 1
                    log(logger, 'info', f"✓ Filled duplicate field for {field_type}", 'ADDRESS_FILL', 'LLM')
                    await asyncio.sleep(0.3)
        
        return {'filled_count': filled_count}
    except Exception as e:
        log(logger, 'error', f"Error filling duplicate fields: {e}", 'ADDRESS_FILL', 'LLM')
        return {'filled_count': 0}


async def _ai_determine_next_action(page, llm_client, current_stage):
    """Use AI to determine next action when stuck"""
    try:
        state = await get_page_state(page)
        simple_btns = [{"text": b.get('text','')[:60], "class": b.get('className','')[:40]} for b in state['buttons'][:20]]
        simple_fields = [{"type": f.get('type',''), "name": f.get('name','')[:30], "label": f.get('label','')[:40]} for f in state['fields'][:15]]
        
        prompt = f"""Determine next action after filling {current_stage}.

CURRENT STATE:
- URL: {state['url']}
- Buttons: {simple_btns[:10]}
- Fields: {simple_fields[:10]}

TASK: What should we do next?
Options:
1. Click a button (provide keywords)
2. Fill more fields (provide field type)
3. Wait (page is loading)
4. Already progressed (no action needed)

RESPONSE (JSON):
{{"reasoning": "...", "action": "click_button|fill_field|wait|none", "keywords": ["..."], "confidence": 0.8}}"""
        
        response = await llm_client.complete(prompt, max_tokens=400)
        action_type = response.get('action', 'none')
        
        if action_type == 'click_button' and response.get('keywords'):
            result = await execute_tool(page, 'find_and_click_button', {
                'keywords': response['keywords'],
                'max_retries': 2
            })
            return {'success': result.get('success'), 'action': f"clicked {response['keywords']}"}
        elif action_type == 'wait':
            await asyncio.sleep(3)
            return {'success': True, 'action': 'waited'}
        else:
            return {'success': True, 'action': 'no action needed'}
    except Exception as e:
        log(logger, 'error', f"AI next action error: {e}", 'ADDRESS_FILL', 'LLM')
        return {'success': False}


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


async def _validate_page_changed(page, initial_url, initial_state, action_description):
    """Validate that page changed after an action"""
    await asyncio.sleep(2)  # Wait for changes to take effect
    
    new_url = page.url
    new_state = await get_page_state(page)
    
    # Log initial vs new state
    log(logger, 'info', f'Validation check: Initial URL={initial_url}, New URL={new_url}', 'CHECKOUT', 'VALIDATION')
    log(logger, 'info', f'Validation check: Initial fields={len(initial_state["fields"])}, New fields={len(new_state["fields"])}', 'CHECKOUT', 'VALIDATION')
    log(logger, 'info', f'Validation check: Initial buttons={len(initial_state["buttons"])}, New buttons={len(new_state["buttons"])}', 'CHECKOUT', 'VALIDATION')
    
    # Check multiple indicators of change
    url_changed = new_url != initial_url
    field_count_changed = len(new_state['fields']) != len(initial_state['fields'])
    button_count_changed = len(new_state['buttons']) != len(initial_state['buttons'])
    
    # Check if field names changed (only if counts are same)
    fields_changed = False
    if len(initial_state['fields']) == len(new_state['fields']):
        initial_field_names = set((f.get('name','') + '|' + f.get('id','')) for f in initial_state['fields'] if f.get('name') or f.get('id'))
        new_field_names = set((f.get('name','') + '|' + f.get('id','')) for f in new_state['fields'] if f.get('name') or f.get('id'))
        fields_changed = len(initial_field_names) > 0 and initial_field_names != new_field_names
    
    # Check if button text changed (only if counts are same)
    buttons_changed = False
    if len(initial_state['buttons']) == len(new_state['buttons']):
        initial_button_texts = set(b.get('text','').strip()[:50] for b in initial_state['buttons'] if b.get('text','').strip())
        new_button_texts = set(b.get('text','').strip()[:50] for b in new_state['buttons'] if b.get('text','').strip())
        buttons_changed = len(initial_button_texts) > 0 and initial_button_texts != new_button_texts
    
    # Check if page title changed
    title_changed = initial_state.get('title','') != new_state.get('title','')
    
    # Any change is valid
    page_changed = url_changed or field_count_changed or button_count_changed or fields_changed or buttons_changed or title_changed
    
    # Log detailed comparison
    log(logger, 'info', f'Change detection: URL={url_changed}, FieldCount={field_count_changed}, ButtonCount={button_count_changed}, FieldNames={fields_changed}, ButtonTexts={buttons_changed}, Title={title_changed}', 'CHECKOUT', 'VALIDATION')
    
    if page_changed:
        changes = []
        if url_changed: changes.append(f'URL: {initial_url} → {new_url}')
        if field_count_changed: changes.append(f'Fields: {len(initial_state["fields"])} → {len(new_state["fields"])}')
        if button_count_changed: changes.append(f'Buttons: {len(initial_state["buttons"])} → {len(new_state["buttons"])}')
        if fields_changed: changes.append('Field names changed')
        if buttons_changed: changes.append('Button texts changed')
        if title_changed: changes.append(f'Title changed')
        
        log(logger, 'info', f'✓ Page changed after {action_description}: {" | ".join(changes)}', 'CHECKOUT', 'VALIDATION')
        return True
    else:
        log(logger, 'error', f'✗ VALIDATION FAILED: No page change detected after {action_description}', 'CHECKOUT', 'VALIDATION')
        log(logger, 'error', f'  URL unchanged: {initial_url}', 'CHECKOUT', 'VALIDATION')
        log(logger, 'error', f'  Fields unchanged: {len(initial_state["fields"])} fields', 'CHECKOUT', 'VALIDATION')
        log(logger, 'error', f'  Buttons unchanged: {len(initial_state["buttons"])} buttons', 'CHECKOUT', 'VALIDATION')
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
    
    from ui.api.llm_config_api import get_session_llm_config
    llm_config = get_session_llm_config()
    llm_client = LLMClient(config=llm_config) if llm_config else LLMClient()
    
    try:
        # Stage 1: Proceed to checkout
        log(logger, 'info', 'STAGE 1: Proceed to Checkout', 'CHECKOUT', 'CORE')
        result = await ai_proceed_to_checkout(page, llm_client)
        if not result.get('success'):
            log(logger, 'warning', 'Primary checkout failed, trying direct URL navigation...', 'CHECKOUT', 'CORE')
            # Final fallback: Try direct URL navigation
            from urllib.parse import urlparse
            parsed = urlparse(page.url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            cart_paths = ['/checkout', '/cart', '/checkout/information', '/checkout/cart']
            checkout_found = False
            
            for cart_path in cart_paths:
                try:
                    cart_url = base_url + cart_path
                    log(logger, 'info', f'Trying direct navigation: {cart_url}', 'CHECKOUT', 'CORE')
                    response = await page.goto(cart_url, wait_until='domcontentloaded', timeout=10000)
                    
                    if response and response.status < 400:
                        await asyncio.sleep(3)
                        state = await get_page_state(page)
                        
                        # Check if we're on checkout page with form fields
                        has_email = any('email' in f.get('name','').lower() or f.get('type')=='email' for f in state['fields'])
                        has_form = len(state['fields']) >= 2
                        
                        if 'checkout' in page.url.lower() and (has_email or has_form):
                            log(logger, 'info', f'✓ Successfully navigated to checkout: {page.url}', 'CHECKOUT', 'CORE')
                            checkout_found = True
                            break
                except Exception as e:
                    log(logger, 'warning', f'Failed {cart_url}: {str(e)[:50]}', 'CHECKOUT', 'CORE')
                    continue
            
            if not checkout_found:
                return {'success': False, 'error': 'Failed to proceed to checkout', 'stage': 'checkout_button'}
        
        # Stage 2: Guest checkout (ALWAYS prioritize guest checkout)
        log(logger, 'info', 'STAGE 2: Guest Checkout (PRIORITY)', 'CHECKOUT', 'CORE')
        await asyncio.sleep(3)  # Wait for page to fully load
        
        # Try guest checkout with continue button
        guest_result = await ai_handle_guest_checkout(page, llm_client)
        
        # ALWAYS try to click continue after guest checkout
        if guest_result.get('success'):
            log(logger, 'info', 'Guest checkout selected, looking for continue button...', 'CHECKOUT', 'CORE')
            await asyncio.sleep(2)
            continue_result = await execute_tool(page, 'find_and_click_button', {
                'keywords': ['continue', 'next', 'proceed'],
                'max_retries': 2
            })
            if continue_result.get('success'):
                log(logger, 'info', 'Continue button clicked after guest checkout', 'CHECKOUT', 'CORE')
                await asyncio.sleep(3)
        
        await asyncio.sleep(2)
        
        # Check for password field after guest checkout attempt
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
        await asyncio.sleep(2)  # Wait for form to render
        contact_data = customer_data.get('contact', {})
        result = await ai_fill_contact_info(page, contact_data, llm_client)
        if not result.get('success'):
            return {'success': False, 'error': 'Failed to fill contact info', 'stage': 'contact_info'}
        
        await asyncio.sleep(3)  # Wait after contact info
        
        # Stage 4: Shipping address
        log(logger, 'info', 'STAGE 4: Shipping Address', 'CHECKOUT', 'CORE')
        await asyncio.sleep(2)  # Wait for shipping form to render
        address_data = customer_data.get('shippingAddress', {})
        result = await ai_fill_shipping_address(page, address_data, llm_client)
        if not result.get('success'):
            return {'success': False, 'error': 'Failed to fill shipping address', 'stage': 'shipping_address'}
        
        # Validate all address fields
        await asyncio.sleep(2)
        log(logger, 'info', 'Validating address fields...', 'CHECKOUT', 'VALIDATION')
        verification = await page.evaluate('''
            () => {
                const fields = Array.from(document.querySelectorAll('input, select'));
                const actual = {};
                
                fields.forEach(f => {
                    if (!f.offsetParent) return;
                    const name = (f.name || f.id || '').toLowerCase();
                    const value = f.value || '';
                    
                    if (name.includes('address') && !name.includes('email')) actual.address = value;
                    if (name.includes('city')) actual.city = value;
                    if (name.includes('zip') || name.includes('postal')) actual.zip = value;
                    if (name.includes('state') || name.includes('province') || name.includes('region')) actual.state = value;
                    if (name.includes('country')) actual.country = value;
                });
                
                return actual;
            }
        ''')
        log(logger, 'info', f'Current values: {verification}', 'CHECKOUT', 'VALIDATION')
        
        # Validate and correct each field
        from phase2.checkout_dom_finder import fill_input_field, find_and_select_dropdown
        
        # Validate Zip
        expected_zip = address_data.get('postalCode', '')
        actual_zip = verification.get('zip', '')
        if expected_zip and actual_zip != expected_zip:
            log(logger, 'warning', f'Zip mismatch: expected={expected_zip}, actual={actual_zip}', 'CHECKOUT', 'VALIDATION')
            await fill_input_field(page, ['zip', 'postal', 'zipcode'], expected_zip, max_retries=1)
            await asyncio.sleep(0.5)
        else:
            log(logger, 'info', f'✓ Zip validated: {actual_zip}', 'CHECKOUT', 'VALIDATION')
        
        # Validate City
        expected_city = address_data.get('city', '')
        actual_city = verification.get('city', '')
        if expected_city and actual_city.lower() != expected_city.lower():
            log(logger, 'warning', f'City mismatch: expected={expected_city}, actual={actual_city}', 'CHECKOUT', 'VALIDATION')
            await fill_input_field(page, ['city'], expected_city, max_retries=1)
            await asyncio.sleep(0.5)
        else:
            log(logger, 'info', f'✓ City validated: {actual_city}', 'CHECKOUT', 'VALIDATION')
        
        # Validate State
        expected_state = address_data.get('province', '')
        actual_state = verification.get('state', '')
        if expected_state and actual_state.upper() != expected_state.upper():
            log(logger, 'warning', f'State mismatch: expected={expected_state}, actual={actual_state}', 'CHECKOUT', 'VALIDATION')
            await find_and_select_dropdown(page, ['state', 'province', 'region'], expected_state, max_retries=1)
            await asyncio.sleep(0.5)
        else:
            log(logger, 'info', f'✓ State validated: {actual_state}', 'CHECKOUT', 'VALIDATION')
        
        # Validate Country
        expected_country = address_data.get('country', 'United States')
        actual_country = verification.get('country', '')
        country_codes = {'United States': 'US', 'India': 'IN', 'Canada': 'CA', 'United Kingdom': 'GB'}
        expected_code = country_codes.get(expected_country, expected_country)
        if actual_country and actual_country.upper() not in [expected_country.upper(), expected_code.upper()]:
            log(logger, 'warning', f'Country mismatch: expected={expected_country}, actual={actual_country}', 'CHECKOUT', 'VALIDATION')
            await find_and_select_dropdown(page, ['country'], expected_code, max_retries=1)
            await asyncio.sleep(0.5)
        else:
            log(logger, 'info', f'✓ Country validated: {actual_country}', 'CHECKOUT', 'VALIDATION')
        
        # Validate Address
        expected_address = address_data.get('addressLine1', '')
        actual_address = verification.get('address', '')
        if expected_address and expected_address.lower() not in actual_address.lower():
            log(logger, 'warning', f'Address mismatch: expected={expected_address}, actual={actual_address}', 'CHECKOUT', 'VALIDATION')
            await fill_input_field(page, ['address', 'street'], expected_address, max_retries=1)
            await asyncio.sleep(0.5)
        else:
            log(logger, 'info', f'✓ Address validated: {actual_address[:50]}', 'CHECKOUT', 'VALIDATION')
        
        log(logger, 'info', '✓ Address validation complete', 'CHECKOUT', 'VALIDATION')
        
        # Wait for address suggestions and select if available
        await asyncio.sleep(2)
        suggestion_clicked = await execute_tool(page, 'find_and_click_button', {
            'keywords': ['suggested', 'use this address', 'select address'],
            'max_retries': 1
        })
        if suggestion_clicked.get('success'):
            log(logger, 'info', 'Selected suggested address', 'CHECKOUT', 'CORE')
            await asyncio.sleep(1)
        
        # Click continue/save button after address with fallbacks and validation
        continue_keywords = [
            ['save and continue', 'continue to shipping'],
            ['continue', 'next'],
            ['save', 'submit']
        ]
        continue_clicked = False
        initial_url = page.url
        initial_state = await get_page_state(page)
        
        for keywords in continue_keywords:
            result = await execute_tool(page, 'find_and_click_button', {
                'keywords': keywords,
                'max_retries': 1
            })
            if result.get('success'):
                log(logger, 'info', f'Clicked button with keywords: {keywords}', 'CHECKOUT', 'CORE')
                
                # Validate: Check if ANY change happened on page
                if await _validate_page_changed(page, initial_url, initial_state, f'clicking {keywords}'):
                    continue_clicked = True
                    await asyncio.sleep(1)
                    break
                else:
                    # Try next keyword set
                    continue
        
        # Stage 5: Continue to payment with fallbacks and validation
        log(logger, 'info', 'STAGE 5: Continue to Payment', 'CHECKOUT', 'CORE')
        payment_keywords = [
            ['continue to payment', 'proceed to payment'],
            ['continue', 'next'],
            ['save and continue']
        ]
        initial_url = page.url
        initial_state = await get_page_state(page)
        
        for keywords in payment_keywords:
            result = await execute_tool(page, 'find_and_click_button', {
                'keywords': keywords,
                'max_retries': 1
            })
            if result.get('success'):
                log(logger, 'info', f'Clicked payment button with keywords: {keywords}', 'CHECKOUT', 'CORE')
                
                # Validate: Check if ANY change happened on page
                if await _validate_page_changed(page, initial_url, initial_state, f'clicking {keywords}'):
                    await asyncio.sleep(2)
                    break
                else:
                    # Try next keyword set
                    continue
        
        log(logger, 'info', '=' * 60, 'CHECKOUT', 'CORE')
        log(logger, 'info', 'AI Checkout Flow Completed Successfully', 'CHECKOUT', 'CORE')
        log(logger, 'info', '=' * 60, 'CHECKOUT', 'CORE')
        
        return {'success': True, 'message': 'AI checkout flow completed'}
        
    except Exception as e:
        log(logger, 'error', f"AI checkout flow error: {e}", 'CHECKOUT', 'CORE')
        return {'success': False, 'error': str(e)}
