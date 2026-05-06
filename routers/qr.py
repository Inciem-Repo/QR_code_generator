import os
import uuid
import json
import base64
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Request, Depends, Header
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel, HttpUrl
from qr_service import QRCodeService
from services.qr_history_service import log_qr_generation, get_user_qr_history
from services.admin_service import AdminService
from services.ads_service import AdsService
from routers.auth import get_current_user, get_current_user_optional
from routers.admin import get_current_admin
from utils.s3_utils import S3Service

router = APIRouter(tags=["QR & Ads"])


from config import config

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


class QRCustomization(BaseModel):
    fill_color: Optional[str] = "black"
    back_color: Optional[str] = "white"
    pattern: Optional[str] = "square"
    error_correction: Optional[str] = "L"
    logo: Optional[str] = None
    logo_size: Optional[float] = 0.3

class QRRequest(BaseModel):
    url: str
    customization: Optional[QRCustomization] = None

class AdUpdate(BaseModel):
    placement: Optional[str] = None
    redirectUrl: Optional[str] = None
    isActive: Optional[bool] = None

class AdStatusUpdate(BaseModel):
    isActive: bool


@router.get("/uploads/{filename}")
async def serve_uploaded_file(filename: str):
    file_path = os.path.join(config.UPLOAD_FOLDER, filename)
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

    filename = f"ads/{uuid.uuid4().hex}_{image.filename}"
    content = await image.read()
    
    image_url = await S3Service.upload_file(content, filename, content_type=image.content_type)
    
    if not image_url:
        raise HTTPException(status_code=500, detail="Failed to upload image to S3")

    ad = {
        "placement": placement,
        "imageUrl": image_url,
        "redirectUrl": redirectUrl,
        "isActive": isActive,
        "imagePath": filename, # Store S3 key as imagePath
    }
    
    saved_ad = await AdsService.create_ad(ad)
    return serialize_ad(saved_ad)

@router.get("/ads")
async def list_ads(
    placement: Optional[str] = Query(None), 
    all_ads: bool = Query(False),
    admin: Optional[dict] = Depends(get_current_user_optional)
):
   
    if not await AdminService.is_ads_enabled():
        return []
    
    # Only admins can see inactive ads, or if all_ads is False we only show active ones
    only_active = True
    if all_ads and admin and admin.get("role") == "admin":
        only_active = False
        
    ads = await AdsService.get_all_ads(placement=placement, only_active=only_active)
    return [serialize_ad(ad) for ad in ads]

@router.get("/ads/{ad_id}")
async def get_ad(ad_id: int):
    ad = await AdsService.get_ad_by_id(ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    return serialize_ad(ad)

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
        
        filename = f"ads/{uuid.uuid4().hex}_{image.filename}"
        content = await image.read()
        if not content:
             raise HTTPException(status_code=400, detail="Uploaded image is empty")

        new_image_url = await S3Service.upload_file(content, filename, content_type=image.content_type)
        if not new_image_url:
            raise HTTPException(status_code=500, detail="Failed to upload image to S3")
            
        # Cleanup old image
        old_path = ad.get("imagePath")
        if old_path:
            if isinstance(old_path, str) and old_path.startswith("ads/"):
                await S3Service.delete_file(old_path)
            elif os.path.exists(str(old_path)):
                try: os.remove(str(old_path))
                except: pass
            
        update_data["imagePath"] = filename
        update_data["imageUrl"] = new_image_url

    updated_ad = await AdsService.update_ad(ad_id, update_data)
    return serialize_ad(updated_ad)

@router.delete("/ads/{ad_id}")
async def delete_ad(ad_id: int, admin: dict = Depends(get_current_admin)):
    ad = await AdsService.get_ad_by_id(ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    image_path = ad.get("imagePath")
    if image_path:
        if isinstance(image_path, str) and image_path.startswith("ads/"):
            await S3Service.delete_file(image_path)
        elif os.path.exists(str(image_path)):
            try: os.remove(str(image_path))
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


@router.post("/generate")
async def generate_qr_code(request: Request, body: QRRequest, user: Optional[dict] = Depends(get_current_user_optional)):
    # Extract customization parameters
    customization_dict = {}
    if body.customization:
        customization_dict = {
            "fill_color": body.customization.fill_color,
            "back_color": body.customization.back_color,
            "pattern": body.customization.pattern,
            "error_correction": body.customization.error_correction,
            "logo": body.customization.logo,
            "logo_size": body.customization.logo_size
        }
    
    # Generate QR code with customization
    qr_code_base64 = qr_service.generate_qr_code_base64(
        url=body.url,
        fill_color=customization_dict.get("fill_color", "black"),
        back_color=customization_dict.get("back_color", "white"),
        pattern=customization_dict.get("pattern", "square"),
        error_correction=customization_dict.get("error_correction", "L"),
        logo=customization_dict.get("logo"),
        logo_size=customization_dict.get("logo_size", 0.3)
    )
    
    if qr_code_base64:
        if user:
            user_id = user["id"]
            base_url = str(request.base_url).rstrip("/")
            await log_qr_generation(body.url, qr_code_base64, user_id, customization_dict if body.customization else None, base_url)
            
        return {
            "success": True,
            "url": body.url,
            "qr_code": qr_code_base64,
            "format": "PNG",
            "customization": customization_dict if body.customization else None,
            "message": "QR code generated successfully"
        }
    raise HTTPException(status_code=500, detail="Failed to generate QR code")

@router.post("/generate/image")
async def generate_qr_code_image(request: Request, body: QRRequest, user: Optional[dict] = Depends(get_current_user_optional)):
    # Extract customization parameters
    customization_dict = {}
    if body.customization:
        customization_dict = {
            "fill_color": body.customization.fill_color,
            "back_color": body.customization.back_color,
            "pattern": body.customization.pattern,
            "error_correction": body.customization.error_correction,
            "logo": body.customization.logo,
            "logo_size": body.customization.logo_size
        }
    
    # Generate QR code with customization
    qr_code_bytes = qr_service.generate_qr_code(
        url=body.url,
        fill_color=customization_dict.get("fill_color", "black"),
        back_color=customization_dict.get("back_color", "white"),
        pattern=customization_dict.get("pattern", "square"),
        error_correction=customization_dict.get("error_correction", "L"),
        logo=customization_dict.get("logo"),
        logo_size=customization_dict.get("logo_size", 0.3)
    )
    
    if qr_code_bytes:
        if user:
            user_id = user["id"]
            base_url = str(request.base_url).rstrip("/")
            qr_code_base64 = base64.b64encode(qr_code_bytes).decode('utf-8')
            await log_qr_generation(body.url, qr_code_base64, user_id, customization_dict if body.customization else None, base_url)
            
        from io import BytesIO
        return StreamingResponse(BytesIO(qr_code_bytes), media_type="image/png")
    raise HTTPException(status_code=500, detail="Failed to generate QR code")

@router.get("/generate/{url:path}")
async def generate_qr_code_get(
    request: Request, 
    url: str, 
    fill_color: Optional[str] = Query("black"),
    back_color: Optional[str] = Query("white"),
    pattern: Optional[str] = Query("square"),
    error_correction: Optional[str] = Query("L"),
    user: Optional[dict] = Depends(get_current_user_optional)
):
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url
    
    # Build customization dict
    customization_dict = {
        "fill_color": fill_color,
        "back_color": back_color,
        "pattern": pattern,
        "error_correction": error_correction
    }
    
    # Generate QR code with customization
    qr_code_bytes = qr_service.generate_qr_code(
        url=url,
        fill_color=fill_color,
        back_color=back_color,
        pattern=pattern,
        error_correction=error_correction
    )
    
    if qr_code_bytes:
        if user:
            user_id = user["id"]
            base_url = str(request.base_url).rstrip("/")
            qr_code_base64 = base64.b64encode(qr_code_bytes).decode('utf-8')
            await log_qr_generation(url, qr_code_base64, user_id, customization_dict, base_url)
            
        from io import BytesIO
        return StreamingResponse(BytesIO(qr_code_bytes), media_type="image/png")
    raise HTTPException(status_code=500, detail="Failed to generate QR code")

@router.post("/download")
async def download_qr_code(body: QRRequest, user: dict = Depends(get_current_user)):
    """Only authenticated users can download the QR code image."""
    # Extract customization parameters
    customization_dict = {}
    if body.customization:
        customization_dict = {
            "fill_color": body.customization.fill_color,
            "back_color": body.customization.back_color,
            "pattern": body.customization.pattern,
            "error_correction": body.customization.error_correction,
            "logo": body.customization.logo,
            "logo_size": body.customization.logo_size
        }
    
    # Generate QR code with customization
    qr_code_bytes = qr_service.generate_qr_code(
        url=body.url,
        fill_color=customization_dict.get("fill_color", "black"),
        back_color=customization_dict.get("back_color", "white"),
        pattern=customization_dict.get("pattern", "square"),
        error_correction=customization_dict.get("error_correction", "L"),
        logo=customization_dict.get("logo"),
        logo_size=customization_dict.get("logo_size", 0.3)
    )
    
    if qr_code_bytes:
        # Log generation for history
        user_id = user["id"]
        qr_code_base64 = base64.b64encode(qr_code_bytes).decode('utf-8')
        await log_qr_generation(body.url, qr_code_base64, user_id, customization_dict if body.customization else None)

        from io import BytesIO
        filename = f"qr_{uuid.uuid4().hex[:8]}.png"
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        return StreamingResponse(BytesIO(qr_code_bytes), media_type="image/png", headers=headers)
    raise HTTPException(status_code=500, detail="Failed to generate QR code for download")

@router.get("/history")
async def get_history(request: Request, user: dict = Depends(get_current_user)):
    history = await get_user_qr_history(user["id"])
    base_url = str(request.base_url).rstrip("/")
    for entry in history:
        # Provide the actual base64 image data in his preferred field name
        if "qr_code" in entry:
            qr_data = entry["qr_code"]
            # Ensure it's a string and add prefix
            if isinstance(qr_data, str):
                if not qr_data.startswith("data:"):
                    entry["qr_image"] = f"data:image/png;base64,{qr_data}"
                else:
                    entry["qr_image"] = qr_data
            else:
                entry["qr_image"] = None
        
        # Also provide the direct view URL
        if not entry.get("qr_image_url") or not entry["qr_image_url"].startswith("http"):
             entry["qr_image_url"] = f"{base_url}/history/{entry['_id']}/image"
    return history

@router.get("/history/{history_id}/image")
async def get_history_image(history_id: str):
    from services.qr_history_service import get_qr_history_item_public
    from io import BytesIO
    
    item = await get_qr_history_item_public(history_id)
    if not item:
        raise HTTPException(status_code=404, detail="QR history item not found")
    
    # Try to get from stored qr_code
    if "qr_code" in item:
        try:
            qr_data = item["qr_code"]
            if "," in qr_data:
                qr_data = qr_data.split(",")[1]
            qr_code_bytes = base64.b64decode(qr_data)
            return StreamingResponse(BytesIO(qr_code_bytes), media_type="image/png")
        except Exception:
            pass # Fallback to regeneration
            
    # Fallback: Regenerate if missing or corrupted
    if "url" in item:
        customization = item.get("customization", {})
        qr_code_bytes = qr_service.generate_qr_code(
            url=item["url"],
            fill_color=customization.get("fill_color", "black"),
            back_color=customization.get("back_color", "white"),
            pattern=customization.get("pattern", "square"),
            error_correction=customization.get("error_correction", "L"),
            logo=customization.get("logo"),
            logo_size=customization.get("logo_size", 0.3)
        )
        if qr_code_bytes:
            return StreamingResponse(BytesIO(qr_code_bytes), media_type="image/png")
            
    raise HTTPException(status_code=404, detail="QR image could not be retrieved or regenerated")

@router.delete("/history/{history_id}")
async def delete_history(history_id: str, user: dict = Depends(get_current_user)):
    from services.qr_history_service import delete_qr_history_item
    
    success = await delete_qr_history_item(history_id, user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="History item not found or could not be deleted")
    
    return {"message": "History item deleted successfully", "id": history_id}

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "QR Code API Service"}
