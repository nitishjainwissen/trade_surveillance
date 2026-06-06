# Trade Surveillance & Alert Triage Engine

A financial compliance tool that ingests simulated trade/order data, detects suspicious trading patterns, triages alerts using the Anthropic Claude API, and triggers automated escalation workflows.

Built for the **Wissen Technology Hackathon 2026**.

---

## Architecture

```
Trade Data (CSV)
      │
      ▼
[Ingestion]      Load & replay order/trade events in chronological order
      │
      ▼
[Detection]      Rule-based pattern detection → Alert objects with severity
      │
      ▼
[AI Triage]      Claude API → ESCALATE / REVIEW / DISMISS + confidence score
      │
      ▼
[Escalation]     Conditional workflows → compliance case, notification, watchlist
```

---

## Detected Patterns

| Pattern | Description |
|---------|-------------|
| **Layering** | Burst of same-side orders placed and rapidly cancelled to move the order book, followed by an opposite-side execution |
| **Wash Trading** | Matched buy/sell pairs by the same trader at near-identical prices, generating artificial volume with zero real P&L |

---

## Project Structure

```
trade_surveillance/
├── main.py                        # Pipeline entry point
├── requirements.txt
├── .env.example                   # API key template
├── data/
│   ├── orders.csv                 # Sample order events
│   └── trades.csv                 # Sample trade executions
└── src/
    ├── ingestion/
    │   ├── models.py              # OrderEvent, TradeEvent, Alert dataclasses
    │   ├── loader.py              # CSV loader
    │   └── replayer.py            # Chronological event replay
    ├── detection/
    │   ├── base.py                # BaseDetector interface
    │   ├── layering.py            # Layering detector
    │   ├── wash_trading.py        # Wash trading detector
    │   └── engine.py              # Runs all detectors, aggregates alerts
    ├── triage/
    │   ├── schema.py              # Pydantic TriageResult model
    │   ├── prompts.py             # Cached compliance system prompt
    │   └── engine.py              # Claude API triage calls
    └── escalation/
        ├── actions.py             # Case creation, notifications, watchlist
        └── engine.py              # Verdict × severity routing matrix
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/nitishjainwissen/trade_surveillance.git
cd trade_surveillance
pip install -r requirements.txt
```

### 2. Configure your API key

```bash
cp .env.example .env
# Edit .env and set your Anthropic API key:
# ANTHROPIC_API_KEY=your_api_key_here
```

### 3. Run the full pipeline

```bash
python main.py
```

### 3b. Run the Streamlit web UI (local)

```bash
streamlit run app.py
```

---

## Deploy to Streamlit Cloud (free)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app** → select this repo → set **Main file path** to `app.py`
3. Open **Advanced settings → Secrets** and add:
   ```toml
   ANTHROPIC_API_KEY = "your_api_key_here"
   ```
4. Click **Deploy** — your app will be live at a public URL in ~60 seconds

---

## Sample Output

```
=== Pattern Detection ===
  [HIGH]   LAYERING      | TRD001 / AAPL
           14 BUY orders placed within 2000ms, 12 cancelled (86% cancel rate),
           followed by opposite-side fill

  [MED]    WASH_TRADING  | TRD002 / MSFT
           3 matched buy/sell pairs within 30s, total volume 3,000 shares, P&L ≈ 0

=== AI Triage (Claude) ===
  [ESCALATE] LAYERING | TRD001 / AAPL  — Confidence: 87%
  [REVIEW]   WASH_TRADING | TRD002 / MSFT  — Confidence: 58%

=== Automated Escalation ===
  [OK] Case CASE-06C655 opened [HIGH] -> compliance-team
  [OK] Notification sent to #compliance-urgent
  [OK] Trader TRD001 added to watchlist (72h monitoring)

  [OK] Case CASE-F132A8 opened [LOW] -> compliance-team
  [OK] Notification sent to #compliance-review
```

---

## Escalation Routing

| Verdict | Severity | Actions |
|---------|----------|---------|
| ESCALATE | HIGH | Compliance case (HIGH) + urgent notification + watchlist 72h |
| ESCALATE | MEDIUM | Compliance case (MEDIUM) + urgent notification + watchlist 48h |
| REVIEW | any | Compliance case (LOW) + review-channel notification |
| DISMISS | any | No actions |

Escalation outputs are written to `data/cases.json`, `data/notifications.json`, and `data/watchlist.json`. In production these actions map to Jira, Slack, and a risk management system respectively.

---

## Claude API Features Used

| Feature | Where |
|---------|-------|
| `claude-sonnet-4-6` model | `src/triage/engine.py` |
| Prompt caching (`cache_control: ephemeral`) | System prompt cached across all triage calls |
| Structured JSON output (`messages.parse`) | Pydantic `TriageResult` schema enforced on every response |

---

## Evaluation Criteria Coverage

| Criterion | Implementation |
|-----------|---------------|
| AI Triage Quality (25%) | Claude verdict with confidence score, false-positive probability, rationale, and recommended action |
| Pattern Detection (20%) | Layering + wash trading detectors with severity classification |
| Automation & Workflow (20%) | 3 escalation actions routed by verdict × severity |
| Working Demo (20%) | Single `python main.py` runs the complete ingest → detect → triage → escalate flow |
| API Efficiency (10%) | Prompt caching on stable system prompt; `max_tokens=1024` per triage call |
| Docs/README (5%) | This file |
