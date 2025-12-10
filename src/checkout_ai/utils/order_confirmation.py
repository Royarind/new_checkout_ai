"""
Order Confirmation Handler
Prompts user for confirmation before placing order (configurable via .env)
"""
import os
import asyncio
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

class OrderConfirmationHandler:
    """Handles order placement confirmation"""
    
    def __init__(self):
        self.require_confirmation = os.getenv('REQUIRE_ORDER_CONFIRMATION', 'true').lower() == 'true'
        self.timeout = int(os.getenv('ORDER_CONFIRMATION_TIMEOUT', '30'))
    
    async def confirm_order_placement(self, order_details: dict = None) -> bool:
        """
        Ask user to confirm order placement
        
        Args:
            order_details: Optional dict with order info (items, total, etc.)
            
        Returns:
            True if confirmed, False if cancelled/timeout
        """
        if not self.require_confirmation:
            logger.info("⚠️ Order confirmation disabled (REQUIRE_ORDER_CONFIRMATION=false)")
            logger.info("   Proceeding with automatic order placement")
            return True
        
        logger.info("=" * 70)
        logger.info("🛑 ORDER PLACEMENT CONFIRMATION REQUIRED")
        logger.info("=" * 70)
        
        if order_details:
            logger.info("\n📋 Order Details:")
            for key, value in order_details.items():
                logger.info(f"   {key}: {value}")
        
        logger.info(f"\n⏱️  You have {self.timeout} seconds to review and confirm")
        logger.info("   Press ENTER to CONFIRM order placement")
        logger.info("   Press Ctrl+C to CANCEL")
        logger.info("=" * 70)
        
        try:
            # Wait for user input with timeout
            await asyncio.wait_for(
                self._wait_for_user_input(),
                timeout=self.timeout
            )
            
            logger.info("\n✅ Order placement CONFIRMED by user")
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"\n⏰ Timeout after {self.timeout}s - Auto-confirming order placement")
            logger.warning("   (Set ORDER_CONFIRMATION_TIMEOUT in .env to change timeout)")
            return True
            
        except KeyboardInterrupt:
            logger.error("\n❌ Order placement CANCELLED by user (Ctrl+C)")
            return False
    
    async def _wait_for_user_input(self):
        """Wait for user to press Enter"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input)
    
    def is_enabled(self) -> bool:
        """Check if order confirmation is enabled"""
        return self.require_confirmation


# Singleton instance
_confirmation_handler = None

def get_confirmation_handler() -> OrderConfirmationHandler:
    """Get or create singleton confirmation handler"""
    global _confirmation_handler
    if _confirmation_handler is None:
        _confirmation_handler = OrderConfirmationHandler()
    return _confirmation_handler
