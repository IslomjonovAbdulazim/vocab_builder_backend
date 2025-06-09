import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Simple, reliable email service for OTP delivery"""

    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.from_email = settings.from_email
        self.from_name = settings.from_name

    async def send_otp_email(self, email: str, otp_code: str, purpose: str = "verification") -> bool:
        """Send OTP email - returns True if successful, False otherwise"""
        logger.info(f"📧 Starting email send process to {email} (purpose: {purpose}, OTP: {otp_code})")

        try:
            # Create message
            msg = MIMEMultipart('alternative')

            # Set headers
            if purpose == "reset":
                msg['Subject'] = "Reset Your VocabBuilder Password"
                message_text = f"Your password reset code: {otp_code}\n\nThis code expires in 5 minutes."
                logger.info(f"📝 Created password reset message for {email}")
            else:
                msg['Subject'] = "Verify Your VocabBuilder Account"
                message_text = f"Your verification code: {otp_code}\n\nThis code expires in 5 minutes."
                logger.info(f"📝 Created verification message for {email}")

            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = email
            logger.info(f"📮 Email headers set - From: {self.from_email}, To: {email}")

            # Create plain text version
            text_part = MIMEText(message_text, 'plain', 'utf-8')

            # Create HTML version
            html_content = self._create_html_email(otp_code, purpose)
            html_part = MIMEText(html_content, 'html', 'utf-8')

            # Attach both versions
            msg.attach(text_part)
            msg.attach(html_part)
            logger.info(f"📎 Email content attached (text + HTML)")

            # Send email
            logger.info(f"🚀 Attempting to send email via SMTP...")
            await self._send_message(msg)
            logger.info(f"✅ Email sent successfully to {email} with OTP: {otp_code}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email to {email}: {str(e)}")
            logger.error(f"💡 Email details - From: {self.from_email}, To: {email}, OTP: {otp_code}")
            return False

    async def _send_message(self, msg):
        """Send email message via SMTP"""
        logger.info(f"🔌 Connecting to SMTP server: {self.smtp_host}:{self.smtp_port}")

        loop = asyncio.get_event_loop()

        def _sync_send():
            try:
                logger.info(f"🌐 Creating SMTP connection...")
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    logger.info(f"🔐 Starting TLS encryption...")
                    server.starttls()

                    logger.info(f"👤 Logging in with username: {self.smtp_username}")
                    server.login(self.smtp_username, self.smtp_password)
                    logger.info(f"✅ SMTP login successful")

                    logger.info(f"📤 Sending message...")
                    server.send_message(msg)
                    logger.info(f"🎉 Message sent successfully via SMTP")

            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"🔑 SMTP Authentication failed: {str(e)}")
                logger.error(f"💡 Check your SMTP_USERNAME and SMTP_PASSWORD")
                raise
            except smtplib.SMTPRecipientsRefused as e:
                logger.error(f"📧 Recipient refused: {str(e)}")
                raise
            except smtplib.SMTPServerDisconnected as e:
                logger.error(f"🔌 SMTP server disconnected: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"💥 SMTP error: {str(e)}")
                raise

        await loop.run_in_executor(None, _sync_send)

    def _create_html_email(self, otp_code: str, purpose: str) -> str:
        """Create simple HTML email"""
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


# Global instance
email_service = EmailService()


# Simple function for backward compatibility
def send_otp_email(email: str, otp_code: str, purpose: str = "verification"):
    """Synchronous wrapper - DEPRECATED, use email_service.send_otp_email() instead"""
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(email_service.send_otp_email(email, otp_code, purpose))
    except RuntimeError:
        # No event loop running, create one
        return asyncio.run(email_service.send_otp_email(email, otp_code, purpose))