# Trade Surveillance & Alert Triage Engine

A financial compliance tool that ingests simulated trade/order data, detects suspicious trading patterns, triages alerts using the Anthropic Claude API, and triggers automated escalation workflows.

Built for the **Wissen Technology Hackathon 2026**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Trade Surveillance Pipeline                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     orders.csv / trades.csv (or uploaded files)   │
│  │   CSV Data   │──────────────────────────┐                        │
│  └──────────────┘                          │                        │
│                                            ▼                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Stage 1: Ingestion                                          │    │
│  │  loader.py → OrderEvent / TradeEvent dataclasses            │    │
│  │  replayer.py → chronological event replay                   │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             │  List[OrderEvent], List[TradeEvent]   │
│                             ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Stage 2: Pattern Detection                                  │    │
│  │                                                              │    │
│  │  ┌──────────────────────┐   ┌─────────────────────────────┐ │    │
│  │  │  LayeringDetector    │   │  WashTradingDetector        │ │    │
│  │  │  • Burst window scan │   │  • Buy/sell pair matching   │ │    │
│  │  │  • Cancel rate check │   │  • Qty + price tolerance    │ │    │
│  │  │  • Baseline compare  │   │  • P&L ≈ 0 verification     │ │    │
│  │  │  • Median cancel ms  │   │                             │ │    │
│  │  └──────────┬───────────┘   └──────────────┬──────────────┘ │    │
│  │             └──────────────┬────────────────┘               │    │
│  │                            │  List[Alert] (ALT-YYYY-NNNN)   │    │
│  └────────────────────────────┼───────────────────────────────-┘    │
│                               │                                      │
│                               ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Stage 3: AI Triage  (Claude claude-sonnet-4-6)              │    │
│  │                                                              │    │
│  │  Cached system prompt ──► cache_control: ephemeral           │    │
│  │  Per-alert user message ──► messages.parse(TriageResult)     │    │
│  │                                                              │    │
│  │  Output: verdict  confidence  false_positive_prob  rationale │    │
│  │          ESCALATE   91%            9%              "..."     │    │
│  │          REVIEW     58%           42%              "..."     │    │
│  └────────────────────────────┬────────────────────────────────┘    │
│                               │  List[TriageResult]                  │
│                               ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Stage 4: Escalation                                         │    │
│  │                                                              │    │
│  │  Verdict × Severity routing matrix:                          │    │
│  │  ESCALATE + HIGH   ──► Case(HIGH) + Urgent notif + WL 72h   │    │
│  │  ESCALATE + MEDIUM ──► Case(MED)  + Urgent notif + WL 48h   │    │
│  │  REVIEW   + any    ──► Case(LOW)  + Review notif             │    │
│  │  DISMISS  + any    ──► (no actions)                          │    │
│  │                                                              │    │
│  │  Output files: cases.json  notifications.json  watchlist.json│    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Detected Patterns

| Pattern | Description |
|---------|-------------|
| **Layering** | Burst of same-side orders placed and rapidly cancelled to move the order book, followed by an opposite-side execution. Includes baseline anomaly comparison (cancel rate vs 30-day baseline, median time-to-cancel) |
| **Wash Trading** | Matched buy/sell pairs by the same trader at near-identical prices, generating artificial volume with zero real P&L |

---

## Project Structure

```
trade_surveillance/
├── app.py                         # Streamlit web UI
├── main.py                        # CLI pipeline entry point
├── requirements.txt
├── .env.example                   # API key template
├── data/
│   ├── orders.csv                 # Sample order events
│   └── trades.csv                 # Sample trade executions
└── src/
    ├── ingestion/
    │   ├── models.py              # OrderEvent, TradeEvent, Alert dataclasses
    │   ├── loader.py              # CSV loader (file path + BytesIO buffer)
    │   └── replayer.py            # Chronological event replay
    ├── detection/
    │   ├── base.py                # BaseDetector interface
    │   ├── layering.py            # Layering detector with baseline comparison
    │   ├── wash_trading.py        # Wash trading detector
    │   ├── utils.py               # Shared alert ID generator (ALT-YYYY-NNNN)
    │   └── engine.py              # Runs all detectors, aggregates alerts
    ├── triage/
    │   ├── schema.py              # Pydantic TriageResult model
    │   ├── prompts.py             # Cached compliance system prompt
    │   └── engine.py              # Claude API triage + token usage tracking
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
2. Click **New app** -> select this repo -> set **Main file path** to `app.py`
3. Open **Advanced settings -> Secrets** and add:
   ```toml
   ANTHROPIC_API_KEY = "your_api_key_here"
   ```
4. Click **Deploy** — your app will be live at a public URL in ~60 seconds

---

## Sample Output

```
=== Pattern Detection ===
  [HIGH]   LAYERING      | TRD001 / AAPL
           ALT-2026-0001 | 14 BUY orders placed within 2000ms, 12 cancelled (86% cancel rate),
           followed by opposite-side fill
           Anomaly vs 30d baseline: +56% cancel rate, median cancel 620ms (-88% vs 5000ms baseline)

  [MED]    WASH_TRADING  | TRD002 / MSFT
           ALT-2026-0002 | 3 matched buy/sell pairs within 30s, total volume 3,000 shares, P&L = 0

=== AI Triage (Claude) ===
  [ESCALATE] LAYERING | TRD001 / AAPL  — Confidence: 87%
  [REVIEW]   WASH_TRADING | TRD002 / MSFT  — Confidence: 58%

  --- Token Usage ---
  API calls       : 2
  Input tokens    : 312
  Cache write     : 1,847  ($0.0069)
  Cache read      : 1,847  ($0.0006)
  Output tokens   : 284    ($0.0043)
  Total cost      : $0.0118
  Cache savings   : $0.0050

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
| Token usage tracking | Per-call + aggregate input/cache/output counts with USD cost breakdown |

