"""
Fake Social Platform Simulation Server
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R

Simulates external social platform APIs:
- OAuth token verification
- Rate limits (429 Too Many Requests + Retry-After)
- Exactly-once idempotency key deduplication
- HMAC-SHA256 signed delivery webhooks
"""

import hmac
import hashlib
import time
import json
import uuid
from typing import Dict, Any, Tuple, Optional
from config import WEBHOOK_SECRET


class FakePlatformServer:
    def __init__(self):
        # In-memory storage for the simulated platform
        self.published_posts: Dict[str, Dict[str, Any]] = {}
        self.idempotency_store: Dict[str, Dict[str, Any]] = {}
        self.rate_limit_until: float = 0.0
        self.rate_limit_retry_after_seconds: int = 1
        self.force_rate_limit: bool = False

    def trigger_temporary_rate_limit(self, seconds: int = 1):
        """Forces the next request to trigger a 429 Retry-After response."""
        self.force_rate_limit = True
        self.rate_limit_retry_after_seconds = seconds
        self.rate_limit_until = time.time() + seconds

    def clear_rate_limit(self):
        self.force_rate_limit = False
        self.rate_limit_until = 0.0

    def publish_post(
        self,
        platform: str,
        oauth_token: str,
        idempotency_key: str,
        caption: str,
        image_path: Optional[str] = None
    ) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        """
        Simulates POST /v1/posts on external platform.
        Returns:
            (status_code, response_body, headers)
        """
        # 1. OAuth Validation
        if not oauth_token or not oauth_token.startswith("tok_"):
            return 401, {"error": "Unauthorized", "message": "Invalid or expired OAuth token"}, {}

        # 2. Rate Limit Check (429 + Retry-After)
        now = time.time()
        if self.force_rate_limit and now < self.rate_limit_until:
            retry_after = max(1, int(self.rate_limit_until - now))
            headers = {"Retry-After": str(retry_after)}
            return 429, {
                "error": "Too Many Requests",
                "message": f"Platform rate limit exceeded. Retry after {retry_after} seconds."
            }, headers
        elif self.force_rate_limit and now >= self.rate_limit_until:
            # Cooldown passed
            self.force_rate_limit = False

        # 3. Idempotency Check (Zero duplicate posts)
        combined_key = f"{platform}:{idempotency_key}"
        if combined_key in self.idempotency_store:
            cached_record = self.idempotency_store[combined_key]
            return 200, {
                "status": "success",
                "idempotent_replay": True,
                "post_id": cached_record["post_id"],
                "post_url": cached_record["post_url"],
                "platform": platform
            }, {}

        # 4. Success - Create new post
        post_id = f"ext_{platform}_{uuid.uuid4().hex[:10]}"
        post_url = f"https://{platform}.fake-social.net/posts/{post_id}"
        record = {
            "post_id": post_id,
            "post_url": post_url,
            "platform": platform,
            "caption": caption,
            "image_path": image_path,
            "created_at": time.time()
        }
        self.published_posts[post_id] = record
        self.idempotency_store[combined_key] = record

        return 201, {
            "status": "success",
            "idempotent_replay": False,
            "post_id": post_id,
            "post_url": post_url,
            "platform": platform
        }, {}

    def generate_delivery_webhook(
        self,
        campaign_id: str,
        variant_id: str,
        platform: str,
        external_post_id: str,
        post_url: str,
        status: str = "published",
        secret: str = WEBHOOK_SECRET,
        forge_signature: bool = False
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Generates a delivery event payload with cryptographic HMAC-SHA256 signature.
        """
        payload = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "campaign_id": campaign_id,
            "variant_id": variant_id,
            "platform": platform,
            "status": status,
            "external_post_id": external_post_id,
            "post_url": post_url,
            "timestamp": int(time.time())
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

        if forge_signature:
            signature = "sha256=forged_bad_signature_hash_000000"
        else:
            computed = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
            signature = f"sha256={computed}"

        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature
        }
        return payload, headers


# Singleton instance for in-process testing & server use
fake_platform = FakePlatformServer()
