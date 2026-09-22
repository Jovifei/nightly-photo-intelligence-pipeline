import pytest
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.real20 import Real20Error, run_real20


def test_public_runner_cannot_bind_an_unrelated_repository(tmp_path):
    with pytest.raises(Real20Error, match="REAL20_EXECUTING_SOURCE_MISMATCH"):
        run_real20(
            project_root=tmp_path,
            source_root=tmp_path / "unopened",
            manifest_path=tmp_path / "manifest.json",
            credential_path=tmp_path / "lease.json",
            anchor_path=tmp_path / "anchor.json",
            runtime_identity_path=tmp_path / "runtime.json",
            model_identity_path=tmp_path / "models.json",
            ledger_root=tmp_path / "ledger",
            output_root=tmp_path / "output",
        )


def test_cli_rejects_fake_switch_before_opening_any_control(tmp_path):
    argv = ["real20", "run"]
    for option in (
        "project-root",
        "source-root",
        "manifest",
        "credential",
        "anchor",
        "runtime-identity",
        "model-identity",
        "ledger-root",
        "output-root",
    ):
        argv += ["--" + option, str(tmp_path / option)]
    result = CliRunner().invoke(app, argv + ["--backend", "fake", "--synthetic-test-mode"])
    assert result.exit_code != 0
    assert "REAL20_FAKE_BACKEND_TEST_ONLY" in result.output
    assert list(tmp_path.iterdir()) == []
