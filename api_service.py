"""
API Microservice
Handles HTTP requests for QR code generation
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from qr_service import QRCodeService
from io import BytesIO
import re

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# Initialize QR Code Service
qr_service = QRCodeService()


def validate_url(url: str) -> bool:
    """
    Validate URL format
    
    Args:
        url: URL string to validate
    
    Returns:
        True if valid URL format, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    # Basic URL pattern validation
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None


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

