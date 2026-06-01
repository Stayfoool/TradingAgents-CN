from app.services.smart_screening.registry import ExecutionMode, get_field_spec, normalize_field_name
from app.services.smart_screening.schema import SmartScreeningDSL
from app.services.smart_screening.validator import validate_dsl


def _valid_mixed_dsl() -> dict:
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
                "threshold": 5,
            },
            {
                "condition_type": "value",
                "field": "volume_ratio",
                "operator": ">",
                "value": 1.2,
            },
            {
                "condition_type": "field_compare",
                "field": "close",
                "operator": ">",
                "right_field": "ma5",
            },
            {
                "condition_type": "field_compare",
                "field": "ma5",
                "operator": ">",
                "right_field": "ma10",
            },
            {
                "condition_type": "value",
                "field": "is_st",
                "operator": "==",
                "value": False,
            },
            {
                "condition_type": "text_event",
                "event_types": ["earnings_beat", "guidance_raise"],
                "keywords": ["订单", "营收增长"],
                "sources": ["announcement", "research_report"],
                "date_range": {"start": "2026-05-01", "end": "2026-05-31"},
            },
        ],
        "sort": [{"field": "return_5d", "direction": "desc"}],
        "limit": 20,
    }


def test_smart_screening_dsl_accepts_mixed_factor_and_text_query():
    dsl = SmartScreeningDSL.model_validate(_valid_mixed_dsl())
    result = validate_dsl(dsl)

    assert result.is_valid is True
    assert result.issues == []
    assert "return_5d" in result.referenced_fields
    assert "volume_ratio" in result.referenced_fields
    assert "is_st" in result.referenced_fields
    assert ExecutionMode.HISTORICAL_FACTOR in result.required_execution_modes
    assert ExecutionMode.DYNAMIC_PRICE_CALC in result.required_execution_modes
    assert ExecutionMode.TEXT_EVENT_SEARCH in result.required_execution_modes


def test_smart_screening_validator_rejects_unknown_fields():
    dsl = _valid_mixed_dsl()
    dsl["conditions"][0]["field"] = "magic_alpha"

    result = validate_dsl(dsl)

    assert result.is_valid is False
    assert any(issue.code == "unknown_field" for issue in result.issues)


def test_smart_screening_validator_rejects_unsupported_operator():
    dsl = _valid_mixed_dsl()
    dsl["conditions"][1] = {
        "condition_type": "value",
        "field": "close",
        "operator": "contains",
        "value": "10",
    }

    result = validate_dsl(dsl)

    assert result.is_valid is False
    assert any(issue.code == "unsupported_operator" for issue in result.issues)


def test_smart_screening_validator_rejects_incompatible_field_compare():
    dsl = _valid_mixed_dsl()
    dsl["conditions"][2] = {
        "condition_type": "field_compare",
        "field": "close",
        "operator": ">",
        "right_field": "industry",
    }

    result = validate_dsl(dsl)

    assert result.is_valid is False
    assert any(issue.code == "incompatible_field_types" for issue in result.issues)


def test_smart_screening_validator_rejects_invalid_rank_threshold():
    dsl = _valid_mixed_dsl()
    dsl["conditions"][0]["threshold"] = 101

    result = validate_dsl(dsl)

    assert result.is_valid is False
    assert any(issue.code == "invalid_rank_threshold" for issue in result.issues)


def test_smart_screening_validator_rejects_future_text_events():
    dsl = _valid_mixed_dsl()
    dsl["conditions"][-1]["date_range"]["end"] = "2026-06-02"

    result = validate_dsl(dsl)

    assert result.is_valid is False
    assert any(issue.code == "future_text_event" for issue in result.issues)


def test_smart_screening_registry_normalizes_aliases():
    assert normalize_field_name("code") == "symbol"
    assert get_field_spec("price").name == "close"
