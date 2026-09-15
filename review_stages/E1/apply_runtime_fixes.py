"""Apply Stage E1 only to exact, verified Stage D source bytes; no Git writes.

Default: check only. --apply: six explicitly listed source files. Run only in
an isolated worktree after its current remote handoff-stage identity is verified.
This does NOT run inference, approve a lease, or edit history/approvals/state.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path

BASE = "835007b3cf12cd19a23cbd476545a2d10cf49c50"
PACKAGE = "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/"
EXPECTED = {
    "controlled_runtime.py": "0b4fe00f7b57e3e9e934bbc4d769ad7c74b04e8008cace41f4baf4ba0a22af7e",
    "controlled_runtime_worker.py": "1a93951841d2b2723b81abf49c06412bd6c612905441c06ab1175cab714159e2",
    "orchestrator.py": "f5b5d2b8c974564a5b3104dd4738c6fdbf7efe75fb0a176e03128f687ebdf3ae",
    "s20_orchestrator.py": "511c8af9badc1cc1a30a57adbb9a8ffb3871dcd3704196c39066b93715b77ea1",
}


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("E1_PATCH_ANCHOR_MISMATCH")
    return text.replace(old, new, 1)


def patch_parent(text: str) -> str:
    text = once(text, '    command = [Path(sys.executable).name, "-c", _WORKER_CALL, "--mode", mode]\n',
                '    from .worker_dispatch import issue\n\n'
                '    envelope = issue(configuration, mode)\n'
                '    command = [Path(sys.executable).name, "-c", _WORKER_CALL, "--mode", mode]\n')
    text = once(text, '            input=canonical(configuration),', '            input=canonical(envelope),')
    text = once(text, '            "reviewed_commit": str(source["candidate_commit"]),\n',
                '            "reviewed_commit": str(source["candidate_commit"]),\n'
                '            "candidate_tree": str(source["candidate_tree"]),\n'
                '            "source_manifest_sha256": str(source["source_manifest_sha256"]),\n'
                '            "runtime_identity_sha256": sha256(\n'
                '                canonical(identity_observations[0]["identity"])\n'
                '            ),\n')
    text = once(text, '    require(bool(review_bytes), "NPI_REVIEW_ARTIFACT_EMPTY")\n',
                '    require(bool(review_bytes), "NPI_REVIEW_ARTIFACT_EMPTY")\n'
                '    from .legacy_s20_binding import validate_legacy_s20_binding\n\n'
                '    # Reject stale/mismatched historical inputs BEFORE ledger creation or S3.\n'
                '    validate_legacy_s20_binding(\n'
                '        root, prior_path, inputs["s20_manifest"] / "fixture_manifest.json"\n'
                '    )\n')
    text = once(text,
                '        observations.append(_observation("preflight", observed))\n',
                '')
    text = once(text,
                '            current_identity=observed,\n'
                '        )\n'
                '        return observed\n',
                '            current_identity=observed,\n'
                '        )\n'
                '        observations.append(_observation("preflight", observed))\n'
                '        return observed\n')
    return text


def patch_worker(text: str) -> str:
    text = once(text, 'import sys\n', 'import sys\nfrom contextlib import redirect_stdout\n')
    text = once(text, 'from .s20_orchestrator import run_s20\n',
                'from .s20_orchestrator import run_s20\n'
                'from .legacy_s20_binding import validate_legacy_s20_binding\n'
                'from .worker_dispatch import MAX_BYTES, assert_identity, assert_source, claim, finish\n')
    text = once(text,
                '    reviewed_commit = payload.get("reviewed_commit")\n'
                '    require(isinstance(reviewed_commit, str), "NPI_RUNNER_CONFIGURATION_INVALID")\n',
                '    # The historical review SHA and current execution SHA have different roles.\n'
                '    reviewed_commit = validate_legacy_s20_binding(\n'
                '        root, prior_review, s20_manifest / "fixture_manifest.json"\n'
                '    )\n')
    text = once(text, '    client = OllamaClient()\n    observations: list[dict[str, object]] = []\n',
                '    # Check all legacy S20 inputs before S3 can consume GPU work.\n'
                '    common = _common(payload)\n'
                '    client = OllamaClient()\n'
                '    observations: list[dict[str, object]] = []\n')
    text = once(text, '        observations.append(_observation(label, client.verify_identity()))\n',
                '        identity = client.verify_identity()\n'
                '        assert_identity(payload, _identity_record(identity))\n'
                '        observations.append(_observation(label, identity))\n')
    text = once(text, '    observe("before_s20")\n    common = _common(payload)\n',
                '    observe("before_s20")\n')
    text = once(text, '    observations = [_observation("before_resume", client.verify_identity())]\n',
                '    identity = client.verify_identity()\n'
                '    assert_identity(payload, _identity_record(identity))\n'
                '    observations = [_observation("before_resume", identity)]\n')
    text = once(text, '    observations.append(_observation("after_resume", client.verify_identity()))\n',
                '    identity = client.verify_identity()\n'
                '    assert_identity(payload, _identity_record(identity))\n'
                '    observations.append(_observation("after_resume", identity))\n')
    text = once(text,
                '    payload = strict_json(sys.stdin.buffer.read())\n'
                '    require(isinstance(payload, Mapping), "NPI_RUNNER_CONFIGURATION_INVALID")\n'
                '    _require_parent_reservation(payload)\n'
                '    result = _fresh(payload) if args.mode == "fresh" else _resume(payload)\n',
                '    data = sys.stdin.buffer.read(MAX_BYTES + 1)\n'
                '    require(len(data) <= MAX_BYTES, "NPI_DISPATCH_SIZE_LIMIT")\n'
                '    envelope = strict_json(data)\n'
                '    require(isinstance(envelope, Mapping), "NPI_RUNNER_CONFIGURATION_INVALID")\n'
                '    payload = claim(envelope, args.mode)\n'
                '    try:\n'
                '        _require_parent_reservation(payload)\n'
                '        from ..engineering.readiness import python_check\n'
                '        from ..engineering.source_identity import full_source_identity\n\n'
                '        require(\n'
                '            python_check(tuple(sys.version_info[:3]))["status"] == "PASS",\n'
                '            "NPI_UNSUPPORTED_PYTHON",\n'
                '        )\n'
                '        assert_source(payload, full_source_identity(_path(payload, "project_root")))\n'
                '        # Keep machine-readable stdout separate from runner diagnostics.\n'
                '        with redirect_stdout(sys.stderr):\n'
                '            result = _fresh(payload) if args.mode == "fresh" else _resume(payload)\n'
                '        finish(payload, args.mode, outcome="COMPLETE", result=result)\n'
                '    except Exception as exc:\n'
                '        finish(payload, args.mode, outcome="FAILED", result={"error_type": type(exc).__name__})\n'
                '        raise\n')
    return text


def patch_counter_producer(text: str) -> str:
    # Both producers are synthetic-only writers. This is their explicit scope
    # declaration, not an adapter default and not independent OS telemetry.
    return once(text,
                '        "app_write_count": 0,\n        "obsidian_write_count": 0,\n',
                '        "app_write_count": 0,\n'
                '        # This runner writes synthetic validation bundles only.\n'
                '        "production_bundle_count": 0,\n'
                '        "obsidian_write_count": 0,\n')


def planned_files(root: Path, delivery: Path) -> dict[Path, bytes]:
    planned: dict[Path, bytes] = {}
    for name, digest in EXPECTED.items():
        path = root / PACKAGE / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("E1_BASE_FILE_MISSING")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("E1_BASE_BYTES_CHANGED")
        text = data.decode("utf-8")
        if name == "controlled_runtime.py":
            changed = patch_parent(text)
        elif name == "controlled_runtime_worker.py":
            changed = patch_worker(text)
        else:
            changed = patch_counter_producer(text)
        ast.parse(changed, feature_version=(3, 12))
        planned[path] = changed.encode("utf-8")
    for name in ("worker_dispatch.py", "legacy_s20_binding.py"):
        path = root / PACKAGE / name
        if path.exists() or path.is_symlink():
            raise ValueError("E1_NEW_PATH_EXISTS")
        data = (delivery / "payload" / name).read_bytes()
        ast.parse(data.decode("utf-8"), feature_version=(3, 12))
        planned[path] = data
    return planned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        planned = planned_files(args.project_root, Path(__file__).resolve().parent)
        # Every anchor is checked before any target is written. The isolated
        # worktree can be discarded on I/O failure; no real runtime is involved.
        for path, data in planned.items():
            if args.apply:
                path.write_bytes(data)
            print(path.relative_to(args.project_root).as_posix(), hashlib.sha256(data).hexdigest())
    except (ValueError, OSError, SyntaxError) as exc:
        print(type(exc).__name__, str(exc) if isinstance(exc, ValueError) else "E1_APPLY_FAILED")
        return 1
    print("E1_APPLIED_NOT_QUALIFIED" if args.apply else "E1_CHECK_ONLY_NO_MUTATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
