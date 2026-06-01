from __future__ import annotations

from typing import Any

from app.services.smart_screening.service import ScreeningCandidate, SmartScreeningResult


async def build_deep_analysis_tasks(result: SmartScreeningResult, *, top_n: int = 3) -> list[dict[str, Any]]:
    tasks = []
    for candidate in result.items[:top_n]:
        tasks.append(_candidate_to_task(candidate))
    return tasks


def _candidate_to_task(candidate: ScreeningCandidate) -> dict[str, Any]:
    return {
        "symbol": candidate.symbol,
        "name": candidate.name,
        "analysts": ["market", "fundamentals", "news"],
        "reason": "智能选股候选股，可进入现有 market/fundamentals/news analyst 深度分析。",
        "context": {
            "score": candidate.score,
            "matched_conditions": candidate.matched_conditions,
            "reasons": candidate.reasons,
            "evidence": [item.model_dump(mode="json", exclude_none=True) for item in candidate.evidence],
        },
    }
