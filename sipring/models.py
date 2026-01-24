"""Pydantic models for ring configurations."""

import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    # Normalize unicode characters (convert umlauts etc to ASCII)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


class RingConfigBase(BaseModel):
    """Base model for ring configuration."""

    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    slug: Optional[str] = Field(None, max_length=50, description="URL-friendly identifier")
    sip_user: str = Field(..., min_length=1, max_length=100, description="SIP user/extension to call")
    sip_server: str = Field(..., min_length=1, max_length=255, description="SIP server hostname/IP")
    sip_port: int = Field(5060, ge=1, le=65535, description="SIP server port")
    caller_name: str = Field(..., min_length=1, max_length=100, description="Caller display name")
    caller_user: str = Field("doorbell", max_length=100, description="Caller SIP user")
    ring_duration: int = Field(30, ge=1, le=300, description="Max ring duration in seconds")
    local_port: int = Field(5062, ge=1024, le=65535, description="Local UDP port for SIP")
    enabled: bool = Field(True, description="Whether this config is enabled")

    @field_validator('slug', mode='before')
    @classmethod
    def auto_slug(cls, v, info):
        """Auto-generate slug from name if not provided."""
        if v is None and 'name' in info.data:
            return slugify(info.data['name'])
        return v

    @field_validator('sip_server')
    @classmethod
    def validate_server(cls, v):
        """Validate server is hostname or IP."""
        if not v or v.startswith('http'):
            raise ValueError('Server must be hostname or IP, not URL')
        return v


class RingConfigCreate(RingConfigBase):
    """Model for creating a new ring configuration."""
    pass


class RingConfigUpdate(BaseModel):
    """Model for updating a ring configuration (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    slug: Optional[str] = Field(None, max_length=50)
    sip_user: Optional[str] = Field(None, min_length=1, max_length=100)
    sip_server: Optional[str] = Field(None, min_length=1, max_length=255)
    sip_port: Optional[int] = Field(None, ge=1, le=65535)
    caller_name: Optional[str] = Field(None, min_length=1, max_length=100)
    caller_user: Optional[str] = Field(None, max_length=100)
    ring_duration: Optional[int] = Field(None, ge=1, le=300)
    local_port: Optional[int] = Field(None, ge=1024, le=65535)
    enabled: Optional[bool] = None


def utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class RingConfig(RingConfigBase):
    """Full ring configuration model with metadata."""

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    created_at: datetime = Field(default_factory=utc_now)
    last_ring_at: Optional[datetime] = Field(None, description="Last ring timestamp")
    last_ring_status: Optional[str] = Field(None, description="Last ring result")


class RingConfigResponse(RingConfig):
    """Response model for ring configuration."""

    ring_url: Optional[str] = Field(None, description="URL to trigger ring")
    cancel_url: Optional[str] = Field(None, description="URL to cancel ring")


class RingResponse(BaseModel):
    """Response model for ring operations."""

    status: str = Field(..., description="Operation status")
    config_id: UUID = Field(..., description="Configuration ID")
    message: str = Field(..., description="Status message")
    result: Optional[str] = Field(None, description="Call result if completed")


class ConfigListResponse(BaseModel):
    """Response model for listing configurations."""

    configs: list[RingConfigResponse]
    count: int
