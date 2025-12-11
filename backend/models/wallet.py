from pydantic import BaseModel
from typing import Optional, Dict, Any

class PaymentMethod(BaseModel):
    """Payment method model"""
    id: Optional[str] = None
    type: str  # 'card', 'upi', 'netbanking'
    label: str  # User-friendly name
    masked_data: str  # Masked version for display (e.g., "**** 1234")
    is_default: bool = False

class CardCreate(BaseModel):
    """Model for creating a new card"""
    card_number: str
    card_holder: str
    expiry_month: str
    expiry_year: str
    cvv: str
    label: Optional[str] = None
    is_default: bool = False

class UPICreate(BaseModel):
    """Model for creating UPI payment"""
    upi_id: str
    label: Optional[str] = None
    is_default: bool = False

class EncryptedPaymentData(BaseModel):
    """Encrypted payment data for storage"""
    id: str
    type: str
    encrypted_data: str
    label: str
    masked_data: str
    is_default: bool
