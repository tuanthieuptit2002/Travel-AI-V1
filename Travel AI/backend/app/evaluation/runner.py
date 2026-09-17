"""Run the TripMind agent evaluation suite and persist JSON reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agent.graph import build_travel_agent_graph
from app.evaluation.dataset import REFERENCE_DATE, load_eval_dataset
from app.evaluation.instrumentation import ToolCallRecorder
from app.evaluation.models import AggregateMetrics, CaseScores, EvaluationReport
from app.evaluation.scoring import score_case
from app.tools import ToolDependencies, create_agent_tools

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parents[2] / "evaluation" / "results"
DEFAULT_BASELINE_PATH = (
    Path(__file__).resolve().parents[2] / "evaluation" / "baselines" / "latest.json"
)


def run_evaluation(
    *,
    results_dir: Optional[Path] = None,
    write_latest: bool = True,
) -> EvaluationReport:
    """Execute all gold cases against mock providers and aggregate metrics."""
    cases = load_eval_dataset()
    case_scores: List[CaseScores] = []

    for case in cases:
        recorder = ToolCallRecorder()
        dependencies = ToolDependencies.with_mocks()
        tools = {tool.name: tool for tool in create_agent_tools(dependencies)}
        wrapped = recorder.wrap(tools)
        app = build_travel_agent_graph(
            dependencies=dependencies,
            reference_date=case.reference_date,
            tools=wrapped,
        )
        state = app.invoke({"user_request": case.user_request})
        case_scores.append(
            score_case(case, agent_state=state, tools_used=recorder.unique_calls)
        )

    metrics = _aggregate(case_scores)
    report = EvaluationReport(
        created_at=datetime.now(timezone.utc).isoformat(),
        reference_date=REFERENCE_DATE.isoformat(),
        metrics=metrics,
        cases=case_scores,
    )
    report.summary_lines = report.format_summary().splitlines()

    if write_latest:
        out_dir = results_dir or DEFAULT_RESULTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stamped = out_dir / f"eval_{stamp}.json"
        latest = out_dir / "latest.json"
        payload = report.model_dump(mode="json")
        stamped.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        latest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    return report


def save_baseline(report: EvaluationReport, path: Optional[Path] = None) -> Path:
    target = path or DEFAULT_BASELINE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
    )
    return target


def load_report(path: Path) -> EvaluationReport:
    return EvaluationReport.model_validate(json.loads(path.read_text()))


def compare_to_baseline(
    report: EvaluationReport,
    *,
    baseline_path: Optional[Path] = None,
    max_drop: float = 0.05,
    max_rate_increase: float = 0.05,
) -> Dict[str, Any]:
    """Compare high-level metrics to a stored baseline for regression tests.

    Quality metrics (understanding, tools, budget, itinerary, duplicate_free)
    must not drop by more than ``max_drop``.

    Error-rate metrics (unsupported_claims, hallucination_rate) must not rise
    by more than ``max_rate_increase``.
    """
    path = baseline_path or DEFAULT_BASELINE_PATH
    if not path.exists():
        return {
            "ok": False,
            "reason": f"Baseline missing at {path}. Run scripts/run_evaluation.py --save-baseline.",
            "regressions": [],
        }

    baseline = load_report(path)
    quality_keys = (
        "request_understanding",
        "tool_selection",
        "budget_validity",
        "itinerary_validity",
        "duplicate_free",
    )
    rate_keys = ("unsupported_claims", "hallucination_rate")
    regressions: List[str] = []

    for key in quality_keys:
        current = getattr(report.metrics, key)
        previous = getattr(baseline.metrics, key)
        if current + 1e-9 < previous - max_drop:
            regressions.append(
                f"{key} dropped from {previous:.3f} to {current:.3f} (max drop {max_drop})"
            )

    for key in rate_keys:
        current = getattr(report.metrics, key)
        previous = getattr(baseline.metrics, key)
        if current - 1e-9 > previous + max_rate_increase:
            regressions.append(
                f"{key} rose from {previous:.3f} to {current:.3f} "
                f"(max increase {max_rate_increase})"
            )

    return {
        "ok": not regressions,
        "baseline_path": str(path),
        "baseline_created_at": baseline.created_at,
        "regressions": regressions,
        "current": report.metrics.model_dump(),
        "baseline": baseline.metrics.model_dump(),
    }


def _aggregate(cases: List[CaseScores]) -> AggregateMetrics:
    def avg(attr: str) -> float:
        if not cases:
            return 0.0
        return sum(getattr(c, attr) for c in cases) / len(cases)

    return AggregateMetrics(
        request_understanding=avg("request_understanding"),
        tool_selection=avg("tool_selection"),
        budget_validity=avg("budget_validity"),
        itinerary_validity=avg("itinerary_validity"),
        duplicate_free=avg("duplicate_free"),
        unsupported_claims=avg("unsupported_claims_rate"),
        hallucination_rate=avg("hallucination_rate"),
        case_count=len(cases),
    )
