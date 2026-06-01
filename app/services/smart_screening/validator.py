from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from app.services.smart_screening.registry import (
    ExecutionMode,
    FieldDataType,
    FieldSpec,
    get_field_spec,
    normalize_field_name,
)
from app.services.smart_screening.schema import (
    ComparisonOperator,
    ConditionType,
    RankOperator,
    SmartCondition,
    SmartScreeningDSL,
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str
    severity: str = "error"


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    referenced_fields: list[str] = field(default_factory=list)
    required_execution_modes: list[ExecutionMode] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "issues": [issue.__dict__ for issue in self.issues],
            "warnings": [warning.__dict__ for warning in self.warnings],
            "referenced_fields": self.referenced_fields,
            "required_execution_modes": [mode.value for mode in self.required_execution_modes],
        }


class SmartScreeningDSLValidator:
    def validate(self, dsl: SmartScreeningDSL | dict) -> ValidationResult:
        try:
            parsed = dsl if isinstance(dsl, SmartScreeningDSL) else SmartScreeningDSL.model_validate(dsl)
        except ValidationError as exc:
            return ValidationResult(
                is_valid=False,
                issues=[
                    ValidationIssue(
                        code="schema_error",
                        message=error.get("msg", "invalid DSL schema"),
                        path=".".join(str(part) for part in error.get("loc", ())),
                    )
                    for error in exc.errors()
                ],
            )

        issues: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        referenced_fields: list[str] = []
        execution_modes: list[ExecutionMode] = []

        if not parsed.conditions:
            warnings.append(
                ValidationIssue(
                    code="empty_conditions",
                    message="DSL has no conditions; screening will only apply universe and sort.",
                    path="conditions",
                    severity="warning",
                )
            )

        for idx, condition in enumerate(parsed.conditions):
            self._validate_condition(
                condition=condition,
                path=f"conditions[{idx}]",
                as_of=parsed.as_of,
                issues=issues,
                referenced_fields=referenced_fields,
                execution_modes=execution_modes,
            )

        for idx, sort in enumerate(parsed.sort):
            spec = get_field_spec(sort.field)
            if spec is None:
                issues.append(
                    ValidationIssue(
                        code="unknown_sort_field",
                        message=f"Unknown sort field: {sort.field}",
                        path=f"sort[{idx}].field",
                    )
                )
            else:
                self._add_field(spec, referenced_fields, execution_modes)

        return ValidationResult(
            is_valid=not issues,
            issues=issues,
            warnings=warnings,
            referenced_fields=sorted(set(referenced_fields)),
            required_execution_modes=sorted(set(execution_modes), key=lambda mode: mode.value),
        )

    def _validate_condition(
        self,
        condition: SmartCondition,
        path: str,
        as_of,
        issues: list[ValidationIssue],
        referenced_fields: list[str],
        execution_modes: list[ExecutionMode],
    ) -> None:
        if condition.condition_type == ConditionType.GROUP:
            for idx, child in enumerate(condition.children):
                self._validate_condition(
                    condition=child,
                    path=f"{path}.children[{idx}]",
                    as_of=as_of,
                    issues=issues,
                    referenced_fields=referenced_fields,
                    execution_modes=execution_modes,
                )
            return

        if condition.condition_type == ConditionType.TEXT_EVENT:
            self._validate_text_event(condition, path, as_of, issues, execution_modes)
            return

        field_spec = self._require_field(condition.field, f"{path}.field", issues)
        if field_spec is None:
            return

        self._add_field(field_spec, referenced_fields, execution_modes)

        if condition.condition_type == ConditionType.VALUE:
            self._validate_value_condition(condition, field_spec, path, issues)
            return

        if condition.condition_type == ConditionType.FIELD_COMPARE:
            right_spec = self._require_field(condition.right_field, f"{path}.right_field", issues)
            if right_spec is None:
                return
            self._add_field(right_spec, referenced_fields, execution_modes)
            self._validate_field_compare(condition, field_spec, right_spec, path, issues)
            return

        if condition.condition_type == ConditionType.RANK:
            self._validate_rank_condition(condition, field_spec, path, issues)

    def _validate_text_event(
        self,
        condition: SmartCondition,
        path: str,
        as_of,
        issues: list[ValidationIssue],
        execution_modes: list[ExecutionMode],
    ) -> None:
        self._add_execution_mode(ExecutionMode.TEXT_EVENT_SEARCH, execution_modes)
        if condition.date_range:
            if condition.date_range.start and condition.date_range.end:
                if condition.date_range.start > condition.date_range.end:
                    issues.append(
                        ValidationIssue(
                            code="invalid_date_range",
                            message="date_range.start must be <= date_range.end",
                            path=f"{path}.date_range",
                        )
                    )
            if as_of and condition.date_range.end and condition.date_range.end > as_of:
                issues.append(
                    ValidationIssue(
                        code="future_text_event",
                        message="text_event date_range.end cannot be later than as_of",
                        path=f"{path}.date_range.end",
                    )
                )
            if as_of and condition.date_range.start and condition.date_range.start > as_of:
                issues.append(
                    ValidationIssue(
                        code="future_text_event",
                        message="text_event date_range.start cannot be later than as_of",
                        path=f"{path}.date_range.start",
                    )
                )

    def _validate_value_condition(
        self,
        condition: SmartCondition,
        field_spec: FieldSpec,
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        if condition.operator not in field_spec.supported_operators:
            issues.append(
                ValidationIssue(
                    code="unsupported_operator",
                    message=f"{condition.operator.value} is not supported for {field_spec.name}",
                    path=f"{path}.operator",
                )
            )
            return

        if condition.operator == ComparisonOperator.BETWEEN:
            value = condition.value
            if not isinstance(value, list) or len(value) != 2:
                issues.append(
                    ValidationIssue(
                        code="invalid_between_value",
                        message="between requires a two-item value list",
                        path=f"{path}.value",
                    )
                )
        if condition.operator in {ComparisonOperator.IN, ComparisonOperator.NOT_IN}:
            if not isinstance(condition.value, list) or not condition.value:
                issues.append(
                    ValidationIssue(
                        code="invalid_list_value",
                        message=f"{condition.operator.value} requires a non-empty value list",
                        path=f"{path}.value",
                    )
                )

    def _validate_field_compare(
        self,
        condition: SmartCondition,
        left: FieldSpec,
        right: FieldSpec,
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        if condition.operator not in left.supported_operators:
            issues.append(
                ValidationIssue(
                    code="unsupported_operator",
                    message=f"{condition.operator.value} is not supported for {left.name}",
                    path=f"{path}.operator",
                )
            )
        if left.data_type != right.data_type:
            issues.append(
                ValidationIssue(
                    code="incompatible_field_types",
                    message=f"Cannot compare {left.name} ({left.data_type.value}) with {right.name} ({right.data_type.value})",
                    path=path,
                )
            )
        if left.data_type not in {FieldDataType.NUMBER, FieldDataType.DATE}:
            issues.append(
                ValidationIssue(
                    code="invalid_field_compare_type",
                    message=f"Field comparison only supports number/date fields, got {left.data_type.value}",
                    path=path,
                )
            )

    def _validate_rank_condition(
        self,
        condition: SmartCondition,
        field_spec: FieldSpec,
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        if field_spec.data_type != FieldDataType.NUMBER:
            issues.append(
                ValidationIssue(
                    code="rank_requires_numeric_field",
                    message=f"Rank condition requires a numeric field, got {field_spec.name}",
                    path=f"{path}.field",
                )
            )
            return

        threshold = condition.threshold
        if condition.rank_operator in {RankOperator.TOP_N, RankOperator.BOTTOM_N}:
            if not isinstance(threshold, int) or threshold < 1:
                issues.append(
                    ValidationIssue(
                        code="invalid_rank_threshold",
                        message="top_n/bottom_n threshold must be a positive integer",
                        path=f"{path}.threshold",
                    )
                )
        if condition.rank_operator in {RankOperator.TOP_PERCENTILE, RankOperator.BOTTOM_PERCENTILE}:
            if not isinstance(threshold, (int, float)) or not (0 < float(threshold) <= 100):
                issues.append(
                    ValidationIssue(
                        code="invalid_rank_threshold",
                        message="top_percentile/bottom_percentile threshold must be in (0, 100]",
                        path=f"{path}.threshold",
                    )
                )

    def _require_field(
        self,
        field_name: str | None,
        path: str,
        issues: list[ValidationIssue],
    ) -> FieldSpec | None:
        if not field_name:
            issues.append(ValidationIssue(code="missing_field", message="field is required", path=path))
            return None
        spec = get_field_spec(field_name)
        if spec is None:
            issues.append(
                ValidationIssue(
                    code="unknown_field",
                    message=f"Unknown field: {field_name}",
                    path=path,
                )
            )
        return spec

    def _add_field(
        self,
        spec: FieldSpec,
        referenced_fields: list[str],
        execution_modes: list[ExecutionMode],
    ) -> None:
        referenced_fields.append(normalize_field_name(spec.name))
        for mode in spec.execution_modes:
            self._add_execution_mode(mode, execution_modes)

    def _add_execution_mode(self, mode: ExecutionMode, execution_modes: list[ExecutionMode]) -> None:
        execution_modes.append(mode)


def validate_dsl(dsl: SmartScreeningDSL | dict) -> ValidationResult:
    return SmartScreeningDSLValidator().validate(dsl)
