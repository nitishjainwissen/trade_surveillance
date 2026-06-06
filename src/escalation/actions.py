"""
Concrete escalation actions.

Each action writes to a local JSON store that represents the downstream system
(case management, notification bus, trader watchlist). In production these
calls would be replaced by real API integrations (Jira, Slack, etc.).
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

DATA_DIR = Path(__file__).parent.parent.parent / "data"


# ── Shared helpers ──────────────────────────────────────────────────────────

def _load_json(path: Path) -> list:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


@dataclass
class ActionResult:
    action: str
    success: bool
    details: Dict[str, Any] = field(default_factory=dict)
    message: str = ""


# ── Action 1: Compliance Case ───────────────────────────────────────────────

CASES_FILE = DATA_DIR / "cases.json"


def create_compliance_case(
    alert_id: str,
    pattern_type: str,
    trader_id: str,
    symbol: str,
    severity: str,
    verdict: str,
    confidence: float,
    rationale: str,
    recommended_action: str,
    priority: str = "MEDIUM",
) -> ActionResult:
    """
    Create a compliance case in the case management system.
    Production: POST /rest/api/3/issue  (Jira) or equivalent.
    """
    case_id = f"CASE-{uuid.uuid4().hex[:6].upper()}"
    case = {
        "case_id": case_id,
        "alert_id": alert_id,
        "created_at": datetime.utcnow().isoformat(),
        "status": "OPEN",
        "priority": priority,
        "pattern_type": pattern_type,
        "trader_id": trader_id,
        "symbol": symbol,
        "alert_severity": severity,
        "triage_verdict": verdict,
        "ai_confidence": confidence,
        "rationale": rationale,
        "recommended_action": recommended_action,
        "assigned_to": "compliance-team",
    }

    cases = _load_json(CASES_FILE)
    cases.append(case)
    _save_json(CASES_FILE, cases)

    return ActionResult(
        action="create_compliance_case",
        success=True,
        details={"case_id": case_id, "priority": priority},
        message=f"Case {case_id} opened [{priority}] -> compliance-team",
    )


# ── Action 2: Alert Notification ────────────────────────────────────────────

NOTIFICATIONS_FILE = DATA_DIR / "notifications.json"


def send_alert_notification(
    alert_id: str,
    pattern_type: str,
    trader_id: str,
    symbol: str,
    verdict: str,
    confidence: float,
    channel: str,
    case_id: Optional[str] = None,
) -> ActionResult:
    """
    Publish an alert notification to the compliance channel.
    Production: POST https://slack.com/api/chat.postMessage  or email/Teams webhook.
    """
    notif_id = f"NOTIF-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "notif_id": notif_id,
        "sent_at": datetime.utcnow().isoformat(),
        "channel": channel,
        "alert_id": alert_id,
        "case_id": case_id,
        "message": (
            f"[{verdict}] {pattern_type} detected — "
            f"Trader: {trader_id}, Symbol: {symbol}, "
            f"AI Confidence: {confidence:.0%}"
        ),
        "delivered": True,
    }

    notifs = _load_json(NOTIFICATIONS_FILE)
    notifs.append(payload)
    _save_json(NOTIFICATIONS_FILE, notifs)

    return ActionResult(
        action="send_alert_notification",
        success=True,
        details={"notif_id": notif_id, "channel": channel},
        message=f"Notification {notif_id} sent to #{channel}",
    )


# ── Action 3: Trader Watchlist ───────────────────────────────────────────────

WATCHLIST_FILE = DATA_DIR / "watchlist.json"


def add_to_watchlist(
    trader_id: str,
    reason: str,
    alert_id: str,
    duration_hours: int = 72,
) -> ActionResult:
    """
    Flag a trader for heightened monitoring.
    Production: PATCH /api/v1/traders/{id}/risk-flags  or risk management system.
    """
    watchlist = _load_json(WATCHLIST_FILE)

    # Update existing entry if trader already flagged
    existing = next((e for e in watchlist if e["trader_id"] == trader_id), None)
    expires_at = (datetime.utcnow() + timedelta(hours=duration_hours)).isoformat()

    if existing:
        existing["alert_count"] = existing.get("alert_count", 1) + 1
        existing["last_alert_id"] = alert_id
        existing["monitoring_expires_at"] = expires_at
        existing["updated_at"] = datetime.utcnow().isoformat()
        action_taken = "updated"
    else:
        watchlist.append({
            "trader_id": trader_id,
            "flagged_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "reason": reason,
            "alert_count": 1,
            "last_alert_id": alert_id,
            "monitoring_expires_at": expires_at,
            "status": "ACTIVE",
        })
        action_taken = "added"

    _save_json(WATCHLIST_FILE, watchlist)

    return ActionResult(
        action="add_to_watchlist",
        success=True,
        details={"trader_id": trader_id, "monitoring_hours": duration_hours, "action": action_taken},
        message=f"Trader {trader_id} {action_taken} on watchlist ({duration_hours}h monitoring)",
    )
