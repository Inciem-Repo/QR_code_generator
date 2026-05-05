from database import db
from typing import List, Optional, Dict, Any
from datetime import datetime

class AdsService:
    @staticmethod
    async def get_all_ads(placement: Optional[str] = None, only_active: bool = False) -> List[Dict[str, Any]]:
        query = {}
        if placement:
            query["placement"] = placement

        cursor = db.db.ads.find(query)
        ads = await cursor.to_list(length=100)
        
        return ads

    @staticmethod
    async def create_ad(ad_data: Dict[str, Any]) -> Dict[str, Any]:
        
        last_ad = await db.db.ads.find_one(sort=[("id", -1)])
        new_id = (last_ad["id"] + 1) if last_ad and "id" in last_ad else 1
        
        ad_data["id"] = new_id
        ad_data["created_at"] = datetime.utcnow()
        
        result = await db.db.ads.insert_one(ad_data)
        ad_data["_id"] = str(result.inserted_id)
        return ad_data

    @staticmethod
    async def get_ad_by_id(ad_id: int) -> Optional[Dict[str, Any]]:
        ad = await db.db.ads.find_one({"id": ad_id})
        if ad:
            ad["_id"] = str(ad["_id"])
        return ad

    @staticmethod
    async def update_ad(ad_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        await db.db.ads.update_one({"id": ad_id}, {"$set": update_data})
        return await AdsService.get_ad_by_id(ad_id)

    @staticmethod
    async def delete_ad(ad_id: int) -> bool:
        result = await db.db.ads.delete_one({"id": ad_id})
        return result.deleted_count > 0

    @staticmethod
    async def toggle_ad_status(ad_id: int) -> Optional[Dict[str, Any]]:
        ad = await AdsService.get_ad_by_id(ad_id)
        if not ad:
            return None
        
        new_status = not ad.get("isActive", True)
        return await AdsService.update_ad(ad_id, {"isActive": new_status})
