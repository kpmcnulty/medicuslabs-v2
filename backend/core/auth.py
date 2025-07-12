from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    """Verify JWT token and return admin username"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        if username != settings.admin_username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

def authenticate_admin(username: str, password: str) -> bool:
    """Authenticate admin user"""
    if username != settings.admin_username:
        return False
    if not settings.admin_password_hash:
        # If no password hash is set, reject all logins for security
        return False
    return verify_password(password, settings.admin_password_hash)

# Utility function to generate a password hash (for initial setup)
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        password = sys.argv[1]
        print(f"Password hash: {get_password_hash(password)}")
        print(f"Add this to your .env file as ADMIN_PASSWORD_HASH={get_password_hash(password)}")
    else:
        print("Usage: python auth.py <password>")