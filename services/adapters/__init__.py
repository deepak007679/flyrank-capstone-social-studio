"""
Adapter Registry & Factory
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R
"""

from typing import Dict, Type
from services.adapters.base import SocialPublisher
from services.adapters.instagram_adapter import FakeInstagramPublisher
from services.adapters.x_adapter import FakeXPublisher
from services.adapters.mock_adapter import MockPublisher

# Active Platform Adapter Registry
_ADAPTER_REGISTRY: Dict[str, SocialPublisher] = {
    "instagram": FakeInstagramPublisher(),
    "x": FakeXPublisher(),
    "mock_x": MockPublisher("mock_x"),
    "mock_telegram": MockPublisher("mock_telegram"),
    "telegram": FakeXPublisher(),  # Default routing for demonstration
}


def get_publisher(platform: str) -> SocialPublisher:
    """Returns the registered publisher adapter for a platform."""
    plat = platform.lower()
    if plat in _ADAPTER_REGISTRY:
        return _ADAPTER_REGISTRY[plat]
    # Fallback to dynamic mock adapter for unknown/swapped platforms
    return MockPublisher(plat)


def register_adapter(platform: str, adapter: SocialPublisher):
    """Allows runtime configuration swap (e.g. swapping telegram to mock_x) without touching business logic."""
    _ADAPTER_REGISTRY[platform.lower()] = adapter
