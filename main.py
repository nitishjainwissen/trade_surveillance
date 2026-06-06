"""
Trade Surveillance & Alert Triage Engine
Entry point — runs the full pipeline: ingest -> detect -> triage -> escalate
"""
from pathlib import Path

from src.ingestion import load_dataset, DataReplayer
from src.detection import DetectionEngine
from src.triage import TriageEngine
from src.escalation import EscalationEngine

DATA_DIR = Path(__file__).parent / "data"

SEVERITY_TAG = {"HIGH": "[HIGH]  ", "MEDIUM": "[MED]   ", "LOW": "[LOW]   "}
VERDICT_TAG  = {"ESCALATE": "[ESCALATE]", "REVIEW": "[REVIEW]  ", "DISMISS": "[DISMISS] "}


def _divider(title: str) -> None:
    print(f"\n{'=' * 3} {title} {'=' * (50 - len(title))}")


def main():
    # ── Task 1: Ingest ────────────────────────────────────────────────────────
    _divider("Dataset Summary")
    orders, trades = load_dataset(str(DATA_DIR))

    replayer = DataReplayer(orders, trades, speed_factor=100.0)
    summary = replayer.summary()
    print(f"  Total events : {summary['total_events']}")
    print(f"  Order events : {summary['order_events']}")
    print(f"  Trade events : {summary['trade_events']}")
    print(f"  Symbols      : {', '.join(summary['symbols'])}")
    print(f"  Traders      : {', '.join(summary['traders'])}")
    print(f"  Time range   : {summary['time_range']['start']} to {summary['time_range']['end']}")

    _divider("Replaying Events")
    event_log = []

    def handle_event(event):
        event_log.append(event)
        etype = type(event).__name__
        trader = getattr(event, "trader_id", None) or event.buyer_trader_id
        print(f"  [{event.timestamp.strftime('%H:%M:%S.%f')[:-3]}] {etype:12s} | {event.symbol:5s} | {trader}")

    replayer.replay(on_event=handle_event, real_time=False)
    print(f"\n  Ingestion complete - {len(event_log)} events processed.")

    # ── Task 2: Detect ────────────────────────────────────────────────────────
    _divider("Pattern Detection")
    alerts = DetectionEngine().run(orders, trades)

    if not alerts:
        print("  No suspicious patterns detected.")
    else:
        for alert in alerts:
            tag = SEVERITY_TAG.get(alert.severity, "        ")
            print(f"  {tag} {alert.pattern_type:15s} | {alert.trader_id} / {alert.symbol}")
            print(f"           {alert.description}")
            for k, v in alert.evidence.items():
                print(f"             {k}: {v}")
            print()

    print(f"  {len(alerts)} alert(s) queued for triage.")

    # ── Task 3: AI Triage ─────────────────────────────────────────────────────
    _divider("AI Triage (Claude)")
    triage_results = TriageEngine().triage_all(alerts)

    for alert, result in zip(alerts, triage_results):
        tag = VERDICT_TAG.get(result.verdict, "          ")
        print(f"\n  {tag} {alert.pattern_type} | {alert.trader_id} / {alert.symbol}")
        print(f"    Confidence      : {result.confidence_score:.0%}")
        print(f"    False-pos prob  : {result.false_positive_probability:.0%}")
        print(f"    Rationale       : {result.rationale[:200]}...")
        print(f"    Recommended     : {result.recommended_action[:150]}...")

    print(f"\n  {len(triage_results)} verdict(s) issued.")

    # ── Task 4: Escalation ────────────────────────────────────────────────────
    _divider("Automated Escalation")
    outcomes = EscalationEngine().escalate_all(alerts, triage_results)

    for outcome in outcomes:
        if not outcome.actions_taken:
            print(f"\n  [DISMISSED] {outcome.alert_id[:8]}... - no actions taken")
            continue

        case_ref = f"  Case: {outcome.case_id}" if outcome.case_id else ""
        print(f"\n  Alert {outcome.alert_id[:8]}... -> {outcome.verdict}{case_ref}")
        for action in outcome.actions_taken:
            status = "OK" if action.success else "FAIL"
            print(f"    [{status}] {action.message}")

    print(f"\n  Escalation complete. Output files written to data/")
    print(f"    cases.json        - compliance cases")
    print(f"    notifications.json - alert notifications")
    print(f"    watchlist.json     - trader monitoring flags")

    # ── Final summary ─────────────────────────────────────────────────────────
    _divider("Pipeline Complete")
    escalated = sum(1 for o in outcomes if o.verdict == "ESCALATE")
    reviewed   = sum(1 for o in outcomes if o.verdict == "REVIEW")
    dismissed  = sum(1 for o in outcomes if o.verdict == "DISMISS")
    print(f"  Alerts detected : {len(alerts)}")
    print(f"  Escalated       : {escalated}")
    print(f"  For review      : {reviewed}")
    print(f"  Dismissed       : {dismissed}")
    total_actions = sum(len(o.actions_taken) for o in outcomes)
    print(f"  Actions fired   : {total_actions}")


if __name__ == "__main__":
    main()
