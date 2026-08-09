"""Unit contracts for the explicit N2B2 GPU runtime path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.json_strict import load_json_strict
from nightly_photo_intelligence_pipeline.n2b2_synthetic.config import N2B2RunConfig
from nightly_photo_intelligence_pipeline.n2b2_synthetic.metrics import MetricsCollector
from nightly_photo_intelligence_pipeline.n2b2_synthetic.ollama_client import OllamaClient
from nightly_photo_intelligence_pipeline.n2b2_synthetic.torchvision_loader import (
    RealTorchVisionBackend,
)

ROOT = Path(__file__).resolve().parents[1]


def test_real_config_requires_explicit_device_value() -> None:
    config = N2B2RunConfig(
        project_root=ROOT,
        cache_root=ROOT,
        fixtures_dir=ROOT,
        runtime_out_dir=ROOT,
        backend="real",
        device="cuda",
    )
    assert config.device == "cuda"


def test_cuda_backend_fails_closed_without_cuda() -> None:
    backend = RealTorchVisionBackend(ROOT, {})

    class FakeCuda:
        @staticmethod
        def is_available() -> bool:
            return False

        @staticmethod
        def device_count() -> int:
            return 0

    class FakeTorch:
        cuda = FakeCuda()

    backend._requested_device = "cuda"
    backend._torch = FakeTorch()
    backend._tv = object()
    with pytest.raises(RuntimeError, match="N2B2_GPU_RUNTIME_UNAVAILABLE"):
        backend.runtime_attestation()


def test_metrics_records_stage_devices_and_peak(monkeypatch: pytest.MonkeyPatch) -> None:
    metrics = MetricsCollector()
    monkeypatch.setattr(metrics, "_nvidia_smi_used_mib", staticmethod(lambda: 123))
    record = metrics.begin_stage(
        role="POSE_BASELINE_SMOKE",
        model_name="pose",
        device="cuda:0",
        dtype="torch.float32",
    )
    metrics.note_stage_inference(
        record,
        seconds=0.25,
        input_device="cuda:0",
        raw_output_device="cuda:0",
    )
    metrics.end_stage(record, unload_seconds=0.01)
    assert record["device"] == "cuda:0"
    assert record["input_devices"] == ["cuda:0"]
    assert record["raw_output_devices"] == ["cuda:0"]
    assert metrics.gpu_peak_mib == 123


def test_ollama_explicit_unload_is_separate_from_residency_request() -> None:
    requests: list[tuple[str, dict]] = []

    class Response:
        def __init__(self, payload: dict) -> None:
            self.payload = json.dumps(payload).encode("utf-8")

        def read(self) -> bytes:
            return self.payload

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_: object) -> bool:
            return False

    def opener(request: object) -> Response:
        body = getattr(request, "data", None)
        requests.append((getattr(request, "full_url", ""), json.loads(body) if body else {}))
        return Response({"response": "{}"})

    OllamaClient(opener=opener).unload()
    assert requests[-1][0].endswith("/api/generate")
    assert requests[-1][1]["keep_alive"] == 0
    assert requests[-1][1]["prompt"] == ""


def test_s20_schema_has_exactly_twenty_case_contract() -> None:
    schema = load_json_strict(ROOT / "schemas" / "n2b2_s20_fixture_manifest.schema.json")
    entries = []
    for number in range(1, 21):
        entries.append(
            {
                "case_id": f"n2b2-s20-{number:02d}",
                "case_type": "negative_control" if number == 19 else "single_person",
                "filename": f"n2b2-s20-{number:02d}.png",
                "synthetic": True,
                "image_sha256": "a" * 64,
                "width": 832,
                "height": 1216,
                "seed": number,
                "generation_parameters": {
                    "prompt": "synthetic",
                    "negative_prompt": "real photo",
                    "sampler": "dpmpp_2m",
                    "scheduler": "karras",
                    "steps": 30,
                    "cfg": 6.0,
                    "denoise": 1.0,
                },
                "expected_processability": "unsupported" if number == 19 else "processable",
                "expected_person_count": 0 if number == 19 else 1,
                "tags": ["synthetic"],
            }
        )
    manifest = {
        "schema_version": "n2b2-s20-fixture-manifest-v1",
        "fixture_set": "N2B2_S20_SYNTHETIC",
        "generator_version": "test",
        "fixtures": entries,
    }
    import jsonschema

    jsonschema.Draft202012Validator(schema).validate(manifest)


def test_runtime_reports_bind_current_gpu_s3_and_s20_states() -> None:
    gpu_report = (ROOT / "reports" / "N2B2_GPU_runtime_validation_report.md").read_text(
        encoding="utf-8"
    )
    s3_report = (ROOT / "reports" / "N2B2_synthetic_validation_execution_20260809.md").read_text(
        encoding="utf-8"
    )
    s20_report = (ROOT / "reports" / "N2B2_S20_synthetic_validation_plan.md").read_text(
        encoding="utf-8"
    )

    assert "N2B2_GPU_RUNTIME_VALIDATION_COMPLETE_AWAITING_OWNER_REVIEW" in gpu_report
    assert "N2B2_GPU_RUNTIME_UNAVAILABLE: INSUFFICIENT_EXCLUSIVE_HEADROOM" in gpu_report
    assert "e48bf9091efffc2e1100a025636b5ea347687044f1dc00acd160153434ccbbcd" in gpu_report
    assert "e3498356d1f867e3b908c41c1dc329b816aeaed654c55b8c6fc226da59eee9bf" in gpu_report
    assert "226d6f5b1525da025d8800c85eaab799415c93e1574a39f310e10a51530427ef" in gpu_report
    assert "cuda:0" in gpu_report
    assert "fallback=false" in gpu_report

    assert "N2B2_SYNTHETIC_FIXTURE_CAPABILITY_INSUFFICIENT" in s3_report
    assert "N2B2 GPU runtime v2 authoritative continuation" in s3_report
    assert "A `n2b2-s3-01`" in s3_report
    assert "B `n2b2-s3-02`" in s3_report
    assert "C `n2b2-s3-03`" in s3_report
    assert "byte-identical" in s3_report
    assert "Qwen schema validation passed" in s3_report

    assert "S20_TECHNICAL_PREPARATION=READY" in s20_report
    assert "S20_EXECUTION_AUTHORIZATION=LOCKED" in s20_report
    assert "S20_EXECUTION_STATUS=NOT_PERFORMED" in s20_report
    assert "S20_FIXTURE_MANIFEST_INSTANCE=NOT_CREATED" in s20_report

    forbidden_windows_drive_prefix = "F" + ":" + chr(92)
    for report in (gpu_report, s3_report, s20_report):
        assert forbidden_windows_drive_prefix not in report
        assert "PID" not in report
        assert "CommandLine" not in report

    state = json.loads((ROOT / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    assert state["phase_status"]["N2B2"] == "LOCKED"
