"""
Profile Service - User profile management
Handles personal info, shipping, and billing addresses
"""
from checkout_ai.db import db
from typing import Dict, Any, List, Optional

class ProfileService:
    """Service for managing user profiles and addresses"""
    
    @staticmethod
    def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
        """Get complete user profile including personal info"""
        user = db.fetch_one("""
            SELECT id, email, full_name, phone, country, preferred_currency,
                   created_at, updated_at, last_login_at
            FROM users
            WHERE id = ?
        """, (user_id,))
        
        return user
    
    @staticmethod
    def update_user_profile(user_id: int, full_name: str = None, 
                           phone: str = None, country: str = None) -> bool:
        """Update user personal information"""
        updates = []
        params = []
        
        if full_name is not None:
            updates.append("full_name = ?")
            params.append(full_name)
        
        if phone is not None:
            updates.append("phone = ?")
            params.append(phone)
        
        if country is not None:
            updates.append("country = ?")
            params.append(country)
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)
        
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        db.execute_update(query, tuple(params))
        
        return True
    
    # Shipping Addresses
    
    @staticmethod
    def get_shipping_addresses(user_id: int) -> List[Dict[str, Any]]:
        """Get all shipping addresses for user"""
        addresses = db.execute_query("""
            SELECT id, label, recipient_name, address_line1, address_line2,
                   city, state, postal_code, country, is_default
            FROM shipping_addresses
            WHERE user_id = ?
            ORDER BY is_default DESC, created_at DESC
        """, (user_id,))
        
        return addresses
    
    @staticmethod
    def get_default_shipping_address(user_id: int) -> Optional[Dict[str, Any]]:
        """Get default shipping address for user"""
        address = db.fetch_one("""
            SELECT id, label, recipient_name, address_line1, address_line2,
                   city, state, postal_code, country
            FROM shipping_addresses
            WHERE user_id = ? AND is_default = 1
        """, (user_id,))
        
        return address
    
    @staticmethod
    def add_shipping_address(user_id: int, label: str, recipient_name: str,
                            address_line1: str, city: str, state: str,
                            postal_code: str, country: str,
                            address_line2: str = "", is_default: bool = False) -> int:
        """Add new shipping address"""
        
        # If setting as default, unset other defaults
        if is_default:
            db.execute_update("""
                UPDATE shipping_addresses SET is_default = 0 WHERE user_id = ?
            """, (user_id,))
        
        address_id = db.execute_insert("""
            INSERT INTO shipping_addresses 
            (user_id, label, recipient_name, address_line1, address_line2,
             city, state, postal_code, country, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, label, recipient_name, address_line1, address_line2,
              city, state, postal_code, country, 1 if is_default else 0))
        
        return address_id
    
    @staticmethod
    def update_shipping_address(address_id: int, user_id: int, **kwargs) -> bool:
        """Update shipping address"""
        allowed_fields = ['label', 'recipient_name', 'address_line1', 'address_line2',
                         'city', 'state', 'postal_code', 'country']
        
        updates = []
        params = []
        
        for field in allowed_fields:
            if field in kwargs:
                updates.append(f"{field} = ?")
                params.append(kwargs[field])
        
        if not updates:
            return False
        
        params.extend([address_id, user_id])
        
        query = f"""
            UPDATE shipping_addresses 
            SET {', '.join(updates)}
            WHERE id = ? AND user_id = ?
        """
        
        db.execute_update(query, tuple(params))
        return True
    
    @staticmethod
    def delete_shipping_address(address_id: int, user_id: int) -> bool:
        """Delete shipping address"""
        db.execute_update("""
            DELETE FROM shipping_addresses WHERE id = ? AND user_id = ?
        """, (address_id, user_id))
        
        return True
    
    @staticmethod
    def set_default_shipping_address(address_id: int, user_id: int) -> bool:
        """Set address as default shipping"""
        # Unset all defaults
        db.execute_update("""
            UPDATE shipping_addresses SET is_default = 0 WHERE user_id = ?
        """, (user_id,))
        
        # Set new default
        db.execute_update("""
            UPDATE shipping_addresses SET is_default = 1 
            WHERE id = ? AND user_id = ?
        """, (address_id, user_id))
        
        return True
    
    # Billing Addresses (similar to shipping)
    
    @staticmethod
    def get_billing_addresses(user_id: int) -> List[Dict[str, Any]]:
        """Get all billing addresses for user"""
        addresses = db.execute_query("""
            SELECT id, label, full_name, address_line1, address_line2,
                   city, state, postal_code, country, is_default
            FROM billing_addresses
            WHERE user_id = ?
            ORDER BY is_default DESC, created_at DESC
        """, (user_id,))
        
        return addresses
    
    @staticmethod
    def get_default_billing_address(user_id: int) -> Optional[Dict[str, Any]]:
        """Get default billing address for user"""
        address = db.fetch_one("""
            SELECT id, label, full_name, address_line1, address_line2,
                   city, state, postal_code, country
            FROM billing_addresses
            WHERE user_id = ? AND is_default = 1
        """, (user_id,))
        
        return address
    
    @staticmethod
    def add_billing_address(user_id: int, label: str, full_name: str,
                           address_line1: str, city: str, state: str,
                           postal_code: str, country: str,
                           address_line2: str = "", is_default: bool = False) -> int:
        """Add new billing address"""
        
        # If setting as default, unset other defaults
        if is_default:
            db.execute_update("""
                UPDATE billing_addresses SET is_default = 0 WHERE user_id = ?
            """, (user_id,))
        
        address_id = db.execute_insert("""
            INSERT INTO billing_addresses 
            (user_id, label, full_name, address_line1, address_line2,
             city, state, postal_code, country, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, label, full_name, address_line1, address_line2,
              city, state, postal_code, country, 1 if is_default else 0))
        
        return address_id
    
    @staticmethod
    def set_default_billing_address(address_id: int, user_id: int) -> bool:
        """Set address as default billing"""
        # Unset all defaults
        db.execute_update("""
            UPDATE billing_addresses SET is_default = 0 WHERE user_id = ?
        """, (user_id,))
        
        # Set new default
        db.execute_update("""
            UPDATE billing_addresses SET is_default = 1 
            WHERE id = ? AND user_id = ?
        """, (address_id, user_id))
        
        return True
    
    @staticmethod
    def delete_billing_address(address_id: int, user_id: int) -> bool:
        """Delete billing address"""
        db.execute_update("""
            DELETE FROM billing_addresses WHERE id = ? AND user_id = ?
        """, (address_id, user_id))
        
        return True
