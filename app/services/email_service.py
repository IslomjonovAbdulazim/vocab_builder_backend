import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from datetime import datetime
import logging
from dataclasses import dataclass
from jinja2 import Template
import time
from functools import wraps

from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    """Result of email sending operation"""
    success: bool
    message: str
    timestamp: datetime
    retry_count: int = 0
    error_details: Optional[str] = None


class SMTPConnectionPool:
    """Manages SMTP connections with pooling for better performance"""

    def __init__(self, max_connections: int = 5):
        self.max_connections = max_connections
        self._connections = []
        self._lock = asyncio.Lock()

    async def get_connection(self):
        """Get an SMTP connection from pool or create new one"""
        async with self._lock:
            if self._connections:
                return self._connections.pop()
            return await self._create_connection()

    async def return_connection(self, conn):
        """Return connection to pool"""
        async with self._lock:
            if len(self._connections) < self.max_connections:
                self._connections.append(conn)
            else:
                try:
                    conn.quit()
                except:
                    pass

    async def _create_connection(self):
        """Create new SMTP connection with optimized settings"""
        # Try ports in order of reliability
        ports_config = [
            {"port": 587, "use_tls": True, "timeout": 10},
            {"port": 2525, "use_tls": False, "timeout": 10},
            {"port": 25, "use_tls": False, "timeout": 15}
        ]

        last_error = None
        for config in ports_config:
            try:
                conn = smtplib.SMTP(
                    host=settings.smtp_host,
                    port=config["port"],
                    timeout=config["timeout"]
                )

                # Enable debugging in development
                if settings.database_url.startswith("sqlite"):
                    conn.set_debuglevel(0)

                # Start TLS if required
                if config["use_tls"]:
                    conn.starttls()

                # Authenticate
                conn.login(settings.smtp_username, settings.smtp_password)

                logger.info(f"SMTP connection established on port {config['port']}")
                return conn

            except Exception as e:
                last_error = e
                logger.warning(f"Failed to connect on port {config['port']}: {str(e)}")
                continue

        raise ConnectionError(f"All SMTP ports failed. Last error: {last_error}")

    async def close_all(self):
        """Close all pooled connections"""
        async with self._lock:
            for conn in self._connections:
                try:
                    conn.quit()
                except:
                    pass
            self._connections.clear()


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retry logic with exponential backoff"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {str(e)}. "
                            f"Retrying in {current_delay} seconds..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries} attempts failed")

            raise last_exception

        return wrapper

    return decorator


class EmailTemplates:
    """Email templates with modern, responsive design"""

    BASE_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <title>{{ title }}</title>
        <!--[if mso]>
        <style type="text/css">
        table {border-collapse: collapse !important;}
        </style>
        <![endif]-->
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8f9fa; -webkit-font-smoothing: antialiased;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f8f9fa;">
            <tr>
                <td align="center" style="padding: 40px 20px;">
                    <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden;">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); padding: 40px 20px; text-align: center;">
                                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 600;">
                                    📚 VocabBuilder
                                </h1>
                                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 16px;">
                                    {{ header_subtitle }}
                                </p>
                            </td>
                        </tr>

                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                {{ content }}
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                                <p style="color: #6b7280; font-size: 12px; margin: 0;">
                                    © {{ year }} VocabBuilder • Build your vocabulary, build your future
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    OTP_CONTENT = """
        <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 30px 0;">
            {{ message }}
        </p>

        <!-- OTP Code Box -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
            <tr>
                <td align="center">
                    <table role="presentation" cellspacing="0" cellpadding="0" style="background: #f9fafb; border: 2px dashed #6366f1; border-radius: 12px;">
                        <tr>
                            <td style="padding: 30px; text-align: center;">
                                <p style="color: #6b7280; margin: 0 0 10px 0; font-size: 14px; font-weight: 500;">
                                    Your verification code:
                                </p>
                                <p style="color: #6366f1; margin: 0; font-size: 36px; font-weight: 700; letter-spacing: 6px; font-family: 'Courier New', monospace;">
                                    {{ otp_code }}
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <!-- Warning Box -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top: 30px;">
            <tr>
                <td>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 6px;">
                        <tr>
                            <td style="padding: 16px;">
                                <p style="color: #92400e; font-size: 14px; line-height: 1.5; margin: 0;">
                                    ⏱️ This code expires in <strong>5 minutes</strong><br>
                                    🔒 Keep this code secure and don't share it with anyone
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <!-- Footer Info -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
            <tr>
                <td align="center">
                    <p style="color: #9ca3af; font-size: 12px; line-height: 1.4; margin: 0; text-align: center;">
                        If you didn't request this code, please ignore this email.<br>
                        This is an automated message, please don't reply.
                    </p>
                </td>
            </tr>
        </table>
    """


class EmailService:
    """
    Production-ready email service with Timeweb SMTP
    Features:
    - Connection pooling for performance
    - Automatic retry with exponential backoff
    - Multiple port fallback
    - Template rendering
    - Comprehensive error handling
    - Async support
    """

    def __init__(self):
        self.connection_pool = SMTPConnectionPool(max_connections=3)
        self.templates = EmailTemplates()
        self._stats = {
            "sent": 0,
            "failed": 0,
            "retries": 0,
            "last_error": None,
            "last_success": None
        }

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    async def send_otp_email(
            self,
            email: str,
            otp_code: str,
            purpose: str = "verification"
    ) -> EmailResult:
        """
        Send OTP email with automatic retry and connection pooling

        Args:
            email: Recipient email address
            otp_code: OTP code to send
            purpose: 'verification' or 'reset'

        Returns:
            EmailResult with status and details
        """
        start_time = time.time()

        # Prepare email content based on purpose
        if purpose == "reset":
            subject = "Reset Your VocabBuilder Password"
            header_subtitle = "Password Reset"
            message = "You requested to reset your password. Use the code below:"
        else:
            subject = "Verify Your VocabBuilder Account"
            header_subtitle = "Email Verification"
            message = "Welcome to VocabBuilder! Please verify your email with the code below:"

        # Render templates
        content_html = self._render_template(
            self.templates.OTP_CONTENT,
            message=message,
            otp_code=otp_code
        )

        full_html = self._render_template(
            self.templates.BASE_TEMPLATE,
            title=subject,
            header_subtitle=header_subtitle,
            content=content_html,
            year=datetime.now().year
        )

        # Send email
        conn = None
        try:
            # Get connection from pool
            conn = await self.connection_pool.get_connection()

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{settings.from_name} <{settings.from_email}>"
            msg['To'] = email
            msg['Message-ID'] = self._generate_message_id()
            msg['Date'] = self._format_date()

            # Add plain text version for better deliverability
            text_content = f"""
{header_subtitle}

{message}

Your verification code: {otp_code}

This code expires in 5 minutes.
Keep this code secure and don't share it with anyone.

If you didn't request this code, please ignore this email.

---
VocabBuilder - Build your vocabulary, build your future
            """.strip()

            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
            msg.attach(MIMEText(full_html, 'html', 'utf-8'))

            # Send message
            send_start = time.time()
            conn.send_message(msg)
            send_time = time.time() - send_start

            # Update stats
            self._stats["sent"] += 1
            self._stats["last_success"] = datetime.now()

            logger.info(
                f"Email sent successfully to {email} "
                f"(purpose: {purpose}, send_time: {send_time:.2f}s, "
                f"total_time: {time.time() - start_time:.2f}s)"
            )

            return EmailResult(
                success=True,
                message=f"Email sent successfully in {send_time:.2f}s",
                timestamp=datetime.now()
            )

        except Exception as e:
            self._stats["failed"] += 1
            self._stats["last_error"] = str(e)

            logger.error(f"Failed to send email to {email}: {str(e)}")

            return EmailResult(
                success=False,
                message="Failed to send email",
                timestamp=datetime.now(),
                error_details=str(e)
            )

        finally:
            # Return connection to pool
            if conn:
                await self.connection_pool.return_connection(conn)

    def _render_template(self, template_str: str, **kwargs) -> str:
        """Render Jinja2 template with data"""
        template = Template(template_str)
        return template.render(**kwargs)

    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        import uuid
        domain = settings.from_email.split('@')[1]
        return f"<{uuid.uuid4()}@{domain}>"

    def _format_date(self) -> str:
        """Format date for email header"""
        from email.utils import formatdate
        return formatdate(localtime=True)

    async def get_stats(self) -> Dict[str, Any]:
        """Get email service statistics"""
        return {
            **self._stats,
            "success_rate": (
                                self._stats["sent"] / (self._stats["sent"] + self._stats["failed"])
                                if (self._stats["sent"] + self._stats["failed"]) > 0
                                else 0
                            ) * 100
        }

    async def health_check(self) -> bool:
        """Check if email service is healthy"""
        try:
            conn = await self.connection_pool.get_connection()
            await self.connection_pool.return_connection(conn)
            return True
        except Exception as e:
            logger.error(f"Email service health check failed: {str(e)}")
            return False

    async def close(self):
        """Cleanup resources"""
        await self.connection_pool.close_all()


# Global email service instance
email_service = EmailService()


# Convenience function for backward compatibility
async def send_otp_email(email: str, otp_code: str, purpose: str = "verification") -> bool:
    """Send OTP email using the global email service"""
    result = await email_service.send_otp_email(email, otp_code, purpose)
    return result.success