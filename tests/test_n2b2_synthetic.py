"""N2B2 synthetic model-stack validation — mock-based contract tests.

These tests run entirely in the managed ``.venv`` (no torch, no real Ollama,
no real photos) by injecting a fake TorchVision backend and a fake Ollama
HTTP opener. They cover the CODEX §15 requirement matrix: loopback refusal,
identity mismatch, vision-capability / quantization gating, forbidden fields,
fact_digest echo, unknown fact ids, schema failure, thinking not persisted,
keep_alive=0 + /api/ps unload, concurrent residency rejection, synthetic-only
hard counts, cache no-redownload, S3 fixture-capability stop, GPU threshold,
and reference-bundle checksums.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from nightly_photo_intelligence_pipeline.domain.errors import NPI_SECURITY_BOUNDARY
from nightly_photo_intelligence_pipeline.json_strict import load_json_strict
from nightly_photo_intelligence_pipeline.n2b2_synthetic import (
    N2B2RunConfig,
    SyntheticFixture,
    run_n2b2,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.metrics import MetricsCollector
from nightly_photo_intelligence_pipeline.n2b2_synthetic.ollama_client import OllamaClient
from nightly_photo_intelligence_pipeline.n2b2_synthetic.orchestrator import ResidencyGate
from nightly_photo_intelligence_pipeline.n2b2_synthetic.qwen_reasoning import validate_reasoning
from nightly_photo_intelligence_pipeline.n2b2_synthetic.torchvision_loader import (
    FakeTorchVisionBackend,
    RawPoseDetections,
    RawSegmentation,
    verify_cache_hit,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.vision_facts import (
    build_vision_facts,
    compute_fact_digest,
)

ROOT = Path(__file__).resolve().parents[1]
REASONING_SCHEMA = load_json_strict(ROOT / "schemas" / "n2b2_photography_reasoning.schema.json")
VISION_SCHEMA = load_json_strict(ROOT / "schemas" / "n2b2_vision_fact_contract.schema.json")
BUNDLE_SCHEMA = load_json_strict(ROOT / "schemas" / "reference_bundle_v1_synthetic.schema.json")


def _make_png_bytes(
    color: tuple[int, int, int], size: tuple[int, int] = (64, 48)
) -> tuple[bytes, int, int]:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    data = buf.getvalue()
    return data, size[0], size[1]


class _Resp:
    def __init__(self, payload: dict) -> None:
        self._p = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._p

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *_: object) -> bool:
        return False


class FakeOllamaOpener:
    def __init__(
        self,
        *,
        vision: bool = True,
        quantization: str = "Q4_K_M",
        model_name: str = "qwen3.5:9b",
        ps_clear: bool = True,
        leak_path: bool = False,
    ) -> None:
        self.vision = vision
        self.quantization = quantization
        self.model_name = model_name
        self.ps_clear = ps_clear
        self.leak_path = leak_path
        self.paths: list[str] = []
        self.generate_bodies: list[dict] = []

    def __call__(self, req: object) -> _Resp:  # type: ignore[override]
        url = getattr(req, "full_url", "")
        data = getattr(req, "data", None)
        body = json.loads(data) if data else {}
        self.paths.append(url)
        if url.endswith("/api/tags"):
            return _Resp(
                {
                    "models": [
                        {
                            "name": self.model_name,
                            "digest": "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7",
                            "size": 6594474711,
                            "details": {
                                "format": "gguf",
                                "family": "qwen35",
                                "parameter_size": "9.7B",
                                "quantization_level": self.quantization,
                                "capabilities": (["vision"] if self.vision else ["completion"]),
                                "license": "apache-2.0",
                                "modified_at": "2026-08-04T23:03:22Z",
                            },
                        }
                    ]
                }
            )
        if url.endswith("/api/version"):
            return _Resp({"version": "0.4.0"})
        if url.endswith("/api/generate"):
            self.generate_bodies.append(body)
            if self.leak_path:
                body["images"] = ["/abs/path/to/photo.png"]
            m = re.search(r"fact_digest=([0-9a-f]{64})", body.get("prompt", ""))
            fd = m.group(1) if m else "0" * 64
            case_match = re.search(r'"case_id":"(n2b2-s3-[0-9]{2})"', body.get("prompt", ""))
            case_id = case_match.group(1) if case_match else "n2b2-s3-01"
            # Realistic Ollama shape: the structured object is returned as a
            # JSON string inside the ``response`` field. ``reason()`` parses it.
            reasoning = {
                "schema_version": "1.0",
                "case_id": case_id,
                "input_fact_digest": fd,
                "reasoning_based_on_fact_ids": ["fact-person-count"],
                "photographic_interpretation": {
                    "scene_value": "medium",
                    "composition_notes": "balanced",
                    "lighting_notes": "low key",
                    "tone_notes": "cool",
                },
                "story_candidates": {"safe": "a", "narrative": "b", "dynamic": "c"},
                "director_prompts": {
                    "standard": "s",
                    "dramatic": "d",
                    "plan_b": "p",
                    "technical": "t",
                },
                "uncertainties": [],
            }
            return _Resp({"response": json.dumps(reasoning)})
        if url.endswith("/api/ps"):
            return _Resp(
                {"models": []} if self.ps_clear else {"models": [{"name": self.model_name}]}
            )
        return _Resp({})


def _config(backend: str = "fake", gpu_limit: int = 11500, device: str = "cpu") -> N2B2RunConfig:
    return N2B2RunConfig(
        project_root=ROOT,
        cache_root=Path("npi-model-cache"),
        fixtures_dir=ROOT / "fixtures",
        runtime_out_dir=ROOT / ".npi_runtime" / "n2b2_test",
        backend=backend,  # type: ignore[arg-type]
        device=device,  # type: ignore[arg-type]
        gpu_limit_mib=gpu_limit,
    )


def _fake_cache_entries(cache_root: object, subdirs: object) -> list[dict[str, str]]:
    """Stand-in for ``verify_cache_hit`` so orchestrator tests don't need a
    real TorchVision weight cache on disk (the cache check itself is covered
    by ``test_cache_no_redownload``)."""
    return [
        {"artifact_id": "keypointrcnn-resnet50-fpn", "role": "pose_baseline_smoke", "path": "x"},
        {"artifact_id": "lraspp-mobilenet-v3-large", "role": "segmentation_primary", "path": "x"},
        {
            "artifact_id": "deeplabv3-mobilenet-v3-large",
            "role": "segmentation_quality_comparator",
            "path": "x",
        },
    ]


def _fixtures(count: int, person_positive: bool) -> list[SyntheticFixture]:
    out: list[SyntheticFixture] = []
    for i in range(count):
        data, w, h = _make_png_bytes((i * 10 % 255, 100, 200))
        out.append(
            SyntheticFixture(case_id=f"n2b2-s3-{i + 1:02d}", image_bytes=data, width=w, height=h)
        )
    if person_positive and out:
        out[0].image_bytes = _make_png_bytes((255, 0, 0))[0] or out[0].image_bytes
    return out


# --- Ollama identity / loopback -----------------------------------------


def test_non_loopback_rejected():
    try:
        OllamaClient("http://10.0.0.5:11434")
    except PermissionError as exc:
        assert NPI_SECURITY_BOUNDARY in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected loopback refusal")


def test_identity_name_mismatch():
    opener = FakeOllamaOpener(model_name="other:7b")
    client = OllamaClient(opener=opener)
    try:
        client.verify_identity()
    except ValueError as exc:
        assert "IDENTITY_MISMATCH" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected identity mismatch")


def test_identity_vision_missing():
    opener = FakeOllamaOpener(vision=False)
    client = OllamaClient(opener=opener)
    try:
        client.verify_identity()
    except ValueError as exc:
        assert "VISION_CAPABILITY_MISSING" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected vision missing")


def test_identity_quantization_mismatch():
    opener = FakeOllamaOpener(quantization="F16")
    client = OllamaClient(opener=opener)
    try:
        client.verify_identity()
    except ValueError as exc:
        assert "IDENTITY_MISMATCH" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected quantization mismatch")


def test_identity_ok():
    client = OllamaClient(opener=FakeOllamaOpener())
    ident = client.verify_identity()
    assert ident.model_name == "qwen3.5:9b"
    assert "vision" in ident.capabilities
    assert ident.quantization_level == "Q4_K_M"


# --- reasoning contract --------------------------------------------------


def _good_reasoning(fact_digest: str) -> dict:
    return {
        "schema_version": "1.0",
        "case_id": "n2b2-s3-01",
        "input_fact_digest": fact_digest,
        "reasoning_based_on_fact_ids": ["fact-person-count"],
        "photographic_interpretation": {
            "scene_value": "medium",
            "composition_notes": "c",
            "lighting_notes": "l",
            "tone_notes": "t",
        },
        "story_candidates": {"safe": "a", "narrative": "b", "dynamic": "c"},
        "director_prompts": {"standard": "s", "dramatic": "d", "plan_b": "p", "technical": "t"},
        "uncertainties": [],
    }


def test_reasoning_forbidden_fields():
    out = _good_reasoning("0" * 64)
    out["person_count"] = 1
    vr = validate_reasoning(
        out,
        input_fact_digest="0" * 64,
        valid_fact_ids=["fact-person-count"],
        schema=REASONING_SCHEMA,
    )
    assert not vr.ok
    assert vr.forbidden_field_count >= 1


def test_reasoning_fact_digest_mismatch():
    out = _good_reasoning("0" * 64)
    vr = validate_reasoning(
        out,
        input_fact_digest="1" * 64,
        valid_fact_ids=["fact-person-count"],
        schema=REASONING_SCHEMA,
    )
    assert not vr.ok


def test_reasoning_unknown_fact_id():
    out = _good_reasoning("0" * 64)
    out["reasoning_based_on_fact_ids"] = ["fact-does-not-exist"]
    vr = validate_reasoning(
        out,
        input_fact_digest="0" * 64,
        valid_fact_ids=["fact-person-count"],
        schema=REASONING_SCHEMA,
    )
    assert not vr.ok


def test_reasoning_schema_fail():
    out = {"schema_version": "1.0"}
    vr = validate_reasoning(
        out, input_fact_digest="0" * 64, valid_fact_ids=[], schema=REASONING_SCHEMA
    )
    assert not vr.ok


def test_reasoning_happy():
    out = _good_reasoning("0" * 64)
    vr = validate_reasoning(
        out,
        input_fact_digest="0" * 64,
        valid_fact_ids=["fact-person-count"],
        schema=REASONING_SCHEMA,
    )
    assert vr.ok


# --- request shape / unload ----------------------------------------------


def test_no_pull_and_keep_alive_zero():
    opener = FakeOllamaOpener()
    client = OllamaClient(opener=opener)
    client.verify_identity()
    client.reason(
        image_b64="QUJD",
        case_id="n2b2-s3-01",
        fact_digest="0" * 64,
        fact_ids=["fact-person-count"],
        uncertainties=[],
        response_schema=REASONING_SCHEMA,
    )
    client.verify_unloaded()
    assert not any("pull" in p for p in opener.paths)
    gen = [b for b in opener.generate_bodies if b]
    assert gen, "expected a generate body"
    assert gen[0]["keep_alive"] == 0
    assert gen[0]["stream"] is False
    assert gen[0]["think"] is False


def test_image_path_not_leaked():
    opener = FakeOllamaOpener(leak_path=False)
    client = OllamaClient(opener=opener)
    client.verify_identity()
    client.reason(
        image_b64="QUJD",
        case_id="n2b2-s3-01",
        fact_digest="0" * 64,
        fact_ids=["fact-person-count"],
        uncertainties=[],
        response_schema=REASONING_SCHEMA,
    )
    blob = json.dumps(opener.generate_bodies[-1])
    assert "E:/" not in blob and "/e/" not in blob and "/abs/path" not in blob


def test_thinking_not_persisted():
    opener = FakeOllamaOpener()
    client = OllamaClient(opener=opener)
    client.verify_identity()
    # Simulate a server that returns a thinking trace despite think=false.
    import nightly_photo_intelligence_pipeline.n2b2_synthetic.ollama_client as oc  # noqa: PLC0415

    def _fake_request(self, method, path, body=None):  # noqa: ANN001
        if path.endswith("/api/generate"):
            return {
                "response": json.dumps(
                    {**_good_reasoning("0" * 64), "thinking": "secret chain of thought"}
                )
            }
        return {}

    monkeypatch_request = _fake_request
    orig = oc.OllamaClient._request
    oc.OllamaClient._request = monkeypatch_request  # type: ignore[assignment]
    try:
        parsed = client.reason(
            image_b64="QUJD",
            case_id="n2b2-s3-01",
            fact_digest="0" * 64,
            fact_ids=["fact-person-count"],
            uncertainties=[],
            response_schema=REASONING_SCHEMA,
        )
    finally:
        oc.OllamaClient._request = orig  # type: ignore[assignment]
    assert "thinking" not in parsed


def test_concurrent_residency_rejected():
    gate = ResidencyGate()
    gate.acquire("torchvision:pose")
    try:
        gate.acquire("qwen")
    except RuntimeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected concurrent residency rejection")
    gate.release("torchvision:pose")
    gate.acquire("qwen")  # now allowed
    gate.release("qwen")


# --- cache / facts / hard counts ----------------------------------------


def test_cache_no_redownload(tmp_path: Path):
    missing = tmp_path / "missing"
    try:
        verify_cache_hit(missing, _config().cache_subdirs)
    except FileNotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected cache miss refusal (no download)")


def test_fact_immutability():
    data, w, h = _make_png_bytes((10, 20, 30))
    backend = FakeTorchVisionBackend()
    f1 = build_vision_facts(
        case_id="n2b2-s3-01",
        image_sha256="0" * 64,
        generator_version="v1",
        seed=1,
        width=w,
        height=h,
        pose=backend.detect_pose(data),
        seg_primary=backend.segment(
            data,
            __import__(
                "nightly_photo_intelligence_pipeline.n2b2_synthetic.config",
                fromlist=["TorchVisionRole"],
            ).TorchVisionRole.SEGMENTATION_PRIMARY,
        ),
        seg_comparator=backend.segment(
            data,
            __import__(
                "nightly_photo_intelligence_pipeline.n2b2_synthetic.config",
                fromlist=["TorchVisionRole"],
            ).TorchVisionRole.SEGMENTATION_QUALITY_COMPARATOR,
        ),
    )
    f2 = build_vision_facts(
        case_id="n2b2-s3-01",
        image_sha256="0" * 64,
        generator_version="v1",
        seed=1,
        width=w,
        height=h,
        pose=backend.detect_pose(data),
        seg_primary=backend.segment(
            data,
            __import__(
                "nightly_photo_intelligence_pipeline.n2b2_synthetic.config",
                fromlist=["TorchVisionRole"],
            ).TorchVisionRole.SEGMENTATION_PRIMARY,
        ),
        seg_comparator=backend.segment(
            data,
            __import__(
                "nightly_photo_intelligence_pipeline.n2b2_synthetic.config",
                fromlist=["TorchVisionRole"],
            ).TorchVisionRole.SEGMENTATION_QUALITY_COMPARATOR,
        ),
    )
    assert compute_fact_digest(f1) == compute_fact_digest(f2)


def test_reference_bundle_checksum():
    import jsonschema  # noqa: PLC0415

    bundle = {
        "schema_version": "1.0-synthetic",
        "bundle_type": "SYNTHETIC_VALIDATION",
        "case_id": "n2b2-s3-01",
        "image_sha256": "0" * 64,
        "vision_facts": {"fact_digest": "a" * 64, "fact_ids": ["fact-person-count"]},
        "photographic_reasoning": {
            "input_fact_digest": "a" * 64,
            "reasoning_model": "qwen3.5:9b",
            "qwen_echo_verified": True,
            "qwen_echoed_fact_digest": "a" * 64,
        },
        "checksums": {
            "vision_facts_sha256": "b" * 64,
            "reasoning_sha256": "c" * 64,
            "director_prompt_sha256": "d" * 64,
        },
        "provenance": {
            "data_gate": "SYNTHETIC_ONLY_DATA_GATE",
            "real_photo_read_count": 0,
            "real_exif_read_count": 0,
            "g1_source_access": 0,
            "sqlite_write_count": 0,
            "created_at_utc": "2026-08-06T00:00:00Z",
            "pipeline_stage": "N2B2_SYNTHETIC_MODEL_STACK_VALIDATION",
        },
    }
    jsonschema.Draft202012Validator(BUNDLE_SCHEMA).validate(bundle)


# --- orchestrator end-to-end (fake backend) -----------------------------


def _s3_person_positive_fixtures() -> list[SyntheticFixture]:
    def _one_person(case_id: str, color: tuple[int, int, int]) -> SyntheticFixture:
        data, w, h = _make_png_bytes(color)
        return SyntheticFixture(case_id=case_id, image_bytes=data, width=w, height=h)

    return [_one_person(f"n2b2-s3-{i + 1:02d}", (200, 50 + i, 50)) for i in range(3)]


def test_n2b2_happy_complete(monkeypatch):
    config = _config()
    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.n2b2_synthetic.orchestrator.verify_cache_hit",
        _fake_cache_entries,
    )
    s3 = _s3_person_positive_fixtures()
    negative_bytes = s3[2].image_bytes
    original_segment = FakeTorchVisionBackend.segment
    monkeypatch.setattr(
        FakeTorchVisionBackend,
        "segment",
        lambda self, b, role: (
            RawSegmentation() if b == negative_bytes else original_segment(self, b, role)
        ),
    )
    # Force the fake backend to return a complete person for all three S3 cases.
    monkeypatch.setattr(
        FakeTorchVisionBackend,
        "detect_pose",
        lambda self, b: (
            RawPoseDetections()
            if b == negative_bytes
            else RawPoseDetections(
                person_boxes=[{"x_min": 1, "y_min": 1, "x_max": 20, "y_max": 20}],
                pose_keypoints=[[{"x": float(k), "y": float(k), "score": 0.9} for k in range(17)]],
                pose_scores=[0.9],
            )
        ),
    )
    opener = FakeOllamaOpener()
    client = OllamaClient(opener=opener)
    result = run_n2b2(
        config=config,
        s3_fixtures=s3,
        s20_fixtures=[],
        reasoning_schema=REASONING_SCHEMA,
        vision_schema=VISION_SCHEMA,
        n2b1p_sha="a" * 40,
        n2b1p_review_passed=True,
        start_head="b" * 40,
        ollama=client,
    )
    assert result.result == "N2B2_SYNTHETIC_SMOKE_VALIDATION_COMPLETE_AWAITING_OWNER_REVIEW"
    hc = result.summary["hard_counts"]
    assert hc["real_photo_read_count"] == 0
    assert hc["real_exif_read_count"] == 0
    assert hc["g1_source_access"] == 0
    assert hc["sqlite_write_count"] == 0
    assert result.summary["model_download_bytes"] == 0
    assert result.summary["torchvision_cache"][0]["verification_status"] == "CACHE_HIT"


def test_n2b2_blocked_without_review():
    config = _config()
    s3 = _s3_person_positive_fixtures()
    result = run_n2b2(
        config=config,
        s3_fixtures=s3,
        s20_fixtures=[],
        reasoning_schema=REASONING_SCHEMA,
        vision_schema=VISION_SCHEMA,
        n2b1p_sha="a" * 40,
        n2b1p_review_passed=False,
        start_head="b" * 40,
        ollama=OllamaClient(opener=FakeOllamaOpener()),
    )
    assert result.result == "N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED"


def test_n2b2_s3_fixture_insufficient(monkeypatch):
    config = _config()
    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.n2b2_synthetic.orchestrator.verify_cache_hit",
        _fake_cache_entries,
    )
    # Force zero persons for all fixtures -> no S3 positive case.
    monkeypatch.setattr(FakeTorchVisionBackend, "detect_pose", lambda self, b: RawPoseDetections())
    s3 = [
        SyntheticFixture(
            case_id=f"n2b2-s3-{i + 1:02d}",
            image_bytes=_make_png_bytes((i, i, i))[0],
            width=64,
            height=48,
        )
        for i in range(3)
    ]
    result = run_n2b2(
        config=config,
        s3_fixtures=s3,
        s20_fixtures=[],
        reasoning_schema=REASONING_SCHEMA,
        vision_schema=VISION_SCHEMA,
        n2b1p_sha="a" * 40,
        n2b1p_review_passed=True,
        start_head="b" * 40,
        ollama=OllamaClient(opener=FakeOllamaOpener()),
    )
    assert result.result == "N2B2_SYNTHETIC_FIXTURE_CAPABILITY_REQUIRES_DESIGN_REVIEW"


def test_n2b2_gpu_threshold_exceeded(monkeypatch):
    config = _config(gpu_limit=100, device="cuda")
    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.n2b2_synthetic.orchestrator.verify_cache_hit",
        _fake_cache_entries,
    )
    monkeypatch.setattr(MetricsCollector, "_gpu_allocated_mib", lambda self: 20000)
    s3 = _s3_person_positive_fixtures()
    negative_bytes = s3[2].image_bytes
    original_segment = FakeTorchVisionBackend.segment
    monkeypatch.setattr(
        FakeTorchVisionBackend,
        "segment",
        lambda self, b, role: (
            RawSegmentation() if b == negative_bytes else original_segment(self, b, role)
        ),
    )
    monkeypatch.setattr(
        FakeTorchVisionBackend,
        "detect_pose",
        lambda self, b: (
            RawPoseDetections()
            if b == negative_bytes
            else RawPoseDetections(
                person_boxes=[{"x_min": 1, "y_min": 1, "x_max": 20, "y_max": 20}],
                pose_keypoints=[[{"x": float(k), "y": float(k), "score": 0.9} for k in range(17)]],
                pose_scores=[0.9],
            )
        ),
    )
    result = run_n2b2(
        config=config,
        s3_fixtures=s3,
        s20_fixtures=[],
        reasoning_schema=REASONING_SCHEMA,
        vision_schema=VISION_SCHEMA,
        n2b1p_sha="a" * 40,
        n2b1p_review_passed=True,
        start_head="b" * 40,
        ollama=OllamaClient(opener=FakeOllamaOpener()),
    )
    assert result.result == "N2B2_GPU_LIMIT_EXCEEDED"
