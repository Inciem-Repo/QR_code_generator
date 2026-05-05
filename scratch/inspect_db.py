import asyncio
import os
import sys
from bson.objectid import ObjectId

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import db

async def inspect():
    await db.connect_db()
    print("Checking QR History...")
    history = await db.db.qr_history.find().sort("timestamp", -1).limit(5).to_list(None)
    for entry in history:
        print(f"ID: {entry['_id']}, Date: {entry.get('timestamp')}, Type: {entry.get('type')}")
        qr_code = entry.get('qr_code')
        if qr_code:
            print(f"  QR Code Length: {len(qr_code)}")
            print(f"  QR Code Start: {qr_code[:50]}...")
        else:
            print("  QR Code: MISSING")
            
    print("\nChecking Ads...")
    ads = await db.db.ads.find().to_list(None)
    for ad in ads:
        print(f"ID: {ad.get('id')}, URL: {ad.get('redirectUrl')}, Image: {ad.get('imageUrl')}")
        
    await db.close_db()

if __name__ == "__main__":
    asyncio.run(inspect())
