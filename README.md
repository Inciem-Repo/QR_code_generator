# QR Code Generator - Microservices Architecture

A microservices-based QR code generator that converts URLs into QR codes. The project is structured with separate Python files for each service, following microservices principles.

## Architecture

The project consists of three main microservices:

1. **`qr_service.py`** - QR Code Generation Service
   - Handles QR code generation logic
   - Converts URLs to QR code images
   - Supports multiple output formats (PNG, base64)

2. **`api_service.py`** - API Service
   - Handles HTTP requests
   - Validates URLs
   - Exposes RESTful endpoints
   - Returns QR codes as JSON or image files

3. **`main.py`** - Main Application Orchestrator
   - Entry point for the application
   - Starts and coordinates all services

## Features

- ✅ Generate QR codes from any URL
- ✅ RESTful API endpoints
- ✅ Multiple response formats (JSON with base64, PNG image)
- ✅ URL validation
- ✅ CORS enabled for cross-origin requests
- ✅ Health check endpoint
- ✅ Microservices architecture

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd "QR code generator"
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Starting the Server

Run the main application:
```bash
python main.py
```

The API will be available at `http://localhost:5000`

### API Endpoints

#### 1. Generate QR Code (JSON Response)
**POST** `/generate`

Request body:
```json
{
  "url": "https://www.example.com"
}
```

Response:
```json
{
  "success": true,
  "url": "https://www.example.com",
  "qr_code": "base64_encoded_image_string",
  "format": "PNG",
  "message": "QR code generated successfully"
}
```

#### 2. Generate QR Code (Image File)
**POST** `/generate/image`

Request body:
```json
{
  "url": "https://www.example.com"
}
```

Returns: PNG image file

#### 3. Generate QR Code (GET Request)
**GET** `/generate/<url>`

Example:
```
GET http://localhost:5000/generate/https://www.example.com
```

Returns: PNG image file

#### 4. Health Check
**GET** `/health`

Returns:
```json
{
  "status": "healthy",
  "service": "QR Code API Service"
}
```

## Example Usage

### Using cURL

**POST request with JSON:**
```bash
curl -X POST http://localhost:5000/generate \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"https://www.example.com\"}"
```

**GET request:**
```bash
curl http://localhost:5000/generate/https://www.example.com --output qrcode.png
```

### Using Python

```python
import requests

# Generate QR code
response = requests.post(
    'http://localhost:5000/generate',
    json={'url': 'https://www.example.com'}
)

data = response.json()
if data.get('success'):
    # Save base64 image
    import base64
    img_data = base64.b64decode(data['qr_code'])
    with open('qrcode.png', 'wb') as f:
        f.write(img_data)
```

### Using JavaScript (Fetch API)

```javascript
fetch('http://localhost:5000/generate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ url: 'https://www.example.com' })
})
.then(response => response.json())
.then(data => {
  if (data.success) {
    // Display QR code
    const img = document.createElement('img');
    img.src = 'data:image/png;base64,' + data.qr_code;
    document.body.appendChild(img);
  }
});
```

## Project Structure

```
QR code generator/
│
├── qr_service.py          # QR Code Generation Microservice
├── api_service.py         # API Microservice
├── main.py                # Main Application Orchestrator
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Testing Individual Services

### Test QR Service
```bash
python qr_service.py
```

This will generate a test QR code and save it as `test_qr_code.png`.

### Test API Service
```bash
python api_service.py
```

Then test with:
```bash
curl http://localhost:5000/health
```

## Dependencies

- **Flask** - Web framework for API
- **flask-cors** - CORS support
- **qrcode** - QR code generation library
- **Pillow** - Image processing

## Error Handling

The API returns appropriate HTTP status codes:
- `200` - Success
- `400` - Bad Request (invalid URL or missing data)
- `500` - Internal Server Error

## License

This project is open source and available for use.

## Contributing

Feel free to submit issues and enhancement requests!

