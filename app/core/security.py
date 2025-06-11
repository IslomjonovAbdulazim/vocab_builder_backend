from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(email: str) -> str:
    """Create JWT token with proper timezone handling"""
    logger.info(f"🔑 Creating JWT token for email: {email}")

    expire = datetime.now(timezone.utc) + timedelta(days=settings.access_token_expire_days)
    issued_at = datetime.now(timezone.utc)

    to_encode = {
        "sub": email,
        "exp": expire,
        "iat": issued_at
    }

    logger.info(f"🕐 Token will expire at: {expire}")
    logger.info(f"⚙️ Using secret key: {settings.secret_key[:10]}...")
    logger.info(f"⚙️ Using algorithm: {settings.algorithm}")

    token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    logger.info(f"✅ JWT token created successfully: {token[:20]}...")

    return token


def verify_token(token: str) -> str | None:
    """Verify JWT token and return email"""
    logger.info(f"🔍 Starting token verification for: {token[:20]}...")

    try:
        logger.info(f"⚙️ Using secret key: {settings.secret_key[:10]}...")
        logger.info(f"⚙️ Using algorithm: {settings.algorithm}")

        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        logger.info(f"📦 Token payload decoded: {payload}")

        email = payload.get("sub")
        exp = payload.get("exp")
        iat = payload.get("iat")

        logger.info(f"📧 Email from token: {email}")
        logger.info(f"⏰ Token expires at: {exp}")
        logger.info(f"⏰ Token issued at: {iat}")

        # Check if token has expired
        current_time = datetime.now(timezone.utc).timestamp()
        logger.info(f"🕐 Current time: {current_time}")

        if exp and current_time > exp:
            logger.error(f"❌ Token has expired! Current: {current_time}, Expires: {exp}")
            return None

        if not email:
            logger.error("❌ No email found in token payload")
            return None

        logger.info(f"✅ Token verification successful for: {email}")
        return email

    except JWTError as e:
        logger.error(f"❌ JWT Error during token verification: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error during token verification: {str(e)}")
        return None