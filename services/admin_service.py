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
    async def get_dashboard_stats() -> Dict[str, Any]:
        total_qr_codes = await db.db.qr_history.count_documents({})
        active_users = await db.db.users.count_documents({})
        activated_ads = await db.db.ads.count_documents({"isActive": True})
        
        return {
            "total_qr_codes": total_qr_codes,
            "active_users": active_users,
            "activated_ads": activated_ads
        }

    @staticmethod
    async def get_admin_profile() -> Dict[str, Any]:
        profile = await db.db.settings.find_one({"type": "admin_profile"})
        if not profile:
            default_profile = {
                "type": "admin_profile",
                "name": "Admin",
                "email": "admin@123",
                "logo_url": None,
                "profile_image_url": None,
                "logo_key": None,
                "profile_image_key": None
            }
            await db.db.settings.insert_one(default_profile)
            return default_profile
        
        # Remove internal keys for response
        res = profile.copy()
        res["_id"] = str(res["_id"])
        return res

    @staticmethod
    async def update_admin_profile(update_data: Dict[str, Any]):
        # Filter allowed fields
        allowed_fields = {"name", "email"}
        filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        if not filtered_data:
            return await AdminService.get_admin_profile()

        await db.db.settings.update_one(
            {"type": "admin_profile"},
            {"$set": filtered_data},
            upsert=True
        )
        return await AdminService.get_admin_profile()

    @staticmethod
    async def update_admin_images(logo_content=None, logo_name=None, logo_type=None, profile_image_content=None, profile_image_name=None, profile_image_type=None):
        from utils.s3_utils import S3Service
        import uuid
        
        update_data = {}
        current_profile = await AdminService.get_admin_profile()

        if logo_content:
            logo_key = f"admin/logo_{uuid.uuid4().hex}_{logo_name}"
            logo_url = await S3Service.upload_file(logo_content, logo_key, content_type=logo_type)
            if logo_url:
                update_data["logo_url"] = logo_url
                update_data["logo_key"] = logo_key
                # Cleanup old logo
                if current_profile.get("logo_key"):
                    await S3Service.delete_file(current_profile["logo_key"])

        if profile_image_content:
            profile_key = f"admin/profile_{uuid.uuid4().hex}_{profile_image_name}"
            profile_url = await S3Service.upload_file(profile_image_content, profile_key, content_type=profile_image_type)
            if profile_url:
                update_data["profile_image_url"] = profile_url
                update_data["profile_image_key"] = profile_key
                # Cleanup old profile image
                if current_profile.get("profile_image_key"):
                    await S3Service.delete_file(current_profile["profile_image_key"])

        if update_data:
            await db.db.settings.update_one(
                {"type": "admin_profile"},
                {"$set": update_data},
                upsert=True
            )
            
        return await AdminService.get_admin_profile()
