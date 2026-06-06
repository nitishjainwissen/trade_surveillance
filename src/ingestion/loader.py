import csv
import io
from datetime import datetime
from pathlib import Path
from typing import IO, List, Tuple

from .models import OrderEvent, OrderSide, OrderStatus, OrderType, TradeEvent


def _parse_orders(reader: csv.DictReader) -> List[OrderEvent]:
    orders = []
    for row in reader:
        orders.append(OrderEvent(
            order_id=row["order_id"],
            trader_id=row["trader_id"],
            account_id=row.get("account_id", ""),
            symbol=row["symbol"],
            side=OrderSide(row["side"]),
            order_type=OrderType(row["order_type"]),
            quantity=float(row["quantity"]),
            price=float(row["price"]),
            status=OrderStatus(row["status"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            venue=row.get("venue", "NYSE"),
        ))
    return orders


def _parse_trades(reader: csv.DictReader) -> List[TradeEvent]:
    trades = []
    for row in reader:
        trades.append(TradeEvent(
            trade_id=row["trade_id"],
            buy_order_id=row["buy_order_id"],
            sell_order_id=row["sell_order_id"],
            symbol=row["symbol"],
            quantity=float(row["quantity"]),
            price=float(row["price"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            buyer_trader_id=row["buyer_trader_id"],
            seller_trader_id=row["seller_trader_id"],
            venue=row.get("venue", "NYSE"),
        ))
    return trades


def load_orders(filepath: str) -> List[OrderEvent]:
    with open(filepath, newline="", encoding="utf-8") as f:
        return _parse_orders(csv.DictReader(f))


def load_trades(filepath: str) -> List[TradeEvent]:
    with open(filepath, newline="", encoding="utf-8") as f:
        return _parse_trades(csv.DictReader(f))


def load_orders_from_buffer(buf: IO[bytes]) -> List[OrderEvent]:
    """Load orders from an in-memory buffer (e.g. Streamlit file_uploader)."""
    text = io.StringIO(buf.read().decode("utf-8"))
    return _parse_orders(csv.DictReader(text))


def load_trades_from_buffer(buf: IO[bytes]) -> List[TradeEvent]:
    """Load trades from an in-memory buffer (e.g. Streamlit file_uploader)."""
    text = io.StringIO(buf.read().decode("utf-8"))
    return _parse_trades(csv.DictReader(text))


def load_dataset(data_dir: str) -> Tuple[List[OrderEvent], List[TradeEvent]]:
    base = Path(data_dir)
    orders = load_orders(base / "orders.csv")
    trades = load_trades(base / "trades.csv")
    print(f"[Loader] Loaded {len(orders)} order events, {len(trades)} trade events")
    return orders, trades
