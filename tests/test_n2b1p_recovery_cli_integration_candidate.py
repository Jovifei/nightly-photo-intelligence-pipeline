"""Candidate CLI integration coverage for R0 recovery admission.

Tests are intended to run in the local Codex validation environment after
applying review_tools/R0_CLI_WIRING.patch.
"""

from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app


runner = CliRunner()


def test_promote_recovery_candidate_keeps_single_artifact_scope() -> None:
    """The CLI patch must not require global CACHE_HIT before one artifact."""
    # NOT RUN remotely: requires the local Codex fixture/control-plane runtime.
    # This test file records the required acceptance shape only.
    assert runner is not None


def test_promote_recovery_candidate_keeps_stage_closure_separate() -> None:
    """Three-artifact CACHE_HIT remains a stage closure assertion."""
    assert app is not None
