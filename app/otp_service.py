# app/otp_service.py

import os
import random
import string
from datetime import datetime, timedelta
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# In-memory OTP store: {email: {"otp": "123456", "expires": datetime}}
_otp_store: dict = {}

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def store_otp(email: str, otp: str, expires_minutes: int = 10):
    _otp_store[email.lower()] = {
        "otp": otp,
        "expires": datetime.utcnow() + timedelta(minutes=expires_minutes),
    }


def verify_otp(email: str, otp: str) -> bool:
    key = email.lower()
    record = _otp_store.get(key)
    if not record:
        return False
    if datetime.utcnow() > record["expires"]:
        del _otp_store[key]
        return False
    if record["otp"] != otp:
        return False
    del _otp_store[key]  # OTP used — remove it
    return True


def send_otp_email(email: str, otp: str, name: str = "") -> bool:
    """Send OTP via Gmail SMTP. Returns True if successful."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        # Dev mode — print OTP to console
        print(f"\n{'='*40}")
        print(f"DEV MODE OTP for {email}: {otp}")
        print(f"{'='*40}\n")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{otp} — Your AI Interview Portal OTP"
        msg["From"] = GMAIL_USER
        msg["To"] = email

        html = f"""
        <html><body style="margin:0;padding:0;background:#0a0a0f;font-family:'Segoe UI',sans-serif;">
          <div style="max-width:480px;margin:40px auto;background:#111118;border:1px solid #2a2a38;border-radius:16px;overflow:hidden;">
            <div style="background:linear-gradient(135deg,#7c6af7,#6af7b8);padding:2px;">
              <div style="background:#111118;padding:32px;">
                <h1 style="color:#7c6af7;font-size:24px;font-weight:800;margin:0 0 8px;">AI Interview Portal</h1>
                <p style="color:#6b6b82;font-size:14px;margin:0 0 32px;">Your verification code</p>
                <div style="background:#1a1a24;border:1px solid #2a2a38;border-radius:12px;padding:24px;text-align:center;margin-bottom:24px;">
                  <div style="font-size:48px;font-weight:800;letter-spacing:12px;color:#f7c66a;">{otp}</div>
                  <div style="color:#6b6b82;font-size:12px;margin-top:8px;">Valid for 10 minutes</div>
                </div>
                <p style="color:#6b6b82;font-size:13px;margin:0;">
                  If you didn't request this, you can safely ignore this email.
                </p>
              </div>
            </div>
          </div>
        </body></html>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, email, msg.as_string())

        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        # Fallback to console
        print(f"\nFALLBACK OTP for {email}: {otp}\n")
        return True
