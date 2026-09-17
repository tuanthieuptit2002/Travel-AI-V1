"""Regression tests for the TripMind agent evaluation framework."""

from __future__ import annotations

from app.evaluation.dataset import load_eval_dataset
from app.evaluation.runner import (
    DEFAULT_BASELINE_PATH,
    compare_to_baseline,
    run_evaluation,
)


def test_eval_dataset_covers_required_destinations() -> None:
    cases = load_eval_dataset()
    destinations = {case.expected_destination for case in cases}
    assert destinations == {"Da Nang", "Hanoi", "Da Lat", "Phu Quoc", "Hoi An"}
    assert {case.expected_days for case in cases} == {4, 3, 5, 4, 2}
    phu_quoc = next(case for case in cases if case.id == "phuquoc_4d")
    assert phu_quoc.expected_origin == "Ho Chi Minh City"
    assert "search_flights" in phu_quoc.required_tools


def test_evaluation_produces_metrics_and_json_shape() -> None:
    report = run_evaluation(write_latest=False)
    assert report.metrics.case_count == 5
    assert 0.0 <= report.metrics.request_understanding <= 1.0
    assert 0.0 <= report.metrics.tool_selection <= 1.0
    assert 0.0 <= report.metrics.budget_validity <= 1.0
    assert 0.0 <= report.metrics.itinerary_validity <= 1.0
    assert 0.0 <= report.metrics.unsupported_claims <= 1.0
    assert 0.0 <= report.metrics.hallucination_rate <= 1.0
    assert "Agent Evaluation" in report.format_summary()
    # Grounded plans should not invent place IDs on the mock catalog.
    assert report.metrics.hallucination_rate == 0.0
    assert report.metrics.request_understanding >= 0.9


def test_evaluation_does_not_regress_vs_baseline() -> None:
    assert DEFAULT_BASELINE_PATH.exists(), (
        f"Missing baseline at {DEFAULT_BASELINE_PATH}. "
        "Run: python scripts/run_evaluation.py --save-baseline"
    )
    report = run_evaluation(write_latest=False)
    comparison = compare_to_baseline(report, max_drop=0.05, max_rate_increase=0.05)
    assert comparison["ok"], comparison.get("regressions") or comparison.get("reason")
