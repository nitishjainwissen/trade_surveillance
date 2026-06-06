from abc import ABC, abstractmethod
from typing import List

from src.ingestion.models import OrderEvent, TradeEvent, Alert


class BaseDetector(ABC):
    """All pattern detectors implement this interface."""

    @abstractmethod
    def analyze(self, orders: List[OrderEvent], trades: List[TradeEvent]) -> List[Alert]:
        """Return any alerts detected from the provided events."""
        ...
