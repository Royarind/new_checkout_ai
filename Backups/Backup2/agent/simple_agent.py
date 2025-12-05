"""
Simple Agent - Single agent to assist rule-based checkout flow
Helps overcome obstacles and execute failed steps
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

AGENT_PROMPT = """ROLE: AI Coordinator - Support rule-based checkout automation

PRIMARY: Rule-based system handles checkout flow
FALLBACK: You assist ONLY when rule-based fails at a specific stage

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHECKOUT FLOW (Rule-based handles this)

1. Cart → 2. Checkout Button → 3. Guest/Login → 4. Contact Info → 
5. Shipping Address → 6. Shipping Method → 7. Payment → 8. Place Order

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT SITUATION

Stage: {stage}
Rule-based failed: {rule_result}
Customer: {customer_data}

Page state:
- Buttons: {buttons}
- Fields: {fields}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK

Rule-based system tried {stage} but failed. Help it progress by:
1. Analyzing what's visible on the page
2. Identifying the obstacle (hidden element, different text, etc.)
3. Providing ONE action to overcome the obstacle

STAGE REQUIREMENTS:
• proceed_to_checkout → Find and click checkout/proceed button to reach checkout page
• guest_checkout → Click guest checkout option (or skip if already on guest form)
• fill_contact → Fill email, firstName, lastName fields with customer data
• fill_shipping → Fill address, city, state/province, postalCode fields

CONTEXT:
Rule-based uses keyword matching. It may fail if:
- Button text is unusual ("Continue" instead of "Checkout")
- Fields have non-standard names ("mail" instead of "email")
- Elements are in modals, dropdowns, or hidden sections
- Page requires interaction before fields appear

RULES:
1. Use EXACT text/names from page state above
2. ONE action only - let rule-based continue after
3. Skip if stage is already complete
4. Be specific with target names

RESPONSE (JSON only):
{{
  "action": "click|fill|skip",
  "target": "exact button text or field name",
  "value": "data to fill (fill action only)",
  "reasoning": "why this overcomes the obstacle"
}}

EXAMPLES:
{{"action": "click", "target": "Continue to Checkout", "reasoning": "Checkout button has different text"}}
{{"action": "fill", "target": "email", "value": "{{{{email}}}}", "reasoning": "Email field visible"}}
{{"action": "skip", "reasoning": "Already on checkout page, no button needed"}}

Focus: Unblock {stage} so rule-based can continue the flow.
"""


class SimpleAgent:
    def __init__(self, page, llm_client):
        self.page = page
        self.llm = llm_client
    
    async def assist_stage(self, stage, customer_data, rule_result):
        """
        Assist with a failed checkout stage
        Returns: {'success': bool, 'action_taken': str}
        """
        logger.info(f"AGENT: Assisting with stage: {stage}")
        
        try:
            # Capture page state
            page_state = await self._capture_page_state()
            
            # Build prompt
            prompt = AGENT_PROMPT.format(
                stage=stage,
                rule_result=rule_result.get('error', 'Unknown error'),
                customer_data=self._format_customer_data(customer_data, stage),
                buttons=page_state['buttons'][:10],
                fields=page_state['fields'][:10]
            )
            
            # Get LLM response
            logger.info(f"AGENT: Requesting LLM assistance...")
            response = await self.llm.complete(prompt)
            
            if not response:
                logger.error(f"AGENT: No response from LLM")
                return {'success': False, 'error': 'No LLM response'}
            
            logger.info(f"AGENT: LLM analysis: {response.get('analysis', 'N/A')}")
            logger.info(f"AGENT: LLM action: {response.get('action', 'N/A')}")
            
            # Execute action
            action = response.get('action', '').lower()
            
            if action == 'skip':
                logger.info(f"AGENT: Skipping stage - {response.get('reasoning')}")
                return {'success': True, 'action_taken': 'skipped'}
            
            elif action == 'click':
                target = response.get('target', '')
                logger.info(f"AGENT: Clicking: {target}")
                success = await self._click_element(target)
                return {'success': success, 'action_taken': f'clicked {target}'}
            
            elif action == 'fill':
                target = response.get('target', '')
                value = response.get('value', '')
                # Replace placeholders
                value = self._replace_placeholders(value, customer_data)
                logger.info(f"AGENT: Filling {target} with value")
                success = await self._fill_field(target, value)
                return {'success': success, 'action_taken': f'filled {target}'}
            
            else:
                logger.warning(f"AGENT: Unknown action: {action}")
                return {'success': False, 'error': f'Unknown action: {action}'}
        
        except Exception as e:
            logger.error(f"AGENT: Error assisting stage: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    async def _capture_page_state(self):
        """Capture current page state"""
        state = await self.page.evaluate("""
            () => {
                // Get visible buttons
                const buttons = Array.from(document.querySelectorAll('button, a, input[type="submit"]'))
                    .filter(el => el.offsetParent)
                    .map(el => el.textContent?.trim() || el.value || '')
                    .filter(text => text.length > 0 && text.length < 50)
                    .slice(0, 15);
                
                // Get visible form fields
                const fields = Array.from(document.querySelectorAll('input:not([type="hidden"]), select, textarea'))
                    .filter(el => el.offsetParent)
                    .map(el => ({
                        name: el.name || el.id || '',
                        placeholder: el.placeholder || '',
                        label: (el.closest('label') || document.querySelector(`label[for="${el.id}"]`))?.textContent?.trim() || ''
                    }))
                    .filter(f => f.name || f.placeholder || f.label)
                    .slice(0, 15);
                
                return { buttons, fields };
            }
        """)
        return state
    
    def _format_customer_data(self, customer_data, stage):
        """Format customer data relevant to stage"""
        if stage in ['fill_contact']:
            contact = customer_data.get('contact', {})
            return f"Email: {contact.get('email')}, Name: {contact.get('firstName')} {contact.get('lastName')}"
        elif stage in ['fill_shipping']:
            addr = customer_data.get('shippingAddress', {})
            return f"Address: {addr.get('addressLine1')}, City: {addr.get('city')}, State: {addr.get('province')}, Zip: {addr.get('postalCode')}"
        return "N/A"
    
    def _replace_placeholders(self, value, customer_data):
        """Replace {{placeholder}} with actual data"""
        if '{{email}}' in value:
            value = customer_data.get('contact', {}).get('email', '')
        elif '{{firstName}}' in value:
            value = customer_data.get('contact', {}).get('firstName', '')
        elif '{{lastName}}' in value:
            value = customer_data.get('contact', {}).get('lastName', '')
        elif '{{address}}' in value:
            value = customer_data.get('shippingAddress', {}).get('addressLine1', '')
        elif '{{city}}' in value:
            value = customer_data.get('shippingAddress', {}).get('city', '')
        elif '{{state}}' in value:
            value = customer_data.get('shippingAddress', {}).get('province', '')
        elif '{{zip}}' in value:
            value = customer_data.get('shippingAddress', {}).get('postalCode', '')
        return value
    
    async def _click_element(self, target_text):
        """Click element by text"""
        try:
            result = await self.page.evaluate("""
                (targetText) => {
                    const elements = document.querySelectorAll('button, a, input[type="submit"]');
                    for (const el of elements) {
                        const text = (el.textContent || el.value || '').toLowerCase();
                        if (text.includes(targetText.toLowerCase())) {
                            el.scrollIntoView({ block: 'center' });
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }
            """, target_text)
            
            if result:
                await asyncio.sleep(2)
                return True
            return False
        except Exception as e:
            logger.error(f"AGENT: Click error: {e}")
            return False
    
    async def _fill_field(self, field_name, value):
        """Fill form field"""
        try:
            result = await self.page.evaluate("""
                (args) => {
                    const { fieldName, value } = args;
                    const inputs = document.querySelectorAll('input:not([type="hidden"]), select, textarea');
                    
                    for (const input of inputs) {
                        if (!input.offsetParent) continue;
                        
                        const name = (input.name || '').toLowerCase();
                        const id = (input.id || '').toLowerCase();
                        const placeholder = (input.placeholder || '').toLowerCase();
                        const label = (input.closest('label')?.textContent || '').toLowerCase();
                        
                        const allText = name + id + placeholder + label;
                        
                        if (allText.includes(fieldName.toLowerCase())) {
                            input.scrollIntoView({ block: 'center' });
                            input.focus();
                            input.value = value;
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            return true;
                        }
                    }
                    return false;
                }
            """, {'fieldName': field_name, 'value': value})
            
            if result:
                await asyncio.sleep(1)
                return True
            return False
        except Exception as e:
            logger.error(f"AGENT: Fill error: {e}")
            return False
