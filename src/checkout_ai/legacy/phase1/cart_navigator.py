#!/usr/bin/env python3
"""
Cart Navigator - Navigate to cart page after adding items
Handles cart modals, drawers, and direct cart navigation
Part of Phase 1 completion
"""

import asyncio
import logging
from typing import Dict, Any
from src.checkout_ai.dom.service import UniversalDOMFinder
from src.checkout_ai.utils.ecommerce_keywords import VIEW_CART_KEYWORDS
from playwright.async_api import Page

logger = logging.getLogger(__name__)

async def navigate_to_cart(page: Page) -> Dict[str, Any]:
    """
    Navigate to shopping cart after items have been added
    Handles different cart access patterns:
    - Cart modal/drawer with "View Cart" button
    - Direct cart icon/link in header
    - Cart URL patterns
    
    Returns:
        Dict with 'success': bool, 'cart_url': str, 'method': str
    """
    
    logger.info("CART NAVIGATION: Starting cart navigation")
    
    # Strategy 1: Check if cart modal/drawer appeared after adding item (with retry)
    for attempt in range(3):
        if attempt > 0:
            logger.info(f"CART NAVIGATION: Retry attempt {attempt + 1}/3")
            await asyncio.sleep(1)
        else:
            logger.info("CART NAVIGATION: Looking for cart modal/drawer")
        
        modal_result = await _check_cart_modal(page)
        if modal_result.get('found'):
            logger.info("CART NAVIGATION: Found cart modal/drawer")
            
            # Try to find "View Cart" button in modal
            view_cart_clicked = await _click_view_cart_in_modal(page)
            
            if view_cart_clicked:
                # Wait for navigation to cart page
                await asyncio.sleep(2)
                
                current_url = page.url
                logger.info("CART NAVIGATION: Successfully navigated to cart")
                logger.info(f"CART NAVIGATION: Method - Cart modal to View Cart button")
                logger.info(f"CART NAVIGATION: Cart URL - {current_url}")
                
                return {
                    'success': True,
                    'cart_url': current_url,
                    'method': 'modal_view_cart'
                }
            else:
                logger.warning(f"CART NAVIGATION: Attempt {attempt + 1}/3 - View Cart button not found or click failed")
        else:
            logger.warning(f"CART NAVIGATION: Attempt {attempt + 1}/3 - Cart modal not found")
    
    # Strategy 1 failed - try direct URL navigation
    logger.info("CART NAVIGATION: Strategy 1 failed, trying direct cart URL navigation")
    
    try:
        current_url = page.url
        base_url = '/'.join(current_url.split('/')[:3])
        
        cart_urls = [
            f"{base_url}/cart",
            f"{base_url}/cart/",
            f"{base_url}/shopping-cart",
            f"{base_url}/basket",
            f"{base_url}/checkout/cart"
        ]
        
        for cart_url in cart_urls:
            try:
                logger.info(f"CART NAVIGATION: Trying URL: {cart_url}")
                await page.goto(cart_url, wait_until='domcontentloaded', timeout=10000)
                await asyncio.sleep(1)
                
                is_cart = await page.evaluate("""
                    () => {
                        const text = document.body.textContent.toLowerCase();
                        const url = window.location.href.toLowerCase();
                        return url.includes('cart') || url.includes('basket') || 
                               text.includes('shopping cart') || text.includes('your cart');
                    }
                """)
                
                if is_cart:
                    logger.info("CART NAVIGATION: Successfully navigated to cart via URL")
                    logger.info(f"CART NAVIGATION: Method - Direct URL navigation")
                    logger.info(f"CART NAVIGATION: Cart URL - {page.url}")
                    return {
                        'success': True,
                        'cart_url': page.url,
                        'method': 'direct_url'
                    }
            except:
                continue
        
        logger.error("CART NAVIGATION: All cart URL attempts failed")
        
    except Exception as e:
        logger.error(f"CART NAVIGATION: Direct URL navigation error: {e}")
    
    logger.error("CART NAVIGATION: Failed to navigate to cart")
    return {
        'success': False,
        'cart_url': None,
        'method': 'none'
    }


async def _check_cart_modal(page: Page) -> Dict[str, Any]:
    """Check if a cart modal/drawer appeared after adding item"""
    try:
        # Wait a bit for modal animation to complete
        await asyncio.sleep(1)
        
        result = await page.evaluate("""
            () => {
                // Comprehensive selectors for cart modals/drawers
                const modalSelectors = [
                    // Class-based selectors
                    '[class*="cart-modal"]',
                    '[class*="cart-drawer"]',
                    '[class*="minicart"]',
                    '[class*="mini-cart"]',
                    '[class*="cart-popup"]',
                    '[class*="cart-overlay"]',
                    '[class*="shopping-cart-modal"]',
                    '[class*="bag-modal"]',
                    '[class*="mini-bag"]',
                    
                    // ID-based selectors
                    '[id*="cart-modal"]',
                    '[id*="cartModal"]',
                    '[id*="miniCart"]',
                    '[id*="mini-cart"]',
                    '[id*="cart-drawer"]',
                    
                    // Role-based selectors
                    '[role="dialog"][class*="cart"]',
                    '[role="dialog"][id*="cart"]',
                    '[role="dialog"][aria-label*="cart" i]',
                    '[role="dialog"][aria-label*="bag" i]',
                    
                    // Generic modal with cart content
                    '.modal[class*="cart"]',
                    '.drawer[class*="cart"]',
                    '.popup[class*="cart"]',
                    
                    // Data attribute selectors
                    '[data-cart-modal]',
                    '[data-minicart]',
                    '[data-cart-drawer]',
                    '[data-modal="cart"]',
                    '[data-drawer="cart"]'
                ];
                
                for (const selector of modalSelectors) {
                    const modals = document.querySelectorAll(selector);
                    
                    for (const modal of modals) {
                        // Check if visible
                        const rect = modal.getBoundingClientRect();
                        const style = window.getComputedStyle(modal);
                        const isVisible = rect.width > 0 && rect.height > 0 && 
                                        style.display !== 'none' && 
                                        style.visibility !== 'hidden' &&
                                        style.opacity !== '0';
                        
                        if (isVisible) {
                            // Additional check: modal should contain cart-related content
                            const content = modal.textContent.toLowerCase();
                            const hasCartContent = content.includes('cart') || 
                                                  content.includes('bag') || 
                                                  content.includes('item') ||
                                                  content.includes('subtotal') ||
                                                  content.includes('checkout');
                            
                            if (hasCartContent) {
                                modal.setAttribute('data-cart-modal-found', 'true');
                                console.log('Found cart modal with selector:', selector);
                                return {
                                    found: true,
                                    selector: selector
                                };
                            }
                        }
                    }
                }
                
                return { found: false };
            }
        """)
        
        return result
    except Exception as e:
        logger.warning(f"CART NAVIGATION: Error checking cart modal - {e}")
        return {'found': False}


async def _click_view_cart_in_modal(page: Page) -> bool:
    """Click 'View Cart' button in cart modal/drawer"""
    try:
        # First, debug: log all buttons in the modal
        debug_info = await page.evaluate("""
            () => {
                const modal = document.querySelector('[data-cart-modal-found="true"]');
                if (!modal) return { found: false, buttons: [] };
                
                const buttons = [];
                const elements = modal.querySelectorAll('button, a, [role="button"], [role="link"]');
                
                elements.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        buttons.push({
                            text: el.textContent?.trim(),
                            ariaLabel: el.getAttribute('aria-label'),
                            href: el.getAttribute('href'),
                            tagName: el.tagName
                        });
                    }
                });
                
                return { found: true, buttons: buttons };
            }
        """)
        
        if debug_info.get('found'):
            logger.info(f"CART NAVIGATION: Found {len(debug_info.get('buttons', []))} clickable elements in modal")
            for i, btn in enumerate(debug_info.get('buttons', [])[:5]):  # Log first 5
                logger.info(f"CART NAVIGATION: Button {i+1} - Text: {btn.get('text')}, Aria: {btn.get('ariaLabel')}, Href: {btn.get('href')}")
        
        # Get all possible keywords
        all_keywords = VIEW_CART_KEYWORDS.all_keywords()
        
        # Add common variations - CHECKOUT FIRST (most common after add-to-cart)
        additional_keywords = [
            'checkout',  # PRIORITY: Most sites show "Checkout" in modal
            'proceed to checkout',
            'go to checkout',
            'view cart',
            'view bag',
            'go to cart',
            'go to bag',
            'cart',
            'bag',
            'view'
        ]
        for kw in additional_keywords:
            if kw not in all_keywords:
                all_keywords.append(kw)
        
        logger.info(f"CART NAVIGATION: Trying {len(all_keywords)} keywords")
        
        for keyword in all_keywords:
            result = await page.evaluate("""
                (keyword) => {
                    const normalize = (text) => {
                        if (!text) return '';
                        if (typeof text !== 'string') text = String(text);
                        return text.toLowerCase().trim().replace(/[^a-z0-9\\s]/g, '');
                    };
                    
                    const modal = document.querySelector('[data-cart-modal-found="true"]');
                    if (!modal) return { found: false, reason: 'Modal not found' };
                    
                    const keywordNorm = normalize(keyword);
                    const keywordWords = keywordNorm.split(/\\s+/).filter(w => w.length > 0);
                    
                    // Comprehensive element search within modal
                    const selectors = [
                        'button',
                        'a',
                        '[role="button"]',
                        '[role="link"]',
                        'input[type="button"]',
                        'input[type="submit"]',
                        '.button',
                        '.btn',
                        'div[onclick]',
                        'span[onclick]'
                    ];
                    
                    let bestMatch = null;
                    let bestScore = 0;
                    
                    for (const selector of selectors) {
                        const elements = modal.querySelectorAll(selector);
                        
                        for (const el of elements) {
                            const text = normalize(el.textContent);
                            const ariaLabel = normalize(el.getAttribute('aria-label'));
                            const title = normalize(el.getAttribute('title'));
                            const href = normalize(el.getAttribute('href'));
                            const className = normalize(el.className);
                            
                            // Check all text sources
                            const sources = [text, ariaLabel, title, href, className];
                            
                            for (const source of sources) {
                                if (!source) continue;
                                
                                // Strategy 1: Exact phrase match
                                let isMatch = source.includes(keywordNorm);
                                
                                // Strategy 2: All words present (for multi-word keywords)
                                if (!isMatch && keywordWords.length > 1) {
                                    isMatch = keywordWords.every(word => source.includes(word));
                                }
                                
                                // Strategy 3: Partial match for single words (more flexible)
                                if (!isMatch && keywordWords.length === 1 && keywordWords[0].length >= 4) {
                                    isMatch = source.includes(keywordWords[0]);
                                }
                                
                                if (isMatch) {
                                    const rect = el.getBoundingClientRect();
                                    const style = window.getComputedStyle(el);
                                    const isVisible = rect.width > 0 && rect.height > 0 && 
                                                    style.display !== 'none' && 
                                                    style.visibility !== 'hidden';
                                    
                                    if (isVisible) {
                                        // Skip buttons with no meaningful text (empty or icon-only buttons)
                                        const hasText = text.length > 0 || ariaLabel.length > 0 || title.length > 0;
                                        if (!hasText) continue;
                                        
                                        // Calculate score based on button characteristics
                                        let score = 0;
                                        
                                        // STRONG NEGATIVE SIGNALS (exclude these completely)
                                        if (text.includes('close') || ariaLabel.includes('close')) score -= 100;
                                        if (text.includes('dismiss')) score -= 100;
                                        if (text.includes('continue shopping')) score -= 100;
                                        if (text.includes('keep shopping')) score -= 100;
                                        if (href && href.includes('/product')) score -= 100;
                                        if (text.match(/^[A-Z][a-z]+,\\s*[A-Z]$/)) score -= 100; // "Slate Grey, M" pattern
                                        if (text.match(/^(XS|S|M|L|XL|XXL)$/)) score -= 100; // Size only
                                        
                                        // POSITIVE SIGNALS (cart-related)
                                        if (text.includes('checkout') || ariaLabel.includes('checkout')) score += 50;
                                        if (text.includes('view cart') || ariaLabel.includes('view cart')) score += 40;
                                        if (text.includes('view bag') || ariaLabel.includes('view bag')) score += 40;
                                        if (text.includes('go to cart') || ariaLabel.includes('go to cart')) score += 40;
                                        if (text.includes('cart') || ariaLabel.includes('cart')) score += 20;
                                        if (text.includes('bag') || ariaLabel.includes('bag')) score += 20;
                                        if (el.tagName === 'BUTTON') score += 10;
                                        if (className.includes('checkout')) score += 15;
                                        if (className.includes('cart') && !className.includes('close')) score += 10;
                                        if (href && href.includes('checkout')) score += 20;
                                        if (href && href.includes('cart') && !href.includes('product')) score += 15;
                                        
                                        // NEGATIVE SIGNALS (likely not cart button)
                                        if (text.length > 50) score -= 30;
                                        if (el.tagName === 'A' && !href.includes('cart') && !href.includes('checkout')) score -= 20;
                                        
                                        // Only consider if score is positive
                                        if (score > bestScore) {
                                            bestScore = score;
                                            bestMatch = {
                                                element: el,
                                                text: el.textContent?.trim(),
                                                selector: selector,
                                                matchedOn: source,
                                                keyword: keyword,
                                                score: score
                                            };
                                        }
                                    }
                                }
                            }
                        }
                    }
                    
                    // Return best match if found
                    if (bestMatch && bestScore > 0) {
                        bestMatch.element.setAttribute('data-view-cart-button', 'true');
                        console.log('Best match:', bestMatch.text, '| Score:', bestMatch.score, '| Keyword:', bestMatch.keyword);
                        return {
                            found: true,
                            text: bestMatch.text,
                            selector: bestMatch.selector,
                            matchedOn: bestMatch.matchedOn,
                            keyword: bestMatch.keyword,
                            score: bestMatch.score
                        };
                    }
                    
                    return { found: false, reason: 'No matching button found' };
                }
            """, keyword)
            
            if result.get('found'):
                logger.info(f"CART NAVIGATION: Found View Cart button - {result.get('text')} (score: {result.get('score')})")
                
                # Try clicking button and parents progressively
                try:
                    click_result = await page.evaluate("""
                        () => {
                            const button = document.querySelector('[data-view-cart-button="true"]');
                            if (!button) return { success: false, reason: 'Button not found' };
                            
                            button.scrollIntoView({ block: 'center', behavior: 'instant' });
                            
                            // Build hierarchy from button up to body
                            const hierarchy = [button];
                            let parent = button.parentElement;
                            while (parent && parent !== document.body) {
                                hierarchy.push(parent);
                                parent = parent.parentElement;
                            }
                            
                            // Try clicking each level starting from button
                            for (let i = 0; i < hierarchy.length; i++) {
                                const target = hierarchy[i];
                                const tagName = target.tagName;
                                const hasOnclick = target.onclick || target.getAttribute('onclick');
                                
                                try {
                                    target.click();
                                    return { 
                                        success: true, 
                                        level: i, 
                                        tag: tagName,
                                        hadOnclick: !!hasOnclick
                                    };
                                } catch (e) {
                                    // Try mouse events
                                    try {
                                        const rect = target.getBoundingClientRect();
                                        ['mousedown', 'mouseup', 'click'].forEach(eventType => {
                                            target.dispatchEvent(new MouseEvent(eventType, {
                                                bubbles: true,
                                                cancelable: true,
                                                view: window,
                                                clientX: rect.left + rect.width / 2,
                                                clientY: rect.top + rect.height / 2
                                            }));
                                        });
                                        return { 
                                            success: true, 
                                            level: i, 
                                            tag: tagName,
                                            hadOnclick: !!hasOnclick,
                                            method: 'mouseEvents'
                                        };
                                    } catch (e2) {
                                        continue;
                                    }
                                }
                            }
                            
                            return { success: false, reason: 'All click attempts failed' };
                        }
                    """)
                    
                    if click_result.get('success'):
                        level = click_result.get('level', 0)
                        method = click_result.get('method', 'direct')
                        logger.info(f"CART NAVIGATION: Clicked successfully at level {level} using {method}")
                        return True
                    else:
                        logger.warning(f"CART NAVIGATION: {click_result.get('reason')}")
                        continue
                except Exception as e:
                    logger.warning(f"CART NAVIGATION: Click failed - {e}")
                    continue
        
        logger.warning("CART NAVIGATION: Strategy 1 failed - trying Strategy 2")
        
        # STRATEGY 2: Dismiss modal and click minicart icon in header
        try:
            logger.info("CART NAVIGATION: Attempting to dismiss modal and click minicart")
            
            # Step 1: Dismiss the modal
            dismiss_result = await page.evaluate("""
                () => {
                    const closeSelectors = [
                        '[aria-label*="close" i]', '[aria-label*="dismiss" i]',
                        'button.close', 'button[class*="close"]', '.modal-close',
                        '[data-dismiss="modal"]', '.drawer-close', '[class*="drawer-close"]'
                    ];
                    
                    for (const selector of closeSelectors) {
                        const closeBtn = document.querySelector(selector);
                        if (closeBtn) {
                            const rect = closeBtn.getBoundingClientRect();
                            const style = window.getComputedStyle(closeBtn);
                            if (rect.width > 0 && rect.height > 0 && style.display !== 'none') {
                                closeBtn.click();
                                return { dismissed: true, selector };
                            }
                        }
                    }
                    return { dismissed: false };
                }
            """)
            
            if dismiss_result.get('dismissed'):
                logger.info("CART NAVIGATION: Modal dismissed")
                await page.wait_for_timeout(500)
            
            # Step 2: Click minicart icon in header
            minicart_result = await page.evaluate("""
                () => {
                    const minicartSelectors = [
                        'a[href*="cart"]', 'button[class*="cart"]', '[class*="minicart"]',
                        '[aria-label*="cart" i]', '[data-cart-icon]', '.cart-icon',
                        'a[class*="bag"]', '[aria-label*="bag" i]'
                    ];
                    
                    for (const selector of minicartSelectors) {
                        const icons = document.querySelectorAll(selector);
                        for (const icon of icons) {
                            const rect = icon.getBoundingClientRect();
                            // Check if in header area (top 150px of page)
                            if (rect.top < 150 && rect.width > 0 && rect.height > 0) {
                                const style = window.getComputedStyle(icon);
                                if (style.display !== 'none' && style.visibility !== 'hidden') {
                                    icon.click();
                                    return { 
                                        clicked: true, 
                                        selector, 
                                        text: icon.textContent?.trim() 
                                    };
                                }
                            }
                        }
                    }
                    return { clicked: false };
                }
            """)
            
            if minicart_result.get('clicked'):
                logger.info(f"CART NAVIGATION: Clicked minicart icon - {minicart_result.get('text')}")
                return True
            else:
                logger.warning("CART NAVIGATION: No minicart icon found in header")
                return False
                
        except Exception as e:
            logger.error(f"CART NAVIGATION: Strategy 2 failed - {e}")
            return False
        
    except Exception as e:
        logger.error(f"CART NAVIGATION: Error in cart navigation - {e}")
        return False





# Export for use in other modules
__all__ = ['navigate_to_cart']
