"""
Image Variant Pipeline
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R

Generates platform-compliant image variants:
- Instagram: 1080x1080 (1:1 square)
- X (Twitter): 1600x900 (16:9 landscape)
Keeps content bounded inside designated platform safe zones.
"""

import os
import uuid
from typing import Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

from config import ARTIFACTS_DIR, PLATFORM_PROFILES


def create_base_canvas(width: int = 1600, height: int = 1200, title: str = "FlyRank System") -> Image.Image:
    """Creates a high-contrast branded master canvas if no raw image is uploaded."""
    img = Image.new("RGB", (width, height), color=(15, 23, 42))  # Slate dark
    draw = ImageDraw.Draw(img)

    # Gradient-like visual elements & branding overlay
    draw.rectangle([(0, 0), (width, 8)], fill=(59, 130, 246))  # Blue accent top
    draw.rectangle([(60, 60), (width - 60, height - 60)], outline=(30, 41, 59), width=3)
    
    # Safe zone visual marker
    draw.rectangle([(120, 120), (width - 120, height - 120)], outline=(51, 65, 85), width=2)
    
    # Title overlay in center safe-zone
    draw.text((160, height // 2 - 40), title[:40], fill=(248, 250, 252))
    draw.text((160, height // 2 + 20), "Production Architecture & Engineering Verified", fill=(148, 163, 184))

    return img


def generate_platform_variant(
    source_image_path: Optional[str],
    platform: str,
    title: str = "Campaign Post"
) -> Tuple[str, Tuple[int, int]]:
    """
    Generates an image variant strictly matching target platform dimensions:
    - Instagram: 1080 x 1080 (1:1)
    - X (Twitter): 1600 x 900 (16:9)
    Returns:
        (saved_filepath, (width, height))
    """
    profile = PLATFORM_PROFILES.get(platform.lower())
    if not profile:
        raise ValueError(f"Unknown platform profile: {platform}")

    target_w = profile["image_width"]
    target_h = profile["image_height"]

    # 1. Load or generate source
    if source_image_path and os.path.exists(source_image_path):
        source_img = Image.open(source_image_path).convert("RGB")
    else:
        source_img = create_base_canvas(1600, 1200, title=title)

    # 2. Aspect-preserving crop and scale (fit with center gravity)
    src_w, src_h = source_img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # Source is wider than target: crop horizontal margins
        new_width = int(src_h * target_ratio)
        left = (src_w - new_width) // 2
        crop_box = (left, 0, left + new_width, src_h)
    else:
        # Source is taller than target: crop vertical margins
        new_height = int(src_w / target_ratio)
        top = (src_h - new_height) // 2
        crop_box = (0, top, src_w, top + new_height)

    cropped_img = source_img.crop(crop_box)
    final_variant = cropped_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # 3. Apply platform-specific safe-zone watermark
    draw = ImageDraw.Draw(final_variant)
    brand_tag = f"FLYRANK // {profile['name'].upper()}"
    draw.text((target_w - 240, target_h - 40), brand_tag, fill=(148, 163, 184))

    # 4. Save to artifacts
    filename = f"{platform}_{uuid.uuid4().hex[:8]}.jpg"
    out_path = os.path.join(ARTIFACTS_DIR, filename)
    final_variant.save(out_path, format="JPEG", quality=95)

    return out_path, (target_w, target_h)
