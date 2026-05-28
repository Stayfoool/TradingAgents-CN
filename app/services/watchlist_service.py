"""
Watchlist and portfolio persistence service.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.core.database import get_mongo_db
from app.models.watchlist import (
    PortfolioPositionCreate,
    PortfolioPositionUpdate,
    WatchlistItemCreate,
    WatchlistItemUpdate,
)
from app.utils.timezone import now_tz


def _normalize_symbol(symbol: str, market: str = "") -> str:
    value = str(symbol or "").strip().upper()
    if (market or "").upper() in {"CN", "A股"} and value.isdigit():
        return value.zfill(6)
    return value


def _normalize_market(market: str) -> str:
    value = str(market or "US").strip().upper()
    aliases = {"A股": "CN", "美股": "US", "港股": "HK"}
    return aliases.get(value, value)


def _public_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(doc)
    if "_id" in item:
        item["id"] = str(item.pop("_id"))
    for key in ("created_at", "updated_at"):
        if isinstance(item.get(key), datetime):
            item[key] = item[key].isoformat()
    return item


class WatchlistService:
    def __init__(self) -> None:
        self._db = None

    def _get_db(self):
        if self._db is None:
            self._db = get_mongo_db()
        return self._db

    async def ensure_indexes(self) -> None:
        db = self._get_db()
        await db.watchlists.create_index(
            [("user_id", 1), ("market", 1), ("symbol", 1)],
            unique=True,
            name="user_market_symbol_unique",
            background=True,
        )
        await db.watchlists.create_index([("user_id", 1), ("enabled", 1)], background=True)
        await db.portfolio_positions.create_index(
            [("user_id", 1), ("market", 1), ("symbol", 1)],
            unique=True,
            name="user_market_position_unique",
            background=True,
        )
        await db.portfolio_positions.create_index([("user_id", 1), ("enabled", 1)], background=True)

    async def list_watchlist(self, user_id: str, include_disabled: bool = False) -> List[Dict[str, Any]]:
        await self.ensure_indexes()
        query: Dict[str, Any] = {"user_id": user_id}
        if not include_disabled:
            query["enabled"] = {"$ne": False}
        cursor = self._get_db().watchlists.find(query).sort([("market", 1), ("symbol", 1)])
        return [_public_doc(doc) async for doc in cursor]

    async def add_watchlist_item(self, user_id: str, payload: WatchlistItemCreate) -> Dict[str, Any]:
        await self.ensure_indexes()
        market = _normalize_market(payload.market)
        symbol = _normalize_symbol(payload.symbol, market)
        now = now_tz()
        doc = {
            "user_id": user_id,
            "symbol": symbol,
            "stock_name": payload.stock_name or symbol,
            "market": market,
            "tags": payload.tags,
            "notes": payload.notes,
            "enabled": payload.enabled,
            "updated_at": now,
        }
        await self._get_db().watchlists.update_one(
            {"user_id": user_id, "market": market, "symbol": symbol},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        saved = await self._get_db().watchlists.find_one({"user_id": user_id, "market": market, "symbol": symbol})
        return _public_doc(saved)

    async def update_watchlist_item(
        self, user_id: str, item_id: str, payload: WatchlistItemUpdate
    ) -> Optional[Dict[str, Any]]:
        await self.ensure_indexes()
        updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
        if "market" in updates:
            updates["market"] = _normalize_market(updates["market"])
        updates["updated_at"] = now_tz()
        result = await self._get_db().watchlists.update_one(
            {"_id": ObjectId(item_id), "user_id": user_id},
            {"$set": updates},
        )
        if result.matched_count == 0:
            return None
        doc = await self._get_db().watchlists.find_one({"_id": ObjectId(item_id), "user_id": user_id})
        return _public_doc(doc)

    async def delete_watchlist_item(self, user_id: str, item_id: str) -> bool:
        await self.ensure_indexes()
        result = await self._get_db().watchlists.delete_one({"_id": ObjectId(item_id), "user_id": user_id})
        return result.deleted_count > 0

    async def list_positions(self, user_id: str, include_disabled: bool = False) -> List[Dict[str, Any]]:
        await self.ensure_indexes()
        query: Dict[str, Any] = {"user_id": user_id}
        if not include_disabled:
            query["enabled"] = {"$ne": False}
        cursor = self._get_db().portfolio_positions.find(query).sort([("market", 1), ("symbol", 1)])
        return [_public_doc(doc) async for doc in cursor]

    async def add_position(self, user_id: str, payload: PortfolioPositionCreate) -> Dict[str, Any]:
        await self.ensure_indexes()
        market = _normalize_market(payload.market)
        symbol = _normalize_symbol(payload.symbol, market)
        now = now_tz()
        doc = {
            "user_id": user_id,
            "symbol": symbol,
            "stock_name": payload.stock_name or symbol,
            "market": market,
            "quantity": payload.quantity,
            "cost_basis": payload.cost_basis,
            "target_price": payload.target_price,
            "stop_loss": payload.stop_loss,
            "tags": payload.tags,
            "notes": payload.notes,
            "enabled": payload.enabled,
            "updated_at": now,
        }
        await self._get_db().portfolio_positions.update_one(
            {"user_id": user_id, "market": market, "symbol": symbol},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        saved = await self._get_db().portfolio_positions.find_one({"user_id": user_id, "market": market, "symbol": symbol})
        return _public_doc(saved)

    async def update_position(
        self, user_id: str, item_id: str, payload: PortfolioPositionUpdate
    ) -> Optional[Dict[str, Any]]:
        await self.ensure_indexes()
        updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
        if "market" in updates:
            updates["market"] = _normalize_market(updates["market"])
        updates["updated_at"] = now_tz()
        result = await self._get_db().portfolio_positions.update_one(
            {"_id": ObjectId(item_id), "user_id": user_id},
            {"$set": updates},
        )
        if result.matched_count == 0:
            return None
        doc = await self._get_db().portfolio_positions.find_one({"_id": ObjectId(item_id), "user_id": user_id})
        return _public_doc(doc)

    async def delete_position(self, user_id: str, item_id: str) -> bool:
        await self.ensure_indexes()
        result = await self._get_db().portfolio_positions.delete_one({"_id": ObjectId(item_id), "user_id": user_id})
        return result.deleted_count > 0


watchlist_service = WatchlistService()
