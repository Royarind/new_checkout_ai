"""Intelligent Conversation Agent for CHKout.ai - FIXED"""

import json
import sys
import os
from dotenv import load_dotenv
import re

# Load environment variables from parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(parent_dir)
load_dotenv(os.path.join(parent_dir, '.env'))

from agent.llm_client import LLMClient
from ui.services.variant_detector import detect_variants


class ConversationAgent:
    """Manages intelligent conversation and JSON building"""
    
    PROFILE_FILE = os.path.expanduser('~/.chkout_profile.json')
    
    def __init__(self):
        self.llm = LLMClient(provider='openai')
        self.history = []
        self.json_data = {'tasks': [{}]}  # Initialize with empty task
        self.state = 'INIT'
        self.current_task_index = 0
        self.detected_variants = {}
        self.saved_profile = self._load_profile()
        
    async def process_message(self, user_message):
        """Process user message and return AI response"""
        
        print(f"\n{'='*60}")
        print(f"INCOMING MESSAGE: {user_message}")
        print(f"CURRENT STATE: {self.state}")
        print(f"{'='*60}\n")
        
        # Add to history
        self.history.append({'role': 'user', 'content': user_message})
        
        # Check if URL is in message FIRST
        url_match = re.search(r'https?://[^\s]+', user_message)
        if url_match and self.state == 'INIT':
            url = url_match.group(0)
            self.json_data['tasks'][0]['url'] = url
            
            # Detect variants
            print(f"Detecting variants for: {url}")
            variant_info = await detect_variants(url)
            self.detected_variants = variant_info.get('variants', {})
            print(f"Detected variants: {self.detected_variants}")
            
            # Check if saved profile exists
            if self.saved_profile and 'customer' in self.saved_profile:
                self.json_data['customer'] = self.saved_profile['customer']
                self.state = 'CONFIRM_PROFILE'
            else:
                # Move to variants if detected, otherwise contact
                if self.detected_variants:
                    self.state = 'NEED_VARIANTS'
                else:
                    self.state = 'NEED_CONTACT'
        
        # Manual extraction (as fallback/supplement)
        manual_extracted = self._manual_extract(user_message)
        if manual_extracted:
            print(f"Manual extraction found: {manual_extracted}")
            self._update_json(manual_extracted)
        
        # Build prompt and get LLM response
        prompt = self._build_prompt(user_message)
        
        try:
            response = await self.llm.complete(prompt, max_tokens=1000)
            
            print(f"\nLLM RESPONSE:")
            print(json.dumps(response, indent=2))
            
            # Extract AI message
            if 'error' in response:
                print(f"ERROR: {response['error']}")
                ai_message = "I encountered an error. Please try again."
            else:
                ai_message = response.get('message', response.get('ai_response', 
                             response.get('text', 'Please continue.')))
            
            # Extract and merge data
            extracted_data = response.get('extracted_data', {})
            if extracted_data:
                print(f"LLM extracted: {extracted_data}")
                self._update_json(extracted_data)
            
            # Auto-progress state based on completeness
            self._auto_progress_state()
            
            # Update next_state if provided by LLM
            if 'next_state' in response and response['next_state'] != self.state:
                self.state = response['next_state']
            
            # Save profile after customer data update
            if 'customer' in self.json_data:
                self._save_profile()
            
            # Validate JSON
            validation = self._validate_json()
            print(f"\nJSON STATUS:")
            print(f"  State: {self.state}")
            print(f"  Progress: {validation['progress']}%")
            print(f"  Missing: {validation['missing']}")
            print(f"  Complete: {validation['complete']}")
            
            # Add to history
            self.history.append({'role': 'assistant', 'content': ai_message})
            
            return {
                'message': ai_message,
                'json_data': self.json_data,
                'state': self.state,
                'can_proceed': validation['complete'],
                'validation': validation
            }
            
        except Exception as e:
            print(f"\nEXCEPTION: {str(e)}")
            import traceback
            traceback.print_exc()
            
            error_msg = f"I encountered an error: {str(e)}. Please try again."
            self.history.append({'role': 'assistant', 'content': error_msg})
            return {
                'message': error_msg,
                'json_data': self.json_data,
                'state': self.state,
                'can_proceed': False
            }
    
    def _build_prompt(self, user_message):
        """Build context-aware prompt for LLM with clear extraction instructions"""
        
        # Get current data status
        task = self.json_data['tasks'][0]
        contact = self.json_data.get('customer', {}).get('contact', {})
        address = self.json_data.get('customer', {}).get('shippingAddress', {})
        
        # Build field status
        field_status = {
            'url': task.get('url', ''),
            'variants': task.get('selectedVariant', {}),
            'quantity': task.get('quantity', ''),
            'email': contact.get('email', ''),
            'firstName': contact.get('firstName', ''),
            'lastName': contact.get('lastName', ''),
            'phone': contact.get('phone', ''),
            'addressLine1': address.get('addressLine1', ''),
            'city': address.get('city', ''),
            'province': address.get('province', ''),
            'postalCode': address.get('postalCode', ''),
            'country': address.get('country', 'United States')
        }
        
        # Determine what to ask based on state
        if self.state == 'INIT':
            instruction = "Ask user for the product URL they want to buy"
            extract_fields = ['url']
            
        elif self.state == 'CONFIRM_PROFILE':
            profile_summary = f"""
Email: {contact.get('email', 'N/A')}
Name: {contact.get('firstName', '')} {contact.get('lastName', '')}
Address: {address.get('addressLine1', '')}, {address.get('city', '')}, {address.get('province', '')} {address.get('postalCode', '')}
"""
            instruction = f"Show saved profile and ask if they want to use it:\n{profile_summary}\nAsk: 'Use this profile? (yes/no)'"
            extract_fields = ['confirmation']
            
        elif self.state == 'NEED_VARIANTS':
            missing = []
            extract_fields = []
            
            if self.detected_variants:
                for variant_name, variant_options in self.detected_variants.items():
                    if variant_name not in field_status['variants']:
                        missing.append(f"{variant_name} ({', '.join(variant_options[:5])})")
                        extract_fields.append(f"selectedVariant.{variant_name}")
            
            if not field_status['quantity']:
                missing.append("Quantity")
                extract_fields.append('quantity')
            
            if missing:
                instruction = f"Ask user to specify: {' and '.join(missing)}"
            else:
                instruction = "All variants collected. Move to contact info."
                
        elif self.state == 'NEED_CONTACT':
            missing = []
            extract_fields = []
            
            if not field_status['email']:
                missing.append('Email')
                extract_fields.append('email')
            if not field_status['firstName']:
                missing.append('First Name')
                extract_fields.append('firstName')
            if not field_status['lastName']:
                missing.append('Last Name')
                extract_fields.append('lastName')
            if not field_status['phone']:
                missing.append('Phone (optional)')
                extract_fields.append('phone')
            
            if missing:
                instruction = f"Ask ONLY for: {', '.join(missing)}"
            else:
                instruction = "Contact info complete. Move to address."
                
        elif self.state == 'NEED_ADDRESS':
            missing = []
            extract_fields = []
            
            if not field_status['addressLine1']:
                missing.append('Street Address')
                extract_fields.append('addressLine1')
            if not field_status['city']:
                missing.append('City')
                extract_fields.append('city')
            if not field_status['province']:
                missing.append('State/Province')
                extract_fields.append('province')
            if not field_status['postalCode']:
                missing.append('Zip/Postal Code')
                extract_fields.append('postalCode')
            
            if missing:
                instruction = f"Ask for: {', '.join(missing)}"
            else:
                instruction = "Address complete. Ready for checkout."
                
        elif self.state == 'COMPLETE':
            instruction = "Tell user all information is collected. They can click 'Start Automation' button."
            extract_fields = []
        
        else:
            instruction = "Continue conversation naturally"
            extract_fields = []
        
        # Build conversation context
        recent_history = self._format_history()
        
        # Create structured prompt
        system_prompt = f"""You are a helpful checkout assistant. Extract information from user messages and guide them through the checkout process.

CURRENT STATE: {self.state}
USER MESSAGE: "{user_message}"

CURRENT DATA:
{json.dumps(field_status, indent=2)}

YOUR TASK: {instruction}

EXTRACTION RULES:
1. Extract ONLY the fields: {', '.join(extract_fields) if extract_fields else 'none'}
2. For variants: match user input to detected options: {json.dumps(self.detected_variants) if self.detected_variants else 'none'}
3. For quantity: extract any number mentioned
4. For contact: extract email, names, phone
5. For address: extract street, city, state, zip

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "message": "Your friendly message to user (ask for missing info or confirm)",
    "extracted_data": {{
        // Only include fields you found in the user message
        // Examples:
        // "quantity": 2,
        // "selectedVariant": {{"color": "Blue", "size": "Medium"}},
        // "email": "user@example.com",
        // "firstName": "John",
        // "lastName": "Doe",
        // "addressLine1": "123 Main St",
        // "city": "New York",
        // "province": "NY",
        // "postalCode": "10001"
    }},
    "next_state": "{self._get_next_state()}"
}}

IMPORTANT:
- Keep messages short and friendly
- Only ask for what's missing
- Extract ALL data found in user message
- Use exact field names from extraction rules
- For variants, use detected variant names as keys
"""
        
        return system_prompt
    
    def _get_next_state(self):
        """Determine next state based on current state and data completeness"""
        task = self.json_data['tasks'][0]
        contact = self.json_data.get('customer', {}).get('contact', {})
        address = self.json_data.get('customer', {}).get('shippingAddress', {})
        
        if self.state == 'INIT':
            if task.get('url'):
                if self.saved_profile:
                    return 'CONFIRM_PROFILE'
                elif self.detected_variants:
                    return 'NEED_VARIANTS'
                else:
                    return 'NEED_CONTACT'
            return 'INIT'
        
        elif self.state == 'CONFIRM_PROFILE':
            # If user confirms, go to variants/contact
            if self.detected_variants:
                return 'NEED_VARIANTS'
            return 'NEED_CONTACT'
        
        elif self.state == 'NEED_VARIANTS':
            has_variants = bool(task.get('selectedVariant')) or not self.detected_variants
            has_quantity = 'quantity' in task
            if has_variants and has_quantity:
                return 'NEED_CONTACT'
            return 'NEED_VARIANTS'
        
        elif self.state == 'NEED_CONTACT':
            if contact.get('email') and contact.get('firstName') and contact.get('lastName'):
                return 'NEED_ADDRESS'
            return 'NEED_CONTACT'
        
        elif self.state == 'NEED_ADDRESS':
            required = ['addressLine1', 'city', 'province', 'postalCode']
            if all(address.get(field) for field in required):
                return 'COMPLETE'
            return 'NEED_ADDRESS'
        
        elif self.state == 'COMPLETE':
            return 'COMPLETE'
        
        return self.state
    
    def _format_history(self):
        """Format recent conversation history"""
        formatted = []
        for msg in self.history[-4:]:  # Last 4 messages
            role = "User" if msg['role'] == 'user' else "Assistant"
            formatted.append(f"{role}: {msg['content']}")
        return "\n".join(formatted) if formatted else "No previous messages"
    
    def _update_json(self, extracted_data):
        """Update JSON with extracted data - CLEANED UP"""
        
        if not self.json_data.get('tasks'):
            self.json_data['tasks'] = [{}]
        
        task = self.json_data['tasks'][self.current_task_index]
        
        # Update URL
        if 'url' in extracted_data:
            task['url'] = extracted_data['url']
            print(f"Updated URL: {task['url']}")
        
        # Update variants
        if 'selectedVariant' in extracted_data:
            if 'selectedVariant' not in task:
                task['selectedVariant'] = {}
            task['selectedVariant'].update(extracted_data['selectedVariant'])
            print(f"Updated variants: {task['selectedVariant']}")
            
            # Add metadata structure if not exists
            if 'options' not in task:
                task['options'] = [{'name': '', 'values': []}]
            if 'metadata' not in task:
                task['metadata'] = {
                    'title': '', 'description': '', 
                    'primaryImage': '', 'price': ''
                }
        
        # Update quantity
        if 'quantity' in extracted_data:
            task['quantity'] = int(extracted_data['quantity'])
            print(f"Updated quantity: {task['quantity']}")
        
        # Update contact info
        contact_fields = ['email', 'firstName', 'lastName', 'phone']
        if any(field in extracted_data for field in contact_fields):
            if 'customer' not in self.json_data:
                self.json_data['customer'] = {}
            if 'contact' not in self.json_data['customer']:
                self.json_data['customer']['contact'] = {}
            
            for field in contact_fields:
                if field in extracted_data:
                    self.json_data['customer']['contact'][field] = extracted_data[field]
                    print(f"Updated contact.{field}: {extracted_data[field]}")
        
        # Update address
        address_fields = ['addressLine1', 'addressLine2', 'city', 'province', 'state', 'postalCode', 'country']
        if any(field in extracted_data for field in address_fields):
            if 'customer' not in self.json_data:
                self.json_data['customer'] = {}
            if 'shippingAddress' not in self.json_data['customer']:
                self.json_data['customer']['shippingAddress'] = {}
            
            for field in address_fields:
                if field in extracted_data:
                    # Map 'state' to 'province'
                    if field == 'state':
                        self.json_data['customer']['shippingAddress']['province'] = extracted_data['state']
                        print(f"Updated address.province (from state): {extracted_data['state']}")
                    else:
                        self.json_data['customer']['shippingAddress'][field] = extracted_data[field]
                        print(f"Updated address.{field}: {extracted_data[field]}")
        
        # Add default country if address exists but no country
        if 'customer' in self.json_data and 'shippingAddress' in self.json_data['customer']:
            if 'country' not in self.json_data['customer']['shippingAddress']:
                self.json_data['customer']['shippingAddress']['country'] = 'United States'
        
        # Add shipping method when complete
        if self.state == 'COMPLETE' and 'customer' in self.json_data:
            if 'shippingMethod' not in self.json_data['customer']:
                self.json_data['customer']['shippingMethod'] = {'strategy': 'cheapest'}
                print("Added shipping method: cheapest")
        
        print(f"\nJSON after update:")
        print(json.dumps(self.json_data, indent=2))
    
    def _manual_extract(self, message):
        """Manual extraction as fallback - IMPROVED"""
        extracted = {}
        msg_lower = message.lower().strip()
        
        # Extract email (always try)
        email_match = re.search(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', message)
        if email_match:
            extracted['email'] = email_match.group(0)
        
        # Extract phone (always try)
        phone_match = re.search(r'\b\+?1?[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b', message)
        if phone_match:
            extracted['phone'] = phone_match.group(0).strip()
        
        # State-specific extraction
        if self.state == 'NEED_VARIANTS':
            # Extract quantity - try to find any number
            if msg_lower.isdigit():
                extracted['quantity'] = int(msg_lower)
            else:
                qty_match = re.search(r'\b(\d+)\b', message)
                if qty_match:
                    num = int(qty_match.group(1))
                    # Only treat as quantity if it's reasonable (1-99)
                    if 1 <= num <= 99:
                        extracted['quantity'] = num
            
            # Extract variants by matching against detected options
            if self.detected_variants:
                extracted['selectedVariant'] = {}
                for variant_type, variant_options in self.detected_variants.items():
                    for option in variant_options:
                        option_lower = option.lower()
                        # Exact word match or contained match
                        if (f" {option_lower} " in f" {msg_lower} " or 
                            msg_lower == option_lower or
                            option_lower in msg_lower.split()):
                            extracted['selectedVariant'][variant_type] = option
                            break
                
                # Remove empty variant dict if nothing found
                if not extracted.get('selectedVariant'):
                    extracted.pop('selectedVariant', None)
        
        elif self.state == 'NEED_CONTACT':
            # Extract names - only if not email
            if not email_match:
                words = [w for w in message.split() if w.isalpha() and len(w) > 1]
                contact = self.json_data.get('customer', {}).get('contact', {})
                
                if len(words) == 1:
                    # Single word - first or last name
                    if not contact.get('firstName'):
                        extracted['firstName'] = words[0].title()
                    elif not contact.get('lastName'):
                        extracted['lastName'] = words[0].title()
                elif len(words) >= 2:
                    # Multiple words - first and last name
                    extracted['firstName'] = words[0].title()
                    extracted['lastName'] = words[1].title()
        
        elif self.state == 'NEED_ADDRESS':
            address = self.json_data.get('customer', {}).get('shippingAddress', {})
            
            # Extract postal code
            zip_match = re.search(r'\b\d{5}(?:-\d{4})?\b', message)
            if zip_match:
                extracted['postalCode'] = zip_match.group(0)
            
            # Extract state abbreviation
            state_match = re.search(r'\b([A-Z]{2})\b', message)
            if state_match and not zip_match:  # Don't match if it's part of zip
                extracted['province'] = state_match.group(1)
            
            # Progressive address extraction
            if not address.get('addressLine1') and not zip_match:
                # First message is likely the street address
                extracted['addressLine1'] = message
            elif address.get('addressLine1') and not address.get('city'):
                # Second message is likely city
                # Remove state and zip if present
                city = message
                city = re.sub(r'\b[A-Z]{2}\b', '', city)
                city = re.sub(r'\b\d{5}(?:-\d{4})?\b', '', city)
                city = city.strip().rstrip(',').strip()
                if city:
                    extracted['city'] = city
            elif address.get('city') and not address.get('province') and not zip_match:
                # Could be state
                if len(message.strip()) == 2:
                    extracted['province'] = message.strip().upper()
                else:
                    # Try to extract state from full name
                    extracted['province'] = message.strip()
        
        return extracted
    
    def _auto_progress_state(self):
        """Auto-progress state when requirements are met"""
        old_state = self.state
        new_state = self._get_next_state()
        
        if old_state != new_state:
            print(f"STATE TRANSITION: {old_state} → {new_state}")
            self.state = new_state
    
    def _validate_json(self):
        """Validate JSON completeness"""
        task = self.json_data.get('tasks', [{}])[0]
        contact = self.json_data.get('customer', {}).get('contact', {})
        address = self.json_data.get('customer', {}).get('shippingAddress', {})
        
        required_fields = {
            'url': bool(task.get('url')),
            'quantity': bool(task.get('quantity')),
            'email': bool(contact.get('email')),
            'firstName': bool(contact.get('firstName')),
            'lastName': bool(contact.get('lastName')),
            'addressLine1': bool(address.get('addressLine1')),
            'city': bool(address.get('city')),
            'province': bool(address.get('province')),
            'postalCode': bool(address.get('postalCode'))
        }
        
        # Add variant requirement if variants exist
        if self.detected_variants:
            required_fields['selectedVariant'] = bool(task.get('selectedVariant'))
        
        missing = [k for k, v in required_fields.items() if not v]
        complete = len(missing) == 0
        progress = int((len(required_fields) - len(missing)) / len(required_fields) * 100)
        
        return {
            'complete': complete,
            'missing': missing,
            'progress': progress,
            'fields': required_fields
        }
    
    def _load_profile(self):
        """Load saved customer profile"""
        if os.path.exists(self.PROFILE_FILE):
            try:
                with open(self.PROFILE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading profile: {e}")
        return None
    
    def _save_profile(self):
        """Save customer profile"""
        if 'customer' in self.json_data:
            try:
                with open(self.PROFILE_FILE, 'w') as f:
                    json.dump({'customer': self.json_data['customer']}, f, indent=2)
                print(f"Profile saved to {self.PROFILE_FILE}")
            except Exception as e:
                print(f"Error saving profile: {e}")
    
    def get_json(self):
        """Get current JSON data"""
        return self.json_data
    
    def reset(self):
        """Reset conversation"""
        self.history = []
        self.json_data = {'tasks': [{}]}
        self.state = 'INIT'
        self.detected_variants = {}
        self.saved_profile = self._load_profile()
        print("Conversation reset")