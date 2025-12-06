"""
User Profile Service
Manage user addresses, payment methods, and site credentials
"""

from typing import List, Dict, Optional
from ..db import db

class ProfileService:
    # =============== SHIPPING ADDRESSES ===============
    
    @staticmethod
    def get_shipping_addresses(user_id: int) -> List[Dict]:
        """Get all shipping addresses for user"""
        return db.execute_query("""
            SELECT * FROM shipping_addresses
            WHERE user_id = ?
            ORDER BY is_default DESC, created_at DESC
        """, (user_id,))
    
    @staticmethod
    def add_shipping_address(user_id: int, label: str, recipient_name: str,
                            address_line1: str, city: str, state_province: str,
                            postal_code: str, country: str, phone: str = None,
                            address_line2: str = None, delivery_instructions: str = None,
                            is_default: bool = False) -> int:
        """Add new shipping address"""
        
        # If setting as default, unset other defaults
        if is_default:
            db.execute_update(
                "UPDATE shipping_addresses SET is_default = 0 WHERE user_id = ?",
                (user_id,)
            )
        
        address_id = db.execute_insert("""
            INSERT INTO shipping_addresses (
                user_id, label, is_default, recipient_name, address_line1, address_line2,
                city, state_province, postal_code, country, phone, delivery_instructions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, label, 1 if is_default else 0, recipient_name, address_line1,
              address_line2, city, state_province, postal_code, country, phone,
              delivery_instructions))
        
        print(f"[OK] Added shipping address: {label} for user {user_id}")
        return address_id
    
    @staticmethod
    def delete_shipping_address(address_id: int, user_id: int) -> bool:
        """Delete shipping address"""
        rows_affected = db.execute_update(
            "DELETE FROM shipping_addresses WHERE id = ? AND user_id = ?",
            (address_id, user_id)
        )
        return rows_affected > 0
    
    # =============== PAYMENT METHODS ===============
    
    @staticmethod
    def get_payment_methods(user_id: int) -> List[Dict]:
        """Get all payment methods for user"""
        return db.execute_query("""
            SELECT * FROM payment_methods
            WHERE user_id = ?
            ORDER BY is_default DESC, created_at DESC
        """, (user_id,))
    
    @staticmethod
    def add_card(user_id: int, label: str, card_number: str, card_holder_name: str,
                expiry_month: int, expiry_year: int, cvv: str, card_brand: str = "visa",
                is_default: bool = False) -> int:
        """Add credit/debit card (stored as plain text - NO encryption for now)"""
        
        # WARNING: This stores card data in plain text!
        # Security layer is future scope as per user request
        
        if is_default:
            db.execute_update(
                "UPDATE payment_methods SET is_default = 0 WHERE user_id = ?",
                (user_id,)
            )
        
        payment_id = db.execute_insert("""
            INSERT INTO payment_methods (
                user_id, label, is_default, payment_type, card_number, card_holder_name,
                card_expiry_month, card_expiry_year, card_cvv, card_brand
            ) VALUES (?, ?, ?, 'card', ?, ?, ?, ?, ?, ?)
        """, (user_id, label, 1 if is_default else 0, card_number, card_holder_name,
              expiry_month, expiry_year, cvv, card_brand))
        
        print(f"[OK] Added card: {label} ending in {card_number[-4:]}")
        return payment_id
    
    @staticmethod
    def add_upi(user_id: int, label: str, upi_id: str, is_default: bool = False) -> int:
        """Add UPI ID (India)"""
        if is_default:
            db.execute_update(
                "UPDATE payment_methods SET is_default = 0 WHERE user_id = ?",
                (user_id,)
            )
        
        payment_id = db.execute_insert("""
            INSERT INTO payment_methods (user_id, label, is_default, payment_type, upi_id)
            VALUES (?, ?, ?, 'upi', ?)
        """, (user_id, label, 1 if is_default else 0, upi_id))
        
        print(f"[OK] Added UPI: {upi_id}")
        return payment_id
    
    @staticmethod
    def delete_payment_method(payment_id: int, user_id: int) -> bool:
        """Delete payment method"""
        rows_affected = db.execute_update(
            "DELETE FROM payment_methods WHERE id = ? AND user_id = ?",
            (payment_id, user_id)
        )
        return rows_affected > 0
    
    # =============== SITE CREDENTIALS ===============
    
    @staticmethod
    def get_site_credentials(user_id: int) -> List[Dict]:
        """Get all saved site credentials"""
        return db.execute_query("""
            SELECT id, site_domain, site_name, email, notes, last_used_at
            FROM site_credentials
            WHERE user_id = ?
            ORDER BY last_used_at DESC NULLS LAST
        """, (user_id,))
    
    @staticmethod
    def add_site_credentials(user_id: int, site_domain: str, email: str,
                            password: str, site_name: str = None,
                            notes: str = None) -> int:
        """Add site credentials (NO encryption for now)"""
        
        # Check if credentials for this site already exist
        existing = db.fetch_one(
            "SELECT id FROM site_credentials WHERE user_id = ? AND site_domain = ?",
            (user_id, site_domain)
        )
        
        if existing:
            # Update existing
            db.execute_update("""
                UPDATE site_credentials
                SET email = ?, password = ?, site_name = ?, notes = ?
                WHERE id = ?
            """, (email, password, site_name, notes, existing['id']))
            return existing['id']
        else:
            # Insert new
            cred_id = db.execute_insert("""
                INSERT INTO site_credentials (user_id, site_domain, site_name, email, password, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, site_domain, site_name, email, password, notes))
            print(f"[OK] Added credentials for {site_domain}")
            return cred_id
    
    @staticmethod
    def get_site_password(user_id: int, site_domain: str) -> Optional[Dict]:
        """Get credentials for specific site"""
        return db.fetch_one("""
            SELECT * FROM site_credentials
            WHERE user_id = ? AND site_domain = ?
        """, (user_id, site_domain))
