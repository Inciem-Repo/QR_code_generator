import os
import uuid
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Request, Depends, Header
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel, HttpUrl
from qr_service import QRCodeService
from services.qr_history_service import log_qr_generation, get_user_qr_history
from services.admin_service import AdminService
from services.ads_service import AdsService
from routers.auth import get_current_user
from routers.admin import get_current_admin

router = APIRouter(tags=["QR & Ads"])

# Paths and configuration
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ADS_DATA_FILE = os.path.join(BASE_DIR, "ads_data.json")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
VALID_PLACEMENTS = {
    "top-wide",
    "vertical-right",
    "left-1",
    "left-2",
    "bottom-wide-1",
    "bottom-wide-2",
    "mobile-bottom-1",
    "mobile-bottom-2",
}

qr_service = QRCodeService()

# Helper Functions
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def serialize_ad(ad: dict) -> dict:
    return {
        "id": ad.get("id"),
        "placement": ad.get("placement"),
        "imageUrl": ad.get("imageUrl"),
        "redirectUrl": ad.get("redirectUrl"),
        "isActive": bool(ad.get("isActive", True)),
    }

# Models
class QRRequest(BaseModel):
    url: str

class AdUpdate(BaseModel):
    placement: Optional[str] = None
    redirectUrl: Optional[str] = None
    isActive: Optional[bool] = None

class AdStatusUpdate(BaseModel):
    isActive: bool

# Routes

@router.get("/uploads/{filename}")
async def serve_uploaded_file(filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@router.post("/ads")
async def create_ad(
    request: Request,
    placement: str = Form(...),
    redirectUrl: str = Form(None),
    isActive: bool = Form(True),
    image: UploadFile = File(...),
    admin: dict = Depends(get_current_admin)
):
    if placement not in VALID_PLACEMENTS:
        raise HTTPException(status_code=400, detail="Invalid placement")
    
    if not allowed_file(image.filename):
        raise HTTPException(status_code=400, detail=f"Invalid image type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")

    filename = f"{uuid.uuid4().hex}_{image.filename}"
    image_path = os.path.join(UPLOAD_FOLDER, filename)
    
    with open(image_path, "wb") as buffer:
        content = await image.read()
        buffer.write(content)
    
    base_url = str(request.base_url).rstrip("/")
    image_url = f"{base_url}/uploads/{filename}"

    ad = {
        "placement": placement,
        "imageUrl": image_url,
        "redirectUrl": redirectUrl,
        "isActive": isActive,
        "imagePath": image_path,
    }
    
    saved_ad = await AdsService.create_ad(ad)
    return serialize_ad(saved_ad)

@router.get("/ads")
async def list_ads(placement: Optional[str] = Query(None)):
    # Check if ads are globally enabled
    if not await AdminService.is_ads_enabled():
        return []
    
    ads = await AdsService.get_all_ads(placement=placement, only_active=True)
    return [serialize_ad(ad) for ad in ads]

@router.put("/ads/{ad_id}")
async def update_ad(
    ad_id: int,
    request: Request,
    placement: Optional[str] = Form(None),
    redirectUrl: Optional[str] = Form(None),
    isActive: Optional[bool] = Form(None),
    image: Optional[UploadFile] = File(None),
    admin: dict = Depends(get_current_admin)
):
    ad = await AdsService.get_ad_by_id(ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    update_data = {}
    if placement:
        if placement not in VALID_PLACEMENTS:
            raise HTTPException(status_code=400, detail="Invalid placement")
        update_data["placement"] = placement
    
    if redirectUrl:
        update_data["redirectUrl"] = redirectUrl
    
    if isActive is not None:
        update_data["isActive"] = isActive

    if image and image.filename:
        if not allowed_file(image.filename):
            raise HTTPException(status_code=400, detail="Invalid image type")
        
        filename = f"{uuid.uuid4().hex}_{image.filename}"
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(image_path, "wb") as buffer:
            content = await image.read()
            buffer.write(content)
            
        # Cleanup old image
        old_path = ad.get("imagePath")
        if old_path and os.path.exists(old_path):
            try: os.remove(old_path)
            except: pass
            
        update_data["imagePath"] = image_path
        base_url = str(request.base_url).rstrip("/")
        update_data["imageUrl"] = f"{base_url}/uploads/{filename}"

    updated_ad = await AdsService.update_ad(ad_id, update_data)
    return serialize_ad(updated_ad)

@router.delete("/ads/{ad_id}")
async def delete_ad(ad_id: int, admin: dict = Depends(get_current_admin)):
    ad = await AdsService.get_ad_by_id(ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    image_path = ad.get("imagePath")
    if image_path and os.path.exists(image_path):
        try: os.remove(image_path)
        except: pass
        
    await AdsService.delete_ad(ad_id)
    return {"deleted": ad_id}

@router.post("/ads/{ad_id}/status")
async def set_ad_status(ad_id: int, body: AdStatusUpdate, admin: dict = Depends(get_current_admin)):
    """Explicitly enable or disable a specific advertisement."""
    updated_ad = await AdsService.update_ad(ad_id, {"isActive": body.isActive})
    if not updated_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    
    status_str = "enabled" if body.isActive else "disabled"
    return {
        "message": f"Ad {ad_id} {status_str} successfully",
        "ad_id": ad_id,
        "isActive": body.isActive
    }

@router.post("/ads/{ad_id}/toggle")
async def toggle_ad_status(ad_id: int, admin: dict = Depends(get_current_admin)):
    """Toggle the active status of a specific advertisement."""
    updated_ad = await AdsService.toggle_ad_status(ad_id)
    if not updated_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    
    status_str = "enabled" if updated_ad["isActive"] else "disabled"
    return {
        "message": f"Ad {ad_id} {status_str} successfully",
        "ad_id": ad_id,
        "isActive": updated_ad["isActive"]
    }

# QR Generation Routes
@router.post("/generate")
async def generate_qr_code(request: QRRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    qr_code_base64 = qr_service.generate_qr_code_base64(request.url)
    if qr_code_base64:
        await log_qr_generation(request.url, user_id)
        return {
            "success": True,
            "url": request.url,
            "qr_code": qr_code_base64,
            "format": "PNG",
            "message": "QR code generated successfully"
        }
    raise HTTPException(status_code=500, detail="Failed to generate QR code")

@router.post("/generate/image")
async def generate_qr_code_image(request: QRRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    qr_code_bytes = qr_service.generate_qr_code(request.url)
    if qr_code_bytes:
        await log_qr_generation(request.url, user_id)
        from io import BytesIO
        return StreamingResponse(BytesIO(qr_code_bytes), media_type="image/png")
    raise HTTPException(status_code=500, detail="Failed to generate QR code")

@router.get("/generate/{url:path}")
async def generate_qr_code_get(url: str, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url
    
    qr_code_bytes = qr_service.generate_qr_code(url)
    if qr_code_bytes:
        await log_qr_generation(url, user_id)
        from io import BytesIO
        return StreamingResponse(BytesIO(qr_code_bytes), media_type="image/png")
    raise HTTPException(status_code=500, detail="Failed to generate QR code")

@router.get("/history")
async def get_history(user: dict = Depends(get_current_user)):
    history = await get_user_qr_history(user["id"])
    return history

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "QR Code API Service"}
