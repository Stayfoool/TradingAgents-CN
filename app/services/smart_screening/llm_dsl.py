from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Protocol

from app.services.smart_screening.nl_parser import parse_natural_language_to_dsl
from app.services.smart_screening.schema import SmartScreeningDSL


class DSLGeneratorLLM(Protocol):
    def invoke(self, messages: list[dict[str, str]]) -> Any:
        ...


def generate_dsl_from_natural_language(
    query: str,
    *,
    as_of: date | None = None,
    llm: DSLGeneratorLLM | None = None,
) -> SmartScreeningDSL:
    if llm is None:
        return parse_natural_language_to_dsl(query, as_of=as_of)

    response = llm.invoke(
        [
            {
                "role": "system",
                "content": (
                    "你是股票智能选股 DSL 生成器。只输出 JSON，不要输出解释。"
                    "DSL version 必须是 1.0，字段必须使用系统注册字段，LLM 不允许生成数据库查询代码。"
                ),
            },
            {"role": "user", "content": query},
        ]
    )
    content = getattr(response, "content", response)
    if not isinstance(content, str):
        content = str(content)
    payload = json.loads(_extract_json(content))
    if as_of and not payload.get("as_of"):
        payload["as_of"] = as_of.isoformat()
    if not payload.get("raw_user_query"):
        payload["raw_user_query"] = query
    return SmartScreeningDSL.model_validate(payload)


def _extract_json(content: str) -> str:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if match:
        return match.group(1)
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        return content[start : end + 1]
    return content
