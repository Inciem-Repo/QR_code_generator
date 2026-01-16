from motor.motor_asyncio import AsyncIOMotorClient
from config import config

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect_db(cls):
        cls.client = AsyncIOMotorClient(config.MONGODB_URL)
        cls.db = cls.client[config.DATABASE_NAME]
        print(f"Connected to MongoDB: {config.DATABASE_NAME}")

    @classmethod
    async def close_db(cls):
        if cls.client:
            cls.client.close()
            print("Closed MongoDB connection")

db = Database
