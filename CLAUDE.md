# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Wissen Technology Hackathon 2026** — Trade Surveillance & Alert Triage Engine

A financial compliance tool that ingests simulated trade/order data, detects suspicious trading patterns, uses the Anthropic Claude API to triage alerts (genuine misconduct vs. false positive), and triggers automated escalation workflows.

## Four Core Tasks

| Task | Description |
|------|-------------|
| 1. Data Ingestion | Pipeline to load and replay order/trade event data |
| 2. Pattern Detection | Detect ≥2 manipulation types (e.g., layering, spoofing) with severity classification |
| 3. AI Triage | Claude API call per alert → verdict (ESCALATE/REVIEW/DISMISS), confidence score, human-readable rationale |
| 4. Escalation Workflows | ≥2 downstream actions based on severity+confidence (e.g., Jira case, Slack alert, watchlist update) |

## Architecture

```
Trade Data (CSV/stream)
        │
        ▼
[Ingestion Layer]  ← Task 1: load datasets, replay simulation
        │
        ▼
[Pattern Detector] ← Task 2: rule/ML-based anomaly detection → Alert objects
        │
        ▼
[AI Triage Engine] ← Task 3: Claude API → verdict + confidence + rationale
        │
        ▼
[Escalation Engine] ← Task 4: conditional workflows (Jira, Slack, watchlist)
```

**Alert lifecycle example**: 14 large buy orders placed, 12 cancelled within 800ms → layering pattern detected → Claude triages at 91% confidence → ESCALATE → Jira case created + Slack notification + trader flagged for 72h monitoring.

## Evaluation Weights

- AI Triage Quality: 25% — Claude verdict accuracy, confidence scores, reasoning quality
- Pattern Detection: 20% — coverage, precision, false-positive suppression
- Automation & Workflow: 20% — post-triage escalation effectiveness
- Working Demo: 20% — live end-to-end replay (ingest → detect → triage → escalate)
- API Efficiency: 10% — minimal/purposeful Claude API calls, token cost awareness
- Docs/README: 5%

## Claude API Usage Guidelines

- Use prompt caching for repeated system prompts (compliance context, pattern definitions)
- Batch non-urgent alerts where possible to reduce API calls
- Structure prompts to return structured JSON (verdict, confidence, rationale, recommended_action)
- Default to `claude-sonnet-4-6` for triage; consider `claude-haiku-4-5-20251001` for high-volume pre-filtering
- The `claude-api` skill is available — invoke it for any Anthropic SDK work

## Key Domain Concepts

- **Layering/Spoofing**: Place large orders to move price, cancel before execution
- **Wash Trading**: Buy and sell to self to create artificial volume
- **Momentum Ignition**: Rapid small trades to trigger other algorithms
- **Alert Severity**: HIGH / MEDIUM / LOW based on pattern confidence and trade size
- **False Positive Rate**: Primary metric for triage quality — most real alerts are false positives
