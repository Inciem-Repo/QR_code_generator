import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, UploadFile, File, Form
from pydantic import BaseModel, EmailStr
from services.admin_service import AdminService
from utils.jwt_utils import create_access_token, decode_access_token

router = APIRouter(prefix="/admin", tags=["Admin"])

ADMIN_USERNAME = "admin@123"
ADMIN_PASSWORD = "1234"

class AdminLoginRequest(BaseModel):
    username: str
    password: str

async def get_current_admin(
    authorization: Optional[str] = Header(None),
    auth_query: Optional[str] = Query(None, alias="authorization")
):
    token_str = authorization or auth_query
    if not token_str:
        raise HTTPException(status_code=401, detail="Missing Authorization header or authorization query parameter")
    
    if token_str.lower().startswith("bearer "):
        parts = token_str.split()
        if len(parts) != 2:
            raise HTTPException(status_code=401, detail="Invalid authorization format")
        token = parts[1]
    else:
        token = token_str
        
    payload = decode_access_token(token)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Invalid or expired admin token")
    
    return {"id": "admin", "role": "admin"}

class AdsStatusUpdate(BaseModel):
    enabled: bool

@router.get("/ads/status")
async def get_ads_status():
    """Get the current global status of advertisements."""
    is_enabled = await AdminService.is_ads_enabled()
    return {"ads_enabled": is_enabled}

@router.get("/stats")
async def get_stats(admin: dict = Depends(get_current_admin)):
    """Get dashboard statistics: Total QR codes, Active users, Activated ads."""
    return await AdminService.get_dashboard_stats()

@router.post("/login")
async def admin_login(body: AdminLoginRequest):
    """Admin login endpoint (matches Flask service behavior)."""
    if body.username != ADMIN_USERNAME or body.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    from services.auth_service import find_user_by_email, create_user
    admin_user = await find_user_by_email(body.username)
    
    if not admin_user:
        admin_user = await create_user(
            name="Admin",
            email=body.username,
            role="admin"
        )
    
    mongo_id = admin_user.get("mongo_id")
    
    token = create_access_token(data={
        "sub": body.username,
        "mongo_id": mongo_id,
        "name": "Admin",
        "role": "admin"
    })
    return {"token": token, "tokenType": "Bearer"}

@router.post("/ads/toggle")
async def toggle_ads(body: AdsStatusUpdate, admin: dict = Depends(get_current_admin)):
    """Enable or disable advertisements globally. (Requires Admin Authentication)"""
    result = await AdminService.set_ads_enabled(body.enabled)
    return {
        "message": f"Ads {'enabled' if body.enabled else 'disabled'} successfully",
        "ads_enabled": body.enabled
    }
@router.get("/profile")
async def get_admin_profile(admin: dict = Depends(get_current_admin)):
    """Fetch the current admin logo and profile image URLs."""
    return await AdminService.get_admin_profile()

@router.post("/profile")
async def update_admin_images(
    logo: Optional[UploadFile] = File(None),
    profile_image: Optional[UploadFile] = File(None),
    admin: dict = Depends(get_current_admin)
):
    """Upload or update the admin logo and profile picture."""
    logo_content = None
    logo_name = None
    logo_type = None
    if logo:
        logo_content = await logo.read()
        logo_name = logo.filename
        logo_type = logo.content_type

    profile_image_content = None
    profile_image_name = None
    profile_image_type = None
    if profile_image:
        profile_image_content = await profile_image.read()
        profile_image_name = profile_image.filename
        profile_image_type = profile_image.content_type

    return await AdminService.update_admin_images(
        logo_content=logo_content,
        logo_name=logo_name,
        logo_type=logo_type,
        profile_image_content=profile_image_content,
        profile_image_name=profile_image_name,
        profile_image_type=profile_image_type
    )

class AdminProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None

@router.put("/profile")
async def update_admin_profile(
    body: AdminProfileUpdate,
    admin: dict = Depends(get_current_admin)
):
    """Update admin profile details (name, email)."""
    update_data = body.model_dump(exclude_unset=True)
    return await AdminService.update_admin_profile(update_data)
