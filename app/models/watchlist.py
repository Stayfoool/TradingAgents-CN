"""
Watchlist and monitoring models.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer

from app.utils.timezone import now_tz


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    stock_name: Optional[str] = Field(default=None, max_length=120)
    market: str = Field(default="US", max_length=10)
    tags: List[str] = Field(default_factory=list)
    notes: str = ""
    enabled: bool = True


class WatchlistItemUpdate(BaseModel):
    stock_name: Optional[str] = Field(default=None, max_length=120)
    market: Optional[str] = Field(default=None, max_length=10)
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    enabled: Optional[bool] = None


class PortfolioPositionCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    stock_name: Optional[str] = Field(default=None, max_length=120)
    market: str = Field(default="US", max_length=10)
    quantity: Optional[float] = None
    cost_basis: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    tags: List[str] = Field(default_factory=list)
    notes: str = ""
    enabled: bool = True


class PortfolioPositionUpdate(BaseModel):
    stock_name: Optional[str] = Field(default=None, max_length=120)
    market: Optional[str] = Field(default=None, max_length=10)
    quantity: Optional[float] = None
    cost_basis: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    enabled: Optional[bool] = None


class MonitoringRunRequest(BaseModel):
    symbols: Optional[List[str]] = Field(default=None, description="Optional symbol override.")
    market: Optional[str] = Field(default=None, description="Optional market filter.")
    include_disabled: bool = False
    max_deep_analysis: int = Field(default=10, ge=1, le=50)
    lookback_days: int = Field(default=30, ge=5, le=180)
    news_days: int = Field(default=7, ge=1, le=30)
    force_refresh: bool = False


class MonitoringEvidence(BaseModel):
    type: str
    source: Optional[str] = None
    title: Optional[str] = None
    published_at: Optional[Any] = None
    url: Optional[str] = None
    summary: Optional[str] = None
    extracted_metrics: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    status: Optional[str] = None
    reason: Optional[str] = None


class MonitoringSignal(BaseModel):
    symbol: str
    stock_name: Optional[str] = None
    market: str
    signal_type: str
    severity: str = "info"
    score: float = 0.0
    current_price: Optional[float] = None
    change_percent: Optional[float] = None
    reasons: List[str] = Field(default_factory=list)
    evidence: List[MonitoringEvidence] = Field(default_factory=list)
    recommendation: str = ""
    created_at: datetime = Field(default_factory=now_tz)

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime, _info) -> str:
        return dt.isoformat()
