"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Any, List
import os
from urllib.parse import urlparse, urlunparse


class Settings(BaseSettings):
    """Central configuration for the LMS backend."""

    # ── App ──────────────────────────────────────────────────────────
    APP_NAME: str = "FinTrade LMS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000,http://localhost:8001,http://127.0.0.1:8001,https://fintrade-frontend-three.vercel.app"

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://lms_user:lms_password@localhost:5432/lms_db"

    @property
    def async_database_url(self) -> str:
        """Ensure the database URL uses the asyncpg driver and strip incompatible params.
        Render/Neon provide postgresql:// but we need postgresql+asyncpg://
        Also, asyncpg doesn't understand the sslmode query param."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        parsed = urlparse(url)

        # docker-compose exposes Postgres as db:5432 inside containers, but as
        # localhost:5433 when the backend is run directly on Windows/macOS/Linux.
        if parsed.hostname == "db" and not os.path.exists("/.dockerenv"):
            netloc = "localhost:5433"
            if parsed.username:
                netloc = parsed.username
                if parsed.password:
                    netloc += f":{parsed.password}"
                netloc += "@localhost:5433"
            url = urlunparse(parsed._replace(netloc=netloc))
            parsed = urlparse(url)

        # Strip sslmode if present
        if "sslmode=" in url:
            from urllib.parse import parse_qs, urlencode
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            params.pop("sslmode", None)
            cleaned_query = urlencode(params, doseq=True)
            url = urlunparse(parsed._replace(query=cleaned_query))
            
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
    ACTIVE_PAYMENT_GATEWAY: str = "easebuzz"  # Or cashfree, razorpay

    # ── Easebuzz ─────────────────────────────────────────────────────
    EASEBUZZ_KEY: str = ""
    EASEBUZZ_SALT: str = ""
    EASEBUZZ_ENV: str = "test"  # 'test' or 'prod'

    @property
    def easebuzz_base_url(self) -> str:
        return "https://pay.easebuzz.in" if self.EASEBUZZ_ENV == "prod" else "https://testpay.easebuzz.in"


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

    # ── AWS (SNS for SMS, SES for Email) ─────────────────────────────
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    SES_SENDER_EMAIL: str = "noreply@thefintrade.com"

    # ── Google OAuth ─────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── OTP ──────────────────────────────────────────────────────────
    OTP_EXPIRY_MINUTES: int = 5

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> Any:
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value

    # ── Admin seed credentials ───────────────────────────────────────
    ADMIN_EMAIL: str = "admin@platform.com"
    ADMIN_PASSWORD: str = "admin123!"
    ADMIN_FULL_NAME: str = "Platform Admin"

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


settings = Settings()
