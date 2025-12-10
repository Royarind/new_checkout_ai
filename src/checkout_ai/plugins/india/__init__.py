"""
India Plugin for Checkout AI
Handles India-specific e-commerce workflows including OTP, COD payments, and address fields
"""

from .otp_handler import IndiaOTPHandler
from .payment import IndiaPaymentHandler
from .workflow_hooks import IndiaWorkflowPlugin
from .smart_login import SmartLoginHandler

__all__ = [
    'IndiaOTPHandler',
    'IndiaPaymentHandler', 
    'IndiaWorkflowPlugin',
    'SmartLoginHandler'
]
