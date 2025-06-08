import smtplib
import time
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings


def test_smtp_connection(host: str, port: int) -> bool:
    """Test if SMTP port is reachable"""
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except (socket.error, socket.timeout):
        return False


def send_otp_email(email: str, otp_code: str, purpose: str = "verification") -> bool:
    """Send beautiful OTP email via Gmail SMTP with port fallback"""

    # Email content based on purpose
    if purpose == "reset":
        subject = "Reset Your VocabBuilder Password"
        title = "Password Reset"
        message = "You requested to reset your password. Use the code below:"
    else:
        subject = "Verify Your VocabBuilder Account"
        title = "Email Verification"
        message = "Welcome to VocabBuilder! Please verify your email with the code below:"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8f9fa;">
        <div style="max-width: 600px; margin: 40px auto; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden;">

            <!-- Header -->
            <div style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); padding: 40px 20px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 600;">📚 VocabBuilder</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 16px;">{title}</p>
            </div>

            <!-- Content -->
            <div style="padding: 40px 30px;">
                <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 30px 0;">
                    {message}
                </p>

                <!-- OTP Code -->
                <div style="background: #f9fafb; border: 2px dashed #6366f1; border-radius: 12px; padding: 30px; text-align: center; margin: 30px 0;">
                    <p style="color: #6b7280; margin: 0 0 10px 0; font-size: 14px; font-weight: 500;">Your verification code:</p>
                    <h2 style="color: #6366f1; margin: 0; font-size: 36px; font-weight: 700; letter-spacing: 6px; font-family: 'Courier New', monospace;">{otp_code}</h2>
                </div>

                <!-- Info -->
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px; border-radius: 6px; margin: 30px 0;">
                    <p style="color: #92400e; font-size: 14px; line-height: 1.5; margin: 0;">
                        ⏱️ This code expires in <strong>5 minutes</strong><br>
                        🔒 Keep this code secure and don't share it with anyone
                    </p>
                </div>

                <!-- Footer Info -->
                <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="color: #9ca3af; font-size: 12px; line-height: 1.4; margin: 0; text-align: center;">
                        If you didn't request this code, please ignore this email.<br>
                        This is an automated message, please don't reply.
                    </p>
                </div>
            </div>

            <!-- Footer -->
            <div style="background: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 12px; margin: 0;">
                    © 2024 VocabBuilder • Build your vocabulary, build your future
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    # Try multiple SMTP configurations (ports that might not be blocked)
    smtp_configs = [
        # Gmail alternative ports (some ISPs don't block these)
        {"host": "smtp.gmail.com", "port": 2525, "ssl": False},  # Alternative port
        {"host": "smtp.gmail.com", "port": 587, "ssl": False},  # Standard TLS
        {"host": "smtp.gmail.com", "port": 465, "ssl": True},  # SSL
        {"host": "smtp.gmail.com", "port": 25, "ssl": False},  # Legacy port
    ]

    for config in smtp_configs:
        try:
            print(f"🔍 Testing {config['host']}:{config['port']} ({'SSL' if config['ssl'] else 'TLS'})")

            # Test connectivity first
            if not test_smtp_connection(config['host'], config['port']):
                print(f"❌ Port {config['port']} is blocked")
                continue

            print(f"✅ Port {config['port']} is reachable, attempting to send...")

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{settings.from_name} <{settings.from_email}>"
            msg['To'] = email

            # Add HTML content
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            # Try to send
            if config['ssl']:
                # Use SSL connection
                with smtplib.SMTP_SSL(config['host'], config['port'], timeout=15) as server:
                    server.ehlo()
                    server.login(settings.smtp_username, settings.smtp_password)
                    server.send_message(msg)
            else:
                # Use TLS connection
                with smtplib.SMTP(config['host'], config['port'], timeout=15) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(settings.smtp_username, settings.smtp_password)
                    server.send_message(msg)

            print(f"✅ Email sent successfully via {config['host']}:{config['port']}")
            return True

        except socket.error as e:
            print(f"❌ Network error on port {config['port']}: {e}")
            continue
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Auth error on port {config['port']}: {e}")
            continue
        except Exception as e:
            print(f"❌ Failed on port {config['port']}: {e}")
            continue

    # If all Gmail ports fail, provide helpful error message
    print("❌ All Gmail SMTP ports are blocked by your network/ISP")
    print("💡 Solutions:")
    print("   1. Contact your ISP/hosting provider about SMTP restrictions")
    print("   2. Use SMTP2GO, MailerSend, or another email service")
    print("   3. Try using a VPN to bypass restrictions")
    print("   4. Use HTTP-based email APIs instead of SMTP")

    return False