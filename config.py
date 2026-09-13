"""
Configuration & Platform Profiles
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R
"""

import os
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'social_studio.db')}")

# Encryption Key for AES-GCM token storage at rest (32 bytes = 256 bits)
ENCRYPTION_KEY_HEX = os.getenv(
    "TOKEN_ENCRYPTION_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)

# Webhook Secret for HMAC-SHA256 signature verification
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "whsec_social_studio_delivery_verified_2026")

# Constraint Profiles for Target Platforms
PLATFORM_PROFILES: Dict[str, Dict[str, Any]] = {
    "instagram": {
        "name": "Instagram",
        "image_width": 1080,
        "image_height": 1080,
        "aspect_ratio": "1:1",
        "max_caption_length": 2200,
        "min_hashtags": 3,
        "max_hashtags": 15,
        "tone": "engaging, visual, storytelling",
        "safe_zone_ratio": 0.85
    },
    "x": {
        "name": "X (Twitter)",
        "image_width": 1600,
        "image_height": 900,
        "aspect_ratio": "16:9",
        "max_caption_length": 280,
        "min_hashtags": 1,
        "max_hashtags": 3,
        "tone": "punchy, concise, authoritative",
        "safe_zone_ratio": 0.85
    },
    "linkedin": {
        "name": "LinkedIn",
        "image_width": 1200,
        "image_height": 627,
        "aspect_ratio": "1.91:1",
        "max_caption_length": 3000,
        "min_hashtags": 2,
        "max_hashtags": 5,
        "tone": "professional, structured, insight-driven",
        "safe_zone_ratio": 0.90
    }
}

# Composable Prompt Fragments (Modelled on FlyRank config/social-prompts.config.ts)
BRAND_VOICE_FRAGMENT = (
    "Voice: Authoritative, pragmatic, deeply technical yet accessible. "
    "Focus on real-world engineering resilience, measurable metrics, and zero marketing fluff."
)

PLATFORM_PROMPT_FRAGMENTS: Dict[str, str] = {
    "instagram": (
        "Focus on behind-the-scenes engineering craftsmanship and visual aesthetics. "
        "Include line breaks for scannability and append 3 to 10 relevant topic hashtags."
    ),
    "x": (
        "Distill the core technical insight into a high-impact hook under 280 characters. "
        "Max 2 hashtags. Every character must deliver value."
    ),
    "linkedin": (
        "Structure with a provocative opening question, 3 bullet points of technical takeaway, "
        "and a call to engineering discussion. Use 3 professional industry hashtags."
    )
}
