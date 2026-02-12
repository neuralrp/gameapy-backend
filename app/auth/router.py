from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from app.db.database import db
from app.models.schemas import APIResponse
from .security import create_access_token, verify_password, get_password_hash, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str
    name: str = "Gameapy User"


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register", response_model=APIResponse)
async def register(request: RegisterRequest):
    existing = db.get_user_by_username(request.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters"
        )
    
    if len(request.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters"
        )
    
    password_hash = get_password_hash(request.password)
    
    profile_data = {
        "spec": "client_profile_v1",
        "spec_version": "1.0",
        "data": {
            "name": request.name,
            "personality": "New user",
            "traits": [],
            "goals": [],
            "presenting_issues": [],
            "life_events": []
        }
    }
    
    user_id = db.create_user(
        username=request.username,
        password_hash=password_hash,
        profile_data=profile_data
    )
    
    access_token = create_access_token(data={"sub": str(user_id)})
    
    return APIResponse(
        success=True,
        message="User registered successfully",
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 30 * 24 * 60 * 60,
            "user_id": user_id,
            "username": request.username
        }
    )


@router.post("/login", response_model=APIResponse)
async def login(request: LoginRequest):
    user = db.get_user_by_username(request.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    access_token = create_access_token(data={"sub": str(user["id"])})
    
    return APIResponse(
        success=True,
        message="Login successful",
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 30 * 24 * 60 * 60,
            "user_id": user["id"],
            "username": user["username"]
        }
    )


@router.get("/me", response_model=APIResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return APIResponse(
        success=True,
        message="User retrieved successfully",
        data={
            "user_id": current_user["id"],
            "username": current_user.get("username"),
            "name": current_user.get("name"),
            "entity_id": current_user.get("entity_id")
        }
    )
