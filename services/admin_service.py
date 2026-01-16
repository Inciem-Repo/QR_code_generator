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
