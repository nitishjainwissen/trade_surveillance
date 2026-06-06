from typing import Literal, List
from pydantic import BaseModel, Field


class TriageResult(BaseModel):
    verdict: Literal["ESCALATE", "REVIEW", "DISMISS"]
    confidence_score: float = Field(ge=0.0, le=1.0, description="0-1 probability of genuine misconduct")
    false_positive_probability: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(description="Human-readable explanation of the decision")
    recommended_action: str = Field(description="Specific next step for the compliance team")
    key_risk_factors: List[str] = Field(description="Top reasons supporting the verdict")
