"""
Durable Scheduling Worker
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R

Guarantees crash-resilient scheduling:
- Persistent jobs stored in SQLite database
- Idempotent execution: interrupted batches resume without duplicate posts
- Atomic state transitions
"""

import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from models import ScheduledJob, Campaign, SocialVariant, IdempotencyRecord
from services.adapters import get_publisher


def enqueue_campaign_job(db: Session, campaign_id: str, run_at: datetime.datetime) -> ScheduledJob:
    """Enqueues a campaign for execution at a scheduled timestamp."""
    job = ScheduledJob(
        campaign_id=campaign_id,
        run_at=run_at,
        status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def process_due_jobs(
    db: Session,
    current_time: Optional[datetime.datetime] = None,
    simulate_crash_at_index: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Executes all scheduled jobs due on or before current_time.
    Supports crash simulation for Probe 3 verification.
    """
    if not current_time:
        current_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    # Find due pending or crashed (running) jobs
    due_jobs = db.query(ScheduledJob).filter(
        ScheduledJob.run_at <= current_time,
        ScheduledJob.status.in_(["pending", "running"])
    ).all()

    results = []

    for job in due_jobs:
        job.status = "running"
        job.attempts += 1
        db.commit()

        campaign = db.query(Campaign).filter(Campaign.id == job.campaign_id).first()
        if not campaign:
            job.status = "failed"
            job.last_error = "Campaign not found"
            db.commit()
            continue

        # Process each approved variant
        approved_variants = [v for v in campaign.variants if v.status == "approved"]
        post_count = 0

        try:
            for idx, variant in enumerate(approved_variants):
                # Check crash simulation
                if simulate_crash_at_index is not None and idx == simulate_crash_at_index:
                    db.commit()  # Leave state as interrupted
                    raise RuntimeError("SIMULATED_WORKER_CRASH_MID_BATCH")

                publisher = get_publisher(variant.platform)
                
                # Deterministic Idempotency Key bound to campaign and platform slot
                idemp_key = f"idemp_{campaign.id}_{variant.platform}_slot1"

                # Crash-recovery & deduplication: Return cached result without re-publishing
                existing_record = db.query(IdempotencyRecord).filter(
                    IdempotencyRecord.idempotency_key == idemp_key
                ).first()
                if existing_record:
                    results.append({
                        "campaign_id": campaign.id,
                        "platform": variant.platform,
                        "post_id": existing_record.external_post_id,
                        "idempotent_replay": True
                    })
                    continue

                # Publish via adapter
                pub_result = publisher.publish(
                    db=db,
                    variant=variant,
                    idempotency_key=idemp_key
                )
                post_count += 1
                results.append({
                    "campaign_id": campaign.id,
                    "platform": variant.platform,
                    "post_id": pub_result.get("post_id"),
                    "idempotent_replay": pub_result.get("idempotent_replay", False)
                })

            # Mark job complete and campaign in publishing state (awaiting webhook)
            job.status = "completed"
            campaign.status = "publishing"
            db.commit()

        except RuntimeError as ex:
            if "SIMULATED_WORKER_CRASH" in str(ex):
                # Worker crashed mid-batch; leave status as 'running' for resumption test
                raise
            job.status = "failed"
            job.last_error = str(ex)
            campaign.status = "failed"
            db.commit()

    return results
