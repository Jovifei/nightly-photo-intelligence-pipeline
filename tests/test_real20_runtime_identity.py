from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.engineering.common import canonical, sha256
from nightly_photo_intelligence_pipeline.real20 import Real20Error, runner
from nightly_photo_intelligence_pipeline.real20.runtime_identity import validate_runtime_identity

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _proof(*, status: str = "ADMISSION_ELIGIBLE") -> dict[str, object]:
    return {
        "contract_version": "npi-real20-ledger-acl-probe-v1",
        "status": status,
        "inheritance_status": "PROBE_PASS",
        "cleanup_status": "CLEANUP_PASS",
        "runner_identity_sha256": "a" * 64,
        "cleanup_identity_sha256": "b" * 64,
        "ledger_policy_sha256": "c" * 64,
        "probe_policy_sha256": "c" * 64,
        "probe_object_sha256": "d" * 64,
        "created_at_utc": "2026-09-27T11:00:00Z",
        "expires_at_utc": "2026-09-27T13:00:00Z",
    }


def _identity(*, proof: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "runtime_observation": {
            "models": {"pose": "test"},
            "worker": {"python": "3.12"},
            "vision": {"device": "cpu"},
            "qwen": {"model_id": "test"},
        },
        "ledger_acl_probe": proof or _proof(),
    }


def test_v2_uses_separate_control_and_live_observation_digests() -> None:
    value = _identity()
    result = validate_runtime_identity(value, now=NOW)

    assert result.control_digest == sha256(canonical(value))
    assert result.observation_digest == sha256(canonical(value["runtime_observation"]))
    assert result.control_digest != result.observation_digest


def test_changing_probe_changes_control_digest_but_not_live_digest() -> None:
    first = validate_runtime_identity(_identity(), now=NOW)
    second_value = _identity()
    second_value["ledger_acl_probe"] = _proof(status="ADMISSION_ELIGIBLE")
    second_value["ledger_acl_probe"]["probe_object_sha256"] = "e" * 64  # type: ignore[index]
    second = validate_runtime_identity(second_value, now=NOW)

    assert first.observation_digest == second.observation_digest
    assert first.control_digest != second.control_digest


def test_v1_is_rejected_for_new_admission() -> None:
    with pytest.raises(Real20Error, match="REAL20_RUNTIME_IDENTITY_SCHEMA_INVALID"):
        validate_runtime_identity({"models": {"pose": "old"}}, now=NOW)


def test_probe_pass_without_cleanup_is_not_admission_eligible() -> None:
    with pytest.raises(Real20Error, match="REAL20_LEDGER_PROBE_NOT_ADMISSION_ELIGIBLE"):
        validate_runtime_identity(_identity(proof=_proof(status="PROBE_PASS")), now=NOW)


def test_expired_probe_fails_closed() -> None:
    proof = _proof()
    proof["expires_at_utc"] = (NOW - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    with pytest.raises(Real20Error, match="REAL20_LEDGER_PROBE_STALE"):
        validate_runtime_identity(_identity(proof=proof), now=NOW)


@pytest.mark.parametrize(
    "attestation, message",
    [
        ({"current_runner_identity_sha256": "e" * 64}, "RUNNER_IDENTITY_MISMATCH"),
        ({"current_ledger_policy_sha256": "e" * 64}, "LIVE_POLICY_MISMATCH"),
        ({"current_ledger_object_sha256": "e" * 64}, "OBJECT_MISMATCH"),
    ],
)
def test_live_binding_mismatch_fails_closed(attestation: dict[str, str], message: str) -> None:
    with pytest.raises(Real20Error, match=message):
        validate_runtime_identity(
            _identity(),
            now=NOW,
            current_runner_identity_sha256=attestation.get(
                "current_runner_identity_sha256", "a" * 64
            ),
            current_ledger_policy_sha256=attestation.get("current_ledger_policy_sha256", "c" * 64),
            current_ledger_object_sha256=attestation.get("current_ledger_object_sha256", "d" * 64),
            require_live_binding=True,
        )


def test_unknown_runtime_observation_field_fails_closed() -> None:
    value = _identity()
    value["runtime_observation"]["unknown"] = {}
    with pytest.raises(Real20Error, match="REAL20_RUNTIME_OBSERVATION_FIELDS_INVALID"):
        validate_runtime_identity(value, now=NOW)


def test_missing_runtime_observation_domain_fails_closed() -> None:
    value = _identity()
    del value["runtime_observation"]["qwen"]
    with pytest.raises(Real20Error, match="REAL20_RUNTIME_OBSERVATION_FIELDS_INVALID"):
        validate_runtime_identity(value, now=NOW)


def test_invalid_probe_fails_before_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    invalid = _identity(proof=_proof(status="PROBE_PASS"))
    monkeypatch.setattr(
        runner,
        "load_manifest",
        lambda _path: SimpleNamespace(sha256="a" * 64, source_fingerprint="source", assets=()),
    )
    monkeypatch.setattr(runner, "candidate_identity", lambda _root: {})
    monkeypatch.setattr(
        runner,
        "_read_control",
        lambda path: invalid if str(path).endswith("runtime.json") else {},
    )
    monkeypatch.setattr(runner, "_reservation", lambda *_args, **_kwargs: calls.append("reserve"))

    with pytest.raises(Real20Error, match="REAL20_LEDGER_PROBE_NOT_ADMISSION_ELIGIBLE"):
        runner._run_real20(
            project_root=Path("project"),
            source_root=Path("source"),
            manifest_path=Path("manifest"),
            credential_path=Path("lease"),
            anchor_path=Path("anchor"),
            runtime_identity_path=Path("runtime.json"),
            model_identity_path=Path("model_identity"),
            ledger_root=Path("ledger"),
            output_root=Path("output"),
        )
    assert calls == []


@pytest.mark.parametrize("command", ["ledger-probe", "ledger-probe-clean"])
def test_probe_commands_fail_closed_without_owner_configuration(
    tmp_path: Path, command: str
) -> None:
    result = CliRunner().invoke(
        app,
        ["real20", command, "--project-root", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert '"status": "NOT_AVAILABLE"' in result.stdout
    assert not list(tmp_path.iterdir())
