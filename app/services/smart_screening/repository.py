from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from app.services.smart_screening.registry import FieldCategory, get_field_spec
from app.services.smart_screening.sample_data import get_sample_stock_rows, get_sample_text_events
from app.services.smart_screening.schema import Market, UniverseSpec, UniverseType


class SmartScreeningRepository(Protocol):
    async def load_factor_rows(self, *, market: Market, as_of: date | None, universe: UniverseSpec) -> list[dict[str, Any]]:
        ...

    async def load_price_history(self, *, market: Market, as_of: date | None, universe: UniverseSpec) -> list[dict[str, Any]]:
        ...

    async def load_text_events(self, *, market: Market, as_of: date | None, universe: UniverseSpec) -> list[dict[str, Any]]:
        ...


class InMemorySmartScreeningRepository:
    def __init__(self, stock_rows: list[dict[str, Any]] | None = None, text_events: list[dict[str, Any]] | None = None):
        self.stock_rows = stock_rows or get_sample_stock_rows()
        self.text_events = text_events or get_sample_text_events()

    async def load_factor_rows(self, *, market: Market, as_of: date | None, universe: UniverseSpec) -> list[dict[str, Any]]:
        rows = [row.copy() for row in self.stock_rows if _matches_market(row, market)]
        if as_of:
            rows = [row for row in rows if _parse_iso_date(row.get("date")) <= as_of]
        return [row for row in rows if _matches_universe(row, universe)]

    async def load_price_history(self, *, market: Market, as_of: date | None, universe: UniverseSpec) -> list[dict[str, Any]]:
        return await self.load_factor_rows(market=market, as_of=as_of, universe=universe)

    async def load_text_events(self, *, market: Market, as_of: date | None, universe: UniverseSpec) -> list[dict[str, Any]]:
        stock_rows = await self.load_factor_rows(market=market, as_of=as_of, universe=universe)
        allowed_symbols = {row.get("symbol") for row in stock_rows}
        events = [event.copy() for event in self.text_events if event.get("symbol") in allowed_symbols]
        if as_of:
            events = [event for event in events if _parse_iso_date(event.get("event_date")) <= as_of]
        return events


class MongoSmartScreeningRepository:
    def __init__(self, db: Any):
        self.db = db

    async def load_factor_rows(self, *, market: Market, as_of: date | None, universe: UniverseSpec) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if market != Market.ALL:
            query["market"] = {"$in": [market.value, _market_label(market)]}
        if as_of:
            query["date"] = {"$lte": as_of.isoformat()}
        query.update(_universe_query(universe))

        projection = {"_id": 0}
        cursor = self.db["stock_daily_factors"].find(query, projection)
        if as_of:
            cursor = cursor.sort("date", -1)
        rows = await cursor.to_list(length=5000)

        latest_by_symbol: dict[str, dict[str, Any]] = {}
        for row in rows:
            symbol = _symbol_of(row)
            if symbol and symbol not in latest_by_symbol:
                latest_by_symbol[symbol] = _normalize_row(row)

        if latest_by_symbol:
            await self._merge_basic_info(latest_by_symbol)
            await self._merge_financial_data(latest_by_symbol, as_of)
            return list(latest_by_symbol.values())

        return await self._load_from_legacy_collections(market=market, as_of=as_of, universe=universe)

    async def load_text_events(self, *, market: Market, as_of: date | None, universe: UniverseSpec) -> list[dict[str, Any]]:
        factor_rows = await self.load_factor_rows(market=market, as_of=as_of, universe=universe)
        allowed_symbols = {_symbol_of(row) for row in factor_rows if _symbol_of(row)}
        if not allowed_symbols:
            return []

        query: dict[str, Any] = {"symbol": {"$in": sorted(allowed_symbols)}}
        if as_of:
            query["event_date"] = {"$lte": as_of.isoformat()}

        events = await self.db["stock_text_events"].find(query, {"_id": 0}).to_list(length=10000)
        if events:
            return [_normalize_event(event) for event in events]

        news_query: dict[str, Any] = {"$or": [{"symbol": {"$in": sorted(allowed_symbols)}}, {"code": {"$in": sorted(allowed_symbols)}}]}
        if as_of:
            news_query["$and"] = [
                {
                    "$or": [
                        {"event_date": {"$lte": as_of.isoformat()}},
                        {"publish_time": {"$lte": as_of.isoformat()}},
                        {"date": {"$lte": as_of.isoformat()}},
                    ]
                }
            ]
        news = await self.db["stock_news"].find(news_query, {"_id": 0}).to_list(length=10000)
        return [_normalize_event(item) for item in news]

    async def load_price_history(self, *, market: Market, as_of: date | None, universe: UniverseSpec) -> list[dict[str, Any]]:
        query = build_mongo_match_query_from_parts(market=market, as_of=as_of, universe=universe)
        cursor = self.db["stock_daily_quotes"].find(query, {"_id": 0})
        if as_of:
            cursor = cursor.sort([("symbol", 1), ("code", 1), ("date", 1)])
        rows = await cursor.to_list(length=200000)
        return [_normalize_row(row) for row in rows]

    async def _load_from_legacy_collections(self, *, market: Market, as_of: date | None, universe: UniverseSpec) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if market != Market.ALL:
            query["market"] = {"$in": [market.value, _market_label(market)]}
        if as_of:
            query["date"] = {"$lte": as_of.isoformat()}
        query.update(_universe_query(universe))
        cursor = self.db["stock_daily_quotes"].find(query, {"_id": 0})
        if as_of:
            cursor = cursor.sort("date", -1)
        rows = await cursor.to_list(length=5000)

        latest_by_symbol: dict[str, dict[str, Any]] = {}
        for row in rows:
            symbol = _symbol_of(row)
            if symbol and symbol not in latest_by_symbol:
                latest_by_symbol[symbol] = _normalize_row(row)

        await self._merge_basic_info(latest_by_symbol)
        await self._merge_financial_data(latest_by_symbol, as_of)
        return list(latest_by_symbol.values())

    async def _merge_basic_info(self, rows_by_symbol: dict[str, dict[str, Any]]) -> None:
        if not rows_by_symbol:
            return
        symbols = sorted(rows_by_symbol)
        cursor = self.db["stock_basic_info"].find(
            {"$or": [{"symbol": {"$in": symbols}}, {"code": {"$in": symbols}}]},
            {"_id": 0},
        )
        async for doc in cursor:
            symbol = _symbol_of(doc)
            if not symbol or symbol not in rows_by_symbol:
                continue
            row = rows_by_symbol[symbol]
            row.setdefault("symbol", symbol)
            row.setdefault("name", doc.get("name") or doc.get("stock_name"))
            row.setdefault("industry", doc.get("industry"))
            row.setdefault("market", doc.get("market"))
            row.setdefault("is_st", _infer_is_st(row.get("name") or doc.get("name") or doc.get("stock_name")))

    async def _merge_financial_data(self, rows_by_symbol: dict[str, dict[str, Any]], as_of: date | None) -> None:
        if not rows_by_symbol:
            return
        symbols = sorted(rows_by_symbol)
        query: dict[str, Any] = {"$or": [{"symbol": {"$in": symbols}}, {"code": {"$in": symbols}}]}
        if as_of:
            query["$and"] = [
                {
                    "$or": [
                        {"date": {"$lte": as_of.isoformat()}},
                        {"report_date": {"$lte": as_of.isoformat()}},
                        {"end_date": {"$lte": as_of.isoformat()}},
                    ]
                }
            ]
        cursor = self.db["stock_financial_data"].find(query, {"_id": 0})
        if as_of:
            cursor = cursor.sort([("date", -1), ("report_date", -1), ("end_date", -1)])

        seen: set[str] = set()
        async for doc in cursor:
            symbol = _symbol_of(doc)
            if not symbol or symbol in seen or symbol not in rows_by_symbol:
                continue
            seen.add(symbol)
            for field in ("pe", "pb", "roe", "revenue_growth", "net_profit_growth"):
                if rows_by_symbol[symbol].get(field) is None and doc.get(field) is not None:
                    rows_by_symbol[symbol][field] = doc.get(field)


def build_mongo_match_query(dsl) -> dict[str, Any]:
    return build_mongo_match_query_from_parts(market=dsl.market, as_of=dsl.as_of, universe=dsl.universe)


def build_mongo_match_query_from_parts(*, market: Market, as_of: date | None, universe: UniverseSpec) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if market != Market.ALL:
        query["market"] = {"$in": [market.value, _market_label(market)]}
    if as_of:
        query["date"] = {"$lte": as_of.isoformat()}
    query.update(_universe_query(universe))
    return query


def _universe_query(universe: UniverseSpec) -> dict[str, Any]:
    if universe.universe_type == UniverseType.ALL:
        return {}
    if universe.universe_type == UniverseType.CUSTOM_SYMBOLS:
        values = [_normalize_symbol(value) for value in universe.values]
        return {"$or": [{"symbol": {"$in": values}}, {"code": {"$in": values}}]}
    if universe.universe_type == UniverseType.INDUSTRY:
        return {"industry": {"$in": universe.values}}
    if universe.universe_type in {UniverseType.SECTOR, UniverseType.THEME}:
        return {universe.universe_type.value: {"$in": universe.values}}
    return {}


def _matches_market(row: dict[str, Any], market: Market) -> bool:
    if market == Market.ALL:
        return True
    row_market = str(row.get("market") or "").upper()
    return row_market in {market.value, _market_label(market).upper()}


def _matches_universe(row: dict[str, Any], universe: UniverseSpec) -> bool:
    if universe.universe_type == UniverseType.ALL:
        return True
    values = set(universe.values)
    if universe.universe_type == UniverseType.CUSTOM_SYMBOLS:
        symbols = {_normalize_symbol(value) for value in values}
        return _symbol_of(row) in symbols
    if universe.universe_type == UniverseType.INDUSTRY:
        return row.get("industry") in values
    if universe.universe_type == UniverseType.SECTOR:
        return row.get("sector") in values
    if universe.universe_type == UniverseType.THEME:
        return row.get("theme") in values
    return True


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = row.copy()
    symbol = _symbol_of(normalized)
    if symbol:
        normalized["symbol"] = symbol
        normalized.setdefault("code", symbol)
    if "is_st" not in normalized:
        normalized["is_st"] = _infer_is_st(normalized.get("name"))
    return normalized


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    normalized = event.copy()
    symbol = _symbol_of(normalized)
    if symbol:
        normalized["symbol"] = symbol
    normalized.setdefault("event_date", normalized.get("publish_time") or normalized.get("date"))
    normalized.setdefault("event_type", normalized.get("type") or normalized.get("category") or "news")
    normalized.setdefault("source", normalized.get("source") or normalized.get("media") or "stock_news")
    normalized.setdefault("summary", normalized.get("summary") or normalized.get("content") or normalized.get("title") or "")
    normalized.setdefault("title", normalized.get("title") or normalized.get("headline") or "")
    return normalized


def _symbol_of(row: dict[str, Any]) -> str:
    return _normalize_symbol(row.get("symbol") or row.get("code") or row.get("stock_code") or "")


def _normalize_symbol(value: Any) -> str:
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".")[0]
    return text.zfill(6) if text.isdigit() and len(text) < 6 else text


def _parse_iso_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "1900-01-01")[:10]
    return date.fromisoformat(text)


def _market_label(market: Market) -> str:
    labels = {Market.CN: "A股", Market.HK: "港股", Market.US: "美股", Market.ALL: "ALL"}
    return labels[market]


def _infer_is_st(name: Any) -> bool:
    text = str(name or "").upper()
    return "ST" in text


def uses_text_field(field_name: str | None) -> bool:
    if not field_name:
        return False
    spec = get_field_spec(field_name)
    return bool(spec and spec.category == FieldCategory.TEXT)
