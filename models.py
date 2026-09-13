"""
Database Models & Pydantic Schemas
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R
"""

import datetime
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime, Text, ForeignKey, Boolean
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from pydantic import BaseModel, Field

from config import DATABASE_URL

def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# -----------------------------------------------------------------------------
# SQLAlchemy Models
# -----------------------------------------------------------------------------
class BlogPost(Base):
    """Single Source of Truth: Ingested blog post."""
    __tablename__ = "blog_posts"

    id = Column(String(64), primary_key=True, default=lambda: f"post_{uuid.uuid4().hex[:12]}")
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    campaigns = relationship("Campaign", back_populates="blog_post", cascade="all, delete-orphan")


class Campaign(Base):
    """Social Campaign grouping variants across platforms."""
    __tablename__ = "campaigns"

    id = Column(String(64), primary_key=True, default=lambda: f"camp_{uuid.uuid4().hex[:12]}")
    blog_post_id = Column(String(64), ForeignKey("blog_posts.id"), nullable=False)
    # Statuses: queued -> publishing -> published | failed
    status = Column(String(32), default="queued", nullable=False)
    scheduled_for = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    blog_post = relationship("BlogPost", back_populates="campaigns")
    variants = relationship("SocialVariant", back_populates="campaign", cascade="all, delete-orphan")
    jobs = relationship("ScheduledJob", back_populates="campaign", cascade="all, delete-orphan")


class SocialVariant(Base):
    """Platform-specific variant (caption + image)."""
    __tablename__ = "social_variants"

    id = Column(String(64), primary_key=True, default=lambda: f"var_{uuid.uuid4().hex[:12]}")
    campaign_id = Column(String(64), ForeignKey("campaigns.id"), nullable=False)
    platform = Column(String(32), nullable=False)  # instagram, x, linkedin
    caption = Column(Text, nullable=False)
    image_path = Column(String(512), nullable=True)
    # Review statuses: draft, approved, rejected, published
    status = Column(String(32), default="draft", nullable=False)
    rejection_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    campaign = relationship("Campaign", back_populates="variants")


class ScheduledJob(Base):
    """Durable Scheduling Queue surviving crashes and restarts."""
    __tablename__ = "scheduled_jobs"

    id = Column(String(64), primary_key=True, default=lambda: f"job_{uuid.uuid4().hex[:12]}")
    campaign_id = Column(String(64), ForeignKey("campaigns.id"), nullable=False)
    run_at = Column(DateTime, nullable=False)
    # Statuses: pending, running, completed, failed
    status = Column(String(32), default="pending", nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    campaign = relationship("Campaign", back_populates="jobs")


class OAuthCredential(Base):
    """Encrypted OAuth credentials at rest (AES-GCM). Plaintext never stored."""
    __tablename__ = "oauth_credentials"

    id = Column(String(64), primary_key=True, default=lambda: f"cred_{uuid.uuid4().hex[:12]}")
    platform = Column(String(32), unique=True, nullable=False)
    encrypted_token = Column(Text, nullable=False)
    nonce_hex = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class IdempotencyRecord(Base):
    """Idempotency store preventing duplicate actions under network retries."""
    __tablename__ = "idempotency_records"

    id = Column(String(64), primary_key=True, default=lambda: f"idemp_{uuid.uuid4().hex[:12]}")
    idempotency_key = Column(String(128), unique=True, nullable=False)
    platform = Column(String(32), nullable=False)
    external_post_id = Column(String(128), nullable=False)
    response_body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)


class PublishHistory(Base):
    """Audit log of each individual publish attempt."""
    __tablename__ = "publish_history"

    id = Column(String(64), primary_key=True, default=lambda: f"pub_{uuid.uuid4().hex[:12]}")
    campaign_id = Column(String(64), nullable=False)
    variant_id = Column(String(64), nullable=False)
    platform = Column(String(32), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False)  # success, retry, failed
    external_post_id = Column(String(128), nullable=True)
    post_url = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utc_now)


def init_db():
    Base.metadata.create_all(bind=engine)


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class IngestPostRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    content: str = Field(..., min_length=10)
    source_url: Optional[str] = None
    image_source: Optional[str] = None  # Optional URL or base64 / path


class BlogPostResponse(BaseModel):
    id: str
    title: str
    content: str
    source_url: Optional[str] = None
    created_at: datetime.datetime


class VariantResponse(BaseModel):
    id: str
    platform: str
    caption: str
    image_path: Optional[str] = None
    status: str
    rejection_reason: Optional[str] = None


class CampaignResponse(BaseModel):
    id: str
    blog_post_id: str
    status: str
    scheduled_for: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    variants: List[VariantResponse] = []


class UpdateVariantStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|draft)$")
    rejection_reason: Optional[str] = None
    edited_caption: Optional[str] = None


class ScheduleCampaignRequest(BaseModel):
    scheduled_for: datetime.datetime


class DeliveryWebhookPayload(BaseModel):
    event_id: str
    campaign_id: str
    variant_id: str
    platform: str
    status: str  # published, failed
    external_post_id: str
    post_url: str
    timestamp: int
