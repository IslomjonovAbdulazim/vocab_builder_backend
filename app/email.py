# app/email.py - Simplified email service
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Simple email service for sending OTPs"""

    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.from_email = settings.from_email
        self.from_name = settings.from_name

    async def send_otp_email(self, email: str, otp_code: str, purpose: str = "verification") -> bool:
        """Send OTP email - returns True if successful"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')

            # Set subject and content based on purpose
            if purpose == "reset":
                msg['Subject'] = "Reset Your VocabBuilder Password"
                text_content = f"Your password reset code: {otp_code}\n\nThis code expires in 5 minutes."
            else:
                msg['Subject'] = "Verify Your VocabBuilder Account"
                text_content = f"Your verification code: {otp_code}\n\nThis code expires in 5 minutes."

            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = email

            # Create text and HTML versions
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(self._create_html_email(otp_code, purpose), 'html', 'utf-8')

            msg.attach(text_part)
            msg.attach(html_part)

            # Send email
            success = await self._send_with_smtp(msg)

            if success:
                logger.info(f"✅ Email sent to {email}")
            else:
                logger.error(f"❌ Email failed to {email}")

            return success

        except Exception as e:
            logger.error(f"❌ Email error: {str(e)}")
            return False

    async def _send_with_smtp(self, msg):
        """Send email via SMTP with multiple port fallback"""
        # Timeweb SMTP configurations
        configs = [
            {"port": 2525, "tls": True},
            {"port": 25, "tls": True},
            {"port": 465, "ssl": True}
        ]

        for config in configs:
            try:
                await self._send_message(msg, config)
                return True
            except Exception:
                continue
        return False

    async def _send_message(self, msg, config):
        """Send message with specific SMTP configuration"""
        loop = asyncio.get_event_loop()

        def _sync_send():
            if config.get('ssl', False):
                server = smtplib.SMTP_SSL(self.smtp_host, config['port'], timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_host, config['port'], timeout=10)
                if config.get('tls', False):
                    server.starttls()

            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()

        await loop.run_in_executor(None, _sync_send)

    def _create_html_email(self, otp_code: str, purpose: str) -> str:
        """Create beautiful HTML email"""
        if purpose == "reset":
            title = "Reset Your Password"
            message = "You requested to reset your password. Use the code below:"
        else:
            title = "Verify Your Email"
            message = "Welcome to VocabBuilder! Please verify your email with the code below:"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
        </head>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 30px;">

                <!-- Header -->
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #333; margin: 0; font-size: 24px;">📚 VocabBuilder</h1>
                    <p style="color: #666; margin: 10px 0 0 0;">{title}</p>
                </div>

                <!-- Message -->
                <p style="color: #333; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                    {message}
                </p>

                <!-- OTP Code -->
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background: #f8f9fa; border: 2px dashed #007bff; border-radius: 8px; padding: 20px; display: inline-block;">
                        <p style="color: #666; margin: 0 0 10px 0; font-size: 14px;">Your verification code:</p>
                        <p style="color: #007bff; margin: 0; font-size: 32px; font-weight: bold; letter-spacing: 4px; font-family: monospace;">
                            {otp_code}
                        </p>
                    </div>
                </div>

                <!-- Warning -->
                <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 6px; padding: 15px; margin: 20px 0;">
                    <p style="color: #856404; margin: 0; font-size: 14px;">
                        ⏱️ This code expires in <strong>5 minutes</strong><br>
                        🔒 Keep this code secure and don't share it with anyone
                    </p>
                </div>

                <!-- Footer -->
                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        If you didn't request this code, please ignore this email.<br>
                        © VocabBuilder - Build your vocabulary, build your future
                    </p>
                </div>

            </div>
        </body>
        </html>
        """


# Global email service instance
email_service = EmailService()


# Simple function wrapper for backwards compatibility
async def send_otp_email(email: str, otp_code: str, purpose: str = "verification") -> bool:
    """Send OTP email - simple wrapper function"""
    return await email_service.send_otp_email(email, otp_code, purpose)