import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "qr_code_generator")
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-for-jwt-if-needed")
    
config = Config()

