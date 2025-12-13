"""
Address Book Service
Manages user addresses with SQLite storage
"""
import aiosqlite
import uuid
from pathlib import Path
from typing import List, Optional
from backend.models.address import Address, AddressCreate, AddressUpdate

class AddressService:
    """Service for managing addresses"""
    
    def __init__(self, db_path: str = "backend/storage/addresses.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Initialize database schema"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS addresses (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    address_line1 TEXT NOT NULL,
                    address_line2 TEXT,
                    city TEXT NOT NULL,
                    state TEXT NOT NULL,
                    postal_code TEXT NOT NULL,
                    country TEXT NOT NULL,
                    phone TEXT,
                    is_default INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
    
    async def create_address(self, address: AddressCreate) -> Address:
        """Create a new address"""
        address_id = str(uuid.uuid4())
        
        async with aiosqlite.connect(self.db_path) as db:
            # If this is set as default, unset other defaults
            if address.isDefault:
                await db.execute("UPDATE addresses SET is_default = 0")
            
            await db.execute("""
                INSERT INTO addresses (
                    id, type, full_name, address_line1, address_line2,
                    city, state, postal_code, country, phone, is_default
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                address_id, address.type, address.fullName, address.addressLine1,
                address.addressLine2, address.city, address.province, address.postalCode,
                address.country, address.phone, 1 if address.isDefault else 0
            ))
            await db.commit()
        
        return await self.get_address(address_id)
    
    async def get_address(self, address_id: str) -> Optional[Address]:
        """Get address by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM addresses WHERE id = ?", (address_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Address(
                        id=row['id'],
                        type=row['type'],
                        fullName=row['full_name'],
                        addressLine1=row['address_line1'],
                        addressLine2=row['address_line2'],
                        city=row['city'],
                        province=row['state'],
                        postalCode=row['postal_code'],
                        country=row['country'],
                        phone=row['phone'],
                        isDefault=bool(row['is_default'])
                    )
        return None
    
    async def list_addresses(self) -> List[Address]:
        """List all addresses"""
        addresses = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM addresses ORDER BY is_default DESC, created_at DESC"
            ) as cursor:
                async for row in cursor:
                    addresses.append(Address(
                        id=row['id'],
                        type=row['type'],
                        fullName=row['full_name'],
                        addressLine1=row['address_line1'],
                        addressLine2=row['address_line2'],
                        city=row['city'],
                        province=row['state'],
                        postalCode=row['postal_code'],
                        country=row['country'],
                        phone=row['phone'],
                        isDefault=bool(row['is_default'])
                    ))
        return addresses
    
    async def update_address(self, address_id: str, update: AddressUpdate) -> Optional[Address]:
        """Update an address"""
        async with aiosqlite.connect(self.db_path) as db:
            # Build update query dynamically
            updates = []
            values = []
            
            if update.type is not None:
                updates.append("type = ?")
                values.append(update.type)
            if update.fullName is not None:
                updates.append("full_name = ?")
                values.append(update.fullName)
            if update.addressLine1 is not None:
                updates.append("address_line1 = ?")
                values.append(update.addressLine1)
            if update.addressLine2 is not None:
                updates.append("address_line2 = ?")
                values.append(update.addressLine2)
            if update.city is not None:
                updates.append("city = ?")
                values.append(update.city)
            if update.province is not None:
                updates.append("state = ?")
                values.append(update.province)
            if update.postalCode is not None:
                updates.append("postal_code = ?")
                values.append(update.postalCode)
            if update.country is not None:
                updates.append("country = ?")
                values.append(update.country)
            if update.phone is not None:
                updates.append("phone = ?")
                values.append(update.phone)
            if update.isDefault is not None:
                if update.isDefault:
                    await db.execute("UPDATE addresses SET is_default = 0")
                updates.append("is_default = ?")
                values.append(1 if update.isDefault else 0)
            
            if updates:
                values.append(address_id)
                query = f"UPDATE addresses SET {', '.join(updates)} WHERE id = ?"
                await db.execute(query, values)
                await db.commit()
        
        return await self.get_address(address_id)
    
    async def delete_address(self, address_id: str) -> bool:
        """Delete an address"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM addresses WHERE id = ?", (address_id,))
            await db.commit()
            return True
    
    async def set_default(self, address_id: str) -> Optional[Address]:
        """Set an address as default"""
        async with aiosqlite.connect(self.db_path) as db:
            # Unset all defaults
            await db.execute("UPDATE addresses SET is_default = 0")
            # Set this one as default
            await db.execute("UPDATE addresses SET is_default = 1 WHERE id = ?", (address_id,))
            await db.commit()
        
        return await self.get_address(address_id)

# Global instance
address_service = AddressService()
