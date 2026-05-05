import asyncio
import os
import sys
from bson.objectid import ObjectId

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import db

async def inspect():
    await db.connect_db()
    print("--- QR History Inspection ---")
    history = await db.db.qr_history.find().sort("timestamp", -1).limit(10).to_list(None)
    for entry in history:
        print(f"ID: {entry['_id']}")
        print(f"  Date: {entry.get('timestamp')}")
        print(f"  URL: {entry.get('url')}")
        print(f"  Type: {entry.get('type')}")
        qr_code = entry.get('qr_code')
        if qr_code:
            print(f"  QR Code (first 100 chars): {qr_code[:100]}")
            if qr_code.startswith("data:"):
                print("  [INFO] Has data URL prefix")
            else:
                print("  [INFO] MISSING data URL prefix")
        else:
            print("  QR Code: MISSING")
        print("-" * 30)
            
    await db.close_db()

if __name__ == "__main__":
    asyncio.run(inspect())
