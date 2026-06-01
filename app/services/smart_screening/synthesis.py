from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.smart_screening.service import SmartScreeningResult


class ScreeningSynthesis(BaseModel):
    summary: str
    top_symbols: list[str] = Field(default_factory=list)
    key_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


def synthesize_screening_result(result: SmartScreeningResult) -> ScreeningSynthesis:
    top = result.items[:5]
    key_reasons: list[str] = []
    for candidate in top:
        key_reasons.extend(candidate.reasons[:2])

    if not result.items:
        summary = "本次智能选股没有返回候选股。"
    else:
        summary = f"本次智能选股返回 {result.total} 只候选股，前 {len(top)} 只具备可追溯证据。"

    risks = []
    if result.data_gaps:
        risks.append("存在数据缺口，需复核缺失字段。")
    if any(not candidate.evidence for candidate in result.items):
        risks.append("部分候选股缺少证据链，不能直接进入交易决策。")

    return ScreeningSynthesis(
        summary=summary,
        top_symbols=[candidate.symbol for candidate in top],
        key_reasons=list(dict.fromkeys(key_reasons))[:8],
        risks=risks,
    )
