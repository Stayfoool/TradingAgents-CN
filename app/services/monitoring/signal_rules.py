"""
Deterministic signal rules for watchlist monitoring.
"""
from statistics import mean
from typing import Any, Dict, List, Optional


POSITIVE_EVIDENCE_KEYWORDS = {
    "earnings beat": "财报超预期",
    "beats estimates": "业绩超过预期",
    "beat estimates": "业绩超过预期",
    "revenue beat": "收入超过预期",
    "above estimates": "高于市场预期",
    "above consensus": "高于一致预期",
    "raised guidance": "上调指引",
    "raises guidance": "上调指引",
    "strong guidance": "强劲指引",
    "growth guidance": "增长指引",
    "revenue growth": "收入增长",
    "product revenue": "产品收入增长",
    "margin expansion": "利润率改善",
    "upgrade": "评级上调",
    "price target raised": "目标价上调",
    "业绩超预期": "业绩超预期",
    "上调指引": "上调指引",
    "收入增长": "收入增长",
}

NEGATIVE_EVIDENCE_KEYWORDS = {
    "earnings miss": "财报不及预期",
    "misses estimates": "业绩不及预期",
    "missed estimates": "业绩不及预期",
    "below estimates": "低于市场预期",
    "below consensus": "低于一致预期",
    "cut guidance": "下调指引",
    "cuts guidance": "下调指引",
    "lowered guidance": "下调指引",
    "weak guidance": "疲弱指引",
    "downgrade": "评级下调",
    "price target cut": "目标价下调",
    "lawsuit": "诉讼风险",
    "investigation": "调查风险",
    "sec investigation": "监管调查",
    "layoffs": "裁员",
    "下调指引": "下调指引",
    "业绩不及预期": "业绩不及预期",
    "监管调查": "监管调查",
}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip().replace("%", "").replace(",", "")
            if value in {"", "-"}:
                return None
        return float(value)
    except Exception:
        return None


def _close(item: Dict[str, Any]) -> Optional[float]:
    return _safe_float(item.get("close") or item.get("price"))


def _volume(item: Dict[str, Any]) -> Optional[float]:
    return _safe_float(item.get("volume") or item.get("vol"))


def normalize_klines(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(row: Dict[str, Any]) -> str:
        return str(row.get("trade_date") or row.get("time") or row.get("date") or "")

    rows = [dict(item) for item in items if _close(item) is not None]
    return sorted(rows, key=key)


def _matched_evidence_labels(text: str, keyword_map: Dict[str, str]) -> List[str]:
    lowered = text.lower()
    labels: List[str] = []
    seen = set()
    for keyword, label in keyword_map.items():
        if keyword.lower() in lowered and label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def _evidence_text(item: Dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("source", "title", "summary", "content")
    )


def evaluate_evidence_signal(
    *,
    evidence: List[Dict[str, Any]],
    has_position: bool,
) -> Dict[str, Any]:
    """Build a signal from sourced news/filing evidence, independent of quote availability."""
    positive_hits: List[str] = []
    negative_hits: List[str] = []
    valid_items: List[Dict[str, Any]] = []
    max_confidence = 0.0

    for item in evidence:
        if item.get("status") == "not_found":
            continue
        confidence = _safe_float(item.get("confidence")) or 0.0
        if confidence < 0.45:
            continue

        text = _evidence_text(item)
        item_positive = _matched_evidence_labels(text, POSITIVE_EVIDENCE_KEYWORDS)
        item_negative = _matched_evidence_labels(text, NEGATIVE_EVIDENCE_KEYWORDS)
        if not item_positive and not item_negative:
            continue

        valid_items.append(item)
        max_confidence = max(max_confidence, confidence)
        positive_hits.extend(item_positive)
        negative_hits.extend(item_negative)

    if not valid_items:
        return {
            "triggered": False,
            "score": 0.0,
            "signal_type": "no_action",
            "severity": "info",
            "reasons": [],
            "metrics": {
                "authoritative_evidence_count": 0,
            },
        }

    positive_count = len(positive_hits)
    negative_count = len(negative_hits)
    directional_hits = positive_hits if positive_count >= negative_count else negative_hits
    unique_labels = list(dict.fromkeys(directional_hits))

    score = 2.0 + max_confidence * 3 + min(len(valid_items), 3) * 0.5 + min(len(unique_labels), 4) * 0.3
    score = round(min(score, 7.0), 2)

    if negative_count > positive_count:
        signal_type = "risk_alert" if has_position else "sell_watch"
        severity = "error" if score >= 4.5 else "warning"
        reason_prefix = "权威媒体/公告证据出现风险事件关键词"
    elif has_position:
        signal_type = "hold_confirm"
        severity = "success" if score >= 4 else "info"
        reason_prefix = "权威媒体/公告证据出现积极事件关键词"
    else:
        signal_type = "buy_watch"
        severity = "warning" if score >= 4 else "info"
        reason_prefix = "权威媒体/公告证据出现积极事件关键词"

    reasons = [
        f"{reason_prefix}：{'、'.join(unique_labels[:5])}。",
        f"近窗口内找到 {len(valid_items)} 条相关证据，最高证据置信度 {max_confidence:.2f}。",
    ]

    return {
        "triggered": score >= 2,
        "score": score,
        "signal_type": signal_type,
        "severity": severity,
        "reasons": reasons,
        "metrics": {
            "authoritative_evidence_count": len(valid_items),
            "max_evidence_confidence": round(max_confidence, 2),
            "positive_evidence_hits": list(dict.fromkeys(positive_hits)),
            "negative_evidence_hits": list(dict.fromkeys(negative_hits)),
        },
    }


def _signal_is_negative(signal: Dict[str, Any]) -> bool:
    return signal.get("signal_type") in {"risk_alert", "sell_watch"}


def merge_signals(*signals: Dict[str, Any]) -> Dict[str, Any]:
    """Merge price/trend and evidence signals into one reportable signal."""
    triggered = [signal for signal in signals if signal and signal.get("triggered")]
    if not triggered:
        return signals[0] if signals else {
            "triggered": False,
            "score": 0.0,
            "signal_type": "no_action",
            "severity": "info",
            "reasons": [],
            "metrics": {},
        }

    negative_signals = [signal for signal in triggered if _signal_is_negative(signal)]
    positive_signals = [signal for signal in triggered if not _signal_is_negative(signal)]
    candidates = negative_signals if negative_signals and not positive_signals else triggered
    primary = max(candidates, key=lambda row: _safe_float(row.get("score")) or 0)

    reasons: List[str] = []
    metrics: Dict[str, Any] = {}
    score = 0.0
    for signal in triggered:
        score += _safe_float(signal.get("score")) or 0.0
        metrics.update(signal.get("metrics") or {})
        for reason in signal.get("reasons") or []:
            if reason not in reasons:
                reasons.append(reason)

    severities = [signal.get("severity", "info") for signal in triggered]
    if "error" in severities:
        severity = "error"
    elif "warning" in severities:
        severity = "warning"
    elif "success" in severities:
        severity = "success"
    else:
        severity = "info"

    merged = dict(primary)
    merged.update({
        "triggered": True,
        "score": round(min(score, 10.0), 2),
        "severity": severity,
        "reasons": reasons,
        "metrics": metrics,
    })
    return merged


def evaluate_symbol(
    *,
    quote: Dict[str, Any],
    klines: List[Dict[str, Any]],
    has_position: bool,
    position: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rows = normalize_klines(klines)
    latest = rows[-1] if rows else {}
    current_price = _safe_float(quote.get("price") or quote.get("close") or _close(latest))
    change_percent = _safe_float(quote.get("change_percent") or quote.get("pct_chg"))
    latest_volume = _safe_float(quote.get("volume") or _volume(latest))

    closes = [_close(row) for row in rows if _close(row) is not None]
    volumes = [_volume(row) for row in rows if _volume(row) is not None]

    reasons: List[str] = []
    metrics: Dict[str, Any] = {
        "current_price": current_price,
        "change_percent": change_percent,
        "latest_volume": latest_volume,
    }
    score = 0.0
    positive = 0
    negative = 0

    if change_percent is not None:
        if change_percent >= 5:
            reasons.append(f"单日涨幅达到 {change_percent:.2f}%，超过 5% 异动阈值。")
            score += min(change_percent / 5, 3)
            positive += 1
        elif change_percent <= -5:
            reasons.append(f"单日跌幅达到 {change_percent:.2f}%，超过 -5% 风险阈值。")
            score += min(abs(change_percent) / 5, 3)
            negative += 1

    if closes:
        lookback = closes[-60:] if len(closes) >= 60 else closes
        low_lookback = min(lookback)
        high_20 = max(closes[-20:]) if len(closes) >= 20 else max(closes)
        low_20 = min(closes[-20:]) if len(closes) >= 20 else min(closes)
        metrics.update({"lookback_low": low_lookback, "high_20": high_20, "low_20": low_20})

        if current_price and low_lookback and low_lookback > 0:
            rebound = (current_price / low_lookback - 1) * 100
            metrics["rebound_from_low_pct"] = round(rebound, 2)
            if rebound >= 15:
                reasons.append(f"股价较近阶段低点反弹 {rebound:.2f}%，出现低位修复趋势。")
                score += min(rebound / 15, 3)
                positive += 1

        if current_price and high_20 and current_price >= high_20:
            reasons.append("股价触及或突破近 20 日高点。")
            score += 1.5
            positive += 1

        if current_price and low_20 and current_price <= low_20:
            reasons.append("股价触及或跌破近 20 日低点。")
            score += 1.5
            negative += 1

        if len(closes) >= 5:
            up_days = sum(1 for prev, cur in zip(closes[-5:-1], closes[-4:]) if cur > prev)
            down_days = sum(1 for prev, cur in zip(closes[-5:-1], closes[-4:]) if cur < prev)
            metrics["up_days_last_5"] = up_days
            metrics["down_days_last_5"] = down_days
            if up_days >= 4:
                reasons.append("最近 5 个交易日中至少 4 日上涨，短期趋势偏强。")
                score += 1
                positive += 1
            if down_days >= 4:
                reasons.append("最近 5 个交易日中至少 4 日下跌，短期趋势偏弱。")
                score += 1
                negative += 1

    if volumes and latest_volume:
        base_vols = volumes[-21:-1] if len(volumes) >= 21 else volumes[:-1]
        avg_vol = mean(base_vols) if base_vols else None
        if avg_vol and avg_vol > 0:
            volume_ratio = latest_volume / avg_vol
            metrics["volume_ratio_20d"] = round(volume_ratio, 2)
            if volume_ratio >= 2:
                reasons.append(f"成交量约为近 20 日均量的 {volume_ratio:.2f} 倍，量能明显放大。")
                score += min(volume_ratio / 2, 2)

    if has_position and position and current_price:
        stop_loss = _safe_float(position.get("stop_loss"))
        target_price = _safe_float(position.get("target_price"))
        cost_basis = _safe_float(position.get("cost_basis"))

        if stop_loss and current_price <= stop_loss:
            reasons.append(f"当前价格 {current_price:.2f} 已触及或跌破止损价 {stop_loss:.2f}。")
            score += 3
            negative += 2
        if target_price and current_price >= target_price:
            reasons.append(f"当前价格 {current_price:.2f} 已达到或超过目标价 {target_price:.2f}。")
            score += 2
            positive += 1
        if cost_basis and cost_basis > 0:
            pnl = (current_price / cost_basis - 1) * 100
            metrics["unrealized_pnl_pct"] = round(pnl, 2)
            if pnl <= -8:
                reasons.append(f"较持仓成本浮亏 {abs(pnl):.2f}%，需要复核持仓风险。")
                score += 2
                negative += 1

    if not reasons:
        return {
            "triggered": False,
            "score": 0.0,
            "signal_type": "no_action",
            "severity": "info",
            "reasons": [],
            "metrics": metrics,
        }

    if negative > positive:
        signal_type = "risk_alert" if has_position else "sell_watch"
        severity = "error" if score >= 5 else "warning"
    elif has_position:
        signal_type = "hold_confirm"
        severity = "success" if score >= 4 else "info"
    else:
        signal_type = "buy_watch"
        severity = "warning" if score >= 4 else "info"

    return {
        "triggered": score >= 2,
        "score": round(score, 2),
        "signal_type": signal_type,
        "severity": severity,
        "reasons": reasons,
        "metrics": metrics,
    }
