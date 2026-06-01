from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.services.smart_screening.schema import ComparisonOperator


class FieldCategory(str, Enum):
    BASIC = "basic"
    PRICE = "price"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    TEXT = "text"
    CONTROL = "control"


class FieldDataType(str, Enum):
    NUMBER = "number"
    STRING = "string"
    DATE = "date"
    BOOL = "bool"


class ExecutionMode(str, Enum):
    HISTORICAL_FACTOR = "historical_factor"
    DYNAMIC_PRICE_CALC = "dynamic_price_calc"
    DYNAMIC_FINANCIAL_CALC = "dynamic_financial_calc"
    TEXT_EVENT_SEARCH = "text_event_search"
    REALTIME_ALERT = "realtime_alert"
    UNSUPPORTED_OR_NEEDS_CONFIRMATION = "unsupported_or_needs_confirmation"


NUMERIC_OPERATORS = frozenset(
    {
        ComparisonOperator.GT,
        ComparisonOperator.LT,
        ComparisonOperator.GTE,
        ComparisonOperator.LTE,
        ComparisonOperator.EQ,
        ComparisonOperator.NE,
        ComparisonOperator.BETWEEN,
        ComparisonOperator.EXISTS,
    }
)

STRING_OPERATORS = frozenset(
    {
        ComparisonOperator.EQ,
        ComparisonOperator.NE,
        ComparisonOperator.IN,
        ComparisonOperator.NOT_IN,
        ComparisonOperator.CONTAINS,
        ComparisonOperator.EXISTS,
    }
)

BOOL_OPERATORS = frozenset({ComparisonOperator.EQ, ComparisonOperator.NE, ComparisonOperator.EXISTS})

DATE_OPERATORS = frozenset(
    {
        ComparisonOperator.GT,
        ComparisonOperator.LT,
        ComparisonOperator.GTE,
        ComparisonOperator.LTE,
        ComparisonOperator.EQ,
        ComparisonOperator.NE,
        ComparisonOperator.BETWEEN,
        ComparisonOperator.EXISTS,
    }
)


@dataclass(frozen=True)
class FieldSpec:
    name: str
    display_name: str
    category: FieldCategory
    data_type: FieldDataType
    source_collection: str
    source_field: str
    supported_operators: frozenset[ComparisonOperator]
    execution_modes: frozenset[ExecutionMode]
    description: str = ""
    unit: Optional[str] = None
    required_base_fields: tuple[str, ...] = ()


FIELD_REGISTRY: dict[str, FieldSpec] = {
    "symbol": FieldSpec(
        name="symbol",
        display_name="Stock symbol",
        category=FieldCategory.BASIC,
        data_type=FieldDataType.STRING,
        source_collection="stock_basic_info",
        source_field="symbol",
        supported_operators=STRING_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR}),
    ),
    "name": FieldSpec(
        name="name",
        display_name="Stock name",
        category=FieldCategory.BASIC,
        data_type=FieldDataType.STRING,
        source_collection="stock_basic_info",
        source_field="name",
        supported_operators=STRING_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR}),
    ),
    "industry": FieldSpec(
        name="industry",
        display_name="Industry",
        category=FieldCategory.BASIC,
        data_type=FieldDataType.STRING,
        source_collection="stock_basic_info",
        source_field="industry",
        supported_operators=STRING_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR}),
    ),
    "is_st": FieldSpec(
        name="is_st",
        display_name="Is ST",
        category=FieldCategory.CONTROL,
        data_type=FieldDataType.BOOL,
        source_collection="stock_basic_info",
        source_field="is_st",
        supported_operators=BOOL_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR}),
    ),
    "is_suspended": FieldSpec(
        name="is_suspended",
        display_name="Is suspended",
        category=FieldCategory.CONTROL,
        data_type=FieldDataType.BOOL,
        source_collection="stock_daily_factors",
        source_field="is_suspended",
        supported_operators=BOOL_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR}),
    ),
    "list_days": FieldSpec(
        name="list_days",
        display_name="Listed days",
        category=FieldCategory.CONTROL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_factors",
        source_field="list_days",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR}),
    ),
    "open": FieldSpec(
        name="open",
        display_name="Open",
        category=FieldCategory.PRICE,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_quotes",
        source_field="open",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_PRICE_CALC}),
        unit="price",
    ),
    "high": FieldSpec(
        name="high",
        display_name="High",
        category=FieldCategory.PRICE,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_quotes",
        source_field="high",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_PRICE_CALC}),
        unit="price",
    ),
    "low": FieldSpec(
        name="low",
        display_name="Low",
        category=FieldCategory.PRICE,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_quotes",
        source_field="low",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_PRICE_CALC}),
        unit="price",
    ),
    "close": FieldSpec(
        name="close",
        display_name="Close",
        category=FieldCategory.PRICE,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_quotes",
        source_field="close",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_PRICE_CALC}),
        unit="price",
    ),
    "volume": FieldSpec(
        name="volume",
        display_name="Volume",
        category=FieldCategory.PRICE,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_quotes",
        source_field="volume",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_PRICE_CALC, ExecutionMode.REALTIME_ALERT}),
    ),
    "amount": FieldSpec(
        name="amount",
        display_name="Amount",
        category=FieldCategory.PRICE,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_quotes",
        source_field="amount",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_PRICE_CALC, ExecutionMode.REALTIME_ALERT}),
    ),
    "pct_chg": FieldSpec(
        name="pct_chg",
        display_name="Daily return percent",
        category=FieldCategory.PRICE,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_factors",
        source_field="pct_chg",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR, ExecutionMode.REALTIME_ALERT}),
        unit="%",
    ),
    "turnover_rate": FieldSpec(
        name="turnover_rate",
        display_name="Turnover rate",
        category=FieldCategory.TECHNICAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_factors",
        source_field="turnover_rate",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR}),
        unit="%",
    ),
    "volume_ratio": FieldSpec(
        name="volume_ratio",
        display_name="Volume ratio",
        category=FieldCategory.TECHNICAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_factors",
        source_field="volume_ratio",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR}),
    ),
    "ma5": FieldSpec(
        name="ma5",
        display_name="MA5",
        category=FieldCategory.TECHNICAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_factors",
        source_field="ma5",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR, ExecutionMode.DYNAMIC_PRICE_CALC}),
        required_base_fields=("close",),
    ),
    "ma10": FieldSpec(
        name="ma10",
        display_name="MA10",
        category=FieldCategory.TECHNICAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_factors",
        source_field="ma10",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR, ExecutionMode.DYNAMIC_PRICE_CALC}),
        required_base_fields=("close",),
    ),
    "ma20": FieldSpec(
        name="ma20",
        display_name="MA20",
        category=FieldCategory.TECHNICAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_factors",
        source_field="ma20",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR, ExecutionMode.DYNAMIC_PRICE_CALC}),
        required_base_fields=("close",),
    ),
    "return_5d": FieldSpec(
        name="return_5d",
        display_name="5-day return",
        category=FieldCategory.TECHNICAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_factors",
        source_field="return_5d",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR, ExecutionMode.DYNAMIC_PRICE_CALC}),
        unit="%",
        required_base_fields=("close",),
    ),
    "return_10d": FieldSpec(
        name="return_10d",
        display_name="10-day return",
        category=FieldCategory.TECHNICAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_factors",
        source_field="return_10d",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR, ExecutionMode.DYNAMIC_PRICE_CALC}),
        unit="%",
        required_base_fields=("close",),
    ),
    "return_20d": FieldSpec(
        name="return_20d",
        display_name="20-day return",
        category=FieldCategory.TECHNICAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_daily_factors",
        source_field="return_20d",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.HISTORICAL_FACTOR, ExecutionMode.DYNAMIC_PRICE_CALC}),
        unit="%",
        required_base_fields=("close",),
    ),
    "pe": FieldSpec(
        name="pe",
        display_name="PE",
        category=FieldCategory.FUNDAMENTAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_financial_data",
        source_field="pe",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_FINANCIAL_CALC}),
    ),
    "pb": FieldSpec(
        name="pb",
        display_name="PB",
        category=FieldCategory.FUNDAMENTAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_financial_data",
        source_field="pb",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_FINANCIAL_CALC}),
    ),
    "roe": FieldSpec(
        name="roe",
        display_name="ROE",
        category=FieldCategory.FUNDAMENTAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_financial_data",
        source_field="roe",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_FINANCIAL_CALC}),
        unit="%",
    ),
    "revenue_growth": FieldSpec(
        name="revenue_growth",
        display_name="Revenue growth",
        category=FieldCategory.FUNDAMENTAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_financial_data",
        source_field="revenue_growth",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_FINANCIAL_CALC}),
        unit="%",
    ),
    "net_profit_growth": FieldSpec(
        name="net_profit_growth",
        display_name="Net profit growth",
        category=FieldCategory.FUNDAMENTAL,
        data_type=FieldDataType.NUMBER,
        source_collection="stock_financial_data",
        source_field="net_profit_growth",
        supported_operators=NUMERIC_OPERATORS,
        execution_modes=frozenset({ExecutionMode.DYNAMIC_FINANCIAL_CALC}),
        unit="%",
    ),
}

FIELD_ALIASES = {
    "code": "symbol",
    "stock_code": "symbol",
    "stock_name": "name",
    "industry_name": "industry",
    "close_price": "close",
    "price": "close",
    "change_percent": "pct_chg",
    "pct_change": "pct_chg",
    "turnover": "turnover_rate",
}


def normalize_field_name(field_name: str) -> str:
    normalized = field_name.strip()
    return FIELD_ALIASES.get(normalized, normalized)


def get_field_spec(field_name: str) -> Optional[FieldSpec]:
    return FIELD_REGISTRY.get(normalize_field_name(field_name))


def list_registered_fields() -> list[str]:
    return sorted(FIELD_REGISTRY)
