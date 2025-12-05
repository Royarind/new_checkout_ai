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
            await asyncio.sleep(5)  # Wait longer for page load
            
            # Verify we're on checkout page with form fields
            has_form = await page.evaluate("""
                () => {
                    const inputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"]');
                    return inputs.length > 0;
                }
            """)
            
            if has_form:
                logger.info("DILLARDS: Successfully navigated to checkout form")
                return {'success': True}
            else:
                logger.warning("DILLARDS: No form fields found, may need to wait or dismiss modal")
                await asyncio.sleep(3)
                return {'success': True}  # Proceed anyway
        
        logger.error("DILLARDS: PROCEED TO CHECKOUT button not found")
        return {'success': False, 'error': 'Button not found'}
        
    except Exception as e:
        logger.error(f"DILLARDS: Error - {e}")
        return {'success': False, 'error': str(e)}


async def select_dillards_variant(page, variant_type, variant_value):
    """
    Dillard's-specific variant selection
    Works for ANY variant (color, size, etc.) using data-attrval attribute
    """
    logger.info(f"DILLARDS: Selecting {variant_type}={variant_value}")
    
    try:
        # Store original URL to detect navigation
        original_url = page.url
        logger.info(f"DILLARDS: Original URL: {original_url}")
        
        result = await page.evaluate("""
            (variantValue) => {
                // Find ALL elements with data-attrval attribute
                const elements = document.querySelectorAll('[data-attrval]');
                
                for (const el of elements) {
                    const attrVal = el.getAttribute('data-attrval');
                    if (!attrVal) continue;
                    
                    // Match variant value (case-insensitive, trim whitespace)
                    if (attrVal.trim().toLowerCase() === variantValue.trim().toLowerCase()) {
                        // Check if visible
                        if (!el.offsetParent) continue;
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        
                        // Scroll into view
                        el.scrollIntoView({ block: 'center', behavior: 'smooth' });
                        
                        // Find clickable element (button or parent button)
                        let clickTarget = el;
                        if (el.tagName === 'BUTTON') {
                            clickTarget = el;
                        } else if (el.querySelector('button')) {
                            clickTarget = el.querySelector('button');
                        } else if (el.closest('button')) {
                            clickTarget = el.closest('button');
                        }
                        
                        // CRITICAL FIX: For links, use onclick to prevent navigation
                        if (clickTarget.tagName === 'A') {
                            // Store original onclick
                            const originalOnclick = clickTarget.onclick;
                            
                            // Override onclick to prevent navigation
                            clickTarget.onclick = function(e) {
                                e.preventDefault();
                                e.stopPropagation();
                                // Call original onclick if it exists
                                if (originalOnclick) originalOnclick.call(this, e);
                                return false;
                            };
                            
                            // Trigger click
                            clickTarget.click();
                        } else {
                            clickTarget.click();
                        }
                        
                        return { success: true, selected: attrVal };
                    }
                }
                
                return { success: false, error: `Variant "${variantValue}" not found` };
            }
        """, variant_value)
        
        if result.get('success'):
            logger.info(f"DILLARDS: ✓ Clicked {result.get('selected')}")
            await asyncio.sleep(2)  # Wait for variant to update
            
            # Verify we're still on product page
            current_url = page.url
            logger.info(f"DILLARDS: Current URL after click: {current_url}")
            
            if '/c/' in current_url or '/catalogs' in current_url:
                logger.error(f"DILLARDS: ❌ Unwanted navigation detected!")
                logger.error(f"   From: {original_url}")
                logger.error(f"   To: {current_url}")
                logger.info(f"DILLARDS: Navigating back to product page...")
                
                # Navigate back to original product page
                await page.goto(original_url, wait_until='domcontentloaded')
                await asyncio.sleep(2)
                
                logger.info(f"DILLARDS: Returned to product page, retrying selection...")
                # Retry the selection
                return await select_dillards_variant(page, variant_type, variant_value)
            
            logger.info(f"DILLARDS: ✓ Selection successful, still on product page")
            return {'success': True}
        else:
            logger.error(f"DILLARDS: ✗ {result.get('error')}")
            return {'success': False, 'error': result.get('error')}
            
    except Exception as e:
        logger.error(f"DILLARDS: Error - {e}")
        return {'success': False, 'error': str(e)}




def is_dillards(url: str) -> bool:
    """Check if URL is Dillard's"""
    return 'dillards.com' in url.lower()
