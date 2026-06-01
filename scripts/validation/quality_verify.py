#!/usr/bin/env python3
"""
Unified quality gate runner for TradingAgents-CN development.

The script keeps local, server, and CI checks aligned without depending on a
shell-specific Makefile. It intentionally separates fast pre-commit checks from
slower frontend and browser checks.
"""
from __future__ import annotations

import argparse
import ast
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

BACKEND_SYNTAX_PATHS = (
    PROJECT_ROOT / "app",
    PROJECT_ROOT / "tradingagents",
    PROJECT_ROOT / "scripts" / "validation",
    PROJECT_ROOT / "tests" / "quality",
    PROJECT_ROOT / "tests" / "services",
    PROJECT_ROOT / "tests" / "tradingagents",
)

PYTEST_QUALITY_TARGETS = ("tests/quality",)

PYTEST_SERVICE_TARGETS = (
    "tests/quality",
    "tests/services/test_watchlist_monitoring_rules.py",
    "tests/services/test_screening_roe_field.py",
    "tests/services/test_quotes_ingestion_and_enrichment.py",
    "tests/services/test_quotes_backfill.py",
    "tests/tradingagents/test_app_cache_toggle.py",
)

RUFF_TARGETS = (
    "scripts/validation/quality_verify.py",
    "scripts/validation/monitoring_quality_gate.py",
    "tests/quality",
)


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: Sequence[str]
    cwd: Path = PROJECT_ROOT
    env: dict[str, str] | None = None


def _print_step(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def _run(step: CommandStep) -> None:
    _print_step(step.name)
    env = os.environ.copy()
    if step.env:
        env.update(step.env)
    print("$ " + " ".join(step.command), flush=True)
    subprocess.run(step.command, cwd=step.cwd, env=env, check=True)


def _iter_python_files(paths: Iterable[Path]) -> Iterable[Path]:
    ignored_dirs = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "node_modules",
    }
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            yield path
            continue
        if not path.exists():
            continue
        for file_path in path.rglob("*.py"):
            if ignored_dirs.intersection(file_path.parts):
                continue
            yield file_path


def check_python_syntax() -> None:
    _print_step("Check Python syntax without writing __pycache__")
    checked = 0
    for file_path in _iter_python_files(BACKEND_SYNTAX_PATHS):
        source = file_path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(file_path))
        checked += 1
    print(f"Checked {checked} Python files")


def run_ruff() -> None:
    _run(
        CommandStep(
            name="Run Ruff on quality gate files",
            command=[sys.executable, "-m", "ruff", "check", *RUFF_TARGETS],
        )
    )


def run_backend_smoke() -> None:
    _run(
        CommandStep(
            name="Run deterministic backend monitoring smoke gate",
            command=[sys.executable, "scripts/validation/monitoring_quality_gate.py"],
        )
    )


def run_backend_pytest() -> None:
    _run(
        CommandStep(
            name="Run backend quality pytest subset",
            command=[sys.executable, "-m", "pytest", "-q", *PYTEST_QUALITY_TARGETS],
        )
    )


def run_backend_service_pytest() -> None:
    _run(
        CommandStep(
            name="Run extended backend service regression subset",
            command=[sys.executable, "-m", "pytest", "-q", *PYTEST_SERVICE_TARGETS],
        )
    )


def run_frontend_typecheck() -> None:
    _ensure_yarn()
    _run(
        CommandStep(
            name="Run frontend type-check",
            command=["yarn", "type-check"],
            cwd=FRONTEND_DIR,
            env={"COREPACK_ENABLE_AUTO_PIN": "0"},
        )
    )


def run_frontend_unit() -> None:
    _ensure_yarn()
    _run(
        CommandStep(
            name="Run frontend unit tests",
            command=["yarn", "test:unit"],
            cwd=FRONTEND_DIR,
            env={"COREPACK_ENABLE_AUTO_PIN": "0"},
        )
    )


def run_frontend_build() -> None:
    _ensure_yarn()
    _run(
        CommandStep(
            name="Build frontend assets",
            command=["yarn", "vite", "build"],
            cwd=FRONTEND_DIR,
            env={"COREPACK_ENABLE_AUTO_PIN": "0"},
        )
    )


def run_frontend_e2e() -> None:
    _ensure_yarn()
    _run(
        CommandStep(
            name="Run Playwright E2E tests",
            command=["yarn", "test:e2e"],
            cwd=FRONTEND_DIR,
            env={"COREPACK_ENABLE_AUTO_PIN": "0"},
        )
    )


def _ensure_yarn() -> None:
    if shutil.which("yarn") is None:
        raise RuntimeError("yarn was not found. Install frontend dependencies before running frontend gates.")


def run_profile(profile: str, skip_ruff: bool) -> None:
    if profile == "syntax":
        check_python_syntax()
        return

    if profile == "precommit":
        check_python_syntax()
        if not skip_ruff:
            run_ruff()
        run_backend_smoke()
        return

    if profile == "backend":
        check_python_syntax()
        if not skip_ruff:
            run_ruff()
        run_backend_smoke()
        run_backend_pytest()
        return

    if profile == "services":
        check_python_syntax()
        if not skip_ruff:
            run_ruff()
        run_backend_smoke()
        run_backend_service_pytest()
        return

    if profile == "frontend":
        run_frontend_typecheck()
        run_frontend_unit()
        run_frontend_build()
        return

    if profile == "frontend-e2e":
        run_frontend_e2e()
        return

    if profile == "all":
        check_python_syntax()
        if not skip_ruff:
            run_ruff()
        run_backend_smoke()
        run_backend_pytest()
        run_frontend_typecheck()
        run_frontend_unit()
        run_frontend_build()
        return

    raise ValueError(f"Unknown profile: {profile}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TradingAgents-CN quality gates.")
    parser.add_argument(
        "--profile",
        choices=("syntax", "precommit", "backend", "services", "frontend", "frontend-e2e", "all"),
        default="backend",
        help="Quality gate profile to run.",
    )
    parser.add_argument(
        "--skip-ruff",
        action="store_true",
        help="Skip Ruff. Intended only for bootstrapping environments before quality deps are installed.",
    )
    args = parser.parse_args()

    try:
        run_profile(args.profile, skip_ruff=args.skip_ruff)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
    except Exception as exc:
        print(f"quality_verify failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
