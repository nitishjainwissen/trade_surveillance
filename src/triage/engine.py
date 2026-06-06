import json
import os
from typing import List

import anthropic
from dotenv import load_dotenv

from src.ingestion.models import Alert
from .prompts import SYSTEM_PROMPT
from .schema import TriageResult

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

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


class TriageEngine:
    """Calls Claude to assess each alert and populate verdict fields."""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set. Add it to your .env file.")
        self._client = anthropic.Anthropic(api_key=api_key)

    def triage_alert(self, alert: Alert) -> TriageResult:
        response = self._client.messages.parse(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_CACHED_SYSTEM,
            messages=[{"role": "user", "content": _build_alert_prompt(alert)}],
            output_format=TriageResult,
        )

        result: TriageResult = response.parsed_output

        # Persist triage results back onto the Alert
        alert.triage_verdict = result.verdict
        alert.confidence_score = result.confidence_score
        alert.rationale = result.rationale

        usage = response.usage
        cache_hit = getattr(usage, "cache_read_input_tokens", 0) or 0
        print(
            f"  [Triage] {alert.alert_id[:8]}... | {result.verdict:8s} | "
            f"conf={result.confidence_score:.0%} | "
            f"cache_hit={cache_hit} tokens"
        )
        return result

    def triage_all(self, alerts: List[Alert]) -> List[TriageResult]:
        results = []
        for alert in alerts:
            result = self.triage_alert(alert)
            results.append(result)
        return results
