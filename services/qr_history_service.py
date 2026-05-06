from datetime import datetime
from database import db
from typing import Optional
import base64
import uuid
from utils.s3_utils import S3Service

async def log_qr_generation(url: str, qr_code: str, user_id: Optional[str] = None, customization: Optional[dict] = None, base_url: Optional[str] = None):
    """
    Log a QR code generation event to MongoDB with customization details.
    
    Args:
        url: The URL encoded in the QR code
        qr_code: Base64 encoded QR code image data
        user_id: User ID who generated the QR code
        customization: Dictionary containing customization options (colors, pattern, logo, etc.)
        base_url: Base URL for generating image URLs
    """
    from bson.objectid import ObjectId
    history_id = ObjectId()
    
    # Upload to S3
    qr_image_url = None
    try:
        # Decode base64 if it has prefix
        qr_data = qr_code
        if "," in qr_data:
            qr_data = qr_data.split(",")[1]
        
        qr_bytes = base64.b64decode(qr_data)
        filename = f"qrcodes/{uuid.uuid4().hex}.png"
        qr_image_url = await S3Service.upload_file(qr_bytes, filename, content_type="image/png")
    except Exception as e:
        print(f"Error uploading QR to S3: {e}")

    log_entry = {
        "_id": history_id,
        "url": url,
        "qr_code": qr_code, # Keep base64 for compatibility if needed, or remove to save space
        "qr_image_url": qr_image_url,
        "user_id": user_id,
        "timestamp": datetime.utcnow(),
        "type": "qr_generation",
        "s3_key": filename if qr_image_url else None
    }
    
    # Add customization data if provided
    if customization:
        log_entry["customization"] = {
            "fill_color": customization.get("fill_color", "black"),
            "back_color": customization.get("back_color", "white"),
            "pattern": customization.get("pattern", "square"),
            "error_correction": customization.get("error_correction", "L"),
            "has_logo": bool(customization.get("logo")),
            "logo_size": customization.get("logo_size", 0.3) if customization.get("logo") else None
        }
    
    # If S3 upload failed, fallback to local history URL if base_url is provided
    if not qr_image_url and base_url:
        log_entry["qr_image_url"] = f"{base_url}/history/{str(history_id)}/image"
        
    await db.db.qr_history.insert_one(log_entry)
    print(f"Logged QR generation: {url} (User: {user_id}, Customized: {bool(customization)})")

async def get_user_qr_history(user_id: str):
    """
    Retrieve QR generation history for a specific user.
    """
    cursor = db.db.qr_history.find({"user_id": user_id}).sort("timestamp", -1)
    history = await cursor.to_list(length=100)
    for entry in history:
        entry["_id"] = str(entry["_id"])
    return history

async def get_qr_history_item(history_id: str, user_id: str):
    """
    Retrieve a specific QR history item by ID and user_id.
    """
    from bson.objectid import ObjectId
    try:
        item = await db.db.qr_history.find_one({
            "_id": ObjectId(history_id),
            "user_id": user_id
        })
        if item:
            item["_id"] = str(item["_id"])
        return item
    except Exception:
        return None

async def get_qr_history_item_public(history_id: str):
    """
    Retrieve a specific QR history item by ID ONLY (for public image viewing).
    """
    from bson.objectid import ObjectId
    try:
        item = await db.db.qr_history.find_one({
            "_id": ObjectId(history_id)
        })
        if item:
            item["_id"] = str(item["_id"])
        return item
    except Exception:
        return None

async def delete_qr_history_item(history_id: str, user_id: str) -> bool:
    """
    Delete a specific QR history item.
    """
    from bson.objectid import ObjectId
    try:
        # Get the item first to get the s3_key
        item = await db.db.qr_history.find_one({
            "_id": ObjectId(history_id),
            "user_id": user_id
        })
        
        if item and item.get("s3_key"):
            await S3Service.delete_file(item["s3_key"])

        result = await db.db.qr_history.delete_one({
            "_id": ObjectId(history_id),
            "user_id": user_id
        })
        return result.deleted_count > 0
    except Exception:
        return False
