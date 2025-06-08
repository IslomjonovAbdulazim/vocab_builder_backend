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

    # Basic Email Settings
    from_email: str
    from_name: str = "VocabBuilder"
    otp_expire_minutes: int = 5

    # MailerSend (HTTP API)
    mailersend_token: str = ""

    # Other email services (optional)
    mailgun_api_key: str = ""
    mailgun_domain: str = ""
    sendgrid_api_key: str = ""
    brevo_api_key: str = ""
    elastic_api_key: str = ""

    # Gmail SMTP (fallback)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""

    class Config:
        env_file = ".env"


settings = Settings()