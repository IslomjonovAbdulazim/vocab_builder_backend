from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./database/vocabbuilder_1.db"

    # JWT Configuration
    secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_days: int = 100

    # SMTP Configuration
    smtp_host: str = "smtp.timeweb.ru"
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""
    from_name: str = "VocabBuilder"

    # OTP Configuration
    otp_expire_minutes: int = 5

    # Application Configuration
    debug: bool = False

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"  # Ignore extra fields
    }

    def is_email_configured(self) -> bool:
        """Check if email is properly configured"""
        is_configured = bool(self.smtp_username and self.smtp_password and self.from_email)

        if is_configured:
            logger.info("✅ Email configuration loaded successfully")
        else:
            logger.warning("⚠️ Email configuration incomplete - emails will not be sent")
            logger.warning(f"SMTP_USERNAME: {'✅' if self.smtp_username else '❌'}")
            logger.warning(f"SMTP_PASSWORD: {'✅' if self.smtp_password else '❌'}")
            logger.warning(f"FROM_EMAIL: {'✅' if self.from_email else '❌'}")

        return is_configured


settings = Settings()