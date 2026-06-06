import os
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Trade Surveillance Engine",
    page_icon="🔍",
    layout="wide",
)

# Inject API key from Streamlit secrets (Streamlit Cloud) or fall back to .env
if "ANTHROPIC_API_KEY" in st.secrets:
    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

from src.ingestion import load_dataset, DataReplayer
from src.ingestion.models import OrderEvent, TradeEvent
from src.detection import DetectionEngine
from src.triage import TriageEngine
from src.escalation import EscalationEngine

DATA_DIR = Path(__file__).parent / "data"

# ── Colour helpers ────────────────────────────────────────────────────────────
_SEV_COLOR     = {"HIGH": "#e74c3c", "MEDIUM": "#e67e22", "LOW": "#27ae60"}
_VERDICT_COLOR = {"ESCALATE": "#e74c3c", "REVIEW": "#e67e22", "DISMISS": "#27ae60"}

def _badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color};color:#fff;padding:3px 10px;'
        f'border-radius:12px;font-size:0.78em;font-weight:700">{text}</span>'
    )


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🔍 Trade Surveillance & Alert Triage Engine")
st.caption("Wissen Technology Hackathon 2026  •  Ingest → Detect → Triage → Escalate")
st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Pipeline Controls")
    run = st.button("▶ Run Full Pipeline", type="primary", use_container_width=True)
    st.divider()
    st.markdown("**Claude API**")
    st.markdown("- Model: `claude-sonnet-4-6`")
    st.markdown("- Prompt caching ✓")
    st.markdown("- Structured JSON output ✓")
    st.divider()
    st.markdown("**Detectors**")
    st.markdown("- Layering / Spoofing")
    st.markdown("- Wash Trading")

if not run:
    st.info("Click **▶ Run Full Pipeline** in the sidebar to start the demo.")
    with st.expander("What does this do?"):
        st.markdown("""
This engine runs a four-stage compliance pipeline on simulated trading data:

| Stage | What happens |
|-------|-------------|
| 1 — Ingest | Loads order and trade events, replays them in time order |
| 2 — Detect | Scans for layering and wash-trading patterns, raises alerts |
| 3 — Triage | Sends each alert to Claude for a verdict + confidence score |
| 4 — Escalate | Routes outcomes to compliance cases, notifications, watchlist |
        """)
    st.stop()

# ── Guard: API key ────────────────────────────────────────────────────────────
if not os.getenv("ANTHROPIC_API_KEY"):
    st.error(
        "**ANTHROPIC_API_KEY not found.**  \n"
        "Add it to `.env` locally, or to *App settings → Secrets* on Streamlit Cloud."
    )
    st.stop()

# ═════════════════════════════════════════════════════════════════════════════
# Run the pipeline
# ═════════════════════════════════════════════════════════════════════════════

with st.status("Stage 1 — Ingesting trade data …", expanded=True) as s1:
    orders, trades = load_dataset(str(DATA_DIR))
    replayer = DataReplayer(orders, trades, speed_factor=1000.0)
    summary  = replayer.summary()
    events   = replayer.get_events()
    s1.update(label=f"Stage 1 — Ingestion complete  ({len(events)} events)", state="complete")

with st.status("Stage 2 — Running pattern detection …", expanded=True) as s2:
    alerts = DetectionEngine().run(orders, trades)
    s2.update(label=f"Stage 2 — Detection complete  ({len(alerts)} alert(s))", state="complete")

with st.status("Stage 3 — AI triage via Claude …", expanded=True) as s3:
    triage_results = TriageEngine().triage_all(alerts)
    s3.update(label=f"Stage 3 — Triage complete  ({len(triage_results)} verdict(s))", state="complete")

with st.status("Stage 4 — Triggering escalation workflows …", expanded=True) as s4:
    outcomes      = EscalationEngine().escalate_all(alerts, triage_results)
    total_actions = sum(len(o.actions_taken) for o in outcomes)
    s4.update(label=f"Stage 4 — Escalation complete  ({total_actions} actions fired)", state="complete")

st.success("✅ Pipeline complete!")

# ── Top-level metrics ─────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Events Processed", len(events))
c2.metric("Alerts Detected",  len(alerts))
c3.metric("Escalated",   sum(1 for r in triage_results if r.verdict == "ESCALATE"))
c4.metric("For Review",  sum(1 for r in triage_results if r.verdict == "REVIEW"))
c5.metric("Actions Fired", total_actions)

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# Tabs
# ═════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 Event Replay", "🚨 Detected Patterns", "🤖 AI Triage", "⚡ Escalation"]
)

# ── Tab 1 — Event Replay ──────────────────────────────────────────────────────
with tab1:
    st.subheader("Dataset Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Order Events", summary["order_events"])
    m2.metric("Trade Events", summary["trade_events"])
    m3.metric("Symbols",  len(summary["symbols"]))
    m4.metric("Traders",  len(summary["traders"]))

    st.markdown(
        f"**Time range:** `{summary['time_range']['start']}`  →  `{summary['time_range']['end']}`"
    )
    st.markdown(f"**Symbols:** {', '.join(f'`{s}`' for s in summary['symbols'])}")

    st.subheader("Event Log")
    rows = []
    for e in events:
        if isinstance(e, OrderEvent):
            rows.append({
                "Timestamp": e.timestamp.strftime("%H:%M:%S.%f")[:-3],
                "Type": "Order",
                "Symbol": e.symbol,
                "Trader": e.trader_id,
                "Side": e.side.value,
                "Qty": int(e.quantity),
                "Price": e.price,
                "Status": e.status.value,
            })
        else:
            rows.append({
                "Timestamp": e.timestamp.strftime("%H:%M:%S.%f")[:-3],
                "Type": "Trade",
                "Symbol": e.symbol,
                "Trader": e.buyer_trader_id,
                "Side": "EXEC",
                "Qty": int(e.quantity),
                "Price": e.price,
                "Status": "FILLED",
            })
    st.dataframe(rows, use_container_width=True, height=420)

# ── Tab 2 — Detected Patterns ─────────────────────────────────────────────────
with tab2:
    if not alerts:
        st.info("No suspicious patterns detected.")
    else:
        st.subheader(f"{len(alerts)} Alert(s) Raised")
        for alert in alerts:
            sev_color = _SEV_COLOR.get(alert.severity, "#888")
            with st.container(border=True):
                col_left, col_right = st.columns([3, 1])
                with col_left:
                    st.markdown(
                        f"**{alert.pattern_type}** &nbsp;"
                        + _badge(alert.severity, sev_color),
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Trader:** `{alert.trader_id}` &nbsp; **Symbol:** `{alert.symbol}`")
                    st.markdown(alert.description)
                with col_right:
                    st.markdown("**Evidence**")
                    for k, v in alert.evidence.items():
                        st.markdown(f"- `{k}`: **{v}**")

# ── Tab 3 — AI Triage ─────────────────────────────────────────────────────────
with tab3:
    st.subheader("Claude Triage Verdicts")
    for alert, result in zip(alerts, triage_results):
        verdict_color = _VERDICT_COLOR.get(result.verdict, "#888")
        with st.container(border=True):
            h1, h2 = st.columns([3, 1])
            with h1:
                st.markdown(
                    f"**{alert.pattern_type}** — `{alert.trader_id}` / `{alert.symbol}` &nbsp;"
                    + _badge(result.verdict, verdict_color),
                    unsafe_allow_html=True,
                )
            with h2:
                st.metric("AI Confidence", f"{result.confidence_score:.0%}")

            m1, m2 = st.columns(2)
            m1.metric("False Positive Probability", f"{result.false_positive_probability:.0%}")
            m2.metric("Severity", alert.severity)

            st.markdown("**Rationale**")
            st.markdown(result.rationale)

            st.markdown("**Recommended Action**")
            st.info(result.recommended_action)

            if result.key_risk_factors:
                st.markdown("**Key Risk Factors**")
                for factor in result.key_risk_factors:
                    st.markdown(f"- {factor}")

# ── Tab 4 — Escalation ────────────────────────────────────────────────────────
with tab4:
    st.subheader("Escalation Outcomes")
    for outcome, alert, result in zip(outcomes, alerts, triage_results):
        verdict_color = _VERDICT_COLOR.get(outcome.verdict, "#888")
        with st.container(border=True):
            st.markdown(
                f"**{alert.pattern_type}** — `{alert.trader_id}` / `{alert.symbol}` &nbsp;"
                + _badge(outcome.verdict, verdict_color),
                unsafe_allow_html=True,
            )
            if not outcome.actions_taken:
                st.markdown("_No actions taken (dismissed)._")
            else:
                for action in outcome.actions_taken:
                    icon = "✅" if action.success else "❌"
                    st.markdown(f"{icon} {action.message}")

    # Show output file contents
    st.divider()
    st.subheader("Output Files")
    out_col1, out_col2, out_col3 = st.columns(3)

    import json
    for col, fname, label in [
        (out_col1, "cases.json",        "📁 cases.json"),
        (out_col2, "notifications.json","🔔 notifications.json"),
        (out_col3, "watchlist.json",    "👁 watchlist.json"),
    ]:
        fpath = DATA_DIR / fname
        with col:
            st.markdown(f"**{label}**")
            if fpath.exists():
                data = json.loads(fpath.read_text())
                st.json(data, expanded=False)
            else:
                st.caption("(not generated yet)")
