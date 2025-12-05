"""
Planner Agent - Strategizes checkout flow
Analyzes page state and creates action plans
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PlannerAgent:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.stage_prompts = self._load_stage_prompts()
    
    def _load_stage_prompts(self):
        return {
            'dismiss_popups': DISMISS_POPUPS_PROMPT,
            'proceed_to_checkout': PROCEED_TO_CHECKOUT_PROMPT,
            'guest_checkout': GUEST_CHECKOUT_PROMPT,
            'fill_contact': FILL_CONTACT_PROMPT,
            'fill_shipping': FILL_SHIPPING_PROMPT,
            'select_shipping_method': SELECT_SHIPPING_PROMPT,
            'recovery': RECOVERY_PROMPT
        }
    
    async def plan_action(self, stage, page_state, failure_context=None):
        """
        Create action plan for current stage
        Returns: {'actions': [list], 'reasoning': str, 'confidence': float}
        """
        logger.info(f"PLANNER: [{datetime.now().strftime('%H:%M:%S')}] Planning for stage: {stage}")
        
        prompt = self._build_prompt(stage, page_state, failure_context)
        response = await self.llm.complete(prompt, image=page_state.get('screenshot'))
        plan = self._parse_plan(response)
        
        logger.info(f"PLANNER: [{datetime.now().strftime('%H:%M:%S')}] Plan created with {len(plan['actions'])} actions")
        return plan
    
    def _build_prompt(self, stage, page_state, failure_context):
        base_prompt = self.stage_prompts.get(stage, RECOVERY_PROMPT)
        
        context = f"""
PAGE STATE:
- URL: {page_state['url']}
- Visible Buttons: {page_state['visible_buttons'][:5]}
- Visible Forms: {page_state['visible_forms'][:3]}
- Modals Present: {page_state['modals_present']}
- Current Step: {page_state['current_step']}
"""
        
        if failure_context:
            context += f"\nPREVIOUS FAILURES:\n{failure_context}"
        
        return base_prompt.format(context=context)
    
    def _parse_plan(self, llm_response):
        """Parse LLM response into structured action plan"""
        return {
            'actions': llm_response.get('actions', []),
            'reasoning': llm_response.get('reasoning', ''),
            'confidence': llm_response.get('confidence', 0.5)
        }


# ============= STAGE-WISE PROMPTS =============

DISMISS_POPUPS_PROMPT = """
ROLE: You are a checkout automation planner analyzing an e-commerce page.

STAGE: Dismiss Pop-ups and Modals

GOAL: Identify and plan actions to dismiss cookie banners, promotional pop-ups, and blocking modals.

{context}

AVAILABLE ACTIONS:
- press_key(key): Press keyboard key (e.g., 'Escape')
- click_element(selector, method): Click element by CSS selector or text
- wait(seconds): Wait for specified time

INSTRUCTIONS:
1. Analyze the screenshot for visible modals, overlays, cookie banners
2. Identify close buttons (X, ×, "Accept", "Close", "Dismiss")
3. Create a sequence of actions to clear all blocking elements
4. Prioritize Escape key first, then targeted clicks

OUTPUT FORMAT (JSON):
{{
  "reasoning": "Brief explanation of what you see and why these actions",
  "confidence": 0.0-1.0,
  "actions": [
    {{"action": "press_key", "params": {{"key": "Escape"}}}},
    {{"action": "click_element", "params": {{"selector": "button.cookie-accept", "method": "css"}}}}
  ]
}}
"""

PROCEED_TO_CHECKOUT_PROMPT = """
ROLE: You are a checkout automation planner analyzing an e-commerce cart page.

STAGE: Proceed to Checkout

GOAL: Navigate from cart page to checkout page by clicking the checkout button.

{context}

AVAILABLE ACTIONS:
- click_element(selector, method): Click element (method: 'css', 'text', 'xpath')
- press_key(key): Press keyboard key
- wait(seconds): Wait for page transition

WORKFLOW CONTEXT:
1. May need to dismiss "View Cart" modal first
2. May need to click mini cart icon on top right corner nto open cart drawer
3. Then click checkout button inside drawer or on page

INSTRUCTIONS:
1. Analyze screenshot for cart state (modal, drawer, or full page)
2. Identify checkout button location and text
3. Plan sequence: dismiss modal → open cart (if needed) → click checkout
4. Look for keywords: "checkout", "proceed", "continue to checkout"

OUTPUT FORMAT (JSON):
{{
  "reasoning": "Explain cart state and checkout button location",
  "confidence": 0.0-1.0,
  "actions": [
    {{"action": "press_key", "params": {{"key": "Escape"}}}},
    {{"action": "click_element", "params": {{"selector": "Checkout", "method": "text"}}}},
    {{"action": "wait", "params": {{"seconds": 2}}}}
  ]
}}
"""

GUEST_CHECKOUT_PROMPT = """
ROLE: You are a checkout automation planner analyzing a checkout login page.

STAGE: Guest Checkout Selection

GOAL: Select guest checkout option (avoid login/registration).

{context}

AVAILABLE ACTIONS:
- click_element(selector, method): Click element
- wait(seconds): Wait for form to appear

INSTRUCTIONS:
1. Look for guest checkout button/link
2. Common text: "Guest Checkout", "Continue as Guest", "Checkout without account"
3. If no guest option visible, assume already on guest form
4. Plan single click action or skip if not needed

OUTPUT FORMAT (JSON):
{{
  "reasoning": "Guest checkout button location or why skipping",
  "confidence": 0.0-1.0,
  "actions": [
    {{"action": "click_element", "params": {{"selector": "Continue as Guest", "method": "text"}}}}
  ]
}}
"""

FILL_CONTACT_PROMPT = """
ROLE: You are a checkout automation planner analyzing a contact information form.

STAGE: Fill Contact Information

GOAL: Identify and plan filling email, name, and phone fields.

{context}

CUSTOMER DATA AVAILABLE:
- email
- firstName
- lastName
- phone

AVAILABLE ACTIONS:
- fill_field(field_type, value): Fill form field (field_type: 'email', 'firstName', 'lastName', 'phone', 'fullName')
- wait(seconds): Wait between fields

INSTRUCTIONS:
1. Identify visible form fields in screenshot
2. Determine if name is split (first/last) or combined (full name)
3. Plan field filling order: email first (may trigger form expansion), then name, then phone
4. Mark optional fields (phone usually optional)

OUTPUT FORMAT (JSON):
{{
  "reasoning": "Form structure and field identification",
  "confidence": 0.0-1.0,
  "actions": [
    {{"action": "fill_field", "params": {{"field_type": "email", "value": "{{email}}"}}}},
    {{"action": "fill_field", "params": {{"field_type": "firstName", "value": "{{firstName}}"}}}},
    {{"action": "fill_field", "params": {{"field_type": "lastName", "value": "{{lastName}}"}}}}
  ]
}}
"""

FILL_SHIPPING_PROMPT = """
ROLE: You are a checkout automation planner analyzing a shipping address form.

STAGE: Fill Shipping Address

GOAL: Identify and plan filling address, city, state, postal code fields.

{context}

ADDRESS DATA AVAILABLE:
- addressLine1
- addressLine2 (optional)
- city
- province/state
- postalCode
- country

AVAILABLE ACTIONS:
- fill_field(field_type, value): Fill text field
- select_dropdown(field_type, value): Select from dropdown (for state/country)
- wait(seconds): Wait between fields

INSTRUCTIONS:
1. Identify all address fields in screenshot
2. Note which fields are dropdowns (state, country) vs text inputs
3. Plan filling order: address → city → state → postal code
4. Country may be pre-selected or need selection first

OUTPUT FORMAT (JSON):
{{
  "reasoning": "Address form structure and field types",
  "confidence": 0.0-1.0,
  "actions": [
    {{"action": "fill_field", "params": {{"field_type": "addressLine1", "value": "{{addressLine1}}"}}}},
    {{"action": "fill_field", "params": {{"field_type": "city", "value": "{{city}}"}}}},
    {{"action": "select_dropdown", "params": {{"field_type": "province", "value": "{{province}}"}}}},
    {{"action": "fill_field", "params": {{"field_type": "postalCode", "value": "{{postalCode}}"}}}}
  ]
}}
"""

SELECT_SHIPPING_PROMPT = """
ROLE: You are a checkout automation planner analyzing shipping method options.

STAGE: Select Shipping Method

GOAL: Identify and select the cheapest shipping option.

{context}

AVAILABLE ACTIONS:
- select_shipping(strategy): Select shipping (strategy: 'cheapest', 'fastest', 'specific')
- click_element(selector, method): Click specific radio button
- wait(seconds): Wait for selection to register

INSTRUCTIONS:
1. Identify shipping options with prices in screenshot
2. Determine cheapest option
3. Plan selection action
4. If no options visible, assume auto-selected

OUTPUT FORMAT (JSON):
{{
  "reasoning": "Shipping options identified and cheapest choice",
  "confidence": 0.0-1.0,
  "actions": [
    {{"action": "select_shipping", "params": {{"strategy": "cheapest"}}}}
  ]
}}
"""

RECOVERY_PROMPT = """
ROLE: You are a checkout automation recovery planner analyzing a stuck/failed state.

STAGE: Recovery from Failure

GOAL: Diagnose issue and suggest recovery actions.

{context}

AVAILABLE ACTIONS:
- click_element(selector, method): Click any element
- fill_field(field_type, value): Fill any field
- press_key(key): Press key
- scroll(direction): Scroll page
- wait(seconds): Wait
- take_screenshot(): Capture current state
- retry_last_action(): Retry previous action with different approach

INSTRUCTIONS:
1. Analyze what went wrong from failure context
2. Look for error messages, validation issues, or UI changes
3. Suggest alternative approach or recovery steps
4. If truly stuck, recommend human intervention

OUTPUT FORMAT (JSON):
{{
  "reasoning": "Diagnosis of failure and recovery strategy",
  "confidence": 0.0-1.0,
  "actions": [
    {{"action": "scroll", "params": {{"direction": "down"}}}},
    {{"action": "take_screenshot", "params": {{}}}},
    {{"action": "retry_last_action", "params": {{}}}}
  ],
  "requires_human": false
}}
"""
