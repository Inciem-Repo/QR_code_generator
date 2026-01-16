import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, qr, admin


from database import db

app = FastAPI(
    title="QR Code Generator API",
    description="API for QR code generation and advertisement management with authentication.",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_db_client():
    await db.connect_db()

@app.on_event("shutdown")
async def shutdown_db_client():
    await db.close_db()

# CORS Configuration

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix="/auth")
app.include_router(qr.router)
app.include_router(admin.router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to the QR Code Generator API",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    print("=" * 50)
    print("QR Code Generator - FastAPI Backend")
    print("=" * 50)
    print("\nStarting services...")
    print("\nAPI Service running on http://localhost:5000")
    print("\nAvailable Endpoints:")
    print("  POST /generate - Generate QR code (JSON)")
    print("  GET  /generate/{url} - Generate QR code (Image)")
    print("  POST /auth/send-otp - Request login OTP")
    print("  POST /auth/login - Login/Auto-register with OTP")
    print("\nDocumentation available at http://localhost:5000/docs")
    print("\n" + "=" * 50)
    
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)