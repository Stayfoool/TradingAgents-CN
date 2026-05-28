"""
Evidence collection for monitoring signals.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

AUTHORITATIVE_SOURCES = {
    "benzinga",
    "zacks",
    "reuters",
    "associated press",
    "ap",
    "bloomberg",
    "cnbc",
    "marketwatch",
    "wsj",
    "wall street journal",
    "barron's",
    "barrons",
    "the motley fool",
    "motley fool",
    "seeking alpha",
    "pr newswire",
    "business wire",
    "globenewswire",
    "sec",
    "edgar",
}

EVENT_KEYWORDS = {
    "earnings": ["earnings", "revenue", "eps", "profit", "quarter", "q1", "q2", "q3", "q4"],
    "guidance": ["guidance", "outlook", "forecast", "raise", "raised", "cut", "lowered"],
    "risk": ["downgrade", "lawsuit", "investigation", "probe", "miss", "misses", "layoffs"],
    "corporate": ["acquisition", "merger", "partnership", "contract", "approval"],
}


def _safe_lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except Exception:
            return None
    text = str(value)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except Exception:
            continue
    return None


def _extract_metrics(text: str) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    revenue_match = re.search(r"revenue[^$0-9]*(?:of\s*)?\$?([0-9]+(?:\.[0-9]+)?)\s*(billion|million|bn|m)?", text, re.I)
    if revenue_match:
        metrics["revenue_mentioned"] = " ".join(part for part in revenue_match.groups() if part)

    surprise_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:above|beat|higher|surprise)", text, re.I)
    if surprise_match:
        metrics["surprise_pct_mentioned"] = surprise_match.group(1) + "%"

    growth_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:growth|increase|同比|增长)", text, re.I)
    if growth_match:
        metrics["growth_pct_mentioned"] = growth_match.group(1) + "%"

    return metrics


def score_news_item(item: Dict[str, Any], symbol: str) -> float:
    source = _safe_lower(item.get("source"))
    title = _safe_lower(item.get("title"))
    summary = _safe_lower(item.get("summary") or item.get("content"))
    combined = f"{title} {summary}"

    score = 0.0
    if any(src in source for src in AUTHORITATIVE_SOURCES):
        score += 0.45
    if symbol.lower() in combined:
        score += 0.15
    if any(keyword in combined for words in EVENT_KEYWORDS.values() for keyword in words):
        score += 0.25
    if item.get("url"):
        score += 0.1
    if item.get("summary"):
        score += 0.05
    return round(min(score, 1.0), 2)


def format_evidence(item: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    text = f"{item.get('title', '')} {item.get('summary', '')} {item.get('content', '')}"
    published = _parse_dt(item.get("publish_time") or item.get("published_at"))
    return {
        "type": "authoritative_media",
        "source": item.get("source") or item.get("data_source"),
        "title": item.get("title"),
        "published_at": published.isoformat() if published else item.get("publish_time"),
        "url": item.get("url"),
        "summary": item.get("summary") or item.get("content"),
        "extracted_metrics": _extract_metrics(text),
        "confidence": score_news_item(item, symbol),
    }


class EvidenceCollector:
    async def collect_news_evidence(
        self,
        *,
        symbol: str,
        market: str,
        days: int = 7,
        limit: int = 20,
        force_refresh: bool = False,
        db=None,
    ) -> List[Dict[str, Any]]:
        start_time = datetime.utcnow() - timedelta(days=days)
        news_items: List[Dict[str, Any]] = []

        try:
            from app.services.news_data_service import NewsQueryParams, get_news_data_service

            news_service = await get_news_data_service()
            stored_news = await news_service.query_news(
                NewsQueryParams(symbol=symbol, start_time=start_time, limit=limit, sort_by="publish_time")
            )
            news_items.extend(stored_news)
        except Exception:
            pass

        if (force_refresh or not news_items) and market.upper() in {"US", "HK"}:
            try:
                from app.services.foreign_stock_service import ForeignStockService

                service = ForeignStockService(db=db)
                if market.upper() == "US":
                    fetched = await service.get_us_news(symbol, days=days, limit=limit)
                else:
                    fetched = await service.get_hk_news(symbol, days=days, limit=limit)
                for item in fetched.get("items", []):
                    item = dict(item)
                    item.setdefault("symbol", symbol)
                    item.setdefault("market", market.upper())
                    news_items.append(item)
            except Exception:
                pass

        scored = []
        seen = set()
        for item in news_items:
            key = item.get("url") or f"{item.get('title')}:{item.get('publish_time')}"
            if key in seen:
                continue
            seen.add(key)
            evidence = format_evidence(item, symbol)
            if evidence["confidence"] and evidence["confidence"] >= 0.45:
                scored.append(evidence)

        scored.sort(key=lambda row: row.get("confidence") or 0, reverse=True)
        if scored:
            return scored[:limit]

        return [{
            "type": "authoritative_media",
            "status": "not_found",
            "reason": "No whitelisted authoritative media found within the configured lookback window.",
            "confidence": 0.0,
        }]
