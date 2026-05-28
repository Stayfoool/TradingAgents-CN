"""
Monitoring APIs.
"""
from fastapi import APIRouter, Depends, Query

from app.core.response import ok
from app.models.watchlist import MonitoringRunRequest
from app.routers.auth_db import get_current_user
from app.services.monitoring.watchlist_monitor_service import watchlist_monitor_service

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.post("/watchlist/run")
async def run_watchlist_monitoring(
    payload: MonitoringRunRequest,
    user: dict = Depends(get_current_user),
):
    result = await watchlist_monitor_service.run_for_user(user["id"], payload)
    return ok(data=result, message="watchlist monitoring completed")


@router.get("/reports")
async def list_monitoring_reports(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    result = await watchlist_monitor_service.list_reports(user["id"], limit=limit, skip=skip)
    return ok(data=result)


@router.get("/runs")
async def list_monitoring_runs(
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    result = await watchlist_monitor_service.list_runs(user["id"], limit=limit, skip=skip)
    return ok(data=result)
