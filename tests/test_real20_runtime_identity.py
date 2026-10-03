from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.engineering.common import canonical, sha256
from nightly_photo_intelligence_pipeline.json_strict import load_json_strict
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
        "ledger_object_sha256": "f" * 64,
        "created_at_utc": "2026-09-27T11:00:00Z",
        "expires_at_utc": "2026-09-27T13:00:00Z",
    }


def _proof_v3(*, status: str = "ADMISSION_ELIGIBLE") -> dict[str, object]:
    value = _proof(status=status)
    value["contract_version"] = "npi-real20-ledger-acl-probe-v2"
    value["probe_nonce_sha256"] = "e" * 64
    return value


def _cleanup_capability() -> dict[str, object]:
    return {
        "capability_version": "npi-real20-cleanup-capability-v1",
        "probe_nonce_sha256": "e" * 64,
        "probe_object_sha256": "d" * 64,
        "cleanup_identity_sha256": "b" * 64,
        "expires_at_utc": "2026-09-27T12:30:00Z",
    }


def _observation() -> dict[str, object]:
    return {
        "models": {"pose": "test"},
        "worker": {"python": "3.12"},
        "vision": {"device": "cpu"},
        "qwen": {"model_id": "test"},
    }


def _identity(*, proof: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "runtime_observation": _observation(),
        "ledger_acl_probe": proof or _proof(),
    }


def _identity_v3(
    *,
    proof: dict[str, object] | None = None,
    capability: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "3.0",
        "runtime_observation": _observation(),
        "ledger_acl_probe": proof or _proof_v3(),
        "cleanup_capability": capability or _cleanup_capability(),
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


def test_v3_binds_cleanup_capability_to_probe() -> None:
    value = _identity_v3()
    result = validate_runtime_identity(value, now=NOW, require_v3=True)

    assert result.control_digest == sha256(canonical(value))
    assert result.observation_digest == sha256(canonical(value["runtime_observation"]))
    assert result.cleanup_capability is not None
    assert result.cleanup_capability.probe_nonce_sha256 == "e" * 64


def test_v3_schema_accepts_bound_identity(project_root: Path) -> None:
    schema = load_json_strict(project_root / "schemas/n2b2_real20_runtime_identity_v3.schema.json")
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(_identity_v3())
    )
    assert errors == []


def test_v2_is_rejected_when_v3_is_required() -> None:
    with pytest.raises(Real20Error, match="REAL20_RUNTIME_IDENTITY_V3_REQUIRED"):
        validate_runtime_identity(_identity(), now=NOW, require_v3=True)


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
    "attestation,message",
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
            current_ledger_object_sha256=attestation.get("current_ledger_object_sha256", "f" * 64),
            require_live_binding=True,
        )


def test_invalid_ledger_object_digest_fails_even_when_live_value_matches() -> None:
    value = _identity()
    value["ledger_acl_probe"]["ledger_object_sha256"] = "invalid"  # type: ignore[index]
    with pytest.raises(Real20Error, match="REAL20_LEDGER_PROBE_DIGEST_INVALID"):
        validate_runtime_identity(
            value,
            now=NOW,
            current_runner_identity_sha256="a" * 64,
            current_ledger_policy_sha256="c" * 64,
            current_ledger_object_sha256="invalid",
            require_live_binding=True,
        )


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("probe_nonce_sha256", "9" * 64, "NONCE_MISMATCH"),
        ("probe_object_sha256", "9" * 64, "OBJECT_MISMATCH"),
        ("cleanup_identity_sha256", "9" * 64, "IDENTITY_MISMATCH"),
    ],
)
def test_v3_cleanup_binding_drift_fails_closed(field: str, value: str, error: str) -> None:
    capability = _cleanup_capability()
    capability[field] = value
    with pytest.raises(Real20Error, match=error):
        validate_runtime_identity(_identity_v3(capability=capability), now=NOW, require_v3=True)


def test_runtime_identity_rejects_naive_now() -> None:
    with pytest.raises(Real20Error, match="REAL20_RUNTIME_IDENTITY_TIME_INVALID"):
        validate_runtime_identity(_identity_v3(), now=datetime(2026, 9, 27, 12, 0))


def test_unknown_runtime_observation_field_fails_closed() -> None:
    value = _identity()
    value["runtime_observation"]["unknown"] = {}  # type: ignore[index]
    with pytest.raises(Real20Error, match="REAL20_RUNTIME_OBSERVATION_FIELDS_INVALID"):
        validate_runtime_identity(value, now=NOW)


def test_missing_runtime_observation_domain_fails_closed() -> None:
    value = _identity()
    del value["runtime_observation"]["qwen"]  # type: ignore[index]
    with pytest.raises(Real20Error, match="REAL20_RUNTIME_OBSERVATION_FIELDS_INVALID"):
        validate_runtime_identity(value, now=NOW)


def test_public_run_does_not_expose_attestation_override() -> None:
    from nightly_photo_intelligence_pipeline.real20.runner import run_real20

    assert "ledger_attestation_probe" not in inspect.signature(run_real20).parameters


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
            now=NOW,
        )
    assert calls == []


def test_invalid_v3_cleanup_binding_fails_before_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    invalid = _identity_v3()
    invalid["cleanup_capability"]["probe_nonce_sha256"] = "9" * 64  # type: ignore[index]
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

    with pytest.raises(Real20Error, match="REAL20_CLEANUP_CAPABILITY_NONCE_MISMATCH"):
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
            now=NOW,
        )
    assert calls == []


@pytest.mark.parametrize(
    "fault,error",
    [
        ("nonce", "REAL20_CLEANUP_CAPABILITY_NONCE_MISMATCH"),
        ("object", "REAL20_CLEANUP_CAPABILITY_OBJECT_MISMATCH"),
        ("helper", "REAL20_CLEANUP_CAPABILITY_IDENTITY_MISMATCH"),
        ("cleanup_expired", "REAL20_CLEANUP_CAPABILITY_EXPIRED"),
        ("probe_stale", "REAL20_LEDGER_PROBE_STALE"),
    ],
)
def test_invalid_v3_control_blocks_reservation_backend_and_image(
    monkeypatch: pytest.MonkeyPatch, fault: str, error: str
) -> None:
    invalid = _identity_v3()
    if fault == "nonce":
        invalid["cleanup_capability"]["probe_nonce_sha256"] = "9" * 64  # type: ignore[index]
    elif fault == "object":
        invalid["cleanup_capability"]["probe_object_sha256"] = "9" * 64  # type: ignore[index]
    elif fault == "helper":
        invalid["cleanup_capability"]["cleanup_identity_sha256"] = "9" * 64  # type: ignore[index]
    elif fault == "cleanup_expired":
        invalid["cleanup_capability"]["expires_at_utc"] = "2026-09-27T11:59:59Z"  # type: ignore[index]
    elif fault == "probe_stale":
        invalid["ledger_acl_probe"]["expires_at_utc"] = "2026-09-27T11:59:59Z"  # type: ignore[index]
    else:  # pragma: no cover - parametrization is closed
        raise AssertionError(fault)

    calls: list[str] = []
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
    monkeypatch.setattr(
        runner,
        "_read_image",
        lambda *_args, **_kwargs: calls.append("image") or (b"", 1, 1),
    )

    def backend_factory():
        calls.append("backend")
        raise AssertionError("backend construction must be unreachable")

    with pytest.raises(Real20Error, match=error):
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
            backend_factory=backend_factory,
            now=NOW,
        )
    assert calls == []


def test_probe_command_fails_closed_without_owner_configuration(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["real20", "ledger-probe", "--project-root", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert '"status": "NOT_AVAILABLE"' in result.stdout
    assert not list(tmp_path.iterdir())


def test_cleanup_helper_command_requires_inherited_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "NPI_REAL20_CLEANUP_HANDLE",
        "NPI_REAL20_CLEANUP_CAPABILITY_JSON",
        "NPI_REAL20_PROBE_NONCE_SHA256",
    ):
        monkeypatch.delenv(name, raising=False)

    result = CliRunner().invoke(app, ["real20", "ledger-probe-clean"])

    assert result.exit_code == 1
    assert "REAL20_CLEANUP_HELPER_INHERITED_HANDLE_REQUIRED" in result.stdout
