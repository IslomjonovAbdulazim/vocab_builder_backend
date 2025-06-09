import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings


def send_otp_email(email: str, otp_code: str, purpose: str = "verification") -> bool:
    """
    Send OTP email via Timeweb SMTP with automatic port fallback
    Tries ports in order: 2525 → 25 → 587
    """

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

    print(f"🔍 Sending OTP email to {email} via Timeweb SMTP (trying multiple ports)...")

    # Port configurations in order of preference
    smtp_configs = [
        {
            "port": 2525,
            "use_tls": False,
            "description": "Port 2525 (unencrypted, ISP-friendly)"
        },
        {
            "port": 25,
            "use_tls": False,
            "description": "Port 25 (standard SMTP)"
        },
        {
            "port": 587,
            "use_tls": True,
            "description": "Port 587 (STARTTLS)"
        }
    ]

    for config in smtp_configs:
        port = config["port"]
        use_tls = config["use_tls"]
        description = config["description"]

        print(f"\n🔄 Trying {description}...")

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{settings.from_name} <{settings.from_email}>"
            msg['To'] = email

            # Add HTML content
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            # Connect with short timeout to fail fast
            with smtplib.SMTP(settings.smtp_host, port, timeout=10) as server:
                print(f"🔗 Connected to {settings.smtp_host}:{port}")

                # Use TLS if specified
                if use_tls:
                    server.starttls()
                    print("🔒 Started TLS encryption")

                # Authenticate
                server.login(settings.smtp_username, settings.smtp_password)
                print(f"✅ Authenticated as {settings.smtp_username}")

                # Send email
                server.send_message(msg)

            print(f"✅ Email sent successfully via Timeweb SMTP!")
            print(f"   📧 Port: {port} ({description})")
            print(f"   📧 From: {settings.from_email}")
            print(f"   📧 To: {email}")
            print(f"   🔢 OTP: {otp_code}")
            print(f"   🔒 Encryption: {'TLS' if use_tls else 'None'}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Authentication Error on port {port}: {e}")
            print("💡 Check your Timeweb email credentials!")
            return False  # Don't try other ports if auth fails

        except (smtplib.SMTPServerDisconnected, ConnectionError, OSError) as e:
            print(f"❌ Connection failed on port {port}: {e}")
            continue  # Try next port

        except Exception as e:
            print(f"❌ Unexpected error on port {port}: {e}")
            continue  # Try next port

    print("❌ All SMTP port configurations failed!")
    print("💡 Troubleshooting steps:")
    print("   1. Check if Timeweb email service is active")
    print("   2. Verify email credentials in Timeweb panel")
    print("   3. Contact Timeweb support for SMTP settings")
    print("   4. Check if your ISP blocks SMTP ports")

    return False