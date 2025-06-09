from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./database/vocabbuilder_1.db"

    # JWT Configuration
    secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_days: int = 100

    # SMTP Configuration
    smtp_host: str = "smtp.timeweb.ru"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""
    from_name: str = "VocabBuilder"

    # OTP Configuration
    otp_expire_minutes: int = 5

    # Application Configuration
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Validate email configuration
        if not self.smtp_username or not self.smtp_password or not self.from_email:
            raise ValueError(
                "Email configuration incomplete. Please set SMTP_USERNAME, "
                "SMTP_PASSWORD, and FROM_EMAIL in your .env file"
            )


settings = Settings()