import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from config import config


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
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            /* Keep these for clients that support style blocks */
            .header {{
                background-color: #2563eb !important;
            }}
            .otp-box {{
                background-color: #2563eb !important;
            }}
        </style>
    </head>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0;">
        <div class="container" style="max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); overflow: hidden;">
            <div class="header" style="background-color: #2563eb; background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: #ffffff; padding: 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px; color: #ffffff;">{title}</h1>
            </div>
            <div class="content" style="padding: 40px 30px; text-align: center;">
                <p style="color: #555555; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">{message}</p>
                <div class="otp-box" style="background-color: #2563eb; background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: #ffffff; font-size: 36px; font-weight: bold; letter-spacing: 8px; padding: 20px; border-radius: 8px; display: inline-block; margin: 20px 0;">
                    {otp}
                </div>
                <p class="warning" style="color: #e74c3c; font-size: 14px; margin-top: 20px;">⚠️ This OTP is valid for 10 minutes. Do not share it with anyone.</p>
            </div>
            <div class="footer" style="background-color: #f8f9fa; padding: 20px; text-align: center; color: #888888; font-size: 14px;">
                <p style="margin: 5px 0;">QR Code Generator - Secure Authentication</p>
                <p style="margin: 5px 0;">If you didn't request this, please ignore this email.</p>
            </div>
        </div>
    </body>
    </html>
    """


from config import config

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
        # Get SMTP credentials from config
        smtp_server = config.SMTP_SERVER
        smtp_port = config.SMTP_PORT
        smtp_username = config.SMTP_USERNAME
        smtp_password = config.SMTP_PASSWORD
        
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
