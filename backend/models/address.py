from pydantic import BaseModel
from typing import Optional

class Address(BaseModel):
    """Address model"""
    id: Optional[str] = None
    type: str  # 'shipping', 'billing', 'both'
    full_name: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str
    phone: Optional[str] = None
    is_default: bool = False

class AddressCreate(BaseModel):
    """Model for creating a new address"""
    type: str
    full_name: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str
    phone: Optional[str] = None
    is_default: bool = False

class AddressUpdate(BaseModel):
    """Model for updating an address"""
    type: Optional[str] = None
    full_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    is_default: Optional[bool] = None
