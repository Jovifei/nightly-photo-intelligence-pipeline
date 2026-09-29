from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def test_python312_qualification_checkpoint_is_closed_and_stopped() -> None:
    schema = json.loads(
        (ROOT / "schemas/python312_environment_qualification_checkpoint_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    checkpoint = json.loads(
        (ROOT / "research/python312_environment_qualification_checkpoint_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert list(Draft202012Validator(schema).iter_errors(checkpoint)) == []
    assert checkpoint["qualification"]["installed_distribution_count"] == 30
    assert checkpoint["qualification"]["pip_check"] == "PASS"
    assert checkpoint["qualification"]["network_access"] == "DENY"
    assert checkpoint["mandatory_stop"]["next_action"] == (
        "EXTERNAL_REVIEW_PY312_ENVIRONMENT_QUALIFICATION"
    )


def test_python312_qualification_checkpoint_rejects_evidence_drift() -> None:
    schema = json.loads(
        (ROOT / "schemas/python312_environment_qualification_checkpoint_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    checkpoint = json.loads(
        (ROOT / "research/python312_environment_qualification_checkpoint_v1.json").read_text(
            encoding="utf-8"
        )
    )
    checkpoint["evidence"]["qualification_sha256"] = "0" * 64
    assert list(Draft202012Validator(schema).iter_errors(checkpoint))
