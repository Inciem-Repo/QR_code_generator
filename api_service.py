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

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

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

# In-memory state for simplicity
active_tokens = set()

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
        if token not in active_tokens:
            return jsonify({"error": "Unauthorized", "message": "Invalid or expired token"}), 401
        return fn(*args, **kwargs)

    return wrapper


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

    token = uuid.uuid4().hex
    active_tokens.add(token)
    return jsonify({"token": token, "tokenType": "Bearer"}), 200


# ---------------------- Ads CRUD ---------------------- #
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
    placement = request.args.get("placement")
    results = ads_data
    if placement:
        results = [ad for ad in ads_data if ad["placement"] == placement]
    return jsonify([serialize_ad(ad) for ad in results]), 200


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


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "QR Code API Service"
    }), 200


@app.route('/generate', methods=['POST'])
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