import json
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

from src.ingestion import (
    load_dataset,
    load_orders_from_buffer,
    load_trades_from_buffer,
    DataReplayer,
)
from src.ingestion.models import OrderEvent
from src.detection import DetectionEngine
from src.triage import TriageEngine
from src.escalation import EscalationEngine
from src.triage.engine import MODEL, _INPUT_PRICE_PER_M, _CACHE_READ_PRICE_PER_M, _OUTPUT_PRICE_PER_M

DATA_DIR = Path(__file__).parent / "data"

_SEV_COLOR     = {"HIGH": "#e74c3c", "MEDIUM": "#e67e22", "LOW": "#27ae60"}
_VERDICT_COLOR = {"ESCALATE": "#e74c3c", "REVIEW": "#e67e22", "DISMISS": "#27ae60"}


def _badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color};color:#fff;padding:3px 10px;'
        f'border-radius:12px;font-size:0.78em;font-weight:700">{text}</span>'
    )


# ── Header ────────────────────────────────────────────────────────────────────
st.title("Trade Surveillance & Alert Triage Engine")
st.caption("Wissen Technology Hackathon 2026  |  Ingest  ->  Detect  ->  Triage  ->  Escalate")
st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Pipeline Controls")

    st.markdown("**Data Source**")
    orders_file = st.file_uploader("Upload orders CSV", type="csv", key="orders_up")
    trades_file = st.file_uploader("Upload trades CSV", type="csv", key="trades_up")

    if orders_file or trades_file:
        missing = []
        if not orders_file:
            missing.append("orders CSV")
        if not trades_file:
            missing.append("trades CSV")
        if missing:
            st.warning(f"Also upload: {', '.join(missing)}")

    if not orders_file and not trades_file:
        st.caption("No files uploaded — sample data will be used.")

    st.divider()
    run = st.button("Run Full Pipeline", type="primary", use_container_width=True)
    st.divider()
    st.markdown("**Claude API**")
    st.markdown("- Model: `claude-sonnet-4-6`")
    st.markdown("- Prompt caching enabled")
    st.markdown("- Structured JSON output")
    st.divider()
    st.markdown("**Detectors**")
    st.markdown("- Layering / Spoofing")
    st.markdown("- Wash Trading")

# ── Landing state ─────────────────────────────────────────────────────────────
if not run:
    st.info("Click **Run Full Pipeline** in the sidebar to start the demo.")
    st.markdown("""
**What does this do?**

This engine runs a four-stage compliance pipeline on simulated trading data:

| Stage | What happens |
|-------|-------------|
| 1 — Ingest | Loads order and trade events, replays them in time order |
| 2 — Detect | Scans for layering and wash-trading patterns, raises alerts |
| 3 — Triage | Sends each alert to Claude for a verdict and confidence score |
| 4 — Escalate | Routes outcomes to compliance cases, notifications, and watchlist |
    """)
    st.stop()

# ── Guard: API key ────────────────────────────────────────────────────────────
if not os.getenv("ANTHROPIC_API_KEY"):
    st.error(
        "ANTHROPIC_API_KEY not found.  \n"
        "Add it to `.env` locally, or to App settings > Secrets on Streamlit Cloud."
    )
    st.stop()

# ═════════════════════════════════════════════════════════════════════════════
# Run the pipeline — use spinner + progress bar (avoids st.status icon bugs)
# ═════════════════════════════════════════════════════════════════════════════
progress  = st.progress(0)
stage_msg = st.empty()

with st.spinner("Running pipeline..."):

    stage_msg.info("Stage 1 / 4  —  Ingesting trade data...")
    using_upload = orders_file and trades_file
    if using_upload:
        orders = load_orders_from_buffer(orders_file)
        trades = load_trades_from_buffer(trades_file)
    else:
        orders, trades = load_dataset(str(DATA_DIR))
    replayer = DataReplayer(orders, trades, speed_factor=1000.0)
    summary  = replayer.summary()
    events   = replayer.get_events()
    progress.progress(25)

    stage_msg.info("Stage 2 / 4  —  Running pattern detection...")
    alerts = DetectionEngine().run(orders, trades)
    progress.progress(50)

    stage_msg.info("Stage 3 / 4  —  AI triage via Claude...")
    triage_results, triage_usage = TriageEngine().triage_all(alerts)
    progress.progress(75)

    stage_msg.info("Stage 4 / 4  —  Triggering escalation workflows...")
    outcomes      = EscalationEngine().escalate_all(alerts, triage_results)
    total_actions = sum(len(o.actions_taken) for o in outcomes)
    progress.progress(100)

stage_msg.empty()
progress.empty()
if using_upload:
    st.success(f"Pipeline complete!  |  Source: uploaded files ({orders_file.name}, {trades_file.name})")
else:
    st.success("Pipeline complete!  |  Source: built-in sample data")

# ── Top-level metrics ─────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Events Processed", len(events))
c2.metric("Alerts Detected",  len(alerts))
c3.metric("Escalated",    sum(1 for r in triage_results if r.verdict == "ESCALATE"))
c4.metric("For Review",   sum(1 for r in triage_results if r.verdict == "REVIEW"))
c5.metric("Actions Fired", total_actions)

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# Tabs
# ═════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs(
    ["Event Replay", "Detected Patterns", "AI Triage", "Escalation"]
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
        f"**Time range:** `{summary['time_range']['start']}`  to  `{summary['time_range']['end']}`"
    )
    st.markdown(f"**Symbols:** {', '.join(f'`{s}`' for s in summary['symbols'])}")

    st.subheader("Event Log")
    rows = []
    for e in events:
        if isinstance(e, OrderEvent):
            rows.append({
                "Timestamp": e.timestamp.strftime("%H:%M:%S.%f")[:-3],
                "Type":   "Order",
                "Symbol": e.symbol,
                "Trader": e.trader_id,
                "Side":   e.side.value,
                "Qty":    int(e.quantity),
                "Price":  e.price,
                "Status": e.status.value,
            })
        else:
            rows.append({
                "Timestamp": e.timestamp.strftime("%H:%M:%S.%f")[:-3],
                "Type":   "Trade",
                "Symbol": e.symbol,
                "Trader": e.buyer_trader_id,
                "Side":   "EXEC",
                "Qty":    int(e.quantity),
                "Price":  e.price,
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
            st.markdown("---")
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

    # ── Token usage & cache savings panel ─────────────────────────────────────
    st.markdown("**API Usage & Cache Savings**")
    u = triage_usage
    tu1, tu2, tu3, tu4 = st.columns(4)
    tu1.metric("API Calls", u["calls"])
    tu2.metric("Input Tokens",  f"{u['input_tokens']:,}")
    tu3.metric("Cache Read Tokens", f"{u['cache_read']:,}")
    tu4.metric("Cache Write Tokens", f"{u['cache_creation']:,}")

    cu1, cu2, cu3, cu4 = st.columns(4)
    cu1.metric("Total Cost (USD)", f"${u['total_usd']:.4f}")
    cu2.metric("Cache Read Cost",  f"${u['cost_read_usd']:.4f}")
    cu3.metric("Cache Write Cost", f"${u['cost_write_usd']:.4f}")
    cu4.metric("Savings from Caching", f"${u['savings_usd']:.4f}",
               delta=f"-${u['savings_usd']:.4f}", delta_color="inverse")

    if u["cache_read"] > 0:
        cache_pct = u["cache_read"] / max(u["cache_read"] + u["input_tokens"] + u["cache_creation"], 1)
        st.progress(min(cache_pct, 1.0), text=f"Cache hit rate: {cache_pct:.0%} of input tokens served from cache")
    st.caption(
        f"Model: `{MODEL}` | Prompt caching enabled (ephemeral) | "
        f"Pricing: input ${_INPUT_PRICE_PER_M}/M, cache read ${_CACHE_READ_PRICE_PER_M}/M, output ${_OUTPUT_PRICE_PER_M}/M"
    )

    st.divider()
    for alert, result in zip(alerts, triage_results):
        verdict_color = _VERDICT_COLOR.get(result.verdict, "#888")
        st.markdown("---")
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
        st.markdown("---")
        st.markdown(
            f"**{alert.pattern_type}** — `{alert.trader_id}` / `{alert.symbol}` &nbsp;"
            + _badge(outcome.verdict, verdict_color),
            unsafe_allow_html=True,
        )
        if not outcome.actions_taken:
            st.markdown("_No actions taken (dismissed)._")
        else:
            for action in outcome.actions_taken:
                icon = "OK" if action.success else "FAIL"
                st.markdown(f"**[{icon}]** {action.message}")

    st.divider()
    st.subheader("Output Files")
    out_col1, out_col2, out_col3 = st.columns(3)

    for col, fname, label in [
        (out_col1, "cases.json",         "cases.json"),
        (out_col2, "notifications.json", "notifications.json"),
        (out_col3, "watchlist.json",     "watchlist.json"),
    ]:
        fpath = DATA_DIR / fname
        with col:
            st.markdown(f"**{label}**")
            if fpath.exists():
                data = json.loads(fpath.read_text())
                st.json(data, expanded=False)
            else:
                st.caption("(not generated yet)")
