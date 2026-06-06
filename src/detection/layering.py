import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List

from src.ingestion.models import Alert, OrderEvent, OrderSide, OrderStatus, TradeEvent
from .base import BaseDetector
from .utils import next_alert_id


class LayeringDetector(BaseDetector):
    """
    Detects layering: a trader floods one side of the book with orders,
    cancels most of them rapidly, then executes a large order on the opposite side.

    Layering artificially moves the perceived supply/demand to nudge the price
    before the real trade fires.
    """

    def __init__(
        self,
        min_orders: int = 5,
        cancel_rate_threshold: float = 0.6,
        time_window_ms: float = 2000,
        opposite_trade_window_s: float = 10.0,
        baseline_cancel_rate: float = 0.30,
        baseline_cancel_time_ms: float = 5000.0,
    ):
        self.min_orders = min_orders
        self.cancel_rate_threshold = cancel_rate_threshold
        self.time_window_ms = time_window_ms
        self.opposite_trade_window_s = opposite_trade_window_s
        self.baseline_cancel_rate = baseline_cancel_rate
        self.baseline_cancel_time_ms = baseline_cancel_time_ms

    def analyze(self, orders: List[OrderEvent], trades: List[TradeEvent]) -> List[Alert]:
        alerts = []

        # Group orders by (trader, symbol)
        groups: dict = defaultdict(list)
        for o in orders:
            groups[(o.trader_id, o.symbol)].append(o)

        for (trader_id, symbol), evts in groups.items():
            evts_sorted = sorted(evts, key=lambda e: e.timestamp)
            alerts += self._scan_windows(trader_id, symbol, evts_sorted, orders, trades)

        return alerts

    def _scan_windows(
        self,
        trader_id: str,
        symbol: str,
        evts: List[OrderEvent],
        all_orders: List[OrderEvent],
        trades: List[TradeEvent],
    ) -> List[Alert]:
        alerts = []
        placed = [e for e in evts if e.status == OrderStatus.PLACED]

        # Slide a window over PLACED events grouped by side
        for side in (OrderSide.BUY, OrderSide.SELL):
            side_placed = [e for e in placed if e.side == side]
            if len(side_placed) < self.min_orders:
                continue

            # Find dense bursts: first-to-last span <= time_window_ms
            window_start = 0
            while window_start < len(side_placed):
                burst = [side_placed[window_start]]
                for i in range(window_start + 1, len(side_placed)):
                    span_ms = (side_placed[i].timestamp - burst[0].timestamp).total_seconds() * 1000
                    if span_ms <= self.time_window_ms:
                        burst.append(side_placed[i])
                    else:
                        break

                if len(burst) >= self.min_orders:
                    alert = self._evaluate_burst(trader_id, symbol, side, burst, all_orders, trades)
                    if alert:
                        alerts.append(alert)
                    window_start += len(burst)
                else:
                    window_start += 1

        return alerts

    def _evaluate_burst(
        self,
        trader_id: str,
        symbol: str,
        side: OrderSide,
        burst: List[OrderEvent],
        all_orders: List[OrderEvent],
        trades: List[TradeEvent],
    ) -> Alert | None:
        burst_ids = {e.order_id for e in burst}
        burst_end = max(e.timestamp for e in burst)

        # Count cancellations of these orders
        placed_time = {e.order_id: e.timestamp for e in burst}
        cancelled_events = [
            e for e in all_orders
            if e.order_id in burst_ids and e.status == OrderStatus.CANCELLED
        ]
        cancelled_ids = {e.order_id for e in cancelled_events}
        cancel_rate = len(cancelled_ids) / len(burst)

        if cancel_rate < self.cancel_rate_threshold:
            return None

        # Compute median time-to-cancel for cancelled orders
        cancel_times_ms = [
            (e.timestamp - placed_time[e.order_id]).total_seconds() * 1000
            for e in cancelled_events
            if e.order_id in placed_time
        ]
        median_cancel_ms = round(statistics.median(cancel_times_ms), 1) if cancel_times_ms else 0.0

        # Look for an opposite-side execution shortly after the burst
        opposite_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
        deadline = burst_end + timedelta(seconds=self.opposite_trade_window_s)

        opposite_fills = [
            e for e in all_orders
            if e.trader_id == trader_id
            and e.symbol == symbol
            and e.side == opposite_side
            and e.status == OrderStatus.FILLED
            and burst_end <= e.timestamp <= deadline
        ]

        total_burst_qty = sum(e.quantity for e in burst)
        avg_burst_price = sum(e.price for e in burst) / len(burst)
        burst_duration_ms = round(
            (max(e.timestamp for e in burst) - burst[0].timestamp).total_seconds() * 1000, 1
        )

        # Baseline comparison metrics
        cancel_rate_delta = round(cancel_rate - self.baseline_cancel_rate, 3)
        cancel_time_vs_baseline = round(
            ((median_cancel_ms - self.baseline_cancel_time_ms) / self.baseline_cancel_time_ms) * 100, 1
        ) if self.baseline_cancel_time_ms > 0 else 0.0

        severity = self._severity(len(burst), cancel_rate, bool(opposite_fills))

        anomaly_note = (
            f" | Anomaly vs 30d baseline: +{cancel_rate_delta:.0%} cancel rate"
            f", median cancel {median_cancel_ms:.0f}ms"
            f" ({cancel_time_vs_baseline:+.0f}% vs {self.baseline_cancel_time_ms:.0f}ms baseline)"
        )

        return Alert(
            alert_id=next_alert_id(),
            pattern_type="LAYERING",
            severity=severity,
            trader_id=trader_id,
            symbol=symbol,
            description=(
                f"Layering detected: {len(burst)} {side.value} orders placed within "
                f"{self.time_window_ms}ms, {len(cancelled_ids)} cancelled "
                f"({cancel_rate:.0%} cancel rate)"
                + (", followed by opposite-side fill" if opposite_fills else "")
                + anomaly_note
            ),
            evidence={
                "burst_order_count": len(burst),
                "cancelled_count": len(cancelled_ids),
                "cancel_rate": round(cancel_rate, 3),
                "baseline_cancel_rate": self.baseline_cancel_rate,
                "cancel_rate_vs_baseline": f"+{cancel_rate_delta:.1%}" if cancel_rate_delta >= 0 else f"{cancel_rate_delta:.1%}",
                "median_cancel_time_ms": median_cancel_ms,
                "baseline_cancel_time_ms": self.baseline_cancel_time_ms,
                "cancel_time_vs_baseline": f"{cancel_time_vs_baseline:+.0f}%",
                "burst_side": side.value,
                "avg_burst_price": round(avg_burst_price, 4),
                "total_burst_qty": total_burst_qty,
                "burst_duration_ms": burst_duration_ms,
                "opposite_fills": len(opposite_fills),
            },
            timestamp=burst[0].timestamp,
            order_ids=list(burst_ids),
        )

    @staticmethod
    def _severity(burst_count: int, cancel_rate: float, has_opposite_fill: bool) -> str:
        score = 0
        if burst_count >= 10:
            score += 2
        elif burst_count >= 7:
            score += 1
        if cancel_rate >= 0.85:
            score += 2
        elif cancel_rate >= 0.70:
            score += 1
        if has_opposite_fill:
            score += 2

        if score >= 4:
            return "HIGH"
        elif score >= 2:
            return "MEDIUM"
        return "LOW"
