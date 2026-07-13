#!/usr/bin/env python3
"""Offline, read-only verification for the agent handoff package."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []
warnings: list[str] = []
passes: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def ok(message: str) -> None:
    passes.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def load_json(rel: str) -> Any:
    path = ROOT / rel
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{rel}: cannot parse JSON: {exc}")
        return {}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_required_files() -> None:
    required = [
        "README_FIRST.md",
        "HANDOFF_INDEX.md",
        "MASTER_EXECUTION_CONTRACT.md",
        "AGENTS.md",
        "CLAUDE.md",
        "OPENCLAW.md",
        "PROJECT_CHARTER.md",
        "PROJECT_STATE.json",
        "OWNER_INPUTS_REQUIRED.md",
        "tasks/phase_n0_environment_scaffold.yaml",
        "schemas/photo_intelligence_item_v1.schema.json",
        "schemas/photo_intelligence_bundle_v1.schema.json",
        "fixtures/fixture_manifest.json",
        "tools/verify_handoff.py",
        "MANIFEST.sha256",
    ]
    missing = [rel for rel in required if not (ROOT / rel).is_file()]
    if missing:
        fail("missing required files: " + ", ".join(missing))
    else:
        ok("required files exist")


def check_authorization() -> None:
    state = load_json("PROJECT_STATE.json")
    try:
        assert state["authorization"]["phase"] == {"id": "N0", "status": "AUTHORIZED"}
        assert state["authorization"]["data_gate"] == {
            "id": "G0_THREE_SYNTHETIC_FIXTURES",
            "status": "AUTHORIZED",
        }
        assert state["authorization"]["real_photo_access"] == "NOT_AUTHORIZED"
        assert state["authorization"]["large_model_downloads"] == "NOT_AUTHORIZED"
        assert state["authorization"]["openclaw_activation"] == "NOT_AUTHORIZED"
        assert state["locked"]["phases"] == [f"N{i}" for i in range(1, 9)]
    except Exception:
        fail("PROJECT_STATE authorization is not the expected N0/G0-only state")
        return

    task_index = load_json("tasks/index.json")
    if len(task_index.get("authorized", [])) != 1:
        fail("tasks/index.json must authorize exactly one phase")
    elif task_index["authorized"][0].get("phase") != "N0":
        fail("tasks/index.json authorized phase must be N0")
    else:
        ok("only N0/G0 is authorized")

    n0 = (ROOT / "tasks/phase_n0_environment_scaffold.yaml").read_text(encoding="utf-8")
    if 'status: "AUTHORIZED"' not in n0 or "G0_THREE_SYNTHETIC_FIXTURES" not in n0:
        fail("N0 task does not contain expected authorization")
    for path in sorted((ROOT / "tasks").glob("phase_n[1-8]_*.yaml")):
        text = path.read_text(encoding="utf-8")
        if 'status: "LOCKED"' not in text:
            fail(f"{path.relative_to(ROOT)} is not locked")
    if not any("locked" in p.lower() for p in passes):
        ok("N1-N8 task files are locked")


def check_approval_templates() -> None:
    for path in sorted((ROOT / "approvals").glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        if 'status: "APPROVED"' in text:
            fail(f"approval template is accidentally approved: {path.relative_to(ROOT)}")
    ok("approval templates are not approvals")


def check_fixtures() -> None:
    manifest = load_json("fixtures/fixture_manifest.json")
    files = manifest.get("files", [])
    if len(files) != 3:
        fail(f"fixture manifest must contain exactly 3 files, got {len(files)}")
        return
    group: list[str] = []
    for entry in files:
        path = ROOT / "fixtures/three_image_smoke_set" / entry["name"]
        if not path.is_file():
            fail(f"missing fixture {entry['name']}")
            continue
        actual = sha256(path)
        if actual != entry["sha256"]:
            fail(f"fixture hash mismatch: {entry['name']}")
        if path.stat().st_size != entry["size_bytes"]:
            fail(f"fixture size mismatch: {entry['name']}")
        if entry.get("expected_exact_duplicate_group") == "dup-a":
            group.append(actual)
    if len(group) != 2 or len(set(group)) != 1:
        fail("expected exact duplicate fixture pair is not byte-identical")
    else:
        ok("three synthetic fixtures and duplicate relation verified")


def core_item_errors(item: dict[str, Any]) -> list[str]:
    out: list[str] = []
    required = {
        "schema_version",
        "asset_id",
        "source_reference",
        "observed_facts",
        "photographic_interpretation",
        "story_candidates",
        "pose_template",
        "director_prompts",
        "uncertainties",
        "review",
        "provenance",
        "output_hashes",
    }
    missing = required - set(item)
    if missing:
        out.append("missing:" + ",".join(sorted(missing)))
    source = item.get("source_reference", {})
    name = source.get("sanitized_name", "")
    if not isinstance(name, str) or "/" in name or "\\" in name or re.match(r"^[A-Za-z]:", name):
        out.append("absolute-or-unsanitized-source-name")
    review = item.get("review", {})
    if review.get("status") == "APPROVED" and review.get("approved_by_human") is not True:
        out.append("approved-without-human")
    producer = item.get("pose_template", {}).get("producer", {}).get("producer_type")
    if producer not in {"PROFESSIONAL_POSE_MODEL", "DETERMINISTIC_GEOMETRY"}:
        out.append("invalid-pose-producer")
    stories = item.get("story_candidates", {})
    if set(stories) != {"safe", "narrative", "dynamic"}:
        out.append("story-triplet-invalid")
    return out


def check_examples() -> None:
    valid = load_json("examples/valid/photo_intelligence_item_v1.json")
    if core_item_errors(valid):
        fail("valid item fails core rules: " + ", ".join(core_item_errors(valid)))
    else:
        ok("valid item passes core rules")

    expectations = {
        "item_absolute_path.json": "absolute-or-unsanitized-source-name",
        "item_auto_approved.json": "approved-without-human",
        "item_pose_from_vlm.json": "invalid-pose-producer",
    }
    for name, expected in expectations.items():
        item = load_json(f"examples/invalid/{name}")
        found = core_item_errors(item)
        if expected not in found:
            fail(f"{name} did not fail expected core rule {expected}; found {found}")
    ok("invalid examples fail expected core rules")

    # Optional full Draft 2020-12 validation.
    try:
        from jsonschema import Draft202012Validator  # type: ignore
        from referencing import Registry, Resource  # type: ignore

        schema_dir = ROOT / "schemas"
        item_schema = load_json("schemas/photo_intelligence_item_v1.schema.json")
        registry = Registry()
        for path in schema_dir.glob("*.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            if "$schema" not in schema:
                continue
            resource = Resource.from_contents(schema)
            if "$id" in schema:
                registry = registry.with_resource(schema["$id"], resource)
            registry = registry.with_resource(path.resolve().as_uri(), resource)
        validator = Draft202012Validator(item_schema, registry=registry)
        full_errors = sorted(validator.iter_errors(valid), key=lambda e: list(e.path))
        if full_errors:
            fail("full JSON Schema validation failed for valid item: " + "; ".join(e.message for e in full_errors[:5]))
        else:
            ok("valid item passes Draft 2020-12 validation")
        for name in expectations:
            invalid = load_json(f"examples/invalid/{name}")
            if not list(validator.iter_errors(invalid)):
                fail(f"{name} unexpectedly passes full JSON Schema")
        ok("invalid items are rejected by Draft 2020-12 validation")
    except ImportError:
        warn("jsonschema/referencing package not installed; full optional schema validation skipped")
    except Exception as exc:
        warn(f"full optional JSON Schema validation could not run in this environment: {exc}")

def check_bundle() -> None:
    bundle_root = ROOT / "examples/app_fixture_bundle_v1"
    bundle = load_json("examples/app_fixture_bundle_v1/bundle.json")
    items = bundle.get("items", [])
    if bundle.get("item_count") != len(items):
        fail("fixture bundle item_count mismatch")
    for item in items:
        path = bundle_root / item["item_path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            fail(f"fixture bundle item checksum mismatch: {item.get('item_path')}")
        if item.get("review_status") != "APPROVED":
            fail("fixture bundle contains non-approved manifest item")

    checksums_path = bundle_root / "CHECKSUMS.sha256"
    if not checksums_path.is_file():
        fail("fixture bundle missing CHECKSUMS.sha256")
    else:
        for line in checksums_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                expected, rel = line.split("  ", 1)
            except ValueError:
                fail(f"invalid checksum line: {line}")
                continue
            path = bundle_root / rel
            if not path.is_file() or sha256(path) != expected:
                fail(f"fixture bundle checksum mismatch: {rel}")
    ok("App fixture bundle checksums verified")



def check_yaml_files() -> None:
    try:
        import yaml  # type: ignore
    except ImportError:
        warn("PyYAML not installed; optional YAML syntax validation skipped")
        return
    bad: list[str] = []
    for path in ROOT.rglob("*.yaml"):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            bad.append(f"{path.relative_to(ROOT)}: {exc}")
    if bad:
        fail("YAML parse failures: " + " | ".join(bad))
    else:
        ok("all YAML files parse")

def check_json_files() -> None:
    bad = []
    for path in ROOT.rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            bad.append(f"{path.relative_to(ROOT)}: {exc}")
    if bad:
        fail("JSON parse failures: " + " | ".join(bad))
    else:
        ok("all JSON files parse")


def check_sensitive_and_large_files() -> None:
    private_key_markers = ["-----BEGIN " + "PRIVATE KEY-----", "-----BEGIN " + "OPENSSH PRIVATE KEY-----"]
    suspicious = []
    large = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name == "MANIFEST.sha256":
            continue
        size = path.stat().st_size
        if size > 5 * 1024 * 1024:
            large.append(f"{path.relative_to(ROOT)} ({size})")
        if path.suffix.lower() in {".png", ".zip"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(marker in text for marker in private_key_markers):
            suspicious.append(str(path.relative_to(ROOT)))
        # Detect likely real home paths, but allow documented placeholders and the intentional invalid fixture.
        if re.search(r"/home/(?!<)[A-Za-z0-9._-]+/", text):
            suspicious.append(str(path.relative_to(ROOT)))
        if re.search(r"C:\\\\Users\\\\(?!<|owner(?:\\\\|$))[A-Za-z0-9._-]+\\\\", text):
            suspicious.append(str(path.relative_to(ROOT)))
    if large:
        fail("unexpected files larger than 5 MiB: " + ", ".join(large))
    else:
        ok("no unexpected large files")
    if suspicious:
        fail("possible secret or personal absolute path: " + ", ".join(sorted(set(suspicious))))
    else:
        ok("no private keys or likely personal home paths detected")


def check_local_markdown_links() -> None:
    missing: set[str] = set()
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in link_re.findall(text):
            target = target.split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            candidate = (path.parent / target).resolve()
            try:
                candidate.relative_to(ROOT.resolve())
            except ValueError:
                missing.add(f"{path.relative_to(ROOT)} -> {target} (escape)")
                continue
            if not candidate.exists():
                missing.add(f"{path.relative_to(ROOT)} -> {target}")
    if missing:
        fail("broken local markdown links: " + "; ".join(sorted(missing)))
    else:
        ok("local Markdown links resolve")


def check_manifest() -> None:
    path = ROOT / "MANIFEST.sha256"
    if not path.is_file():
        fail("MANIFEST.sha256 missing")
        return
    listed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, rel = line.split("  ", 1)
        except ValueError:
            fail(f"invalid manifest line: {line}")
            continue
        listed[rel] = digest
    actual_files = {
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*")
        if p.is_file() and p.name != "MANIFEST.sha256"
    }
    if set(listed) != actual_files:
        missing = sorted(actual_files - set(listed))
        extra = sorted(set(listed) - actual_files)
        fail(f"manifest file set mismatch; missing={missing}, extra={extra}")
        return
    mismatches = [rel for rel, digest in listed.items() if sha256(ROOT / rel) != digest]
    if mismatches:
        fail("manifest hash mismatch: " + ", ".join(mismatches))
    else:
        ok("MANIFEST.sha256 verifies all package files")


def main() -> int:
    check_required_files()
    check_authorization()
    check_approval_templates()
    check_fixtures()
    check_json_files()
    check_yaml_files()
    check_examples()
    check_bundle()
    check_sensitive_and_large_files()
    check_local_markdown_links()
    check_manifest()

    print("NPI handoff verification")
    print("========================")
    for message in passes:
        print(f"PASS: {message}")
    for message in warnings:
        print(f"WARN: {message}")
    for message in errors:
        print(f"FAIL: {message}")
    print(f"Summary: {len(passes)} pass, {len(warnings)} warn, {len(errors)} fail")
    if errors:
        print("HANDOFF_INVALID: do not execute N0")
        return 1
    print("HANDOFF_VALID: N0/G0 only; all later phases remain locked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
