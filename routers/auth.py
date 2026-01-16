from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel, EmailStr
from typing import Optional
from services.auth_service import (
    find_user_by_email,
    create_user,
    generate_otp,
    save_otp,
    verify_otp,
    find_user_by_id,
    log_user_login
)
from services.email_service import send_otp_email
from utils.jwt_utils import create_access_token, decode_access_token

router = APIRouter(tags=["Auth"])
user_router = APIRouter(tags=["Users"])


# =======================
# Request Models
# =======================

class SendOTPRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    otp: str
    profile_pic: Optional[str] = None


class RegisterResponse(BaseModel):
    id: str
    mongo_id: str
    name: str
    email: EmailStr
    profile_pic: Optional[str] = None
    login_type: str
    created_at: str
    message: str

class LoginRequest(BaseModel):
    email: EmailStr
    otp: str

class GoogleAuthRequest(BaseModel):
    token: str

# =======================
# Dependencies
# =======================

async def get_current_user(
    authorization: Optional[str] = Header(None),
    auth_query: Optional[str] = Query(None, alias="authorization")
):
    token_str = authorization or auth_query
    if not token_str:
        raise HTTPException(status_code=401, detail="Missing Authorization header or authorization query parameter")
    
    try:
        if token_str.lower().startswith("bearer "):
            parts = token_str.split()
            if len(parts) != 2:
                raise HTTPException(status_code=401, detail="Invalid authorization format")
            token = parts[1]
        else:
            token = token_str  # Accept direct token (common in query params)
        
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
             raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        user_id = payload["sub"]
        user = await find_user_by_id(user_id)
        if not user:
             raise HTTPException(status_code=401, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")


# =======================
# Send OTP (For Register/Login)
# =======================

@router.post("/send-otp")
async def send_otp(body: SendOTPRequest):
    """Send an OTP code to the user's email for verification."""
    otp = generate_otp()
    await save_otp(body.email, otp)

    try:
        success = send_otp_email(body.email, otp, purpose="verification")
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send email. Please check server logs.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
    
    print(f"✅ OTP sent to {body.email}: {otp}")  # dev only

    return {"message": "OTP sent to your email. Please check your inbox."}


@router.post("/verify-otp")
async def verify_otp_route(body: VerifyOTPRequest):
    """Verify the OTP code sent to the user's email and return a token."""
    if not await verify_otp(body.email, body.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    user = await find_user_by_email(body.email)
    
    # Auto-register if user doesn't exist
    if not user:
        user = await create_user(
            name=body.email.split('@')[0], # Use part of email as default name
            email=body.email,
            login_type="email"
        )
        message = "User registered and verified successfully"
    else:
        message = "OTP verified successfully"
    
    # Log the login activity
    await log_user_login(user["id"], user["email"], user.get("login_type", "email"))

    # Create access token
    access_token = create_access_token(data={
        "sub": user["id"],
        "mongo_id": user.get("mongo_id"),
        "name": user.get("name"),
        "email": user["email"],
        "role": user.get("role", "user")
    })

    # Return access token and user info
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": message,
        "user": {
            "id": user["id"],
            "mongo_id": user.get("mongo_id"),
            "name": user.get("name"),
            "email": user["email"],
            "profile_pic": user.get("profile_pic"),
            "login_type": user.get("login_type", "email"),
            "role": user.get("role", "user"),
            "created_at": user.get("created_at")
        }
    }


@router.post("/login")
async def login(body: LoginRequest):
    """Verify OTP and login. Creates a new user if one doesn't exist."""
    # Verify OTP
    if not await verify_otp(body.email, body.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    user = await find_user_by_email(body.email)
    
    # Auto-register if user doesn't exist
    if not user:
        user = await create_user(
            name=body.email.split('@')[0], # Use part of email as default name
            email=body.email,
            login_type="email"
        )
        message = "User registered and logged in successfully"
    else:
        message = "Logged in successfully"
    
    # Log the login activity
    await log_user_login(user["id"], user["email"], user.get("login_type", "email"))

    # Create access token
    access_token = create_access_token(data={
        "sub": user["id"],
        "mongo_id": user.get("mongo_id"),
        "name": user.get("name"),
        "email": user["email"],
        "role": user.get("role", "user")
    })

    # Return access token and user info
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": message,
        "user": {
            "id": user["id"],
            "mongo_id": user.get("mongo_id"),
            "name": user.get("name"),
            "email": user["email"],
            "profile_pic": user.get("profile_pic"),
            "login_type": user.get("login_type", "email"),
            "role": user.get("role", "user"),
            "created_at": user.get("created_at")
        }
    }

# =======================
# Google Auth
# =======================

@router.post("/google")
async def google_auth(body: GoogleAuthRequest):
    # Mock Google Auth validation
    return {"message": "Google auth implementation remains the same (passwordless)"}

# =======================
# Get User Info
# =======================

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    user_response = {
        "id": user.get("id"),
        "mongo_id": user.get("mongo_id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "profile_pic": user.get("profile_pic"),
        "login_type": user.get("login_type", "email"),
        "role": user.get("role", "user"),
        "created_at": user.get("created_at"),
        "email_verified": user.get("email_verified", False)
    }
    return user_response

@user_router.get("/user/{user_id}")
async def get_user_route(user_id: str):
    """Get user information by either UUID or MongoDB ID."""
    from services.auth_service import find_user_by_mongo_id, find_user_by_id
    
    # Try looking up by MongoDB ObjectId hex string
    user = await find_user_by_mongo_id(user_id)
    
    # If not found, try looking up by UUID
    if not user:
        user = await find_user_by_id(user_id)
        
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.get("id"),
        "mongo_id": user.get("mongo_id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "profile_pic": user.get("profile_pic"),
        "login_type": user.get("login_type", "email"),
        "role": user.get("role", "user"),
        "created_at": user.get("created_at"),
        "email_verified": user.get("email_verified", False)
    }
