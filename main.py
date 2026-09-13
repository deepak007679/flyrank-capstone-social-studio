"""
FastAPI Server: Multi-Platform Social Campaign Publisher
FlyRank Backend Capstone Project
Author: Deepak R
"""

import os
import hmac
import hashlib
import json
import datetime
from typing import Optional, List, Dict, Any
from fastapi import (
    FastAPI, Request, Response, HTTPException, status, Depends, Header, Query
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import WEBHOOK_SECRET
from models import (
    init_db, SessionLocal, BlogPost, Campaign, SocialVariant,
    ScheduledJob, OAuthCredential, PublishHistory, IdempotencyRecord,
    IngestPostRequest, BlogPostResponse, CampaignResponse, VariantResponse,
    UpdateVariantStatusRequest, ScheduleCampaignRequest, DeliveryWebhookPayload
)
from services.crypto import encrypt_token, decrypt_token
from services.image_pipeline import generate_platform_variant
from services.caption_composer import compose_caption, validate_caption_constraints
from services.scheduler import enqueue_campaign_job, process_due_jobs
from services.adapters import get_publisher, register_adapter
from services.adapters.mock_adapter import MockPublisher

# Initialize database tables
init_db()

app = FastAPI(
    title="Multi-Platform Social Campaign Publisher",
    version="1.0.0",
    description="Production-grade, resilient social media campaign publisher with adapter architecture, durable scheduling, and cryptographically verified delivery webhooks."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 1. System Metadata & Root
# -----------------------------------------------------------------------------
@app.get("/", tags=["System"])
def read_root():
    return {
        "name": "Multi-Platform Social Campaign Publisher",
        "version": "1.0",
        "guarantees": [
            "Source-of-truth post ingestion",
            "Platform image variants: 1080x1080 Instagram, 1600x900 X (16:9)",
            "Code-enforced constraint profiles (char length & hashtag bounds)",
            "Strict review workflow: unapproved variants cannot be scheduled (4xx)",
            "Clean SocialPublisher adapter seam with configuration swapping",
            "Durable scheduler with mid-batch crash recovery & zero-duplicate guarantee",
            "Tokens encrypted at rest via AES-GCM (zero plaintext stored or logged)",
            "HMAC-SHA256 signature-verified delivery webhooks (forged -> 400)"
        ]
    }


# -----------------------------------------------------------------------------
# 2. Database Seed Endpoint
# -----------------------------------------------------------------------------
@app.post("/seed", tags=["Admin"])
def seed_database(db: Session = Depends(get_db)):
    """Seeds OAuth credentials encrypted at rest and sample blog post."""
    # Reset existing records
    db.query(PublishHistory).delete()
    db.query(IdempotencyRecord).delete()
    db.query(ScheduledJob).delete()
    db.query(SocialVariant).delete()
    db.query(Campaign).delete()
    db.query(BlogPost).delete()
    db.query(OAuthCredential).delete()
    db.commit()

    # Seed encrypted tokens (AES-GCM)
    ig_enc, ig_nonce = encrypt_token("tok_instagram_live_valid_credential_secret_9988")
    x_enc, x_nonce = encrypt_token("tok_x_live_valid_credential_secret_7766")

    db.add(OAuthCredential(platform="instagram", encrypted_token=ig_enc, nonce_hex=ig_nonce))
    db.add(OAuthCredential(platform="x", encrypted_token=x_enc, nonce_hex=x_nonce))
    db.commit()

    # Seed initial blog post
    post = BlogPost(
        id="post_sample_001",
        title="Building Resilient Distributed Backends",
        content=(
            "When building enterprise backends, hope is not an architecture. "
            "Systems must be designed for eventual consistency, idempotent API retries, "
            "and strict cryptographic trust boundaries across external webhooks."
        ),
        source_url="https://flyrank.com/blog/resilient-distributed-backends"
    )
    db.add(post)
    db.commit()

    return {
        "status": "seeded",
        "encrypted_platforms": ["instagram", "x"],
        "sample_post_id": post.id
    }


# -----------------------------------------------------------------------------
# 3. Post Ingestion & Variant Generation
# -----------------------------------------------------------------------------
@app.post("/posts/ingest", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED, tags=["Campaigns"])
def ingest_post_and_generate_campaign(
    payload: IngestPostRequest,
    db: Session = Depends(get_db)
):
    """
    Ingestion & Generation:
    1. Stores blog post as single source of truth.
    2. Generates platform-tailored image variants (1080x1080 Instagram, 1600x900 X).
    3. Composes platform-aware captions.
    4. Enforces constraint profiles; broken rules reject variants before review.
    """
    # 1. Store blog post (single source of truth)
    blog_post = BlogPost(
        title=payload.title,
        content=payload.content,
        source_url=payload.source_url
    )
    db.add(blog_post)
    db.commit()
    db.refresh(blog_post)

    # 2. Create campaign
    campaign = Campaign(
        blog_post_id=blog_post.id,
        status="queued"
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    # 3. Generate platform variants reading only from stored blog post
    target_platforms = ["instagram", "x"]
    for platform in target_platforms:
        # Generate image variant
        img_path, dims = generate_platform_variant(
            source_image_path=payload.image_source,
            platform=platform,
            title=blog_post.title
        )

        # Compose caption
        caption = compose_caption(platform, blog_post.title, blog_post.content)

        # Enforce constraint profile before review
        is_valid, error_msg = validate_caption_constraints(platform, caption)
        variant_status = "draft" if is_valid else "rejected"
        rejection_reason = error_msg if not is_valid else None

        variant = SocialVariant(
            campaign_id=campaign.id,
            platform=platform,
            caption=caption,
            image_path=img_path,
            status=variant_status,
            rejection_reason=rejection_reason
        )
        db.add(variant)

    db.commit()
    db.refresh(campaign)

    return campaign


# -----------------------------------------------------------------------------
# 4. Review Workflow
# -----------------------------------------------------------------------------
@app.get("/campaigns/{campaign_id}", response_model=CampaignResponse, tags=["Campaigns"])
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@app.patch("/variants/{variant_id}", tags=["Review"])
def update_variant_status(
    variant_id: str,
    payload: UpdateVariantStatusRequest,
    db: Session = Depends(get_db)
):
    """
    Review Workflow:
    Updates variant status (draft, approved, rejected).
    Can also update edited caption with constraint re-validation.
    """
    variant = db.query(SocialVariant).filter(SocialVariant.id == variant_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    if payload.edited_caption:
        # Re-validate constraints
        is_valid, err = validate_caption_constraints(variant.platform, payload.edited_caption)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed: {err}"
            )
        variant.caption = payload.edited_caption

    variant.status = payload.status
    variant.rejection_reason = payload.rejection_reason
    db.commit()
    db.refresh(variant)

    return {
        "status": "updated",
        "variant_id": variant.id,
        "platform": variant.platform,
        "new_status": variant.status,
        "caption": variant.caption
    }


# -----------------------------------------------------------------------------
# 5. Scheduling & Publishing
# -----------------------------------------------------------------------------
@app.post("/campaigns/{campaign_id}/schedule", tags=["Scheduling"])
def schedule_campaign(
    campaign_id: str,
    payload: ScheduleCampaignRequest,
    db: Session = Depends(get_db)
):
    """
    Review Gate Enforcement:
    Refuses schedule requests if ANY variant in the campaign is unapproved.
    Returns HTTP 400 with a descriptive error message.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Verify that at least one variant is approved, and no unapproved variants remain scheduled
    unapproved = [v for v in campaign.variants if v.status != "approved"]
    if unapproved:
        unapproved_platforms = [f"{v.platform} ({v.status})" for v in unapproved]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot schedule campaign: variants not approved: {', '.join(unapproved_platforms)}. Review and approve all variants before scheduling."
        )

    # Schedule the job
    job = enqueue_campaign_job(db, campaign_id, payload.scheduled_for)
    campaign.scheduled_for = payload.scheduled_for
    db.commit()

    return {
        "status": "scheduled",
        "campaign_id": campaign.id,
        "job_id": job.id,
        "scheduled_for": payload.scheduled_for.isoformat()
    }


@app.post("/scheduler/tick", tags=["Scheduling"])
def trigger_scheduler_tick(
    advance_seconds: int = Query(0, description="Advance clock by seconds for testing"),
    db: Session = Depends(get_db)
):
    """Triggers scheduler worker to process all due jobs."""
    current_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(seconds=advance_seconds)
    results = process_due_jobs(db=db, current_time=current_time)
    return {
        "status": "tick_completed",
        "processed_jobs_count": len(results),
        "results": results
    }


# -----------------------------------------------------------------------------
# 6. Delivery Webhooks (HMAC-SHA256 Signature Verification)
# -----------------------------------------------------------------------------
@app.post("/webhook/social-delivery", tags=["Webhooks"])
async def receive_delivery_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Signature-Verified Delivery Webhook:
    1. Verifies HMAC-SHA256 signature from X-Hub-Signature-256 header.
    2. Forged or modified requests are rejected with 400.
    3. Flips campaign and variant status to 'published' (or 'failed').
    """
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")

    if not signature_header:
        raise HTTPException(status_code=400, detail="Missing required signature header: X-Hub-Signature-256")

    # Compute expected signature
    expected_hash = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    expected_sig = f"sha256={expected_hash}"

    # Verify signature in constant time
    if not hmac.compare_digest(signature_header, expected_sig):
        raise HTTPException(status_code=400, detail="Invalid webhook signature: forged or modified event rejected")

    # Parse payload
    try:
        event = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON in webhook body")

    campaign_id = event.get("campaign_id")
    variant_id = event.get("variant_id")
    event_status = event.get("status", "published")

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign:
        campaign.status = event_status
        db.commit()

    variant = db.query(SocialVariant).filter(SocialVariant.id == variant_id).first()
    if variant:
        variant.status = event_status
        db.commit()

    return {
        "status": "acknowledged",
        "campaign_id": campaign_id,
        "variant_id": variant_id,
        "new_status": event_status
    }


# -----------------------------------------------------------------------------
# 7. Publish History Audit Trail
# -----------------------------------------------------------------------------
@app.get("/history", tags=["Audit"])
def get_publish_history(db: Session = Depends(get_db)):
    records = db.query(PublishHistory).order_by(PublishHistory.timestamp.desc()).all()
    return {
        "total_records": len(records),
        "history": [
            {
                "id": r.id,
                "campaign_id": r.campaign_id,
                "variant_id": r.variant_id,
                "platform": r.platform,
                "status": r.status,
                "external_post_id": r.external_post_id,
                "post_url": r.post_url,
                "error_message": r.error_message,
                "timestamp": r.timestamp.isoformat()
            }
            for r in records
        ]
    }
