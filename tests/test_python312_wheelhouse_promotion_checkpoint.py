from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _schema() -> dict:
    return json.loads(
        (ROOT / "schemas/python312_wheelhouse_promotion_checkpoint_v2.schema.json").read_text(
            encoding="utf-8"
        )
    )


def _checkpoint() -> dict:
    return json.loads(
        (ROOT / "research/python312_wheelhouse_promotion_checkpoint_v2.json").read_text(
            encoding="utf-8"
        )
    )


def test_promotion_checkpoint_is_valid_and_install_stopped() -> None:
    errors = list(Draft202012Validator(_schema()).iter_errors(_checkpoint()))
    assert errors == []
    assert _checkpoint()["wheelhouse"]["promotion"] == "PASS"
    assert _checkpoint()["wheelhouse"]["installation"] == "NOT_RUN"


def test_promotion_checkpoint_rejects_identity_or_package_set_drift() -> None:
    forged = copy.deepcopy(_checkpoint())
    forged["wheelhouse"]["object_identity_sha256"] = "0" * 64
    assert list(Draft202012Validator(_schema()).iter_errors(forged))
    forged = copy.deepcopy(_checkpoint())
    forged["wheelhouse"]["package_set_sha256"] = "0" * 64
    assert list(Draft202012Validator(_schema()).iter_errors(forged))
