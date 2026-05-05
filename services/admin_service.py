from database import db
from typing import Dict, Any

class AdminService:
    @staticmethod
    async def get_settings() -> Dict[str, Any]:
        settings = await db.db.settings.find_one({"type": "global"})
        if not settings:
            # Default settings
            default_settings = {
                "type": "global",
                "ads_enabled": True
            }
            await db.db.settings.insert_one(default_settings)
            return default_settings
        return settings

    @staticmethod
    async def set_ads_enabled(enabled: bool):
        await db.db.settings.update_one(
            {"type": "global"},
            {"$set": {"ads_enabled": enabled}},
            upsert=True
        )
        return {"ads_enabled": enabled}

    @staticmethod
    async def is_ads_enabled() -> bool:
        settings = await AdminService.get_settings()
        return settings.get("ads_enabled", True)

    @staticmethod
    async def update_profile(data: Dict[str, Any]):
        await db.db.settings.update_one(
            {"type": "global"},
            {"$set": data},
            upsert=True
        )
        return await AdminService.get_profile()

    @staticmethod
    async def get_profile() -> Dict[str, Any]:
        settings = await AdminService.get_settings()
        return {
            "logo": settings.get("logo"),
            "profile_image": settings.get("profile_image"),
            "ads_enabled": settings.get("ads_enabled", True)
        }

    @staticmethod
    async def get_dashboard_stats() -> Dict[str, Any]:
        total_qr_codes = await db.db.qr_history.count_documents({})
        active_users = await db.db.users.count_documents({})
        activated_ads = await db.db.ads.count_documents({"isActive": True})
        profile = await AdminService.get_profile()
        
        return {
            "total_qr_codes": total_qr_codes,
            "active_users": active_users,
            "activated_ads": activated_ads,
            "admin_profile": profile
        }
