from __future__ import annotations

import re
from datetime import date

from app.services.smart_screening.schema import SmartScreeningDSL


def parse_natural_language_to_dsl(query: str, *, as_of: date | None = None) -> SmartScreeningDSL:
    text = query.strip()
    lowered = text.lower()
    conditions: list[dict] = []
    sort: list[dict] = []

    industry = _extract_industry(text)
    universe = {"universe_type": "industry", "values": [industry]} if industry else {"universe_type": "all", "values": []}

    if "非st" in lowered or "非 st" in lowered or "不是st" in lowered:
        conditions.append({"condition_type": "value", "field": "is_st", "operator": "==", "value": False})
    if "非停牌" in text or "不停牌" in text:
        conditions.append({"condition_type": "value", "field": "is_suspended", "operator": "==", "value": False})

    for field, aliases in {
        "volume_ratio": ("量比",),
        "turnover_rate": ("换手率",),
        "pct_chg": ("涨跌幅", "单日涨幅", "单日跌幅"),
        "return_5d": ("近5日涨幅", "5日涨幅", "最近5日涨幅"),
        "return_10d": ("近10日涨幅", "10日涨幅", "最近10日涨幅"),
        "return_20d": ("近20日涨幅", "20日涨幅", "最近20日涨幅"),
        "pe": ("pe", "市盈率"),
        "pb": ("pb", "市净率"),
        "roe": ("roe",),
        "revenue_growth": ("营收增长", "收入增长"),
        "net_profit_growth": ("净利润增长", "利润增长"),
    }.items():
        condition = _extract_numeric_condition(text, field, aliases)
        if condition:
            conditions.append(condition)

    rank_condition = _extract_rank_condition(text)
    if rank_condition:
        conditions.append(rank_condition)
        sort.append({"field": rank_condition["field"], "direction": "desc"})

    if _contains_ma_chain(text):
        conditions.extend(
            [
                {"condition_type": "field_compare", "field": "close", "operator": ">", "right_field": "ma5"},
                {"condition_type": "field_compare", "field": "ma5", "operator": ">", "right_field": "ma10"},
            ]
        )

    text_event = _extract_text_event_condition(text, as_of)
    if text_event:
        conditions.append(text_event)

    if not sort:
        sort_field = _extract_sort_field(text)
        if sort_field:
            sort.append({"field": sort_field, "direction": "desc"})

    return SmartScreeningDSL.model_validate(
        {
            "version": "1.0",
            "market": "CN",
            "as_of": as_of.isoformat() if as_of else None,
            "universe": universe,
            "condition_logic": "AND",
            "conditions": conditions,
            "sort": sort,
            "limit": _extract_limit(text),
            "raw_user_query": text,
        }
    )


def _extract_industry(text: str) -> str | None:
    known = ("半导体", "商业航天", "银行", "证券", "保险", "医药", "新能源", "人工智能", "机器人", "芯片")
    for item in known:
        if item in text:
            return "半导体" if item == "芯片" else item
    match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]+?)(?:行业|板块)", text)
    return match.group(1) if match else None


def _extract_numeric_condition(text: str, field: str, aliases: tuple[str, ...]) -> dict | None:
    for alias in aliases:
        escaped = re.escape(alias)
        match = re.search(rf"{escaped}\s*(>=|<=|>|<|大于|高于|超过|小于|低于)\s*(-?\d+(?:\.\d+)?)%?", text, re.IGNORECASE)
        if not match:
            continue
        return {
            "condition_type": "value",
            "field": field,
            "operator": _normalize_operator(match.group(1)),
            "value": float(match.group(2)),
        }
    return None


def _extract_rank_condition(text: str) -> dict | None:
    match = re.search(r"(?:近|最近)?(5|10|20)日涨幅.*?(?:前|top)\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
    if match:
        return {
            "condition_type": "rank",
            "field": f"return_{match.group(1)}d",
            "rank_operator": "top_percentile",
            "threshold": float(match.group(2)),
        }
    match = re.search(r"(?:涨幅|收益|回报).*?(?:前|top)\s*(\d+)", text, re.IGNORECASE)
    if match:
        return {
            "condition_type": "rank",
            "field": "return_5d",
            "rank_operator": "top_n",
            "threshold": int(match.group(1)),
        }
    return None


def _contains_ma_chain(text: str) -> bool:
    normalized = text.replace("日线", "").replace("均线", "").replace(" ", "").lower()
    return "收盘价>5>10" in normalized or "close>ma5>ma10" in normalized or "收盘价>ma5>ma10" in normalized


def _extract_text_event_condition(text: str, as_of: date | None) -> dict | None:
    event_types: list[str] = []
    keywords: list[str] = []
    sources: list[str] = []
    sentiment = None

    if any(word in text for word in ("研报", "券商", "分析师")):
        sources.append("research_report")
    if "公告" in text:
        sources.append("announcement")
    if "新闻" in text or "媒体" in text:
        sources.append("news")
    if any(word in text for word in ("营收增长", "收入增长", "订单", "超预期", "业绩")):
        event_types.extend(["earnings_beat", "guidance_raise"])
        keywords.extend([word for word in ("营收增长", "收入增长", "订单", "超预期", "业绩") if word in text])
        sentiment = "positive"
    if any(word in text for word in ("减持", "监管", "风险警示", "下调")):
        event_types.extend(["shareholder_reduction", "regulatory_risk", "downgrade"])
        keywords.extend([word for word in ("减持", "监管", "风险警示", "下调") if word in text])
        sentiment = "negative"

    if not (event_types or keywords or sources or sentiment):
        return None

    return {
        "condition_type": "text_event",
        "event_types": list(dict.fromkeys(event_types)),
        "keywords": list(dict.fromkeys(keywords)),
        "sources": sources,
        "sentiment": sentiment,
        "date_range": {"start": None, "end": as_of.isoformat() if as_of else None},
    }


def _extract_sort_field(text: str) -> str | None:
    for keyword, field in (("近5日涨幅", "return_5d"), ("近10日涨幅", "return_10d"), ("近20日涨幅", "return_20d"), ("涨幅", "pct_chg")):
        if keyword in text:
            return field
    return None


def _extract_limit(text: str) -> int:
    match = re.search(r"(?:前|top)\s*(\d+)(?!\s*%)", text, re.IGNORECASE)
    if match:
        return max(1, min(500, int(match.group(1))))
    return 50


def _normalize_operator(value: str) -> str:
    return {
        "大于": ">",
        "高于": ">",
        "超过": ">",
        "小于": "<",
        "低于": "<",
    }.get(value, value)
