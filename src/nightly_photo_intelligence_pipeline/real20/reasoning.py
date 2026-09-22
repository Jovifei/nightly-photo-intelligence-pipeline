"""Local photography interpretation constrained by immutable v1.2 facts."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from ..engineering.common import canonical, sha256, strict_json
from ..n2b2_synthetic.ollama_client import OllamaClient
from ..n2b2_synthetic.qwen_reasoning import validate_reasoning
from .contracts import Real20Error


def interpret(
    data: bytes, facts: dict[str, Any], *, project_root: Path, expected_identity: dict[str, Any]
) -> dict[str, Any]:
    from dataclasses import asdict

    from ..n2b2_synthetic.qwen_fact_binding import bind_reasoning_schema

    client = OllamaClient()
    if asdict(client.verify_identity()) != expected_identity:
        raise Real20Error("REAL20_QWEN_IDENTITY_DRIFT")
    schema = strict_json(
        (project_root / "schemas/n2b2_photography_reasoning.schema.json").read_bytes()
    )
    schema = bind_reasoning_schema(
        schema,
        case_id=facts["case_id"],
        fact_digest=facts["fact_digest"],
        fact_ids=facts["fact_ids"],
    )
    before = sha256(canonical(facts))
    # Send only pixels to the already-local model; discard all original EXIF.
    pixels = BytesIO()
    with Image.open(BytesIO(data)) as image:
        rgb = image.convert("RGB")
        rgb.info.clear()
        rgb.save(pixels, format="PNG")
    try:
        response = client.reason(
            image_b64=base64.b64encode(pixels.getvalue()).decode("ascii"),
            case_id=facts["case_id"],
            vision_facts=facts,
            fact_digest=facts["fact_digest"],
            fact_ids=facts["fact_ids"],
            uncertainties=facts["uncertainties"],
            response_schema=schema,
        )
        validation = validate_reasoning(
            response,
            case_id=facts["case_id"],
            input_fact_digest=facts["fact_digest"],
            valid_fact_ids=facts["fact_ids"],
            schema=schema,
        )
        if not validation.ok or sha256(canonical(facts)) != before:
            raise Real20Error("REAL20_REASONING_CONTRACT_INVALID")
        if asdict(client.verify_identity()) != expected_identity:
            raise Real20Error("REAL20_QWEN_IDENTITY_DRIFT")
        return response
    finally:
        client.unload()
        if not client.verify_unloaded():
            raise Real20Error("REAL20_QWEN_UNLOAD_FAILED")
