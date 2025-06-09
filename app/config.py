from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Database
    database_url: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_days: int = 100

    # Timeweb SMTP Settings
    smtp_host: str = "smtp.timeweb.ru"
    smtp_port: int = 465
    smtp_username: str
    smtp_password: str
    from_email: str
    from_name: str = "VocabBuilder"

    # OTP Configuration
    otp_expire_minutes: int = 5

    class Config:
        env_file = ".env"


settings = Settings()