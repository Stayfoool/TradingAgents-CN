from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.services.smart_screening.planner import ExecutionPlan, plan_execution
from app.services.smart_screening.repository import InMemorySmartScreeningRepository, SmartScreeningRepository
from app.services.smart_screening.schema import (
    ComparisonOperator,
    ConditionType,
    LogicalOperator,
    RankOperator,
    SmartCondition,
    SmartScreeningDSL,
    SortDirection,
)

PRICE_DERIVED_FIELDS = {"ma5", "ma10", "ma20", "return_5d", "return_10d", "return_20d", "pct_chg"}


class ScreeningEvidence(BaseModel):
    evidence_type: str
    source: str
    field: str | None = None
    value: Any = None
    condition: str | None = None
    title: str | None = None
    event_date: str | None = None
    summary: str | None = None


class ScreeningCandidate(BaseModel):
    symbol: str
    name: str | None = None
    market: str | None = None
    industry: str | None = None
    score: float = 0
    matched_conditions: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    evidence: list[ScreeningEvidence] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class SmartScreeningResult(BaseModel):
    total: int
    items: list[ScreeningCandidate]
    plan: ExecutionPlan
    data_gaps: list[str] = Field(default_factory=list)
    audit: dict[str, Any] = Field(default_factory=dict)


@dataclass
class _EvaluationContext:
    rank_sets: dict[str, set[str]]
    text_events_by_symbol: dict[str, list[dict[str, Any]]]
    condition_evidence: dict[str, list[ScreeningEvidence]] = field(default_factory=dict)
    condition_reasons: dict[str, list[str]] = field(default_factory=dict)


async def run_stock_screening_by_dsl(
    dsl: SmartScreeningDSL | dict,
    repository: SmartScreeningRepository | None = None,
) -> SmartScreeningResult:
    parsed = dsl if isinstance(dsl, SmartScreeningDSL) else SmartScreeningDSL.model_validate(dsl)
    plan = plan_execution(parsed)
    if not plan.is_valid:
        return SmartScreeningResult(
            total=0,
            items=[],
            plan=plan,
            data_gaps=["DSL validation failed; execution was skipped."],
            audit={"is_auditable": False, "issues": plan.issues},
        )

    repo = repository or InMemorySmartScreeningRepository()
    rows = await repo.load_factor_rows(market=parsed.market, as_of=parsed.as_of, universe=parsed.universe)
    if _needs_dynamic_price_enrichment(parsed, rows):
        price_history = await repo.load_price_history(market=parsed.market, as_of=parsed.as_of, universe=parsed.universe)
        rows = _merge_dynamic_price_fields(rows, price_history)
    text_events = await repo.load_text_events(market=parsed.market, as_of=parsed.as_of, universe=parsed.universe)
    text_events_by_symbol = _group_events_by_symbol(text_events)
    rank_sets = _build_rank_sets(rows, parsed.conditions)
    ctx = _EvaluationContext(rank_sets=rank_sets, text_events_by_symbol=text_events_by_symbol)

    candidates: list[ScreeningCandidate] = []
    for row in rows:
        symbol = _symbol_of(row)
        if not symbol:
            continue
        passed, matched_paths = _evaluate_conditions(parsed.conditions, parsed.condition_logic, row, ctx, parsed.as_of)
        if not passed:
            continue
        evidence = _dedupe_evidence([ev for path in matched_paths for ev in ctx.condition_evidence.get(path, [])])
        reasons = _dedupe_strings([reason for path in matched_paths for reason in ctx.condition_reasons.get(path, [])])
        candidates.append(
            ScreeningCandidate(
                symbol=symbol,
                name=row.get("name"),
                market=row.get("market"),
                industry=row.get("industry"),
                score=float(len(matched_paths) + min(len(evidence), 5) * 0.2),
                matched_conditions=matched_paths,
                reasons=reasons,
                evidence=evidence,
                data=_public_row_data(row),
            )
        )

    candidates = _sort_candidates(candidates, parsed)
    total = len(candidates)
    page = candidates[parsed.offset : parsed.offset + parsed.limit]

    return SmartScreeningResult(
        total=total,
        items=page,
        plan=plan,
        data_gaps=_collect_data_gaps(parsed, rows),
        audit={
            "is_auditable": True,
            "dsl": parsed.to_audit_dict(),
            "rows_loaded": len(rows),
            "text_events_loaded": len(text_events),
            "returned": len(page),
            "evidence_count": sum(len(candidate.evidence) for candidate in page),
        },
    )


def _evaluate_conditions(
    conditions: list[SmartCondition],
    logic: LogicalOperator,
    row: dict[str, Any],
    ctx: _EvaluationContext,
    as_of: date | None,
) -> tuple[bool, list[str]]:
    if not conditions:
        return True, []

    outcomes: list[tuple[bool, list[str]]] = []
    for idx, condition in enumerate(conditions):
        outcomes.append(_evaluate_condition(condition, f"conditions[{idx}]", row, ctx, as_of))

    if logic == LogicalOperator.OR:
        passed_paths = [path for passed, paths in outcomes if passed for path in paths]
        return bool(passed_paths), passed_paths

    all_passed = all(passed for passed, _ in outcomes)
    if not all_passed:
        return False, []
    return True, [path for _, paths in outcomes for path in paths]


def _evaluate_condition(
    condition: SmartCondition,
    path: str,
    row: dict[str, Any],
    ctx: _EvaluationContext,
    as_of: date | None,
) -> tuple[bool, list[str]]:
    if condition.condition_type == ConditionType.GROUP:
        return _evaluate_conditions(condition.children, condition.logic or LogicalOperator.AND, row, ctx, as_of)

    if condition.condition_type == ConditionType.TEXT_EVENT:
        events = _matching_text_events(condition, ctx.text_events_by_symbol.get(_symbol_of(row), []), as_of)
        if not events:
            return False, []
        ctx.condition_evidence[path] = [
            ScreeningEvidence(
                evidence_type="text_event",
                source=str(event.get("source") or "stock_text_events"),
                field="stock_text_events",
                value=event.get("event_type"),
                condition=path,
                title=event.get("title"),
                event_date=str(event.get("event_date") or ""),
                summary=event.get("summary"),
            )
            for event in events[:3]
        ]
        ctx.condition_reasons[path] = [f"命中文本事件：{event.get('title') or event.get('event_type')}" for event in events[:3]]
        return True, [path]

    if condition.condition_type == ConditionType.RANK:
        key = _rank_key(condition)
        passed = _symbol_of(row) in ctx.rank_sets.get(key, set())
        if passed:
            _add_field_evidence(condition, path, row, ctx, "rank")
        return passed, [path] if passed else []

    if condition.condition_type == ConditionType.FIELD_COMPARE:
        left = _as_comparable(row.get(condition.field or ""))
        right = _as_comparable(row.get(condition.right_field or ""))
        passed = _compare_values(left, condition.operator, right)
        if passed:
            _add_field_evidence(condition, path, row, ctx, "field_compare", right_field=condition.right_field)
        return passed, [path] if passed else []

    passed = _compare_values(row.get(condition.field or ""), condition.operator, condition.value)
    if passed:
        _add_field_evidence(condition, path, row, ctx, "value")
    return passed, [path] if passed else []


def _build_rank_sets(rows: list[dict[str, Any]], conditions: list[SmartCondition]) -> dict[str, set[str]]:
    rank_conditions = _flatten_rank_conditions(conditions)
    result: dict[str, set[str]] = {}
    for condition in rank_conditions:
        field = condition.field or ""
        ranked = sorted(
            (row for row in rows if _is_number(row.get(field)) and _symbol_of(row)),
            key=lambda row: float(row[field]),
            reverse=condition.rank_operator in {RankOperator.TOP_N, RankOperator.TOP_PERCENTILE},
        )
        if not ranked:
            result[_rank_key(condition)] = set()
            continue
        if condition.rank_operator in {RankOperator.TOP_N, RankOperator.BOTTOM_N}:
            count = int(condition.threshold or 0)
        else:
            count = max(1, math.ceil(len(ranked) * float(condition.threshold or 0) / 100))
        result[_rank_key(condition)] = {_symbol_of(row) for row in ranked[:count]}
    return result


def _needs_dynamic_price_enrichment(dsl: SmartScreeningDSL, rows: list[dict[str, Any]]) -> bool:
    fields = _referenced_condition_fields(dsl.conditions) | {sort.field for sort in dsl.sort}
    needed = fields & PRICE_DERIVED_FIELDS
    return bool(needed and any(all(row.get(field) is None for row in rows) for field in needed))


def _referenced_condition_fields(conditions: list[SmartCondition]) -> set[str]:
    fields: set[str] = set()
    for condition in conditions:
        if condition.condition_type == ConditionType.GROUP:
            fields.update(_referenced_condition_fields(condition.children))
            continue
        if condition.field:
            fields.add(condition.field)
        if condition.right_field:
            fields.add(condition.right_field)
    return fields


def _merge_dynamic_price_fields(rows: list[dict[str, Any]], price_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    history_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for item in price_history:
        symbol = _symbol_of(item)
        if symbol:
            history_by_symbol.setdefault(symbol, []).append(item)

    latest_by_symbol = {_symbol_of(row): row.copy() for row in rows if _symbol_of(row)}
    for symbol, history in history_by_symbol.items():
        ordered = sorted(history, key=lambda item: str(item.get("date") or ""))
        if not ordered:
            continue
        latest = latest_by_symbol.get(symbol, ordered[-1].copy())
        latest.update({key: latest.get(key, value) for key, value in ordered[-1].items()})
        _add_dynamic_price_fields(latest, ordered)
        latest_by_symbol[symbol] = latest

    return list(latest_by_symbol.values())


def _add_dynamic_price_fields(row: dict[str, Any], history: list[dict[str, Any]]) -> None:
    closes = [_as_number(item.get("close")) for item in history if _is_number(item.get("close"))]
    if not closes:
        return
    _set_if_missing(row, "close", closes[-1])
    for length in (5, 10, 20):
        if len(closes) >= length:
            _set_if_missing(row, f"ma{length}", round(sum(closes[-length:]) / length, 4))
        if len(closes) > length:
            base = closes[-(length + 1)]
            if base:
                _set_if_missing(row, f"return_{length}d", round((closes[-1] / base - 1) * 100, 4))
    if len(closes) >= 2:
        base = closes[-2]
        if base:
            _set_if_missing(row, "pct_chg", round((closes[-1] / base - 1) * 100, 4))


def _set_if_missing(row: dict[str, Any], field: str, value: Any) -> None:
    if row.get(field) is None:
        row[field] = value


def _flatten_rank_conditions(conditions: list[SmartCondition]) -> list[SmartCondition]:
    rank_conditions: list[SmartCondition] = []
    for condition in conditions:
        if condition.condition_type == ConditionType.GROUP:
            rank_conditions.extend(_flatten_rank_conditions(condition.children))
        elif condition.condition_type == ConditionType.RANK:
            rank_conditions.append(condition)
    return rank_conditions


def _matching_text_events(condition: SmartCondition, events: list[dict[str, Any]], as_of: date | None) -> list[dict[str, Any]]:
    matches = []
    for event in events:
        event_date = _parse_optional_date(event.get("event_date"))
        if as_of and event_date and event_date > as_of:
            continue
        if condition.date_range:
            if condition.date_range.start and event_date and event_date < condition.date_range.start:
                continue
            if condition.date_range.end and event_date and event_date > condition.date_range.end:
                continue
        if condition.event_types and str(event.get("event_type")) not in set(condition.event_types):
            continue
        if condition.sources and str(event.get("source")) not in set(condition.sources):
            continue
        if condition.sentiment and str(event.get("sentiment")) != condition.sentiment:
            continue
        haystack = f"{event.get('title') or ''}\n{event.get('summary') or ''}".lower()
        if condition.keywords and not any(keyword.lower() in haystack for keyword in condition.keywords):
            continue
        matches.append(event)
    return matches


def _compare_values(left: Any, operator: ComparisonOperator | None, right: Any) -> bool:
    if operator is None:
        return False
    if operator == ComparisonOperator.EXISTS:
        return left is not None and left != ""
    if operator == ComparisonOperator.BETWEEN:
        return isinstance(right, list) and len(right) == 2 and _as_number(right[0]) <= _as_number(left) <= _as_number(right[1])
    if operator == ComparisonOperator.IN:
        return isinstance(right, list) and left in right
    if operator == ComparisonOperator.NOT_IN:
        return isinstance(right, list) and left not in right
    if operator == ComparisonOperator.CONTAINS:
        return str(right).lower() in str(left).lower()
    if operator == ComparisonOperator.EQ:
        return left == right
    if operator == ComparisonOperator.NE:
        return left != right

    left_cmp = _as_comparable(left)
    right_cmp = _as_comparable(right)
    if operator == ComparisonOperator.GT:
        return left_cmp > right_cmp
    if operator == ComparisonOperator.GTE:
        return left_cmp >= right_cmp
    if operator == ComparisonOperator.LT:
        return left_cmp < right_cmp
    if operator == ComparisonOperator.LTE:
        return left_cmp <= right_cmp
    return False


def _add_field_evidence(
    condition: SmartCondition,
    path: str,
    row: dict[str, Any],
    ctx: _EvaluationContext,
    evidence_type: str,
    right_field: str | None = None,
) -> None:
    field = condition.field or ""
    right_value = row.get(right_field) if right_field else condition.value
    ctx.condition_evidence[path] = [
        ScreeningEvidence(
            evidence_type=evidence_type,
            source="stock_daily_factors",
            field=field,
            value=row.get(field),
            condition=path,
            summary=f"{field}={row.get(field)}, threshold={right_value}",
        )
    ]
    ctx.condition_reasons[path] = [f"{field} 命中条件，当前值 {row.get(field)}"]


def _sort_candidates(candidates: list[ScreeningCandidate], dsl: SmartScreeningDSL) -> list[ScreeningCandidate]:
    sorted_candidates = candidates
    for sort in reversed(dsl.sort):
        sorted_candidates = sorted(
            sorted_candidates,
            key=lambda candidate: _sort_value(candidate.data.get(sort.field)),
            reverse=sort.direction == SortDirection.DESC,
        )
    if not dsl.sort:
        sorted_candidates = sorted(sorted_candidates, key=lambda candidate: candidate.score, reverse=True)
    return sorted_candidates


def _collect_data_gaps(dsl: SmartScreeningDSL, rows: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    for sort in dsl.sort:
        if not any(row.get(sort.field) is not None for row in rows):
            gaps.append(f"sort field has no data: {sort.field}")
    return gaps


def _public_row_data(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _group_events_by_symbol(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(_symbol_of(event), []).append(event)
    return grouped


def _rank_key(condition: SmartCondition) -> str:
    return f"{condition.field}:{condition.rank_operator}:{condition.threshold}"


def _symbol_of(row: dict[str, Any]) -> str:
    return str(row.get("symbol") or row.get("code") or "").strip()


def _as_number(value: Any) -> float:
    if value is None or value == "":
        return float("nan")
    return float(value)


def _as_comparable(value: Any) -> Any:
    try:
        return _as_number(value)
    except (TypeError, ValueError):
        return value


def _is_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return not math.isnan(number)


def _sort_value(value: Any) -> Any:
    if value is None:
        return float("-inf")
    return _as_comparable(value)


def _parse_optional_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _dedupe_evidence(values: list[ScreeningEvidence]) -> list[ScreeningEvidence]:
    seen: set[tuple[str, str | None, str | None, str | None]] = set()
    result: list[ScreeningEvidence] = []
    for item in values:
        key = (item.evidence_type, item.source, item.field, item.title)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
