from app.services.monitoring.evidence_collector import score_news_item
from app.services.monitoring.signal_rules import evaluate_symbol


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
