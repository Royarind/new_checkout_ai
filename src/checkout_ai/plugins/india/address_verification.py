"""
Address Verification Handler for Indian E-commerce
Intelligently matches user's delivery address with saved addresses on site
"""
import asyncio
import logging
from playwright.async_api import Page
from typing import Optional, Dict, Any, List
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class AddressVerificationHandler:
    """Handles intelligent address verification and selection for Indian sites"""
    
    def __init__(self, page: Page):
        self.page = page
        # Thresholds for matching
        self.PIN_CODE_WEIGHT = 0.4  # PIN code is most critical
        self.CITY_WEIGHT = 0.25
        self.STREET_WEIGHT = 0.20
        self.NAME_WEIGHT = 0.15
        self.MATCH_THRESHOLD = 0.70  # 70% similarity required
    
    async def verify_and_select_address(self, target_address: Dict[str, str]) -> Dict[str, Any]:
        """
        Verify if saved address matches target, or add new address
        
        Args:
            target_address: Dict with keys:
                - firstName, lastName
                - addressLine1, addressLine2
                - city, province (state)
                - postalCode (PIN code)
                - country, phone
                
        Returns:
            Dict with success status and action taken
        """
        logger.info("🏠 Starting address verification...")
        
        # Step 1: Extract all saved addresses from page
        saved_addresses = await self._extract_saved_addresses()
        
        if not saved_addresses:
            logger.warning("   ⚠️ No saved addresses found, will add new address")
            return await self._add_new_address(target_address)
        
        logger.info(f"   Found {len(saved_addresses)} saved address(es)")
        
        # Step 2: Find best matching address
        best_match = await self._find_best_match(saved_addresses, target_address)
        
        if best_match and best_match['score'] >= self.MATCH_THRESHOLD:
            logger.info(f"   ✅ Found matching address (score: {best_match['score']:.2%})")
            logger.info(f"      Match: {best_match['address']['preview']}")
            
            # Step 3: Select the matching address
            success = await self._select_saved_address(best_match['index'])
            
            if success:
                return {
                    'success': True,
                    'action': 'selected_existing',
                    'match_score': best_match['score'],
                    'address_preview': best_match['address']['preview']
                }
            else:
                logger.warning("   ⚠️ Failed to select address, adding new")
                return await self._add_new_address(target_address)
        else:
            score = best_match['score'] if best_match else 0
            logger.info(f"   ❌ No good match (best score: {score:.2%} < {self.MATCH_THRESHOLD:.2%})")
            logger.info(f"   Will add new address")
            
            return await self._add_new_address(target_address)
    
    async def _extract_saved_addresses(self) -> List[Dict[str, Any]]:
        """Extract all saved addresses from the page"""
        try:
            addresses = await self.page.evaluate("""
                () => {
                    const addresses = [];
                    
                    // Common selectors for saved addresses
                    const selectors = [
                        '.address-card', '.saved-address', '[class*="address-item"]',
                        '[data-address-id]', '.address-list > div', '.checkout-address',
                        '[class*="AddressCard"]', '[class*="savedAddress"]'
                    ];
                    
                    let foundElements = [];
                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            foundElements = Array.from(elements);
                            break;
                        }
                    }
                    
                    foundElements.forEach((element, index) => {
                        // Extract text content
                        const text = element.textContent || '';
                        
                        // Try to parse structured data
                        const nameMatch = text.match(/([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)+)/);
                        const phoneMatch = text.match(/(\\d{10}|\\+91[\\s-]?\\d{10})/);
                        const pinMatch = text.match(/\\b(\\d{6})\\b/);
                        const cityMatch = text.match(/([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*),?\\s*([A-Z]{2,})?/);
                        
                        // Check if address is selected/active
                        const isSelected = element.classList.contains('selected') ||
                                         element.classList.contains('active') ||
                                         element.querySelector('input[type="radio"]:checked') !== null;
                        
                        addresses.push({
                            index: index,
                            text: text.replace(/\\s+/g, ' ').trim(),
                            preview: text.substring(0, 100).replace(/\\s+/g, ' ').trim(),
                            name: nameMatch ? nameMatch[0] : '',
                            phone: phoneMatch ? phoneMatch[0].replace(/\\D/g, '') : '',
                            pinCode: pinMatch ? pinMatch[1] : '',
                            city: cityMatch ? cityMatch[1] : '',
                            isSelected: isSelected,
                            element: true  // Marker that element exists
                        });
                    });
                    
                    return addresses;
                }
            """)
            
            return addresses
            
        except Exception as e:
            logger.error(f"Error extracting addresses: {e}")
            return []
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings"""
        if not str1 or not str2:
            return 0.0
        
        # Normalize
        s1 = str1.lower().strip()
        s2 = str2.lower().strip()
        
        # Exact match
        if s1 == s2:
            return 1.0
        
        # Fuzzy match using SequenceMatcher
        return SequenceMatcher(None, s1, s2).ratio()
    
    async def _find_best_match(self, saved_addresses: List[Dict], target_address: Dict) -> Optional[Dict]:
        """
        Find best matching address using weighted similarity scoring
        
        Scoring weights:
        - PIN code: 40% (most critical for Indian addresses)
        - City: 25%
        - Street address: 20%
        - Name: 15%
        """
        best_match = None
        best_score = 0.0
        
        # Normalize target address
        target_pin = target_address.get('postalCode', '').strip()
        target_city = target_address.get('city', '').strip()
        target_street = f"{target_address.get('addressLine1', '')} {target_address.get('addressLine2', '')}".strip()
        target_name = f"{target_address.get('firstName', '')} {target_address.get('lastName', '')}".strip()
        
        for addr in saved_addresses:
            score = 0.0
            
            # PIN code match (40% weight) - MOST IMPORTANT
            if target_pin and addr.get('pinCode'):
                if target_pin == addr['pinCode']:
                    score += self.PIN_CODE_WEIGHT  # Exact PIN match
                else:
                    score += 0  # No partial credit for PIN
            
            # City match (25% weight)
            if target_city and addr.get('city'):
                city_sim = self._calculate_similarity(target_city, addr['city'])
                score += city_sim * self.CITY_WEIGHT
            
            # Street address match (20% weight)
            if target_street and addr.get('text'):
                street_sim = self._calculate_similarity(target_street, addr['text'])
                score += street_sim * self.STREET_WEIGHT
            
            # Name match (15% weight)
            if target_name and addr.get('name'):
                name_sim = self._calculate_similarity(target_name, addr['name'])
                score += name_sim * self.NAME_WEIGHT
            
            logger.debug(f"   Address {addr['index']}: score={score:.2%}")
            logger.debug(f"      Preview: {addr['preview']}")
            
            if score > best_score:
                best_score = score
                best_match = {
                    'index': addr['index'],
                    'score': score,
                    'address': addr
                }
        
        return best_match
    
    async def _select_saved_address(self, address_index: int) -> bool:
        """Select a saved address by clicking it"""
        try:
            result = await self.page.evaluate("""
                (index) => {
                    const selectors = [
                        '.address-card', '.saved-address', '[class*="address-item"]',
                        '[data-address-id]', '.address-list > div'
                    ];
                    
                    let foundElements = [];
                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            foundElements = Array.from(elements);
                            break;
                        }
                    }
                    
                    if (index >= 0 && index < foundElements.length) {
                        const element = foundElements[index];
                        
                        // Try to find radio button
                        const radio = element.querySelector('input[type="radio"]');
                        if (radio && !radio.checked) {
                            radio.click();
                            return {success: true, method: 'radio'};
                        }
                        
                        // Try to find select/use button
                        const button = element.querySelector('button, a[role="button"]');
                        if (button) {
                            button.click();
                            return {success: true, method: 'button'};
                        }
                        
                        // Click the card itself
                        element.scrollIntoView({block: 'center'});
                        element.click();
                        return {success: true, method: 'card_click'};
                    }
                    
                    return {success: false, error: 'Address not found'};
                }
            """, address_index)
            
            await asyncio.sleep(1)  # Wait for UI update
            
            return result.get('success', False)
            
        except Exception as e:
            logger.error(f"Error selecting address: {e}")
            return False
    
    async def _add_new_address(self, address: Dict[str, str]) -> Dict[str, Any]:
        """Click 'Add New Address' button and signal to fill form"""
        try:
            # Find and click "Add New Address" button
            clicked = await self.page.evaluate("""
                () => {
                    const keywords = [
                        'add new address', 'add address', 'new address',
                        'add new', 'use new address', '+ add address',
                        'add a new address', 'deliver to a new address'
                    ];
                    
                    const buttons = document.querySelectorAll('button, a[role="button"], [class*="button"], [class*="btn"]');
                    
                    for (const btn of buttons) {
                        const text = (btn.textContent || '').toLowerCase().trim();
                        const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                        
                        if (keywords.some(kw => text.includes(kw) || ariaLabel.includes(kw))) {
                            const rect = btn.getBoundingClientRect();
                            const style = window.getComputedStyle(btn);
                            const isVisible = rect.width > 0 && rect.height > 0 && 
                                            style.display !== 'none';
                            
                            if (isVisible) {
                                btn.scrollIntoView({block: 'center'});
                                btn.click();
                                return {success: true, text: text};
                            }
                        }
                    }
                    
                    return {success: false};
                }
            """)
            
            if clicked.get('success'):
                await asyncio.sleep(1.5)  # Wait for form to appear
                
                logger.info(f"   ✅ Clicked 'Add New Address' button")
                
                return {
                    'success': True,
                    'action': 'add_new_address_initiated',
                    'note': 'Address form should now be visible. Agent will fill it in next step.'
                }
            else:
                logger.error("   ❌ Could not find 'Add New Address' button")
                return {
                    'success': False,
                    'action': 'add_new_failed',
                    'error': 'Add New Address button not found'
                }
                
        except Exception as e:
            logger.error(f"Error adding new address: {e}")
            return {'success': False, 'error': str(e)}


# Singleton instance
_address_verifier = None

def get_address_verifier(page: Page) -> AddressVerificationHandler:
    """Get or create address verification handler"""
    return AddressVerificationHandler(page)
