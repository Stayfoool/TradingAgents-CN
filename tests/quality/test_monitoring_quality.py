import sys
import types
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_monitoring_import_stubs() -> None:
    """Avoid real DB, Redis, provider, and tradingagents imports for focused tests."""

    package_paths = {
        "app": PROJECT_ROOT / "app",
        "app.core": PROJECT_ROOT / "app" / "core",
        "app.services": PROJECT_ROOT / "app" / "services",
        "app.utils": PROJECT_ROOT / "app" / "utils",
        "app.models": PROJECT_ROOT / "app" / "models",
    }

    def package(name: str) -> types.ModuleType:
        mod = sys.modules.get(name)
        if mod is None:
            mod = types.ModuleType(name)
            sys.modules[name] = mod
            parent_name, _, child_name = name.rpartition(".")
            if parent_name:
                setattr(package(parent_name), child_name, mod)
        mod.__path__ = [str(package_paths[name])] if name in package_paths else []  # type: ignore[attr-defined]
        return mod

    def module(name: str) -> types.ModuleType:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        parent_name, _, child_name = name.rpartition(".")
        if parent_name:
            setattr(package(parent_name), child_name, mod)
        return mod

    package("app.models")

    database_mod = module("app.core.database")
    database_mod.get_mongo_db = lambda: None

    notification_mod = module("app.models.notification")

    @dataclass
    class NotificationCreate:
        user_id: str
        type: str
        title: str
        content: str | None = None
        link: str | None = None
        source: str | None = None
        severity: str | None = None
        metadata: dict[str, Any] | None = None

    notification_mod.NotificationCreate = NotificationCreate

    watchlist_mod = module("app.models.watchlist")

    @dataclass
    class MonitoringRunRequest:
        symbols: list[str] | None = None
        market: str | None = None
        include_disabled: bool = False
        max_deep_analysis: int = 10
        lookback_days: int = 30
        news_days: int = 7
        force_refresh: bool = False

        def model_dump(self) -> dict[str, Any]:
            return {
                "symbols": self.symbols,
                "market": self.market,
                "include_disabled": self.include_disabled,
                "max_deep_analysis": self.max_deep_analysis,
                "lookback_days": self.lookback_days,
                "news_days": self.news_days,
                "force_refresh": self.force_refresh,
            }

    watchlist_mod.MonitoringRunRequest = MonitoringRunRequest

    foreign_stock_mod = module("app.services.foreign_stock_service")

    class ForeignStockService:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    foreign_stock_mod.ForeignStockService = ForeignStockService

    historical_data_mod = module("app.services.historical_data_service")

    async def get_historical_data_service() -> Any:
        raise RuntimeError("historical data service is stubbed in monitoring quality tests")

    historical_data_mod.get_historical_data_service = get_historical_data_service

    notifications_service_mod = module("app.services.notifications_service")

    class NotificationsService:
        async def create_and_publish(self, *args: Any, **kwargs: Any) -> str:
            return "quality-notification"

    notifications_service_mod.get_notifications_service = lambda: NotificationsService()

    watchlist_service_mod = module("app.services.watchlist_service")

    class WatchlistService:
        async def list_watchlist(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            return []

        async def list_positions(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            return []

    watchlist_service_mod.watchlist_service = WatchlistService()

    timezone_mod = module("app.utils.timezone")
    timezone_mod.now_tz = lambda: datetime.now(ZoneInfo("Asia/Shanghai"))


_install_monitoring_import_stubs()

from app.models.watchlist import MonitoringRunRequest
from app.services.monitoring.signal_rules import evaluate_symbol
from app.services.monitoring.watchlist_monitor_service import WatchlistMonitorService


class InsertResult:
    inserted_id = "quality-run"


class UpdateResult:
    upserted_id = "quality-signal"


class FakeCollection:
    def __init__(self) -> None:
        self.inserted: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []

    async def create_index(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def insert_one(self, doc: dict[str, Any]) -> InsertResult:
        self.inserted.append(doc)
        return InsertResult()

    async def insert_many(self, docs: list[dict[str, Any]]) -> None:
        self.inserted.extend(docs)

    async def update_one(self, *args: Any, **kwargs: Any) -> UpdateResult:
        self.updates.append({"args": args, "kwargs": kwargs})
        return UpdateResult()


class FakeDB:
    def __init__(self) -> None:
        self.monitoring_runs = FakeCollection()
        self.monitoring_reports = FakeCollection()
        self.monitoring_evidence = FakeCollection()
        self.monitoring_signals = FakeCollection()


def _targets() -> list[dict[str, Any]]:
    return [
        {"symbol": f"QG{i:03d}", "stock_name": f"Quality Gate {i}", "market": "US", "position": None}
        for i in range(1, 10)
    ]


def _quotes() -> list[dict[str, Any]]:
    return [
        {"price": 110, "pre_close": 100, "volume": 1000, "name": "Quality Gate 1"},
        {"price": 120, "pre_close": 100, "volume": 1000, "name": "Quality Gate 2"},
        *[
            {"price": 100, "pre_close": 100, "volume": 1000, "name": f"Quality Gate {i}"}
            for i in range(3, 10)
        ],
    ]


@pytest.mark.asyncio
async def test_watchlist_monitor_scans_all_targets_even_when_report_limit_is_one():
    service = WatchlistMonitorService()
    service._get_db = lambda: FakeDB()  # type: ignore[method-assign]
    service._notify = AsyncMock()  # type: ignore[method-assign]
    service._load_targets = AsyncMock(return_value=_targets())  # type: ignore[method-assign]
    service._get_quote = AsyncMock(side_effect=_quotes())  # type: ignore[method-assign]
    service._get_klines = AsyncMock(return_value=[])  # type: ignore[method-assign]
    service.evidence_collector.collect_news_evidence = AsyncMock(return_value=[])

    result = await service.run_for_user(
        "quality-user",
        MonitoringRunRequest(max_deep_analysis=1, lookback_days=5, news_days=1),
    )

    statuses = [item["status"] for item in result["scanned_items"]]
    skipped = [item for item in result["scanned_items"] if item.get("report_skipped_reason")]

    assert result["target_count"] == 9
    assert result["scanned_count"] == 9
    assert len(result["scanned_items"]) == 9
    assert result["triggered_count"] == 2
    assert result["report_count"] == 1
    assert result["no_signal_count"] == 7
    assert result["error_count"] == 0
    assert Counter(statuses) == {"triggered": 2, "no_signal": 7}
    assert len(skipped) == 1


def test_missing_price_sentinel_minus_100_does_not_trigger_false_signal():
    result = evaluate_symbol(
        quote={"price": None, "close": None, "change_percent": -100},
        klines=[],
        has_position=False,
    )

    assert result["triggered"] is False
    assert result["metrics"]["current_price"] is None
    assert result["metrics"]["change_percent"] is None
    assert result["reasons"] == []


def test_valid_price_recomputes_change_percent_instead_of_trusting_sentinel():
    result = evaluate_symbol(
        quote={"price": 134.79, "pre_close": 135.98, "change_percent": -100},
        klines=[],
        has_position=False,
    )

    assert result["triggered"] is False
    assert result["metrics"]["current_price"] == 134.79
    assert round(result["metrics"]["change_percent"], 2) == -0.88
