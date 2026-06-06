import time
from datetime import datetime
from typing import Callable, List, Union

from .models import OrderEvent, TradeEvent

Event = Union[OrderEvent, TradeEvent]


class DataReplayer:
    """Replays trade/order events in chronological order at a configurable speed."""

    def __init__(self, orders: List[OrderEvent], trades: List[TradeEvent], speed_factor: float = 1.0):
        self.speed_factor = speed_factor  # >1 = faster, <1 = slower
        self._events: List[Event] = sorted(
            orders + trades,
            key=lambda e: e.timestamp
        )

    def replay(self, on_event: Callable[[Event], None], real_time: bool = False) -> None:
        """
        Iterate events in time order, calling on_event for each.
        If real_time=True, sleep between events to simulate live feed.
        """
        prev_ts: datetime = None
        print(f"[Replayer] Starting replay of {len(self._events)} events "
              f"(speed_factor={self.speed_factor}, real_time={real_time})")

        for event in self._events:
            if real_time and prev_ts is not None:
                delta = (event.timestamp - prev_ts).total_seconds()
                sleep_time = delta / self.speed_factor
                if sleep_time > 0:
                    time.sleep(min(sleep_time, 5.0))  # cap at 5s to keep demos snappy

            on_event(event)
            prev_ts = event.timestamp

        print("[Replayer] Replay complete.")

    def get_events(self) -> List[Event]:
        return self._events

    def summary(self) -> dict:
        if not self._events:
            return {"total": 0}
        order_events = [e for e in self._events if isinstance(e, OrderEvent)]
        trade_events = [e for e in self._events if isinstance(e, TradeEvent)]
        symbols = {e.symbol for e in self._events}
        traders = {e.trader_id if isinstance(e, OrderEvent) else e.buyer_trader_id
                   for e in self._events}
        return {
            "total_events": len(self._events),
            "order_events": len(order_events),
            "trade_events": len(trade_events),
            "symbols": sorted(symbols),
            "traders": sorted(traders),
            "time_range": {
                "start": self._events[0].timestamp.isoformat(),
                "end": self._events[-1].timestamp.isoformat(),
            },
        }
