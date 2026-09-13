"""
MockPublisher Adapter
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R

Simulates a local mock adapter (e.g. MockXPublisher / MockTelegramPublisher).
Records what it would post in the local database and renders a preview without hitting external APIs.
"""

import uuid
from typing import Dict, Any
from sqlalchemy.orm import Session

from services.adapters.base import SocialPublisher
from models import SocialVariant, PublishHistory, IdempotencyRecord


class MockPublisher(SocialPublisher):
    def __init__(self, platform_name_override: str = "mock_x"):
        self._name = platform_name_override

    @property
    def platform_name(self) -> str:
        return self._name

    def publish(
        self,
        db: Session,
        variant: SocialVariant,
        idempotency_key: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Records the mock publish in database and returns preview payload."""
        # 1. Idempotency Check
        existing_idemp = db.query(IdempotencyRecord).filter(
            IdempotencyRecord.idempotency_key == idempotency_key
        ).first()
        if existing_idemp:
            import json
            return json.loads(existing_idemp.response_body)

        mock_post_id = f"mock_{self._name}_{uuid.uuid4().hex[:8]}"
        mock_url = f"https://mock-social.local/{self._name}/{mock_post_id}"

        response_body = {
            "status": "success",
            "idempotent_replay": False,
            "post_id": mock_post_id,
            "post_url": mock_url,
            "platform": self._name,
            "preview": {
                "caption": variant.caption,
                "image_path": variant.image_path
            }
        }

        # 2. Record PublishHistory
        history = PublishHistory(
            campaign_id=variant.campaign_id,
            variant_id=variant.id,
            platform=self._name,
            idempotency_key=idempotency_key,
            status="success",
            external_post_id=mock_post_id,
            post_url=mock_url,
            error_message=None
        )
        db.add(history)

        # 3. Store Idempotency Record
        import json
        idemp_rec = IdempotencyRecord(
            idempotency_key=idempotency_key,
            platform=self._name,
            external_post_id=mock_post_id,
            response_body=json.dumps(response_body)
        )
        db.add(idemp_rec)
        db.commit()

        return response_body
