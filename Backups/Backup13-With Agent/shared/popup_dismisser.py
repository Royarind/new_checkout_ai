#!/usr/bin/env python3

import asyncio
from playwright.async_api import Page

async def dismiss_popups(page: Page) -> bool:
    """Dismiss common popups, cookies, geolocation, modals, and cart/basket overlays"""
    
    print("🔍 Checking for popups...")
    dismissed_count = 0
    
    try:
        # Wait for page to stabilize
        await asyncio.sleep(1)
        
        # First try: Click outside modal area (left side of page) to dismiss side modals
        try:
            await page.mouse.click(50, 300)
            await asyncio.sleep(0.5)
            dismissed_count += 1
            print("✅ Clicked outside modal area")
        except:
            pass
        
        # Dismiss popups using JavaScript
        result = await page.evaluate("""
            () => {
                let dismissed = 0;
                
                // Cookie consent selectors - PRIORITIZE ACCEPT ALL
                const cookieAcceptSelectors = [
                    'button:has-text("Accept All")', 'button:has-text("Accept all")',
                    'button:has-text("Accept All Cookies")', 'button:has-text("Allow All")',
                    '#onetrust-accept-btn-handler', '#truste-consent-button',
                    '[id*="accept-all" i]', '[class*="accept-all" i]',
                    '[data-testid*="accept-all" i]', '[aria-label*="accept all" i]',
                    '.cookie-accept', '.gdpr-accept', '.consent-accept',
                    'button:has-text("Accept")', 'button:has-text("I Accept")',
                    'button:has-text("Allow")', 'button:has-text("I agree")',
                    'button:has-text("Agree")', 'button:has-text("OK")',
                    'button:has-text("Got it")', 'button:has-text("Continue")',
                    '[id*="cookie"] button', '[class*="cookie"] button',
                    '[data-testid*="cookie"] button', '[aria-label*="cookie" i] button',
                    '.cookie-banner button', '.cookie-consent button',
                    '#cookie-banner button', '#cookie-consent button', '[data-cookie] button'
                ];
                
                // Try cookie accept buttons FIRST
                for (const selector of cookieAcceptSelectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            if (el.offsetParent !== null && typeof el.click === 'function') {
                                const text = (el.textContent || '').toLowerCase().trim();
                                const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
                                
                                // Click accept/allow buttons for cookies
                                if (text.includes('accept') || text.includes('allow') || 
                                    text.includes('agree') || text.includes('ok') || text.includes('got it') ||
                                    ariaLabel.includes('accept') || ariaLabel.includes('allow')) {
                                    el.click();
                                    dismissed++;
                                    console.log('Accepted cookies:', text || ariaLabel);
                                }
                            }
                        }
                    } catch (e) {}
                }
                
                // Modal/popup close selectors (including side modals/drawers)
                const closeSelectors = [
                    '[data-drawer-action="close"]', '.drawer__close',
                    '[aria-label*="close" i]', '[aria-label*="dismiss" i]',
                    '.modal-close', '.popup-close', '.overlay-close',
                    '[data-backdrop]', '.backdrop', '[data-overlay]',
                    'button[class*="close"]', '.close-button', '.btn-close',
                    '[data-dismiss]', '[data-dismiss="modal"]',
                    '.dismiss', '.dismiss-button',
                    'button:has-text("×")', 'button:has-text("✕")',
                    'button:has-text("✖")', 'button:has-text("⨉")',
                    '[role="dialog"] button', '.dialog button',
                    '.modal button[class*="close"]', '.popup button[class*="close"]',
                    '[class*="modal"] [class*="close"]',
                    '[class*="drawer"] button[class*="close"]',
                    '[class*="sidebar"] button[class*="close"]',
                    '[class*="side-modal"] button[class*="close"]',
                    '[class*="offcanvas"] button[class*="close"]',
                    '.drawer button', '.sidebar button[class*="close"]',
                    '[data-drawer] button', '[data-sidebar] button'
                ];
                
                // Newsletter/signup/email capture dismissal
                const newsletterSelectors = [
                    '[class*="newsletter"] button[class*="close"]',
                    '[class*="newsletter"] [aria-label*="close" i]',
                    '[class*="signup"] button[class*="close"]',
                    '[class*="signup"] [aria-label*="close" i]',
                    '[class*="email"] button[class*="close"]',
                    '[class*="subscribe"] button[class*="close"]',
                    'button:has-text("No thanks")', 'button:has-text("No Thanks")',
                    'button:has-text("Skip")', 'button:has-text("Maybe later")',
                    'button:has-text("Not now")', 'button:has-text("Later")',
                    'button:has-text("Dismiss")', 'button:has-text("Close")',
                    '[id*="newsletter"] button[class*="close"]',
                    '[data-newsletter] button', '.newsletter-popup button[class*="close"]'
                ];
                
                // Age verification
                const ageSelectors = [
                    'button:has-text("Yes")', 'button:has-text("I am 18")',
                    'button:has-text("I am 21")', 'button:has-text("Enter")',
                    'button:has-text("Confirm")', '[class*="age"] button',
                    '[id*="age"] button', '[data-age-gate] button'
                ];
                
                // Notification/alert dismissal
                const notificationSelectors = [
                    '[class*="notification"] button[class*="close"]',
                    '[class*="alert"] button[class*="close"]',
                    '[class*="banner"] button[class*="close"]',
                    '[role="alert"] button', '[role="alertdialog"] button',
                    '.notification-close', '.alert-close', '.banner-close'
                ];
                
                // Cart drawer/overlay and side panels
                const cartOverlaySelectors = [
                    '[data-drawer="cart"] [data-drawer-action="close"]',
                    '.cart-drawer button[class*="close"]',
                    '.cart-overlay button[class*="close"]',
                    '[id*="cart-drawer"] button[class*="close"]',
                    '.minicart-overlay button[class*="close"]',
                    '[class*="cart-overlay"] [aria-label*="close" i]',
                    '[class*="side-cart"] button[class*="close"]',
                    '[class*="mini-cart"] button[class*="close"]'
                ];
                
                // Promotional/discount popups
                const promoSelectors = [
                    '[class*="promo"] button[class*="close"]',
                    '[class*="discount"] button[class*="close"]',
                    '[class*="offer"] button[class*="close"]',
                    '[class*="sale"] button[class*="close"]',
                    'button:has-text("Continue shopping")'
                ];
                
                // Geolocation/region selectors
                const geolocationSelectors = [
                    '[class*="geolocation"] button',
                    '[class*="location"] button[class*="close"]',
                    '[class*="region"] button[class*="close"]',
                    '[class*="country"] button[class*="close"]',
                    'button:has-text("Stay here")', 
                    'button:has-text("Keep shopping")'
                ];
                
                // Survey/feedback dismissal
                const surveySelectors = [
                    '[class*="survey"] button[class*="close"]',
                    '[class*="feedback"] button[class*="close"]',
                    '[class*="review"] button[class*="close"]',
                    'button:has-text("No, thanks")',
                    '[data-survey] button[class*="close"]'
                ];
                
                // App download prompts
                const appPromptSelectors = [
                    '[class*="app-banner"] button[class*="close"]',
                    '[class*="download"] button[class*="close"]',
                    '[id*="app-banner"] button[class*="close"]',
                    'button:has-text("Continue in browser")',
                    'button:has-text("Not now")'
                ];
                
                // Interstitial/splash screens
                const interstitialSelectors = [
                    '[class*="interstitial"] button',
                    '[class*="splash"] button',
                    '[class*="welcome"] button[class*="close"]',
                    '[data-interstitial] button'
                ];
                
                // Prioritize close buttons (cookies already handled above)
                const allSelectors = [
                    ...closeSelectors,
                    ...cartOverlaySelectors,
                    ...newsletterSelectors,
                    ...promoSelectors,
                    ...notificationSelectors,
                    ...surveySelectors,
                    ...appPromptSelectors,
                    ...interstitialSelectors,
                    ...ageSelectors,
                    ...geolocationSelectors
                ];
                
                // Try each selector and click ONLY close/dismiss buttons
                for (const selector of allSelectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            if (el.offsetParent !== null && typeof el.click === 'function') {
                                const text = (el.textContent || '').toLowerCase().trim();
                                const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
                                const className = (el.className || '').toLowerCase();
                                const id = (el.id || '').toLowerCase();
                                
                                // 🚨 CRITICAL: Skip coupon/promo/gift certificate/discount buttons - NEVER CLICK THESE
                                const isCouponButton = 
                                    text.includes('apply') || text.includes('redeem') || 
                                    text.includes('add code') || text.includes('submit') ||
                                    text.includes('coupon') || text.includes('promo') || 
                                    text.includes('discount code') || text.includes('gift card') ||
                                    text.includes('gift certificate') || text.includes('discount') ||
                                    ariaLabel.includes('apply') || ariaLabel.includes('redeem') ||
                                    ariaLabel.includes('coupon') || ariaLabel.includes('promo') ||
                                    ariaLabel.includes('gift') || ariaLabel.includes('discount') ||
                                    className.includes('coupon') || className.includes('promo') ||
                                    className.includes('gift') || className.includes('discount') ||
                                    className.includes('apply') || className.includes('redeem') ||
                                    id.includes('coupon') || id.includes('promo') ||
                                    id.includes('gift') || id.includes('discount') ||
                                    id.includes('apply') || id.includes('redeem');
                                
                                // Click if it's a close/dismiss button AND not a coupon button
                                const isCloseButton = 
                                    text === '×' || text === '✕' || text === '✖' || text === '⨉' ||
                                    text === 'close' || text === 'dismiss' || text === 'no thanks' ||
                                    text === 'skip' || text === 'maybe later' || text === 'not now' ||
                                    ariaLabel.includes('close') || ariaLabel.includes('dismiss') ||
                                    className.includes('close') || className.includes('dismiss') ||
                                    id.includes('close') || id.includes('dismiss') ||
                                    el.hasAttribute('data-dismiss') || el.hasAttribute('data-drawer-action');
                                
                                if (isCloseButton && !isCouponButton) {
                                    el.click();
                                    dismissed++;
                                    console.log('Dismissed popup:', selector, text || ariaLabel);
                                }
                            }
                        }
                    } catch (e) {}
                }
                
                // Remove overlay/backdrop elements that might block interaction
                try {
                    const overlays = document.querySelectorAll(
                        '.overlay, .backdrop, [data-backdrop], [class*="modal-backdrop"], ' +
                        '[class*="overlay-backdrop"], .drawer-overlay, [data-overlay]'
                    );
                    overlays.forEach(overlay => {
                        if (overlay.offsetParent !== null) {
                            overlay.style.display = 'none';
                            overlay.remove();
                            dismissed++;
                        }
                    });
                } catch (e) {
                    // Continue
                }
                
                // Press Escape key to close any remaining popups
                document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
                document.dispatchEvent(new KeyboardEvent('keyup', {key: 'Escape', bubbles: true, cancelable: true}));
                
                // Remove aria-hidden from body (some popups set this)
                try {
                    document.body.removeAttribute('aria-hidden');
                    document.body.style.overflow = '';
                    document.documentElement.style.overflow = '';
                } catch (e) {
                    // Continue
                }
                
                return dismissed;
            }
        """)
        
        dismissed_count = result
        
        if dismissed_count > 0:
            print(f"✅ Dismissed {dismissed_count} popup(s)")
            await asyncio.sleep(0.5)
        else:
            print("ℹ️  No popups found")
        
        # Additional Playwright-level dismissals
        try:
            # Press Escape key through Playwright
            await page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
        except:
            pass
            
        return dismissed_count > 0
        
    except Exception as e:
        print(f"   ⚠️ Error dismissing popups: {e}")
        return False

async def handle_geolocation_permission(page: Page):
    """Handle geolocation permission requests"""
    try:
        # Block geolocation requests
        await page.context.grant_permissions([], origin=page.url)
    except Exception:
        pass

async def handle_notifications_permission(page: Page):
    """Block notification permission requests"""
    try:
        # Deny notification permissions
        await page.context.grant_permissions([], origin=page.url)
    except Exception:
        pass

async def comprehensive_popup_handler(page: Page) -> bool:
    """Comprehensive popup handling with multiple attempts"""
    
    try:
        # Block permissions first
        await handle_geolocation_permission(page)
        await handle_notifications_permission(page)
        
        # Wait for page load
        await page.wait_for_load_state('networkidle', timeout=5000)
        
        # First dismissal attempt - immediate
        dismissed = await dismiss_popups(page)
        
        # Second attempt after short delay (some popups appear delayed)
        await asyncio.sleep(2)
        dismissed2 = await dismiss_popups(page)
        
        # Third attempt - for stubborn popups
        if dismissed or dismissed2:
            await asyncio.sleep(1)
            await dismiss_popups(page)
        
        return dismissed or dismissed2
        
    except Exception as e:
        print(f"   ⚠️ Comprehensive popup handler error: {e}")
        return False

async def dismiss_popups_on_interval(page: Page, interval: int = 3, duration: int = 15):
    """Periodically dismiss popups for a duration (useful for SPAs with dynamic popups)"""
    
    end_time = asyncio.get_event_loop().time() + duration
    
    while asyncio.get_event_loop().time() < end_time:
        await dismiss_popups(page)
        await asyncio.sleep(interval)