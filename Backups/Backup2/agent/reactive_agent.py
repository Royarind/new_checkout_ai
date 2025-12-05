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
        self.max_iterations = 20
        self.last_url = None
        
    async def observe_page(self):
        """Observe current page state - text-based without vision"""
        for attempt in range(3):
            try:
                await self.page.wait_for_load_state('domcontentloaded', timeout=5000)
                break
            except:
                if attempt < 2:
                    await asyncio.sleep(1)
        
        try:
            from shared.page_analyzer import analyze_page_content
            analysis = await analyze_page_content(self.page)
            
            return {
                'url': analysis['url'],
                'pageType': analysis['pageType'],
                'hasBlockingOverlay': analysis['hasBlockingOverlay'],
                'buttons': analysis['buttons'][:8],
                'inputs': analysis['inputs'][:8],
                'errors': []
            }
        except Exception as e:
            logger.warning(f"Observation failed: {e}, retrying...")
            await asyncio.sleep(2)
            return {
                'url': self.page.url,
                'pageType': 'unknown',
                'hasBlockingOverlay': False,
                'buttons': [],
                'inputs': [],
                'errors': []
            }
    
    async def reason_and_decide(self, goal, customer_data, observation, is_first):
        """Ask LLM to reason about current state and decide next action"""
        
        history_text = "\n".join([
            f"{h['action']}({h.get('params', {})}) → {'SUCCESS' if h['result'].get('success') else 'FAILED'}: {h['result'].get('message', '')[:50]}"
            for h in self.conversation_history[-2:]
        ])
        
        customer_info = ""
        if is_first:
            customer_info = f"""CUSTOMER DATA:
Email: {customer_data.get('contact', {}).get('email')}
Name: {customer_data.get('contact', {}).get('firstName')} {customer_data.get('contact', {}).get('lastName')}
Address: {customer_data.get('shippingAddress', {}).get('addressLine1')}, {customer_data.get('shippingAddress', {}).get('city')}, {customer_data.get('shippingAddress', {}).get('province')} {customer_data.get('shippingAddress', {}).get('postalCode')}
Country: {customer_data.get('shippingAddress', {}).get('country')}

"""
        
        prompt = f"""E-commerce checkout. Observe, decide ONE action.

GOAL: {goal}

{customer_info}URL: {observation['url']}
Page Type: {observation.get('pageType', 'unknown')}
Blocking Overlay: {observation.get('hasBlockingOverlay', False)}

Buttons: {self._format_buttons(observation['buttons'])}
Inputs: {self._format_inputs(observation['inputs'])}
Errors: {observation['errors'] or 'None'}

Last actions:
{history_text or 'None'}

TOOLS:
- click_button(text) - Click button
- dismiss_modal() - Dismiss side modal/drawer if blocking
- use_checkout_flow(action) - Fill forms using rule-based system
  Actions: fill_contact (email+name), fill_shipping (address), select_shipping
  ONLY use if you see matching input fields
- fill_field(field_identifier, value) - Fill single field
- wait(seconds)

RULES:
1. If Blocking Overlay=True → dismiss_modal first
2. If checkout button clicked but URL unchanged → dismiss_modal then click again
3. If you see email/name inputs → use_checkout_flow(fill_contact)
4. If you see address/city inputs → use_checkout_flow(fill_shipping)
5. If last action FAILED, retry or try different approach

JSON: {{"reasoning": "...", "action": "tool", "params": {{}}}}
"""
        
        response = await self.llm.complete(prompt, max_tokens=150)
        return response
    
    def _format_buttons(self, buttons):
        return ", ".join([f"'{b['text'] or b['ariaLabel']}'"
            for b in buttons if b['text'] or b['ariaLabel']]) or "None"
    
    def _format_inputs(self, inputs):
        return ", ".join([f"{i['type']}[name={i['name'] or i['id']}]"
            for i in inputs if i['name'] or i['id']]) or "None"
    
    async def execute_action(self, action_decision, customer_data):
        """Execute the decided action"""
        action = action_decision.get('action')
        params = action_decision.get('params', {})
        
        logger.info(f"REACTIVE AGENT: Executing {action} with params {params}")
        
        try:
            if action == 'click_button':
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
            elif action == 'dismiss_modal':
                return await self._dismiss_modal()
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
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    async def _dismiss_modal(self):
        """Dismiss side modal/drawer"""
        try:
            dismissed = await self.page.evaluate("""
                () => {
                    const selectors = ['button[aria-label*="close" i]', 'button[aria-label*="dismiss" i]', '[class*="close" i][role="button"]', '[class*="modal" i] button[class*="close" i]', '[class*="drawer" i] button[class*="close" i]', '.modal-backdrop', '.drawer-overlay'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.offsetParent) { el.click(); return true; }
                    }
                    return false;
                }
            """)
            await asyncio.sleep(1)
            return {'success': dismissed, 'message': 'Modal dismissed' if dismissed else 'No modal found'}
        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    async def _use_checkout_flow(self, action, customer_data):
        """Use rule-based checkout functions with validation"""
        from phase2.checkout_flow import fill_contact_info, fill_shipping_address, select_cheapest_shipping
        
        # Validate form fields exist before calling rule-based system
        if action == 'fill_contact':
            has_fields = await self.page.evaluate("""
                () => {
                    const inputs = Array.from(document.querySelectorAll('input, textarea, select'))
                        .filter(el => el.offsetParent && el.type !== 'hidden');
                    const hasEmail = inputs.some(el => 
                        el.type === 'email' || 
                        el.name?.toLowerCase().includes('email') ||
                        el.id?.toLowerCase().includes('email') ||
                        el.placeholder?.toLowerCase().includes('email')
                    );
                    const hasName = inputs.some(el => 
                        el.name?.toLowerCase().includes('name') ||
                        el.id?.toLowerCase().includes('name') ||
                        el.placeholder?.toLowerCase().includes('name')
                    );
                    return hasEmail || hasName;
                }
            """)
            if not has_fields:
                return {'success': False, 'message': 'Contact form not loaded yet'}
            result = await fill_contact_info(self.page, customer_data.get('contact', {}))
            
        elif action == 'fill_shipping':
            has_fields = await self.page.evaluate("""
                () => {
                    const inputs = Array.from(document.querySelectorAll('input, textarea, select'))
                        .filter(el => el.offsetParent && el.type !== 'hidden');
                    const hasAddress = inputs.some(el => 
                        el.name?.toLowerCase().includes('address') ||
                        el.id?.toLowerCase().includes('address') ||
                        el.placeholder?.toLowerCase().includes('address')
                    );
                    const hasCity = inputs.some(el => 
                        el.name?.toLowerCase().includes('city') ||
                        el.id?.toLowerCase().includes('city') ||
                        el.placeholder?.toLowerCase().includes('city')
                    );
                    return hasAddress || hasCity;
                }
            """)
            if not has_fields:
                return {'success': False, 'message': 'Shipping form not loaded yet'}
            result = await fill_shipping_address(self.page, customer_data.get('shippingAddress', {}))
            
        elif action == 'select_shipping':
            result = await select_cheapest_shipping(self.page)
        else:
            return {'success': False, 'message': f'Unknown checkout action: {action}'}
        
        if not result.get('success'):
            result['message'] = f"Rule-based {action} failed. Try individual fields."
        
        return result
    
    async def _click_button(self, text):
        """Click button by text and wait for URL change if checkout button"""
        from phase2.checkout_dom_finder import find_and_click_button
        
        url_before = self.page.url
        result = await find_and_click_button(self.page, [text.lower()], max_retries=1)
        
        if result.get('success'):
            # If checkout/continue button, wait for URL change
            if any(kw in text.lower() for kw in ['checkout', 'continue', 'proceed', 'next']):
                try:
                    await self.page.wait_for_url(lambda url: url != url_before, timeout=3000)
                    await asyncio.sleep(1)
                    return {'success': True, 'message': f'Clicked {text}, URL changed'}
                except:
                    return {'success': False, 'message': f'Clicked {text} but URL did not change. Try dismiss_modal.'}
            else:
                await asyncio.sleep(1)
        
        return result
    
    async def _fill_field(self, field_identifier, value):
        """Fill input field by name, id, or placeholder"""
        try:
            filled = await self.page.evaluate(f"""
                (identifier, val) => {{
                    const input = document.querySelector(`input[name="${{identifier}}"]`) ||
                                  document.querySelector(`input[id="${{identifier}}"]`) ||
                                  document.querySelector(`input[placeholder*="${{identifier}}"]`) ||
                                  document.querySelector(`textarea[name="${{identifier}}"]`) ||
                                  document.querySelector(`textarea[id="${{identifier}}"]`);
                    if (input) {{
                        input.value = val;
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                }}
            """, field_identifier, value)
            await asyncio.sleep(0.5)
            return {'success': filled, 'message': f'Filled {field_identifier}' if filled else f'Field {field_identifier} not found'}
        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    async def _select_dropdown(self, field_identifier, value):
        """Select dropdown option by name or id"""
        try:
            selected = await self.page.evaluate(f"""
                (identifier, val) => {{
                    const select = document.querySelector(`select[name="${{identifier}}"]`) ||
                                   document.querySelector(`select[id="${{identifier}}"]`);
                    if (select) {{
                        const option = Array.from(select.options).find(opt => 
                            opt.text.toLowerCase().includes(val.toLowerCase()) ||
                            opt.value.toLowerCase().includes(val.toLowerCase())
                        );
                        if (option) {{
                            select.value = option.value;
                            select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            return true;
                        }}
                    }}
                    return false;
                }}
            """, field_identifier, value)
            await asyncio.sleep(0.5)
            return {'success': selected, 'message': f'Selected {value} in {field_identifier}' if selected else f'Dropdown {field_identifier} not found'}
        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}
    

    async def run(self, goal, customer_data):
        """Main reactive loop: observe → reason → act → repeat"""
        logger.info(f"REACTIVE AGENT: Starting with goal: {goal}")
        
        for iteration in range(self.max_iterations):
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"REACTIVE AGENT: Iteration {iteration + 1}/{self.max_iterations}")
                logger.info(f"{'='*60}")
                
                # 1. Observe
                observation = await self.observe_page()
                logger.info(f"REACTIVE AGENT: Observed page - URL: {observation['url'][:80]}")
                logger.info(f"REACTIVE AGENT: Found {len(observation['buttons'])} buttons, {len(observation['inputs'])} inputs")
                if observation['buttons']:
                    logger.info(f"REACTIVE AGENT: Buttons: {[b['text'] or b['ariaLabel'] for b in observation['buttons']]}")
                if observation['inputs']:
                    logger.info(f"REACTIVE AGENT: Inputs: {[f"{i['type']}[{i['name'] or i['id']}]" for i in observation['inputs']]}")
                if observation['errors']:
                    logger.info(f"REACTIVE AGENT: Errors: {observation['errors']}")
                
                # Check if goal achieved by URL
                if 'payment' in observation['url'].lower() or 'billing' in observation['url'].lower():
                    logger.info(f"REACTIVE AGENT: Goal achieved - reached payment page")
                    return {'success': True, 'iterations': iteration + 1}
                
                # 2. Reason and Decide
                decision = await self.reason_and_decide(goal, customer_data, observation, iteration == 0)
                logger.info(f"REACTIVE AGENT: Reasoning: {decision.get('reasoning', 'N/A')[:200]}")
                logger.info(f"REACTIVE AGENT: Decision: {decision.get('action')} with params {decision.get('params', {})}")
                
                # Check if goal achieved
                if decision.get('goal_achieved'):
                    logger.info(f"REACTIVE AGENT: Goal achieved!")
                    return {'success': True, 'iterations': iteration + 1}
                
                # 3. Act
                result = await self.execute_action(decision, customer_data)
                logger.info(f"REACTIVE AGENT: Action result: SUCCESS={result.get('success')}, {result.get('message', result)}")
                
                # 4. Record in history
                self.conversation_history.append({
                    'iteration': iteration + 1,
                    'observation': observation,
                    'reasoning': decision.get('reasoning'),
                    'action': decision.get('action'),
                    'params': decision.get('params'),
                    'result': result
                })
                
                # Check if goal achieved from action result
                if result.get('goal_achieved'):
                    logger.info(f"REACTIVE AGENT: Goal achieved!")
                    return {'success': True, 'iterations': iteration + 1}
                
                # Small delay between iterations
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"REACTIVE AGENT: Iteration error: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(2)
                continue
        
        logger.warning(f"REACTIVE AGENT: Max iterations reached without achieving goal")
        return {'success': False, 'error': 'Max iterations reached', 'iterations': self.max_iterations}
