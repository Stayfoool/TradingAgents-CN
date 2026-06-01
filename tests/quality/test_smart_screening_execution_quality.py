from __future__ import annotations

import pytest

from app.services.smart_screening.audit import audit_screening_result
from app.services.smart_screening.deep_analysis import build_deep_analysis_tasks
from app.services.smart_screening.llm_dsl import generate_dsl_from_natural_language
from app.services.smart_screening.planner import plan_execution
from app.services.smart_screening.repository import InMemorySmartScreeningRepository
from app.services.smart_screening.repository import build_mongo_match_query
from app.services.smart_screening.schema import SmartScreeningDSL
from app.services.smart_screening.service import run_stock_screening_by_dsl
from app.services.smart_screening.synthesis import synthesize_screening_result


def _mixed_screening_dsl() -> dict:
    return {
        "version": "1.0",
        "market": "CN",
        "as_of": "2026-05-31",
        "universe": {"universe_type": "industry", "values": ["半导体"]},
        "condition_logic": "AND",
        "conditions": [
            {
                "condition_type": "rank",
                "field": "return_5d",
                "rank_operator": "top_percentile",
                "threshold": 50,
            },
            {"condition_type": "value", "field": "volume_ratio", "operator": ">", "value": 1.2},
            {"condition_type": "value", "field": "turnover_rate", "operator": ">", "value": 3},
            {"condition_type": "field_compare", "field": "close", "operator": ">", "right_field": "ma5"},
            {"condition_type": "field_compare", "field": "ma5", "operator": ">", "right_field": "ma10"},
            {"condition_type": "value", "field": "is_st", "operator": "==", "value": False},
            {
                "condition_type": "text_event",
                "event_types": ["earnings_beat"],
                "keywords": ["营收增长"],
                "sources": ["research_report"],
                "date_range": {"start": "2026-05-01", "end": "2026-05-31"},
            },
        ],
        "sort": [{"field": "return_5d", "direction": "desc"}],
        "limit": 20,
        "raw_user_query": "半导体，近5日涨幅排名前50%，量比>1.2，换手率>3%，收盘价>5日线>10日线，非ST，并有营收增长研报",
    }


def test_execution_planner_collects_modes_fields_and_collections():
    plan = plan_execution(_mixed_screening_dsl())

    assert plan.is_valid is True
    assert "historical_factor" in plan.required_execution_modes
    assert "dynamic_price_calc" in plan.required_execution_modes
    assert "text_event_search" in plan.required_execution_modes
    assert "stock_daily_factors" in plan.source_collections
    assert "stock_text_events" in plan.source_collections
    assert "return_5d" in plan.referenced_fields
    assert plan.needs_text_events is True


@pytest.mark.asyncio
async def test_run_stock_screening_by_dsl_returns_candidates_with_evidence():
    result = await run_stock_screening_by_dsl(_mixed_screening_dsl())

    assert result.total == 1
    assert result.items[0].symbol == "688001"
    assert result.items[0].data["return_5d"] == 18.4
    assert any(evidence.evidence_type == "text_event" for evidence in result.items[0].evidence)
    assert all("未来新闻" not in str(evidence.summary) for evidence in result.items[0].evidence)

    audit = audit_screening_result(result)
    assert audit.passed is True
    assert audit.checked_candidates == 1
    assert audit.checked_evidence >= 1


@pytest.mark.asyncio
async def test_top_candidates_can_be_converted_to_existing_analyst_tasks():
    result = await run_stock_screening_by_dsl(_mixed_screening_dsl())

    tasks = await build_deep_analysis_tasks(result, top_n=1)

    assert tasks == [
        {
            "symbol": "688001",
            "name": "样例半导体A",
            "analysts": ["market", "fundamentals", "news"],
            "reason": "智能选股候选股，可进入现有 market/fundamentals/news analyst 深度分析。",
            "context": {
                "score": result.items[0].score,
                "matched_conditions": result.items[0].matched_conditions,
                "reasons": result.items[0].reasons,
                "evidence": [item.model_dump(mode="json", exclude_none=True) for item in result.items[0].evidence],
            },
        }
    ]


def test_audit_flags_candidates_without_traceable_evidence():
    from app.services.smart_screening.service import ScreeningCandidate, SmartScreeningResult

    result = SmartScreeningResult(
        total=1,
        items=[ScreeningCandidate(symbol="000001", matched_conditions=["conditions[0]"], evidence=[])],
        plan=plan_execution({"version": "1.0", "market": "CN", "conditions": []}),
        audit={},
    )

    audit = audit_screening_result(result)

    assert audit.passed is False
    assert "000001 has matched conditions but no evidence" in audit.issues


@pytest.mark.asyncio
async def test_dynamic_price_fields_are_calculated_from_daily_quotes_when_factors_are_missing():
    rows = []
    for index, close in enumerate([10, 11, 12, 13, 14, 15], start=1):
        rows.append(
            {
                "symbol": "600001",
                "name": "动态计算样例",
                "market": "CN",
                "industry": "半导体",
                "is_st": False,
                "date": f"2026-05-{25 + index:02d}",
                "open": close - 0.2,
                "high": close + 0.3,
                "low": close - 0.4,
                "close": close,
                "volume": 1000000,
                "amount": 10000000,
                "volume_ratio": 1.5,
                "turnover_rate": 4.0,
            }
        )
    latest_without_factors = [rows[-1] | {"ma5": None, "return_5d": None, "pct_chg": None}]
    repository = InMemorySmartScreeningRepository(stock_rows=latest_without_factors, text_events=[])

    async def load_price_history(**kwargs):
        return rows

    repository.load_price_history = load_price_history  # type: ignore[method-assign]
    dsl = {
        "version": "1.0",
        "market": "CN",
        "as_of": "2026-05-31",
        "universe": {"universe_type": "industry", "values": ["半导体"]},
        "conditions": [{"condition_type": "field_compare", "field": "close", "operator": ">", "right_field": "ma5"}],
        "sort": [{"field": "return_5d", "direction": "desc"}],
    }

    result = await run_stock_screening_by_dsl(dsl, repository=repository)

    assert result.total == 1
    assert result.items[0].data["ma5"] == 13
    assert result.items[0].data["return_5d"] == 50
    assert result.items[0].data["pct_chg"] == pytest.approx(7.1429)


def test_fake_llm_can_generate_valid_dsl_json():
    class FakeLLM:
        def invoke(self, messages):
            return type(
                "Response",
                (),
                {
                    "content": '{"version":"1.0","market":"CN","as_of":"2026-05-31","universe":{"universe_type":"industry","values":["半导体"]},"conditions":[{"condition_type":"value","field":"volume_ratio","operator":">","value":1.2}],"sort":[],"limit":20}'
                },
            )()

    dsl = generate_dsl_from_natural_language("半导体量比>1.2", llm=FakeLLM())

    assert dsl.universe.values == ["半导体"]
    assert dsl.conditions[0].field == "volume_ratio"


@pytest.mark.asyncio
async def test_synthesis_summarizes_screening_result():
    result = await run_stock_screening_by_dsl(_mixed_screening_dsl())

    synthesis = synthesize_screening_result(result)

    assert synthesis.top_symbols == ["688001"]
    assert "返回 1 只候选股" in synthesis.summary
    assert synthesis.key_reasons


@pytest.mark.asyncio
async def test_text_event_future_data_is_not_used_when_as_of_blocks_it():
    dsl = _mixed_screening_dsl()
    dsl["conditions"][-1] = {
        "condition_type": "text_event",
        "event_types": ["earnings_beat"],
        "keywords": ["未来新闻"],
        "sources": ["news"],
        "date_range": {"start": "2026-05-01", "end": "2026-05-31"},
    }

    result = await run_stock_screening_by_dsl(dsl)

    assert result.total == 0
    assert result.items == []


def test_mongo_query_builder_preserves_market_date_and_universe_filters():
    dsl = SmartScreeningDSL.model_validate(_mixed_screening_dsl())

    query = build_mongo_match_query(dsl)

    assert query["market"] == {"$in": ["CN", "A股"]}
    assert query["date"] == {"$lte": "2026-05-31"}
    assert query["industry"] == {"$in": ["半导体"]}
