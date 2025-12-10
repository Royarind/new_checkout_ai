"""
Payment Handler for Indian E-commerce Sites
Handles India-specific payment methods: COD, UPI, Razorpay, etc.
"""
import logging
from playwright.async_api import Page
from typing import Optional

logger = logging.getLogger(__name__)

class IndiaPaymentHandler:
    """Handles India-specific payment methods"""
    
    async def select_cod(self, page: Page) -> bool:
        """
        Select Cash on Delivery (COD) payment method
        
        Args:
            page: Playwright page
            
        Returns:
            True if COD selected successfully
        """
        logger.info("Attempting to select Cash on Delivery (COD)")
        
        # Common COD selectors for Indian sites
        cod_selectors = [
            # Input/radio buttons
            'input[value="cod" i]',
            'input[value="COD" i]',
            'input[value="cash_on_delivery" i]',
            'input[id*="cod" i]',
            'input[name*="cod" i]',
            
            # Labels and text
            'label:has-text("Cash on Delivery")',
            'label:has-text("COD")',
            'div:has-text("Cash on Delivery"):has(input)',
            
            # Data attributes
            '[data-payment="cod"]',
            '[data-payment="cash_on_delivery"]',
            '[data-payment-method="cod"]',
            
            # Site-specific
            '.payment-option-cod',
            '#payment_method_cod'
        ]
        
        for selector in cod_selectors:
            try:
                if await page.is_visible(selector, timeout=2000):
                    await page.click(selector)
                    logger.info(f"✅ COD selected via: {selector}")
                    
                    # Wait for selection to register
                    await page.wait_for_timeout(1000)
                    return True
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        logger.warning("❌ Could not find COD payment option")
        return False
    
    async def detect_payment_gateway(self, page: Page) -> Optional[str]:
        """
        Detect which payment gateway is being used
        
        Args:
            page: Playwright page
            
        Returns:
            Payment gateway name ('razorpay', 'paytm', 'stripe', etc.) or None
        """
        # Check page content for payment gateway indicators
        page_content = await page.content()
        
        gateways = {
            'razorpay': ['razorpay', 'api.razorpay.com'],
            'paytm': ['paytm', 'securegw.paytm.in'],
            'phonepe': ['phonepe', 'mercury.phonepe.com'],
            'stripe': ['stripe', 'js.stripe.com'],
            'paypal': ['paypal', 'www.paypal.com']
        }
        
        for gateway, indicators in gateways.items():
            if any(indicator in page_content.lower() for indicator in indicators):
                logger.info(f"Detected payment gateway: {gateway}")
                return gateway
        
        return None
    
    async def handle_razorpay(self, page: Page):
        """
        Handle Razorpay payment flow
        Note: Razorpay requires manual payment completion
        
        Args:
            page: Playwright page
        """
        logger.info("🔔 Razorpay detected - manual payment required")
        logger.info("   Please complete payment in the browser window")
        
        # Wait for Razorpay modal/iframe
        try:
            # Razorpay typically loads in an iframe
            razorpay_frame = page.frame(name="razorpay-checkout-frame")
            if razorpay_frame:
                logger.info("   Razorpay payment modal is open")
                # Pause automation, let user complete payment
                # await page.pause()  # Uncomment for debugging
        except:
            pass
    
    async def handle_paytm(self, page: Page):
        """
        Handle Paytm payment flow
        Note: Requires manual payment completion
        
        Args:
            page: Playwright page
        """
        logger.info("🔔 Paytm detected - manual payment required")
        logger.info("   Please complete payment in the browser window")
    
    async def select_upi(self, page: Page, upi_id: str = None) -> bool:
        """
        Select UPI payment method
        
        Args:
            page: Playwright page
            upi_id: UPI ID (optional)
            
        Returns:
            True if UPI selected
        """
        logger.info("Attempting to select UPI payment")
        
        upi_selectors = [
            'input[value="upi" i]',
            'label:has-text("UPI")',
            '[data-payment="upi"]',
            '.payment-option-upi'
        ]
        
        for selector in upi_selectors:
            try:
                if await page.is_visible(selector, timeout=2000):
                    await page.click(selector)
                    logger.info(f"✅ UPI selected via: {selector}")
                    
                    # If UPI ID provided, try to enter it
                    if upi_id:
                        await self._enter_upi_id(page, upi_id)
                    
                    return True
            except:
                continue
        
        logger.warning("❌ Could not find UPI payment option")
        return False
    
    async def _enter_upi_id(self, page: Page, upi_id: str):
        """Enter UPI ID in the field"""
        upi_input_selectors = [
            'input[name*="upi" i]',
            'input[placeholder*="UPI" i]',
            '#upi_id'
        ]
        
        for selector in upi_input_selectors:
            try:
                if await page.is_visible(selector, timeout=1000):
                    await page.fill(selector, upi_id)
                    logger.info(f"✅ UPI ID entered: {upi_id}")
                    return
            except:
                continue
        
        logger.warning("Could not find UPI ID input field")
