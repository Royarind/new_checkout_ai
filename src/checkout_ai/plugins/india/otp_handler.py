"""
OTP Handler for Indian E-commerce Sites
Manages OTP verification flow with frontend integration
"""
import asyncio
import logging
from playwright.async_api import Page
from typing import Optional

logger = logging.getLogger(__name__)

class IndiaOTPHandler:
    """Handles OTP verification for Indian e-commerce sites"""
    
    def __init__(self):
        self.otp_timeout = 60  # seconds
        self._pending_otp = None
        
    async def wait_for_otp_input(self, site: str, timeout: int = None) -> Optional[str]:
        """
        Wait for user to input OTP via frontend
        
        Args:
            site: Site name (e.g., 'myntra', 'flipkart')
            timeout: Timeout in seconds (default: 60)
            
        Returns:
            OTP string if received, None if timeout
        """
        timeout = timeout or self.otp_timeout
        
        logger.info(f"🔔 Waiting for OTP input for {site} (timeout: {timeout}s)")
        
        # TODO: Implement WebSocket communication with frontend
        # For now, this is a placeholder that will be connected to frontend
        
        # Notify frontend that OTP is needed
        await self._notify_frontend_otp_needed(site)
        
        # Wait for OTP with timeout
        try:
            otp = await asyncio.wait_for(
                self._receive_otp_from_frontend(),
                timeout=timeout
            )
            
            if otp:
                logger.info(f"✅ OTP received for {site}")
                return otp
            else:
                logger.warning(f"❌ No OTP received for {site}")
                return None
                
        except asyncio.TimeoutError:
            logger.error(f"⏱️ OTP timeout for {site} after {timeout}s")
            return None
    
    async def enter_otp(self, page: Page, otp: str) -> bool:
        """
        Enter OTP in the page
        
        Args:
            page: Playwright page
            otp: OTP string
            
        Returns:
            True if OTP entered successfully
        """
        logger.info(f"Entering OTP: {otp}")
        
        # Common OTP field selectors for Indian sites
        otp_selectors = [
            'input[name="otp"]',
            'input[id="otp"]',
            'input[placeholder*="OTP" i]',
            'input[placeholder*="code" i]',
            'input[type="tel"][maxlength="6"]',
            'input[type="text"][maxlength="6"]',
            '.otp-input',
            '#otpInput',
            '[data-purpose="otp-input"]'
        ]
        
        # Try each selector
        for selector in otp_selectors:
            try:
                if await page.is_visible(selector, timeout=2000):
                    await page.fill(selector, otp)
                    logger.info(f"✅ OTP entered via selector: {selector}")
                    
                    # Wait a bit for auto-submit or find verify button
                    await asyncio.sleep(1)
                    
                    # Try to click verify/submit button
                    await self._click_verify_button(page)
                    
                    return True
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        logger.error("❌ Could not find OTP input field")
        return False
    
    async def _click_verify_button(self, page: Page):
        """Try to click OTP verify button"""
        verify_buttons = [
            'button:has-text("Verify")',
            'button:has-text("Submit")',
            'button:has-text("Continue")',
            'button:has-text("Confirm")',
            'button[type="submit"]',
            '.verify-button',
            '#verifyOtp'
        ]
        
        for selector in verify_buttons:
            try:
                if await page.is_visible(selector, timeout=1000):
                    await page.click(selector)
                    logger.info(f"✅ Clicked verify button: {selector}")
                    return True
            except:
                continue
        
        logger.warning("No verify button found (might auto-submit)")
        return False
    
    async def _notify_frontend_otp_needed(self, site: str):
        """
        Notify frontend that OTP input is needed
        TODO: Implement WebSocket/API call to frontend
        """
        logger.info(f"📤 Notifying frontend: OTP needed for {site}")
        # Placeholder - will be implemented with WebSocket
        pass
    
    async def _receive_otp_from_frontend(self) -> Optional[str]:
        """
        Receive OTP from frontend via WebSocket
        TODO: Implement WebSocket listener
        """
        # Placeholder - will be implemented with WebSocket
        # For now, simulate waiting
        await asyncio.sleep(30)  # Simulate user taking 30s to enter OTP
        return None  # Will be replaced with actual WebSocket receive
    
    def set_otp(self, otp: str):
        """
        Set OTP (called by WebSocket handler when frontend sends OTP)
        
        Args:
            otp: OTP string from user
        """
        self._pending_otp = otp
        logger.info(f"OTP received from frontend: {otp}")
    
    def verify_otp_format(self, otp: str) -> bool:
        """
        Verify OTP format (6 digits for Indian sites)
        
        Args:
            otp: OTP to verify
            
        Returns:
            True if valid format
        """
        return otp.isdigit() and len(otp) == 6


# Singleton instance for WebSocket communication
_otp_handler = None

def get_otp_handler() -> IndiaOTPHandler:
    """Get or create singleton OTP handler"""
    global _otp_handler
    if _otp_handler is None:
        _otp_handler = IndiaOTPHandler()
    return _otp_handler
