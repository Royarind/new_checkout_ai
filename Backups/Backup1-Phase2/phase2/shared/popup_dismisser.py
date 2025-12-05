#!/usr/bin/env python3

import asyncio
from playwright.async_api import Page

async def dismiss_popups(page: Page) -> bool:
    """Dismiss common popups, cookies, geolocation, and modal dialogs"""
    
    dismissed_count = 0
    
    try:
        # Wait for page to stabilize
        await asyncio.sleep(1)
        
        # Dismiss popups using JavaScript
        result = await page.evaluate("""
            () => {
                let dismissed = 0;
                
                // Cookie consent selectors
                const cookieSelectors = [
                    '[id*="cookie"] button', '[class*="cookie"] button',
                    '[data-testid*="cookie"] button', '[aria-label*="cookie" i] button',
                    'button:has-text("Accept")', 'button:has-text("Allow")',
                    'button:has-text("OK")', 'button:has-text("Got it")',
                    'button:has-text("I agree")', 'button:has-text("Continue")',
                    '.cookie-banner button', '.cookie-consent button',
                    '#cookie-banner button', '#cookie-consent button'
                ];
                
                // Modal/popup close selectors
                const closeSelectors = [
                    '[data-drawer-action="close"]', '.drawer__close',
                    '[aria-label*="close" i]', '.modal-close', '.popup-close',
                    '[data-backdrop]', '.backdrop', 'button[class*="close"]',
                    '.close-button', '[data-dismiss]', '.dismiss',
                    'button:has-text("×")', 'button:has-text("✕")',
                    '[role="dialog"] button', '.dialog button'
                ];
                
                // Newsletter/signup dismissal
                const newsletterSelectors = [
                    '[class*="newsletter"] button[class*="close"]',
                    '[class*="signup"] button[class*="close"]',
                    '[class*="email"] button[class*="close"]',
                    'button:has-text("No thanks")', 'button:has-text("Skip")',
                    'button:has-text("Maybe later")', 'button:has-text("Not now")'
                ];
                
                // Age verification
                const ageSelectors = [
                    'button:has-text("Yes")', 'button:has-text("I am 18")',
                    'button:has-text("Enter")', '[class*="age"] button'
                ];
                
                // Combine all selectors
                const allSelectors = [
                    ...cookieSelectors,
                    ...closeSelectors, 
                    ...newsletterSelectors,
                    ...ageSelectors
                ];
                
                // Try each selector
                for (const selector of allSelectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            if (el.offsetParent !== null && typeof el.click === 'function') {
                                el.click();
                                dismissed++;
                                console.log('Dismissed popup:', selector);
                                break;
                            }
                        }
                        if (dismissed > 0) break;
                    } catch (e) {
                        // Continue to next selector
                    }
                }
                
                // Press Escape key
                document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
                
                return dismissed;
            }
        """)
        
        dismissed_count = result
        
        if dismissed_count > 0:
            await asyncio.sleep(1)  # Wait for popup to close
            
        return dismissed_count > 0
        
    except Exception as e:
        print(f"Error dismissing popups: {e}")
        return False

async def handle_geolocation_permission(page: Page):
    """Handle geolocation permission requests"""
    try:
        # Block geolocation requests
        await page.context.grant_permissions([], origin=page.url)
    except Exception:
        pass