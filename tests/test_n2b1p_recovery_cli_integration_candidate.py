from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline import cli
from nightly_photo_intelligence_pipeline import n2b1p_recovery_admission as recovery
from nightly_photo_intelligence_pipeline.domain.errors import RuntimePolicyError


@pytest.mark.parametrize("status", ["PROMOTED", "CACHE_HIT"])
def test_single_artifact_recovery_without_global_cache_hit(monkeypatch, status):
    calls = []

    def admission(value, *, project_root):
        calls.append("admission")
        assert value.artifact_id == "artifact"
        assert value.quarantine_run_id == "run"

    def selected(artifact):
        calls.append("selection")
        return artifact

    def promote(value, *, quarantine_run_id):
        calls.append("promotion")
        assert value == "artifact"
        assert quarantine_run_id == "run"
        return SimpleNamespace(
            artifact_id=value,
            cache_key="a" * 64,
            byte_count=1,
            local_sha256="a" * 64,
            status=status,
        )

    def global_preflight():
        pytest.fail("single recovery invoked all-artifact steady-state gate")

    monkeypatch.setattr(recovery, "validate_recovery_admission", admission)
    monkeypatch.setattr(cli, "load_authorized_promotion", selected)
    monkeypatch.setattr(cli, "promote_artifact", promote)
    monkeypatch.setattr(cli, "run_preflight", global_preflight)
    result = CliRunner().invoke(
        cli.app, ["model", "promote", "--artifact", "artifact", "--quarantine-run-id", "run"]
    )
    assert result.exit_code == 0, result.output
    assert f'"status": "{status}"' in result.output
    assert calls == ["admission", "selection", "promotion"]


def test_denied_admission_never_promotes(monkeypatch):
    def deny(*args, **kwargs):
        raise RuntimePolicyError("recovery authority denied")

    def unexpected(*args, **kwargs):
        pytest.fail("denied recovery reached promotion")

    monkeypatch.setattr(recovery, "validate_recovery_admission", deny)
    monkeypatch.setattr(cli, "promote_artifact", unexpected)
    result = CliRunner().invoke(
        cli.app, ["model", "promote", "--artifact", "artifact", "--quarantine-run-id", "run"]
    )
    assert result.exit_code != 0
    assert "recovery authority denied" in result.output
