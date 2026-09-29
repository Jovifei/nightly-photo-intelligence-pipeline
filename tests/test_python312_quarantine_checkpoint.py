from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _schema() -> dict:
    return json.loads(
        (ROOT / "schemas/python312_quarantine_checkpoint_v2.schema.json").read_text(
            encoding="utf-8"
        )
    )


def _checkpoint() -> dict:
    return json.loads(
        (ROOT / "research/python312_quarantine_checkpoint_v2.json").read_text(encoding="utf-8")
    )


def _errors(document: dict) -> list[str]:
    return [error.message for error in Draft202012Validator(_schema()).iter_errors(document)]


def test_quarantine_checkpoint_is_schema_valid_and_stopped() -> None:
    checkpoint = _checkpoint()
    assert _errors(checkpoint) == []
    assert checkpoint["quarantine"]["promotion"] == "NOT_RUN"
    assert checkpoint["quarantine"]["installation"] == "NOT_RUN"


def test_quarantine_checkpoint_rejects_manifest_or_count_drift() -> None:
    checkpoint = _checkpoint()
    forged = copy.deepcopy(checkpoint)
    forged["quarantine"]["manifest_sha256"] = "0" * 64
    forged["quarantine"]["wheel_count"] = 31
    errors = _errors(forged)
    assert any("was expected" in error or "30" in error for error in errors)


def test_quarantine_checkpoint_keeps_install_and_promotion_fail_closed() -> None:
    checkpoint = _checkpoint()
    forged = copy.deepcopy(checkpoint)
    forged["quarantine"]["promotion"] = "PASS"
    forged["quarantine"]["installation"] = "PASS"
    assert _errors(forged)
