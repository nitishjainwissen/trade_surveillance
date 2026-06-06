from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PLACED = "PLACED"
    CANCELLED = "CANCELLED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


@dataclass
class OrderEvent:
    order_id: str
    trader_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float
    status: OrderStatus
    timestamp: datetime
    account_id: str = ""
    venue: str = "NYSE"
    remaining_qty: float = field(init=False)

    def __post_init__(self):
        self.remaining_qty = self.quantity
        if isinstance(self.side, str):
            self.side = OrderSide(self.side)
        if isinstance(self.order_type, str):
            self.order_type = OrderType(self.order_type)
        if isinstance(self.status, str):
            self.status = OrderStatus(self.status)
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)


@dataclass
class TradeEvent:
    trade_id: str
    buy_order_id: str
    sell_order_id: str
    symbol: str
    quantity: float
    price: float
    timestamp: datetime
    buyer_trader_id: str
    seller_trader_id: str
    venue: str = "NYSE"

    def __post_init__(self):
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)


@dataclass
class Alert:
    alert_id: str
    pattern_type: str
    severity: str          # HIGH / MEDIUM / LOW
    trader_id: str
    symbol: str
    description: str
    evidence: dict
    timestamp: datetime
    order_ids: list = field(default_factory=list)
    trade_ids: list = field(default_factory=list)
    triage_verdict: Optional[str] = None
    confidence_score: Optional[float] = None
    rationale: Optional[str] = None
    escalation_status: Optional[str] = None
