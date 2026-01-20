import uuid
import random
import string
from typing import Optional, Dict, List
from datetime import datetime
from database import db

async def find_user_by_email(email: str) -> Optional[Dict]:
    user = await db.db.users.find_one({"email": email})
    if user:
        user["mongo_id"] = str(user["_id"])
        user["_id"] = str(user["_id"])
    return user

async def find_user_by_id(user_id: str) -> Optional[Dict]:
    user = await db.db.users.find_one({"id": user_id})
    if user:
        user["mongo_id"] = str(user["_id"])
        user["_id"] = str(user["_id"])
    return user

async def find_user_by_mongo_id(mongo_id: str) -> Optional[Dict]:
    from bson.objectid import ObjectId
    try:
        user = await db.db.users.find_one({"_id": ObjectId(mongo_id)})
        if user:
            user["mongo_id"] = str(user["_id"])
            user["_id"] = str(user["_id"])
        return user
    except Exception:
        return None

async def create_user(name: str, email: str, profile_pic: Optional[str] = None, login_type: str = "email", role: str = "user") -> Dict:
    """Create a new user. Passwords are NO LONGER stored in the database."""
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "name": name,
        "email": email,
        "email_verified": True,
        "profile_pic": profile_pic,
        "login_type": login_type,  # "email" or "google"
        "role": role,
        "created_at": datetime.utcnow().isoformat()
    }
    await db.db.users.insert_one(user)
    user["mongo_id"] = str(user["_id"])
    user["_id"] = str(user["_id"])
    return user

async def create_google_user(name: str, email: str, profile_pic: Optional[str] = None) -> Dict:
    """Create a new user via Google OAuth."""
    return await create_user(name, email, profile_pic, "google")

def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))

async def save_otp(email: str, otp: str):
    await db.db.otps.update_one(
        {"email": email},
        {"$set": {"otp": otp, "created_at": datetime.utcnow()}},
        upsert=True
    )

async def verify_otp(email: str, otp: str) -> bool:
    record = await db.db.otps.find_one({"email": email})
    if record and record["otp"] == otp:
        # Optional: delete after verification
        # await db.db.otps.delete_one({"email": email})
        return True
    return False

async def log_user_login(user_id: str, email: str, login_type: str):
    """Log a user login event to MongoDB."""
    log_entry = {
        "user_id": user_id,
        "email": email,
        "login_type": login_type,
        "timestamp": datetime.utcnow(),
        "type": "user_login"
    }
    await db.db.user_logs.insert_one(log_entry)
    print(f"Logged user login: {email} (ID: {user_id})")

async def get_user_login_history(user_id: str):
    """Retrieve login history for a specific user."""
    cursor = db.db.user_logs.find({"user_id": user_id}).sort("timestamp", -1)
    logs = await cursor.to_list(length=100)
    for log in logs:
        log["_id"] = str(log["_id"])
    return logs
