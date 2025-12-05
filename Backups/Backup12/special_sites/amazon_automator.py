#!/usr/bin/env python3
"""
Amazon-specific automation handler
Handles variant selection for amazon.com, amazon.in, and all Amazon domains
"""

import asyncio
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def select_amazon_variant(page: Page, variant_type: str, variant_value: str):
    """
    Select variant on Amazon product pages
    Handles: Color, Size, Style variations
    """
    logger.info(f"AMAZON: Selecting {variant_type}={variant_value}")
    
    try:
        # Wait for product details to load
        await asyncio.sleep(1)
        
        # Normalize for matching
        normalized_value = variant_value.lower().strip()
        
        # Amazon uses specific patterns for variants
        if variant_type.lower() in ['color', 'colour', 'style']:
            # Find the input element by finding image with matching alt text
            try:
                # Get all images and find the one with matching alt
                images = await page.query_selector_all('img[alt]')
                
                for img in images:
                    alt_text = await img.get_attribute('alt')
                    if alt_text and variant_value.lower() in alt_text.lower():
                        logger.info(f"AMAZON: Found image with alt='{alt_text}'")
                        
                        # Find the parent input element
                        input_elem = await img.evaluate_handle(
                            'el => el.closest("li") || el.closest("span.a-button-inner") || el.parentElement'
                        )
                        
                        if input_elem:
                            # Scroll into view and click
                            await input_elem.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            await input_elem.click()
                            await asyncio.sleep(1)
                            logger.info(f"AMAZON: Clicked color swatch for {variant_value}")
                            return {'success': True}
                
                logger.warning(f"AMAZON: No image found with alt containing '{variant_value}'")
                return {'success': False}
                
            except Exception as e:
                logger.error(f"AMAZON: Error clicking color swatch: {e}")
                return {'success': False}
        
        elif variant_type.lower() in ['size']:
            # Strategy 1: Native select dropdown
            select_clicked = await page.evaluate("""
                (targetValue) => {
                    const normalize = (text) => text ? text.toLowerCase().trim() : '';
                    const target = normalize(targetValue);
                    
                    // Find size dropdown
                    const sizeSelect = document.querySelector('select[name="size"], select#native_dropdown_selected_size_name');
                    if (sizeSelect) {
                        for (const option of sizeSelect.options) {
                            const optionText = normalize(option.text);
                            if (optionText.includes(target) || target.includes(optionText)) {
                                sizeSelect.value = option.value;
                                sizeSelect.dispatchEvent(new Event('change', {bubbles: true}));
                                return true;
                            }
                        }
                    }
                    return false;
                }
            """, variant_value)
            
            if select_clicked:
                await asyncio.sleep(1)
                logger.info(f"AMAZON: Size selected from dropdown")
                return {'success': True}
            
            # Strategy 2: Size buttons
            button_clicked = await page.evaluate("""
                (targetValue) => {
                    const normalize = (text) => text ? text.toLowerCase().trim() : '';
                    const target = normalize(targetValue);
                    
                    // Find size buttons
                    const sizeButtons = document.querySelectorAll(
                        'button[class*="size"], ' +
                        'li[class*="size"], ' +
                        '[id*="size_name"]'
                    );
                    
                    for (const btn of sizeButtons) {
                        const text = normalize(btn.textContent);
                        const value = normalize(btn.value || btn.getAttribute('data-value'));
                        
                        if (text.includes(target) || value.includes(target) || 
                            target.includes(text) || target.includes(value)) {
                            btn.scrollIntoView({block: 'center'});
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """, variant_value)
            
            if button_clicked:
                await asyncio.sleep(1)
                logger.info(f"AMAZON: Size button clicked")
                return {'success': True}
        
        logger.warning(f"AMAZON: Unsupported variant type: {variant_type}")
        return {'success': False}
        
    except Exception as e:
        logger.error(f"AMAZON: Error selecting variant: {e}")
        return {'success': False}


async def _dismiss_amazon_modal(page: Page):
    """Dismiss protection/warranty modals after Buy Now"""
    try:
        await asyncio.sleep(1.5)
        
        # First try: Click outside modal area (left side) to dismiss
        try:
            await page.mouse.click(50, 300)
            await asyncio.sleep(0.5)
            logger.info("AMAZON: Clicked outside modal area")
        except:
            pass
        
        dismissed = await page.evaluate("""
            () => {
                // Find modal/overlay containers
                const modals = document.querySelectorAll('[role="dialog"], [class*="modal"], [class*="overlay"], [id*="modal"]');
                
                for (const modal of modals) {
                    if (modal.offsetParent !== null) {
                        // Look for decline/no thanks buttons inside modal
                        const buttons = modal.querySelectorAll('button, input[type="button"], [role="button"], a');
                        for (const btn of buttons) {
                            const text = (btn.textContent || btn.value || btn.getAttribute('aria-label') || '').toLowerCase().trim();
                            if (text.includes('no thanks') || text.includes('decline') || 
                                text.includes('skip') || text.includes('no, thanks') ||
                                text.includes('continue without') || text.includes('not now')) {
                                btn.click();
                                return true;
                            }
                        }
                    }
                }
                return false;
            }
        """)
        
        if dismissed:
            logger.info("AMAZON: Dismissed protection modal")
            await asyncio.sleep(0.5)
        else:
            logger.debug("AMAZON: No modal found to dismiss")
    except Exception as e:
        logger.debug(f"AMAZON: Modal dismissal error: {e}")


async def handle_amazon_login(page: Page, email: str, password: str):
    """Handle Amazon login flow: email -> Continue -> password"""
    logger.info("AMAZON: Starting login flow")
    
    try:
        # Step 1: Fill email
        email_filled = await page.evaluate(
            """(email) => {
                const emailInput = document.querySelector('#ap_email, input[type="email"], input[name="email"]');
                if (emailInput) {
                    emailInput.value = email;
                    emailInput.dispatchEvent(new Event('input', { bubbles: true }));
                    emailInput.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }
                return false;
            }""",
            email
        )
        
        if not email_filled:
            logger.error("AMAZON: Email field not found")
            return {'success': False, 'error': 'Email field not found'}
        
        logger.info("AMAZON: Email filled")
        await asyncio.sleep(1)
        
        # Step 2: Click Continue button
        continue_clicked = await page.evaluate(
            """() => {
                const continueBtn = document.querySelector('#continue, input[id="continue"], button:has-text("Continue")');
                if (continueBtn) {
                    continueBtn.click();
                    return true;
                }
                return false;
            }"""
        )
        
        if not continue_clicked:
            logger.error("AMAZON: Continue button not found")
            return {'success': False, 'error': 'Continue button not found'}
        
        logger.info("AMAZON: Continue clicked, waiting for password field...")
        await asyncio.sleep(2)
        
        # Step 3: Fill password
        password_filled = await page.evaluate(
            """(password) => {
                const passwordInput = document.querySelector('#ap_password, input[type="password"], input[name="password"]');
                if (passwordInput) {
                    passwordInput.value = password;
                    passwordInput.dispatchEvent(new Event('input', { bubbles: true }));
                    passwordInput.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }
                return false;
            }""",
            password
        )
        
        if not password_filled:
            logger.error("AMAZON: Password field not found")
            return {'success': False, 'error': 'Password field not found'}
        
        logger.info("AMAZON: Password filled")
        await asyncio.sleep(1)
        
        # Step 4: Click Sign In button
        signin_clicked = await page.evaluate(
            """() => {
                const signinBtn = document.querySelector('#signInSubmit, input[id="signInSubmit"], button:has-text("Sign in")');
                if (signinBtn) {
                    signinBtn.click();
                    return true;
                }
                return false;
            }"""
        )
        
        if not signin_clicked:
            logger.error("AMAZON: Sign In button not found")
            return {'success': False, 'error': 'Sign In button not found'}
        
        logger.info("AMAZON: Sign In clicked")
        await asyncio.sleep(3)
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"AMAZON: Login error - {e}")
        return {'success': False, 'error': str(e)}


async def add_amazon_to_cart(page: Page):
    """Click Add to Cart on Amazon"""
    logger.info("AMAZON: Clicking Add to Cart")
    
    try:
        # Click Add to Cart button
        clicked = await page.evaluate("""
            () => {
                const addToCartButtons = [
                    document.querySelector('#add-to-cart-button'),
                    document.querySelector('input[name="submit.add-to-cart"]'),
                    document.querySelector('[id*="add-to-cart"]'),
                    document.querySelector('#addToCart')
                ];
                
                for (const btn of addToCartButtons) {
                    if (btn && btn.offsetParent !== null) {
                        btn.scrollIntoView({block: 'center'});
                        btn.click();
                        return true;
                    }
                }
                return false;
            }
        """)
        
        if clicked:
            await asyncio.sleep(2)
            logger.info("AMAZON: Add to Cart clicked")
            
            # Dismiss protection/warranty modal if it appears
            await _dismiss_amazon_modal(page)
            
            return {'success': True}
        
        return {'success': False}
        
    except Exception as e:
        logger.error(f"AMAZON: Error clicking Add to Cart: {e}")
        return {'success': False}
