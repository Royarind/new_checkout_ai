"""
SQLite Database Schema for CHKout.ai User System
Simplified version without encryption (security = future scope)
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# Database in project root /data directory
DATABASE_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "checkout_ai.db"

def create_database():
    """Create all database tables"""
    
    # Ensure data directory exists
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            phone TEXT,
            country TEXT DEFAULT 'US',
            preferred_currency TEXT DEFAULT 'USD',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    # Shipping addresses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shipping_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            label TEXT DEFAULT 'Home',
            is_default INTEGER DEFAULT 0,
            recipient_name TEXT NOT NULL,
            address_line1 TEXT NOT NULL,
            address_line2 TEXT,
            city TEXT NOT NULL,
            state_province TEXT,
            postal_code TEXT NOT NULL,
            country TEXT NOT NULL,
            phone TEXT,
            delivery_instructions TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Billing addresses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS billing_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            label TEXT DEFAULT 'Primary',
            is_default INTEGER DEFAULT 0,
            recipient_name TEXT NOT NULL,
            address_line1 TEXT NOT NULL,
            address_line2 TEXT,
            city TEXT NOT NULL,
            state_province TEXT,
            postal_code TEXT NOT NULL,
            country TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Payment methods (NO ENCRYPTION - stored as plain text for now)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            label TEXT DEFAULT 'My Card',
            is_default INTEGER DEFAULT 0,
            payment_type TEXT NOT NULL,
            
            -- Credit/Debit Card details (stored as-is)
            card_number TEXT,
            card_holder_name TEXT,
            card_expiry_month INTEGER,
            card_expiry_year INTEGER,
            card_cvv TEXT,
            card_brand TEXT,
            
            -- UPI details (India)
            upi_id TEXT,
            
            -- PayPal
            paypal_email TEXT,
            
            -- Billing address
            billing_address_id INTEGER,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP,
            
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (billing_address_id) REFERENCES billing_addresses (id),
            CHECK (payment_type IN ('card', 'upi', 'paypal'))
        )
    """)
    
    # Site credentials (for auto-login to ecommerce sites)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            site_domain TEXT NOT NULL,
            site_name TEXT,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            notes TEXT,
            last_used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(user_id, site_domain)
        )
    """)
    
    # Orders (purchase history)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_number TEXT,
            site_domain TEXT NOT NULL,
            site_name TEXT,
            order_url TEXT,
            
            -- Financial
            total_amount REAL NOT NULL,
            currency TEXT NOT NULL,
            tax_amount REAL,
            shipping_amount REAL,
            discount_amount REAL,
            
            -- Status
            status TEXT DEFAULT 'completed',
            payment_status TEXT DEFAULT 'paid',
            
            -- Category for analytics
            category TEXT,
            
            -- Timestamps
            ordered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivered_at TIMESTAMP,
            
            -- Store full checkout JSON
            automation_data TEXT,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # Order items
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_name TEXT,
            product_url TEXT,
            product_image_url TEXT,
            quantity INTEGER NOT NULL,
            unit_price REAL,
            total_price REAL,
            variant_details TEXT,
            category TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shipping_addresses_user ON shipping_addresses(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_methods_user ON payment_methods(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_site_credentials_user ON site_credentials(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_date ON orders(user_id, ordered_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_category ON orders(user_id, category)")
    
    conn.commit()
    conn.close()
    
    print(f"[OK] Database created at: {DATABASE_PATH}")
    return DATABASE_PATH

if __name__ == "__main__":
    create_database()
