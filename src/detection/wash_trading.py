from collections import defaultdict
from datetime import timedelta
from typing import List

from src.ingestion.models import Alert, OrderEvent, OrderSide, OrderStatus, TradeEvent
from .base import BaseDetector
from .utils import next_alert_id


class WashTradingDetector(BaseDetector):
    """
    Detects wash trading: a trader rapidly alternates buy/sell executions on the
    same instrument, inflating apparent volume without real economic exposure.

    Classic markers: similar quantities, tight timestamps, price nearly unchanged.
    """

    def __init__(
        self,
        min_pairs: int = 2,
        time_window_s: float = 30.0,
        qty_tolerance: float = 0.20,
        price_tolerance: float = 0.005,
    ):
        self.min_pairs = min_pairs
        self.time_window_s = time_window_s
        self.qty_tolerance = qty_tolerance        # allow 20% qty difference between paired legs
        self.price_tolerance = price_tolerance   # allow 0.5% price difference between legs

    def analyze(self, orders: List[OrderEvent], trades: List[TradeEvent]) -> List[Alert]:
        alerts = []

        # Only consider filled orders (actual executions)
        filled = [o for o in orders if o.status == OrderStatus.FILLED]

        groups: dict = defaultdict(list)
        for o in filled:
            groups[(o.trader_id, o.symbol)].append(o)

        for (trader_id, symbol), evts in groups.items():
            evts_sorted = sorted(evts, key=lambda e: e.timestamp)
            alert = self._detect_pairs(trader_id, symbol, evts_sorted)
            if alert:
                alerts.append(alert)

        return alerts

    def _detect_pairs(
        self, trader_id: str, symbol: str, evts: List[OrderEvent]
    ) -> Alert | None:
        buys = [e for e in evts if e.side == OrderSide.BUY]
        sells = [e for e in evts if e.side == OrderSide.SELL]

        if not buys or not sells:
            return None

        matched_pairs = []
        used_sells = set()

        for buy in buys:
            window_end = buy.timestamp + timedelta(seconds=self.time_window_s)
            for i, sell in enumerate(sells):
                if i in used_sells:
                    continue
                if sell.timestamp < buy.timestamp:
                    continue
                if sell.timestamp > window_end:
                    break

                qty_diff = abs(buy.quantity - sell.quantity) / max(buy.quantity, sell.quantity)
                price_diff = abs(buy.price - sell.price) / max(buy.price, sell.price)

                if qty_diff <= self.qty_tolerance and price_diff <= self.price_tolerance:
                    matched_pairs.append((buy, sell))
                    used_sells.add(i)
                    break

        if len(matched_pairs) < self.min_pairs:
            return None

        total_volume = sum(b.quantity for b, _ in matched_pairs)
        avg_buy_price = sum(b.price for b, _ in matched_pairs) / len(matched_pairs)
        avg_sell_price = sum(s.price for _, s in matched_pairs) / len(matched_pairs)
        order_ids = [o.order_id for pair in matched_pairs for o in pair]
        severity = self._severity(len(matched_pairs), total_volume)

        return Alert(
            alert_id=next_alert_id(),
            pattern_type="WASH_TRADING",
            severity=severity,
            trader_id=trader_id,
            symbol=symbol,
            description=(
                f"Wash trading detected: {len(matched_pairs)} matched buy/sell pairs "
                f"within {self.time_window_s}s window, "
                f"total volume {total_volume:,.0f} shares"
            ),
            evidence={
                "matched_pairs": len(matched_pairs),
                "total_artificial_volume": total_volume,
                "avg_buy_price": round(avg_buy_price, 4),
                "avg_sell_price": round(avg_sell_price, 4),
                "pnl_approx": round((avg_sell_price - avg_buy_price) * total_volume, 2),
                "time_window_s": self.time_window_s,
            },
            timestamp=matched_pairs[0][0].timestamp,
            order_ids=order_ids,
        )

    @staticmethod
    def _severity(pair_count: int, total_volume: float) -> str:
        score = 0
        if pair_count >= 5:
            score += 2
        elif pair_count >= 3:
            score += 1
        if total_volume >= 5000:
            score += 2
        elif total_volume >= 1000:
            score += 1

        if score >= 3:
            return "HIGH"
        elif score >= 2:
            return "MEDIUM"
        return "LOW"
