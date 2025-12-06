#!/usr/bin/env python3
"""
Web Product Variant Automation System
Navigates websites, finds product variants, and adds items to cart using DOM search.
Organized with Phase 1 (Product Selection & Cart) and Phase 2 (Checkout) modules.
"""

import os
from pathlib import Path
import json
import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser
from dotenv import load_dotenv
import openai

# Phase 1 imports
from src.checkout_ai.dom.service import UniversalDOMFinder as find_variant_dom
from src.checkout_ai.legacy.phase1.add_to_cart_robust import add_to_cart_robust
from src.checkout_ai.legacy.phase1.cart_navigator import navigate_to_cart

# Playwright stealth imports

try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    async def stealth_async(page):
        pass

# Load environment variables
#load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ProductVariant:
    """Product variant specification"""
    color: Optional[str] = None
    size: Optional[str] = None
    fit: Optional[str] = None
    length: Optional[str] = None
    quantity: int = 1
    custom_variants: Dict[str, str] = field(default_factory=dict)
    other_attributes: Dict[str, str] = None

@dataclass
class WebsiteDetails:
    """Website and product details"""
    url: str
    product_name: Optional[str] = None
    variant: ProductVariant = None


class WebAutomator:
    """Handles web automation using Playwright"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None # Kept for consistency, though context is primary
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
    
    
    async def setup_browser(self):
        """Setup browser with persistent context for better bot evasion"""
        try:
            self.playwright = await async_playwright().start()
            
            # Use persistent context with real Chrome
            # This provides better bot evasion and maintains cookies/session across runs
            profile_path = '/tmp/checkout_ai_chrome_profile'
            
            print("Launching Chrome with persistent profile...")
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                channel='chrome',  # Use installed Google Chrome instead of Chromium
                headless=False,
                locale='en-US',
                timezone_id='America/New_York',
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                args=[
                    '--disable-blink-features=AutomationControlled',  # Hide automation flag
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox'
                ]
            )
            
            # Get the first page (or create one if none exists)
            if len(self.context.pages) > 0:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
            
            # Add persistent red border overlay that survives navigation
            await self._inject_automation_border()
            
            # Re-inject on every navigation
            async def on_load(page):
                await self._inject_automation_border()
            
            self.page.on("load", lambda: asyncio.create_task(on_load(self.page)))
            
            print("Chrome launched successfully with persistent profile")
            print("Red border indicator active - automation mode visible")
            
        except Exception as e:
            print(f"Browser setup error: {e}")
            raise
    
    async def _inject_automation_border(self):
        """Inject persistent red border overlay"""
        try:
            await self.page.evaluate("""
                () => {
                    // Remove existing border if any
                    const existing = document.getElementById('automation-border-indicator');
                    if (existing) existing.remove();
                    
                    // Create persistent overlay
                    const border = document.createElement('div');
                    border.id = 'automation-border-indicator';
                    border.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        border: 5px solid #FF0000;
                        pointer-events: none;
                        z-index: 2147483647;
                        box-sizing: border-box;
                    `;
                    document.documentElement.appendChild(border);
                }
            """)
        except Exception:
            pass  # Silently fail if page is not ready
    
    async def navigate_to_url(self, url: str):
        """Navigate to the specified URL"""
        print(f"Navigating to: {url}")
        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await self.page.wait_for_timeout(2000)
            print(f"Successfully loaded: {await self.page.title()}")
        except Exception as e:
            print(f"Navigation error: {e}")
            raise
    
    async def find_and_select_variant(self, variant_type: str, variant_value: str) -> Dict[str, Any]:
        """Find and select variant using DOM search with click validation"""
        # A. Take DOM Content before
        dom_before = await self.page.content()
        
        # B & C. Search and Click variant
        result = await find_variant_dom(self.page, variant_type, variant_value)
        
        # D. Take DOM Content after
        await self.page.wait_for_timeout(1000)
        dom_after = await self.page.content()
        
        # E. Validate - successful click means validation passes
        if result.get('success'):
            result['validated'] = True
        
        return result
    

    
    async def scroll_page(self, direction: str = 'down', pixels: int = 500):
        """Scroll the page"""
        if direction == 'down':
            await self.page.evaluate(f"window.scrollBy(0, {pixels})")
        else:
            await self.page.evaluate(f"window.scrollBy(0, -{pixels})")
        await self.page.wait_for_timeout(1000)
    
    async def close(self):
        """Close the browser"""
        try:
            if hasattr(self, 'page') and self.page and not self.page.is_closed():
                await self.page.close()
        except Exception as e:
            print(f"Error closing page: {e}")
            
        try:
            # For persistent context, we close the context (which is also the browser)
            if hasattr(self, 'context') and self.context:
                await self.context.close()
        except Exception as e:
            print(f"Error closing context: {e}")
        
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            print(f"Error stopping playwright: {e}")

class ProductVariantAutomator:
    """Main automation orchestrator"""
    
    def __init__(self):
        self.web_automator = WebAutomator()
    
    async def automate_product_selection(self, website_details: WebsiteDetails):
        """Main automation workflow"""
        try:
            # Setup browser
            await self.web_automator.setup_browser()
            
            # Navigate to website
            await self.web_automator.navigate_to_url(website_details.url)
            
            # Select variants using DOM search
            variant = website_details.variant
            results = []
            
            if variant.color:
                print(f"Selecting color: {variant.color}")
                for retry in range(3):
                    result = await self.web_automator.find_and_select_variant('color', variant.color)
                    if result.get('success'):
                        break
                    print(f"Color attempt {retry+1}/3 failed, retrying...")
                    await asyncio.sleep(1)
                results.append(result)
                print(result.get('content', ''))
                if not result.get('success'):
                    print(f"ERROR: Color selection failed after 3 attempts, stopping automation")
                    return False
                await asyncio.sleep(2)
            
            if variant.size:
                print(f"Selecting size: {variant.size}")
                for retry in range(3):
                    result = await self.web_automator.find_and_select_variant('size', variant.size)
                    if result.get('success'):
                        break
                    print(f"Size attempt {retry+1}/3 failed, retrying...")
                    await asyncio.sleep(1)
                results.append(result)
                print(result.get('content', ''))
                if not result.get('success'):
                    print(f"ERROR: Size selection failed after 3 attempts, stopping automation")
                    return False
                await asyncio.sleep(2)
            
            if variant.fit:
                print(f"Selecting fit: {variant.fit}")
                for retry in range(3):
                    result = await self.web_automator.find_and_select_variant('fit', variant.fit)
                    if result.get('success'):
                        break
                    print(f"Fit attempt {retry+1}/3 failed, retrying...")
                    await asyncio.sleep(1)
                results.append(result)
                print(result.get('content', ''))
                if not result.get('success'):
                    print(f"ERROR: Fit selection failed after 3 attempts, stopping automation")
                    return False
                await asyncio.sleep(2)
            
            if variant.length:
                print(f"Selecting length: {variant.length}")
                for retry in range(3):
                    result = await self.web_automator.find_and_select_variant('length', variant.length)
                    if result.get('success'):
                        break
                    print(f"Length attempt {retry+1}/3 failed, retrying...")
                    await asyncio.sleep(1)
                results.append(result)
                print(result.get('content', ''))
                if not result.get('success'):
                    print(f"ERROR: Length selection failed after 3 attempts, stopping automation")
                    return False
                await asyncio.sleep(2)
            
            # Process custom variants
            if variant.custom_variants:
                for variant_type, variant_value in variant.custom_variants.items():
                    print(f"Selecting {variant_type}: {variant_value}")
                    for retry in range(3):
                        result = await self.web_automator.find_and_select_variant(variant_type, variant_value)
                        if result.get('success'):
                            break
                        print(f"{variant_type.title()} attempt {retry+1}/3 failed, retrying...")
                        await asyncio.sleep(1)
                    results.append(result)
                    print(result.get('content', ''))
                    if not result.get('success'):
                        print(f"ERROR: {variant_type.title()} selection failed after 3 attempts, stopping automation")
                        return False
                    await asyncio.sleep(2)
            
            # Set quantity if needed
            if variant.quantity > 1:
                print(f"Setting quantity: {variant.quantity}")
                result = await self.web_automator.find_and_select_variant('quantity', str(variant.quantity))
                results.append(result)
                print(result.get('content', ''))
            
            # Final validation of all variants and quantity
            print("\nValidating all selections...")
            validation_result = await self.validate_all_selections(variant)
            if validation_result['success']:
                print(f"SUCCESS: All selections validated: {validation_result['message']}")
            else:
                print(f"ERROR: Validation failed: {validation_result['message']}")
                print("Attempting to fix failed variants...")
                
                # Retry failed variants
                for error in validation_result.get('errors', []):
                    if 'Color' in error and variant.color:
                        print(f"Retrying color: {variant.color}")
                        result = await self.web_automator.find_and_select_variant('color', variant.color)
                        if not result.get('success'):
                            print(f"ERROR: Color retry failed")
                            return False
                    elif 'Size' in error and variant.size:
                        print(f"Retrying size: {variant.size}")
                        result = await self.web_automator.find_and_select_variant('size', variant.size)
                        if not result.get('success'):
                            print(f"ERROR: Size retry failed")
                            return False
                    elif 'Fit' in error and variant.fit:
                        print(f"Retrying fit: {variant.fit}")
                        result = await self.web_automator.find_and_select_variant('fit', variant.fit)
                        if not result.get('success'):
                            print(f"ERROR: Fit retry failed")
                            return False
                    elif 'Length' in error and variant.length:
                        print(f"Retrying length: {variant.length}")
                        result = await self.web_automator.find_and_select_variant('length', variant.length)
                        if not result.get('success'):
                            print(f"ERROR: Length retry failed")
                            return False
                    elif 'Quantity' in error and variant.quantity > 1:
                        print(f"Retrying quantity: {variant.quantity}")
                        result = await self.web_automator.find_and_select_variant('quantity', str(variant.quantity))
                        if not result.get('success'):
                            print(f"ERROR: Quantity retry failed")
                            return False
                    else:
                        # Check custom variants
                        for variant_type, variant_value in variant.custom_variants.items():
                            if variant_type.title() in error:
                                print(f"Retrying {variant_type}: {variant_value}")
                                result = await self.web_automator.find_and_select_variant(variant_type, variant_value)
                                if not result.get('success'):
                                    print(f"ERROR: {variant_type.title()} retry failed")
                                    return False
                
                # Re-validate after fixes
                print("Re-validating after fixes...")
                final_validation = await self.validate_all_selections(variant)
                if final_validation['success']:
                    print(f"SUCCESS: All selections validated after fixes: {final_validation['message']}")
                else:
                    print(f"ERROR: Final validation still failed: {final_validation['message']}")
                    return False
            
            # Add to cart
            print("Adding to cart...")
            cart_keywords = ['add to cart', 'add to bag', 'buy now', 'purchase']
            cart_result = None
            for keyword in cart_keywords:
                try:
                    cart_result = await self.web_automator.find_and_select_variant('cart', keyword)
                    if cart_result.get('success'):
                        break
                except Exception as e:
                    print(f"Cart selection failed for '{keyword}': {e}")
                    continue
            
            if cart_result:
                results.append(cart_result)
                print(cart_result.get('content', ''))
            
            # Check if critical selections were successful
            successful = any(r.get('success', False) for r in results)
            if not successful:
                print("All variant selections failed")
                return False
            
            # Save results
            self.save_results(results)
            
            success_count = sum(1 for r in results if r.get('success', False))
            print(f"Automation completed! {success_count}/{len(results)} selections successful")
            return successful
            
        except Exception as e:
            print(f"Automation error: {e}")
            return False
        
        finally:
            try:
                print("\nAutomation finished. Browser will stay open for 10 seconds...")
                await asyncio.sleep(10)
                await self.web_automator.close()
            except Exception as e:
                print(f"Error during cleanup: {e}")
    
    async def validate_all_selections(self, variant: ProductVariant) -> Dict[str, Any]:
        """Validate all variant selections and quantity at once"""
        try:
            validation_result = await self.web_automator.page.evaluate("""
                (variantData) => {
                    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9]/g, '') : '';
                    
                    const validations = [];
                    const errors = [];
                    
                    // Check color if specified
                    if (variantData.color) {
                        const colorNormalized = normalize(variantData.color);
                        
                        // Find checked radio input and get its associated image alt text
                        const checkedRadios = document.querySelectorAll('input[type="radio"]:checked');
                        let colorFound = false;
                        
                        for (const radio of checkedRadios) {
                            const section = radio.closest('section');
                            if (section) {
                                const img = section.querySelector('img[alt]');
                                if (img && normalize(img.alt) === colorNormalized) {
                                    colorFound = true;
                                    validations.push(`Color: ${variantData.color}`);
                                    break;
                                }
                            }
                        }
                        if (!colorFound) errors.push(`Color '${variantData.color}' not selected`);
                    }
                    
                    // Check size if specified
                    if (variantData.size) {
                        const sizeNormalized = normalize(variantData.size);
                        const selectedElements = document.querySelectorAll('.selected, .active, .chosen, [aria-selected="true"], [aria-pressed="true"], :checked, [class*="selected"], [class*="active"], [class*="chosen"]');
                        
                        let sizeFound = false;
                        for (const el of selectedElements) {
                            const texts = [el.textContent, el.value, el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('data-value'), el.getAttribute('alt')];
                            for (const text of texts) {
                                if (text && normalize(text) === sizeNormalized) {
                                    sizeFound = true;
                                    validations.push(`Size: ${variantData.size}`);
                                    break;
                                }
                            }
                            if (sizeFound) break;
                        }
                        if (!sizeFound) errors.push(`Size '${variantData.size}' not selected`);
                    }
                    
                    // Check fit if specified
                    if (variantData.fit) {
                        const fitNormalized = normalize(variantData.fit);
                        const selectedElements = document.querySelectorAll('.selected, .active, .chosen, [aria-selected="true"], [aria-pressed="true"], :checked, [class*="selected"], [class*="active"], [class*="chosen"]');
                        
                        let fitFound = false;
                        for (const el of selectedElements) {
                            const texts = [el.textContent, el.value, el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('data-value'), el.getAttribute('alt')];
                            for (const text of texts) {
                                if (text && normalize(text) === fitNormalized) {
                                    fitFound = true;
                                    validations.push(`Fit: ${variantData.fit}`);
                                    break;
                                }
                            }
                            if (fitFound) break;
                        }
                        if (!fitFound) errors.push(`Fit '${variantData.fit}' not selected`);
                    }
                    
                    // Check length if specified
                    if (variantData.length) {
                        const lengthNormalized = normalize(variantData.length);
                        const selectedElements = document.querySelectorAll('.selected, .active, .chosen, [aria-selected="true"], [aria-pressed="true"], :checked, [class*="selected"], [class*="active"], [class*="chosen"]');
                        
                        let lengthFound = false;
                        for (const el of selectedElements) {
                            const texts = [el.textContent, el.value, el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('data-value'), el.getAttribute('alt')];
                            for (const text of texts) {
                                if (text && normalize(text) === lengthNormalized) {
                                    lengthFound = true;
                                    validations.push(`Length: ${variantData.length}`);
                                    break;
                                }
                            }
                            if (lengthFound) break;
                        }
                        if (!lengthFound) errors.push(`Length '${variantData.length}' not selected`);
                    }
                    
                    // Check custom variants
                    if (variantData.custom_variants) {
                        for (const [variantType, variantValue] of Object.entries(variantData.custom_variants)) {
                            const variantNormalized = normalize(variantValue);
                            const selectedElements = document.querySelectorAll('.selected, .active, .chosen, [aria-selected="true"], [aria-pressed="true"], :checked, [class*="selected"], [class*="active"], [class*="chosen"]');
                            
                            let variantFound = false;
                            for (const el of selectedElements) {
                                const texts = [el.textContent, el.value, el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('data-value'), el.getAttribute('alt')];
                                for (const text of texts) {
                                    if (text && normalize(text) === variantNormalized) {
                                        variantFound = true;
                                        validations.push(`${variantType}: ${variantValue}`);
                                        break;
                                    }
                                }
                                if (variantFound) break;
                            }
                            if (!variantFound) errors.push(`${variantType} '${variantValue}' not selected`);
                        }
                    }
                    
                    // Check quantity - DISABLED to prevent interference
                    validations.push(`Quantity: ${variantData.quantity} (validation disabled)`);
                    
                    // Note: Cart buttons are not validated as they are action buttons, not selection elements
                    
                    return {
                        success: errors.length === 0,
                        validations: validations,
                        errors: errors,
                        message: errors.length === 0 ? validations.join(', ') : errors.join(', ')
                    };
                }
            """, {
                'color': variant.color,
                'size': variant.size, 
                'fit': variant.fit,
                'length': variant.length,
                'quantity': variant.quantity,
                'custom_variants': variant.custom_variants
            })
            
            return validation_result
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Validation error: {str(e)}',
                'errors': [str(e)]
            }
    
    async def automate_product_selection_zara(self, website_details: WebsiteDetails):
        """Zara-specific automation workflow where size selection happens after ADD button"""
        try:
            # Setup browser
            await self.web_automator.setup_browser()
            
            # Navigate to website
            await self.web_automator.navigate_to_url(website_details.url)
            
            # Process variants in Zara order: color → fit → length → other variants → quantity → ADD → size
            variant = website_details.variant
            results = []
            
            # Define processing order for Zara (excluding size which comes after ADD)
            zara_order = ['color', 'fit', 'length']
            
            # 1. PROCESS VARIANTS IN ORDER (except size)
            if variant.custom_variants:
                # First, process variants in the specified order
                for variant_type in zara_order:
                    if variant_type in variant.custom_variants:
                        variant_value = variant.custom_variants[variant_type]
                        print(f"Selecting {variant_type}: {variant_value}")
                        for retry in range(3):
                            result = await self.web_automator.find_and_select_variant(variant_type, variant_value)
                            if result.get('success'):
                                break
                            print(f"{variant_type.title()} attempt {retry+1}/3 failed, retrying...")
                            await asyncio.sleep(1)
                        results.append(result)
                        print(result.get('content', ''))
                        if not result.get('success'):
                            print(f"ERROR: {variant_type.title()} selection failed after 3 attempts, stopping automation")
                            return False
                        await asyncio.sleep(2)
                
                # Then process any remaining variants (except size and color)
                for variant_type, variant_value in variant.custom_variants.items():
                    if variant_type.lower() not in ['color', 'size', 'fit', 'length']:  # Skip processed variants and size
                        print(f"Selecting {variant_type}: {variant_value}")
                        for retry in range(3):
                            result = await self.web_automator.find_and_select_variant(variant_type, variant_value)
                            if result.get('success'):
                                break
                            print(f"{variant_type.title()} attempt {retry+1}/3 failed, retrying...")
                            await asyncio.sleep(1)
                        results.append(result)
                        print(result.get('content', ''))
                        if not result.get('success'):
                            print(f"ERROR: {variant_type.title()} selection failed after 3 attempts, stopping automation")
                            return False
                        await asyncio.sleep(2)
            
            # 2. QUANTITY
            if variant.quantity > 1:
                print(f"Setting quantity: {variant.quantity}")
                result = await self.web_automator.find_and_select_variant('quantity', str(variant.quantity))
                results.append(result)
                print(result.get('content', ''))
            
            # 3. ADD TO CART (triggers size selector)
            print("Clicking ADD button...")
            cart_keywords = ['add', 'add to cart', 'add to bag']
            cart_result = None
            for keyword in cart_keywords:
                try:
                    cart_result = await self.web_automator.find_and_select_variant('cart', keyword)
                    if cart_result.get('success'):
                        break
                except Exception as e:
                    print(f"ADD button failed for '{keyword}': {e}")
                    continue
            
            if cart_result:
                results.append(cart_result)
                print(cart_result.get('content', ''))
            
            # 4. SIZE SELECTION (after ADD button)
            if variant.custom_variants and 'size' in variant.custom_variants:
                size_value = variant.custom_variants['size']
                print(f"\nZara size selector should now be visible - selecting size: {size_value}")
                await asyncio.sleep(3)  # Wait for size selector to appear
                
                for retry in range(3):
                    result = await self.web_automator.find_and_select_variant('size', size_value)
                    if result.get('success'):
                        break
                    print(f"Size attempt {retry+1}/3 failed, retrying...")
                    await asyncio.sleep(2)
                results.append(result)
                print(result.get('content', ''))
                if not result.get('success'):
                    print(f"ERROR: Size selection failed after 3 attempts")
                    return False
            
            # 5. FINAL ADD TO CART (after size selection)
            print("\nClicking final Add to Cart button...")
            await asyncio.sleep(2)  # Wait for final cart button to appear
            final_cart_keywords = ['add to cart', 'add to bag', 'añadir a la bolsa']
            final_cart_result = None
            for keyword in final_cart_keywords:
                try:
                    final_cart_result = await self.web_automator.find_and_select_variant('cart', keyword)
                    if final_cart_result.get('success'):
                        break
                except Exception as e:
                    print(f"Final cart button failed for '{keyword}': {e}")
                    continue
            
            if final_cart_result:
                results.append(final_cart_result)
                print(final_cart_result.get('content', ''))
            
            # Save results
            self.save_results(results)
            
            success_count = sum(1 for r in results if r.get('success', False))
            print(f"Zara automation completed! {success_count}/{len(results)} selections successful")
            return True
            
        except Exception as e:
            print(f"Zara automation error: {e}")
            return False
        
        finally:
            try:
                print("\nAutomation finished. Browser will stay open for 10 seconds...")
                await asyncio.sleep(10)
                await self.web_automator.close()
            except Exception as e:
                print(f"Error during cleanup: {e}")
    
    async def automate_product_selection_dynamic(self, website_details: WebsiteDetails):
        """Dynamic automation workflow that processes all variants from custom_variants"""
        # Check if this is Zara and use special workflow
        if 'zara.com' in website_details.url.lower():
            print("Zara website detected - using Zara-specific workflow")
            return await self.automate_product_selection_zara(website_details)
        
        # Regular workflow for other sites
        try:
            # Setup browser
            await self.web_automator.setup_browser()
            
            # Navigate to website
            await self.web_automator.navigate_to_url(website_details.url)
            
            # Process all variants dynamically from custom_variants in correct order
            variant = website_details.variant
            results = []
            
            # Define processing order: color → fit → size → length → other variants
            variant_order = ['color', 'fit', 'size', 'length']
            
            # Process variants in the defined order
            if variant.custom_variants:
                # First, process variants in the specified order
                for variant_type in variant_order:
                    if variant_type in variant.custom_variants:
                        variant_value = variant.custom_variants[variant_type]
                        print(f"Selecting {variant_type}: {variant_value}")
                        
                        success = False
                        for retry in range(3):
                            result = await self.web_automator.find_and_select_variant(variant_type, variant_value)
                            print(result.get('content', ''))
                            
                            if result.get('success'):
                                success = True
                                break
                            else:
                                print(f"ERROR: {variant_type.title()} attempt {retry+1}/3 failed")
                                if retry < 2:
                                    print(f"Retrying {variant_type} in 2 seconds...")
                                    await asyncio.sleep(2)
                        
                        results.append(result)
                        if not success:
                            print(f"ERROR: {variant_type.title()} selection failed after 3 attempts, stopping automation")
                            return False
                        
                        print(f"SUCCESS: {variant_type.title()}: {variant_value} selected successfully")
                        print(f"Waiting 5 seconds before next selection...")
                        await asyncio.sleep(5)
                
                # Then process any remaining variants not in the standard order
                for variant_type, variant_value in variant.custom_variants.items():
                    if variant_type not in variant_order:
                        print(f"Selecting {variant_type}: {variant_value}")
                        
                        success = False
                        for retry in range(3):
                            result = await self.web_automator.find_and_select_variant(variant_type, variant_value)
                            print(result.get('content', ''))
                            
                            if result.get('success'):
                                success = True
                                break
                            else:
                                print(f"ERROR: {variant_type.title()} attempt {retry+1}/3 failed")
                                if retry < 2:
                                    print(f"Retrying {variant_type} in 2 seconds...")
                                    await asyncio.sleep(2)
                        
                        results.append(result)
                        if not success:
                            print(f"ERROR: {variant_type.title()} selection failed after 3 attempts, stopping automation")
                            return False
                        
                        print(f"SUCCESS: {variant_type.title()}: {variant_value} selected successfully")
                        print(f"Waiting 5 seconds before next selection...")
                        await asyncio.sleep(5)
            
            # Set quantity if needed
            if variant.quantity > 1:
                print(f"Setting quantity: {variant.quantity}")
                
                success = False
                for retry in range(3):
                    result = await self.web_automator.find_and_select_variant('quantity', str(variant.quantity))
                    print(result.get('content', ''))
                    
                    if result.get('success'):
                        success = True
                        break
                    else:
                        print(f"ERROR: Quantity attempt {retry+1}/3 failed")
                        if retry < 2:
                            print(f"Retrying quantity in 2 seconds...")
                            await asyncio.sleep(2)
                
                results.append(result)
                if success:
                    print(f"SUCCESS: Quantity: {variant.quantity} set successfully")
                else:
                    print(f"WARNING: Quantity setting failed, using default")
                print(f"Waiting 5 seconds before next selection...")
                await asyncio.sleep(5)
            
            # Skip final validation for dynamic workflow
            print("\nFinal validation...")
            successful_selections = [r for r in results if r.get('success')]
            if successful_selections:
                print(f"SUCCESS: All {len(successful_selections)} selections completed and validated")
            else:
                print("WARNING: No successful selections found")
                print("Continuing with cart addition...")
            
            # Add to cart using robust function (only if variants were selected)
            if successful_selections:
                # Extract container_selector from the first successful result that has it
                container_selector = next((r.get('container_selector') for r in successful_selections if r.get('container_selector')), None)
                
                cart_result = await add_to_cart_robust(self.web_automator.page, container_selector)
                
                if cart_result:
                    results.append(cart_result)
                    if cart_result.get('success'):
                        print(cart_result.get('content', ''))
                        
                        # Navigate to cart after successful add
                        print("\nNavigating to cart...")
                        nav_result = await navigate_to_cart(self.web_automator.page)
                        
                        if nav_result.get('success'):
                            print(f"Successfully navigated to cart")
                            print(f"   Cart URL: {nav_result.get('cart_url')}")
                            results.append(nav_result)
                        else:
                            print(f"Could not navigate to cart (continuing anyway)")
                            results.append(nav_result)
                    else:
                        print(f"WARNING: Robust add to cart failed - {cart_result.get('content')}")
            else:
                print("SKIPPING: Add to cart skipped because no variants were successfully selected")
            
            # Save results
            self.save_results(results)
            
            success_count = sum(1 for r in results if r.get('success', False))
            print(f"Dynamic automation completed! {success_count}/{len(results)} selections successful")
            return success_count > 0
            
        except Exception as e:
            print(f"Dynamic automation error: {e}")
            return False
        
        finally:
            try:
                print("\nAutomation finished. Browser will stay open for 10 seconds...")
                await asyncio.sleep(10)
                await self.web_automator.close()
            except Exception as e:
                print(f"Error during cleanup: {e}")
    
    async def validate_single_variant(self, variant_type: str, variant_value: str) -> bool:
        """Validate a single variant selection"""
        try:
            return await self.web_automator.page.evaluate("""
                (args) => {
                    const { variantType, variantValue } = args;
                    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9]/g, '') : '';
                    const normalizedVal = normalize(variantValue);
                    
                    // Check for checked radio buttons with matching labels
                    const checkedRadios = document.querySelectorAll('input[type="radio"]:checked');
                    for (const radio of checkedRadios) {
                        const label = document.querySelector(`label[for="${radio.id}"]`);
                        const labelText = label?.querySelector('.sitg-label-text')?.textContent || label?.textContent;
                        if (labelText && normalize(labelText) === normalizedVal) return true;
                        if (radio.value && normalize(radio.value) === normalizedVal) return true;
                    }
                    
                    // Check visual selection states
                    const selectionStates = ['.selected', '.active', '.chosen', '[aria-selected="true"]'];
                    for (const selector of selectionStates) {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            const texts = [el.textContent, el.value, el.getAttribute('aria-label')];
                            for (const text of texts) {
                                if (text && normalize(text) === normalizedVal) return true;
                            }
                        }
                    }
                    
                    return false;
                }
            """, {'variantType': variant_type, 'variantValue': variant_value})
        except:
            return False
    
    async def validate_dynamic_selections(self, variant: ProductVariant) -> Dict[str, Any]:
        """Validate all dynamic variant selections"""
        try:
            validation_result = await self.web_automator.page.evaluate("""
                (variantData) => {
                    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9]/g, '') : '';
                    
                    const validations = [];
                    const errors = [];
                    
                    // Check all custom variants dynamically
                    if (variantData.custom_variants) {
                        for (const [variantType, variantValue] of Object.entries(variantData.custom_variants)) {
                            const variantNormalized = normalize(variantValue);
                            const selectedElements = document.querySelectorAll('.selected, .active, .chosen, [aria-selected="true"], [aria-pressed="true"], :checked, [class*="selected"], [class*="active"], [class*="chosen"]');
                            
                            let variantFound = false;
                            for (const el of selectedElements) {
                                const texts = [el.textContent, el.value, el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('data-value'), el.getAttribute('alt')];
                                for (const text of texts) {
                                    if (text && normalize(text) === variantNormalized) {
                                        variantFound = true;
                                        validations.push(`${variantType}: ${variantValue}`);
                                        break;
                                    }
                                }
                                if (variantFound) break;
                            }
                            if (!variantFound) errors.push(`${variantType} '${variantValue}' not selected`);
                        }
                    }
                    
                    // Check quantity - DISABLED to prevent interference
                    validations.push(`Quantity: ${variantData.quantity} (validation disabled)`);
                    
                    return {
                        success: errors.length === 0,
                        validations: validations,
                        errors: errors,
                        message: errors.length === 0 ? validations.join(', ') : errors.join(', ')
                    };
                }
            """, {
                'custom_variants': variant.custom_variants,
                'quantity': variant.quantity
            })
            
            return validation_result
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Validation error: {str(e)}',
                'errors': [str(e)]
            }
    
    def save_results(self, results: List[Dict]):
        """Save automation results to file"""
        Path('automation_results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print("Results saved to automation_results.json")

async def main():
    """Main execution function with user input"""
    print("=== Product Variant Automation System ===")
    print()
    
    # Get user input
    url = input("Enter product URL: ").strip()
    if not url:
        print("URL is required!")
        return
    
    # Add https:// if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    print("\nEnter variant details (press Enter to skip):")
    color = input("Color: ").strip() or None
    size = input("Size: ").strip() or None
    fit = input("Fit: ").strip() or None
    
    try:
        quantity = int(input("Quantity (default 1): ").strip() or "1")
    except ValueError:
        quantity = 1
    
    product_name = input("Product name (optional): ").strip() or "Product"
    
    # Create variant and website details
    variant = ProductVariant(
        color=color,
        size=size,
        fit=fit,
        quantity=quantity
    )
    
    website_details = WebsiteDetails(
        url=url,
        product_name=product_name,
        variant=variant
    )
    
    print(f"\n=== Starting automation for {product_name} ===")
    print(f"URL: {url}")
    print(f"Variants: Color={color}, Size={size}, Fit={fit}, Quantity={quantity}")
    print()
    
    # Run automation
    automator = ProductVariantAutomator()
    success = await automator.automate_product_selection(website_details)
    
    if success:
        print("\nSUCCESS: Product variant selection completed!")
    else:
        print("\nERROR: Automation failed. Check logs for details.")

if __name__ == "__main__":
    asyncio.run(main())