"""
Payment Automation Service
Connects user wallet → payment form automation → order capture
Handles iframes, shadow DOMs, and order confirmation
"""

from typing import Optional, Dict
import asyncio
import re
from datetime import datetime

from ..db import db
from ..legacy.phase2.checkout_dom_finder import detect_stripe_iframe, interact_with_stripe_iframe
from ..utils.logger_config import log
import logging

logger = logging.getLogger(__name__)

class PaymentAutomationService:
    
    @staticmethod
    async def fill_payment_from_wallet(page, user_id: int, payment_method_id: Optional[int] = None) -> Dict:
        """
        Automatically fill payment details from user's saved payment methods
        
        Args:
            page: Playwright page object
            user_id: ID of the user
            payment_method_id: Specific payment method ID, or None for default
            
        Returns:
            {'success': bool, 'method_used': str, 'error': str}
        """
        try:
            # 1. Get payment method from wallet
            if payment_method_id:
                payment = db.fetch_one(
                    "SELECT * FROM payment_methods WHERE id = ? AND user_id = ?",
                    (payment_method_id, user_id)
                )
            else:
                # Use default payment method
                payment = db.fetch_one(
                    "SELECT * FROM payment_methods WHERE user_id = ? AND is_default = 1 LIMIT 1",
                    (user_id,)
                )
            
            if not payment:
                return {'success': False, 'error': 'No payment method found in wallet'}
            
            log(logger, 'info', f"Using payment method: {payment['label']} ({payment['payment_type']})", 'PAYMENT', 'AUTO')
            
            # 2. Route to appropriate handler based on payment type
            if payment['payment_type'] == 'card':
                result = await PaymentAutomationService._fill_card_details(page, payment)
            elif payment['payment_type'] == 'upi':
                result = await PaymentAutomationService._fill_upi_details(page, payment)
            elif payment['payment_type'] == 'paypal':
                result = await PaymentAutomationService._fill_paypal_details(page, payment)
            else:
                return {'success': False, 'error': f"Unsupported payment type: {payment['payment_type']}"}
            
            # Update last_used_at
            if result.get('success'):
                db.execute_update(
                    "UPDATE payment_methods SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (payment['id'],)
                )
            
            return {**result, 'method_used': payment['label']}
            
        except Exception as e:
            log(logger, 'error', f"Payment automation failed: {e}", 'PAYMENT', 'AUTO')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def _fill_card_details(page, payment: dict) -> Dict:
        """Fill credit/debit card details (handles iframes)"""
        try:
            log(logger, 'info', "Detecting payment form type...", 'PAYMENT', 'CARD')
            
            # Check if Stripe iframe is present
            card_iframe = await detect_stripe_iframe(page, ['card number', 'cardnumber', 'number'])
            
            if card_iframe.get('is_stripe'):
                # === STRIPE IFRAME HANDLING ===
                log(logger, 'info', "Detected Stripe Elements iframe", 'PAYMENT', 'STRIPE')
                
                # Fill card number
                result = await interact_with_stripe_iframe(
                    page, 
                    ['card number', 'cardnumber', 'number'],
                    payment['card_number']
                )
                if not result['success']:
                    return result
                
                await asyncio.sleep(0.3)
                
                # Fill expiry (format: MM/YY)
                expiry = f"{payment['card_expiry_month']:02d}/{str(payment['card_expiry_year'])[-2:]}"
                result = await interact_with_stripe_iframe(
                    page,
                    ['expiry', 'expiration', 'exp'],
                    expiry
                )
                if not result['success']:
                    return result
                
                await asyncio.sleep(0.3)
                
                # Fill CVV
                result = await interact_with_stripe_iframe(
                    page,
                    ['cvc', 'cvv', 'security', 'code'],
                    payment['card_cvv']
                )
                
                log(logger, 'info', "Stripe card details filled successfully", 'PAYMENT', 'STRIPE')
                return {'success': True, 'method': 'stripe_iframe'}
                
            else:
                # === REGULAR FORM HANDLING ===
                log(logger, 'info', "Using regular form field detection", 'PAYMENT', 'CARD')
                
                # Try common card number selectors
                card_selectors = [
                    'input[name*="card"][name*="number"]',
                    'input[placeholder*="card number"]',
                    'input[autocomplete="cc-number"]',
                    'input[id*="cardnumber"]',
                    '#card-number',
                    '.card-number'
                ]
                
                card_filled = False
                for selector in card_selectors:
                    try:
                        element = await page.wait_for_selector(selector, timeout=2000)
                        if element:
                            await element.fill(payment['card_number'])
                            card_filled = True
                            log(logger, 'info', f"Card number filled using: {selector}", 'PAYMENT', 'CARD')
                            break
                    except:
                        continue
                
                if not card_filled:
                    return {'success': False, 'error': 'Could not find card number field'}
                
                # Fill expiry
                expiry_selectors = [
                    'input[name*="expiry"]',
                    'input[placeholder*="MM"]',
                    'input[autocomplete="cc-exp"]'
                ]
                expiry = f"{payment['card_expiry_month']:02d}/{str(payment['card_expiry_year'])[-2:]}"
                for selector in expiry_selectors:
                    try:
                        element = await page.wait_for_selector(selector, timeout=2000)
                        if element:
                            await element.fill(expiry)
                            break
                    except:
                        continue
                
                # Fill CVV
                cvv_selectors = [
                    'input[name*="cvv"]',
                    'input[name*="cvc"]',
                    'input[placeholder*="CVV"]',
                    'input[autocomplete="cc-csc"]'
                ]
                for selector in cvv_selectors:
                    try:
                        element = await page.wait_for_selector(selector, timeout=2000)
                        if element:
                            await element.fill(payment['card_cvv'])
                            break
                    except:
                        continue
                
                log(logger, 'info', "Card details filled successfully (regular form)", 'PAYMENT', 'CARD')
                return {'success': True, 'method': 'regular_form'}
                
        except Exception as e:
            log(logger, 'error', f"Card filling failed: {e}", 'PAYMENT', 'CARD')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def _fill_upi_details(page, payment: dict) -> Dict:
        """Fill UPI ID (India-specific)"""
        try:
            log(logger, 'info', f"Filling UPI ID: {payment['upi_id']}", 'PAYMENT', 'UPI')
            
            # UPI field selectors
            upi_selectors = [
                'input[name*="upi"]',
                'input[placeholder*="UPI"]',
                'input[placeholder*="upi"]',
                'input[id*="upi"]',
                '#upi-id',
                '.upi-input'
            ]
            
            for selector in upi_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        await element.fill(payment['upi_id'])
                        log(logger, 'info', f"UPI ID filled using: {selector}", 'PAYMENT', 'UPI')
                        return {'success': True, 'method': 'upi'}
                except:
                    continue
            
            return {'success': False, 'error': 'Could not find UPI input field'}
            
        except Exception as e:
            log(logger, 'error', f"UPI filling failed: {e}", 'PAYMENT', 'UPI')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def _fill_paypal_details(page, payment: dict) -> Dict:
        """Handle PayPal (usually a redirect/modal)"""
        log(logger, 'info', "PayPal selected (modal handling required)", 'PAYMENT', 'PAYPAL')
        # PayPal typically opens a modal or redirects
        # This requires special handling - click PayPal button and wait for modal
        return {'success': False, 'error': 'PayPal automation not yet implemented'}
    
    @staticmethod
    async def submit_payment(page) -> Dict:
        """
        Click the payment/place order button
        Returns: {'success': bool, 'order_url': str, 'order_number': str}
        """
        try:
            log(logger, 'info', "Looking for payment submit button...", 'PAYMENT', 'SUBMIT')
            
            # Common submit button text patterns
            submit_patterns = [
                'place order',
                'complete purchase',
                'pay now',
                'confirm order',
                'submit payment',
                'buy now',
                'confirm purchase',
                'complete order'
            ]
            
            # Try to find and click submit button
            for pattern in submit_patterns:
                try:
                    # Use Playwright's text selector
                    button = await page.wait_for_selector(
                        f'button:has-text("{pattern}")',
                        timeout=2000,
                        state='visible'
                    )
                    if button:
                        await button.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                        await button.click()
                        log(logger, 'info', f"Clicked: {pattern}", 'PAYMENT', 'SUBMIT')
                        
                        # Wait for navigation or confirmation
                        await page.wait_for_load_state('networkidle', timeout=10000)
                        
                        # Capture order details
                        return await PaymentAutomationService.capture_order_confirmation(page)
                        
                except:
                    continue
            
            return {'success': False, 'error': 'Could not find payment submit button'}
            
        except Exception as e:
            log(logger, 'error', f"Payment submission failed: {e}", 'PAYMENT', 'SUBMIT')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def capture_order_confirmation(page) -> Dict:
        """
        Capture order number and confirmation details after successful payment
        """
        try:
            current_url = page.url
            log(logger, 'info', f"Capturing order confirmation from: {current_url}", 'ORDER', 'CONFIRM')
            
            # Wait a bit for confirmation page to load
            await asyncio.sleep(2)
            
            # Extract order number using multiple strategies
            order_number = await page.evaluate("""
                () => {
                    // Strategy 1: Look for order number in text
                    const bodyText = document.body.innerText;
                    
                    // Patterns for order number
                    const patterns = [
                        /order\\s*#?\\s*([A-Z0-9-]+)/i,
                        /order\\s*number\\s*:?\\s*([A-Z0-9-]+)/i,
                        /confirmation\\s*#?\\s*([A-Z0-9-]+)/i,
                        /order\\s*id\\s*:?\\s*([A-Z0-9-]+)/i
                    ];
                    
                    for (const pattern of patterns) {
                        const match = bodyText.match(pattern);
                        if (match && match[1]) {
                            return match[1];
                        }
                    }
                    
                    // Strategy 2: Look for elements with order-related classes/IDs
                    const orderElements = document.querySelectorAll(
                        '[class*="order-number"], [id*="order-number"], [class*="confirmation"]'
                    );
                    
                    for (const el of orderElements) {
                        const text = el.textContent.trim();
                        if (text.length > 5 && text.length < 30) {
                            return text;
                        }
                    }
                    
                    return null;
                }
            """)
            
            # Check if we're on a confirmation page
            is_confirmation = 'thank' in current_url.lower() or \
                             'success' in current_url.lower() or \
                             'confirmation' in current_url.lower() or \
                             'order' in current_url.lower()
            
            if order_number:
                log(logger, 'info', f"Order confirmed! Order #: {order_number}", 'ORDER', 'CONFIRM')
                return {
                    'success': True,
                    'order_number': order_number,
                    'order_url': current_url,
                    'confirmed': True
                }
            elif is_confirmation:
                log(logger, 'info', "On confirmation page but couldn't extract order number", 'ORDER', 'CONFIRM')
                return {
                    'success': True,
                    'order_number': None,
                    'order_url': current_url,
                    'confirmed': True
                }
            else:
                return {
                    'success': False,
                    'error': 'Not on order confirmation page',
                    'current_url': current_url
                }
                
        except Exception as e:
            log(logger, 'error', f"Order capture failed: {e}", 'ORDER', 'CONFIRM')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def save_order_to_history(user_id: int, order_data: dict, checkout_json: dict) -> int:
        """
        Save completed order to user's purchase history
        
        Args:
            user_id: User ID
            order_data: Result from capture_order_confirmation
            checkout_json: Original checkout JSON data
            
        Returns:
            order_id: ID of saved order
        """
        try:
            import json
            
            # Extract task info
            task = checkout_json.get('tasks', [{}])[0]
            site_domain = task.get('url', '').split('/')[2] if task.get('url') else 'unknown'
            
            # TODO: In future, extract actual price from confirmation page
            # For now, we don't have price info without scraping
            total_amount = 0.0
            currency = checkout_json.get('currency', 'USD')
            
            # Save to database
            order_id = db.execute_insert("""
                INSERT INTO orders (
                    user_id, order_number, site_domain, order_url,
                    total_amount, currency, status, payment_status,
                    automation_data, ordered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                user_id,
                order_data.get('order_number'),
                site_domain,
                order_data.get('order_url'),
                total_amount,
                currency,
                'completed',
                'paid',
                json.dumps(checkout_json)
            ))
            
            log(logger, 'info', f"Order saved to history: ID={order_id}", 'ORDER', 'SAVE')
            return order_id
            
        except Exception as e:
            log(logger, 'error', f"Failed to save order: {e}", 'ORDER', 'SAVE')
            return None
