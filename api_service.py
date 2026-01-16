"""
API Microservice
Handles HTTP requests for QR code generation and advertisement management.
"""

import json
import os
import re
import uuid
from functools import wraps
from io import BytesIO

from flask import Flask, jsonify, request, send_file, send_from_directory, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename

from qr_service import QRCodeService
from services.ads_service import AdsService
from services.admin_service import AdminService
from services.auth_service import find_user_by_id
from services.qr_history_service import log_qr_generation
from database import db
import asyncio
from utils.jwt_utils import create_access_token, decode_access_token

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

@app.after_request
def add_standard_fields(response):
    """
    Standardize all JSON responses to include message, status, and status_code.
    """
    if response.is_json:
        try:
            data = response.get_json()
            
            # Prepare standard fields
            status = "success" if response.status_code < 400 else "error"
            status_code = response.status_code
            message = "successful"
            
            if isinstance(data, dict):
                # Preserving existing message if present
                if "message" in data:
                    message = data.pop("message")
                # If there's an 'error' field but no 'message', use it
                elif "error" in data:
                    message = data["error"]
                
                standard_response = {
                    "status": status,
                    "status_code": status_code,
                    "message": message,
                    **data
                }
            else:
                # For lists or other types
                standard_response = {
                    "status": status,
                    "status_code": status_code,
                    "message": message,
                    "data": data
                }
            
            response.set_data(json.dumps(standard_response))
        except Exception:
            pass # Fallback to original
            
    return response

# Paths and configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ADS_DATA_FILE = os.path.join(BASE_DIR, "ads_data.json")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
VALID_PLACEMENTS = {
    "top-wide",
    "vertical-right",
    "left-1",
    "left-2",
    "bottom-wide-1",
    "bottom-wide-2",
    "mobile-bottom-1",
    "mobile-bottom-2",
}

ADMIN_USERNAME = "admin@123"
ADMIN_PASSWORD = "1234"

# Initialize QR Code Service
qr_service = QRCodeService()


def validate_url(url: str) -> bool:
    """
    Validate URL format.
    """
    if not url or not isinstance(url, str):
        return False

    url_pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return url_pattern.match(url) is not None


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def load_ads_data():
    """Load ads from disk."""
    if not os.path.exists(ADS_DATA_FILE):
        return []
    try:
        with open(ADS_DATA_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


def save_ads_data(ads):
    """Persist ads to disk."""
    with open(ADS_DATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(ads, fh, indent=2)


ads_data = load_ads_data()


def next_ad_id():
    """Generate the next ad id."""
    if not ads_data:
        return 1
    return max(ad["id"] for ad in ads_data) + 1


def require_auth(fn):
    """Decorator to require Bearer token for admin endpoints."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized", "message": "Missing Bearer token"}), 401
        token = auth_header.split(" ", 1)[1]
        
        payload = decode_access_token(token)
        if not payload or payload.get("role") != "admin":
            return jsonify({"error": "Unauthorized", "message": "Invalid or expired admin token"}), 401
            
        return fn(*args, **kwargs)

    return wrapper


def require_user(fn):
    """Decorator to require user authentication via bearer token (user_id)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Check header first then query param
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
        else:
            token = request.args.get("authorization")

        if not token:
            return jsonify({"error": "Unauthorized", "message": "Authentication required (Token or query param)"}), 401
        
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            return jsonify({"error": "Unauthorized", "message": "Invalid or expired user token"}), 401
            
        user_id = payload["sub"]
        user = asyncio.run(find_user_by_id(user_id))
        if not user:
            return jsonify({"error": "Unauthorized", "message": "User not found"}), 401
            
        # Add user to request for use in route
        request.user = user
        return fn(*args, **kwargs)

    return wrapper


def load_settings():
    """Load global settings."""
    settings_file = os.path.join(BASE_DIR, "settings.json")
    if not os.path.exists(settings_file):
        return {"ads_enabled": True}
    try:
        with open(settings_file, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"ads_enabled": True}


def save_settings(settings):
    """Save global settings."""
    settings_file = os.path.join(BASE_DIR, "settings.json")
    with open(settings_file, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)


def is_ads_enabled():
    """Check if ads are globally enabled."""
    return load_settings().get("ads_enabled", True)


def serialize_ad(ad: dict) -> dict:
    """Return ad with consistent keys."""
    return {
        "id": ad["id"],
        "placement": ad["placement"],
        "imageUrl": ad["imageUrl"],
        "redirectUrl": ad["redirectUrl"],
        "isActive": bool(ad.get("isActive", True)),
    }


@app.route("/uploads/<path:filename>", methods=["GET"])
def serve_uploaded_file(filename):
    """Serve uploaded ad images publicly."""
    return send_from_directory(UPLOAD_FOLDER, filename)


# ---------------------- Admin Authentication ---------------------- #
@app.route("/admin/login", methods=["POST"])
def admin_login():
    """Simple admin login returning a bearer token."""
    payload = request.get_json(silent=True) or {}
    username = payload.get("username")
    password = payload.get("password")

    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        return jsonify({"error": "Unauthorized", "message": "Invalid credentials"}), 401

    from services.auth_service import find_user_by_email, create_user
    admin_user = asyncio.run(find_user_by_email(username))
    
    if not admin_user:
        admin_user = asyncio.run(create_user(
            name="Admin",
            email=username,
            role="admin"
        ))
    
    mongo_id = admin_user.get("mongo_id")

    token = create_access_token(data={
        "sub": username,
        "mongo_id": mongo_id,
        "name": "Admin",
        "role": "admin"
    })
    return jsonify({"token": token, "tokenType": "Bearer"}), 200


@app.route("/admin/ads/status", methods=["GET"])
def get_global_ads_status():
    """Get the current global status of advertisements."""
    return jsonify({"ads_enabled": is_ads_enabled()}), 200


@app.route("/admin/ads/toggle", methods=["POST"])
@require_auth
def toggle_global_ads():
    """Enable or disable advertisements globally."""
    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled")
    if enabled is None:
        return jsonify({"error": "Bad Request", "message": "Missing 'enabled' boolean"}), 400
    
    settings = load_settings()
    settings["ads_enabled"] = bool(enabled)
    save_settings(settings)
    
    return jsonify({
        "message": f"Ads {'enabled' if settings['ads_enabled'] else 'disabled'} successfully",
        "ads_enabled": settings["ads_enabled"]
    }), 200



@app.route("/ads", methods=["POST"])
@require_auth
def create_ad():
    """Create a new advertisement with image upload."""
    placement = request.form.get("placement")
    redirect_url = request.form.get("redirectUrl")
    is_active_raw = request.form.get("isActive", "true").lower()
    is_active = is_active_raw not in {"false", "0", "no"}

    image = request.files.get("image")
    if not placement or placement not in VALID_PLACEMENTS:
        return jsonify({"error": "Invalid placement", "message": "Placement must match allowed list"}), 400
    if redirect_url and not validate_url(redirect_url):
        return jsonify({"error": "Invalid redirectUrl", "message": "Provide a valid http/https URL"}), 400
    if not image or image.filename == "":
        return jsonify({"error": "Image required", "message": "Upload an image file under 'image' field"}), 400
    if not allowed_file(image.filename):
        return jsonify({"error": "Invalid image type", "message": f"Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"}), 400

    filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
    image_path = os.path.join(UPLOAD_FOLDER, filename)
    image.save(image_path)
    image_url = url_for("serve_uploaded_file", filename=filename, _external=True)

    ad = {
        "id": next_ad_id(),
        "placement": placement,
        "imageUrl": image_url,
        "redirectUrl": redirect_url,
        "isActive": is_active,
        "imagePath": image_path,
    }
    ads_data.append(ad)
    save_ads_data(ads_data)

    return jsonify(serialize_ad(ad)), 201


@app.route("/ads", methods=["GET"])
def list_ads():
    """List advertisements, optionally filtered by placement."""
    if not asyncio.run(AdminService.is_ads_enabled()):
        return jsonify([]), 200

    placement = request.args.get("placement")
    ads = asyncio.run(AdsService.get_all_ads(placement=placement, only_active=True))
    return jsonify([serialize_ad(ad) for ad in ads]), 200


@app.route("/ads/<int:ad_id>", methods=["PUT"])
@require_auth
def update_ad(ad_id: int):
    """Update an advertisement (metadata and/or image)."""
    ad = next((item for item in ads_data if item["id"] == ad_id), None)
    if not ad:
        return jsonify({"error": "Not found", "message": "Ad does not exist"}), 404

    # Support JSON or multipart form for flexibility
    if request.files or request.form:
        data = request.form
        redirect_url = data.get("redirectUrl", ad["redirectUrl"])
        placement = data.get("placement", ad["placement"])
        is_active_raw = data.get("isActive")
    else:
        data = request.get_json(silent=True) or {}
        redirect_url = data.get("redirectUrl", ad["redirectUrl"])
        placement = data.get("placement", ad["placement"])
        is_active_raw = data.get("isActive")

    if placement not in VALID_PLACEMENTS:
        return jsonify({"error": "Invalid placement", "message": "Placement must match allowed list"}), 400
    if redirect_url and not validate_url(redirect_url):
        return jsonify({"error": "Invalid redirectUrl", "message": "Provide a valid http/https URL"}), 400

    if is_active_raw is not None:
        ad["isActive"] = bool(is_active_raw) if isinstance(is_active_raw, bool) else str(is_active_raw).lower() not in {"false", "0", "no"}
    ad["placement"] = placement
    ad["redirectUrl"] = redirect_url

    image = request.files.get("image") if request.files else None
    if image and image.filename:
        if not allowed_file(image.filename):
            return jsonify({"error": "Invalid image type", "message": f"Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"}), 400
        filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        image.save(image_path)
        old_path = ad.get("imagePath")
        if old_path and os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass
        ad["imagePath"] = image_path
        ad["imageUrl"] = url_for("serve_uploaded_file", filename=filename, _external=True)

    save_ads_data(ads_data)
    return jsonify(serialize_ad(ad)), 200


@app.route("/ads/<int:ad_id>", methods=["DELETE"])
@require_auth
def delete_ad(ad_id: int):
    """Delete an advertisement."""
    global ads_data
    ad = next((item for item in ads_data if item["id"] == ad_id), None)
    if not ad:
        return jsonify({"error": "Not found", "message": "Ad does not exist"}), 404

    ads_data = [item for item in ads_data if item["id"] != ad_id]
    image_path = ad.get("imagePath")
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
        except OSError:
            pass
    save_ads_data(ads_data)
    return jsonify({"deleted": ad_id}), 200


@app.route("/ads/<int:ad_id>/status", methods=["POST"])
@require_auth
def set_ad_status(ad_id: int):
    """Explicitly enable or disable a specific advertisement."""
    ad = next((item for item in ads_data if item["id"] == ad_id), None)
    if not ad:
        return jsonify({"error": "Not found", "message": "Ad does not exist"}), 404
    
    data = request.get_json(silent=True) or {}
    is_active = data.get("isActive")
    if is_active is None:
        return jsonify({"error": "Bad Request", "message": "Missing 'isActive' boolean"}), 400
    
    ad["isActive"] = bool(is_active)
    save_ads_data(ads_data)
    
    status_str = "enabled" if ad["isActive"] else "disabled"
    return jsonify({
        "message": f"Ad {ad_id} {status_str} successfully",
        "ad_id": ad_id,
        "isActive": ad["isActive"]
    }), 200


@app.route("/ads/<int:ad_id>/toggle", methods=["POST"])
@require_auth
def toggle_ad_status(ad_id: int):
    """Toggle the active status of a specific advertisement."""
    ad = next((item for item in ads_data if item["id"] == ad_id), None)
    if not ad:
        return jsonify({"error": "Not found", "message": "Ad does not exist"}), 404
    
    ad["isActive"] = not ad.get("isActive", True)
    save_ads_data(ads_data)
    
    status_str = "enabled" if ad["isActive"] else "disabled"
    return jsonify({
        "message": f"Ad {ad_id} {status_str} successfully",
        "ad_id": ad_id,
        "isActive": ad["isActive"]
    }), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "QR Code API Service"
    }), 200


@app.route('/generate', methods=['POST'])
@require_user
def generate_qr_code():
    """
    Generate QR code from URL
    
    Request body (JSON):
        {
            "url": "https://www.example.com"
        }
    
    Returns:
        JSON response with base64 encoded QR code image or error message
    """
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                "error": "No data provided",
                "message": "Please provide a JSON object with 'url' field"
            }), 400
        
        url = data.get('url')
        
        if not url:
            return jsonify({
                "error": "URL is required",
                "message": "Please provide a 'url' field in the request body"
            }), 400
        
        # Validate URL format
        if not validate_url(url):
            return jsonify({
                "error": "Invalid URL format",
                "message": "Please provide a valid URL (e.g., https://www.example.com)"
            }), 400
        
        # Generate QR code
        qr_code_base64 = qr_service.generate_qr_code_base64(url)
        
        if qr_code_base64:
            asyncio.run(log_qr_generation(url, request.user["id"]))
            return jsonify({
                "success": True,
                "url": url,
                "qr_code": qr_code_base64,
                "format": "PNG",
                "message": "QR code generated successfully"
            }), 200
        else:
            return jsonify({
                "error": "QR code generation failed",
                "message": "Failed to generate QR code. Please try again."
            }), 500
            
    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@app.route('/generate/image', methods=['POST'])
@require_user
def generate_qr_code_image():
    """
    Generate QR code and return as image file
    
    Request body (JSON):
        {
            "url": "https://www.example.com"
        }
    
    Returns:
        PNG image file
    """
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                "error": "No data provided",
                "message": "Please provide a JSON object with 'url' field"
            }), 400
        
        url = data.get('url')
        
        if not url:
            return jsonify({
                "error": "URL is required",
                "message": "Please provide a 'url' field in the request body"
            }), 400
        
        # Validate URL format
        if not validate_url(url):
            return jsonify({
                "error": "Invalid URL format",
                "message": "Please provide a valid URL (e.g., https://www.example.com)"
            }), 400
        
        # Generate QR code
        qr_code_bytes = qr_service.generate_qr_code(url)
        
        if qr_code_bytes:
            asyncio.run(log_qr_generation(url, request.user["id"]))
            return send_file(
                BytesIO(qr_code_bytes),
                mimetype='image/png',
                as_attachment=True,
                download_name='qrcode.png'
            )
        else:
            return jsonify({
                "error": "QR code generation failed",
                "message": "Failed to generate QR code. Please try again."
            }), 500
            
    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@app.route('/generate/<path:url>', methods=['GET'])
@require_user
def generate_qr_code_get(url):
    """
    Generate QR code from URL via GET request
    
    Args:
        url: URL to encode (passed as path parameter)
    
    Returns:
        PNG image file
    """
    try:
        # Decode URL if needed
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'https://' + url
        
        # Validate URL format
        if not validate_url(url):
            return jsonify({
                "error": "Invalid URL format",
                "message": "Please provide a valid URL"
            }), 400
        
        # Generate QR code
        qr_code_bytes = qr_service.generate_qr_code(url)
        
        if qr_code_bytes:
            asyncio.run(log_qr_generation(url, request.user["id"]))
            return send_file(
                BytesIO(qr_code_bytes),
                mimetype='image/png',
                as_attachment=False
            )
        else:
            return jsonify({
                "error": "QR code generation failed",
                "message": "Failed to generate QR code. Please try again."
            }), 500
            
    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


if __name__ == "__main__":
    print("Starting QR Code API Service...")
    print("API Endpoints:")
    print("  POST /generate - Generate QR code (returns JSON with base64)")
    print("  POST /generate/image - Generate QR code (returns PNG image)")
    print("  GET /generate/<url> - Generate QR code via GET (returns PNG image)")
    print("  GET /health - Health check")
    app.run(host='0.0.0.0', port=5000, debug=True)