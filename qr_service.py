"""
QR Code Generation Microservice
Handles QR code generation from URLs
"""

import qrcode
from io import BytesIO
from typing import Optional
import base64


class QRCodeService:
    """Service for generating QR codes from URLs"""
    
    def __init__(self, box_size: int = 10, border: int = 4):
        """
        Initialize QR Code Service
        
        Args:
            box_size: Size of each box in the QR code
            border: Border thickness
        """
        self.box_size = box_size
        self.border = border
    
    def generate_qr_code(self, url: str, format: str = 'PNG') -> Optional[bytes]:
        """
        Generate QR code from URL
        
        Args:
            url: The URL to encode in the QR code
            format: Image format (PNG, JPEG, etc.)
        
        Returns:
            Bytes of the generated QR code image, or None if error
        """
        try:
            # Validate URL format
            if not url or not isinstance(url, str):
                raise ValueError("URL must be a non-empty string")
            
            # Create QR code instance
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=self.box_size,
                border=self.border,
            )
            
            # Add data (URL) to QR code
            qr.add_data(url)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to bytes
            img_buffer = BytesIO()
            img.save(img_buffer, format=format)
            img_bytes = img_buffer.getvalue()
            img_buffer.close()
            
            return img_bytes
            
        except Exception as e:
            print(f"Error generating QR code: {str(e)}")
            return None
    
    def generate_qr_code_base64(self, url: str, format: str = 'PNG') -> Optional[str]:
        """
        Generate QR code and return as base64 encoded string
        
        Args:
            url: The URL to encode in the QR code
            format: Image format (PNG, JPEG, etc.)
        
        Returns:
            Base64 encoded string of the QR code image, or None if error
        """
        img_bytes = self.generate_qr_code(url, format)
        if img_bytes:
            return base64.b64encode(img_bytes).decode('utf-8')
        return None
    
    def save_qr_code(self, url: str, filename: str, format: str = 'PNG') -> bool:
        """
        Generate and save QR code to file
        
        Args:
            url: The URL to encode in the QR code
            filename: Output filename
            format: Image format (PNG, JPEG, etc.)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            img_bytes = self.generate_qr_code(url, format)
            if img_bytes:
                with open(filename, 'wb') as f:
                    f.write(img_bytes)
                return True
            return False
        except Exception as e:
            print(f"Error saving QR code: {str(e)}")
            return False


# Standalone service runner (for testing)
if __name__ == "__main__":
    service = QRCodeService()
    
    # Test with a sample URL
    test_url = "https://www.example.com"
    print(f"Generating QR code for: {test_url}")
    
    # Generate and save
    output_file = "test_qr_code.png"
    if service.save_qr_code(test_url, output_file):
        print(f"QR code saved to {output_file}")
    else:
        print("Failed to generate QR code")

