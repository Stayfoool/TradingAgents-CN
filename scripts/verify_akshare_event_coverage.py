#!/usr/bin/env python3
"""Verify whether AKShare interfaces contain event keywords.

This script is intentionally read-only. It queries a small set of AKShare
news/market/financial endpoints and reports keyword matches so we can evaluate
coverage before relying on a data source for major market-moving events.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
from dataclasses import dataclass
from typing import Any, Callable


DEFAULT_KEYWORDS = [
    "MiniMax",
    "minimax",
    "戴尔",
    "Dell",
    "DELL",
]


@dataclass
class SourceSpec:
    name: str
    fn_name: str
    kwargs: dict[str, Any]


def _query_source(
    queue: mp.Queue,
    spec: SourceSpec,
    keywords: list[str],
    max_matches: int,
) -> None:
    try:
        import akshare as ak
        import pandas as pd

        fn: Callable[..., Any] = getattr(ak, spec.fn_name)
        df = fn(**spec.kwargs)
        if df is None or getattr(df, "empty", True):
            queue.put(
                {
                    "source": spec.name,
                    "status": "empty",
                    "rows": 0,
                    "columns": [],
                    "matches": [],
                }
            )
            return

        text_df = df.astype(str)
        mask = pd.Series(False, index=df.index)
        for keyword in keywords:
            mask = mask | text_df.apply(
                lambda row: row.str.contains(
                    keyword,
                    case=False,
                    regex=False,
                    na=False,
                ).any(),
                axis=1,
            )

        matches_df = df[mask]
        columns = [str(col) for col in df.columns]
        matches = []
        for _, row in matches_df.head(max_matches).iterrows():
            matches.append({str(col): str(row[col])[:300] for col in columns[:12]})

        queue.put(
            {
                "source": spec.name,
                "status": "ok",
                "rows": int(len(df)),
                "columns": columns,
                "match_count": int(len(matches_df)),
                "matches": matches,
            }
        )
    except Exception as exc:  # pragma: no cover - diagnostic script
        queue.put(
            {
                "source": spec.name,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )


def run_source(
    spec: SourceSpec,
    keywords: list[str],
    max_matches: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    queue: mp.Queue = mp.Queue()
    process = mp.Process(
        target=_query_source,
        args=(queue, spec, keywords, max_matches),
        daemon=True,
    )
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(3)
        return {
            "source": spec.name,
            "status": "timeout",
            "timeout_seconds": timeout_seconds,
        }

    if queue.empty():
        return {
            "source": spec.name,
            "status": "no_result",
        }
    return queue.get()


def build_sources(us_stock: str | None) -> list[SourceSpec]:
    sources = [
        SourceSpec("stock_info_global_em", "stock_info_global_em", {}),
        SourceSpec("stock_info_global_sina", "stock_info_global_sina", {}),
        SourceSpec("stock_info_global_futu", "stock_info_global_futu", {}),
        SourceSpec("stock_info_global_ths", "stock_info_global_ths", {}),
        SourceSpec("stock_info_global_cls_all", "stock_info_global_cls", {"symbol": "全部"}),
        SourceSpec("stock_us_spot_em", "stock_us_spot_em", {}),
        SourceSpec("stock_us_famous_spot_em", "stock_us_famous_spot_em", {}),
    ]

    if us_stock:
        for statement in ["综合损益表", "资产负债表", "现金流量表"]:
            sources.append(
                SourceSpec(
                    f"stock_financial_us_report_em_{us_stock}_{statement}_quarterly",
                    "stock_financial_us_report_em",
                    {
                        "stock": us_stock,
                        "symbol": statement,
                        "indicator": "单季报",
                    },
                )
            )
    return sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify event keyword coverage in selected AKShare endpoints.",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        help="Keyword to search. Can be repeated. Defaults to MiniMax/Dell examples.",
    )
    parser.add_argument(
        "--us-stock",
        default="DELL",
        help="US stock symbol for AKShare financial report checks. Use empty string to skip.",
    )
    parser.add_argument("--timeout", type=int, default=20, help="Per-source timeout seconds.")
    parser.add_argument("--max-matches", type=int, default=8, help="Max matches printed per source.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    keywords = args.keywords or DEFAULT_KEYWORDS
    us_stock = args.us_stock.strip() if args.us_stock else None

    print("AKShare event coverage verification")
    print("keywords:", ", ".join(keywords))
    print("us_stock:", us_stock or "(skipped)")
    print()

    for spec in build_sources(us_stock):
        result = run_source(
            spec,
            keywords=keywords,
            max_matches=args.max_matches,
            timeout_seconds=args.timeout,
        )
        print(f"[{result['source']}] status={result['status']}")
        if result["status"] == "ok":
            print(
                f"  rows={result['rows']} matches={result.get('match_count', 0)} "
                f"columns={result['columns'][:12]}"
            )
            for match in result.get("matches", []):
                print("  MATCH", match)
        elif result["status"] == "error":
            print(f"  error={result['error']}")
        elif result["status"] == "timeout":
            print(f"  timeout_seconds={result['timeout_seconds']}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
