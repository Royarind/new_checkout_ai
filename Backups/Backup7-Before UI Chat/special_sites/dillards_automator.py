#!/usr/bin/env python3
"""
Dillard's Specific Automator
Handles Dillard's unique checkout flow with dual checkout buttons
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

async def handle_dillards_checkout(page):
    """
    Dillard's-specific checkout navigation
    Problem: Two checkout buttons - one in side modal, one on cart page
    Solution: Close modal first, then click PROCEED TO CHECKOUT on cart page
    """
    logger.info("DILLARDS: Starting Dillard's-specific checkout flow")
    
    try:
        # Step 1: Close the side modal if it's open
        logger.info("DILLARDS: Closing side modal...")
        modal_closed = await page.evaluate("""
            () => {
                const closeSelectors = [
                    '[aria-label*="close" i]',
                    'button.close',
                    '[data-dismiss]',
                    '.modal-close',
                    '[class*="close"]'
                ];
                
                for (const selector of closeSelectors) {
                    const closeBtn = document.querySelector(selector);
                    if (closeBtn && closeBtn.offsetParent) {
                        const rect = closeBtn.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            closeBtn.click();
                            return true;
                        }
                    }
                }
                return false;
            }
        """)
        
        if modal_closed:
            logger.info("DILLARDS: Modal closed")
            await asyncio.sleep(1)
        
        # Step 2: Find and click "PROCEED TO CHECKOUT" button on cart page
        logger.info("DILLARDS: Looking for PROCEED TO CHECKOUT button...")
        
        result = await page.evaluate("""
            () => {
                const buttons = document.querySelectorAll('button, a, [role="button"]');
                
                for (const btn of buttons) {
                    if (!btn.offsetParent) continue;
                    
                    const text = btn.textContent?.trim() || '';
                    const rect = btn.getBoundingClientRect();
                    
                    // Look for "PROCEED TO CHECKOUT" specifically
                    if (text.toLowerCase().includes('proceed') && 
                        text.toLowerCase().includes('checkout') &&
                        rect.width > 0 && rect.height > 0) {
                        
                        // Ensure it's NOT in a modal (z-index check)
                        const style = window.getComputedStyle(btn);
                        const zIndex = parseInt(style.zIndex) || 0;
                        const inModal = btn.closest('[role="dialog"], .modal, [class*="modal"]');
                        
                        // Prefer buttons NOT in modals
                        if (!inModal || zIndex < 100) {
                            btn.scrollIntoView({ block: 'center' });
                            btn.click();
                            return { success: true, text: text };
                        }
                    }
                }
                return { success: false };
            }
        """)
        
        if result.get('success'):
            logger.info(f"DILLARDS: Clicked '{result.get('text')}'")
            await asyncio.sleep(3)
            return {'success': True}
        
        logger.error("DILLARDS: PROCEED TO CHECKOUT button not found")
        return {'success': False, 'error': 'Button not found'}
        
    except Exception as e:
        logger.error(f"DILLARDS: Error - {e}")
        return {'success': False, 'error': str(e)}


def is_dillards(url):
    """Check if URL is Dillard's"""
    return 'dillards.com' in url.lower()
