"""
Reactive Agent - Iterative observe-reason-act loop
Continuously observes page state, reasons about next action, executes, and adapts
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ReactiveAgent:
    def __init__(self, page, llm_client):
        self.page = page
        self.llm = llm_client
        self.conversation_history = []
        self.max_iterations = 30
        self.last_url = None
        self.url_change_expected = False
        self.last_clicked_button = None
        self.initial_url = None
        self.dismissed_popups_count = 0
        
    async def comprehensive_viewport_cleanup(self):
        """Aggressively dismiss ALL popups, modals, overlays, and blockers"""
        try:
            dismissed = await self.page.evaluate("""
                () => {
                    let dismissed = 0;
                    
                    // Cookie consent selectors
                    const cookieSelectors = [
                        '[id*="cookie"] button', '[class*="cookie"] button',
                        '[data-testid*="cookie"] button', '[aria-label*="cookie" i] button',
                        'button:has-text("Accept")', 'button:has-text("Accept All")',
                        'button:has-text("Allow")', 'button:has-text("OK")',
                        'button:has-text("I agree")', '.cookie-banner button',
                        '#onetrust-accept-btn-handler', '.gdpr-accept'
                    ];
                    
                    // Modal/popup/drawer close selectors (PRIORITY)
                    const closeSelectors = [
                        '[data-drawer-action="close"]', '.drawer__close',
                        '[aria-label*="close" i]', '[aria-label*="dismiss" i]',
                        '.modal-close', '.popup-close', '.overlay-close',
                        '[data-backdrop]', '.backdrop', '[data-overlay]',
                        'button[class*="close"]', '.close-button', '.btn-close',
                        '[data-dismiss]', '[data-dismiss="modal"]',
                        'button:has-text("×")', 'button:has-text("✕")',
                        '[role="dialog"] button[aria-label*="close" i]',
                        '.modal button[class*="close"]',
                        '[class*="drawer"] button[class*="close"]',
                        '[class*="sidebar"] button[class*="close"]',
                        '[class*="offcanvas"] button[class*="close"]',
                        '.drawer button', '[data-drawer] button[class*="close"]'
                    ];
                    
                    // Cart drawer/overlay (often blocks checkout)
                    const cartOverlaySelectors = [
                        '[data-drawer="cart"] [data-drawer-action="close"]',
                        '.cart-drawer button[class*="close"]',
                        '[id*="cart-drawer"] button[class*="close"]',
                        '.minicart-overlay button[class*="close"]',
                        '[class*="cart-overlay"] [aria-label*="close" i]',
                        '[class*="side-cart"] button[class*="close"]',
                        '[class*="mini-cart"] button[class*="close"]'
                    ];
                    
                    // Newsletter/promo dismissal
                    const dismissalSelectors = [
                        '[class*="newsletter"] button[class*="close"]',
                        '[class*="signup"] button[class*="close"]',
                        'button:has-text("No thanks")', 'button:has-text("Skip")',
                        'button:has-text("Maybe later")', 'button:has-text("Not now")',
                        '[class*="promo"] button[class*="close"]',
                        '[class*="discount"] button[class*="close"]'
                    ];
                    
                    // ALL selectors prioritized
                    const allSelectors = [
                        ...closeSelectors,
                        ...cartOverlaySelectors,
                        ...dismissalSelectors,
                        ...cookieSelectors
                    ];
                    
                    // Click ALL visible close/dismiss buttons
                    for (const selector of allSelectors) {
                        try {
                            const elements = document.querySelectorAll(selector);
                            for (const el of elements) {
                                if (el.offsetParent !== null && typeof el.click === 'function') {
                                    const text = el.textContent?.toLowerCase() || '';
                                    const ariaLabel = el.getAttribute('aria-label')?.toLowerCase() || '';
                                    
                                    // Skip primary action buttons
                                    const skipWords = ['add to cart', 'buy now', 'checkout', 'place order', 'submit'];
                                    const shouldSkip = skipWords.some(word => 
                                        text.includes(word) || ariaLabel.includes(word)
                                    );
                                    
                                    if (!shouldSkip) {
                                        el.click();
                                        dismissed++;
                                        console.log('Dismissed:', selector);
                                    }
                                }
                            }
                        } catch (e) {
                            // Continue
                        }
                    }
                    
                    // Remove ALL overlay/backdrop elements
                    try {
                        const overlays = document.querySelectorAll(
                            '.overlay, .backdrop, [data-backdrop], [class*="modal-backdrop"], ' +
                            '[class*="overlay-backdrop"], .drawer-overlay, [data-overlay], ' +
                            '[class*="drawer-backdrop"], [class*="side-modal"], ' +
                            '.modal-backdrop, .drawer-backdrop'
                        );
                        overlays.forEach(overlay => {
                            if (overlay.offsetParent !== null) {
                                overlay.style.display = 'none';
                                overlay.remove();
                                dismissed++;
                            }
                        });
                    } catch (e) {
                        // Continue
                    }
                    
                    // Press Escape multiple times
                    for (let i = 0; i < 3; i++) {
                        document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
                    }
                    
                    // Remove scroll locks
                    try {
                        document.body.removeAttribute('aria-hidden');
                        document.body.style.overflow = '';
                        document.body.style.position = '';
                        document.documentElement.style.overflow = '';
                    } catch (e) {
                        // Continue
                    }
                    
                    return dismissed;
                }
            """)
            
            if dismissed > 0:
                logger.info(f"✅ Dismissed {dismissed} blocking element(s)")
                self.dismissed_popups_count += dismissed
                await asyncio.sleep(1)
            
            # Also press Escape through Playwright
            try:
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.5)
            except:
                pass
                
            return dismissed > 0
            
        except Exception as e:
            logger.warning(f"Viewport cleanup error: {e}")
            return False
    
    async def identify_page_type(self):
        """Enhanced page type identification with navigation handling"""
        for attempt in range(3):
            try:
                page_info = await self.page.evaluate("""
                () => {
                    const url = window.location.href.toLowerCase();
                    const title = document.title.toLowerCase();
                    const bodyText = document.body.innerText.toLowerCase();
                    
                    // Order confirmation
                    if (url.includes('/thank') || url.includes('/confirmation') || 
                        url.includes('/order-complete') || title.includes('thank you')) {
                        return 'order_confirmation';
                    }
                    
                    // Cart page
                    if (url.includes('/cart') || title.includes('cart') || title.includes('basket')) {
                        return 'cart';
                    }
                    
                    // Product page
                    if (url.includes('/product') || url.includes('/p/') || 
                        bodyText.includes('add to cart') || bodyText.includes('add to bag')) {
                        return 'product';
                    }
                    
                    // Checkout pages - be STRICT about payment detection
                    if (url.includes('/checkout') || url.includes('/payment') || 
                        url.includes('/billing') || title.includes('checkout')) {
                        
                        // ONLY mark as payment if we see actual payment fields
                        const hasCardNumber = document.querySelector('input[name*="card" i][name*="number" i]') ||
                                             document.querySelector('input[id*="card" i][id*="number" i]') ||
                                             document.querySelector('input[placeholder*="card number" i]') ||
                                             document.querySelector('iframe[name*="card" i]') ||
                                             bodyText.includes('card number') ||
                                             bodyText.includes('credit card') ||
                                             bodyText.includes('debit card');
                        
                        if (hasCardNumber || url.includes('/payment')) {
                            return 'checkout_payment';
                        }
                        
                        // Check for contact/email fields FIRST (before address)
                        const hasEmail = document.querySelector('input[type="email"]') ||
                                        document.querySelector('input[name*="email" i]') ||
                                        document.querySelector('input[id*="email" i]');
                        const hasName = document.querySelector('input[name*="first" i][name*="name" i]') ||
                                       document.querySelector('input[id*="first" i][id*="name" i]') ||
                                       document.querySelector('input[name*="last" i][name*="name" i]') ||
                                       document.querySelector('input[id*="last" i][id*="name" i]') ||
                                       bodyText.includes('contact information') ||
                                       bodyText.includes('customer information');
                        
                        if (hasEmail || hasName) {
                            return 'checkout_contact';
                        }
                        
                        // Check for shipping/address fields AFTER contact check
                        const hasAddress = document.querySelector('input[name*="address" i]') ||
                                          document.querySelector('input[id*="address" i]') ||
                                          document.querySelector('input[name*="street" i]') ||
                                          document.querySelector('input[id*="street" i]') ||
                                          bodyText.includes('shipping address') ||
                                          bodyText.includes('delivery address');
                        
                        if (hasAddress) {
                            return 'checkout_shipping';
                        }
                        
                        return 'checkout_unknown';
                    }
                    
                    return 'unknown';
                }
            """)
            
                return page_info
                
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"Page type identification attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(1)
                    continue
                else:
                    logger.warning(f"Page type identification error: {e}")
                    return 'unknown'
    
    async def check_blocking_overlays(self):
        """Check if there are blocking overlays/modals/drawers"""
        try:
            has_blocker = await self.page.evaluate("""
                () => {
                    // Check for visible modals, drawers, overlays
                    const blockerSelectors = [
                        '.modal', '.drawer', '.overlay', '.popup', '.dialog',
                        '[role="dialog"]', '[data-drawer]', '[data-modal]',
                        '.cart-drawer', '.side-cart', '.mini-cart',
                        '[class*="modal"]', '[class*="drawer"]', '[class*="overlay"]',
                        '[class*="popup"]', '[class*="dialog"]'
                    ];
                    
                    for (const selector of blockerSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            if (el.offsetParent !== null) {
                                // Check if it's actually blocking (has backdrop or z-index > 1000)
                                const style = window.getComputedStyle(el);
                                const zIndex = parseInt(style.zIndex) || 0;
                                if (zIndex > 100 || el.classList.contains('show') || 
                                    el.classList.contains('open') || el.classList.contains('active')) {
                                    return true;
                                }
                            }
                        }
                    }
                    
                    // Check for backdrop elements
                    const backdrops = document.querySelectorAll('.backdrop, [data-backdrop], .modal-backdrop, .drawer-backdrop');
                    for (const backdrop of backdrops) {
                        if (backdrop.offsetParent !== null) {
                            return true;
                        }
                    }
                    
                    return false;
                }
            """)
            
            return has_blocker
            
        except Exception as e:
            logger.warning(f"Blocker check error: {e}")
            return False
    
    async def observe_page(self):
        """Enhanced observation with better page understanding"""
        
        # Wait for page stability
        for attempt in range(3):
            try:
                await self.page.wait_for_load_state('domcontentloaded', timeout=5000)
                break
            except:
                if attempt < 2:
                    await asyncio.sleep(1)
        
        try:
            # Identify page type
            page_type = await self.identify_page_type()
            
            # Check for blocking overlays
            has_blocker = await self.check_blocking_overlays()
            
            # Get page analysis
            from shared.page_analyzer import analyze_page_content
            analysis = await analyze_page_content(self.page)
            
            # Enhanced observation
            observation = {
                'url': analysis['url'],
                'pageType': page_type,
                'analyzedType': analysis['pageType'],
                'hasBlockingOverlay': has_blocker,
                'buttons': analysis['buttons'][:10],
                'inputs': analysis['inputs'][:10],
                'errors': [],
                'title': await self.page.title()
            }
            
            return observation
            
        except Exception as e:
            logger.warning(f"Observation failed: {e}")
            await asyncio.sleep(2)
            
            # Fallback observation
            page_type = await self.identify_page_type()
            has_blocker = await self.check_blocking_overlays()
            
            return {
                'url': self.page.url,
                'pageType': page_type,
                'analyzedType': 'unknown',
                'hasBlockingOverlay': has_blocker,
                'buttons': [],
                'inputs': [],
                'errors': [],
                'title': await self.page.title()
            }
    
    async def reason_and_decide(self, goal, customer_data, observation, is_first):
        """Enhanced reasoning with better context"""
        
        history_text = "\n".join([
            f"{h['action']}({h.get('params', {})}) → {'✓' if h['result'].get('success') else '✗'}: {h['result'].get('message', '')[:50]}"
            for h in self.conversation_history[-3:]
        ])
        
        customer_info = ""
        if is_first:
            customer_info = f"""CUSTOMER DATA:
Email: {customer_data.get('contact', {}).get('email')}
Name: {customer_data.get('contact', {}).get('firstName')} {customer_data.get('contact', {}).get('lastName')}
Address: {customer_data.get('shippingAddress', {}).get('addressLine1')}, {customer_data.get('shippingAddress', {}).get('city')}, {customer_data.get('shippingAddress', {}).get('province')} {customer_data.get('shippingAddress', {}).get('postalCode')}
Country: {customer_data.get('shippingAddress', {}).get('country')}

"""
        
        # Page type guidance
        page_guidance = ""
        if observation['pageType'] == 'cart':
            page_guidance = "\n🛒 ON CART PAGE: You MUST click 'Checkout' or 'Proceed to Checkout' button to continue."
        elif observation['pageType'] == 'checkout_contact':
            page_guidance = "\n📧 ON CONTACT PAGE: Fill email and name fields using use_checkout_flow(fill_contact)."
        elif observation['pageType'] == 'checkout_shipping':
            page_guidance = "\n📦 ON SHIPPING PAGE: Fill address fields using use_checkout_flow(fill_shipping)."
        elif observation['pageType'] == 'checkout_payment':
            page_guidance = "\n💳 ON PAYMENT PAGE: Goal achieved! Stop here."
        elif observation['pageType'] == 'product':
            page_guidance = "\n🏷️ ON PRODUCT PAGE: Need to add item to cart first if not already in cart."
        
        prompt = f"""E-commerce automation. Observe page, decide ONE action to reach payment page.

GOAL: {goal}

{customer_info}CURRENT STATE:
URL: {observation['url']}
Page Type: {observation['pageType']} (Title: {observation.get('title', 'N/A')[:50]})
Blocking Overlay: {observation['hasBlockingOverlay']}{page_guidance}

Available Buttons: {self._format_buttons(observation['buttons'])}
Available Inputs: {self._format_inputs(observation['inputs'])}

Recent Actions (last 3):
{history_text or 'None yet'}

DECISION RULES:
1. **If hasBlockingOverlay=True** → ALWAYS use dismiss_modal() FIRST before any other action
2. **If on CART page** → Click "Checkout" or "Proceed to Checkout" button
3. **If clicked Checkout but still on cart** → dismiss_modal then click Checkout again
4. **If on checkout and see email/name inputs** → use_checkout_flow(fill_contact)
5. **If contact filled and see address/city inputs** → use_checkout_flow(fill_shipping)
6. **If all forms filled** → Click "Continue" or "Next" button to proceed
7. **If on payment/billing page** → goal_achieved
8. **If last action FAILED** → Try alternative approach or dismiss_modal

AVAILABLE TOOLS:
- dismiss_modal() - Remove blocking overlays/modals/drawers (USE FIRST if hasBlockingOverlay=True)
- click_button(text) - Click button by visible text
- use_checkout_flow(action) - Fill forms: "fill_contact", "fill_shipping", "select_shipping"
- fill_field(field_identifier, value) - Fill single field
- wait(seconds) - Wait before next action
- goal_achieved() - Mark goal as complete

IMPORTANT:
- ALWAYS dismiss modals BEFORE clicking buttons if overlay is blocking
- Be decisive: choose ONE clear action
- If stuck, try dismiss_modal()

Respond with JSON only:
{{"reasoning": "brief explanation", "action": "tool_name", "params": {{"key": "value"}}}}
"""
        
        response = await self.llm.complete(prompt, max_tokens=200)
        return response
    
    def _format_buttons(self, buttons):
        return ", ".join([f"'{b['text'] or b['ariaLabel']}'"
            for b in buttons if (b['text'] or b['ariaLabel']) and len(b['text'] or b['ariaLabel']) < 50][:8]) or "None"
    
    def _format_inputs(self, inputs):
        return ", ".join([f"{i['type']}[{i['name'] or i['id']}]"
            for i in inputs if i['name'] or i['id']][:8]) or "None"
    
    async def execute_action(self, action_decision, customer_data):
        """Execute the decided action"""
        action = action_decision.get('action')
        params = action_decision.get('params', {})
        
        logger.info(f"EXECUTING: {action} with {params}")
        
        try:
            if action == 'dismiss_modal':
                # Use comprehensive cleanup
                dismissed = await self.comprehensive_viewport_cleanup()
                return {'success': dismissed, 'message': f'Dismissed {self.dismissed_popups_count} blocker(s)' if dismissed else 'No blockers found'}
            
            elif action == 'click_button':
                return await self._click_button(params.get('text'))
            
            elif action == 'fill_field':
                return await self._fill_field(params.get('field_name'), params.get('value'))
            
            elif action == 'select_dropdown':
                return await self._select_dropdown(params.get('field_name'), params.get('value'))
            
            elif action == 'press_key':
                await self.page.keyboard.press(params.get('key', 'Escape'))
                return {'success': True, 'message': f"Pressed {params.get('key')}"}
            
            elif action == 'wait':
                await asyncio.sleep(params.get('seconds', 2))
                return {'success': True, 'message': f"Waited {params.get('seconds')}s"}
            
            elif action == 'scroll':
                direction = params.get('direction', 'down')
                await self.page.evaluate(f"window.scrollBy(0, {500 if direction == 'down' else -500})")
                return {'success': True, 'message': f"Scrolled {direction}"}
            
            elif action == 'use_checkout_flow':
                return await self._use_checkout_flow(params.get('action'), customer_data)
            
            elif action == 'goal_achieved':
                return {'success': True, 'message': 'Goal achieved', 'goal_achieved': True}
            
            else:
                return {'success': False, 'message': f'Unknown action: {action}'}
                
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    async def _use_checkout_flow(self, action, customer_data):
        """Use rule-based checkout functions, fallback to LLM if they fail"""
        from phase2.checkout_flow import fill_contact_info, fill_shipping_address, select_cheapest_shipping
        
        # Try rule-based approach first
        if action == 'fill_contact':
            result = await fill_contact_info(self.page, customer_data.get('contact', {}))
        elif action == 'fill_shipping':
            result = await fill_shipping_address(self.page, customer_data.get('shippingAddress', {}))
        elif action == 'select_shipping':
            result = await select_cheapest_shipping(self.page)
        else:
            return {'success': False, 'message': f'Unknown checkout action: {action}'}
        
        # If rule-based failed, use LLM to analyze and fill fields
        if not result.get('success'):
            logger.warning(f"Rule-based {action} failed: {result.get('message')}. Calling LLM for help...")
            return await self._llm_fill_form(action, customer_data)
        
        return result
    
    async def _llm_fill_form(self, form_type, customer_data):
        """Use LLM to analyze page and fill form fields when rule-based approach fails"""
        try:
            # Get all visible form fields
            form_analysis = await self.page.evaluate("""
                () => {
                    const inputs = Array.from(document.querySelectorAll('input, textarea, select'))
                        .filter(el => el.offsetParent && el.type !== 'hidden')
                        .map(el => ({
                            type: el.type || el.tagName.toLowerCase(),
                            name: el.name || '',
                            id: el.id || '',
                            placeholder: el.placeholder || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            value: el.value || '',
                            required: el.required || false
                        }));
                    
                    const buttons = Array.from(document.querySelectorAll('button, input[type="submit"]'))
                        .filter(el => el.offsetParent)
                        .map(el => ({
                            text: el.textContent?.trim() || el.value || '',
                            type: el.type || 'button',
                            ariaLabel: el.getAttribute('aria-label') || ''
                        }));
                    
                    return { inputs, buttons, url: window.location.href };
                }
            """)
            
            # Prepare customer data based on form type
            if form_type == 'fill_contact':
                data_to_fill = customer_data.get('contact', {})
                data_description = f"Email: {data_to_fill.get('email')}, First Name: {data_to_fill.get('firstName')}, Last Name: {data_to_fill.get('lastName')}, Phone: {data_to_fill.get('phone', 'N/A')}"
            elif form_type == 'fill_shipping':
                data_to_fill = customer_data.get('shippingAddress', {})
                data_description = f"Address: {data_to_fill.get('addressLine1')}, City: {data_to_fill.get('city')}, Province: {data_to_fill.get('province')}, Postal Code: {data_to_fill.get('postalCode')}, Country: {data_to_fill.get('country')}"
            else:
                return {'success': False, 'message': f'Unknown form type: {form_type}'}
            
            # Ask LLM to map customer data to form fields
            prompt = f"""Analyze this checkout form and map customer data to the correct fields.

FORM TYPE: {form_type}

CUSTOMER DATA TO FILL:
{data_description}

AVAILABLE FORM FIELDS:
{self._format_fields_for_llm(form_analysis['inputs'][:15])}

AVAILABLE BUTTONS:
{', '.join([b['text'] for b in form_analysis['buttons'][:8] if b['text']])}

TASK: Map each piece of customer data to the correct form field. Return a JSON array of fill actions.

RESPONSE FORMAT:
{{
  "fields": [
    {{"field_identifier": "email", "value": "customer@email.com", "match_reason": "email field"}},
    {{"field_identifier": "firstName", "value": "John", "match_reason": "first name field"}}
  ],
  "continue_button": "Continue" or null
}}

RULES:
- Use field name, id, or placeholder as field_identifier
- Only include fields that exist in the form
- If a Continue button exists, include it
- Be precise with field matching
"""
            
            response = await self.llm.complete(prompt, max_tokens=500)
            
            # Parse LLM response and fill fields
            fields_to_fill = response.get('fields', [])
            filled_count = 0
            
            for field_mapping in fields_to_fill:
                field_id = field_mapping.get('field_identifier')
                value = field_mapping.get('value')
                
                if field_id and value:
                    fill_result = await self._fill_field(field_id, value)
                    if fill_result.get('success'):
                        filled_count += 1
                        logger.info(f"✓ LLM filled {field_id} = {value}")
                    else:
                        logger.warning(f"✗ LLM failed to fill {field_id}")
            
            # Click continue button if specified
            continue_btn = response.get('continue_button')
            if continue_btn:
                await self._click_button(continue_btn)
                logger.info(f"✓ LLM clicked continue button: {continue_btn}")
            
            if filled_count > 0:
                return {'success': True, 'message': f'LLM filled {filled_count} fields for {form_type}'}
            else:
                return {'success': False, 'message': f'LLM could not fill any fields for {form_type}'}
                
        except Exception as e:
            logger.error(f"LLM form filling error: {e}")
            return {'success': False, 'message': f'LLM error: {str(e)}'}
    
    def _format_fields_for_llm(self, fields):
        """Format form fields for LLM prompt"""
        formatted = []
        for f in fields:
            parts = [f"Type: {f['type']}"]
            if f['name']: parts.append(f"name='{f['name']}'")
            if f['id']: parts.append(f"id='{f['id']}'")
            if f['placeholder']: parts.append(f"placeholder='{f['placeholder']}'")
            if f['ariaLabel']: parts.append(f"aria-label='{f['ariaLabel']}'")
            if f['required']: parts.append("REQUIRED")
            formatted.append(" | ".join(parts))
        return "\n".join(formatted)
    
    async def _click_button(self, text):
        """Click button by text and wait for URL change if checkout button"""
        from phase2.checkout_dom_finder import find_and_click_button
        
        url_before = self.page.url
        result = await find_and_click_button(self.page, [text.lower()], max_retries=1)
        
        if result.get('success'):
            # If checkout/continue button, wait for URL change
            if any(kw in text.lower() for kw in ['checkout', 'continue', 'proceed', 'next', 'payment']):
                try:
                    await self.page.wait_for_url(lambda url: url != url_before, timeout=3000)
                    await asyncio.sleep(1)
                    return {'success': True, 'message': f'Clicked {text}, URL changed'}
                except:
                    return {'success': False, 'message': f'Clicked {text} but URL did not change. Modal might be blocking.'}
            else:
                await asyncio.sleep(1)
        
        return result
    
    async def _fill_field(self, field_identifier, value):
        """Fill input field by name, id, or placeholder"""
        try:
            filled = await self.page.evaluate("""
                (identifier, val) => {
                    const input = document.querySelector(`input[name="${identifier}"]`) ||
                                  document.querySelector(`input[id="${identifier}"]`) ||
                                  document.querySelector(`input[placeholder*="${identifier}"]`) ||
                                  document.querySelector(`textarea[name="${identifier}"]`) ||
                                  document.querySelector(`textarea[id="${identifier}"]`);
                    if (input) {
                        input.value = val;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    }
                    return false;
                }
            """, field_identifier, value)
            await asyncio.sleep(0.5)
            return {'success': filled, 'message': f'Filled {field_identifier}' if filled else f'Field {field_identifier} not found'}
        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    async def _select_dropdown(self, field_identifier, value):
        """Select dropdown option by name or id"""
        try:
            selected = await self.page.evaluate("""
                (identifier, val) => {
                    const select = document.querySelector(`select[name="${identifier}"]`) ||
                                   document.querySelector(`select[id="${identifier}"]`);
                    if (select) {
                        const option = Array.from(select.options).find(opt => 
                            opt.text.toLowerCase().includes(val.toLowerCase()) ||
                            opt.value.toLowerCase().includes(val.toLowerCase())
                        );
                        if (option) {
                            select.value = option.value;
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                            return true;
                        }
                    }
                    return false;
                }
            """, field_identifier, value)
            await asyncio.sleep(0.5)
            return {'success': selected, 'message': f'Selected {value} in {field_identifier}' if selected else f'Dropdown {field_identifier} not found'}
        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}
    

    async def run(self, goal, customer_data):
        """Main reactive loop: observe → reason → act → repeat"""
        logger.info(f"🚀 REACTIVE AGENT: Starting with goal: {goal}")
        
        # Store initial URL for loop recovery
        self.initial_url = self.page.url
        logger.info(f"📍 Initial URL: {self.initial_url}")
        
        # Initial cleanup - dismiss any popups/modals
        logger.info("🧹 Performing initial viewport cleanup...")
        await self.comprehensive_viewport_cleanup()
        await asyncio.sleep(1)
        
        for iteration in range(self.max_iterations):
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"🔄 Iteration {iteration + 1}/{self.max_iterations}")
                logger.info(f"{'='*60}")
                
                # 1. Observe
                observation = await self.observe_page()
                logger.info(f"👁️ Page: {observation['pageType']} | URL: {observation['url'][:80]}")
                logger.info(f"📊 Buttons: {len(observation['buttons'])} | Inputs: {len(observation['inputs'])} | Blocker: {observation['hasBlockingOverlay']}")
                
                if observation['buttons']:
                    logger.info(f"🔘 Available buttons: {[b['text'] or b['ariaLabel'] for b in observation['buttons'][:5]]}")
                
                # Auto-dismiss blockers BEFORE reasoning
                if observation['hasBlockingOverlay']:
                    logger.info("⚠️ Blocking overlay detected! Auto-dismissing...")
                    await self.comprehensive_viewport_cleanup()
                    await asyncio.sleep(1)
                    # Re-observe after cleanup
                    observation = await self.observe_page()
                
                # Check if goal achieved by page type - ONLY if we actually see payment fields
                if observation['pageType'] == 'order_confirmation':
                    logger.info(f"✅ GOAL ACHIEVED - Reached order confirmation page")
                    return {'success': True, 'iterations': iteration + 1}
                
                # For payment page, verify we actually filled contact and shipping first
                if observation['pageType'] == 'checkout_payment':
                    # Check if we actually filled forms (history should show successful fills)
                    filled_contact = any(h.get('action') == 'use_checkout_flow' and 
                                       h.get('params', {}).get('action') == 'fill_contact' and 
                                       h.get('result', {}).get('success') 
                                       for h in self.conversation_history)
                    filled_shipping = any(h.get('action') == 'use_checkout_flow' and 
                                        h.get('params', {}).get('action') == 'fill_shipping' and 
                                        h.get('result', {}).get('success') 
                                        for h in self.conversation_history)
                    
                    if filled_contact and filled_shipping:
                        logger.info(f"✅ GOAL ACHIEVED - Reached payment page after filling forms")
                        return {'success': True, 'iterations': iteration + 1}
                    else:
                        logger.warning(f"⚠️ On payment page but forms not filled yet (contact:{filled_contact}, shipping:{filled_shipping})")
                        # Continue to fill forms
                
                # 2. Reason and Decide
                decision = await self.reason_and_decide(goal, customer_data, observation, iteration == 0)
                logger.info(f"🧠 Reasoning: {decision.get('reasoning', 'N/A')[:150]}")
                logger.info(f"⚡ Action: {decision.get('action')} | Params: {decision.get('params', {})}")
                
                # Check if goal achieved by decision
                if decision.get('action') == 'goal_achieved':
                    logger.info(f"✅ GOAL ACHIEVED - Agent decided goal is complete")
                    return {'success': True, 'iterations': iteration + 1}
                
                # 3. Act
                result = await self.execute_action(decision, customer_data)
                success_icon = "✅" if result.get('success') else "❌"
                logger.info(f"{success_icon} Result: {result.get('message', str(result))}")
                
                # 4. Record in history
                self.conversation_history.append({
                    'iteration': iteration + 1,
                    'observation': observation,
                    'reasoning': decision.get('reasoning'),
                    'action': decision.get('action'),
                    'params': decision.get('params'),
                    'result': result
                })
                
                # Detect stuck loop - same action failing repeatedly
                if len(self.conversation_history) >= 3:
                    last_3 = self.conversation_history[-3:]
                    if all(not h['result'].get('success') for h in last_3):
                        if all(h['action'] == last_3[0]['action'] for h in last_3):
                            logger.error(f"🔁 STUCK IN LOOP - {last_3[0]['action']} failing 3 times")
                            logger.error(f"💥 Last error: {last_3[-1]['result'].get('message')}")
                            
                            # If stuck on form filling, fields may not exist - STOP retrying
                            if last_3[0]['action'] == 'use_checkout_flow':
                                logger.error(f"❌ Form fields not found after 3 attempts - stopping agent")
                                return {'success': False, 'error': f"Form fields not found: {last_3[-1]['result'].get('message')}", 'iterations': iteration + 1}
                            
                            # For other actions, try cleanup once
                            logger.info("🧹 Attempting comprehensive cleanup...")
                            await self.comprehensive_viewport_cleanup()
                            await asyncio.sleep(2)
                            
                            # If still stuck, stop
                            return {'success': False, 'error': f"Stuck in loop: {last_3[0]['action']}", 'iterations': iteration + 1}
                
                # Check if goal achieved from action result
                if result.get('goal_achieved'):
                    logger.info(f"✅ GOAL ACHIEVED")
                    return {'success': True, 'iterations': iteration + 1}
                
                # Small delay between iterations
                await asyncio.sleep(1.5)
                
            except Exception as e:
                logger.error(f"💥 Iteration error: {e}")
                import traceback
                traceback.print_exc()
                
                # Try cleanup and continue
                await self.comprehensive_viewport_cleanup()
                await asyncio.sleep(2)
                continue
        
        logger.warning(f"⏱️ Max iterations reached without achieving goal")
        return {'success': False, 'error': 'Max iterations reached', 'iterations': self.max_iterations}