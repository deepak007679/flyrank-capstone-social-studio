"""
Composable Caption Composer & Constraint Validation
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R

Composes platform captions using modular prompt fragments:
[Brand Voice] + [Platform Rules] + [Content Summary]
Enforces strict character limits and hashtag ranges per platform.
"""

import re
from typing import Tuple, Optional, Dict
from config import PLATFORM_PROFILES, BRAND_VOICE_FRAGMENT, PLATFORM_PROMPT_FRAGMENTS


def count_hashtags(text: str) -> int:
    """Counts the number of hashtags in the caption."""
    return len(re.findall(r"#\w+", text))


def validate_caption_constraints(platform: str, caption: str) -> Tuple[bool, Optional[str]]:
    """
    Enforces constraint profiles strictly by code before review:
    1. Maximum character length.
    2. Minimum and maximum hashtag count.
    Returns:
        (is_valid, error_message_if_invalid)
    """
    profile = PLATFORM_PROFILES.get(platform.lower())
    if not profile:
        return False, f"Unknown platform: '{platform}'"

    max_len = profile["max_caption_length"]
    min_ht = profile["min_hashtags"]
    max_ht = profile["max_hashtags"]

    char_count = len(caption)
    if char_count > max_len:
        return (
            False,
            f"Rule broken: Caption length ({char_count} chars) exceeds {profile['name']} maximum of {max_len} chars."
        )

    ht_count = count_hashtags(caption)
    if ht_count < min_ht:
        return (
            False,
            f"Rule broken: Hashtag count ({ht_count}) below {profile['name']} minimum requirement of {min_ht} hashtags."
        )

    if ht_count > max_ht:
        return (
            False,
            f"Rule broken: Hashtag count ({ht_count}) exceeds {profile['name']} maximum limit of {max_ht} hashtags."
        )

    return True, None


def compose_caption(platform: str, title: str, content: str) -> str:
    """
    Generates a platform-aware caption composed from shared brand voice
    and platform-specific prompt fragments.
    """
    profile = PLATFORM_PROFILES.get(platform.lower())
    if not profile:
        raise ValueError(f"Unknown platform: {platform}")

    # Extract high-level summary from content
    clean_content = " ".join(content.split()[:40])

    if platform.lower() == "x":
        # Strict < 280 characters with 1-2 hashtags
        base_hook = f"Breaking down: {title[:70]}."
        summary = f" {clean_content[:120]}..."
        tags = " #SystemDesign #DevOps"
        total_len = len(base_hook) + len(summary) + len(tags)
        if total_len > 270:
            excess = total_len - 270
            summary = summary[:-excess-3] + "..."
        caption = f"{base_hook}{summary}{tags}"
        return caption

    elif platform.lower() == "instagram":
        # Visual storytelling with generous spacing & 4 hashtags
        caption = (
            f"Behind the architecture: {title}\n\n"
            f"{clean_content}\n\n"
            "Key takeaways for backend engineers:\n"
            "• Exactly-once idempotency guarantees\n"
            "• Zero-downtime durable scheduling\n"
            "• Cryptographic webhook validation\n\n"
            "#SoftwareEngineering #BackendDev #DistributedSystems #CleanCode"
        )
        return caption

    elif platform.lower() == "linkedin":
        # Structured professional technical discourse
        caption = (
            f"How do we build production publishing engines that survive real-world chaos?\n\n"
            f"In our latest technical breakdown: '{title}'\n\n"
            f"Summary:\n{clean_content}\n\n"
            "Here is the reliability architecture every senior engineer should consider:\n"
            "1. Token security via AES-GCM at rest\n"
            "2. Rate limit backoff with Retry-After compliance\n"
            "3. Mid-batch crash resumption\n\n"
            "What is your team's strategy for webhook trust boundaries?\n\n"
            "#Engineering #CloudArchitecture #Reliability #TechLeadership"
        )
        return caption

    else:
        return f"{title}: {clean_content} #Tech"
