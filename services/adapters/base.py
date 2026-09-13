"""
SocialPublisher Base Interface
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from models import SocialVariant


class SocialPublisher(ABC):
    """
    Abstract SocialPublisher Interface.
    Any new platform (real or mock) implements this contract.
    The application core depends strictly on this interface.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        pass

    @abstractmethod
    def publish(
        self,
        db: Session,
        variant: SocialVariant,
        idempotency_key: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Publishes a variant idempotently to the target platform.
        Handles rate limits (429 + Retry-After) and records publish history.
        """
        pass
