from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.smart_screening.service import SmartScreeningResult


class ScreeningAuditResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    checked_candidates: int = 0
    checked_evidence: int = 0


def audit_screening_result(result: SmartScreeningResult) -> ScreeningAuditResult:
    issues: list[str] = []
    checked_evidence = 0

    for candidate in result.items:
        if not candidate.symbol:
            issues.append("candidate missing symbol")
        if candidate.matched_conditions and not candidate.evidence:
            issues.append(f"{candidate.symbol} has matched conditions but no evidence")
        for evidence in candidate.evidence:
            checked_evidence += 1
            if not evidence.source:
                issues.append(f"{candidate.symbol} evidence missing source")
            if evidence.evidence_type == "text_event" and not evidence.event_date:
                issues.append(f"{candidate.symbol} text evidence missing event_date")
            if evidence.evidence_type != "text_event" and not evidence.field:
                issues.append(f"{candidate.symbol} factor evidence missing field")

    return ScreeningAuditResult(
        passed=not issues,
        issues=issues,
        checked_candidates=len(result.items),
        checked_evidence=checked_evidence,
    )
