import json
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import config

async def migrate_ads():
    # Setup MongoDB
    client = AsyncIOMotorClient(config.MONGODB_URL)
    db = client[config.DATABASE_NAME]
    
    # Path to JSON
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    ADS_DATA_FILE = os.path.join(BASE_DIR, "ads_data.json")
    
    if os.path.exists(ADS_DATA_FILE):
        print(f"Reading ads from {ADS_DATA_FILE}...")
        try:
            with open(ADS_DATA_FILE, "r", encoding="utf-8") as fh:
                ads = json.load(fh)
            
            if ads:
                print(f"Migrating {len(ads)} ads to MongoDB...")
                # Clear existing ads to avoid duplicates during migration
                await db.ads.delete_many({})
                
                # Insert ads
                # MongoDB doesn't like 'id' being an existing field if we want it to be unique, 
                # but we'll keep it as a field.
                await db.ads.insert_many(ads)
                print("Migration successful!")
            else:
                print("No ads found in JSON file.")
        except Exception as e:
            print(f"Migration failed: {e}")
    else:
        print("JSON ads file not found. Skipping migration.")
        
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate_ads())
