#!/usr/bin/env python3
"""Run TripMind agent evaluation locally and optionally update the baseline.

Usage (from backend/):

    source .venv/bin/activate
    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --save-baseline
    python scripts/run_evaluation.py --compare-baseline
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.evaluation.runner import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    compare_to_baseline,
    run_evaluation,
    save_baseline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TripMind travel agent evaluation")
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help=f"Write aggregate metrics to {DEFAULT_BASELINE_PATH}",
    )
    parser.add_argument(
        "--compare-baseline",
        action="store_true",
        help="Fail with exit code 1 if metrics regress vs baseline",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Do not write evaluation/results/latest.json",
    )
    args = parser.parse_args()

    report = run_evaluation(write_latest=not args.no_write)
    print(report.format_summary())
    print()
    for case in report.cases:
        print(
            f"- {case.case_id}: understanding={case.request_understanding:.0%} "
            f"tools={case.tool_selection:.0%} itinerary={case.itinerary_validity:.0%} "
            f"budget={case.budget_validity:.0%} halluc={case.hallucination_rate:.0%}"
        )

    if args.save_baseline:
        path = save_baseline(report)
        print(f"\nBaseline saved to {path}")

    if args.compare_baseline:
        comparison = compare_to_baseline(report)
        if not comparison["ok"]:
            print("\nREGRESSION DETECTED:")
            for item in comparison.get("regressions") or [comparison.get("reason")]:
                print(f"  - {item}")
            return 1
        print("\nBaseline comparison: OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
