import os
from typing import Dict, List, Tuple

import anthropic
from dotenv import load_dotenv

from src.ingestion.models import Alert
from .prompts import SYSTEM_PROMPT
from .schema import TriageResult

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

# Sonnet 4-6 pricing per million tokens
_INPUT_PRICE_PER_M  = 3.00
_CACHE_READ_PRICE_PER_M = 0.30   # 90% cheaper than regular input
_CACHE_WRITE_PRICE_PER_M = 3.75  # 25% more than regular input on first write
_OUTPUT_PRICE_PER_M = 15.00

# System prompt block with prompt caching — stable across all triage calls
_CACHED_SYSTEM = [
    {
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }
]


def _build_alert_prompt(alert: Alert) -> str:
    evidence_lines = "\n".join(f"  - {k}: {v}" for k, v in alert.evidence.items())
    return f"""Please triage the following trade surveillance alert.

## Alert Details
- Alert ID    : {alert.alert_id}
- Pattern     : {alert.pattern_type}
- Severity    : {alert.severity}
- Trader      : {alert.trader_id}
- Symbol      : {alert.symbol}
- Timestamp   : {alert.timestamp.isoformat()}

## Description
{alert.description}

## Evidence
{evidence_lines}

## Order IDs involved
{', '.join(alert.order_ids) if alert.order_ids else 'N/A'}

Analyse this alert and return your triage verdict as JSON."""


def _compute_cost(input_tokens: int, cache_creation: int, cache_read: int, output_tokens: int) -> Dict[str, float]:
    """Return USD cost breakdown for a single API call."""
    cost_input  = input_tokens    * _INPUT_PRICE_PER_M  / 1_000_000
    cost_write  = cache_creation  * _CACHE_WRITE_PRICE_PER_M / 1_000_000
    cost_read   = cache_read      * _CACHE_READ_PRICE_PER_M  / 1_000_000
    cost_output = output_tokens   * _OUTPUT_PRICE_PER_M / 1_000_000
    # What those cache_read tokens would have cost at full input price
    savings     = cache_read      * (_INPUT_PRICE_PER_M - _CACHE_READ_PRICE_PER_M) / 1_000_000
    return {
        "cost_input_usd":   round(cost_input, 6),
        "cost_write_usd":   round(cost_write, 6),
        "cost_read_usd":    round(cost_read, 6),
        "cost_output_usd":  round(cost_output, 6),
        "total_usd":        round(cost_input + cost_write + cost_read + cost_output, 6),
        "savings_usd":      round(savings, 6),
    }


class TriageEngine:
    """Calls Claude to assess each alert and populate verdict fields."""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set. Add it to your .env file.")
        self._client = anthropic.Anthropic(api_key=api_key)

    def triage_alert(self, alert: Alert) -> Tuple[TriageResult, Dict]:
        response = self._client.messages.parse(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_CACHED_SYSTEM,
            messages=[{"role": "user", "content": _build_alert_prompt(alert)}],
            output_format=TriageResult,
        )

        result: TriageResult = response.parsed_output

        alert.triage_verdict = result.verdict
        alert.confidence_score = result.confidence_score
        alert.rationale = result.rationale

        usage = response.usage
        input_tokens    = getattr(usage, "input_tokens", 0) or 0
        cache_creation  = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read      = getattr(usage, "cache_read_input_tokens", 0) or 0
        output_tokens   = getattr(usage, "output_tokens", 0) or 0

        cost = _compute_cost(input_tokens, cache_creation, cache_read, output_tokens)
        print(
            f"  [Triage] {alert.alert_id[:8]}... | {result.verdict:8s} | "
            f"conf={result.confidence_score:.0%} | "
            f"cache_read={cache_read} tok | savings=${cost['savings_usd']:.4f}"
        )

        usage_stats = {
            "input_tokens":   input_tokens,
            "cache_creation": cache_creation,
            "cache_read":     cache_read,
            "output_tokens":  output_tokens,
            **cost,
        }
        return result, usage_stats

    def triage_all(self, alerts: List[Alert]) -> Tuple[List[TriageResult], Dict]:
        results = []
        totals: Dict = {
            "calls": 0,
            "input_tokens": 0, "cache_creation": 0, "cache_read": 0, "output_tokens": 0,
            "cost_input_usd": 0, "cost_write_usd": 0, "cost_read_usd": 0,
            "cost_output_usd": 0, "total_usd": 0, "savings_usd": 0,
        }
        for alert in alerts:
            result, usage = self.triage_alert(alert)
            results.append(result)
            totals["calls"] += 1
            for k in ("input_tokens", "cache_creation", "cache_read", "output_tokens",
                      "cost_input_usd", "cost_write_usd", "cost_read_usd",
                      "cost_output_usd", "total_usd", "savings_usd"):
                totals[k] = round(totals[k] + usage[k], 6)
        return results, totals
