"""
Profile and Address API endpoints
Add these to backend/main.py after the orders endpoints
"""

from fastapi import HTTPException, Header
from pydantic import BaseModel
from typing import Optional

# ========== PROFILE MODELS ==========

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None

class AddShippingAddressRequest(BaseModel):
    label: str
    recipient_name: str
    address_line1: str
    address_line2: Optional[str] = ""
    city: str
    state: str
    postal_code: str
    country: str
    is_default: bool = False

class AddBillingAddressRequest(BaseModel):
    label: str
    full_name: str
    address_line1: str
    address_line2: Optional[str] = ""
    city: str
    state: str
    postal_code: str
    country: str
    is_default: bool = False

# ========== PROFILE ENDPOINTS ==========

@app.get("/api/profile")
async def get_profile(authorization: str = Header(None)):
    """Get current user profile"""
    user_id = await get_current_user_id(authorization)
    
    from src.checkout_ai.users.profile_service_enhanced import ProfileService
    profile = ProfileService.get_user_profile(user_id)
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profile

@app.put("/api/profile")
async def update_profile(request: UpdateProfileRequest, authorization: str = Header(None)):
    """Update user profile"""
    user_id = await get_current_user_id(authorization)
    
    from src.checkout_ai.users.profile_service_enhanced import ProfileService
    success = ProfileService.update_user_profile(
        user_id=user_id,
        full_name=request.full_name,
        phone=request.phone,
        country=request.country
    )
    
    return {"success": success}

# ========== SHIPPING ADDRESS ENDPOINTS ==========

@app.get("/api/profile/shipping-addresses")
async def get_shipping_addresses(authorization: str = Header(None)):
    """Get all shipping addresses"""
    user_id = await get_current_user_id(authorization)
    
    from src.checkout_ai.users.profile_service_enhanced import ProfileService
    addresses = ProfileService.get_shipping_addresses(user_id)
    
    return addresses

@app.post("/api/profile/shipping-addresses")
async def add_shipping_address(request: AddShippingAddressRequest, authorization: str = Header(None)):
    """Add new shipping address"""
    user_id = await get_current_user_id(authorization)
    
    from src.checkout_ai.users.profile_service_enhanced import ProfileService
    address_id = ProfileService.add_shipping_address(
        user_id=user_id,
        label=request.label,
        recipient_name=request.recipient_name,
        address_line1=request.address_line1,
        address_line2=request.address_line2,
        city=request.city,
        state=request.state,
        postal_code=request.postal_code,
        country=request.country,
        is_default=request.is_default
    )
    
    return {"success": True, "address_id": address_id}

@app.put("/api/profile/shipping-addresses/{address_id}/set-default")
async def set_default_shipping(address_id: int, authorization: str = Header(None)):
    """Set shipping address as default"""
    user_id = await get_current_user_id(authorization)
    
    from src.checkout_ai.users.profile_service_enhanced import ProfileService
    success = ProfileService.set_default_shipping_address(address_id, user_id)
    
    return {"success": success}

@app.delete("/api/profile/shipping-addresses/{address_id}")
async def delete_shipping_address(address_id: int, authorization: str = Header(None)):
    """Delete shipping address"""
    user_id = await get_current_user_id(authorization)
    
    from src.checkout_ai.users.profile_service_enhanced import ProfileService
    success = ProfileService.delete_shipping_address(address_id, user_id)
    
    return {"success": success}

# ========== BILLING ADDRESS ENDPOINTS ==========

@app.get("/api/profile/billing-addresses")
async def get_billing_addresses(authorization: str = Header(None)):
    """Get all billing addresses"""
    user_id = await get_current_user_id(authorization)
    
    from src.checkout_ai.users.profile_service_enhanced import ProfileService
    addresses = ProfileService.get_billing_addresses(user_id)
    
    return addresses

@app.post("/api/profile/billing-addresses")
async def add_billing_address(request: AddBillingAddressRequest, authorization: str = Header(None)):
    """Add new billing address"""
    user_id = await get_current_user_id(authorization)
    
    from src.checkout_ai.users.profile_service_enhanced import ProfileService
    address_id = ProfileService.add_billing_address(
        user_id=user_id,
        label=request.label,
        full_name=request.full_name,
        address_line1=request.address_line1,
        address_line2=request.address_line2,
        city=request.city,
        state=request.state,
        postal_code=request.postal_code,
        country=request.country,
        is_default=request.is_default
    )
    
    return {"success": True, "address_id": address_id}

@app.put("/api/profile/billing-addresses/{address_id}/set-default")
async def set_default_billing(address_id: int, authorization: str = Header(None)):
    """Set billing address as default"""
    user_id = await get_current_user_id(authorization)
    
    from src.checkout_ai.users.profile_service_enhanced import ProfileService
    success = ProfileService.set_default_billing_address(address_id, user_id)
    
    return {"success": success}

@app.delete("/api/profile/billing-addresses/{address_id}")
async def delete_billing_address(address_id: int, authorization: str = Header(None)):
    """Delete billing address"""
    user_id = await get_current_user_id(authorization)
    
    from src.checkout_ai.users.profile_service_enhanced import ProfileService
    success = ProfileService.delete_billing_address(address_id, user_id)
    
    return {"success": success}
