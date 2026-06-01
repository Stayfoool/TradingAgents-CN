from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Market(str, Enum):
    CN = "CN"
    HK = "HK"
    US = "US"
    ALL = "ALL"


class UniverseType(str, Enum):
    ALL = "all"
    WATCHLIST = "watchlist"
    INDUSTRY = "industry"
    SECTOR = "sector"
    THEME = "theme"
    CUSTOM_SYMBOLS = "custom_symbols"


class LogicalOperator(str, Enum):
    AND = "AND"
    OR = "OR"


class ConditionType(str, Enum):
    GROUP = "group"
    VALUE = "value"
    FIELD_COMPARE = "field_compare"
    RANK = "rank"
    TEXT_EVENT = "text_event"


class ComparisonOperator(str, Enum):
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NE = "!="
    BETWEEN = "between"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    EXISTS = "exists"


class RankOperator(str, Enum):
    TOP_N = "top_n"
    TOP_PERCENTILE = "top_percentile"
    BOTTOM_N = "bottom_n"
    BOTTOM_PERCENTILE = "bottom_percentile"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class WindowUnit(str, Enum):
    TRADING_DAY = "trading_day"
    CALENDAR_DAY = "calendar_day"
    MONTH = "month"


ScalarValue = Union[str, int, float, bool]
ConditionValue = Union[ScalarValue, list[ScalarValue]]


class WindowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length: int = Field(..., ge=1, le=500, description="Window length")
    unit: WindowUnit = Field(WindowUnit.TRADING_DAY, description="Window unit")


class DateRangeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: Optional[date] = Field(None, description="Inclusive start date")
    end: Optional[date] = Field(None, description="Inclusive end date")

    @model_validator(mode="after")
    def validate_date_order(self) -> "DateRangeSpec":
        if self.start and self.end and self.start > self.end:
            raise ValueError("date_range.start must be <= date_range.end")
        return self


class UniverseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    universe_type: UniverseType = Field(UniverseType.ALL, description="Universe type")
    values: list[str] = Field(default_factory=list, description="Universe values")

    @field_validator("values")
    @classmethod
    def clean_values(cls, values: list[str]) -> list[str]:
        return [str(value).strip() for value in values if str(value).strip()]

    @model_validator(mode="after")
    def validate_required_values(self) -> "UniverseSpec":
        if self.universe_type != UniverseType.ALL and not self.values:
            raise ValueError(f"universe values are required for {self.universe_type.value}")
        return self


class SortSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(..., description="Sort field")
    direction: SortDirection = Field(SortDirection.DESC, description="Sort direction")

    @field_validator("field")
    @classmethod
    def clean_field(cls, value: str) -> str:
        return value.strip()


class SmartCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition_type: ConditionType = Field(..., description="Condition type")
    field: Optional[str] = Field(None, description="Left field")
    operator: Optional[ComparisonOperator] = Field(None, description="Comparison operator")
    value: Optional[ConditionValue] = Field(None, description="Comparison value")
    right_field: Optional[str] = Field(None, description="Right field for field comparisons")
    rank_operator: Optional[RankOperator] = Field(None, description="Rank operator")
    threshold: Optional[Union[int, float]] = Field(None, description="Rank threshold")
    window: Optional[WindowSpec] = Field(None, description="Window for derived fields")
    date_range: Optional[DateRangeSpec] = Field(None, description="Date range constraint")
    logic: Optional[LogicalOperator] = Field(None, description="Logic for group conditions")
    children: list["SmartCondition"] = Field(default_factory=list, description="Nested conditions")

    event_types: list[str] = Field(default_factory=list, description="Text event types")
    keywords: list[str] = Field(default_factory=list, description="Text event keywords")
    sources: list[str] = Field(default_factory=list, description="Text event sources")
    sentiment: Optional[str] = Field(None, description="Text event sentiment")

    @field_validator("field", "right_field")
    @classmethod
    def clean_optional_field(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("event_types", "keywords", "sources")
    @classmethod
    def clean_string_list(cls, values: list[str]) -> list[str]:
        return [str(value).strip() for value in values if str(value).strip()]

    @model_validator(mode="after")
    def validate_shape(self) -> "SmartCondition":
        if self.condition_type == ConditionType.GROUP:
            if not self.children:
                raise ValueError("group condition requires children")
            if self.logic is None:
                self.logic = LogicalOperator.AND
            return self

        if self.children:
            raise ValueError("non-group condition cannot have children")

        if self.condition_type == ConditionType.VALUE:
            if not self.field or self.operator is None:
                raise ValueError("value condition requires field and operator")
            if self.operator != ComparisonOperator.EXISTS and self.value is None:
                raise ValueError("value condition requires value unless operator is exists")

        if self.condition_type == ConditionType.FIELD_COMPARE:
            if not self.field or self.operator is None or not self.right_field:
                raise ValueError("field_compare condition requires field, operator, and right_field")
            if self.operator in {
                ComparisonOperator.BETWEEN,
                ComparisonOperator.IN,
                ComparisonOperator.NOT_IN,
                ComparisonOperator.CONTAINS,
                ComparisonOperator.EXISTS,
            }:
                raise ValueError(f"{self.operator.value} is not valid for field_compare")

        if self.condition_type == ConditionType.RANK:
            if not self.field or self.rank_operator is None or self.threshold is None:
                raise ValueError("rank condition requires field, rank_operator, and threshold")

        if self.condition_type == ConditionType.TEXT_EVENT:
            has_text_filter = bool(self.event_types or self.keywords or self.sources or self.sentiment)
            if not has_text_filter:
                raise ValueError("text_event condition requires event_types, keywords, sources, or sentiment")

        return self


class SmartScreeningDSL(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field("1.0", description="DSL version")
    market: Market = Field(Market.CN, description="Market")
    as_of: Optional[date] = Field(None, description="Analysis date. Future data must be ignored.")
    universe: UniverseSpec = Field(default_factory=UniverseSpec, description="Stock universe")
    condition_logic: LogicalOperator = Field(LogicalOperator.AND, description="Top-level condition logic")
    conditions: list[SmartCondition] = Field(default_factory=list, description="Screening conditions")
    sort: list[SortSpec] = Field(default_factory=list, description="Sort fields")
    limit: int = Field(50, ge=1, le=500, description="Result limit")
    offset: int = Field(0, ge=0, description="Result offset")
    explain: bool = Field(True, description="Whether to ask LLM to explain final results")
    raw_user_query: Optional[str] = Field(None, description="Original user query")

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if value != "1.0":
            raise ValueError("only DSL version 1.0 is supported")
        return value

    def to_audit_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


SmartCondition.model_rebuild()
