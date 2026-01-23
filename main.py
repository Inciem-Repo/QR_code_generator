import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers import auth, qr, admin
import json


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_standard_response_fields(request: Request, call_next):
    
    response = await call_next(request)
    

    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
      
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
            
        try:
            data = json.loads(body)
            original_data = data
            
       
            status = "failed" if response.status_code >= 400 else "success"
            status_code = response.status_code
            
         
            is_login_path = "/login" in request.url.path or "/auth/login" in request.url.path
            
            if response.status_code == 200 and is_login_path:
                message = "login successful"
            elif response.status_code == 401:
                if is_login_path:
                    message = "email/password is wrong"
                else:
                    message = "Unauthorized"
            elif response.status_code >= 400:
                message = "login failed" if is_login_path else "An error occurred"
            else:
                message = "successful"
            
            if isinstance(data, dict):
                
                if "message" in data:
                    message = data.pop("message")
                
                if "detail" in data and len(data) == 1:
                    detail = data.pop("detail")
                    if response.status_code == 401:
                        message = "email/password is wrong" if is_login_path else str(detail)
                    else:
                        message = str(detail)
                
                standard_response = {
                    "status": status,
                    "status_code": status_code,
                    "message": message,
                    **data
                }
            else:
                
                standard_response = {
                    "status": status,
                    "status_code": status_code,
                    "message": message,
                    "data": data
                }
                
            new_content = json.dumps(standard_response).encode("utf-8")
            
          
            return JSONResponse(
                content=standard_response,
                status_code=response.status_code,
                headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"}
            )
            
        except Exception:
       
            from fastapi.responses import Response
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=content_type
            )
            
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    is_login_path = "/login" in request.url.path or "/auth/login" in request.url.path
    message = str(exc.detail) if hasattr(exc, "detail") else "No detail provided"
    
    
    if exc.status_code == 401 and is_login_path:
        message = "email/password is wrong"
    elif exc.status_code >= 400 and is_login_path and message == "login failed":
       
        pass

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "failed",
            "status_code": exc.status_code,
            "message": message,
        },
    )

@app.exception_handler(Exception)
async def universal_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "status_code": 500,
            "message": "Internal Server Error",
            "detail": str(exc)
        },
    )


app.include_router(auth.router, prefix="/auth")
app.include_router(auth.user_router)
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
    print("\nAPI Service running on http://192.168.53.163:5000")
    print("\nAvailable Endpoints:")
    print("  POST /generate - Generate QR code (JSON)")
    print("  GET  /generate/{url} - Generate QR code (Image)")
    print("  POST /auth/send-otp - Request login OTP")
    print("  POST /auth/verify-otp - Verify OTP only")
    print("  POST /auth/login - Login/Auto-register with OTP")
    print("\nDocumentation available at http://192.168.53.163:5000/docs")
    print("\n" + "=" * 50)
    
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)