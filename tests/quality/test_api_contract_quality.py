from __future__ import annotations

from typing import Any

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.routers import smart_screening


class MonitoringRunRequest(BaseModel):
    symbols: list[str] | None = None
    market: str | None = None
    include_disabled: bool = False
    max_deep_analysis: int = Field(default=10, ge=1, le=50)
    lookback_days: int = Field(default=30, ge=5, le=180)
    news_days: int = Field(default=7, ge=1, le=30)
    force_refresh: bool = False


def _ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def _current_user(authorization: str | None = Header(default=None)) -> dict[str, str]:
    if authorization != "Bearer quality-token":
        raise HTTPException(status_code=401, detail="No authorization header")
    return {"id": "quality-user", "username": "quality"}


def create_quality_api_app() -> FastAPI:
    app = FastAPI(title="TradingAgents-CN Quality API", version="quality")

    watchlist_items = [
        {"id": f"w{i}", "symbol": f"QG{i:03d}", "stock_name": f"Quality Gate {i}", "market": "US", "enabled": True}
        for i in range(1, 10)
    ]

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return _ok(data={"status": "ok", "service": "TradingAgents-CN API"}, message="服务运行正常")

    @app.get("/api/watchlists")
    async def list_watchlist(user: dict = Depends(_current_user)) -> dict[str, Any]:
        return _ok(data={"items": watchlist_items, "total": len(watchlist_items)})

    @app.get("/api/portfolio/positions")
    async def list_positions(user: dict = Depends(_current_user)) -> dict[str, Any]:
        return _ok(data={"items": [], "total": 0})

    @app.post("/api/monitoring/watchlist/run")
    async def run_monitoring(payload: MonitoringRunRequest, user: dict = Depends(_current_user)) -> dict[str, Any]:
        scanned_items = [
            {
                "symbol": item["symbol"],
                "stock_name": item["stock_name"],
                "market": item["market"],
                "status": "triggered" if i == 1 else "no_signal",
                "signal_type": "buy_watch" if i == 1 else "no_action",
                "score": 2.0 if i == 1 else 0.0,
                "triggered": i == 1,
                "reasons": ["权威媒体/公告证据出现积极事件关键词：收入增长。"] if i == 1 else [],
                "data_gaps": [],
            }
            for i, item in enumerate(watchlist_items, start=1)
        ]
        return _ok(
            data={
                "run_id": "quality-run",
                "target_count": 9,
                "scanned_count": 9,
                "triggered_count": 1,
                "report_count": 1,
                "no_signal_count": 8,
                "error_count": 0,
                "scanned_items": scanned_items,
                "reports": [],
                "errors": [],
            },
            message="watchlist monitoring completed",
        )

    @app.get("/api/monitoring/reports")
    async def list_reports(limit: int = 50, skip: int = 0, user: dict = Depends(_current_user)) -> dict[str, Any]:
        return _ok(data={"items": [], "total": 0})

    @app.get("/api/monitoring/runs")
    async def list_runs(limit: int = 20, skip: int = 0, user: dict = Depends(_current_user)) -> dict[str, Any]:
        return _ok(data={"items": [], "total": 0})

    app.include_router(smart_screening.router, prefix="/api/screening/smart", tags=["smart-screening"])
    app.dependency_overrides[smart_screening.get_current_user] = _current_user

    return app


@pytest.fixture()
def quality_client() -> TestClient:
    return TestClient(create_quality_api_app())


def test_minimal_api_smoke_health_and_monitoring_run(quality_client: TestClient):
    health = quality_client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["data"]["status"] == "ok"

    response = quality_client.post(
        "/api/monitoring/watchlist/run",
        headers={"Authorization": "Bearer quality-token"},
        json={"max_deep_analysis": 1, "lookback_days": 5, "news_days": 1},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scanned_count"] == 9
    assert data["triggered_count"] == 1
    assert data["no_signal_count"] == 8
    assert len(data["scanned_items"]) == 9


def test_openapi_contract_exposes_monitoring_coverage_fields(quality_client: TestClient):
    schema = quality_client.get("/openapi.json").json()
    assert "/api/monitoring/watchlist/run" in schema["paths"]
    assert "/api/watchlists" in schema["paths"]
    assert "/api/portfolio/positions" in schema["paths"]
    assert "/api/screening/smart/run-natural-language" in schema["paths"]

    operation = schema["paths"]["/api/monitoring/watchlist/run"]["post"]
    assert "requestBody" in operation
    assert "responses" in operation


def test_schemathesis_can_validate_minimal_openapi_contract(quality_client: TestClient):
    schemathesis = pytest.importorskip("schemathesis")
    app = create_quality_api_app()

    if hasattr(schemathesis, "openapi") and hasattr(schemathesis.openapi, "from_asgi"):
        schema = schemathesis.openapi.from_asgi("/openapi.json", app)
    elif hasattr(schemathesis, "from_asgi"):
        schema = schemathesis.from_asgi("/openapi.json", app)
    else:
        pytest.skip("Installed Schemathesis does not expose an ASGI loader")

    assert "/api/monitoring/watchlist/run" in schema.raw_schema["paths"]


def test_smart_screening_api_runs_natural_language_query(quality_client: TestClient):
    response = quality_client.post(
        "/api/screening/smart/run-natural-language",
        headers={"Authorization": "Bearer quality-token"},
        json={
            "query": "半导体近5日涨幅排名前50%，量比>1.2，换手率>3%，收盘价>5日线>10日线，非ST，并有营收增长研报",
            "as_of": "2026-05-31",
            "use_database": False,
            "include_deep_analysis_tasks": True,
            "deep_analysis_top_n": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["symbol"] == "688001"
    assert data["audit"]["passed"] is True
    assert data["deep_analysis_tasks"][0]["analysts"] == ["market", "fundamentals", "news"]
    assert "返回 1 只候选股" in data["synthesis"]["summary"]


def test_smart_screening_api_exposes_data_contracts(quality_client: TestClient):
    response = quality_client.get(
        "/api/screening/smart/contracts",
        headers={"Authorization": "Bearer quality-token"},
    )

    assert response.status_code == 200
    contracts = response.json()["data"]
    assert "stock_daily_quotes" in contracts
    assert "close" in contracts["stock_daily_quotes"]["required_fields"]
    assert "stock_text_events" in contracts
