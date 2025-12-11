"""
Wallet Service
Manages encrypted payment methods with SQLite storage
"""
import aiosqlite
import uuid
import json
from pathlib import Path
from typing import List, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from backend.models.wallet import (
    PaymentMethod, CardCreate, UPICreate, EncryptedPaymentData
)

class WalletService:
    """Service for managing encrypted payment methods"""
    
    def __init__(self, db_path: str = "backend/storage/wallet.db", encryption_key: str = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use provided key or generate a default one (in production, user should provide)
        if encryption_key:
            self.cipher = self._create_cipher(encryption_key)
        else:
            # Default key for development (NOT SECURE FOR PRODUCTION)
            self.cipher = Fernet(Fernet.generate_key())
    
    def _create_cipher(self, password: str) -> Fernet:
        """Create Fernet cipher from password using PBKDF2"""
        # Use PBKDF2 to derive a key from password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'checkout_ai_salt',  # In production, use random salt per user
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    async def initialize(self):
        """Initialize database schema"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS payment_methods (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    encrypted_data TEXT NOT NULL,
                    label TEXT NOT NULL,
                    masked_data TEXT NOT NULL,
                    is_default INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
    
    def _mask_card(self, card_number: str) -> str:
        """Mask card number for display"""
        return f"**** **** **** {card_number[-4:]}"
    
    def _encrypt_data(self, data: dict) -> str:
        """Encrypt payment data"""
        json_data = json.dumps(data)
        encrypted = self.cipher.encrypt(json_data.encode())
        return encrypted.decode()
    
    def _decrypt_data(self, encrypted_data: str) -> dict:
        """Decrypt payment data"""
        decrypted = self.cipher.decrypt(encrypted_data.encode())
        return json.loads(decrypted.decode())
    
    async def add_card(self, card: CardCreate) -> PaymentMethod:
        """Add a new card"""
        card_id = str(uuid.uuid4())
        
        # Prepare data for encryption
        card_data = {
            "card_number": card.card_number,
            "card_holder": card.card_holder,
            "expiry_month": card.expiry_month,
            "expiry_year": card.expiry_year,
            "cvv": card.cvv
        }
        
        encrypted = self._encrypt_data(card_data)
        masked = self._mask_card(card.card_number)
        label = card.label or f"Card ending in {card.card_number[-4:]}"
        
        async with aiosqlite.connect(self.db_path) as db:
            # If this is set as default, unset other defaults
            if card.is_default:
                await db.execute("UPDATE payment_methods SET is_default = 0")
            
            await db.execute("""
                INSERT INTO payment_methods (
                    id, type, encrypted_data, label, masked_data, is_default
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (card_id, "card", encrypted, label, masked, 1 if card.is_default else 0))
            await db.commit()
        
        return PaymentMethod(
            id=card_id,
            type="card",
            label=label,
            masked_data=masked,
            is_default=card.is_default
        )
    
    async def add_upi(self, upi: UPICreate) -> PaymentMethod:
        """Add a new UPI payment method"""
        upi_id = str(uuid.uuid4())
        
        upi_data = {"upi_id": upi.upi_id}
        encrypted = self._encrypt_data(upi_data)
        label = upi.label or upi.upi_id
        
        async with aiosqlite.connect(self.db_path) as db:
            if upi.is_default:
                await db.execute("UPDATE payment_methods SET is_default = 0")
            
            await db.execute("""
                INSERT INTO payment_methods (
                    id, type, encrypted_data, label, masked_data, is_default
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (upi_id, "upi", encrypted, label, upi.upi_id, 1 if upi.is_default else 0))
            await db.commit()
        
        return PaymentMethod(
            id=upi_id,
            type="upi",
            label=label,
            masked_data=upi.upi_id,
            is_default=upi.is_default
        )
    
    async def list_payment_methods(self) -> List[PaymentMethod]:
        """List all payment methods (masked)"""
        methods = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, type, label, masked_data, is_default FROM payment_methods ORDER BY is_default DESC, created_at DESC"
            ) as cursor:
                async for row in cursor:
                    methods.append(PaymentMethod(
                        id=row['id'],
                        type=row['type'],
                        label=row['label'],
                        masked_data=row['masked_data'],
                        is_default=bool(row['is_default'])
                    ))
        return methods
    
    async def get_payment_method(self, method_id: str, decrypt: bool = False) -> Optional[dict]:
        """Get payment method (optionally decrypted)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM payment_methods WHERE id = ?", (method_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    result = {
                        "id": row['id'],
                        "type": row['type'],
                        "label": row['label'],
                        "masked_data": row['masked_data'],
                        "is_default": bool(row['is_default'])
                    }
                    
                    if decrypt:
                        decrypted = self._decrypt_data(row['encrypted_data'])
                        result["decrypted_data"] = decrypted
                    
                    return result
        return None
    
    async def delete_payment_method(self, method_id: str) -> bool:
        """Delete a payment method"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM payment_methods WHERE id = ?", (method_id,))
            await db.commit()
            return True
    
    async def set_default(self, method_id: str) -> Optional[PaymentMethod]:
        """Set a payment method as default"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE payment_methods SET is_default = 0")
            await db.execute("UPDATE payment_methods SET is_default = 1 WHERE id = ?", (method_id,))
            await db.commit()
        
        method = await self.get_payment_method(method_id)
        if method:
            return PaymentMethod(**method)
        return None

# Global instance (in production, create per-user with their encryption key)
wallet_service = WalletService()
