"""
Main Application Entry Point
Orchestrates the microservices
"""

from api_service import app
import sys

def main():
    """Main entry point for the application"""
    print("=" * 50)
    print("QR Code Generator - Microservices Architecture")
    print("=" * 50)
    print("\nStarting services...")
    print("\nAPI Service running on http://localhost:5000")
    print("\nAvailable Endpoints:")
    print("  POST http://localhost:5000/generate")
    print("     Body: {\"url\": \"https://www.example.com\"}")
    print("     Returns: JSON with base64 encoded QR code")
    print("\n  POST http://localhost:5000/generate/image")
    print("     Body: {\"url\": \"https://www.example.com\"}")
    print("     Returns: PNG image file")
    print("\n  GET http://localhost:5000/generate/<url>")
    print("     Returns: PNG image file")
    print("\n  GET http://localhost:5000/health")
    print("     Returns: Health status")
    print("\n" + "=" * 50)
    print("Press Ctrl+C to stop the server")
    print("=" * 50 + "\n")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\n\nShutting down services...")
        sys.exit(0)


if __name__ == "__main__":
    main()