from datetime import datetime
from database import db
from typing import Optional

async def log_qr_generation(url: str, user_id: Optional[str] = None):
    """
    Log a QR code generation event to MongoDB.
    """
    log_entry = {
        "url": url,
        "user_id": user_id,
        "timestamp": datetime.utcnow(),
        "type": "qr_generation"
    }
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
