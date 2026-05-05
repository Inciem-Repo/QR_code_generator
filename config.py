import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "qr_code_generator")
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-for-jwt-if-needed")
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    
config = Config()
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

