"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Central configuration for the LMS backend."""

    # ── App ──────────────────────────────────────────────────────────
    APP_NAME: str = "FItTrade LMS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://lms_user:lms_password@localhost:5432/lms_db"

    @property
    def async_database_url(self) -> str:
        """Ensure the database URL uses the asyncpg driver.
        Render/Neon provide postgresql:// but we need postgresql+asyncpg://"""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # ── JWT ──────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── AI / OpenAI ──────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    EMBEDDING_MODEL: str = "text-embedding-ada-002"

    # ── Payment Gateways (Future Compatibility) ──────────────────────
    CASHFREE_APP_ID: str = ""
    CASHFREE_SECRET_KEY: str = ""
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    ACTIVE_PAYMENT_GATEWAY: str = "cashfree"  # Or razorpay

    # ── TradingView API ──────────────────────────────────────────────
    TRADINGVIEW_WEBHOOK_SECRET: str = ""
    TRADINGVIEW_API_KEY: str = ""

    # ── WhatsApp / SMS Reminders ─────────────────────────────────────
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""

    # ── Milvus ───────────────────────────────────────────────────────
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    USE_MILVUS: bool = False

    # ── Email ────────────────────────────────────────────────────────
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@fittrade.com"

    # ── Redis (optional) ─────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Admin seed credentials ───────────────────────────────────────
    ADMIN_EMAIL: str = "admin@platform.com"
    ADMIN_PASSWORD: str = "admin123!"
    ADMIN_FULL_NAME: str = "Platform Admin"

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
