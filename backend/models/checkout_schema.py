from typing import Optional, Dict, List
from pydantic import BaseModel, Field


# -------------------------
# CONTACT & ADDRESS MODELS
# -------------------------

class ContactInfo(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ShippingAddress(BaseModel):
    addressLine1: Optional[str] = None
    addressLine2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None   # state / region
    postalCode: Optional[str] = None
    country: Optional[str] = "United States"


# -------------------------
# PAYMENT MODEL
# -------------------------

class WalletInfo(BaseModel):
    preferredPaymentMethod: Optional[str] = None
    cardNumber: Optional[str] = None
    cardExpiry: Optional[str] = None
    cardCVV: Optional[str] = None


# -------------------------
# PRODUCT TASK MODEL
# -------------------------

class Task(BaseModel):
    url: Optional[str] = None
    quantity: Optional[int] = 1
    selectedVariant: Dict[str, str] = Field(default_factory=dict)


# -------------------------
# CUSTOMER ROOT MODEL
# -------------------------

class Customer(BaseModel):
    contact: ContactInfo = Field(default_factory=ContactInfo)
    shippingAddress: ShippingAddress = Field(default_factory=ShippingAddress)
    wallet: WalletInfo = Field(default_factory=WalletInfo)


# -------------------------
# FINAL CHECKOUT MODEL
# -------------------------

class CheckoutData(BaseModel):
    """
    Matches actual structure used in checkout_ai:
    
    {
      "tasks": [ { "url": "...", "selectedVariant": {...}, "quantity": n } ],
      "customer": {
          "contact": {...},
          "shippingAddress": {...},
          "wallet": {...}
      }
    }
    """
    tasks: List[Task] = Field(default_factory=lambda: [Task()])
    customer: Customer = Field(default_factory=Customer)

    def get_missing_field(self) -> Optional[str]:
        """Find which mandatory field is still missing."""
        task = self.tasks[0]

        if not task.url: return "Product URL"
        if not task.quantity: return "Quantity"

        contact = self.customer.contact
        if not contact.email: return "Email Address"
        if not contact.firstName: return "First Name"

        address = self.customer.shippingAddress
        if not address.addressLine1: return "Street Address"
        if not address.city: return "City"
        if not address.province: return "State/Province"
        if not address.postalCode: return "Postal Code"

        wallet = self.customer.wallet
        if not wallet.cardNumber: return "Payment Card Number"

        return None





