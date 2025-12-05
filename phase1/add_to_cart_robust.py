#!/usr/bin/env python3
"""
Robust Add to Cart Functionality
Triggered after all variants are selected and verified
Uses comprehensive keyword matching from shared.ecommerce_keywords
"""

import asyncio
import logging
from typing import Dict, Any
from playwright.async_api import Page
from shared.ecommerce_keywords import ADD_TO_CART_KEYWORDS
import re

logger = logging.getLogger(__name__)

async def add_to_cart_robust(page: Page, container_selector: str = None) -> Dict[str, Any]:
    """
    Robust add to cart that tries multiple strategies with all known keywords
    Site-specific prioritization for conflicting buttons (e.g., Ulta)
    
    Args:
        page: Playwright page object
        container_selector: Optional selector for the product container to restrict search
        
    Returns:
        Dict with 'success': bool, 'content': str, 'method': str
    """
    
    logger.info("ADD TO CART: Starting robust search")
    if container_selector:
        logger.info(f"ADD TO CART: Search restricted to container: {container_selector}")
    
    # Detect site for keyword prioritization
    current_url = page.url
    is_ulta = 'ulta.com' in current_url.lower()
    
    # Get all keywords (primary + secondary)
    all_keywords = ADD_TO_CART_KEYWORDS.all_keywords()
    
    # SITE-SPECIFIC PRIORITIZATION
    # Ulta has both "Add to bag" and "Add for ship" - prioritize shipping
    if is_ulta:
        logger.info("ADD TO CART: Detected Ulta - prioritizing Add for ship over Add to bag")
        # Move 'add for ship' to the front
        if 'add for ship' in all_keywords:
            all_keywords.remove('add for ship')
            all_keywords.insert(0, 'add for ship')
        # Remove 'add to bag' to avoid clicking wrong button
        if 'add to bag' in all_keywords:
            all_keywords.remove('add to bag')
            logger.info("ADD TO CART: Removed add to bag from search (conflicts with add for ship)")
    
    logger.info(f"ADD TO CART: Searching with {len(all_keywords)} keywords")
    if is_ulta:
        logger.info(f"ADD TO CART: Priority keywords - {all_keywords[:3]}")
    
    # Strategy 0: Playwright Native Locators (Most Robust)
    logger.info("ADD TO CART: Strategy 0 - Trying Playwright native locators")
    try:
        # Common add to cart regex patterns
        patterns = [
            re.compile(r"add\s*to\s*(cart|bag|basket)", re.IGNORECASE),
            re.compile(r"^add$", re.IGNORECASE),
            re.compile(r"buy\s*now", re.IGNORECASE),
            re.compile(r"checkout", re.IGNORECASE)
        ]
        
        # Determine search root
        search_root = page.locator(container_selector) if container_selector else page

        for pattern in patterns:
            # Try button role first
            button = search_root.get_by_role("button", name=pattern).first
            if await button.is_visible():
                logger.info(f"ADD TO CART: Found button via locator - {pattern.pattern}")
                # Scroll into view if needed
                await button.scroll_into_view_if_needed()
                await button.click()
                
                # Dismiss potential modals
                await _dismiss_protection_modal(page)
                
                return {
                    'success': True, 
                    'method': 'locator_button', 
                    'content': f"Clicked button matching {pattern.pattern}"
                }
            
            # Try link role (sometimes buttons are <a> tags)
            link = search_root.get_by_role("link", name=pattern).first
            if await link.is_visible():
                logger.info(f"ADD TO CART: Found link via locator - {pattern.pattern}")
                await link.scroll_into_view_if_needed()
                await link.click()
                
                await _dismiss_protection_modal(page)
                
                return {
                    'success': True, 
                    'method': 'locator_link', 
                    'content': f"Clicked link matching {pattern.pattern}"
                }

    except Exception as e:
        logger.warning(f"ADD TO CART: Strategy 0 failed - {e}")

    # Strategy 1: Try to find button by comprehensive keyword search
    logger.info("ADD TO CART: Strategy 1 - Searching for Add to Cart button using keywords")
    
    for keyword in all_keywords:
        logger.info(f"ADD TO CART: Trying keyword - {keyword}")
        
        # Try to find button with this keyword
        result = await page.evaluate("""
            (args) => {
                const keyword = args.keyword;
                const isUlta = args.isUlta;
                
                const normalize = (text) => {
                    if (!text) return '';
                    if (typeof text !== 'string') text = String(text);
                    return text.toLowerCase().trim();
                };
                const keywordNorm = normalize(keyword);
                
                // STRICT: Only search actual buttons, not links or divs
                const selectors = [
                    'button',
                    '[role="button"]',
                    'input[type="submit"]',
                    'input[type="button"]'
                ];
                
                for (const selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    
                    for (const el of elements) {
                        // Check multiple text sources - safely handle non-strings
                        const text = normalize(el.textContent);
                        const ariaLabel = normalize(el.getAttribute('aria-label'));
                        const title = normalize(el.getAttribute('title'));
                        const value = normalize(el.getAttribute('value'));
                        
                        // STRICT: Must match in visible text or aria-label ONLY
                        // Don't match on className, id, or name to avoid false positives
                        const primarySources = [text, ariaLabel, title, value];
                        
                        for (const source of primarySources) {
                            if (source && source.includes(keywordNorm)) {
                                // Additional validation: make sure it's visible and reasonable size
                                const rect = el.getBoundingClientRect();
                                const isReasonableSize = rect.width >= 80 && rect.height >= 30;
                                const isVisible = rect.width > 0 && rect.height > 0;
                                
                                if (isVisible && isReasonableSize) {
                                    // STRICT: Verify this is likely a cart button by checking context
                                    // Reject navigation buttons, close buttons, etc.
                                    const className = normalize(el.className);
                                    const rejectPatterns = ['close', 'dismiss', 'cancel', 'back', 'prev', 'next', 'nav'];
                                    const isRejected = rejectPatterns.some(pattern => 
                                        className.includes(pattern) || text.includes(pattern)
                                    );
                                    
                                    // ULTA-SPECIFIC: If searching for "add for ship", reject "add to bag"
                                    if (isUlta && keywordNorm === 'add for ship') {
                                        if (text.includes('bag') || text.includes('pickup')) {
                                            console.log(`Skipping button "${text}" - looking for "add for ship"`);
                                            continue;
                                        }
                                    }
                                    
                                    if (!isRejected) {
                                        // Mark element
                                        el.setAttribute('data-cart-button', 'true');
                                        
                                        return {
                                            found: true,
                                            keyword: keyword,
                                            matchedText: el.textContent?.trim() || ariaLabel,
                                            tagName: el.tagName,
                                            selector: selector
                                        };
                                    }
                                }
                            }
                        }
                    }
                }
                
                return { found: false };
            }
        """, {'keyword': keyword, 'isUlta': is_ulta})
        
        if result.get('found'):
            logger.info(f"ADD TO CART: Found - {result.get('matchedText')} ({result.get('tagName')})")
            
            # Try to click it
            click_success = await _click_cart_button(page)
            
            if click_success:
                logger.info("ADD TO CART: Successfully added to cart")
                logger.info(f"ADD TO CART: Keyword - {keyword}")
                logger.info(f"ADD TO CART: Button - {result.get('matchedText')}")
                
                # Dismiss any protection/warranty modals that may appear
                await _dismiss_protection_modal(page)
                
                return {
                    'success': True,
                    'content': f"Added to cart using keyword '{keyword}'",
                    'method': 'keyword_search',
                    'keyword': keyword
                }
    
    # Strategy 2: Try pattern matching with common button patterns
    logger.info("ADD TO CART: Strategy 2 - Trying pattern matching")
    
    pattern_result = await page.evaluate("""
        () => {
            // Common patterns for add to cart buttons
            const patterns = [
                /add.*cart/i,
                /add.*bag/i,
                /add.*basket/i,
                /buy.*now/i,
                /purchase/i,
                /^add$/i,  // Just "add" alone
                /añadir/i,  // Spanish
                /ajouter/i  // French
            ];
            
            const buttons = document.querySelectorAll('button, a, [role="button"], input[type="submit"]');
            
            for (const btn of buttons) {
                const text = btn.textContent?.trim() || '';
                const ariaLabel = btn.getAttribute('aria-label') || '';
                const combined = text + ' ' + ariaLabel;
                
                for (const pattern of patterns) {
                    if (pattern.test(combined)) {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            btn.setAttribute('data-cart-button', 'true');
                            return {
                                found: true,
                                text: text,
                                pattern: pattern.source
                            };
                        }
                    }
                }
            }
            
            return { found: false };
        }
    """)
    
    if pattern_result.get('found'):
        logger.info(f"ADD TO CART: Pattern matched - {pattern_result.get('text')}")
        
        click_success = await _click_cart_button(page)
        
        if click_success:
            logger.info("ADD TO CART: Successfully added to cart")
            logger.info(f"ADD TO CART: Pattern - {pattern_result.get('pattern')}")
            
            return {
                'success': True,
                'content': f"Added to cart using pattern matching",
                'method': 'pattern_match'
            }
    
    # Strategy 3: Look for prominent primary buttons (often Add to Cart)
    logger.info("ADD TO CART: Strategy 3 - Searching for prominent primary buttons")
    
    primary_button_result = await page.evaluate("""
        () => {
            // Look for primary/prominent buttons
            const selectors = [
                'button.primary',
                'button[class*="primary"]',
                'button[class*="cta"]',
                'button[class*="main"]',
                '.btn-primary',
                '[class*="add"][class*="button"]',
                '[class*="button"][class*="add"]'
            ];
            
            // Blocklist for false positives (navigation, trends, etc.)
            const blocklist = ['new', 'trend', 'sale', 'story', 'read', 'learn', 'menu', 'nav', 'search', 'account', 'login', 'sign'];

            for (const selector of selectors) {
                const buttons = document.querySelectorAll(selector);
                for (const btn of buttons) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        const text = (btn.textContent?.trim() || '').toLowerCase();
                        
                        // Check blocklist
                        if (blocklist.some(bad => text.includes(bad))) continue;

                        // Check ancestors for nav/header/footer
                        let parent = btn.parentElement;
                        let isNav = false;
                        while (parent) {
                            const tag = parent.tagName.toLowerCase();
                            const cls = (parent.className || '').toString().toLowerCase();
                            if (tag === 'nav' || tag === 'header' || tag === 'footer' || 
                                cls.includes('nav') || cls.includes('header') || cls.includes('footer') || cls.includes('menu')) {
                                isNav = true;
                                break;
                            }
                            parent = parent.parentElement;
                        }
                        if (isNav) continue;

                        btn.setAttribute('data-cart-button', 'true');
                        return {
                            found: true,
                            text: btn.textContent?.trim(),
                            selector: selector
                        };
                    }
                }
            }
            
            return { found: false };
        }
    """)
    
    if primary_button_result.get('found'):
        logger.info(f"ADD TO CART: Primary button found - {primary_button_result.get('text')}")
        
        click_success = await _click_cart_button(page)
        
        if click_success:
            logger.info("ADD TO CART: Successfully added to cart")
            logger.info(f"ADD TO CART: Primary button - {primary_button_result.get('text')}")
            
            return {
                'success': True,
                'content': f"Added to cart using primary button",
                'method': 'primary_button'
            }
    
    # All strategies failed
    logger.error("ADD TO CART: Failed to add to cart")
    logger.error("ADD TO CART: Could not find Add to Cart button with any strategy")
    
    return {
        'success': False,
        'content': 'Could not find Add to Cart button',
        'method': 'none'
    }


async def _dismiss_protection_modal(page: Page):
    """Dismiss protection/warranty modals that appear after add-to-cart"""
    try:
        await asyncio.sleep(1)
        
        dismissed = await page.evaluate("""
            () => {
                // Look for modal/drawer with protection/warranty keywords
                const keywords = ['protection', 'warranty', 'insurance', 'care', 'plan'];
                const modals = document.querySelectorAll('[class*="modal"], [class*="drawer"], [class*="overlay"], [role="dialog"]');
                
                for (const modal of modals) {
                    const text = modal.textContent.toLowerCase();
                    if (keywords.some(kw => text.includes(kw))) {
                        // Find close/dismiss/no thanks button inside modal
                        const buttons = modal.querySelectorAll('button, [role="button"]');
                        for (const btn of buttons) {
                            const btnText = btn.textContent.toLowerCase();
                            if (btnText.includes('no') || btnText.includes('close') || 
                                btnText.includes('dismiss') || btnText.includes('skip') ||
                                btnText.includes('decline') || btnText.includes('cancel')) {
                                btn.click();
                                return true;
                            }
                        }
                    }
                }
                return false;
            }
        """)
        
        if dismissed:
            logger.info("ADD TO CART: Dismissed protection modal")
            await asyncio.sleep(0.5)
    except Exception as e:
        logger.debug(f"ADD TO CART: No protection modal to dismiss: {e}")


async def _click_cart_button(page: Page) -> bool:
    """
    Helper function to click the marked cart button
    Uses incremental scrolling with viewport checks - stops as soon as button is clickable
    """
    try:
        # Remove overlays that block interaction
        await page.evaluate("""
            () => {
                // Remove common overlay patterns
                const overlaySelectors = [
                    '[class*="overlay"]', '[id*="overlay"]',
                    '[class*="backdrop"]', '[id*="backdrop"]',
                    '[class*="modal-backdrop"]',
                    '.overlay', '.backdrop', '.modal-backdrop'
                ];
                
                overlaySelectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => {
                        const style = window.getComputedStyle(el);
                        // Only remove if it's blocking (high z-index, visible, covers screen)
                        if (style.position === 'fixed' || style.position === 'absolute') {
                            const zIndex = parseInt(style.zIndex);
                            if (zIndex > 0 || style.backgroundColor.includes('rgba')) {
                                console.log('Removing overlay:', el.className || el.id);
                                el.remove();
                            }
                        }
                    });
                });
                
                // Also disable pointer-events: none on body
                document.body.style.pointerEvents = 'auto';
                document.body.style.overflow = 'auto';
            }
        """)
        
        # Wait for any animations
        await asyncio.sleep(0.5)
        
        # Try Playwright's native click first (better for handling overlays)
        try:
            button = page.locator('[data-cart-button="true"]').first
            
            # Check if button is in viewport first
            is_visible = await button.is_visible()
            
            if is_visible:
                # Get button position
                box = await button.bounding_box()
                
                if box:
                    viewport_height = await page.evaluate("window.innerHeight")
                    button_center_y = box['y'] + box['height'] / 2
                    
                    # Check if button is in viewport
                    is_in_viewport = 0 <= button_center_y <= viewport_height
                    
                    if not is_in_viewport:
                        logger.info("ADD TO CART: Button not in viewport, starting incremental scroll")
                        
                        # INCREMENTAL SCROLL: Small scrolls with checks in between
                        max_scroll_attempts = 5
                        scroll_increment = viewport_height * 0.2  # Scroll 20% of viewport each time
                        
                        for attempt in range(max_scroll_attempts):
                            # Get current position
                            current_scroll = await page.evaluate("window.pageYOffset")
                            
                            # Calculate next scroll position (small increment)
                            if button_center_y > viewport_height:
                                # Button is below, scroll down
                                next_scroll = current_scroll + scroll_increment
                            else:
                                # Button is above, scroll up
                                next_scroll = current_scroll - scroll_increment
                            
                            logger.info(f"ADD TO CART: Scroll attempt {attempt + 1}/{max_scroll_attempts} - {current_scroll:.0f}px to {next_scroll:.0f}px")
                            
                            # Perform smooth scroll
                            await page.evaluate(f"window.scrollTo({{top: {next_scroll}, behavior: 'smooth'}})")
                            
                            # Wait for scroll to complete and settle
                            await asyncio.sleep(0.6)
                            
                            # CHECK: Is button in viewport now?
                            box = await button.bounding_box()
                            if box:
                                button_center_y = box['y'] + box['height'] / 2
                                is_in_viewport = 0 <= button_center_y <= viewport_height
                                
                                if is_in_viewport:
                                    logger.info(f"ADD TO CART: Button now in viewport after {attempt + 1} scroll(s)")
                                    break
                            
                            # If last attempt and still not in view
                            if attempt == max_scroll_attempts - 1:
                                logger.warning("ADD TO CART: Button still not fully in viewport, proceeding anyway")
                        
                        # Extra settling time after all scrolls
                        await asyncio.sleep(0.4)
                    else:
                        logger.info("ADD TO CART: Button already in viewport")
            
            # Wait a bit before clicking
            await asyncio.sleep(0.3)
            
            # Check if this is Karl Lagerfeld (needs special handling)
            from special_sites.karllagerfeld_automator import is_karl_lagerfeld, add_to_cart_with_double_click
            current_url = await page.evaluate("window.location.href")
            
            if is_karl_lagerfeld(current_url):
                # Use Karl Lagerfeld special handler
                success = await add_to_cart_with_double_click(page, button)
                return success
            else:
                # Check if button is a form submit button
                button_type = await button.get_attribute('type')
                form_id = await button.get_attribute('form')
                
                if button_type == 'submit' and form_id:
                    # Form submit button - trigger form submission
                    logger.info(f"ADD TO CART: Form submit button detected (form={form_id})")
                    await page.evaluate(f"document.getElementById('{form_id}').requestSubmit()")
                    logger.info("ADD TO CART: Form submitted")
                    await asyncio.sleep(2)
                    return True
                else:
                    # Normal button click
                    await button.click(timeout=5000, force=True)
                    logger.info("ADD TO CART: Button clicked successfully")
                    await asyncio.sleep(2)
                    return True
            
        except Exception as click_error:
            logger.warning(f"ADD TO CART: Playwright click failed - {click_error}, trying JS click")
        
        # Fallback: Try JavaScript click with incremental scroll
        clicked = await page.evaluate("""
            async () => {
                const button = document.querySelector('[data-cart-button="true"]');
                if (!button) return false;
                
                const viewportHeight = window.innerHeight;
                
                // Helper to check if button is in viewport
                const isInViewport = () => {
                    const rect = button.getBoundingClientRect();
                    return rect.top >= 0 && rect.bottom <= viewportHeight;
                };
                
                // If already in view, click immediately
                if (isInViewport()) {
                    console.log('Button already in view, clicking immediately');
                    try {
                        button.click();
                        return true;
                    } catch (e) {
                        console.log('Direct click failed:', e);
                        return false;
                    }
                }
                
                // INCREMENTAL SCROLL with checks
                console.log('Button not in view, starting incremental scroll...');
                const maxScrollAttempts = 5;
                const scrollIncrement = viewportHeight * 0.2;  // 20% of viewport per scroll
                
                for (let attempt = 0; attempt < maxScrollAttempts; attempt++) {
                    const currentScroll = window.pageYOffset;
                    const rect = button.getBoundingClientRect();
                    
                    // Determine scroll direction
                    let nextScroll;
                    if (rect.top > viewportHeight) {
                        // Button is below viewport
                        nextScroll = currentScroll + scrollIncrement;
                    } else if (rect.bottom < 0) {
                        // Button is above viewport
                        nextScroll = currentScroll - scrollIncrement;
                    } else {
                        // Button is partially visible, good enough
                        console.log(`Button visible after ${attempt} scroll(s)`);
                        break;
                    }
                    
                    console.log(`Scroll attempt ${attempt + 1}/${maxScrollAttempts}: ${currentScroll} → ${nextScroll}`);
                    window.scrollTo({ top: nextScroll, behavior: 'smooth' });
                    
                    // Wait for scroll and check again
                    await new Promise(resolve => setTimeout(resolve, 600));
                    
                    // Check if button is now in viewport
                    if (isInViewport()) {
                        console.log(`✅ Button in viewport after ${attempt + 1} scroll(s)`);
                        break;
                    }
                }
                
                // Wait a bit more for settling
                await new Promise(resolve => setTimeout(resolve, 400));
                
                // Try to click
                try {
                    button.click();
                    console.log('Button clicked after incremental scroll');
                    return true;
                } catch (e) {
                    console.log('Click failed after scroll:', e);
                    
                    // Last resort: dispatch mouse events
                    try {
                        const rect = button.getBoundingClientRect();
                        const events = ['mousedown', 'mouseup', 'click'];
                        events.forEach(eventType => {
                            button.dispatchEvent(new MouseEvent(eventType, {
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: rect.left + rect.width / 2,
                                clientY: rect.top + rect.height / 2
                            }));
                        });
                        console.log('Mouse events dispatched');
                        return true;
                    } catch (e2) {
                        console.log('Mouse events failed:', e2);
                        return false;
                    }
                }
            }
        """)
        
        if clicked:
            # Wait for cart update
            await asyncio.sleep(2)
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"ADD TO CART: Error clicking cart button - {e}")
        return False


# Export for use in other modules
__all__ = ['add_to_cart_robust']
