"""
Escalation routing engine.

Routing matrix:
  ESCALATE + HIGH   → case (HIGH) + urgent notification + watchlist (72h)
  ESCALATE + MEDIUM → case (MEDIUM) + urgent notification + watchlist (48h)
  ESCALATE + LOW    → case (LOW)   + notification
  REVIEW            → case (LOW)   + review-channel notification
  DISMISS           → no actions
"""
from dataclasses import dataclass, field
from typing import List

from src.ingestion.models import Alert
from src.triage.schema import TriageResult
from .actions import (
    ActionResult,
    add_to_watchlist,
    create_compliance_case,
    send_alert_notification,
)


@dataclass
class EscalationOutcome:
    alert_id: str
    verdict: str
    actions_taken: List[ActionResult] = field(default_factory=list)
    case_id: str = ""

    @property
    def success(self) -> bool:
        return all(a.success for a in self.actions_taken)


class EscalationEngine:

    def escalate(self, alert: Alert, triage: TriageResult) -> EscalationOutcome:
        outcome = EscalationOutcome(alert_id=alert.alert_id, verdict=triage.verdict)

        if triage.verdict == "DISMISS":
            alert.escalation_status = "DISMISSED"
            return outcome

        # ── Create compliance case ────────────────────────────────────────────
        priority = self._case_priority(triage.verdict, alert.severity)
        case_result = create_compliance_case(
            alert_id=alert.alert_id,
            pattern_type=alert.pattern_type,
            trader_id=alert.trader_id,
            symbol=alert.symbol,
            severity=alert.severity,
            verdict=triage.verdict,
            confidence=triage.confidence_score,
            rationale=triage.rationale,
            recommended_action=triage.recommended_action,
            priority=priority,
        )
        outcome.actions_taken.append(case_result)
        if case_result.success:
            outcome.case_id = case_result.details["case_id"]

        # ── Send notification ─────────────────────────────────────────────────
        channel = "compliance-urgent" if triage.verdict == "ESCALATE" else "compliance-review"
        notif_result = send_alert_notification(
            alert_id=alert.alert_id,
            pattern_type=alert.pattern_type,
            trader_id=alert.trader_id,
            symbol=alert.symbol,
            verdict=triage.verdict,
            confidence=triage.confidence_score,
            channel=channel,
            case_id=outcome.case_id or None,
        )
        outcome.actions_taken.append(notif_result)

        # ── Watchlist (ESCALATE + HIGH or MEDIUM only) ────────────────────────
        if triage.verdict == "ESCALATE" and alert.severity in ("HIGH", "MEDIUM"):
            hours = 72 if alert.severity == "HIGH" else 48
            wl_result = add_to_watchlist(
                trader_id=alert.trader_id,
                reason=f"{alert.pattern_type} – conf {triage.confidence_score:.0%}",
                alert_id=alert.alert_id,
                duration_hours=hours,
            )
            outcome.actions_taken.append(wl_result)

        alert.escalation_status = triage.verdict
        return outcome

    def escalate_all(
        self, alerts: List[Alert], triage_results: List[TriageResult]
    ) -> List[EscalationOutcome]:
        return [self.escalate(a, t) for a, t in zip(alerts, triage_results)]

    @staticmethod
    def _case_priority(verdict: str, severity: str) -> str:
        if verdict == "ESCALATE":
            return {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}.get(severity, "MEDIUM")
        return "LOW"
