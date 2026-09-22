import base64
import json
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from nightly_photo_intelligence_pipeline.n2b2_synthetic.ollama_client import (
    ModelIdentity,
    OllamaClient,
)
from nightly_photo_intelligence_pipeline.real20.contracts import Real20Error
from nightly_photo_intelligence_pipeline.real20.reasoning import interpret


@pytest.mark.parametrize("bad_digest", [False, True])
def test_real_ollama_request_and_validation_with_fake_transport(monkeypatch, bad_digest):
    identity = ModelIdentity(
        "qwen3.5:9b",
        "a" * 64,
        1,
        "gguf",
        "qwen",
        "9B",
        "Q4_K_M",
        ["vision"],
        "test",
        "test",
        "0.33.3",
    )
    monkeypatch.setattr(OllamaClient, "verify_identity", lambda self: identity)
    events = []

    def request(self, method, path, body=None):
        if path == "/api/ps":
            return {"models": []}
        if "images" not in body:
            events.append("unload")
            return {}
        with Image.open(BytesIO(base64.b64decode(body["images"][0]))) as image:
            assert not image.getexif()
        events.append("generate")
        response = {
            "schema_version": "1.0",
            "case_id": "real20-001",
            "input_fact_digest": ("b" if bad_digest else "a") * 64,
            "reasoning_based_on_fact_ids": ["fact-person-count"],
            "photographic_interpretation": {
                "scene_value": "medium",
                "composition_notes": "test",
                "lighting_notes": "test",
                "tone_notes": "test",
            },
            "story_candidates": {"safe": "a", "narrative": "b", "dynamic": "c"},
            "director_prompts": {"standard": "a", "dramatic": "b", "plan_b": "c", "technical": "d"},
            "uncertainties": [],
        }
        return {"response": json.dumps(response)}

    monkeypatch.setattr(OllamaClient, "_request", request)
    image = Image.new("RGB", (16, 16))
    exif = Image.Exif()
    exif[315] = "PRIVATE_AUTHOR"
    stream = BytesIO()
    image.save(stream, format="JPEG", exif=exif)
    facts = {
        "case_id": "real20-001",
        "fact_digest": "a" * 64,
        "fact_ids": ["fact-person-count"],
        "uncertainties": [],
    }
    args = {
        "project_root": Path(__file__).resolve().parents[1],
        "expected_identity": asdict(identity),
    }
    if bad_digest:
        with pytest.raises(Real20Error, match="REASONING_CONTRACT_INVALID"):
            interpret(stream.getvalue(), facts, **args)
    else:
        assert interpret(stream.getvalue(), facts, **args)["case_id"] == "real20-001"
    assert events == ["generate", "unload"]
