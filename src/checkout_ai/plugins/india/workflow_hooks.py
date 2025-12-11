"""
Workflow Hooks for India Plugin
Injects India-specific steps into the universal checkout workflow
"""
import logging
from typing import List

logger = logging.getLogger(__name__)

class IndiaWorkflowPlugin:
    """Injects India-specific steps into universal workflow"""
    
    def __init__(self):
        # Steps that require OTP verification (login-related)
        self.login_steps = ['login', 'sign in', 'register', 'create account', 'guest checkout']
        # Steps related to address (no longer trigger OTP)
        self.address_steps = ['fill address', 'shipping address']
        # Payment-related steps
        self.payment_steps = ['payment', 'select payment', 'checkout']
    
    def augment_plan(self, plan_steps: List[str], country_code: str) -> List[str]:
        """
        Add India-specific steps to the plan and replace US-style steps
        
        Args:
            plan_steps: Original plan steps
            country_code: Country code (e.g., 'IN')
            
        Returns:
            Enhanced plan with India-specific steps
        """
        if country_code != 'IN':
            logger.info(f"Country {country_code} is not India, skipping India plugin")
            return plan_steps
        
        logger.info("🇮🇳 Applying India workflow enhancements")
        
        enhanced_plan = []
        otp_added = False
        
        for i, step in enumerate(plan_steps):
            step_lower = step.lower()
            
            # **REPLACE** email/contact filling with smart_login for Indian sites
            if ('fill email' in step_lower or 
                'enter email' in step_lower or
                'fill contact' in step_lower or
                any(keyword in step_lower for keyword in self.login_steps)):
                
                if not any('smart login' in s.lower() for s in enhanced_plan):
                    enhanced_plan.append("Use smart_login to enter mobile/email and handle T&C")
                    logger.info(f"   🔄 Replaced '{step}' with 'smart_login'")
                    
                    # Add OTP step after login
                    if not otp_added:
                        enhanced_plan.append("Verify phone number via OTP")
                        logger.info("   ➕ Added: Verify phone number via OTP")
                        otp_added = True
                else:
                    # Skip duplicate email/contact steps
                    logger.info(f"   ⏭️  Skipped duplicate: '{step}'")
                continue
            
            # **REPLACE** address filling with STRICT verification tool
            if ('shipping address' in step_lower or 'fill address' in step_lower) and 'billing' not in step_lower:
                 enhanced_plan.append("Use 'verify_address' tool to validate selected address matches config. If it clicks 'Add New', fill the form.")
                 logger.info(f"   🔄 Replaced '{step}' with 'Address Verification Tool'")
                 continue
            
            # Keep other steps as-is
            enhanced_plan.append(step)
            
            # Before payment, suggest COD
            if any(keyword in step_lower for keyword in self.payment_steps):
                if not self._has_cod_step(plan_steps, i):
                    enhanced_plan.insert(-1, "Select Cash on Delivery (COD) payment method")
                    logger.info("   ➕ Added: Select COD payment")
        
        logger.info(f"📋 Enhanced plan: {len(plan_steps)} → {len(enhanced_plan)} steps")
        return enhanced_plan
    
    def _has_otp_step(self, plan_steps: List[str], current_index: int) -> bool:
        """Check if OTP step already exists in plan"""
        return any('otp' in step.lower() or 'verify phone' in step.lower() 
                   for step in plan_steps[current_index:])
    
    def _has_cod_step(self, plan_steps: List[str], current_index: int) -> bool:
        """Check if COD step already exists in plan"""
        return any('cod' in step.lower() or 'cash on delivery' in step.lower()
                   for step in plan_steps[current_index:])
    
    def should_use_session_restore(self, site: str) -> bool:
        """
        Check if session restore should be attempted for this site
        
        Args:
            site: Site domain
            
        Returns:
            True if session restore recommended
        """
        # Indian sites that work well with session restore
        session_friendly_sites = [
            'myntra.com',
            'ajio.com',
            'flipkart.com',
            'amazon.in',
            'nykaa.com'
        ]
        
        return any(site_domain in site for site_domain in session_friendly_sites)
    
    def get_site_specific_config(self, site: str) -> dict:
        """
        Get site-specific configuration for Indian sites
        
        Args:
            site: Site domain
            
        Returns:
            Configuration dict
        """
        configs = {
            'myntra.com': {
                'requires_otp': True,
                'supports_cod': True,
                'payment_gateway': 'razorpay',
                'guest_checkout': False
            },
            'flipkart.com': {
                'requires_otp': True,
                'supports_cod': True,
                'payment_gateway': 'razorpay',
                'guest_checkout': False,
                'pin_code_check_upfront': True
            },
            'ajio.com': {
                'requires_otp': True,
                'supports_cod': True,
                'payment_gateway': 'razorpay',
                'guest_checkout': True
            },
            'amazon.in': {
                'requires_otp': True,
                'supports_cod': True,
                'payment_gateway': 'amazon_pay',
                'guest_checkout': False
            },
            'bigbasket.com': {
                'requires_otp': True,
                'supports_cod': True,
                'payment_gateway': 'razorpay',
                'guest_checkout': False,
                'requires_delivery_slot': True
            }
        }
        
        for site_domain, config in configs.items():
            if site_domain in site:
                logger.info(f"Loaded config for {site_domain}: {config}")
                return config
        
        # Default config for unknown Indian sites
        return {
            'requires_otp': True,
            'supports_cod': True,
            'guest_checkout': False
        }
