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
        
        # Dismiss popups using JavaScript with intelligent strategy selection
        result = await page.evaluate("""
            () => {
                let dismissed = 0;
                
                // PHASE 1: Cookie consent - CLICK ACCEPT/ALLOW (not X)
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
                    '[id*="cookie"] button:has-text("Accept")', 
                    '[class*="cookie"] button:has-text("Accept")',
                    '[class*="cookie"] button:has-text("Allow")'
                ];
                
                for (const selector of cookieAcceptSelectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            if (el.offsetParent !== null && typeof el.click === 'function') {
                                const text = (el.textContent || '').toLowerCase().trim();
                                const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
                                const parent = el.closest('[class*="cookie"], [id*="cookie"], [class*="consent"], [class*="gdpr"]');
                                
                                // Only click Accept/Allow if it's in a cookie/consent context
                                if (parent && (text.includes('accept') || text.includes('allow') || 
                                    text.includes('agree') || text.includes('ok') || text.includes('got it') ||
                                    ariaLabel.includes('accept') || ariaLabel.includes('allow'))) {
                                    el.click();
                                    dismissed++;
                                    console.log('Accepted cookies:', text || ariaLabel);
                                }
                            }
                        }
                    } catch (e) {}
                }
                
                // PHASE 2: Address validation popups - CLICK OK/CORRECT/USE THIS ADDRESS
                const addressPopupButtons = [
                    'button:has-text("OK")', 'button:has-text("Correct")',
                    'button:has-text("Use this address")', 'button:has-text("Use suggested")',
                    'button:has-text("Continue with this address")',
                    'button:has-text("Keep this address")', 'button:has-text("Confirm")',
                    '[class*="address"] button:has-text("OK")',
                    '[class*="address"] button:has-text("Correct")',
                    '[class*="suggestion"] button:has-text("Use")'
                ];
                
                for (const selector of addressPopupButtons) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            if (el.offsetParent !== null && typeof el.click === 'function') {
                                const parent = el.closest('[role="dialog"], .modal, [class*="popup"], [class*="address"]');
                                if (parent) {
                                    const text = (el.textContent || '').toLowerCase().trim();
                                    if (text === 'ok' || text === 'correct' || text.includes('use') || text === 'confirm') {
                                        el.click();
                                        dismissed++;
                                        console.log('Clicked address popup button:', text);
                                    }
                                }
                            }
                        }
                    } catch (e) {}
                }
                
                // PHASE 3: Floating chat widgets - REMOVE (don't click, just hide)
                const chatWidgetSelectors = [
                    '#intercom-container', '.intercom-launcher', '[class*="intercom"]',
                    '#drift-widget', '.drift-frame-controller', '[class*="drift"]',
                    '#hubspot-messages-iframe-container', '[id*="hubspot"]',
                    '.crisp-client', '[class*="crisp"]', '#crisp-chatbox',
                    '.tawk-min-container', '[class*="tawk"]',
                    '.livechat-container', '[class*="livechat"]',
                    '[class*="chat-widget"]', '[id*="chat-widget"]',
                    '[class*="messenger"]', '[id*="messenger"]',
                    'iframe[title*="chat" i]', 'iframe[title*="messenger" i]'
                ];
                
                for (const selector of chatWidgetSelectors) {
                    try {
                        const widgets = document.querySelectorAll(selector);
                        widgets.forEach(widget => {
                            widget.style.display = 'none';
                            widget.style.visibility = 'hidden';
                            widget.remove();
                            dismissed++;
                            console.log('Removed chat widget:', selector);
                        });
                    } catch (e) {}
                }
                
                // PHASE 4: Modals, Promos, Geolocation - CLICK X BUTTON (top right close)
                const closeButtonSelectors = [
                    // X buttons specifically
                    'button:has-text("×")', 'button:has-text("✕")',
                    'button:has-text("✖")', 'button:has-text("⨉")',
                    '[aria-label*="close" i]', '[aria-label*="dismiss" i]',
                    '[data-dismiss]', '[data-dismiss="modal"]',
                    '.modal-close', '.popup-close', '.overlay-close',
                    'button[class*="close"]', '.close-button', '.btn-close',
                    '[data-drawer-action="close"]', '.drawer__close',
                    // Newsletter/promo specific close buttons
                    '[class*="newsletter"] button[class*="close"]',
                    '[class*="promo"] button[class*="close"]',
                    '[class*="discount"] button[class*="close"]',
                    '[class*="offer"] button[class*="close"]',
                    // Geolocation close buttons
                    '[class*="geolocation"] button[class*="close"]',
                    '[class*="location"] button[class*="close"]',
                    '[class*="region"] button[class*="close"]',
                    // Generic modal close
                    '[role="dialog"] button[class*="close"]',
                    '.modal button[class*="close"]',
                    '.popup button[class*="close"]'
                ];
                
                for (const selector of closeButtonSelectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            if (el.offsetParent !== null && typeof el.click === 'function') {
                                const text = (el.textContent || '').toLowerCase().trim();
                                const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
                                const className = (el.className || '').toLowerCase();
                                
                                // Skip if it's a cookie accept button (already handled)
                                const isCookieContext = el.closest('[class*="cookie"], [id*="cookie"]');
                                if (isCookieContext && (text.includes('accept') || text.includes('allow'))) {
                                    continue;
                                }
                                
                                // Click X buttons or close buttons
                                const isCloseButton = 
                                    text === '×' || text === '✕' || text === '✖' || text === '⨉' ||
                                    text === 'close' || text === 'dismiss' ||
                                    ariaLabel.includes('close') || ariaLabel.includes('dismiss') ||
                                    className.includes('close') || className.includes('dismiss') ||
                                    el.hasAttribute('data-dismiss') || el.hasAttribute('data-drawer-action');
                                
                                if (isCloseButton) {
                                    el.click();
                                    dismissed++;
                                    console.log('Clicked close button:', selector);
                                }
                            }
                        }
                    } catch (e) {}
                }
                
                // PHASE 5: "No thanks" / "Skip" buttons for newsletters, surveys, etc.
                const dismissTextButtons = [
                    'button:has-text("No thanks")', 'button:has-text("No Thanks")',
                    'button:has-text("Skip")', 'button:has-text("Maybe later")',
                    'button:has-text("Not now")', 'button:has-text("Later")',
                    'button:has-text("Dismiss")', 'button:has-text("Close")',
                    'button:has-text("Continue shopping")',
                    'button:has-text("Stay here")', 'button:has-text("Keep shopping")'
                ];
                
                for (const selector of dismissTextButtons) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            if (el.offsetParent !== null && typeof el.click === 'function') {
                                el.click();
                                dismissed++;
                                console.log('Clicked dismiss button:', el.textContent.trim());
                            }
                        }
                    } catch (e) {}
                }
                
                // PHASE 6: Click outside modal to dismiss (for dismissible overlays)
                try {
                    const modals = document.querySelectorAll('[role="dialog"], .modal, [class*="modal"], [class*="popup"]');
                    modals.forEach(modal => {
                        const backdrop = modal.previousElementSibling || modal.parentElement;
                        if (backdrop && (backdrop.classList.contains('backdrop') || 
                            backdrop.classList.contains('overlay') ||
                            backdrop.hasAttribute('data-backdrop'))) {
                            // Click on backdrop to dismiss
                            backdrop.click();
                            dismissed++;
                            console.log('Clicked outside modal to dismiss');
                        }
                    });
                } catch (e) {}
                // PHASE 7: Image captcha dismissal - click outside captcha area
                try {
                    const captchas = document.querySelectorAll('iframe[src*="captcha"], div[class*="captcha"], div[id*="captcha"]');
                    if (captchas.length > 0) {
                        // Click a safe area (top-left corner) to dismiss the captcha overlay
                        // Use Playwright mouse click via page.mouse after evaluating
                        // We'll signal to the Python side by returning a flag
                        window.__captchaDetected = true;
                    }
                } catch (e) {}
                
                // PHASE 8: Remove overlay/backdrop elements
                try {
                    const overlays = document.querySelectorAll(
                        '.overlay, .backdrop, [data-backdrop], [class*="modal-backdrop"], ' +
                        '[class*="overlay-backdrop"], .drawer-overlay, [data-overlay], ' +
                        '[class*="modal-overlay"], [class*="popup-overlay"]'
                    );
                    overlays.forEach(overlay => {
                        if (overlay.offsetParent !== null) {
                            overlay.style.display = 'none';
                            overlay.remove();
                            dismissed++;
                        }
                    });
                } catch (e) {}
                
                // PHASE 8: Sticky banners (promotional)
                const stickyElements = document.querySelectorAll('[style*="position: fixed"], [style*="position: sticky"]');
                stickyElements.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const isTopBanner = rect.top === 0 && rect.height < 150;
                    const isBottomBanner = rect.bottom === window.innerHeight && rect.height < 150;
                    
                    const text = (el.textContent || '').toLowerCase();
                    if ((isTopBanner || isBottomBanner) && 
                        (text.includes('subscribe') || text.includes('newsletter') || 
                         text.includes('discount') || text.includes('promo'))) {
                        el.style.display = 'none';
                        el.remove();
                        dismissed++;
                        console.log('Removed sticky banner');
                    }
                });
                
                // PHASE 9: High z-index blocking overlays
                try {
                    const allElements = document.querySelectorAll('*');
                    allElements.forEach(el => {
                        const zIndex = parseInt(window.getComputedStyle(el).zIndex);
                        if (zIndex > 9000) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > window.innerWidth * 0.8 && rect.height > window.innerHeight * 0.8) {
                                el.style.display = 'none';
                                el.remove();
                                dismissed++;
                                console.log('Removed high z-index overlay');
                            }
                        }
                    });
                } catch (e) {}
                
                // Press Escape key
                document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
                document.dispatchEvent(new KeyboardEvent('keyup', {key: 'Escape', bubbles: true, cancelable: true}));
                
                // Remove aria-hidden from body
                try {
                    document.body.removeAttribute('aria-hidden');
                    document.body.style.overflow = '';
                    document.documentElement.style.overflow = '';
                } catch (e) {}
                
                return dismissed;
            }
        """)
        
        # If an image captcha overlay was detected, click outside to dismiss
        try:
            captcha_detected = await page.evaluate("() => !!window.__captchaDetected")
            if captcha_detected:
                # Click a safe area (top-left corner) to close the captcha overlay
                await page.mouse.click(10, 10)
                dismissed_count += 1  # Increment Python-side counter
                print('✅ Clicked outside image captcha to dismiss')
        except Exception as e:
            print(f"   ⚠️ Error handling captcha dismissal: {e}")
        
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