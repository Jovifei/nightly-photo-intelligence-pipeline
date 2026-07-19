"""Stable redacted benchmark report DTOs."""

from __future__ import annotations

from typing import Any

from .metrics import BenchmarkAggregate
from .protocol import BenchmarkPlan
from .runner import BenchmarkRunReport
from .schema import strict_json_dumps, validate_document, validate_fragment


def render_plan(plan: BenchmarkPlan) -> str:
    document = plan.to_redacted_dict()
    validate_document(document)
    return strict_json_dumps(document, indent=2)


def render_aggregate(aggregate: BenchmarkAggregate) -> str:
    document = aggregate.to_redacted_dict()
    validate_fragment("aggregate", document)
    return strict_json_dumps(document, indent=2)


def render_run_report(report: BenchmarkRunReport) -> str:
    """Render only typed synthetic metadata; never image bytes or paths."""

    document = report.to_redacted_dict()
    validate_document(document)
    return strict_json_dumps(document, indent=2)


def render_status(status: dict[str, Any]) -> str:
    return strict_json_dumps(status, indent=2)
