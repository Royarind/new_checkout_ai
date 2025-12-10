"""
Smart Login Handler for Indian E-commerce Sites
Handles adaptive login flow: mobile/email detection, password, T&C, etc.
"""
import asyncio
import logging
from playwright.async_api import Page
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SmartLoginHandler:
    """Handles intelligent login flow with field detection"""
    
    def __init__(self, page: Page):
        self.page = page
    
    async def login(self, email: str, phone: str, password: str) -> Dict[str, Any]:
        """
        Smart login that adapts to page content
        
        Args:
            email: Email address
            phone: Phone number (10 digits for India)
            password: Password
            
        Returns:
            Dict with success status and method used
        """
        logger.info("🔐 Starting smart login flow...")
        
        # Step 1: Detect what type of field is present
        field_type = await self._detect_login_field_type()
        
        if not field_type:
            logger.error("❌ No login field detected")
            return {'success': False, 'error': 'No login field found'}
        
        logger.info(f"   Detected field type: {field_type}")
        
        # Step 2: Fill the appropriate field
        if field_type == 'mobile':
            fill_success = await self._fill_mobile_field(phone)
        elif field_type == 'email':
            fill_success = await self._fill_email_field(email)
        elif field_type == 'both':
            # Try email/mobile combo field
            fill_success = await self._fill_combo_field(email, phone)
        else:
            logger.error(f"Unknown field type: {field_type}")
            return {'success': False, 'error': f'Unknown field type: {field_type}'}
        
        if not fill_success:
            logger.error("❌ Failed to fill login field")
            return {'success': False, 'error': 'Failed to fill login field'}
        
        logger.info("   ✅ Login field filled")
        
        # Step 3: Check for password field
        has_password = await self._detect_password_field()
        
        if has_password:
            logger.info("   Password field detected")
            password_filled = await self._fill_password_field(password)
            if not password_filled:
                logger.warning("   ⚠️ Failed to fill password")
        else:
            logger.info("   No password field (likely OTP flow)")
        
        # Step 4: Handle T&C checkboxes
        await self._handle_terms_and_conditions()
        
        # Step 5: Click Continue/Next button
        continue_clicked = await self._click_continue_button()
        
        if not continue_clicked:
            logger.error("❌ Failed to click continue button")
            return {'success': False, 'error': 'Failed to click continue'}
        
        logger.info("✅ Smart login flow completed successfully")
        
        return {
            'success': True,
            'field_type': field_type,
            'has_password': has_password,
            'method': 'smart_login'
        }
    
    async def _detect_login_field_type(self) -> Optional[str]:
        """
        Detect what type of login field is present
        
        Returns:
            'mobile', 'email', 'both', or None
        """
        result = await self.page.evaluate("""
            () => {
                // Look for input fields that could be login
                const inputs = document.querySelectorAll('input[type="text"], input[type="tel"], input[type="email"], input:not([type])');
                
                for (const input of inputs) {
                    const placeholder = (input.placeholder || '').toLowerCase();
                    const label = input.getAttribute('aria-label')?.toLowerCase() || '';
                    const name = (input.name || '').toLowerCase();
                    const id = (input.id || '').toLowerCase();
                    
                    const allText = `${placeholder} ${label} ${name} ${id}`;
                    
                    // Check if it's a mobile field
                    const isMobile = allText.includes('mobile') || 
                                    allText.includes('phone') || 
                                    allText.includes('number') ||
                                    input.type === 'tel' ||
                                    allText.match(/\\d{10}/) || // "Enter 10 digit mobile"
                                    placeholder.match(/^\\+?\\d/); // Starts with + or digit
                    
                    // Check if it's an email field
                    const isEmail = allText.includes('email') ||
                                   allText.includes('e-mail') ||
                                   input.type === 'email' ||
                                   placeholder.includes('@');
                    
                    // Check if it accepts both
                    const isBoth = (allText.includes('email') && allText.includes('mobile')) ||
                                  allText.includes('email or mobile') ||
                                  allText.includes('mobile or email') ||
                                  allText.includes('email/mobile');
                    
                    // Check if visible and not disabled
                    const rect = input.getBoundingClientRect();
                    const style = window.getComputedStyle(input);
                    const isVisible = rect.width > 0 && rect.height > 0 &&
                                    style.display !== 'none' &&
                                    style.visibility !== 'hidden';
                    
                    if (isVisible && !input.disabled) {
                        input.setAttribute('data-login-field', 'true');
                        
                        if (isBoth) return { type: 'both', selector: 'input[data-login-field="true"]' };
                        if (isMobile) return { type: 'mobile', selector: 'input[data-login-field="true"]' };
                        if (isEmail) return { type: 'email', selector: 'input[data-login-field="true"]' };
                    }
                }
                
                return { type: null };
            }
        """)
        
        return result.get('type')
    
    async def _fill_mobile_field(self, phone: str) -> bool:
        """Fill mobile number field"""
        try:
            await self.page.fill('input[data-login-field="true"]', phone)
            await asyncio.sleep(0.5)
            logger.info(f"   Filled mobile: {phone}")
            return True
        except Exception as e:
            logger.error(f"Failed to fill mobile: {e}")
            return False
    
    async def _fill_email_field(self, email: str) -> bool:
        """Fill email field"""
        try:
            await self.page.fill('input[data-login-field="true"]', email)
            await asyncio.sleep(0.5)
            logger.info(f"   Filled email: {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to fill email: {e}")
            return False
    
    async def _fill_combo_field(self, email: str, phone: str) -> bool:
        """Fill a field that accepts both email and mobile"""
        # Indian sites often prefer mobile for login
        try:
            await self.page.fill('input[data-login-field="true"]', phone)
            await asyncio.sleep(0.5)
            logger.info(f"   Filled combo field with mobile: {phone}")
            return True
        except:
            # Fallback to email
            try:
                await self.page.fill('input[data-login-field="true"]', email)
                await asyncio.sleep(0.5)
                logger.info(f"   Filled combo field with email: {email}")
                return True
            except Exception as e:
                logger.error(f"Failed to fill combo field: {e}")
                return False
    
    async def _detect_password_field(self) -> bool:
        """Check if password field is present"""
        try:
            password_field = await self.page.query_selector('input[type="password"]')
            return password_field is not None
        except:
            return False
    
    async def _fill_password_field(self, password: str) -> bool:
        """Fill password field"""
        try:
            await self.page.fill('input[type="password"]', password)
            await asyncio.sleep(0.5)
            logger.info("   Password filled")
            return True
        except Exception as e:
            logger.error(f"Failed to fill password: {e}")
            return False
    
    async def _handle_terms_and_conditions(self) -> bool:
        """
        Find and check all mandatory T&C checkboxes
        """
        try:
            result = await self.page.evaluate("""
                () => {
                    // Find all checkboxes
                    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                    let checkedCount = 0;
                    
                    for (const checkbox of checkboxes) {
                        // Skip if already checked
                        if (checkbox.checked) continue;
                        
                        // Check if it's T&C related
                        const label = checkbox.parentElement?.textContent?.toLowerCase() || '';
                        const ariaLabel = checkbox.getAttribute('aria-label')?.toLowerCase() || '';
                        const name = (checkbox.name || '').toLowerCase();
                        
                        const allText = `${label} ${ariaLabel} ${name}`;
                        
                        const isTerms = allText.includes('terms') ||
                                       allText.includes('conditions') ||
                                       allText.includes('agreement') ||
                                       allText.includes('policy') ||
                                       allText.includes('agree') ||
                                       allText.includes('accept');
                        
                        // Check if it's required/mandatory
                        const isRequired = checkbox.required ||
                                         allText.includes('required') ||
                                         allText.includes('mandatory') ||
                                         allText.includes('must');
                        
                        if (isTerms || isRequired) {
                            // Check if visible
                            const rect = checkbox.getBoundingClientRect();
                            const style = window.getComputedStyle(checkbox);
                            const isVisible = rect.width > 0 && rect.height > 0 &&
                                            style.display !== 'none';
                            
                            if (isVisible && !checkbox.disabled) {
                                checkbox.click();
                                checkedCount++;
                                console.log('Checked T&C checkbox:', label.substring(0, 50));
                            }
                        }
                    }
                    
                    return { checked: checkedCount };
                }
            """)
            
            checked_count = result.get('checked', 0)
            if checked_count > 0:
                logger.info(f"   ✅ Checked {checked_count} T&C checkbox(es)")
            
            return True
            
        except Exception as e:
            logger.warning(f"Error handling T&C: {e}")
            return False
    
    async def _click_continue_button(self) -> bool:
        """
        Find and click Continue/Next/Submit button
        """
        try:
            result = await self.page.evaluate("""
                () => {
                    const keywords = [
                        'continue', 'next', 'proceed', 'submit', 
                        'login', 'sign in', 'get otp', 'send otp',
                        'verify', 'go', 'start'
                    ];
                    
                    const selectors = [
                        'button', 'input[type="submit"]', 'input[type="button"]',
                        'a[role="button"]', '[role="button"]'
                    ];
                    
                    for (const selector of selectors) {
                        const buttons = document.querySelectorAll(selector);
                        
                        for (const btn of buttons) {
                            const text = (btn.textContent || '').toLowerCase().trim();
                            const value = (btn.value || '').toLowerCase();
                            const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                            
                            const allText = `${text} ${value} ${ariaLabel}`;
                            
                            // Check if button matches keywords
                            const matches = keywords.some(kw => allText.includes(kw));
                            
                            if (matches) {
                                // Check visibility
                                const rect = btn.getBoundingClientRect();
                                const style = window.getComputedStyle(btn);
                                const isVisible = rect.width > 0 && rect.height > 0 &&
                                                style.display !== 'none' &&
                                                !btn.disabled;
                                
                                if (isVisible) {
                                    console.log('Clicking continue button:', text);
                                    btn.scrollIntoView({ block: 'center' });
                                    btn.click();
                                    return { success: true, text: text };
                                }
                            }
                        }
                    }
                    
                    return { success: false };
                }
            """)
            
            if result.get('success'):
                logger.info(f"   ✅ Clicked: {result.get('text')}")
                return True
            else:
                logger.warning("   ⚠️ Continue button not found")
                return False
                
        except Exception as e:
            logger.error(f"Error clicking continue: {e}")
            return False
