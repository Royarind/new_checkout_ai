"""
Professional Logging System for Checkout AI
Format: YYYY-MM-DD HH:MM:SS - [Module] - [Source] - Description
"""

import logging
from datetime import datetime


class CheckoutFormatter(logging.Formatter):
    """Custom formatter with module and source context"""
    
    def format(self, record):
        # Extract module and source from extra fields
        module = getattr(record, 'module_name', 'SYSTEM')
        source = getattr(record, 'source', 'CORE')
        
        # Format timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Color codes for different levels
        colors = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m'  # Magenta
        }
        reset = '\033[0m'
        
        color = colors.get(record.levelname, '')
        
        # Format: YYYY-MM-DD HH:MM:SS - [MODULE] - [SOURCE] - Description
        formatted = f"{timestamp} - [{module}] - [{source}] - {record.getMessage()}"
        
        return f"{color}{formatted}{reset}"


def setup_logger(name='checkout_ai'):
    """Setup professional logger with custom formatting"""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(CheckoutFormatter())
    
    logger.addHandler(console_handler)
    logger.propagate = False
    
    return logger


def log(logger, level, message, module='SYSTEM', source='CORE'):
    """Helper function to log with module and source context"""
    extra = {'module_name': module, 'source': source}
    
    if level == 'debug':
        logger.debug(message, extra=extra)
    elif level == 'info':
        logger.info(message, extra=extra)
    elif level == 'warning':
        logger.warning(message, extra=extra)
    elif level == 'error':
        logger.error(message, extra=extra)
    elif level == 'critical':
        logger.critical(message, extra=extra)
