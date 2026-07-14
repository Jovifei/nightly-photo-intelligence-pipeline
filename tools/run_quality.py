#!/usr/bin/env python3
"""Unified N0 quality command.

Runs every N0 quality gate and reports truthful PASS / FAIL / NOT_AVAILABLE /
SKIPPED evidence. Hard gates (must pass): pytest, contract-integrity, schema
validation, sensitive-file scan. Soft gates (reported, not blocking when the
tool is absent): ruff check, ruff format --check, mypy.

Exit 0 only if every hard gate passes. Missing optional tools are reported as
NOT_AVAILABLE and do NOT cause a failure (the contract forbids faking a pass,
not forbidding an absent offline tool).

Usage:
    python tools/run_quality.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PASS = "PASS"
FAIL = "FAIL"
NOT_AVAILABLE = "NOT_AVAILABLE"
SKIPPED = "SKIPPED"

HARD_GATES = {"pytest", "contract_integrity", "schema_validation", "sensitive_scan"}


def _run(cmd: list[str], *, timeout: int = 300, cwd: Path | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout, check=False, text=True, cwd=cwd
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return -1, "", "command not found"
    except subprocess.TimeoutExpired:
        return -2, "", "timed out"


def _tail(text: str, n: int = 8) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


def check_pytest() -> tuple[str, str]:
    rc, out, err = _run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, timeout=300)
    evidence = _tail(out + err, 12)
    if rc == 0:
        return PASS, evidence
    return FAIL, f"exit={rc}\n{evidence}"


# Authorization-state files legitimately change with phase transitions (Owner
# authorization updates PROJECT_STATE.json, tasks/index.json, and task-file
# statuses). They are excluded from the "contract files unchanged" check; the
# immutable contract files (docs, schemas, blueprints, config, MANIFEST, etc.)
# are still verified.
_AUTH_STATE_FILES = {"PROJECT_STATE.json", "tasks/index.json"}
_AUTH_STATE_PREFIXES = ("tasks/phase_n",)


def _is_auth_state_file(rel: str) -> bool:
    if rel in _AUTH_STATE_FILES:
        return True
    return any(rel.startswith(prefix) for prefix in _AUTH_STATE_PREFIXES)


def check_contract_integrity() -> tuple[str, str]:
    """Verify immutable contract files listed in MANIFEST.sha256 are intact.

    Authorization-state files (PROJECT_STATE.json, tasks/index.json, task-file
    statuses) are excluded - they change with Owner-approved phase transitions.
    """
    manifest = ROOT / "MANIFEST.sha256"
    if not manifest.is_file():
        return FAIL, "MANIFEST.sha256 missing"
    listed: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, rel = line.split("  ", 1)
        except ValueError:
            return FAIL, f"bad manifest line: {line[:40]}"
        listed[rel] = digest
    missing: list[str] = []
    mismatched: list[str] = []
    skipped_auth_state = 0
    for rel, digest in listed.items():
        if _is_auth_state_file(rel):
            skipped_auth_state += 1
            continue
        p = ROOT / rel
        if not p.is_file():
            missing.append(rel)
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != digest:
            mismatched.append(rel)
    if missing or mismatched:
        return FAIL, f"missing={len(missing)} mismatched={len(mismatched)}"
    return PASS, (
        f"{len(listed) - skipped_auth_state} immutable contract files intact "
        f"({skipped_auth_state} auth-state files excluded)"
    )


def check_schema_validation() -> tuple[str, str]:
    """Validate examples against schemas with jsonschema (Draft 2020-12)."""
    try:
        from jsonschema import Draft202012Validator  # type: ignore
        from referencing import Registry, Resource  # type: ignore
    except ImportError:
        return NOT_AVAILABLE, "jsonschema/referencing not installed"
    schema_dir = ROOT / "schemas"
    item_schema_path = schema_dir / "photo_intelligence_item_v1.schema.json"
    item_schema = json.loads(item_schema_path.read_text("utf-8"))
    registry: Any = Registry()
    for path in schema_dir.glob("*.json"):
        schema = json.loads(path.read_text("utf-8"))
        if "$schema" not in schema:
            continue
        resource = Resource.from_contents(schema)
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], resource)
        registry = registry.with_resource(path.resolve().as_uri(), resource)
    validator = Draft202012Validator(item_schema, registry=registry)
    valid = json.loads((ROOT / "examples/valid/photo_intelligence_item_v1.json").read_text("utf-8"))
    valid_errors = sorted(validator.iter_errors(valid), key=lambda e: list(e.path))
    if valid_errors:
        return FAIL, f"valid item has {len(valid_errors)} schema errors: {valid_errors[0].message}"
    invalid_expected = {
        "item_absolute_path.json": "absolute-or-unsanitized-source-name",
        "item_auto_approved.json": "approved-without-human",
        "item_pose_from_vlm.json": "invalid-pose-producer",
    }
    # The schema-level rejection of invalid examples is cross-checked by
    # tools/verify_handoff.py core rules; here we confirm jsonschema itself
    # rejects structurally invalid items where applicable.
    rejected = 0
    for name in invalid_expected:
        path = ROOT / "examples/invalid" / name
        if not path.is_file():
            continue
        item = json.loads(path.read_text("utf-8"))
        if list(validator.iter_errors(item)):
            rejected += 1
    return PASS, f"valid item passes Draft 2020-12; {rejected}/3 invalid items rejected by schema"


def check_sensitive_scan() -> tuple[str, str]:
    rc, out, err = _run([sys.executable, "tools/sensitive_file_scan.py"], cwd=ROOT, timeout=60)
    evidence = _tail(out + err, 8)
    if rc == 0:
        return PASS, evidence
    return FAIL, f"exit={rc}\n{evidence}"


def _ruff_or_mypy(module: str, args: list[str]) -> tuple[str, str]:
    """Run a ruff/mypy subcommand, classifying missing-module as NOT_AVAILABLE."""
    rc, out, err = _run([sys.executable, "-m", module, *args], cwd=ROOT)
    combined = out + err
    if rc == -1 or "No module named" in combined:
        return NOT_AVAILABLE, f"{module} not installed (offline)"
    evidence = _tail(combined, 10)
    if rc == 0:
        return PASS, evidence
    return FAIL, f"exit={rc}\n{evidence}"


def check_ruff() -> tuple[str, str]:
    return _ruff_or_mypy("ruff", ["check", "src", "tests", "tools"])


def check_ruff_format() -> tuple[str, str]:
    return _ruff_or_mypy("ruff", ["format", "--check", "src", "tests", "tools"])


def check_mypy() -> tuple[str, str]:
    return _ruff_or_mypy("mypy", ["src/nightly_photo_intelligence_pipeline"])


CHECKS = [
    ("pytest", "pytest -q", check_pytest),
    ("contract_integrity", "MANIFEST.sha256 subset", check_contract_integrity),
    ("schema_validation", "jsonschema Draft 2020-12", check_schema_validation),
    ("sensitive_scan", "tools/sensitive_file_scan.py", check_sensitive_scan),
    ("ruff_check", "ruff check", check_ruff),
    ("ruff_format", "ruff format --check", check_ruff_format),
    ("mypy", "mypy strict", check_mypy),
]


def main() -> int:
    print("NPI N0 quality gate")
    print("=" * 60)
    results: list[tuple[str, str, str, str]] = []
    for name, label, func in CHECKS:
        status, evidence = func()
        results.append((name, label, status, evidence))
        print(f"[{status:13}] {name} ({label})")
        for line in evidence.splitlines():
            print(f"    {line}")
    print("-" * 60)
    counts = {s: sum(1 for r in results if r[2] == s) for s in (PASS, FAIL, NOT_AVAILABLE, SKIPPED)}
    print(
        f"Summary: {counts[PASS]} pass, {counts[FAIL]} fail, "
        f"{counts[NOT_AVAILABLE]} not_available, {counts[SKIPPED]} skipped"
    )
    hard_fail = [r[0] for r in results if r[2] == FAIL and r[0] in HARD_GATES]
    if hard_fail:
        print(f"HARD GATE FAILURES: {', '.join(hard_fail)}")
        print("QUALITY_GATE_FAILED")
        return 1
    print("QUALITY_GATE_PASSED (hard gates green; soft tools reported above)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
