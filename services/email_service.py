import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


def get_otp_email_template(otp: str, purpose: str = "verification") -> str:
    """
    Generate a professional HTML email template for OTP
    """
    if purpose == "reset":
        title = "Password Reset Request"
        message = "You requested to reset your password. Use the OTP below to proceed:"
    else:
        title = "Email Verification"
        message = "Thank you for registering! Use the OTP below to verify your email:"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
            }}
            .content {{
                padding: 40px 30px;
                text-align: center;
            }}
            .content p {{
                color: #555;
                font-size: 16px;
                line-height: 1.6;
                margin-bottom: 30px;
            }}
            .otp-box {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                font-size: 36px;
                font-weight: bold;
                letter-spacing: 8px;
                padding: 20px;
                border-radius: 8px;
                display: inline-block;
                margin: 20px 0;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 20px;
                text-align: center;
                color: #888;
                font-size: 14px;
            }}
            .warning {{
                color: #e74c3c;
                font-size: 14px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 {title}</h1>
            </div>
            <div class="content">
                <p>{message}</p>
                <div class="otp-box">{otp}</div>
                <p class="warning">⚠️ This OTP is valid for 10 minutes. Do not share it with anyone.</p>
            </div>
            <div class="footer">
                <p>QR Code Generator - Secure Authentication</p>
                <p>If you didn't request this, please ignore this email.</p>
            </div>
        </div>
    </body>
    </html>
    """


def send_email(to_email: str, subject: str, body: str, is_html: bool = False) -> bool:
    """
    Send email using SMTP (Gmail)
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body (plain text or HTML)
        is_html: Whether the body is HTML
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Get SMTP credentials from environment
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        
        if not smtp_username or not smtp_password:
            print("❌ SMTP credentials not configured in .env file")
            print(f"📧 [DEV MODE] Email to: {to_email}")
            print(f"📧 Subject: {subject}")
            print(f"📧 Body: {body[:100]}...")
            return False
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_username
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach body
        if is_html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))
        
        # Connect to SMTP server and send email
        print(f"📧 Connecting to {smtp_server}:{smtp_port}...")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Secure the connection
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        print(f"✅ Email sent successfully to {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("❌ SMTP Authentication failed. Check your username/password or app password.")
        print("💡 For Gmail, you need to use an App Password, not your regular password.")
        print("💡 Generate one at: https://myaccount.google.com/apppasswords")
        return False
        
    except smtplib.SMTPException as e:
        print(f"❌ SMTP error occurred: {str(e)}")
        return False
        
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        return False


def send_otp_email(to_email: str, otp: str, purpose: str = "verification") -> bool:
    """
    Send OTP email with professional HTML template
    
    Args:
        to_email: Recipient email address
        otp: One-time password
        purpose: 'verification' or 'reset'
    
    Returns:
        bool: True if email sent successfully
    """
    if purpose == "reset":
        subject = "🔐 Password Reset OTP - QR Code Generator"
    else:
        subject = "🔐 Email Verification OTP - QR Code Generator"
    
    html_body = get_otp_email_template(otp, purpose)
    return send_email(to_email, subject, html_body, is_html=True)
