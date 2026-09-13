"""
FakeXPublisher Adapter
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R
"""

import time
import json
from typing import Dict, Any
from sqlalchemy.orm import Session

from services.adapters.base import SocialPublisher
from models import SocialVariant, OAuthCredential, PublishHistory, IdempotencyRecord
from services.crypto import decrypt_token
from fake_platform import fake_platform


class FakeXPublisher(SocialPublisher):
    @property
    def platform_name(self) -> str:
        return "x"

    def publish(
        self,
        db: Session,
        variant: SocialVariant,
        idempotency_key: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Publishes an X variant (16:9 image + punchy caption) with rate-limit backoff."""
        # 1. Retrieve encrypted OAuth token at rest
        cred = db.query(OAuthCredential).filter(OAuthCredential.platform == "x").first()
        if not cred:
            raise RuntimeError("Missing OAuth credentials for X")

        token = decrypt_token(cred.encrypted_token, cred.nonce_hex)

        attempt = 0
        while attempt < max_retries:
            attempt += 1
            status_code, body, headers = fake_platform.publish_post(
                platform="x",
                oauth_token=token,
                idempotency_key=idempotency_key,
                caption=variant.caption,
                image_path=variant.image_path
            )

            # Handle 429 Too Many Requests
            if status_code == 429:
                retry_after_str = headers.get("Retry-After", "1")
                try:
                    retry_seconds = float(retry_after_str)
                except ValueError:
                    retry_seconds = 1.0

                history = PublishHistory(
                    campaign_id=variant.campaign_id,
                    variant_id=variant.id,
                    platform="x",
                    idempotency_key=idempotency_key,
                    status="retry",
                    error_message=f"Rate limited (429). Backing off for {retry_seconds}s (Attempt {attempt})"
                )
                db.add(history)
                db.commit()

                time.sleep(retry_seconds)
                continue

            # Handle Success (200 / 201)
            if status_code in (200, 201):
                post_id = body.get("post_id", "")
                post_url = body.get("post_url", "")

                history = PublishHistory(
                    campaign_id=variant.campaign_id,
                    variant_id=variant.id,
                    platform="x",
                    idempotency_key=idempotency_key,
                    status="success",
                    external_post_id=post_id,
                    post_url=post_url,
                    error_message=None
                )
                db.add(history)

                existing_idemp = db.query(IdempotencyRecord).filter(
                    IdempotencyRecord.idempotency_key == idempotency_key
                ).first()
                if not existing_idemp:
                    idemp_rec = IdempotencyRecord(
                        idempotency_key=idempotency_key,
                        platform="x",
                        external_post_id=post_id,
                        response_body=json.dumps(body)
                    )
                    db.add(idemp_rec)

                db.commit()
                return body

            err_msg = body.get("message", f"HTTP {status_code}")
            history = PublishHistory(
                campaign_id=variant.campaign_id,
                variant_id=variant.id,
                platform="x",
                idempotency_key=idempotency_key,
                status="failed",
                error_message=err_msg
            )
            db.add(history)
            db.commit()
            raise RuntimeError(f"X publish failed: {err_msg}")

        raise RuntimeError("X publish exceeded maximum rate-limit retries")
