"""
QR Code Generation Microservice
Handles QR code generation from URLs with customization options
"""

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import (
    SquareModuleDrawer,
    RoundedModuleDrawer,
    CircleModuleDrawer,
    VerticalBarsDrawer,
    HorizontalBarsDrawer
)
from qrcode.image.styles.colormasks import SolidFillColorMask
from io import BytesIO
from typing import Optional, Union, Tuple
import base64
from PIL import Image, ImageDraw


class QRCodeService:
    """Service for generating QR codes from URLs with customization options"""
    
    # Pattern style mapping
    PATTERN_STYLES = {
        'square': SquareModuleDrawer,
        'rounded': RoundedModuleDrawer,
        'dots': CircleModuleDrawer,
        'vertical_bars': VerticalBarsDrawer,
        'horizontal_bars': HorizontalBarsDrawer
    }
    
    # Error correction level mapping
    ERROR_CORRECTION_LEVELS = {
        'L': qrcode.constants.ERROR_CORRECT_L,  # 7% recovery
        'M': qrcode.constants.ERROR_CORRECT_M,  # 15% recovery
        'Q': qrcode.constants.ERROR_CORRECT_Q,  # 25% recovery
        'H': qrcode.constants.ERROR_CORRECT_H   # 30% recovery
    }
    
    def __init__(self, box_size: int = 10, border: int = 4):
        """
        Initialize QR Code Service
        
        Args:
            box_size: Size of each box in the QR code
            border: Border thickness
        """
        self.box_size = box_size
        self.border = border
    
    
    # Color name to RGB mapping
    COLOR_MAP = {
        'black': (0, 0, 0),
        'white': (255, 255, 255),
        'red': (255, 0, 0),
        'green': (0, 128, 0),
        'blue': (0, 0, 255),
        'yellow': (255, 255, 0),
        'cyan': (0, 255, 255),
        'magenta': (255, 0, 255),
        'orange': (255, 165, 0),
        'purple': (128, 0, 128),
        'pink': (255, 192, 203),
        'brown': (165, 42, 42),
        'gray': (128, 128, 128),
        'grey': (128, 128, 128),
    }
    
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            # Convert #RGB to #RRGGBB
            hex_color = ''.join([c*2 for c in hex_color])
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _parse_color(self, color: Union[str, Tuple[int, int, int]]) -> Tuple[int, int, int]:
        """
        Parse and validate color input, always returning RGB tuple
        
        Args:
            color: Color as hex string, color name, or RGB tuple
            
        Returns:
            Validated color as RGB tuple
        """
        if isinstance(color, str):
            # Convert color names to RGB tuples
            color_lower = color.lower()
            if color_lower in self.COLOR_MAP:
                return self.COLOR_MAP[color_lower]
            
            # Convert hex color to RGB
            if not color.startswith('#'):
                color = f'#{color}'
            if len(color) not in [4, 7]:  # #RGB or #RRGGBB
                raise ValueError(f"Invalid hex color format: {color}")
            return self._hex_to_rgb(color)
        elif isinstance(color, (list, tuple)) and len(color) == 3:
            # Validate RGB tuple
            if not all(0 <= c <= 255 for c in color):
                raise ValueError(f"RGB values must be between 0 and 255: {color}")
            return tuple(color)
        else:
            raise ValueError(f"Color must be hex string, color name, or RGB tuple: {color}")
    
    def _decode_logo(self, logo_data: str) -> Optional[Image.Image]:
        """
        Decode base64 logo image
        
        Args:
            logo_data: Base64 encoded image string
            
        Returns:
            PIL Image object or None
        """
        try:
            # Remove data URL prefix if present
            if ',' in logo_data:
                logo_data = logo_data.split(',', 1)[1]
            
            # Decode base64
            logo_bytes = base64.b64decode(logo_data)
            logo_image = Image.open(BytesIO(logo_bytes))
            
            # Convert to RGBA for transparency support
            if logo_image.mode != 'RGBA':
                logo_image = logo_image.convert('RGBA')
            
            return logo_image
        except Exception as e:
            print(f"Error decoding logo: {str(e)}")
            return None
    
    def _embed_logo(self, qr_img: Image.Image, logo: Image.Image, logo_size: float = 0.3) -> Image.Image:
        """
        Embed logo in the center of QR code
        
        Args:
            qr_img: QR code image
            logo: Logo image to embed
            logo_size: Ratio of logo size to QR code size (0.1 to 0.4)
            
        Returns:
            QR code image with embedded logo
        """
        try:
            # Validate logo size
            logo_size = max(0.1, min(0.4, logo_size))
            
            # Calculate logo dimensions
            qr_width, qr_height = qr_img.size
            logo_max_size = int(min(qr_width, qr_height) * logo_size)
            
            # Resize logo maintaining aspect ratio
            logo.thumbnail((logo_max_size, logo_max_size), Image.Resampling.LANCZOS)
            
            # Create a white background with border
            border_size = 10
            logo_with_border = Image.new('RGBA', 
                                         (logo.width + border_size * 2, 
                                          logo.height + border_size * 2), 
                                         'white')
            
            # Paste logo on white background
            logo_with_border.paste(logo, (border_size, border_size), logo)
            
            # Calculate position to center logo
            logo_pos = (
                (qr_width - logo_with_border.width) // 2,
                (qr_height - logo_with_border.height) // 2
            )
            
            # Convert QR code to RGBA if needed
            if qr_img.mode != 'RGBA':
                qr_img = qr_img.convert('RGBA')
            
            # Paste logo onto QR code
            qr_img.paste(logo_with_border, logo_pos, logo_with_border)
            
            return qr_img
            
        except Exception as e:
            print(f"Error embedding logo: {str(e)}")
            return qr_img
    
    def generate_qr_code(self, 
                        url: str, 
                        format: str = 'PNG',
                        fill_color: Union[str, Tuple[int, int, int]] = "black",
                        back_color: Union[str, Tuple[int, int, int]] = "white",
                        pattern: str = 'square',
                        error_correction: str = 'L',
                        logo: Optional[str] = None,
                        logo_size: float = 0.3) -> Optional[bytes]:
        """
        Generate customized QR code from URL
        
        Args:
            url: The URL to encode in the QR code
            format: Image format (PNG, JPEG, etc.)
            fill_color: QR code foreground color (hex string or RGB tuple)
            back_color: QR code background color (hex string or RGB tuple)
            pattern: Pattern style ('square', 'rounded', 'dots', 'vertical_bars', 'horizontal_bars')
            error_correction: Error correction level ('L', 'M', 'Q', 'H')
            logo: Base64 encoded logo image (optional)
            logo_size: Ratio of logo size to QR code (0.1 to 0.4)
        
        Returns:
            Bytes of the generated QR code image, or None if error
        """
        try:
            if not url or not isinstance(url, str):
                raise ValueError("URL must be a non-empty string")
            
            # Parse and validate colors
            fill_color = self._parse_color(fill_color)
            back_color = self._parse_color(back_color)
            
            # Validate pattern
            if pattern not in self.PATTERN_STYLES:
                print(f"Invalid pattern '{pattern}', using 'square'")
                pattern = 'square'
            
            # Validate error correction level
            if error_correction not in self.ERROR_CORRECTION_LEVELS:
                print(f"Invalid error correction '{error_correction}', using 'L'")
                error_correction = 'L'
            
            # If logo is provided, use higher error correction
            if logo and error_correction == 'L':
                error_correction = 'H'
                print("Automatically using error correction 'H' for logo embedding")
            
            # Create QR code instance
            qr = qrcode.QRCode(
                version=1,
                error_correction=self.ERROR_CORRECTION_LEVELS[error_correction],
                box_size=self.box_size,
                border=self.border,
            )
            
            qr.add_data(url)
            qr.make(fit=True)
            
            # Get pattern drawer
            module_drawer = self.PATTERN_STYLES[pattern]()
            
            # Create color mask
            color_mask = SolidFillColorMask(back_color=back_color, front_color=fill_color)
            
            # Generate image with style
            img = qr.make_image(
                image_factory=StyledPilImage,
                module_drawer=module_drawer,
                color_mask=color_mask
            )
            
            # Convert to RGB/RGBA for further processing
            if img.mode not in ['RGB', 'RGBA']:
                img = img.convert('RGB')
            
            # Embed logo if provided
            if logo:
                logo_img = self._decode_logo(logo)
                if logo_img:
                    img = self._embed_logo(img, logo_img, logo_size)
            
            # Convert to bytes
            img_buffer = BytesIO()
            
            # Convert RGBA to RGB for formats that don't support transparency
            if format.upper() in ['JPEG', 'JPG'] and img.mode == 'RGBA':
                # Create white background
                rgb_img = Image.new('RGB', img.size, 'white')
                rgb_img.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
                rgb_img.save(img_buffer, format=format)
            else:
                img.save(img_buffer, format=format)
            
            img_bytes = img_buffer.getvalue()
            img_buffer.close()
            
            return img_bytes
            
        except Exception as e:
            print(f"Error generating QR code: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def generate_qr_code_base64(self, 
                                url: str, 
                                format: str = 'PNG',
                                fill_color: Union[str, Tuple[int, int, int]] = "black",
                                back_color: Union[str, Tuple[int, int, int]] = "white",
                                pattern: str = 'square',
                                error_correction: str = 'L',
                                logo: Optional[str] = None,
                                logo_size: float = 0.3) -> Optional[str]:
        """
        Generate QR code and return as base64 encoded string
        
        Args:
            url: The URL to encode in the QR code
            format: Image format (PNG, JPEG, etc.)
            fill_color: QR code foreground color
            back_color: QR code background color
            pattern: Pattern style
            error_correction: Error correction level
            logo: Base64 encoded logo image (optional)
            logo_size: Ratio of logo size to QR code
        
        Returns:
            Base64 encoded string of the QR code image, or None if error
        """
        img_bytes = self.generate_qr_code(
            url, format, fill_color, back_color, 
            pattern, error_correction, logo, logo_size
        )
        if img_bytes:
            return base64.b64encode(img_bytes).decode('utf-8')
        return None
    
    def save_qr_code(self, 
                    url: str, 
                    filename: str, 
                    format: str = 'PNG',
                    fill_color: Union[str, Tuple[int, int, int]] = "black",
                    back_color: Union[str, Tuple[int, int, int]] = "white",
                    pattern: str = 'square',
                    error_correction: str = 'L',
                    logo: Optional[str] = None,
                    logo_size: float = 0.3) -> bool:
        """
        Generate and save QR code to file
        
        Args:
            url: The URL to encode in the QR code
            filename: Output filename
            format: Image format (PNG, JPEG, etc.)
            fill_color: QR code foreground color
            back_color: QR code background color
            pattern: Pattern style
            error_correction: Error correction level
            logo: Base64 encoded logo image (optional)
            logo_size: Ratio of logo size to QR code
        
        Returns:
            True if successful, False otherwise
        """
        try:
            img_bytes = self.generate_qr_code(
                url, format, fill_color, back_color,
                pattern, error_correction, logo, logo_size
            )
            if img_bytes:
                with open(filename, 'wb') as f:
                    f.write(img_bytes)
                return True
            return False
        except Exception as e:
            print(f"Error saving QR code: {str(e)}")
            return False


if __name__ == "__main__":
    service = QRCodeService()
    
    # Test basic QR code
    test_url = "https://www.example.com"
    print(f"Generating QR code for: {test_url}")
    
    # Test 1: Basic QR code
    output_file = "test_qr_basic.png"
    if service.save_qr_code(test_url, output_file):
        print(f"[OK] Basic QR code saved to {output_file}")
    
    # Test 2: Custom colors
    output_file = "test_qr_colors.png"
    if service.save_qr_code(test_url, output_file, fill_color="#0000FF", back_color="#FFFF00"):
        print(f"[OK] Colored QR code saved to {output_file}")
    
    # Test 3: Rounded pattern
    output_file = "test_qr_rounded.png"
    if service.save_qr_code(test_url, output_file, pattern="rounded", fill_color="#FF0000"):
        print(f"[OK] Rounded QR code saved to {output_file}")
    
    # Test 4: Dots pattern
    output_file = "test_qr_dots.png"
    if service.save_qr_code(test_url, output_file, pattern="dots", fill_color="#00FF00"):
        print(f"[OK] Dots QR code saved to {output_file}")
    
    print("\nAll tests completed!")
