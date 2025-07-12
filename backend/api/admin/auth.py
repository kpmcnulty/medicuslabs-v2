from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from core.auth import authenticate_admin, create_access_token, get_current_admin
from core.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin-auth"])

class Token(BaseModel):
    access_token: str
    token_type: str

class AdminInfo(BaseModel):
    username: str

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Admin login endpoint"""
    if not authenticate_admin(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(hours=settings.jwt_expiration_hours)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=AdminInfo)
async def get_admin_info(current_admin: str = Depends(get_current_admin)):
    """Get current admin information"""
    return {"username": current_admin}

@router.post("/logout")
async def logout(current_admin: str = Depends(get_current_admin)):
    """Logout endpoint (client should discard token)"""
    return {"message": "Logout successful"}