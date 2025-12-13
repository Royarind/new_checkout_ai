from pydantic import BaseModel
from typing import Optional

class Address(BaseModel):
    """Address model"""
    id: Optional[str] = None
    type: str  # 'shipping', 'billing', 'both'
    fullName: str
    addressLine1: str
    addressLine2: Optional[str] = None
    city: str
    province: str
    postalCode: str
    country: str
    phone: Optional[str] = None
    isDefault: bool = False

class AddressCreate(BaseModel):
    """Model for creating a new address"""
    type: str
    fullName: str
    addressLine1: str
    addressLine2: Optional[str] = None
    city: str
    province: str
    postalCode: str
    country: str
    phone: Optional[str] = None
    isDefault: bool = False

class AddressUpdate(BaseModel):
    """Model for updating an address"""
    type: Optional[str] = None
    fullName: Optional[str] = None
    addressLine1: Optional[str] = None
    addressLine2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postalCode: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    isDefault: Optional[bool] = None
