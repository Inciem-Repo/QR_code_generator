from datetime import datetime
from database import db
from typing import Optional

async def log_qr_generation(url: str, qr_code: str, user_id: Optional[str] = None, base_url: Optional[str] = None):
    """
    Log a QR code generation event to MongoDB.
    """
    from bson.objectid import ObjectId
    history_id = ObjectId()
    
    log_entry = {
        "_id": history_id,
        "url": url,
        "qr_code": qr_code,
        "user_id": user_id,
        "timestamp": datetime.utcnow(),
        "type": "qr_generation"
    }
    
    if base_url:
        log_entry["qr_image_url"] = f"{base_url}/history/{str(history_id)}/image"
        
    await db.db.qr_history.insert_one(log_entry)
    print(f"Logged QR generation: {url} (User: {user_id})")

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
        result = await db.db.qr_history.delete_one({
            "_id": ObjectId(history_id),
            "user_id": user_id
        })
        return result.deleted_count > 0
    except Exception:
        return False
