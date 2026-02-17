import os
from datetime import timedelta

class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = os.getenv("REMEMBER_COOKIE_SECURE", "false").lower() == "true"
    PREFERRED_URL_SCHEME = "https" if SESSION_COOKIE_SECURE else "http"
    WTF_CSRF_TIME_LIMIT = int(os.getenv("WTF_CSRF_TIME_LIMIT", "3600"))
    N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
    WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "disabled")
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")
    META_WHATSAPP_TOKEN = os.getenv("META_WHATSAPP_TOKEN", "")
    META_WHATSAPP_PHONE_ID = os.getenv("META_WHATSAPP_PHONE_ID", "")
    META_WHATSAPP_URL = os.getenv("META_WHATSAPP_URL", "https://graph.facebook.com/v19.0")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    LOGIN_RATE_LIMIT_MAX = int(os.getenv("LOGIN_RATE_LIMIT_MAX", "5"))
    LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300"))
    LOGIN_LOCKOUT_BASE_SECONDS = int(os.getenv("LOGIN_LOCKOUT_BASE_SECONDS", "60"))
    STUDENT_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "students")
    STUDENT_UPLOAD_MAX_BYTES = int(os.getenv("STUDENT_UPLOAD_MAX_BYTES", str(500 * 1024)))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(2 * 1024 * 1024)))
