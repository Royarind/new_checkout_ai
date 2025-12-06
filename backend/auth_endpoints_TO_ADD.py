"""
Authentication endpoints for CHKout.ai
To be added to backend/main.py
"""

from fastapi import HTTPException, Header
from pydantic import BaseModel

# ==== Authentication Models ====
class RegisterRequest(BaseModel):
    email: str
    password: str
    fullName: str
    country: str = "US"

class LoginRequest(BaseModel):
    email: str
    password: str

# ==== JWT Helper ====
async def get_current_user_id(authorization: str = Header(None)) -> int:
    """Extract user_id from JWT token"""
    if not authorization or not authorization.startswith('Bearer '):
        return 1  # Default to user_id=1 if no token (backward compatibility)
    
    token = authorization.split(' ')[1]
    from checkout_ai.auth import AuthService
    
    user = AuthService.get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user['id']

# ==== Endpoints ====
#  Add these to main.py after line 147

@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """Register a new user"""
    try:
        from checkout_ai.auth import AuthService
        
        user_id = AuthService.register_user(
            email=request.email,
            password=request.password,
            full_name=request.fullName,
            country=request.country
        )
        
        # Auto-login after registration
        auth_result = AuthService.authenticate_user(
            email=request.email,
            password=request.password
        )
        
        return auth_result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Login user and return JWT token"""
    try:
        from checkout_ai.auth import AuthService
        
        auth_result = AuthService.authenticate_user(
            email=request.email,
            password=request.password
        )
        
        return auth_result
        
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/api/auth/me")
async def get_current_user(authorization: str = Header(None)):
    """Get current user profile"""
    user_id = await get_current_user_id(authorization)
    from checkout_ai.db import db
    
    user = db.fetch_one("""
        SELECT id, email, full_name, country, phone
        FROM users
        WHERE id = ?
    """, (user_id,))
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user
