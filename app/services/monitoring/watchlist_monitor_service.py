"""
Watchlist monitoring service.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import get_mongo_db
from app.models.notification import NotificationCreate
from app.models.watchlist import MonitoringRunRequest
from app.services.foreign_stock_service import ForeignStockService
from app.services.historical_data_service import get_historical_data_service
from app.services.monitoring.evidence_collector import EvidenceCollector
from app.services.monitoring.report_builder import build_report
from app.services.monitoring.signal_rules import evaluate_evidence_signal, evaluate_symbol, merge_signals
from app.services.notifications_service import get_notifications_service
from app.services.watchlist_service import watchlist_service
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)


class WatchlistMonitorService:
    def __init__(self) -> None:
        self.evidence_collector = EvidenceCollector()

    def _get_db(self):
        return get_mongo_db()

    async def ensure_indexes(self) -> None:
        db = self._get_db()
        await db.monitoring_runs.create_index([("user_id", 1), ("created_at", -1)], background=True)
        await db.monitoring_reports.create_index([("user_id", 1), ("created_at", -1)], background=True)
        await db.monitoring_reports.create_index([("user_id", 1), ("symbol", 1), ("run_id", 1)], background=True)
        await db.monitoring_evidence.create_index([("user_id", 1), ("symbol", 1), ("created_at", -1)], background=True)
        await db.monitoring_signals.create_index(
            [("user_id", 1), ("symbol", 1), ("signal_day", 1), ("signal_type", 1)],
            unique=True,
            background=True,
            name="dedupe_user_symbol_day_signal",
        )

    @staticmethod
    def _normalize_market(market: str) -> str:
        aliases = {"A股": "CN", "美股": "US", "港股": "HK"}
        return aliases.get(str(market or "US").upper(), str(market or "US").upper())

    async def _load_targets(self, user_id: str, request: MonitoringRunRequest) -> List[Dict[str, Any]]:
        watchlist = await watchlist_service.list_watchlist(user_id, include_disabled=request.include_disabled)
        positions = await watchlist_service.list_positions(user_id, include_disabled=request.include_disabled)
        pos_map = {(p["market"], p["symbol"]): p for p in positions}

        merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for item in watchlist:
            market = self._normalize_market(item.get("market"))
            symbol = str(item.get("symbol")).upper()
            if request.market and market != self._normalize_market(request.market):
                continue
            if request.symbols and symbol not in {s.upper() for s in request.symbols}:
                continue
            merged[(market, symbol)] = {
                "symbol": symbol,
                "stock_name": item.get("stock_name") or symbol,
                "market": market,
                "watchlist": item,
                "position": pos_map.get((market, symbol)),
            }

        for position in positions:
            market = self._normalize_market(position.get("market"))
            symbol = str(position.get("symbol")).upper()
            if request.market and market != self._normalize_market(request.market):
                continue
            if request.symbols and symbol not in {s.upper() for s in request.symbols}:
                continue
            merged.setdefault((market, symbol), {
                "symbol": symbol,
                "stock_name": position.get("stock_name") or symbol,
                "market": market,
                "watchlist": None,
                "position": position,
            })

        if request.symbols:
            for raw_symbol in request.symbols:
                symbol = raw_symbol.upper()
                market = self._normalize_market(request.market or ("CN" if symbol.isdigit() else "US"))
                merged.setdefault((market, symbol), {
                    "symbol": symbol.zfill(6) if market == "CN" and symbol.isdigit() else symbol,
                    "stock_name": symbol,
                    "market": market,
                    "watchlist": None,
                    "position": pos_map.get((market, symbol)),
                })

        return list(merged.values())

    async def _get_quote(self, market: str, symbol: str, force_refresh: bool) -> Dict[str, Any]:
        db = self._get_db()
        if market in {"US", "HK"}:
            return await ForeignStockService(db=db).get_quote(market, symbol, force_refresh=force_refresh)

        code = symbol.zfill(6)
        quote = await db.market_quotes.find_one({"code": code}, {"_id": 0})
        if not quote:
            quote = {}
        return {
            "code": code,
            "name": quote.get("name") or code,
            "market": "CN",
            "price": quote.get("close"),
            "close": quote.get("close"),
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "volume": quote.get("volume"),
            "amount": quote.get("amount"),
            "pre_close": quote.get("pre_close"),
            "change_percent": quote.get("pct_chg"),
            "trade_date": quote.get("trade_date"),
            "source": quote.get("data_source") or "market_quotes",
            "updated_at": quote.get("updated_at"),
        }

    async def _get_klines(self, market: str, symbol: str, lookback_days: int, force_refresh: bool) -> List[Dict[str, Any]]:
        limit = max(lookback_days, 30)
        if market in {"US", "HK"}:
            try:
                return await ForeignStockService(db=self._get_db()).get_kline(market, symbol, "day", limit, force_refresh)
            except Exception as e:
                logger.warning("Failed to fetch foreign kline for %s:%s: %s", market, symbol, e)
                return []

        service = await get_historical_data_service()
        start_date = (datetime.utcnow() - timedelta(days=lookback_days * 2)).strftime("%Y-%m-%d")
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        rows = await service.get_historical_data(
            symbol=symbol.zfill(6),
            start_date=start_date,
            end_date=end_date,
            period="daily",
            limit=limit,
        )
        return list(reversed(rows))

    async def _persist_report(
        self,
        *,
        user_id: str,
        run_id: str,
        report: Dict[str, Any],
    ) -> bool:
        db = self._get_db()
        now = now_tz()
        signal_day = now.strftime("%Y-%m-%d")
        signal_doc = {
            "user_id": user_id,
            "run_id": run_id,
            "symbol": report["symbol"],
            "stock_name": report.get("stock_name"),
            "market": report["market"],
            "signal_type": report["signal_type"],
            "signal_day": signal_day,
            "severity": report.get("severity", "info"),
            "score": report.get("score", 0),
            "summary": report.get("summary"),
            "recommendation": report.get("recommendation"),
            "updated_at": now,
        }

        is_new_signal = False
        try:
            result = await db.monitoring_signals.update_one(
                {
                    "user_id": user_id,
                    "symbol": report["symbol"],
                    "signal_day": signal_day,
                    "signal_type": report["signal_type"],
                },
                {"$set": signal_doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
            is_new_signal = bool(result.upserted_id)
        except Exception as e:
            logger.warning("Failed to upsert monitoring signal: %s", e)

        report_doc = dict(report)
        report_doc.update({"user_id": user_id, "run_id": run_id, "created_at": now, "updated_at": now})
        await db.monitoring_reports.insert_one(report_doc)

        evidence_docs = []
        for evidence in report.get("evidence", []):
            evidence_doc = dict(evidence)
            evidence_doc.update({
                "user_id": user_id,
                "run_id": run_id,
                "symbol": report["symbol"],
                "market": report["market"],
                "created_at": now,
            })
            evidence_docs.append(evidence_doc)
        if evidence_docs:
            await db.monitoring_evidence.insert_many(evidence_docs)

        return is_new_signal

    async def _notify(self, user_id: str, report: Dict[str, Any]) -> None:
        severity = report.get("severity", "info")
        if severity not in {"warning", "error", "success"}:
            return

        title = f"{report['symbol']} {report.get('signal_type')} 监控提醒"
        content = report.get("summary", "")[:800]
        await get_notifications_service().create_and_publish(
            NotificationCreate(
                user_id=user_id,
                type="alert",
                title=title,
                content=content,
                link="/monitoring/reports",
                source="watchlist_monitor",
                severity=severity,
                metadata={
                    "symbol": report["symbol"],
                    "market": report["market"],
                    "signal_type": report.get("signal_type"),
                    "score": report.get("score"),
                },
            )
        )

    async def run_for_user(self, user_id: str, request: Optional[MonitoringRunRequest] = None) -> Dict[str, Any]:
        await self.ensure_indexes()
        request = request or MonitoringRunRequest()
        db = self._get_db()
        now = now_tz()
        run_doc = {
            "user_id": user_id,
            "status": "running",
            "parameters": request.model_dump(),
            "created_at": now,
            "updated_at": now,
        }
        result = await db.monitoring_runs.insert_one(run_doc)
        run_id = str(result.inserted_id)

        targets = await self._load_targets(user_id, request)
        reports: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for target in targets:
            if len(reports) >= request.max_deep_analysis:
                break
            symbol = target["symbol"]
            market = target["market"]
            try:
                data_gaps: List[str] = []
                quote: Dict[str, Any] = {}
                klines: List[Dict[str, Any]] = []

                try:
                    quote = await self._get_quote(market, symbol, request.force_refresh)
                except Exception as e:
                    gap = f"行情数据获取失败：{e}"
                    logger.warning("Monitoring quote unavailable for %s:%s: %s", market, symbol, e)
                    data_gaps.append(gap)

                try:
                    klines = await self._get_klines(market, symbol, request.lookback_days, request.force_refresh)
                except Exception as e:
                    gap = f"K线数据获取失败：{e}"
                    logger.warning("Monitoring kline unavailable for %s:%s: %s", market, symbol, e)
                    data_gaps.append(gap)
                has_position = bool(target.get("position"))
                price_signal = evaluate_symbol(
                    quote=quote,
                    klines=klines,
                    has_position=has_position,
                    position=target.get("position"),
                )

                evidence = await self.evidence_collector.collect_news_evidence(
                    symbol=symbol,
                    market=market,
                    days=request.news_days,
                    limit=20,
                    force_refresh=request.force_refresh,
                    db=db,
                )
                evidence_signal = evaluate_evidence_signal(evidence=evidence, has_position=has_position)
                signal = merge_signals(price_signal, evidence_signal)
                if not signal.get("triggered"):
                    continue

                report = build_report(
                    symbol=symbol,
                    stock_name=target.get("stock_name") or quote.get("name") or symbol,
                    market=market,
                    signal=signal,
                    evidence=evidence,
                    has_position=has_position,
                    data_gaps=data_gaps,
                )
                is_new_signal = await self._persist_report(user_id=user_id, run_id=run_id, report=report)
                if is_new_signal:
                    await self._notify(user_id, report)
                reports.append(report)
            except Exception as e:
                logger.exception("Monitoring failed for %s:%s", market, symbol)
                errors.append({"symbol": symbol, "market": market, "error": str(e)})

        completed_at = now_tz()
        await db.monitoring_runs.update_one(
            {"_id": result.inserted_id},
            {"$set": {
                "status": "completed" if not errors else "partial_success",
                "target_count": len(targets),
                "report_count": len(reports),
                "error_count": len(errors),
                "errors": errors,
                "completed_at": completed_at,
                "updated_at": completed_at,
            }},
        )

        return {
            "run_id": run_id,
            "target_count": len(targets),
            "report_count": len(reports),
            "error_count": len(errors),
            "reports": reports,
            "errors": errors,
        }

    async def list_reports(self, user_id: str, limit: int = 50, skip: int = 0) -> Dict[str, Any]:
        await self.ensure_indexes()
        db = self._get_db()
        query = {"user_id": user_id}
        total = await db.monitoring_reports.count_documents(query)
        cursor = db.monitoring_reports.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
        return {"items": await cursor.to_list(length=limit), "total": total}

    async def list_runs(self, user_id: str, limit: int = 20, skip: int = 0) -> Dict[str, Any]:
        await self.ensure_indexes()
        db = self._get_db()
        query = {"user_id": user_id}
        total = await db.monitoring_runs.count_documents(query)
        cursor = db.monitoring_runs.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
        return {"items": await cursor.to_list(length=limit), "total": total}


watchlist_monitor_service = WatchlistMonitorService()
