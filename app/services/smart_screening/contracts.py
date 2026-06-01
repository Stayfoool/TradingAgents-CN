from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CollectionContract:
    name: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = ()
    description: str = ""


SMART_SCREENING_COLLECTION_CONTRACTS: dict[str, CollectionContract] = {
    "stock_daily_quotes": CollectionContract(
        name="stock_daily_quotes",
        required_fields=("symbol|code", "date", "open", "high", "low", "close", "volume", "amount"),
        optional_fields=("market", "source", "adj"),
        description="Historical OHLCV facts. Used for dynamic return, moving average, and price comparison calculations.",
    ),
    "stock_financial_data": CollectionContract(
        name="stock_financial_data",
        required_fields=("symbol|code",),
        optional_fields=("date", "report_date", "end_date", "pe", "pb", "roe", "revenue_growth", "net_profit_growth"),
        description="Financial and valuation facts merged into screening rows when factor records do not already contain them.",
    ),
    "stock_daily_factors": CollectionContract(
        name="stock_daily_factors",
        required_fields=("symbol|code", "date"),
        optional_fields=(
            "market",
            "industry",
            "is_st",
            "is_suspended",
            "list_days",
            "pct_chg",
            "turnover_rate",
            "volume_ratio",
            "ma5",
            "ma10",
            "ma20",
            "return_5d",
            "return_10d",
            "return_20d",
            "pe",
            "pb",
            "roe",
            "revenue_growth",
            "net_profit_growth",
        ),
        description="Precomputed daily screening factors. Missing price-derived fields can be calculated from stock_daily_quotes.",
    ),
    "stock_text_events": CollectionContract(
        name="stock_text_events",
        required_fields=("symbol|code", "event_date", "event_type", "source"),
        optional_fields=("title", "summary", "sentiment", "url", "publisher", "raw_id"),
        description="Normalized text events extracted from news, announcements, research reports, and industry information.",
    ),
}


def get_smart_screening_contracts() -> dict[str, dict]:
    return {
        name: {
            "name": contract.name,
            "required_fields": list(contract.required_fields),
            "optional_fields": list(contract.optional_fields),
            "description": contract.description,
        }
        for name, contract in SMART_SCREENING_COLLECTION_CONTRACTS.items()
    }
