from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.services.smart_screening.audit import audit_screening_result
from app.services.smart_screening.contracts import get_smart_screening_contracts
from app.services.smart_screening.deep_analysis import build_deep_analysis_tasks
from app.services.smart_screening.llm_dsl import generate_dsl_from_natural_language
from app.services.smart_screening.planner import plan_execution
from app.services.smart_screening.repository import InMemorySmartScreeningRepository, MongoSmartScreeningRepository
from app.services.smart_screening.schema import SmartScreeningDSL
from app.services.smart_screening.service import run_stock_screening_by_dsl
from app.services.smart_screening.synthesis import synthesize_screening_result

router = APIRouter()
logger = logging.getLogger("webapi")


class NaturalLanguageParseRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    as_of: date | None = None
    use_llm: bool = False


class SmartScreeningRunRequest(BaseModel):
    dsl: SmartScreeningDSL
    use_database: bool = True
    include_deep_analysis_tasks: bool = False
    deep_analysis_top_n: int = Field(default=3, ge=1, le=10)


class NaturalLanguageRunRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    as_of: date | None = None
    use_database: bool = True
    use_llm: bool = False
    include_deep_analysis_tasks: bool = False
    deep_analysis_top_n: int = Field(default=3, ge=1, le=10)


def _ok(data: Any, message: str = "ok") -> dict[str, Any]:
    return {"success": True, "data": data, "message": message}


@router.post("/parse")
async def parse_natural_language(req: NaturalLanguageParseRequest, user: dict = Depends(get_current_user)):
    try:
        dsl = generate_dsl_from_natural_language(req.query, as_of=req.as_of, llm=await _get_llm() if req.use_llm else None)
        plan = plan_execution(dsl)
        return _ok({"dsl": dsl.to_audit_dict(), "plan": plan.model_dump(mode="json")}, "智能选股 DSL 生成成功")
    except Exception as exc:
        logger.error(f"[smart_screening.parse] failed: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/plan")
async def create_execution_plan(dsl: SmartScreeningDSL, user: dict = Depends(get_current_user)):
    plan = plan_execution(dsl)
    return _ok(plan.model_dump(mode="json"), "智能选股执行计划生成成功")


@router.post("/run")
async def run_smart_screening(req: SmartScreeningRunRequest, user: dict = Depends(get_current_user)):
    try:
        repository = _get_repository(req.use_database)
        result = await run_stock_screening_by_dsl(req.dsl, repository=repository)
        audit = audit_screening_result(result)
        deep_analysis_tasks = (
            await build_deep_analysis_tasks(result, top_n=req.deep_analysis_top_n) if req.include_deep_analysis_tasks else []
        )
        return _ok(
            {
                **result.model_dump(mode="json"),
                "audit": {**result.audit, **audit.model_dump(mode="json")},
                "deep_analysis_tasks": deep_analysis_tasks,
                "synthesis": synthesize_screening_result(result).model_dump(mode="json"),
            },
            "智能选股执行成功",
        )
    except Exception as exc:
        logger.error(f"[smart_screening.run] failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/run-natural-language")
async def run_smart_screening_from_nl(req: NaturalLanguageRunRequest, user: dict = Depends(get_current_user)):
    try:
        dsl = generate_dsl_from_natural_language(req.query, as_of=req.as_of, llm=await _get_llm() if req.use_llm else None)
        run_req = SmartScreeningRunRequest(
            dsl=dsl,
            use_database=req.use_database,
            include_deep_analysis_tasks=req.include_deep_analysis_tasks,
            deep_analysis_top_n=req.deep_analysis_top_n,
        )
        response = await run_smart_screening(run_req, user)
        response["data"]["dsl"] = dsl.to_audit_dict()
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[smart_screening.run_nl] failed: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _get_repository(use_database: bool):
    if not use_database:
        return InMemorySmartScreeningRepository()
    try:
        from app.core.database import get_mongo_db

        db = get_mongo_db()
        if db is None:
            raise RuntimeError("MongoDB is not initialized")
        return MongoSmartScreeningRepository(db)
    except Exception as exc:
        logger.warning(f"[smart_screening] MongoDB repository unavailable, using sample data: {exc}")
        return InMemorySmartScreeningRepository()


@router.get("/contracts")
async def get_data_contracts(user: dict = Depends(get_current_user)):
    return _ok(get_smart_screening_contracts(), "智能选股数据契约获取成功")


async def _get_llm():
    try:
        from app.services.config_service import config_service
        from tradingagents.llm_clients import create_llm_client

        config = await config_service.get_system_config()
        if not config or not config.default_llm:
            return None
        llm_config = next((item for item in config.llm_configs if item.enabled and item.model_name == config.default_llm), None)
        if llm_config is None:
            return None
        client = create_llm_client(
            provider=llm_config.provider,
            model=llm_config.model_name,
            base_url=llm_config.api_base,
            api_key=llm_config.api_key,
            temperature=0,
            max_tokens=min(llm_config.max_tokens or 4000, 4000),
            timeout=llm_config.timeout,
        )
        return client.get_llm()
    except Exception as exc:
        logger.warning(f"[smart_screening] LLM DSL generator unavailable, using rule parser: {exc}")
        return None
