"""
Executor Agent - Executes action plans
Translates high-level actions into browser operations
"""

import asyncio
import logging
from datetime import datetime
from phase2.checkout_dom_finder import find_and_click_button, fill_input_field, find_and_select_dropdown
from shared.popup_dismisser import dismiss_popups

logger = logging.getLogger(__name__)


# ============= EXECUTION GUIDANCE PROMPT =============

EXECUTION_GUIDANCE_PROMPT = """
ROLE: You are an execution agent analyzing why an action failed and suggesting alternatives.

FAILED ACTION:
Action: {action}
Parameters: {params}
Failure Reason: {failure_reason}

CURRENT PAGE CONTEXT:
{page_context}

AVAILABLE ALTERNATIVE ACTIONS:
- press_key(key): Try different key
- click_element(selector, method): Try different selector or method (css/text/xpath)
- fill_field(field_type, value): Try different field identification
- select_dropdown(field_type, value): Try different dropdown approach
- scroll(direction): Scroll to reveal hidden elements
- wait(seconds): Wait for dynamic content

INSTRUCTIONS:
1. Analyze the present page context to understand the next steps
2. Mandatorily carry out the action as per the plan and click/fill/select the intended element
3. If timing issue, suggest wait + retry
4. If element hidden, suggest scroll + retry
5. Mandatory: If the action is resolved then call rule-based method to carry out the next action in the plan

EXAMPLES:
1. If the page is showing a Checkout button but the click failed, try scrolling to it first and then click it.
2. If the input field is not found, try filling it using a different attribute like name or id.
3. If the dropdown options are not loading, wait for a few seconds and retry selection.
4. If the checkout button is not clickable, suggest waiting for the page to stabilize and then retrying the click.


If no viable alternative exists, return:
{{
  "reasoning": "Explanation of why recovery is not possible",
  "root_cause": "unrecoverable",
  "alternative_action": null
}}
"""


class ExecutorAgent:
    def __init__(self, page, llm_client=None):
        self.page = page
        self.llm = llm_client
        self.action_map = self._build_action_map()
        self.last_action = None
        self.execution_history = []
    
    def _build_action_map(self):
        """Map action names to execution functions"""
        return {
            'press_key': self._press_key,
            'click_element': self._click_element,
            'fill_field': self._fill_field,
            'select_dropdown': self._select_dropdown,
            'select_shipping': self._select_shipping,
            'wait': self._wait,
            'scroll': self._scroll,
            'take_screenshot': self._take_screenshot,
            'retry_last_action': self._retry_last_action
        }
    
    async def execute_plan(self, plan, customer_data=None):
        """
        Execute action plan from Planner Agent
        Returns: {'success': bool, 'results': list, 'error': str}
        """
        logger.info(f"EXECUTOR: [{datetime.now().strftime('%H:%M:%S')}] Executing plan with {len(plan['actions'])} actions")
        
        results = []
        for i, action in enumerate(plan['actions']):
            logger.info(f"EXECUTOR: [{datetime.now().strftime('%H:%M:%S')}] Action {i+1}/{len(plan['actions'])}: {action['action']}")
            
            try:
                # Get execution function
                executor = self.action_map.get(action['action'])
                if not executor:
                    logger.error(f"EXECUTOR: Unknown action: {action['action']}")
                    results.append({'action': action['action'], 'success': False, 'error': 'Unknown action'})
                    continue
                
                # Replace placeholders with customer data
                params = self._inject_customer_data(action['params'], customer_data)
                
                # Filter params to only include valid ones for the executor
                params = self._filter_valid_params(executor, params)
                
                # Execute action
                result = await executor(**params)
                self.last_action = {'action': action, 'result': result}
                
                # If action fails and LLM available, try intelligent retry
                if not result.get('success', True) and self.llm:
                    logger.warning(f"EXECUTOR: Action failed, attempting intelligent retry...")
                    retry_result = await self._intelligent_retry(action, params, result)
                    if retry_result.get('success'):
                        result = retry_result
                        logger.info(f"EXECUTOR: Intelligent retry succeeded")
                
                results.append({'action': action['action'], 'success': result.get('success', True), 'result': result})
                
                # Track execution history
                self.execution_history.append({
                    'action': action,
                    'params': params,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"EXECUTOR: Action execution error: {e}")
                results.append({'action': action['action'], 'success': False, 'error': str(e)})
        
        success_count = sum(1 for r in results if r['success'])
        overall_success = success_count >= len(results) * 0.7  # 70% success threshold
        
        logger.info(f"EXECUTOR: [{datetime.now().strftime('%H:%M:%S')}] Plan execution complete: {success_count}/{len(results)} successful")
        
        return {
            'success': overall_success,
            'results': results,
            'success_rate': success_count / len(results) if results else 0
        }
    
    def _filter_valid_params(self, executor_func, params):
        """Filter params to only include valid parameters for the function"""
        import inspect
        sig = inspect.signature(executor_func)
        valid_params = {}
        
        for key, value in params.items():
            if key in sig.parameters:
                valid_params[key] = value
            else:
                logger.warning(f"EXECUTOR: Ignoring invalid parameter '{key}' for {executor_func.__name__}")
        
        return valid_params
    
    def _inject_customer_data(self, params, customer_data):
        """Replace {{placeholder}} with actual customer data"""
        if not customer_data:
            return params
        
        injected = {}
        for key, value in params.items():
            if isinstance(value, str) and '{{' in value:
                # Extract placeholder name
                placeholder = value.strip('{}')
                
                # Look in contact data
                if placeholder in ['email', 'firstName', 'lastName', 'phone']:
                    injected[key] = customer_data.get('contact', {}).get(placeholder, value)
                # Look in shipping address
                elif placeholder in ['addressLine1', 'addressLine2', 'city', 'province', 'postalCode', 'country']:
                    injected[key] = customer_data.get('shippingAddress', {}).get(placeholder, value)
                else:
                    injected[key] = value
            else:
                injected[key] = value
        
        return injected
    
    # ============= ACTION EXECUTORS =============
    
    async def _press_key(self, key):
        """Press keyboard key"""
        await self.page.keyboard.press(key)
        await asyncio.sleep(0.3)
        return {'success': True}
    
    async def _click_element(self, selector, method='text'):
        """Click element by selector or text with LLM fallback"""
        if method == 'text':
            result = await find_and_click_button(self.page, [selector])
            return result
        elif method == 'css':
            try:
                await self.page.click(selector, timeout=5000)
                return {'success': True}
            except Exception as e:
                return {'success': False, 'error': str(e)}
        elif method == 'xpath':
            try:
                element = await self.page.wait_for_selector(f'xpath={selector}', timeout=5000)
                await element.click()
                return {'success': True}
            except Exception as e:
                return {'success': False, 'error': str(e)}
        elif method == 'llm_guided' and self.llm:
            # LLM analyzes screenshot and suggests exact element to click
            return await self._llm_guided_click(selector)
        
        return {'success': False, 'error': 'Invalid method'}
    
    async def _llm_guided_click(self, target_description):
        """Use LLM to identify and click element from screenshot"""
        screenshot = await self.page.screenshot()
        
        prompt = f"""
Analyze this checkout page screenshot and identify the exact element to click.

TARGET: {target_description}

Provide the best CSS selector or XPath to click this element.

OUTPUT (JSON):
{{
  "selector": "button.checkout-btn",
  "method": "css",
  "confidence": 0.9,
  "reasoning": "Why this selector"
}}
"""
        
        try:
            response = await self.llm.complete(prompt, image=screenshot)
            selector_info = response
            
            # Try the suggested selector
            if selector_info['method'] == 'css':
                await self.page.click(selector_info['selector'], timeout=5000)
            else:
                element = await self.page.wait_for_selector(f"xpath={selector_info['selector']}", timeout=5000)
                await element.click()
            
            return {'success': True, 'selector': selector_info['selector']}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _llm_guided_click(self, target_description):
        """Use LLM to identify and click element from DOM context with bounding boxes"""
        # Extract all visible buttons and links with bounding box and details
        buttons = await self.page.evaluate('''() => {
            function getBoundingBox(el) {
                const rect = el.getBoundingClientRect();
                return {
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height
                };
            }
            return Array.from(document.querySelectorAll('button, a, input[type="submit"]'))
                .filter(el => el.offsetParent)
                .map(el => ({
                    text: el.textContent?.trim() || el.value || '',
                    selector: el.tagName.toLowerCase() + (el.id ? `#${el.id}` : '') + (el.className ? `.${el.className.split(' ').join('.')}` : ''),
                    boundingBox: getBoundingBox(el),
                    type: el.tagName.toLowerCase(),
                    name: el.getAttribute('name') || '',
                    id: el.id || '',
                    classes: el.className || ''
                }));
        }''')

        prompt = f"""
    You are automating a checkout page. Here are all visible clickable elements (buttons, links, submit inputs) with their text, selector, and bounding box:
    {buttons}
    TARGET: {target_description}
    Provide the best selector (css/text/xpath) to click this element. If not found, suggest the closest alternative.
    OUTPUT (JSON):
    {{
    "selector": "button.checkout-btn",
    "method": "css" or "text" or "xpath",
    "confidence": 0.9,
    "reasoning": "Why this selector"
    }}
    """
        try:
            response = await self.llm.complete(prompt)
            selector_info = response
            # Try the suggested selector
            if selector_info['method'] == 'css':
                await self.page.click(selector_info['selector'], timeout=5000)
                return {'success': True, 'selector': selector_info['selector']}
            elif selector_info['method'] == 'xpath':
                element = await self.page.wait_for_selector(f"xpath={selector_info['selector']}", timeout=5000)
                await element.click()
                return {'success': True, 'selector': selector_info['selector']}
            elif selector_info['method'] == 'text':
                result = await find_and_click_button(self.page, [selector_info['selector']])
                if result.get('success'):
                    return {'success': True, 'selector': selector_info['selector']}
                else:
                    return {'success': False, 'error': 'Text selector failed'}
            else:
                return {'success': False, 'error': 'Unknown selector method'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _fill_field(self, field_type, value):
        """Fill form field by type with LLM fallback"""
        label_map = {
            'email': ['email', 'e-mail'],
            'firstName': ['first name', 'firstname', 'given name'],
            'lastName': ['last name', 'lastname', 'surname', 'family name'],
            'phone': ['phone', 'telephone', 'mobile'],
            'fullName': ['name', 'full name', 'your name'],
            'addressLine1': ['address', 'street', 'address line 1'],
            'addressLine2': ['address line 2', 'apartment', 'suite', 'unit'],
            'city': ['city', 'town'],
            'postalCode': ['postal code', 'zip code', 'postcode', 'zip']
        }
        
        labels = label_map.get(field_type, [field_type])
        result = await fill_input_field(self.page, labels, value)
        
        # If rule-based fails and LLM available, try LLM-guided field detection
        if not result.get('success') and self.llm:
            logger.info(f"EXECUTOR: Rule-based field detection failed, trying LLM guidance for {field_type}")
            result = await self._llm_guided_fill(field_type, value)
        
        return result
    
    async def _llm_guided_fill(self, field_type, value):
        """Use LLM to identify form field from DOM context only"""
        inputs = await self.page.evaluate("""
            () => Array.from(document.querySelectorAll('input, select, textarea'))
                .filter(el => el.offsetParent && el.type !== 'hidden')
                .map(el => ({
                    placeholder: el.placeholder,
                    name: el.name,
                    id: el.id,
                    label: el.labels && el.labels.length > 0 ? el.labels[0].textContent : null
                }))
        """)
        prompt = f"""
            You are automating a checkout form. The visible inputs are: {inputs}
            TARGET FIELD: {field_type}
            Provide the best CSS selector, name, or id to fill this field. If not found, suggest the closest alternative.
            OUTPUT (JSON):
            {{
            "selector": "input#email" or "input[name='email']",
            "method": "css" or "name" or "id",
            "confidence": 0.9,
            "reasoning": "Why this selector"
            }}
            """
        try:
            response = await self.llm.complete(prompt)
            selector_info = response
            if selector_info['method'] == 'css':
                try:
                    await self.page.fill(selector_info['selector'], value)
                    return {'success': True, 'selector': selector_info['selector']}
                except Exception as e:
                    try:
                        if selector_info['method'] == 'name':
                            await self.page.fill(f"input[name='{selector_info['selector']}']", value)
                            return {'success': True, 'selector': selector_info['selector']}
                        elif selector_info['method'] == 'id':
                            await self.page.fill(f"#{selector_info['selector']}", value)
                            return {'success': True, 'selector': selector_info['selector']}
                    except Exception:
                        pass
                    return {'success': False, 'error': str(e)}
            elif selector_info['method'] == 'name':
                await self.page.fill(f"input[name='{selector_info['selector']}']", value)
                return {'success': True, 'selector': selector_info['selector']}
            elif selector_info['method'] == 'id':
                await self.page.fill(f"#{selector_info['selector']}", value)
                return {'success': True, 'selector': selector_info['selector']}
            else:
                return {'success': False, 'error': 'Unknown selector method'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _llm_guided_fill(self, field_type, value):
        """Use LLM to identify form field from DOM context only"""
        # Gather all visible input placeholders and labels
        inputs = await self.page.evaluate("""
            () => Array.from(document.querySelectorAll('input, select, textarea'))
                .filter(el => el.offsetParent && el.type !== 'hidden')
                .map(el => ({
                    placeholder: el.placeholder,
                    name: el.name,
                    id: el.id,
                    label: el.labels && el.labels.length > 0 ? el.labels[0].textContent : null
                }))
        """)
        prompt = f"""
You are automating a checkout form. The visible inputs are: {inputs}
TARGET FIELD: {field_type}
Provide the best CSS selector, name, or id to fill this field. If not found, suggest the closest alternative.
OUTPUT (JSON):
{{
    "selector": "input#email" or "input[name='email']",
    "method": "css" or "name" or "id",
    "confidence": 0.9,
    "reasoning": "Why this selector"
}}
"""
        try:
            response = await self.llm.complete(prompt)
            selector_info = response
            if selector_info['method'] == 'css':
                try:
                    await self.page.fill(selector_info['selector'], value)
                    return {'success': True, 'selector': selector_info['selector']}
                except Exception as e:
                    # Try by name or id if CSS fails
                    try:
                        if selector_info['method'] == 'name':
                            await self.page.fill(f"input[name='{selector_info['selector']}']", value)
                            return {'success': True, 'selector': selector_info['selector']}
                        elif selector_info['method'] == 'id':
                            await self.page.fill(f"#{selector_info['selector']}", value)
                            return {'success': True, 'selector': selector_info['selector']}
                    except Exception:
                        pass
                    return {'success': False, 'error': str(e)}
            elif selector_info['method'] == 'name':
                await self.page.fill(f"input[name='{selector_info['selector']}']", value)
                return {'success': True, 'selector': selector_info['selector']}
            elif selector_info['method'] == 'id':
                await self.page.fill(f"#{selector_info['selector']}", value)
                return {'success': True, 'selector': selector_info['selector']}
            else:
                return {'success': False, 'error': 'Unknown selector method'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _select_dropdown(self, field_type, value):
        """Select dropdown option"""
        label_map = {
            'province': ['state', 'province', 'region'],
            'country': ['country']
        }
        
        labels = label_map.get(field_type, [field_type])
        result = await find_and_select_dropdown(self.page, labels, value)
        return result
    
    async def _select_shipping(self, strategy='cheapest'):
        """Select shipping method"""
        if strategy == 'cheapest':
            # Use existing cheapest shipping selector
            try:
                result = await self.page.evaluate("""
                    () => {
                        const options = [];
                        const radios = document.querySelectorAll('input[type="radio"]');
                        
                        radios.forEach(radio => {
                            const label = radio.closest('label') || document.querySelector(`label[for="${radio.id}"]`);
                            const container = radio.closest('div, li, tr, fieldset');
                            const text = (label?.textContent || container?.textContent || '').toLowerCase();
                            
                            if (text.includes('ship') || text.includes('delivery')) {
                                const priceMatches = text.match(/\\$\\s*([0-9]+\\.?[0-9]*)|([0-9]+\\.?[0-9]*)\\s*\\$/g);
                                let price = 999999;
                                
                                if (priceMatches && priceMatches.length > 0) {
                                    const priceStr = priceMatches[0].replace(/[^0-9.]/g, '');
                                    price = parseFloat(priceStr) || 0;
                                } else if (text.includes('free')) {
                                    price = 0;
                                }
                                
                                options.push({ element: radio, price: price });
                            }
                        });
                        
                        if (options.length === 0) return { found: false };
                        
                        options.sort((a, b) => a.price - b.price);
                        const cheapest = options[0];
                        cheapest.element.checked = true;
                        cheapest.element.click();
                        cheapest.element.dispatchEvent(new Event('change', { bubbles: true }));
                        
                        return { found: true, price: cheapest.price };
                    }
                """)
                
                return {'success': result.get('found', False)}
            except Exception as e:
                return {'success': False, 'error': str(e)}
        
        return {'success': False, 'error': 'Unknown strategy'}
    
    async def _wait(self, seconds):
        """Wait for specified time"""
        await asyncio.sleep(seconds)
        return {'success': True}
    
    async def _scroll(self, direction='down'):
        """Scroll page"""
        try:
            if direction == 'down':
                await self.page.evaluate('window.scrollBy(0, 500)')
            elif direction == 'up':
                await self.page.evaluate('window.scrollBy(0, -500)')
            await asyncio.sleep(0.5)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _take_screenshot(self):
        """Take screenshot of current page"""
        try:
            screenshot = await self.page.screenshot()
            return {'success': True, 'screenshot': screenshot}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _retry_last_action(self):
        """Retry last action with LLM guidance"""
        if not self.last_action or not self.llm:
            return {'success': False, 'error': 'No previous action or LLM unavailable'}
        
        logger.info("EXECUTOR: Retrying last action with LLM guidance")
        return await self._intelligent_retry(
            self.last_action['action'],
            self.last_action['action']['params'],
            self.last_action['result']
        )
    
    async def _intelligent_retry(self, action, params, failure_result):
        """Use LLM to adapt and retry failed action"""
        if not self.llm:
            return {'success': False, 'error': 'LLM not available'}
        
        # Capture current page state
        screenshot = await self.page.screenshot()
        page_html = await self.page.evaluate('document.body.innerHTML')
        
        # Build execution guidance prompt
        prompt = EXECUTION_GUIDANCE_PROMPT.format(
            action=action['action'],
            params=params,
            failure_reason=failure_result.get('error', 'Unknown'),
            page_context=page_html[:2000]  # First 2000 chars
        )
        
        try:
            response = await self.llm.complete(prompt, image=screenshot)
            
            # Parse LLM suggestion
            suggestion = self._parse_execution_suggestion(response)
            
            if suggestion.get('alternative_action'):
                # Try alternative approach
                alt_action = suggestion['alternative_action']
                executor = self.action_map.get(alt_action['action'])
                if executor:
                    return await executor(**alt_action['params'])
            
            return {'success': False, 'error': 'No viable alternative found'}
            
        except Exception as e:
            logger.error(f"EXECUTOR: Intelligent retry failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _parse_execution_suggestion(self, llm_response):
        """Parse LLM execution suggestion"""
        return {
            'alternative_action': llm_response.get('alternative_action'),
            'reasoning': llm_response.get('reasoning', ''),
            'root_cause': llm_response.get('root_cause', 'unknown')
        }
    
    def get_execution_history(self):
        """Get execution history for debugging"""
        return self.execution_history
