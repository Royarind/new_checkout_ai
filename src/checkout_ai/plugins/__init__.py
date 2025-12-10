"""
Plugins package for Checkout AI
Contains country-specific and feature-specific plugins
"""

# Currently available plugins
__all__ = []

# Import India plugin if needed
try:
    from .india import IndiaWorkflowPlugin, IndiaOTPHandler, IndiaPaymentHandler
    __all__.extend(['IndiaWorkflowPlugin', 'IndiaOTPHandler', 'IndiaPaymentHandler'])
except ImportError:
    pass
