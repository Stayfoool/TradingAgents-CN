#!/usr/bin/env python3
"""Verify whether TuShare endpoints contain required event data.

The script reads a Tushare token from TUSHARE_TOKEN or the project database
and never prints it. It is read-only and intended for checking permissions
and keyword coverage before selecting TuShare as a production data source.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from typing import Any


DEFAULT_KEYWORDS = [
    "MiniMax",
    "minimax",
    "戴尔",
    "Dell",
    "DELL",
    "大基金",
    "减持",
    "半导体",
    "芯片",
]

DEFAULT_NEWS_SOURCES = [
    "sina",
    "10jqka",
    "eastmoney",
    "yuncaijing",
    "fenghuang",
    "jinrongjie",
    "wallstreetcn",
    "cls",
    "yicai",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify TuShare permission and keyword coverage.",
    )
    parser.add_argument("--keyword", action="append", dest="keywords")
    parser.add_argument("--start-date", help="YYYY-MM-DD or YYYYMMDD")
    parser.add_argument("--end-date", help="YYYY-MM-DD or YYYYMMDD")
    parser.add_argument("--news-source", action="append", dest="news_sources")
    parser.add_argument("--max-rows", type=int, default=20)
    parser.add_argument("--sample-symbol", default="000001.SZ")
    parser.add_argument("--skip-news", action="store_true")
    parser.add_argument("--skip-announcements", action="store_true")
    parser.add_argument("--skip-daily", action="store_true")
    parser.add_argument(
        "--token-source",
        choices=["auto", "env", "database"],
        default="auto",
        help="Where to read Tushare token from. auto uses env first, then project database.",
    )
    return parser.parse_args()


def _valid_token(value: str | None) -> bool:
    if not value:
        return False
    text = str(value).strip().strip('"').strip("'")
    if not text or len(text) <= 10:
        return False
    if text.startswith("your_") or text.startswith("your-"):
        return False
    if text.endswith("_here") or text.endswith("-here"):
        return False
    if "..." in text:
        return False
    return True


def _read_token_from_database() -> str | None:
    try:
        from pymongo import MongoClient
        from app.core.config import settings

        client = MongoClient(settings.MONGO_URI)
        db = client[settings.MONGO_DB]
        doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
        if not doc:
            return None
        for data_source in doc.get("data_source_configs", []):
            name = str(data_source.get("name", ""))
            source_type = str(data_source.get("type", ""))
            token = data_source.get("api_key")
            if "tushare" in name.lower() or "tushare" in source_type.lower():
                if _valid_token(token):
                    return str(token).strip().strip('"').strip("'")
    except Exception as exc:  # pragma: no cover - diagnostic script
        print(f"[token database] error {type(exc).__name__}: {exc}")
    return None


def read_token(token_source: str) -> tuple[str | None, str]:
    env_token = os.getenv("TUSHARE_TOKEN")
    if token_source in {"auto", "env"} and _valid_token(env_token):
        return str(env_token).strip().strip('"').strip("'"), "env"
    if token_source in {"auto", "database"}:
        db_token = _read_token_from_database()
        if _valid_token(db_token):
            return db_token, "database"
    return None, "none"


def yyyymmdd(value: str) -> str:
    text = str(value).strip()
    if "-" in text:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y%m%d")
    return text


def news_datetime(value: str, end: bool = False) -> str:
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        dt = datetime.strptime(text, "%Y%m%d")
    else:
        dt = datetime.strptime(text, "%Y-%m-%d")
    suffix = "23:59:59" if end else "00:00:00"
    return f"{dt.strftime('%Y-%m-%d')} {suffix}"


def default_dates() -> tuple[str, str]:
    end = datetime.now()
    start = end - timedelta(days=7)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def row_matches(row: Any, keywords: list[str]) -> bool:
    text = " ".join(str(value) for value in row.to_dict().values())
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def print_matches(df, source: str, keywords: list[str], max_rows: int) -> None:
    if df is None or df.empty:
        print(f"[{source}] ok rows=0 matches=0")
        return
    matches = df[df.apply(lambda row: row_matches(row, keywords), axis=1)]
    print(f"[{source}] ok rows={len(df)} matches={len(matches)} columns={list(df.columns)[:12]}")
    for _, row in matches.head(max_rows).iterrows():
        print("  MATCH", {str(col): str(row[col])[:300] for col in list(df.columns)[:12]})


def main() -> int:
    args = parse_args()
    token, token_source = read_token(args.token_source)
    if not token:
        print("ERROR: no valid Tushare token found from requested source.")
        return 2

    keywords = args.keywords or DEFAULT_KEYWORDS
    start_raw, end_raw = default_dates()
    start_raw = args.start_date or start_raw
    end_raw = args.end_date or end_raw
    start_day = yyyymmdd(start_raw)
    end_day = yyyymmdd(end_raw)
    start_dt = news_datetime(start_day)
    end_dt = news_datetime(end_day, end=True)
    news_sources = args.news_sources or DEFAULT_NEWS_SOURCES

    import tushare as ts

    pro = ts.pro_api(token)

    print("TuShare event coverage verification")
    print(f"token: (hidden, source={token_source})")
    print("keywords:", ", ".join(keywords))
    print("date_range:", start_day, "->", end_day)
    print()

    if not args.skip_daily:
        try:
            df = pro.daily(ts_code=args.sample_symbol, start_date=start_day, end_date=end_day)
            print(f"[daily {args.sample_symbol}] ok rows={0 if df is None else len(df)} columns={[] if df is None else list(df.columns)[:12]}")
        except Exception as exc:
            print(f"[daily {args.sample_symbol}] error {type(exc).__name__}: {exc}")
        print()

    if not args.skip_news:
        for source in news_sources:
            try:
                df = pro.news(src=source, start_date=start_dt, end_date=end_dt)
                print_matches(df, f"news src={source}", keywords, args.max_rows)
            except Exception as exc:
                print(f"[news src={source}] error {type(exc).__name__}: {exc}")
            print()

    if not args.skip_announcements:
        current = datetime.strptime(start_day, "%Y%m%d")
        end_date = datetime.strptime(end_day, "%Y%m%d")
        while current <= end_date:
            ann_date = current.strftime("%Y%m%d")
            try:
                df = pro.anns_d(ann_date=ann_date)
                print_matches(df, f"anns_d ann_date={ann_date}", keywords, args.max_rows)
            except Exception as exc:
                print(f"[anns_d ann_date={ann_date}] error {type(exc).__name__}: {exc}")
            print()
            current += timedelta(days=1)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
