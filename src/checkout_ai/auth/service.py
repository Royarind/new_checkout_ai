"""
User Authentication Service
Simple JWT-based authentication with bcrypt password hashing
"""

from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict
import os

from ..db import db

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None
    
    @staticmethod
    def register_user(email: str, password: str, full_name: str, country: str = "US") -> int:
        """Register a new user"""
        # Check if email already exists
        existing_user = db.fetch_one("SELECT id FROM users WHERE email = ?", (email,))
        if existing_user:
            raise ValueError("Email already registered")
        
        # Hash password
        password_hash = AuthService.hash_password(password)
        
        # Create user
        user_id = db.execute_insert("""
            INSERT INTO users (email, password_hash, full_name, country)
            VALUES (?, ?, ?, ?)
        """, (email, password_hash, full_name, country))
        
        print(f"[OK] User registered: {email} (ID: {user_id})")
        return user_id
    
    @staticmethod
    def authenticate_user(email: str, password: str) -> Dict:
        """Authenticate user and return token + user info"""
        # Get user
        user = db.fetch_one("""
            SELECT id, email, password_hash, full_name, country, phone
            FROM users
            WHERE email = ? AND is_active = 1
        """, (email,))
        
        if not user:
            raise ValueError("Invalid email or password")
        
        # Verify password
        if not AuthService.verify_password(password, user['password_hash']):
            raise ValueError("Invalid email or password")
        
        # Update last login
        db.execute_update(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user['id'],)
        )
        
        # Create access token
        access_token = AuthService.create_access_token(
            data={"sub": user['email'], "user_id": user['id']}
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user['full_name'],
                "country": user['country'],
                "phone": user['phone']
            }
        }
    
    @staticmethod
    def get_current_user(token: str) -> Optional[Dict]:
        """Get current user from token"""
        payload = AuthService.verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        user = db.fetch_one("""
            SELECT id, email, full_name, country, phone, preferred_currency
            FROM users
            WHERE id = ? AND is_active = 1
        """, (user_id,))
        
        return user
