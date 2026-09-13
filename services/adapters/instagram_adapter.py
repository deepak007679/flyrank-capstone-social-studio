"""
FakeInstagramPublisher Adapter
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R
"""

import time
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from services.adapters.base import SocialPublisher
from models import SocialVariant, OAuthCredential, PublishHistory, IdempotencyRecord
from services.crypto import decrypt_token
from fake_platform import fake_platform


class FakeInstagramPublisher(SocialPublisher):
    @property
    def platform_name(self) -> str:
        return "instagram"

    def publish(
        self,
        db: Session,
        variant: SocialVariant,
        idempotency_key: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Publishes an Instagram variant (1:1 image + caption) with rate-limit backoff."""
        # 1. Retrieve encrypted OAuth token at rest
        cred = db.query(OAuthCredential).filter(OAuthCredential.platform == "instagram").first()
        if not cred:
            raise RuntimeError("Missing OAuth credentials for Instagram")

        token = decrypt_token(cred.encrypted_token, cred.nonce_hex)

        attempt = 0
        while attempt < max_retries:
            attempt += 1
            status_code, body, headers = fake_platform.publish_post(
                platform="instagram",
                oauth_token=token,
                idempotency_key=idempotency_key,
                caption=variant.caption,
                image_path=variant.image_path
            )

            # Handle 429 Too Many Requests (Rate limit backoff)
            if status_code == 429:
                retry_after_str = headers.get("Retry-After", "1")
                try:
                    retry_seconds = float(retry_after_str)
                except ValueError:
                    retry_seconds = 1.0

                # Log retry attempt in history
                history = PublishHistory(
                    campaign_id=variant.campaign_id,
                    variant_id=variant.id,
                    platform="instagram",
                    idempotency_key=idempotency_key,
                    status="retry",
                    error_message=f"Rate limited (429). Backing off for {retry_seconds}s (Attempt {attempt})"
                )
                db.add(history)
                db.commit()

                # Back off
                time.sleep(retry_seconds)
                continue

            # Handle Success (200 / 201)
            if status_code in (200, 201):
                post_id = body.get("post_id", "")
                post_url = body.get("post_url", "")

                # Record in publish history
                history = PublishHistory(
                    campaign_id=variant.campaign_id,
                    variant_id=variant.id,
                    platform="instagram",
                    idempotency_key=idempotency_key,
                    status="success",
                    external_post_id=post_id,
                    post_url=post_url,
                    error_message=None
                )
                db.add(history)

                # Record in local idempotency store if not already present
                existing_idemp = db.query(IdempotencyRecord).filter(
                    IdempotencyRecord.idempotency_key == idempotency_key
                ).first()
                if not existing_idemp:
                    idemp_rec = IdempotencyRecord(
                        idempotency_key=idempotency_key,
                        platform="instagram",
                        external_post_id=post_id,
                        response_body=json.dumps(body)
                    )
                    db.add(idemp_rec)

                db.commit()
                return body

            # Other error
            err_msg = body.get("message", f"HTTP {status_code}")
            history = PublishHistory(
                campaign_id=variant.campaign_id,
                variant_id=variant.id,
                platform="instagram",
                idempotency_key=idempotency_key,
                status="failed",
                error_message=err_msg
            )
            db.add(history)
            db.commit()
            raise RuntimeError(f"Instagram publish failed: {err_msg}")

        raise RuntimeError("Instagram publish exceeded maximum rate-limit retries")
