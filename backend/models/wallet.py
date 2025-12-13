from pydantic import BaseModel
from typing import Optional, Dict, Any

class PaymentMethod(BaseModel):
    """Payment method model"""
    id: Optional[str] = None
    type: str  # 'card', 'upi', 'netbanking'
    label: str  # User-friendly name
    maskedData: str  # Masked version for display (e.g., "**** 1234")
    isDefault: bool = False

class CardCreate(BaseModel):
    """Model for creating a new card"""
    cardNumber: str
    cardHolder: str
    expiryMonth: str
    expiryYear: str
    cardCVV: str
    label: Optional[str] = None
    isDefault: bool = False

class UPICreate(BaseModel):
    """Model for creating UPI payment"""
    upiId: str
    label: Optional[str] = None
    isDefault: bool = False

class EncryptedPaymentData(BaseModel):
    """Encrypted payment data for storage"""
    id: str
    type: str
    encryptedData: str
    label: str
    maskedData: str
    isDefault: bool
