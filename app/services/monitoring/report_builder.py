"""
Build deterministic monitoring report summaries from evidence.
"""
from typing import Any, Dict, List


def _evidence_titles(evidence: List[Dict[str, Any]]) -> List[str]:
    titles = []
    for item in evidence:
        if item.get("status") == "not_found":
            titles.append("未找到白名单权威媒体证据")
        elif item.get("title"):
            source = item.get("source") or "unknown"
            titles.append(f"{source}: {item.get('title')}")
    return titles


def build_recommendation(signal_type: str, has_position: bool, metrics: Dict[str, Any]) -> str:
    price = metrics.get("current_price")
    if signal_type == "risk_alert":
        return "优先复核持仓风险；如已跌破止损或基本面证据转弱，考虑减仓或退出。"
    if signal_type == "sell_watch":
        return "暂不新开仓；等待下跌动能缓和、证据改善后再复核。"
    if signal_type == "hold_confirm":
        if has_position:
            return "继续持有并设置回撤止盈；若后续媒体/财报证据转弱再复核。"
        return "保持观察。"
    if signal_type == "buy_watch":
        if price:
            return "进入买入观察；避免追高，等待回踩、放量延续或下一次财报/指引确认。"
        return "进入买入观察；等待价格和基本面证据进一步确认。"
    return "暂无操作建议。"


def build_report(
    *,
    symbol: str,
    stock_name: str,
    market: str,
    signal: Dict[str, Any],
    evidence: List[Dict[str, Any]],
    has_position: bool,
) -> Dict[str, Any]:
    metrics = signal.get("metrics", {})
    signal_type = signal.get("signal_type", "no_action")
    reasons = list(signal.get("reasons", []))
    evidence_titles = _evidence_titles(evidence)
    recommendation = build_recommendation(signal_type, has_position, metrics)

    summary_lines = [
        f"{symbol} {stock_name or ''} 触发 {signal_type} 信号。",
        f"当前价格：{metrics.get('current_price')}; 涨跌幅：{metrics.get('change_percent')}%。",
    ]
    if reasons:
        summary_lines.append("主要触发原因：" + "；".join(reasons[:4]))
    if evidence_titles:
        summary_lines.append("媒体证据：" + "；".join(evidence_titles[:3]))

    return {
        "symbol": symbol,
        "stock_name": stock_name,
        "market": market,
        "signal_type": signal_type,
        "severity": signal.get("severity", "info"),
        "score": signal.get("score", 0),
        "summary": "\n".join(summary_lines),
        "reasons": reasons,
        "metrics": metrics,
        "evidence": evidence,
        "recommendation": recommendation,
        "has_position": has_position,
        "data_gaps": [
            item.get("reason")
            for item in evidence
            if item.get("status") == "not_found" and item.get("reason")
        ],
    }
