"""
Smart Form Filler - Efficient sequential form filling with field tracking
Handles dynamic forms where fields appear after filling previous fields
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from playwright.async_api import Page
from shared.logger_config import setup_logger, log

logger = setup_logger('smart_form_filler')


def get_country_from_state(state: str) -> str:
    """Map state/province to country code"""
    if not state:
        return 'US'
    
    state_upper = state.upper().strip()
    
    # US States (abbreviations and full names)
    us_states = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA',
        'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK',
        'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
        'ALABAMA', 'ALASKA', 'ARIZONA', 'ARKANSAS', 'CALIFORNIA', 'COLORADO', 'CONNECTICUT', 'DELAWARE', 'FLORIDA',
        'GEORGIA', 'HAWAII', 'IDAHO', 'ILLINOIS', 'INDIANA', 'IOWA', 'KANSAS', 'KENTUCKY', 'LOUISIANA', 'MAINE',
        'MARYLAND', 'MASSACHUSETTS', 'MICHIGAN', 'MINNESOTA', 'MISSISSIPPI', 'MISSOURI', 'MONTANA', 'NEBRASKA',
        'NEVADA', 'NEW HAMPSHIRE', 'NEW JERSEY', 'NEW MEXICO', 'NEW YORK', 'NORTH CAROLINA', 'NORTH DAKOTA', 'OHIO',
        'OKLAHOMA', 'OREGON', 'PENNSYLVANIA', 'RHODE ISLAND', 'SOUTH CAROLINA', 'SOUTH DAKOTA', 'TENNESSEE', 'TEXAS',
        'UTAH', 'VERMONT', 'VIRGINIA', 'WASHINGTON', 'WEST VIRGINIA', 'WISCONSIN', 'WYOMING'
    }
    
    # Indian States
    indian_states = {
        'ANDHRA PRADESH', 'ARUNACHAL PRADESH', 'ASSAM', 'BIHAR', 'CHHATTISGARH', 'GOA', 'GUJARAT', 'HARYANA',
        'HIMACHAL PRADESH', 'JHARKHAND', 'KARNATAKA', 'KERALA', 'MADHYA PRADESH', 'MAHARASHTRA', 'MANIPUR',
        'MEGHALAYA', 'MIZORAM', 'NAGALAND', 'ODISHA', 'PUNJAB', 'RAJASTHAN', 'SIKKIM', 'TAMIL NADU', 'TELANGANA',
        'TRIPURA', 'UTTAR PRADESH', 'UTTARAKHAND', 'WEST BENGAL', 'AP', 'AR', 'AS', 'BR', 'CG', 'GA', 'GJ', 'HR',
        'HP', 'JH', 'KA', 'KL', 'MP', 'MH', 'MN', 'ML', 'MZ', 'NL', 'OD', 'PB', 'RJ', 'SK', 'TN', 'TS', 'TR', 'UP', 'UK', 'WB'
    }
    
    # Canadian Provinces
    canadian_provinces = {
        'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT',
        'ALBERTA', 'BRITISH COLUMBIA', 'MANITOBA', 'NEW BRUNSWICK', 'NEWFOUNDLAND', 'NOVA SCOTIA',
        'NORTHWEST TERRITORIES', 'NUNAVUT', 'ONTARIO', 'PRINCE EDWARD ISLAND', 'QUEBEC', 'SASKATCHEWAN', 'YUKON'
    }
    
    # Australian States
    australian_states = {
        'NSW', 'VIC', 'QLD', 'SA', 'WA', 'TAS', 'NT', 'ACT',
        'NEW SOUTH WALES', 'VICTORIA', 'QUEENSLAND', 'SOUTH AUSTRALIA', 'WESTERN AUSTRALIA', 'TASMANIA',
        'NORTHERN TERRITORY', 'AUSTRALIAN CAPITAL TERRITORY'
    }
    
    if state_upper in us_states:
        return 'US'
    elif state_upper in indian_states:
        return 'IN'
    elif state_upper in canadian_provinces:
        return 'CA'
    elif state_upper in australian_states:
        return 'AU'
    
    # Default to US
    return 'US'


class SmartFormFiller:
    """Tracks field appearances and fills forms efficiently"""
    
    def __init__(self, page: Page, customer_data: Dict[str, Any]):
        self.page = page
        self.customer_data = customer_data
        self.filled_fields = set()  # Track which fields we've already filled
        
    async def fill_checkout_form(self) -> Dict[str, Any]:
        """
        Fill checkout form in optimal order with continue button handling
        Returns: {'success': bool, 'filled_count': int, 'errors': List[str]}
        """
        from phase2.checkout_dom_finder import fill_input_field, find_and_click_button, find_and_select_dropdown
        from shared.checkout_keywords import (
            EMAIL_LABELS, FIRST_NAME_LABELS, LAST_NAME_LABELS, PHONE_LABELS,
            ADDRESS_LINE1_LABELS, CITY_LABELS, STATE_LABELS, POSTAL_CODE_LABELS,
            COUNTRY_LABELS, CONTINUE_BUTTONS
        )
        
        contact = self.customer_data.get('contact', {})
        address = self.customer_data.get('shippingAddress', {})
        
        # Infer country from state if not provided
        country = address.get('country')
        if not country:
            state = address.get('province', '')
            country = get_country_from_state(state)
            log(logger, 'info', f"Inferred country '{country}' from state '{state}'", 'SMART_FILL', 'COUNTRY')
        
        # Define field sequence with priorities
        field_sequence = [
            {'name': 'email', 'labels': EMAIL_LABELS, 'value': contact.get('email'), 'required': True},
            {'name': 'first_name', 'labels': FIRST_NAME_LABELS, 'value': contact.get('firstName'), 'required': True},
            {'name': 'last_name', 'labels': LAST_NAME_LABELS, 'value': contact.get('lastName'), 'required': True},
            {'name': 'phone', 'labels': PHONE_LABELS, 'value': contact.get('phone'), 'required': False},
            {'name': 'country', 'labels': COUNTRY_LABELS, 'value': country, 'required': True, 'is_dropdown': True},
            {'name': 'address_line1', 'labels': ADDRESS_LINE1_LABELS, 'value': address.get('addressLine1'), 'required': True},
            {'name': 'city', 'labels': CITY_LABELS, 'value': address.get('city'), 'required': True},
            {'name': 'state', 'labels': STATE_LABELS, 'value': address.get('province'), 'required': True, 'is_dropdown': True},
            {'name': 'zip', 'labels': POSTAL_CODE_LABELS, 'value': address.get('postalCode'), 'required': True},
        ]
        
        filled_count = 0
        errors = []
        
        log(logger, 'info', f"Starting smart form fill with {len(field_sequence)} fields", 'SMART_FILL', 'START')
        
        for field_def in field_sequence:
            field_name = field_def['name']
            
            # Skip if already filled
            if field_name in self.filled_fields:
                log(logger, 'info', f"Skipping {field_name} - already filled", 'SMART_FILL', 'SKIP')
                continue
            
            # Skip if no value and not required
            if not field_def['value'] and not field_def['required']:
                log(logger, 'info', f"Skipping {field_name} - optional and no value", 'SMART_FILL', 'SKIP')
                continue
            
            # Check if field exists on current page
            field_exists = await self._check_field_exists(field_def['labels'])
            
            if not field_exists:
                log(logger, 'info', f"Field {field_name} not visible yet", 'SMART_FILL', 'NOT_VISIBLE')
                
                # Try clicking continue to reveal more fields
                continue_clicked = await self._try_click_continue()
                if continue_clicked:
                    await asyncio.sleep(1)  # Wait for new fields to appear
                    # Retry checking if field exists
                    field_exists = await self._check_field_exists(field_def['labels'])
                
                if not field_exists:
                    if field_def['required']:
                        log(logger, 'warning', f"Required field {field_name} not found", 'SMART_FILL', 'ERROR')
                    continue
            
            # Fill the field
            try:
                if field_def.get('is_dropdown'):
                    result = await find_and_select_dropdown(
                        self.page, 
                        field_def['labels'], 
                        field_def['value'],
                        max_retries=2
                    )
                else:
                    result = await fill_input_field(
                        self.page,
                        field_def['labels'],
                        field_def['value'],
                        max_retries=2
                    )
                
                if result.get('success'):
                    filled_count += 1
                    self.filled_fields.add(field_name)
                    log(logger, 'info', f"✓ Filled {field_name}: {field_def['value']}", 'SMART_FILL', 'SUCCESS')
                    
                    # Small delay after each field
                    await asyncio.sleep(0.3)
                    
                    # Check if continue button appeared after filling this field
                    await self._try_click_continue()
                    
                else:
                    error_msg = f"Failed to fill {field_name}: {result.get('error', 'Unknown')}"
                    errors.append(error_msg)
                    log(logger, 'error', error_msg, 'SMART_FILL', 'ERROR')
                    
            except Exception as e:
                error_msg = f"Exception filling {field_name}: {str(e)}"
                errors.append(error_msg)
                log(logger, 'error', error_msg, 'SMART_FILL', 'ERROR')
        
        # Final continue click attempt
        await self._try_click_continue()
        
        log(logger, 'info', f"Smart fill completed: {filled_count} fields filled, {len(errors)} errors", 'SMART_FILL', 'COMPLETE')
        
        return {
            'success': filled_count > 0,
            'filled_count': filled_count,
            'errors': errors,
            'filled_fields': list(self.filled_fields)
        }
    
    async def _check_field_exists(self, label_keywords: List[str]) -> bool:
        """Check if a field with given labels exists and is visible"""
        try:
            result = await self.page.evaluate("""
                (keywords) => {
                    const normalize = (text) => {
                        if (!text) return '';
                        return text.toLowerCase().trim().replace(/[-_\\s]/g, '');
                    };
                    
                    const fields = Array.from(document.querySelectorAll('input:not([type="hidden"]), select, textarea'));
                    
                    for (const field of fields) {
                        // Check visibility
                        if (!field.offsetParent) continue;
                        const rect = field.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        
                        // Check if already filled
                        if (field.value && field.value.trim().length > 0) continue;
                        
                        const label = field.closest('label') || document.querySelector(`label[for="${field.id}"]`);
                        const labelText = normalize(label?.textContent || '');
                        const fieldName = normalize(field.name || '');
                        const fieldId = normalize(field.id || '');
                        const placeholder = normalize(field.placeholder || '');
                        
                        const allText = labelText + fieldName + fieldId + placeholder;
                        
                        for (const keyword of keywords) {
                            const normKeyword = normalize(keyword);
                            if (allText.includes(normKeyword) && normKeyword.length > 2) {
                                return true;
                            }
                        }
                    }
                    return false;
                }
            """, label_keywords)
            
            return result
            
        except Exception as e:
            log(logger, 'error', f"Error checking field existence: {e}", 'SMART_FILL', 'ERROR')
            return False
    
    async def _try_click_continue(self) -> bool:
        """Try to click continue button if it exists"""
        from phase2.checkout_dom_finder import find_and_click_button
        from shared.checkout_keywords import CONTINUE_BUTTONS
        
        try:
            result = await find_and_click_button(self.page, CONTINUE_BUTTONS, max_retries=1)
            if result.get('success'):
                log(logger, 'info', "✓ Clicked continue button", 'SMART_FILL', 'CONTINUE')
                await asyncio.sleep(1.5)  # Wait for page transition
                return True
            return False
        except Exception:
            return False


async def smart_fill_checkout_form(page: Page, customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to fill checkout form smartly
    
    Args:
        page: Playwright page object
        customer_data: Dict with 'contact' and 'shippingAddress' keys
    
    Returns:
        Dict with success status and details
    """
    filler = SmartFormFiller(page, customer_data)
    return await filler.fill_checkout_form()
