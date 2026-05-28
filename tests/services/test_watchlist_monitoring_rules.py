from app.services.monitoring.evidence_collector import score_news_item
from app.services.monitoring.report_builder import build_report
from app.services.monitoring.signal_rules import evaluate_evidence_signal, evaluate_symbol, merge_signals


def test_evaluate_symbol_detects_rebound_and_volume_breakout():
    klines = [
        {"time": f"2026-04-{day:02d}", "close": close, "volume": 1000}
        for day, close in enumerate([90, 88, 87, 89, 92, 95, 99, 104, 108, 112], start=1)
    ]
    quote = {"price": 112, "change_percent": 6.2, "volume": 2600}

    result = evaluate_symbol(quote=quote, klines=klines, has_position=False)

    assert result["triggered"] is True
    assert result["signal_type"] == "buy_watch"
    assert any("单日涨幅" in reason for reason in result["reasons"])
    assert any("反弹" in reason for reason in result["reasons"])


def test_evaluate_symbol_detects_position_stop_loss_risk():
    klines = [
        {"time": f"2026-04-{day:02d}", "close": close, "volume": 1000}
        for day, close in enumerate([120, 118, 116, 114, 111, 109, 105, 101], start=1)
    ]
    quote = {"price": 101, "change_percent": -6.5, "volume": 1500}
    position = {"cost_basis": 120, "stop_loss": 105}

    result = evaluate_symbol(quote=quote, klines=klines, has_position=True, position=position)

    assert result["triggered"] is True
    assert result["signal_type"] == "risk_alert"
    assert any("止损" in reason for reason in result["reasons"])


def test_authoritative_news_scores_higher():
    item = {
        "source": "Benzinga",
        "title": "SNOW earnings beat as revenue growth accelerates",
        "summary": "Snowflake raised guidance after a strong quarter.",
        "url": "https://example.com/snow",
    }

    assert score_news_item(item, "SNOW") >= 0.8


def test_authoritative_positive_evidence_can_trigger_buy_watch_without_quote():
    evidence = [{
        "type": "authoritative_media",
        "source": "Benzinga",
        "title": "SNOW earnings beat as revenue growth accelerates",
        "summary": "Snowflake raised guidance and product revenue growth outlook after a strong quarter.",
        "url": "https://example.com/snow",
        "confidence": 0.9,
    }]

    result = evaluate_evidence_signal(evidence=evidence, has_position=False)

    assert result["triggered"] is True
    assert result["signal_type"] == "buy_watch"
    assert result["metrics"]["authoritative_evidence_count"] == 1
    assert any("积极事件关键词" in reason for reason in result["reasons"])


def test_authoritative_negative_evidence_can_trigger_risk_alert_for_position():
    evidence = [{
        "type": "authoritative_media",
        "source": "Reuters",
        "title": "Company cuts guidance after earnings miss",
        "summary": "Management lowered guidance and missed estimates.",
        "url": "https://example.com/risk",
        "confidence": 0.88,
    }]

    result = evaluate_evidence_signal(evidence=evidence, has_position=True)

    assert result["triggered"] is True
    assert result["signal_type"] == "risk_alert"
    assert result["severity"] == "error"


def test_merge_signals_keeps_price_and_evidence_reasons():
    price_signal = evaluate_symbol(
        quote={"price": 112, "change_percent": 6.2, "volume": 2600},
        klines=[
            {"time": f"2026-04-{day:02d}", "close": close, "volume": 1000}
            for day, close in enumerate([90, 88, 87, 89, 92, 95, 99, 104, 108, 112], start=1)
        ],
        has_position=False,
    )
    evidence_signal = evaluate_evidence_signal(
        evidence=[{
            "type": "authoritative_media",
            "source": "Zacks",
            "title": "SNOW Q1 revenues beat estimates",
            "summary": "Revenue was above estimates and guidance was strong.",
            "url": "https://example.com/zacks",
            "confidence": 0.82,
        }],
        has_position=False,
    )

    result = merge_signals(price_signal, evidence_signal)

    assert result["triggered"] is True
    assert result["signal_type"] == "buy_watch"
    assert result["score"] > price_signal["score"]
    assert any("单日涨幅" in reason for reason in result["reasons"])
    assert any("积极事件关键词" in reason for reason in result["reasons"])


def test_report_records_quote_data_gap():
    report = build_report(
        symbol="SNOW",
        stock_name="Snowflake",
        market="US",
        signal={
            "triggered": True,
            "score": 4.0,
            "signal_type": "buy_watch",
            "severity": "warning",
            "reasons": ["权威媒体/公告证据出现积极事件关键词：收入增长。"],
            "metrics": {"current_price": None, "change_percent": None},
        },
        evidence=[{
            "type": "authoritative_media",
            "source": "Benzinga",
            "title": "Snowflake raises guidance",
            "confidence": 0.9,
        }],
        has_position=False,
        data_gaps=["行情数据获取失败：Alpha Vantage API Key 未配置"],
    )

    assert "行情数据获取失败" in report["data_gaps"][0]
    assert "数据缺口" in report["summary"]
