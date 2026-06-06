from typing import List

from src.ingestion.models import Alert, OrderEvent, TradeEvent
from .layering import LayeringDetector
from .wash_trading import WashTradingDetector


class DetectionEngine:
    """Runs all registered detectors and aggregates their alerts."""

    def __init__(self):
        self._detectors = [
            LayeringDetector(
                min_orders=5,
                cancel_rate_threshold=0.60,
                time_window_ms=2000,
                opposite_trade_window_s=10.0,
            ),
            WashTradingDetector(
                min_pairs=2,
                time_window_s=30.0,
                qty_tolerance=0.20,
                price_tolerance=0.005,
            ),
        ]

    def run(self, orders: List[OrderEvent], trades: List[TradeEvent]) -> List[Alert]:
        all_alerts: List[Alert] = []
        for detector in self._detectors:
            found = detector.analyze(orders, trades)
            all_alerts.extend(found)

        all_alerts.sort(key=lambda a: (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[a.severity],
            a.timestamp,
        ))
        return all_alerts
