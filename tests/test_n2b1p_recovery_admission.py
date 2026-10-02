from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from nightly_photo_intelligence_pipeline import n2b1p_recovery_admission as recovery


def _valid() -> recovery.RecoveryAdmission:
    return recovery.RecoveryAdmission(
        artifact_id="torchvision-keypointrcnn-resnet50-fpn-coco-v1",
        quarantine_run_id="run-20261002-example",
        capability="N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
    )


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("capability", "WRONG", "capability"),
        ("artifact_id", "", "binding"),
        ("quarantine_run_id", "", "binding"),
    ],
)
def test_invalid_binding_rejected_before_control_plane_read(
    field, value, match, tmp_path, monkeypatch
):
    def unexpected_read(*args, **kwargs):
        pytest.fail("invalid binding reached control-plane read")

    monkeypatch.setattr(recovery, "load_n2b1p_runtime_configuration", unexpected_read)
    with pytest.raises(ValueError, match=match):
        recovery.validate_recovery_admission(
            replace(_valid(), **{field: value}), project_root=tmp_path
        )


@pytest.mark.parametrize(
    "artifact_id,digest,error",
    [
        (_valid().artifact_id, "a" * 64, None),
        ("wrong-artifact", "a" * 64, "artifact identity"),
        (_valid().artifact_id, "b" * 64, "runtime binding"),
    ],
)
def test_control_plane_binding(artifact_id, digest, error, tmp_path, monkeypatch):
    calls = []

    def load_runtime(root):
        calls.append(("runtime", root))
        return SimpleNamespace(configuration_digest="a" * 64)

    def load_artifact(requested, *, project_root):
        calls.append(("artifact", requested, project_root))
        return SimpleNamespace(artifact_id=artifact_id, runtime_configuration_digest=digest)

    monkeypatch.setattr(recovery, "load_n2b1p_runtime_configuration", load_runtime)
    monkeypatch.setattr(recovery, "load_authorized_promotion", load_artifact)
    if error:
        with pytest.raises(ValueError, match=error):
            recovery.validate_recovery_admission(_valid(), project_root=tmp_path)
    else:
        # The empty root has no cache entries; action admission needs only the
        # bound control plane. Native validation remains with promote_artifact.
        recovery.validate_recovery_admission(_valid(), project_root=tmp_path)
    assert calls == [("runtime", tmp_path), ("artifact", _valid().artifact_id, tmp_path)]
    assert list(tmp_path.iterdir()) == []


def test_control_plane_failure_propagates(tmp_path, monkeypatch):
    def denied(root):
        raise PermissionError("authority denied")

    monkeypatch.setattr(recovery, "load_n2b1p_runtime_configuration", denied)
    with pytest.raises(PermissionError, match="authority denied"):
        recovery.validate_recovery_admission(_valid(), project_root=tmp_path)
