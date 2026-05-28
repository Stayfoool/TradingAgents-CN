"""
Watchlist and portfolio APIs for proactive monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.response import ok
from app.models.watchlist import (
    PortfolioPositionCreate,
    PortfolioPositionUpdate,
    WatchlistItemCreate,
    WatchlistItemUpdate,
)
from app.routers.auth_db import get_current_user
from app.services.watchlist_service import watchlist_service

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])
portfolio_router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
async def list_watchlist(include_disabled: bool = False, user: dict = Depends(get_current_user)):
    items = await watchlist_service.list_watchlist(user["id"], include_disabled=include_disabled)
    return ok(data={"items": items, "total": len(items)})


@router.post("")
async def add_watchlist_item(payload: WatchlistItemCreate, user: dict = Depends(get_current_user)):
    item = await watchlist_service.add_watchlist_item(user["id"], payload)
    return ok(data=item, message="watchlist item saved")


@router.put("/{item_id}")
async def update_watchlist_item(
    item_id: str,
    payload: WatchlistItemUpdate,
    user: dict = Depends(get_current_user),
):
    item = await watchlist_service.update_watchlist_item(user["id"], item_id, payload)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist item not found")
    return ok(data=item, message="watchlist item updated")


@router.delete("/{item_id}")
async def delete_watchlist_item(item_id: str, user: dict = Depends(get_current_user)):
    deleted = await watchlist_service.delete_watchlist_item(user["id"], item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist item not found")
    return ok(message="watchlist item deleted")


@portfolio_router.get("/positions")
async def list_positions(include_disabled: bool = False, user: dict = Depends(get_current_user)):
    items = await watchlist_service.list_positions(user["id"], include_disabled=include_disabled)
    return ok(data={"items": items, "total": len(items)})


@portfolio_router.post("/positions")
async def add_position(payload: PortfolioPositionCreate, user: dict = Depends(get_current_user)):
    item = await watchlist_service.add_position(user["id"], payload)
    return ok(data=item, message="portfolio position saved")


@portfolio_router.put("/positions/{item_id}")
async def update_position(
    item_id: str,
    payload: PortfolioPositionUpdate,
    user: dict = Depends(get_current_user),
):
    item = await watchlist_service.update_position(user["id"], item_id, payload)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio position not found")
    return ok(data=item, message="portfolio position updated")


@portfolio_router.delete("/positions/{item_id}")
async def delete_position(item_id: str, user: dict = Depends(get_current_user)):
    deleted = await watchlist_service.delete_position(user["id"], item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio position not found")
    return ok(message="portfolio position deleted")
