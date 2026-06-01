from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.services.smart_screening.registry import ExecutionMode, get_field_spec
from app.services.smart_screening.schema import ConditionType, SmartCondition, SmartScreeningDSL
from app.services.smart_screening.validator import ValidationIssue, validate_dsl


class ExecutionPlanStep(BaseModel):
    step_id: str
    execution_mode: str
    fields: list[str] = Field(default_factory=list)
    source_collections: list[str] = Field(default_factory=list)
    condition_paths: list[str] = Field(default_factory=list)
    description: str = ""


class ExecutionPlan(BaseModel):
    is_valid: bool
    required_execution_modes: list[str] = Field(default_factory=list)
    referenced_fields: list[str] = Field(default_factory=list)
    source_collections: list[str] = Field(default_factory=list)
    steps: list[ExecutionPlanStep] = Field(default_factory=list)
    issues: list[dict] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)
    needs_text_events: bool = False
    needs_dynamic_price_calc: bool = False
    needs_dynamic_financial_calc: bool = False
    needs_realtime_data: bool = False
    needs_confirmation: bool = False


@dataclass
class _StepAccumulator:
    fields: set[str] = field(default_factory=set)
    source_collections: set[str] = field(default_factory=set)
    condition_paths: list[str] = field(default_factory=list)


def plan_execution(dsl: SmartScreeningDSL | dict) -> ExecutionPlan:
    parsed = dsl if isinstance(dsl, SmartScreeningDSL) else SmartScreeningDSL.model_validate(dsl)
    validation = validate_dsl(parsed)

    by_mode: dict[ExecutionMode, _StepAccumulator] = defaultdict(_StepAccumulator)
    referenced_fields: set[str] = set(validation.referenced_fields)
    source_collections: set[str] = set()

    for idx, condition in enumerate(parsed.conditions):
        _collect_condition_plan(
            condition=condition,
            path=f"conditions[{idx}]",
            by_mode=by_mode,
            referenced_fields=referenced_fields,
            source_collections=source_collections,
        )

    for idx, sort in enumerate(parsed.sort):
        spec = get_field_spec(sort.field)
        if spec is None:
            continue
        referenced_fields.add(spec.name)
        source_collections.add(spec.source_collection)
        for mode in spec.execution_modes:
            by_mode[mode].fields.add(spec.name)
            by_mode[mode].source_collections.add(spec.source_collection)
            by_mode[mode].condition_paths.append(f"sort[{idx}]")

    steps = [
        ExecutionPlanStep(
            step_id=f"step_{idx}",
            execution_mode=mode.value,
            fields=sorted(acc.fields),
            source_collections=sorted(acc.source_collections),
            condition_paths=acc.condition_paths,
            description=_describe_mode(mode),
        )
        for idx, (mode, acc) in enumerate(sorted(by_mode.items(), key=lambda item: item[0].value), start=1)
    ]

    required_modes = sorted({mode.value for mode in validation.required_execution_modes} | {step.execution_mode for step in steps})
    needs_confirmation = any(mode == ExecutionMode.UNSUPPORTED_OR_NEEDS_CONFIRMATION.value for mode in required_modes)

    return ExecutionPlan(
        is_valid=validation.is_valid and not needs_confirmation,
        required_execution_modes=required_modes,
        referenced_fields=sorted(referenced_fields),
        source_collections=sorted(source_collections),
        steps=steps,
        issues=[_issue_to_dict(issue) for issue in validation.issues],
        warnings=[_issue_to_dict(warning) for warning in validation.warnings],
        needs_text_events=ExecutionMode.TEXT_EVENT_SEARCH.value in required_modes,
        needs_dynamic_price_calc=ExecutionMode.DYNAMIC_PRICE_CALC.value in required_modes,
        needs_dynamic_financial_calc=ExecutionMode.DYNAMIC_FINANCIAL_CALC.value in required_modes,
        needs_realtime_data=ExecutionMode.REALTIME_ALERT.value in required_modes,
        needs_confirmation=needs_confirmation,
    )


def _collect_condition_plan(
    condition: SmartCondition,
    path: str,
    by_mode: dict[ExecutionMode, _StepAccumulator],
    referenced_fields: set[str],
    source_collections: set[str],
) -> None:
    if condition.condition_type == ConditionType.GROUP:
        for idx, child in enumerate(condition.children):
            _collect_condition_plan(child, f"{path}.children[{idx}]", by_mode, referenced_fields, source_collections)
        return

    if condition.condition_type == ConditionType.TEXT_EVENT:
        acc = by_mode[ExecutionMode.TEXT_EVENT_SEARCH]
        acc.source_collections.update({"stock_text_events", "stock_news"})
        acc.condition_paths.append(path)
        source_collections.update({"stock_text_events", "stock_news"})
        return

    for field_name in (condition.field, condition.right_field):
        if not field_name:
            continue
        spec = get_field_spec(field_name)
        if spec is None:
            by_mode[ExecutionMode.UNSUPPORTED_OR_NEEDS_CONFIRMATION].condition_paths.append(path)
            continue
        referenced_fields.add(spec.name)
        source_collections.add(spec.source_collection)
        for mode in spec.execution_modes:
            acc = by_mode[mode]
            acc.fields.add(spec.name)
            acc.source_collections.add(spec.source_collection)
            acc.condition_paths.append(path)
            for base_field in spec.required_base_fields:
                base_spec = get_field_spec(base_field)
                if base_spec:
                    acc.fields.add(base_spec.name)
                    acc.source_collections.add(base_spec.source_collection)
                    referenced_fields.add(base_spec.name)
                    source_collections.add(base_spec.source_collection)


def _describe_mode(mode: ExecutionMode) -> str:
    descriptions = {
        ExecutionMode.HISTORICAL_FACTOR: "Read precomputed daily factors and basic stock fields.",
        ExecutionMode.DYNAMIC_PRICE_CALC: "Calculate price-derived fields from historical OHLCV rows if factors are absent.",
        ExecutionMode.DYNAMIC_FINANCIAL_CALC: "Read or calculate financial and valuation fields.",
        ExecutionMode.TEXT_EVENT_SEARCH: "Search announcement, news, research, and event records with as-of protection.",
        ExecutionMode.REALTIME_ALERT: "Use intraday quote fields when the query requires real-time alerts.",
        ExecutionMode.UNSUPPORTED_OR_NEEDS_CONFIRMATION: "The request contains unsupported or ambiguous fields.",
    }
    return descriptions.get(mode, mode.value)


def _issue_to_dict(issue: ValidationIssue) -> dict:
    return {
        "code": issue.code,
        "message": issue.message,
        "path": issue.path,
        "severity": issue.severity,
    }
