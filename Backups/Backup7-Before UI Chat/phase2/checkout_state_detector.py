"""
Checkout State Detector
Detects current page state and available fields to enable adaptive flow
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def wait_for_network_idle(page, timeout=3):
    """
    Wait for network to be idle (no pending requests)
    """
    import asyncio
    try:
        await page.wait_for_load_state('networkidle', timeout=timeout * 1000)
        logger.info("STATE: Network idle detected")
    except Exception:
        logger.info("STATE: Network idle timeout, continuing anyway")
        await asyncio.sleep(1)


async def detect_page_state(page):
    """
    Detect current checkout page state
    Returns: {
        'page_type': 'cart'|'checkout'|'login'|'payment',
        'fields_visible': {'email': bool, 'firstName': bool, ...},
        'buttons_visible': {'checkout': bool, 'continue': bool, ...}
    }
    """
    state = await page.evaluate("""
        () => {
            // Detect page type from URL and title
            const url = window.location.href.toLowerCase();
            const title = document.title.toLowerCase();
            let pageType = 'unknown';
            
            if (url.includes('/cart') || title.includes('cart') || title.includes('bag')) {
                pageType = 'cart';
            } else if (url.includes('/checkout') || title.includes('checkout')) {
                pageType = 'checkout';
            } else if (url.includes('/login') || title.includes('login') || title.includes('sign in')) {
                pageType = 'login';
            } else if (url.includes('/payment') || title.includes('payment')) {
                pageType = 'payment';
            }
            
            // Detect visible fields
            const fields = {};
            const fieldPatterns = {
                email: ['email', 'e-mail', 'mail'],
                firstName: ['firstname', 'first name', 'first_name', 'fname', 'givenname'],
                lastName: ['lastname', 'last name', 'last_name', 'lname', 'surname'],
                phone: ['phone', 'telephone', 'mobile', 'tel'],
                address: ['address', 'street', 'addr'],
                city: ['city', 'town'],
                state: ['state', 'province', 'region'],
                zip: ['zip', 'postal', 'postcode']
            };
            
            for (const [fieldName, patterns] of Object.entries(fieldPatterns)) {
                fields[fieldName] = false;
                const inputs = document.querySelectorAll('input:not([type="hidden"]), select, textarea');
                
                for (const input of inputs) {
                    if (!input.offsetParent) continue;
                    
                    const name = (input.name || '').toLowerCase();
                    const id = (input.id || '').toLowerCase();
                    const placeholder = (input.placeholder || '').toLowerCase();
                    const label = input.closest('label')?.textContent?.toLowerCase() || '';
                    const ariaLabel = (input.getAttribute('aria-label') || '').toLowerCase();
                    
                    const allText = name + id + placeholder + label + ariaLabel;
                    
                    if (patterns.some(p => allText.includes(p))) {
                        fields[fieldName] = true;
                        break;
                    }
                }
            }
            
            // Detect visible buttons
            const buttons = {};
            const buttonPatterns = {
                checkout: ['checkout', 'check out', 'proceed to checkout'],
                viewCart: ['view cart', 'go to cart', 'view bag'],
                guestCheckout: ['guest', 'continue as guest', 'checkout as guest'],
                continue: ['continue', 'next', 'proceed'],
                placeOrder: ['place order', 'complete', 'pay now']
            };
            
            for (const [buttonName, patterns] of Object.entries(buttonPatterns)) {
                buttons[buttonName] = false;
                const elements = document.querySelectorAll('button, a, input[type="submit"], input[type="button"]');
                
                for (const el of elements) {
                    if (!el.offsetParent) continue;
                    
                    const text = (el.textContent || el.value || '').toLowerCase();
                    const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
                    
                    if (patterns.some(p => text.includes(p) || ariaLabel.includes(p))) {
                        buttons[buttonName] = true;
                        break;
                    }
                }
            }
            
            return {
                pageType: pageType,
                fieldsVisible: fields,
                buttonsVisible: buttons
            };
        }
    """)
    
    logger.info(f"STATE: Page type: {state['pageType']}")
    logger.info(f"STATE: Fields visible: {[k for k, v in state['fieldsVisible'].items() if v]}")
    logger.info(f"STATE: Buttons visible: {[k for k, v in state['buttonsVisible'].items() if v]}")
    
    return state


async def detect_field_visibility(page, field_keywords, max_wait=5):
    """
    Check if specific field is visible on page with retry logic
    Returns: bool
    """
    import asyncio
    
    # Try immediate detection first
    result = await page.evaluate("""
        (keywords) => {
            const inputs = document.querySelectorAll('input:not([type="hidden"]), select, textarea');
            
            for (const input of inputs) {
                if (!input.offsetParent) continue;
                
                const name = (input.name || '').toLowerCase();
                const id = (input.id || '').toLowerCase();
                const placeholder = (input.placeholder || '').toLowerCase();
                const label = input.closest('label')?.textContent?.toLowerCase() || '';
                
                const allText = name + id + placeholder + label;
                
                if (keywords.some(k => allText.includes(k.toLowerCase()))) {
                    return true;
                }
            }
            return false;
        }
    """, field_keywords)
    
    if result:
        return True
    
    # Retry with progressive delays for lazy-loaded content
    logger.info(f"STATE: Field not found immediately, waiting for dynamic content...")
    for attempt in range(3):
        await asyncio.sleep(max_wait / 3)
        result = await page.evaluate("""
            (keywords) => {
                const inputs = document.querySelectorAll('input:not([type="hidden"]), select, textarea');
                for (const input of inputs) {
                    if (!input.offsetParent) continue;
                    const name = (input.name || '').toLowerCase();
                    const id = (input.id || '').toLowerCase();
                    const placeholder = (input.placeholder || '').toLowerCase();
                    const label = input.closest('label')?.textContent?.toLowerCase() || '';
                    const allText = name + id + placeholder + label;
                    if (keywords.some(k => allText.includes(k.toLowerCase()))) {
                        return true;
                    }
                }
                return false;
            }
        """, field_keywords)
        if result:
            logger.info(f"STATE: Field found after {attempt + 1} retries")
            return True
    
    return False


async def detect_validation_errors(page):
    """
    Detect form validation errors on page
    Returns: {'has_errors': bool, 'error_messages': [str]}
    """
    result = await page.evaluate("""
        () => {
            const errorSelectors = [
                '[class*="error"]:not([style*="display: none"])',
                '[class*="invalid"]:not([style*="display: none"])',
                '[role="alert"]',
                '.error-message',
                '.field-error',
                '[aria-invalid="true"]',
                'input:invalid',
                'select:invalid'
            ];
            
            const errors = [];
            for (const selector of errorSelectors) {
                const elements = document.querySelectorAll(selector);
                for (const el of elements) {
                    if (el.offsetParent && el.textContent?.trim()) {
                        errors.push(el.textContent.trim().substring(0, 100));
                    }
                }
            }
            
            return {
                hasErrors: errors.length > 0,
                errorMessages: [...new Set(errors)].slice(0, 5)
            };
        }
    """)
    
    if result['hasErrors']:
        logger.warning(f"VALIDATION: Errors detected: {result['errorMessages']}")
    
    return result


async def get_field_dependencies(page):
    """
    Detect field dependencies (e.g., country must be filled before state)
    Returns: {'dependencies': {field: [depends_on]}}
    """
    result = await page.evaluate("""
        () => {
            const dependencies = {};
            
            // Check if state/province field is disabled
            const stateFields = document.querySelectorAll('select[name*="state"], select[name*="province"], select[id*="state"], select[id*="province"]');
            for (const field of stateFields) {
                if (field.disabled || field.options.length <= 1) {
                    dependencies['state'] = ['country'];
                    break;
                }
            }
            
            // Check for fields with data-depends or similar attributes
            const allFields = document.querySelectorAll('input, select, textarea');
            for (const field of allFields) {
                const depends = field.getAttribute('data-depends') || field.getAttribute('depends-on');
                if (depends) {
                    const fieldName = field.name || field.id;
                    dependencies[fieldName] = [depends];
                }
            }
            
            return { dependencies };
        }
    """)
    
    if result['dependencies']:
        logger.info(f"DEPENDENCIES: Detected field dependencies: {result['dependencies']}")
    
    return result['dependencies']
