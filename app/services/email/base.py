# app/services/email/base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, List
from pydantic import BaseModel, EmailStr
import logging

logger = logging.getLogger(__name__)


class EmailMessage(BaseModel):
    to_email: EmailStr
    subject: str
    html_content: str
    text_content: Optional[str] = None
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None
    reply_to: Optional[EmailStr] = None
    headers: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None


class EmailResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None


class EmailProvider(ABC):
    """Abstract base class for email providers"""

    @abstractmethod
    async def send(self, message: EmailMessage) -> EmailResponse:
        """Send an email message"""
        pass

    @abstractmethod
    async def verify_connection(self) -> bool:
        """Verify provider connection and credentials"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name for logging"""
        pass